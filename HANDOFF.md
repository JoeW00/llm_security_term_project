# 專案接手筆記（HANDOFF）

> 最後更新：2026-05-30
> 下次回來請先讀這份，就知道從哪裡開始。

---

## ⏭️ 下次在 Spark 要做的事：W15-P1 §C 全本地消融補跑（最優先）

> **背景**：W15-P1 個人進度報告（`docs/reports/2026-W15-P1-告警分流-個人進度報告.md`，**本機限定、
> gitignore 不進版控**）§6.3 消融原本缺第三臂。**決策（2026-05-30）：把原「雲端零樣本 Claude Haiku」
> 臂改為全本地兩臂**——理由是真實 SOC 工具把原始告警送外部雲端 API 本身是資料外洩／信任邊界疑慮，
> 全本地更貼合自託管 SOC 設計，且離線、免金鑰。`scripts/eval/run_ablation.py` 已改好（見下「已就緒」）。

### 要回答的兩個科學問題（兩臂各管一個）

1. **同基底 `qwen2.5:3b`（未微調）** → 隔離「微調」單一變因（與 `soc-triage` 同為 Qwen2.5-3B，
   差別僅 LoRA）。若它也坍縮成多數類 → 證明**微調沒把模型變更差**，坍縮源自資料。
2. **大模型 `qwen2.5:32b`** → 離線「能力上界」代理。若連它在匿名特徵上也接近 63% 基率／低 macro-F1
   → 確認是**資料集限制**（匿名特徵 + 類別不平衡）；若明顯較高 → 屬**微調／小模型容量**問題。

### 已就緒（本機已改好並（待）推上）

- `scripts/eval/run_ablation.py`：新增 `OllamaChat`（ChatClient，`complete`）+ 兩個本地零樣本臂
  `zero_shot_local_base`（`qwen2.5:3b`）、`zero_shot_local_large`（`qwen2.5:32b`），**預設即跑、
  無需金鑰**；雲端臂改為**可選**（設了 `ANTHROPIC_API_KEY` 才加）。模型名可用環境變數覆寫
  （`OLLAMA_BASE_MODEL` / `OLLAMA_LARGE_MODEL` / `OLLAMA_MODEL`）。四臂共用 `GRADE_SYSTEM_PROMPT`
  （明列 TP/BP/FP，使零樣本臂公平知道標籤空間）+ Pydantic 驗證 + 退回規則式。
- 報告 §6.3 已預先改框架（命名／角色／診斷措辭改成本地兩臂、表格留兩列 `⬜ 待跑`）。

### Spark 執行步驟（逐步照做）

```bash
# 0) 取得最新程式（本機改好的 run_ablation.py）。git pull 不需切帳號。
cd <專案根>
git pull            # 確認抓到 run_ablation.py 的本地零樣本臂改動

# 1) 前置：留出集與微調模型須已在（§A 策展 + §B ollama create 的產物）
ls data/triage/holdout.jsonl        # 1,000 筆；不在版控，須是 Spark 上 §A 既有產物
ollama list | grep soc-triage       # §B 已建立的微調模型

# 2) 起 ollama、拉兩個零樣本模型（首次 32b 約 ~20GB；Spark 128GB 統一記憶體可跑 q4）
ollama serve &
ollama pull qwen2.5:3b
ollama pull qwen2.5:32b

# 3) 跑完整消融（全本地、免金鑰）。存純文字 + 之後整理成 md/json 存檔。
uv run --group eval python scripts/eval/run_ablation.py | tee results/W15-P1-C-full-ablation.txt
#   預期輸出：=== alert_type === 後，每臂一行 acc=/macroF1= + per_class_f1 + confusion；
#   severity 會印「跳過」（GUIDE 無嚴重度真值）。
```

### 跑完後（回填與存檔）

1. 把 `rule_based` / `zero_shot_local_base` / `zero_shot_local_large` / `finetuned_local` 四臂的
   acc、macro-F1、混淆矩陣整理成 `results/W15-P1-C-full-ablation.md`（＋ `.json`），格式仿
   既有的 `results/W15-P1-C-partial-ablation.md`。**這些 results/ 檔有進版控**。
