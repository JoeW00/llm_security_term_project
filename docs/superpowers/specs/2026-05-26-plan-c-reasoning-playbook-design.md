# 計畫 C：研判與劇本（Investigate + Playbook + Critique）設計 spec

> 建立日期：2026-05-26
> 負責子系統：P3 研判與劇本（Investigate + Playbook + Critique 反思迴圈）
> 對應節點：`soc_agent/nodes.investigate`、`nodes.playbook`、`nodes.critique`

---

## 1. 目標與範圍

把骨架中確定性的 `investigate` / `playbook` / `critique` 三個 stub，換成**雲端 LLM 驅動**
的研判與劇本核心：研判告警真偽（TP/FP）+ 信心度與理由、生成三階段處置劇本、並以
**評分式自我批判**驅動「不足就回頭重生」的反思迴圈。

**本 spec 採「整合邊界優先（integration-boundary-first）」策略**（同計畫 A）：先把可注入的
推理器（reasoner）介面、Pydantic 驗證輸出、離線確定性預設、節點替換、封閉反思迴圈與評估
框架立起來，讓真正的雲端 LLM 後端可**零下游改動**地插進來。實際的 live API 串接、prompt
調校、真實 rubric/準確率數字屬於**平行的研究／live 軌**，不在本範圍（見 §9）。

### 設計決策（brainstorming 已確認）

1. **整合邊界優先**：先落地可測試邊界，LLM 後端後插即可。
2. **`IncidentState` 加一個附加欄位 `rationale: str`**（只增不改）：`investigate` 寫入研判理由，
   供最終報告與稽核；劇本細節留在既有 `playbook` dict、批判結果留在既有 `critique` dict。
3. **批判用 rubric 評分 + 回饋進迴圈**：`critique` LLM 依 rubric（各階段完整性、可執行性、
   安全性）評分，全數過門檻才 `complete=True`，並附具體 issues；`playbook` 重生時讀取
   `state["critique"]["issues"]` 加以修正——真正的封閉反思迴圈。`MAX_CRITIQUE_ITERATIONS`（3）
   仍保證終止。

---

## 2. 模組佈局

```
soc_agent/
    reasoning.py                # 新增：LLMClient Protocol + Pydantic 結果模型 + parse_json 信任邊界
    reasoners/
        __init__.py
        investigator.py         # 新增：LLMInvestigator + RuleBasedInvestigator（預設）
        playbook.py             # 新增：LLMPlaybookGenerator + TemplatePlaybookGenerator（預設）
        critic.py               # 新增：LLMCritic + DeterministicCritic（預設）
        anthropic_client.py     # 新增：AnthropicLLMClient 轉接器（包注入的 SDK client；mock 測試）
    nodes.py                    # 修改 investigate / playbook / critique 改用注入的 reasoner
    graph.py                    # 修改 build_graph(... investigator / playbook_gen / critic ...)
    state.py                    # 修改：附加 rationale: str（只增不改）
eval/
    reasoning_eval.py           # 新增：verdict 準確率 + 劇本 rubric（LLM-as-judge）+ 反思收斂指標
```

---

## 3. 邊界契約（`soc_agent/reasoning.py`）

- **`LLMClient`（`typing.Protocol`）**：單一方法 `complete(self, *, system: str, prompt: str) -> str`。
  所有推理器共用此介面。測試注入 `FakeLLMClient`（腳本化回應）；正式注入 `AnthropicLLMClient`。

- **Pydantic 結果模型**（LLM 輸出的唯一合法型別，進入狀態前一律驗證）：
  - `Investigation`：`verdict: Verdict`（沿用 `state.Verdict`）、`confidence: float`（`0–1`）、`rationale: str`。
  - `PlaybookModel`：`containment: list[str]`、`eradication: list[str]`、`recovery: list[str]`。
  - `RubricScores`：`coverage: int`、`executability: int`、`safety: int`（各 `0–5`）。
  - `CritiqueModel`：`complete: bool`、`scores: RubricScores`、`issues: list[str]`。

- **`parse_json(text: str, model: type[BaseModelT]) -> BaseModelT`**：泛型信任邊界輔助。
  `json.loads` 後 `model.model_validate`；失敗（非 JSON、缺鍵、值越界）拋 `ValueError` 系
  例外，由呼叫端決定退路。集中於此一處便於安全審查。