2. **依兩個診斷問題寫結論**：base 是否也坍縮（微調有無傷害）、32b 是否仍接近基率（資料限制 vs 容量）。
3. `git add results/W15-P1-C-full-ablation.*` → commit → **push（須 `gh auth switch --user JoeW00`）**。
4. 回**本機** Mac：`git pull` 取得 results；把兩列數字 + 結論貼回報告 §6.3（報告是本機限定檔，
   不在 Spark）。報告 §6.3 的 `⬜ 待跑` 兩列、§1 更新說明、§9、§10、§11 的「唯一未完項」屆時改成已完成。

### 可選加分（非必需）

- **雲端臂對照**：在 Spark `export ANTHROPIC_API_KEY=...` 後重跑同指令（會多出 `zero_shot_cloud`），
  與本地大模型對比。注意：會把告警送至外部 Anthropic API。
- **類別平衡重訓**：對訓練集重採樣成 TP/BP/FP 近等量再微調（《執行指南》§A.3），看 `true_positive`
  召回是否改善（需再用一次 Spark GPU）。

---

## 一句話現況

LangGraph 版「自主式 SOC Tier-1 事件回應代理」的**基礎骨架（計畫 0）已完成並合併到 `main`**，**計畫 A、C、D 三個整合邊界 + 計畫 D Streamlit Demo UI + 計畫 C 的真實 Anthropic LLM 接線都已完成並合併**，124 個測試全綠（離線、免金鑰）、CLI 可跑（含 `--llm`）、Demo 可互動展示（含 live LLM 切換）。唯一剩下的子系統是計畫 B（組員 2 進行中）；計畫 A 的 LoRA 微調訓練軌與「實跑 live 出評估數字」是需金鑰／資料的手動步驟（邊界皆已就緒、下游零改動）。

---

## 現在做到哪

| 項目 | 狀態 |
|---|---|
| 期末 handout 繁中翻譯 + 必做清單 | ✅ 完成（`docs/`） |
| 設計 spec（含 Mermaid 流程圖 + PDF） | ✅ 完成 |
| 計畫 0：基礎骨架實作計畫 | ✅ 完成 |
| 計畫 0：實作（7 個 task，Subagent 驅動 + 雙重審查） | ✅ 完成、已合併 `main` |
| Claude Code 自動化設定（hooks / subagents / skills / `.mcp.json`） | ✅ 完成、已合併 `main` |
| 計畫 A：告警分流（Ingest + Triage）整合邊界 | ✅ 完成、已合併 `main`（spec + plan + 6 task + 安全修補） |
| 計畫 C：研判與劇本（Investigate + Playbook + Critique）整合邊界 | ✅ 完成、已合併 `main`（spec + plan + 8 task + 安全修補） |
| 計畫 D：編排與安全（Human Approval + Report + 注入韌性）整合邊界 | ✅ 完成、已合併 `main`（spec + plan + 5 task + 安全修補） |
| 計畫 D Demo UI（Streamlit 互動展示） | ✅ 完成、已合併 `main`（spec + plan + 3 task + langgraph 審查） |
| 計畫 C LLM 軌：接真實 Anthropic 後端（韌性 + 工廠 + CLI + Demo 切換） | ✅ 完成、已合併 `main`（spec + plan + 6 task + 安全修補） |
| 計畫 B：Week 14 prototype（組員 2 起手） | 🟡 進行中 |

**git 狀態**：在 `main`（原 `master` 已改名）。本 session 全部工作（計畫 A/C/D + Demo UI + 計畫 C LLM 軌 + 各份 spec/plan/handoff）皆已 merge 並推上 `origin/main`；最後一個 feature merge 是 `425e1ae`（計畫 C LLM 軌 + uv.lock 同步），其後的 handoff 更新亦已推上。功能分支用完即刪。**已推上 GitHub（Private）**：`origin` → https://github.com/JoeW00/llm_security_term_project.git，`main` 追蹤 `origin/main`。注意推送需用 `JoeW00` gh 帳號（`gh auth switch --user JoeW00`）。**下次回來：先讀「下次從哪開始」段。**

**2026-05-26 這次 session 做了什麼**：
1. 合併組員 2 的 Week 14 prototype（`a246796`）：`enrich` / `attack_mapping` 初版 + 下載 MITRE ATT&CK STIX 資料到 `data/enterprise-attack.json`。
2. 合併 Claude Code 自動化設定分支。
3. 清理 `.gitignore`（補 `__pycache__/` / `*.pyc` / `.DS_Store`），並把誤入庫的 `soc_agent/__pycache__/*.pyc` 從版控移除。
4. **修掉組員 2 prototype 的契約 bug**（`fix/enrich-attackmap-honor-inputs` → 已併入 `main`）：原本兩個節點忽略輸入、回傳寫死 mock，導致 2 個契約測試失敗。現在 `enrich` 依 `state["iocs"]` 建 enrichment、`attack_mapping` 依告警內容比對關鍵字回傳 MITRE 技術 ID。25 測試恢復全綠。
5. **完成計畫 A（告警分流整合邊界）**（brainstorming → spec → plan → Subagent 驅動執行 6 task → 雙重審查 + `security-reviewer` / `langgraph-reviewer`，`feat/plan-a-triage` → 已併入 `main` `ea7f82d`）。新增可注入的 `Classifier` 邊界（`soc_agent/classifier.py`：`ClassificationResult` + Protocol + `RuleBasedClassifier`）、`triage` 改用注入分類器（`build_graph(classifier=...)` 經 `functools.partial` 注入，預設規則式）、`ingest` 強化 IOC 萃取、`OllamaClassifier` + 共用 LLM 信任邊界（`soc_agent/classifiers/`）、離線評估／消融框架（`eval/`）。`IncidentState` 不變。安全審查抓到並修掉一個 **ReDoS（domain 正則 catastrophic backtracking）**。測試 25 → 51 全綠。
6. **完成計畫 C（研判與劇本整合邊界）**（同樣 brainstorming → spec → plan → Subagent 驅動執行 8 task → 每步雙重審查 + `security-reviewer` / `langgraph-reviewer`，`feat/plan-c-reasoning` → 已併入 `main` `4e812e7`）。新增可注入的推理邊界（`soc_agent/reasoning.py`：`LLMClient` + `Investigator`/`PlaybookGenerator`/`Critic` Protocols + Pydantic 模型 + `parse_json`）、三個推理器（`soc_agent/reasoners/`：規則式/模板/確定性**預設**保留原 stub 行為，加 LLM 後端）、`AnthropicLLMClient` 轉接器、**封閉式 rubric 評分反思迴圈**（critique issues 回饋進 playbook 重生），離線評估（`eval/reasoning_eval.py`：verdict 準確率 + LLM-as-judge rubric + 收斂）。`IncidentState` 只加一個附加鍵 `rationale`。安全審查抓到並修掉一個 **二階提示注入 laundering**（critique 回饋原本在 `<<<CONTEXT>>>` 分隔區外，已移進區內）。測試 51 → 85 全綠。
7. **完成計畫 D（編排與安全整合邊界）**（同樣 brainstorming → spec → plan → Subagent 驅動執行 5 task → 每步雙重審查 + `security-reviewer` / `langgraph-reviewer`，`feat/plan-d-approval-security` → 已併入 `main` `87d3c97`）。新增可注入核准邊界（`soc_agent/approval.py`：`ApprovalDecision` + `ApprovalPolicy` Protocol + `AutoApprovePolicy` 預設 + `InterruptApprovalPolicy` 真 LangGraph `interrupt`）、`build_graph(approval_policy=…, checkpointer=…)`、Markdown+JSON 報告（`soc_agent/reporting.py`，帶出 rationale + 核准理由）、提示注入韌性評估與端到端指標（`eval/injection_eval.py`、`eval/runtime_metrics.py`）。`IncidentState` 只加一個附加鍵 `approval_reason`。安全審查抓到並修掉兩個問題：核准閘門原本用 Pydantic 寬鬆模式（`"true"`/`1` 會誤放行）→ 改 **strict 驗證、安全預設駁回**；`render_markdown` 對畸形型別加型別防護。Demo UI 依範圍另案。測試 85 → 107 全綠。**（注意：執行中曾短暫 detached HEAD，已把分支 ref 移正、無遺失。）**
8. **完成計畫 D Demo UI（Streamlit）**（brainstorming → spec → plan → Subagent 驅動執行 3 task → 審查 + `langgraph-reviewer`，`feat/plan-d-demo-ui` → 已併入 `main` `416c3e1`）。新增不依賴 streamlit 的 `demo/controller.py`（`IncidentSession` 包 `InterruptApprovalPolicy` + `MemorySaver` 的 start/resume、`injection_report` 確定性基線、樣本告警輔助；可離線單元測試）+ 薄層 `demo/app.py` Streamlit view + 可選 `demo` 依賴群組。後端用確定性預設、離線、免 API key；核心 112 測試在未裝 streamlit 下仍全跑。並把 `demo` 群組的 `uv.lock`（streamlit 相依）補提交。啟動：`uv run --group demo streamlit run demo/app.py`。測試 107 → 112 全綠。
9. **Demo UI 端到端實機驗證（用 `/browse` 驅動）**：選 `ssh_bruteforce.json` → Run → 在人工核准關卡暫停並顯示報告預覽（verdict=true_positive、T1110、三階段劇本、人工核准=None）→ 填理由按「駁回」→ resume 後最終報告 `approved=False` 且帶出核准理由 → 注入面板 `Run injection suite` 顯示 **manipulation rate 0%（total=3）**。確認 interrupt→resume 與安全閘門實際可用。操作備註：首次 `uv run --group demo …` 會下載安裝 streamlit 等約 31 個套件（已入 `uv.lock`）；確定性後端免 API key。
10. **完成計畫 C LLM 軌（接真實 Anthropic 後端）**（brainstorming → spec → plan → Subagent 驅動執行 6 task → 每步雙重審查 + `security-reviewer` / `langgraph-reviewer`，`feat/plan-c-llm-track` → 已併入 `main` `425e1ae`）。新增 `LLMClientError`（`reasoning.py`），`AnthropicLLMClient.complete` 把任何 live 失敗（網路／SDK／空回應）正規化成它、三個 reasoner 加捕捉 → **失敗退回確定性預設而非崩潰**；工廠 `soc_agent/reasoners/factory.py`（`anthropic_llm_client` 讀 `ANTHROPIC_API_KEY` + 延遲 import anthropic、`llm_reasoners`）；CLI `--llm`/`--model`；Demo「使用 live LLM」勾選框；`anthropic` 為可選 `llm` 依賴群組。全部離線可測（fake + 錯誤注入 + 無金鑰路徑），`anthropic` 不在模組載入時匯入。信任邊界不變。安全審查的預防性強化：`LLMClientError` 訊息改靜態（不回填 SDK 字串、避免日後外露洩漏），`from exc` 保留原因。測試 112 → 124 全綠。**實跑需金鑰**（見下）。