**信任邊界（CLAUDE.md 規範）**：告警與情資欄位（`message`、`raw`、`indicators`、`enrichment`）
是**不可信輸入**，只放進清楚分隔的 user 區段，**絕不**進 system prompt；LLM 輸出一律經
`parse_json` 驗證；失敗時退回該節點的確定性預設推理器，不得污染狀態。

---

## 4. 推理器（`soc_agent/reasoners/`）

每個節點對應一個推理器介面（`typing.Protocol`），有兩種實作：**LLM 後端**與**確定性預設**。
三個介面方法（皆吃唯讀的 `state`，回傳已驗證的 Pydantic 模型）：
- `Investigator.assess(state: IncidentState) -> Investigation`
- `PlaybookGenerator.generate(state: IncidentState) -> PlaybookModel`
- `Critic.review(state: IncidentState) -> CritiqueModel`

### 4.1 Investigator（`investigator.py`）
- `LLMInvestigator(client: LLMClient)`：依 `alert` + `enrichment` + `attack_techniques` 建受限
  prompt，呼叫 LLM，`parse_json(..., Investigation)`，回傳 `Investigation`；失敗退回預設。
- `RuleBasedInvestigator`（**預設**，確定性）：沿用現有 stub 行為——`severity in (high, critical)
  → true_positive，否則 unknown`，`confidence=0.5`，`rationale` 為由 severity 推導的短字串。

### 4.2 PlaybookGenerator（`playbook.py`）
- `LLMPlaybookGenerator(client: LLMClient)`：依 `verdict` + `attack_techniques` + `enrichment`
  生成三階段劇本；**重生時讀取 `state["critique"]["issues"]`** 一併修正（封閉迴圈）。
  輸出經 `parse_json(..., PlaybookModel)`，回傳其 `model_dump()`；失敗退回預設。
- `TemplatePlaybookGenerator`（**預設**，確定性）：沿用現有三階段模板，忽略回饋（保持
  「剛好迴圈一次」測試的確定性）。

### 4.3 Critic（`critic.py`）
- `LLMCritic(client: LLMClient)`：依 `playbook`（與 `verdict`）以 rubric 評分，回傳
  `CritiqueModel`；全部維度過門檻才 `complete=True`，附 `issues`。失敗退回預設。
- `DeterministicCritic`（**預設**，確定性）：沿用現有行為——第一輪 `complete=False`（強制
  回頭重生一次），第二輪起 `complete=True`，保持既有迴圈測試與圖測試綠燈。

---

## 5. 節點與圖的變更

### 5.1 節點（`nodes.py`）
- `investigate(state, *, investigator: Investigator | None = None)`：呼叫
  `investigator.assess(state)`，把回傳的 `Investigation` 攤平成部分狀態
  `{"verdict", "confidence", "rationale"}`。預設 `RuleBasedInvestigator`。
- `playbook(state, *, generator: PlaybookGenerator | None = None)`：呼叫
  `generator.generate(state)`，回傳 `{"playbook": <PlaybookModel>.model_dump()}`。
  預設 `TemplatePlaybookGenerator`。
- `critique(state, *, critic: Critic | None = None)`：呼叫 `critic.review(state)`，回傳
  `{"critique": <CritiqueModel>.model_dump(), "critique_iterations": n+1}`。預設 `DeterministicCritic`。
- 三者皆遵守「只回傳更新鍵、不原地改 state」契約；模組層各放一個確定性預設單例。

### 5.2 圖（`graph.py`）
- `build_graph(investigator=None, playbook_gen=None, critic=None)`：以 `functools.partial`
  把各 reasoner 注入對應節點；裸呼叫（既有測試、CLI 預設）退回確定性預設。其餘節點與條件邊
  不變。**`routing.route_after_critique` 不需改動**——它仍讀 `critique["complete"]` 與
  `critique_iterations >= MAX_CRITIQUE_ITERATIONS`，`CritiqueModel` 保留 `complete` 鍵。

### 5.3 契約（`state.py`，只增不改）
- 新增一個 optional 鍵 `rationale: str`，由 `investigate` 寫入。不更動任何既有鍵。這是本計畫
  唯一一次受保護檔編輯（確認 hook 會提示一次）。