---

## 怎麼把專案跑起來（驗證環境還在）

```bash
cd "/Users/joseph/NTHU/114_02/114_02semester_LLM Security System/term_project"
uv sync                                   # 同步依賴（langgraph, pydantic, pytest）
uv run pytest -q                          # 應該 124 passed
uv run python -m soc_agent run data/sample_alerts/ssh_bruteforce.json   # 跑完整路徑（確定性）
uv run python -m soc_agent run data/sample_alerts/info_heartbeat.json   # 跑低風險旁路
uv run --group demo streamlit run demo/app.py                           # 啟動互動式 Demo UI
# 接真實 LLM（需金鑰）：
ANTHROPIC_API_KEY=... uv run --group llm python -m soc_agent run data/sample_alerts/ssh_bruteforce.json --llm
uv run --group demo --group llm streamlit run demo/app.py               # Demo 勾「使用 live LLM」
```

---

## 程式結構（已完成的骨架）

```
soc_agent/
    state.py        # IncidentState (TypedDict 契約) + Alert (Pydantic) + MAX_CRITIQUE_ITERATIONS=3
    nodes.py        # 9 個節點：A/C/D 已接可注入邊界（預設仍確定性）；enrich/attack_mapping 是 B 的 prototype
    routing.py      # route_after_triage(低風險旁路) + route_after_critique(反思迴圈)
    graph.py        # build_graph(classifier, investigator, playbook_gen, critic, approval_policy, checkpointer)
    __main__.py     # CLI: python -m soc_agent run <alert.json> [--llm --model ...]
data/sample_alerts/ # ssh_bruteforce.json(高風險) + info_heartbeat.json(低風險)
soc_agent/classifier.py   # 計畫 A：Classifier 邊界（ClassificationResult + Protocol + RuleBasedClassifier）
soc_agent/classifiers/    # 計畫 A：OllamaClassifier + 共用 LLM 信任邊界（prompts.py）
soc_agent/reasoning.py    # 計畫 C：LLMClient + Investigator/PlaybookGenerator/Critic Protocols + Pydantic 模型 + parse_json
soc_agent/reasoners/      # 計畫 C：investigator/playbook/critic（預設+LLM）+ anthropic_client 轉接器 + factory（live 接線）
soc_agent/approval.py     # 計畫 D：ApprovalPolicy + ApprovalDecision + AutoApprovePolicy + InterruptApprovalPolicy
soc_agent/reporting.py    # 計畫 D：render_markdown（純函式報告渲染）
eval/                     # 計畫 A：triage_eval.py + zero_shot.py；計畫 C：reasoning_eval.py；計畫 D：injection_eval.py + runtime_metrics.py
demo/                     # 計畫 D Demo UI：controller.py（不依賴 streamlit、可測）+ app.py（Streamlit view）
tests/              # 124 個測試（A/C/D 全部 + C LLM 軌：reasoner_llm_fallback/llm_factory + CLI --llm + demo 注入轉發）
```