---

## 6. 封閉反思迴圈

1. 首輪：`state` 無 `critique` → `playbook` 從零生成。
2. `critique` 評分 → 寫 `critique = {complete, scores, issues}` 並 `critique_iterations += 1`。
3. `route_after_critique`：`complete` 或達 `MAX_CRITIQUE_ITERATIONS` → `human_approval`；否則 → `playbook`。
4. 重生：`LLMPlaybookGenerator` 讀 `state["critique"]["issues"]` 修正缺失（真正回饋）。確定性
   `TemplatePlaybookGenerator` 忽略回饋。
5. 終止保證：迭代計數遞增 + 上限 3（不變）。`DeterministicCritic` 預設第二輪即 `complete`，
   既有「剛好迴圈一次」測試維持綠燈；`LLMCritic` 最多跑 3 輪。

---

## 7. 測試策略（全部離線、確定性）

- **`reasoning.py`**：`parse_json` 對各模型驗證／拒絕（非法 `verdict`、`confidence` 越界、rubric
  分數越界）；Pydantic 模型契約測試。
- **各推理器**：LLM 實作以腳本化 `FakeLLMClient` 回合法 JSON → 驗證結果；畸形輸出 → 退回確定性
  預設；不可信告警文字只出現在分隔的 user prompt（system prompt 潔淨測試，同計畫 A）。
- **預設保留 stub**：既有 `test_investigate_*`、`test_playbook_*`、`test_critique_incomplete_then_complete`、
  圖的「剛好迴圈一次」與 CLI verdict 測試維持綠燈。
- **封閉迴圈**：腳本化 client 先回「不完整 + issues」再回「完整」→ 斷言重生 prompt 含先前
  issues 且迴圈收斂；「永不完整」client → 斷言迴圈停在 `MAX_CRITIQUE_ITERATIONS`。
- **注入**：`build_graph(investigator=…, playbook_gen=…, critic=…)` 以 fake 端到端接線。
- **`AnthropicLLMClient`**：mock 注入的 SDK client，斷言 system/prompt 對應與文字擷取；無 live 呼叫。

---

## 8. 評估（`eval/reasoning_eval.py`，離線）

- **Verdict 準確率**：對標註比對 TP/FP，計 precision/recall。
- **劇本 rubric（LLM-as-judge）**：以一個 judge `LLMClient` 對劇本評 coverage/executability/safety；
  以 fake judge 測試計分邏輯。
- **反思收斂**：iterations-to-complete 分佈（平均迭代數、N 輪內收斂比例）。純 Python、fixture 測試。

---

## 9. 不在本 spec 範圍（研究／live 軌另行處理）

live Anthropic API 串接進 CLI、真實 rubric/準確率數字、prompt 調校。全部接在本計畫交付的介面
後方，下游零改動。

---

## 10. 建置順序（TDD，每步可獨立測試）

1. `reasoning.py`（LLMClient Protocol + Pydantic 模型 + parse_json）**＋** `state.py` 附加 `rationale`。
2. `investigator.py`（RuleBased 預設 + LLM）。
3. `playbook.py`（Template 預設 + 讀取批判回饋的 LLM）。
4. `critic.py`（Deterministic 預設 + LLM rubric 評分）。
5. 接 `investigate`/`playbook`/`critique` 到注入 reasoner + `build_graph` 注入 + 封閉迴圈測試。
6. `anthropic_client.py` 轉接器（mock 測試）。
7. `eval/reasoning_eval.py`（verdict 準確率 + rubric judge + 收斂）。
8. 跑 `security-reviewer` + `langgraph-reviewer` subagent。

---

## 11. 相關文件

- 總體設計 spec：`docs/superpowers/specs/2026-05-24-soc-incident-response-agent-design.md`
- 計畫 A spec / plan：`docs/superpowers/specs/2026-05-26-plan-a-triage-classifier-design.md`、
  `docs/superpowers/plans/2026-05-26-plan-a-triage-classifier.md`（可注入介面 + 確定性預設 + 離線測試的範本）
- 共享契約：`soc_agent/state.py`（`IncidentState`、`Verdict`、`Severity`、`MAX_CRITIQUE_ITERATIONS`）
- 路由：`soc_agent/routing.py`（`route_after_critique`）