流程：`ingest → triage → [route] → enrich → investigate → attack_mapping → playbook → [critique 迴圈] → human_approval → report`
- `[route]`：低風險告警直接旁路到 human_approval
- `[critique 迴圈]`：劇本不完整就回頭重生 playbook，stub 設計成剛好迴圈一次

---

## 下次從哪開始（建議順序）

**A/C/D 整合邊界 + 計畫 D Demo UI + 計畫 C 的真實 Anthropic 接線皆已完成。剩下的工作都是「接真實後端／資料／訓練」與「實跑出數字」——邊界已就緒、下游零改動：**
1. **計畫 B**（唯一還沒做整合邊界的子系統）：組員 2 接續把 enrich/attack_mapping 換成真實威脅情資工具呼叫 + 用 `data/enterprise-attack.json` 做檢索式 MITRE 對應。可仿 A/C/D 的可注入介面做法。
2. **計畫 A LLM／訓練軌**：LoRA 微調 + GGUF + `ollama create`、整理 GUIDE 資料集到 `data/triage/`、注入 `OllamaClassifier`、跑 `eval/triage_eval.py` 出消融數字（計畫 A spec §8）。這是最後一個還沒接 live 的軌。
3. **實跑 C/D 的 live 數字（需金鑰）**：`ANTHROPIC_API_KEY=... uv run --group llm python -m soc_agent run <alert> --llm` 已可直接跑真實推理。要出報告數字：把 live 圖／`anthropic_llm_client()`-backed reasoners 當 runner，跑 `eval/reasoning_eval.py`（verdict 準確率／rubric／收斂）、`eval/injection_eval.py` 或 `demo/controller.injection_report`（真實「防禦前後」注入操控率）、`eval/runtime_metrics.end_to_end_metrics`（延遲／迭代）。需標註資料集 + 網路 + 費用。

各子系統替換對應 stub 節點，彼此獨立：

| 計畫 | 負責人 | 替換的 stub | 狀態 / 重點 |
|---|---|---|---|
| **A（P1）** | — | `nodes.ingest` + `nodes.triage` | ✅ 整合邊界完成（可注入 `Classifier`、`OllamaClassifier`、`eval/`）。剩研究軌：LoRA 微調 + 資料集 + 真實消融數字 |
| **B（P2）** | 組員 2 | `nodes.enrich` + `nodes.attack_mapping` | 🟡 prototype 已起手：兩節點會吃輸入但仍回**確定性 mock**。下一步換成真實威脅情資工具呼叫（abuse.ch / AbuseIPDB）+ 用 `data/enterprise-attack.json` 做檢索式 MITRE 對應 |
| **C（P3）** | — | `nodes.investigate` + `nodes.playbook` + `nodes.critique` | ✅ 整合邊界 + 真實 Anthropic 接線完成（可注入推理器、`factory.anthropic_llm_client`/`llm_reasoners`、CLI `--llm`、Demo 切換、失敗退回韌性）。剩：帶金鑰實跑出評估數字 |
| **D（P4）** | — | `nodes.human_approval` + `nodes.report` | ✅ 整合邊界 + Streamlit Demo UI 完成（可注入 `ApprovalPolicy`、`InterruptApprovalPolicy`、Markdown 報告、`eval/injection_eval.py`、`demo/`）。剩：接 live 後出真實注入數字／延遲基準 |

替換邊界很乾淨：改 `nodes.py` 裡的函式（必要時加可注入的協作者），`IncidentState` 是穩定契約、新增欄位採「只增不改」。A/C/D 已示範乾淨做法：把 LLM／外部呼叫／人工關卡抽到可注入的介面後面（Protocol + 確定性預設 + Pydantic 驗證輸出 + 失敗退回安全預設），測試注入替身、保持離線。

**啟動方式**：下次回來可以說「為計畫 A／C 接真實 LLM」、「跑 Demo UI」或續做計畫 B。

---

## 重要設計決策（審查時確認過，別again 翻案）

1. **`IncidentState["alert"]` 用 `dict[str, Any]` 而非 `Alert` 模型**：LangGraph 把 state 序列化成純 dict，模型不能直接放進去。`ingest` 節點用 `Alert.model_validate()` 在入口驗證。這是正確的 LangGraph 模式。
2. **`Alert.timestamp` 用 `str`**：便於 JSON round-trip 與符合告警來源格式。
3. **編排主腦用雲端 API、只有 triage 節點用微調本地模型**：同時滿足「本地模型 + 微調 + 時間可控」，微調只鎖定「告警分類」這個窄任務。
4. **架構選 B（單圖多節點 + 反思迴圈），不是多代理 Supervisor（C）**：3 週時間風險可控，仍完整展示 LangGraph 價值。

---

## 待辦 / 前瞻備註（給計畫 B 與 A/C/D 的 LLM／Demo／資料軌實作者）

- **計畫 A 研究軌注意**：整合邊界已就緒，接微調模型時 (1) 把訓練好的模型 `ollama create` 後，在 CLI／組裝處注入 `OllamaClassifier(ollama_client, "soc-triage")`（目前 `build_graph()` 預設規則式）；(2) 評估資料放 `data/triage/*.jsonl`（格式：每行 `{"alert": {...}, "expected": {"alert_type":..., "severity":...}}`）；(3) 用 `eval/triage_eval.py` 的 `ablation()` 跑微調 vs `ZeroShotClassifier` 消融；(4) `ClassificationResult.confidence` 目前不寫入 `IncidentState`（只供評估）——若路由要用，再走「只增不改」加欄位。(5) 提醒：`ingest` 的 IOC regex 已防 ReDoS（有界標籤 + `_MAX_MESSAGE_LEN` 截斷），改 regex 時別退回巢狀量詞。
- **計畫 B 注意**：`enrich` / `attack_mapping` 雖然已會吃輸入，但回的是寫死的確定性 mock；換成真實工具呼叫時，記得 (1) 外部 API 結果落地快取以利重現、(2) 測試維持離線（patch / 注入），(3) `attack_techniques` 目前存「裸技術 ID」（如 `"T1110"`）以通過 `"T1110" in list` 的成員檢查——若要改成 `"T1110 - Brute Force"` 形式，需同步調整 `tests/test_cli.py`。STIX 來源已在 `data/enterprise-attack.json`。可參考計畫 A 的「可注入介面 + 確定性預設 + 離線測試」做法。
- **計畫 C LLM 軌（已完成接線）**：真實後端已接好——`soc_agent/reasoners/factory.py` 的 `anthropic_llm_client()`（讀 `ANTHROPIC_API_KEY`、延遲 import）+ `llm_reasoners(client)`，CLI `--llm`、Demo「使用 live LLM」勾選框皆可用。韌性已補：任何 live 失敗（網路／SDK／空回應）→ `LLMClientError` → reasoner 退回確定性預設（不崩潰）。剩下只差**帶金鑰實跑出評估數字**（見上「下次從哪開始」#3）。仍適用的設計守則：`LLMCritic` 的 `complete` 由 rubric 門檻（`_RUBRIC_PASS=4`）重算、不信任模型旗標；playbook 重生的 critique 回饋在 `<<<CONTEXT>>>` 區段內（安全修補），別搬回區外；`LLMClientError` 訊息保持靜態（別回填 SDK 字串）。
- **計畫 D Demo UI（已完成）+ live 切換**：互動 Demo 在 `demo/`（`uv run --group demo streamlit run demo/app.py`）；編排在不依賴 streamlit 的 `demo/controller.py`（`IncidentSession`）。**live LLM 已可在 Demo 直接切換**：勾「使用 live LLM」會由 `app.py` 呼叫工廠建 reasoners 傳給 `IncidentSession(reasoners=…)`（同時 `--group demo --group llm`、設好金鑰）。守則不變：(1) UI 的人工核准送 `Command(resume={"approved": bool, "reason": str})`，`approved` 必須是**真 bool**（strict 驗證，`"true"`/`1` 會被當畸形而保守駁回）；(2) `InterruptApprovalPolicy.decide` 在 `interrupt()` 前無副作用、可安全 replay——**未來若把真實處置動作放進 human_approval，務必擺在 `interrupt()` 之後**；(3) 真實注入「防禦前後」數字：把 runner 換成 live 圖。
- **報告 rationale**（已解決）：計畫 D 的 `report` 已把 `rationale` + `approval_reason` + Markdown 帶進 `final_report`。
- **低風險旁路 verdict**：低風險旁路時 `final_report["verdict"]` 仍是 `None`（跳過 investigate）。要決定這是不是預期 sentinel，或改成預設 `"unknown"`（任一實作者都可處理）。
- **CLI**：`run()` 目前對壞掉的告警 JSON 會丟出 Pydantic `ValidationError` 原始 traceback；要不要加友善錯誤訊息可一併在 Demo/CLI 軌處理。
- **遺留死碼**：`soc_agent/nodes.py` 底部的 `if __name__ == "__main__"` mockup 區塊（組員留的、含「看你們需不需要…」註解）參照不存在的 `raw_message` 欄位、跑起來會壞。多次審查都點到——**請組員確認後刪除**（非本批變更引入，故未動）。
- **資料**：spec 規劃以 **Microsoft GUIDE / Security Incident Prediction** 公開資料集為主錨（含真實 TP/FP 分流標籤），支撐 P1 微調與 P3 研判。所有外部 API 查詢結果記得落地快取以利重現。

---

## 相關文件位置

- 設計 spec：`docs/superpowers/specs/2026-05-24-soc-incident-response-agent-design.md`（+ `.pdf`、`assets/soc-agent-flow.png`）
- 計畫 0：`docs/superpowers/plans/2026-05-24-soc-agent-foundation.md`
- 計畫 A spec：`docs/superpowers/specs/2026-05-26-plan-a-triage-classifier-design.md`
- 計畫 A plan：`docs/superpowers/plans/2026-05-26-plan-a-triage-classifier.md`
- 計畫 C spec：`docs/superpowers/specs/2026-05-26-plan-c-reasoning-playbook-design.md`
- 計畫 C plan：`docs/superpowers/plans/2026-05-26-plan-c-reasoning-playbook.md`
- 計畫 D spec：`docs/superpowers/specs/2026-05-26-plan-d-approval-security-design.md`
- 計畫 D plan：`docs/superpowers/plans/2026-05-26-plan-d-approval-security.md`
- 計畫 D Demo UI spec：`docs/superpowers/specs/2026-05-26-plan-d-demo-ui-design.md`
- 計畫 D Demo UI plan：`docs/superpowers/plans/2026-05-26-plan-d-demo-ui.md`
- 計畫 C LLM 軌 spec：`docs/superpowers/specs/2026-05-26-plan-c-llm-track-design.md`
- 計畫 C LLM 軌 plan：`docs/superpowers/plans/2026-05-26-plan-c-llm-track.md`
- handout 翻譯：`docs/期末專題說明_繁體中文翻譯.md`
- 必做清單：`docs/期末專題_必做項目清單.md`

## 課程里程碑提醒

- 第 14 週：個人進度報告（3 頁起、6 頁達優異）
- 第 15 週：個人進度報告（評估指標、微調腳本）
- 第 16 週：團隊最終整合報告 + PoC 成果物
