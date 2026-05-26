# 專案接手筆記（HANDOFF）

> 最後更新：2026-05-26
> 下次回來請先讀這份，就知道從哪裡開始。

---

## 一句話現況

LangGraph 版「自主式 SOC Tier-1 事件回應代理」的**基礎骨架（計畫 0）已完成並合併到 `main`**，**計畫 A（告警分流）與計畫 C（研判與劇本）整合邊界也已完成並合併**，85 個測試全綠、CLI 可跑。剩下計畫 B（進行中）、D。

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
| 計畫 B：Week 14 prototype（組員 2 起手） | 🟡 進行中 |
| 計畫 D | ⬜ 尚未開始 |

**git 狀態**：在 `main`（原 `master` 已改名），最新是 merge commit `4e812e7`（計畫 C）。功能分支用完即刪。**已推上 GitHub（Private）**：`origin` → https://github.com/JoeW00/llm_security_term_project.git，`main` 追蹤 `origin/main`。注意推送需用 `JoeW00` gh 帳號（`gh auth switch --user JoeW00`）。

**2026-05-26 這次 session 做了什麼**：
1. 合併組員 2 的 Week 14 prototype（`a246796`）：`enrich` / `attack_mapping` 初版 + 下載 MITRE ATT&CK STIX 資料到 `data/enterprise-attack.json`。
2. 合併 Claude Code 自動化設定分支。
3. 清理 `.gitignore`（補 `__pycache__/` / `*.pyc` / `.DS_Store`），並把誤入庫的 `soc_agent/__pycache__/*.pyc` 從版控移除。
4. **修掉組員 2 prototype 的契約 bug**（`fix/enrich-attackmap-honor-inputs` → 已併入 `main`）：原本兩個節點忽略輸入、回傳寫死 mock，導致 2 個契約測試失敗。現在 `enrich` 依 `state["iocs"]` 建 enrichment、`attack_mapping` 依告警內容比對關鍵字回傳 MITRE 技術 ID。25 測試恢復全綠。
5. **完成計畫 A（告警分流整合邊界）**（brainstorming → spec → plan → Subagent 驅動執行 6 task → 雙重審查 + `security-reviewer` / `langgraph-reviewer`，`feat/plan-a-triage` → 已併入 `main` `ea7f82d`）。新增可注入的 `Classifier` 邊界（`soc_agent/classifier.py`：`ClassificationResult` + Protocol + `RuleBasedClassifier`）、`triage` 改用注入分類器（`build_graph(classifier=...)` 經 `functools.partial` 注入，預設規則式）、`ingest` 強化 IOC 萃取、`OllamaClassifier` + 共用 LLM 信任邊界（`soc_agent/classifiers/`）、離線評估／消融框架（`eval/`）。`IncidentState` 不變。安全審查抓到並修掉一個 **ReDoS（domain 正則 catastrophic backtracking）**。測試 25 → 51 全綠。
6. **完成計畫 C（研判與劇本整合邊界）**（同樣 brainstorming → spec → plan → Subagent 驅動執行 8 task → 每步雙重審查 + `security-reviewer` / `langgraph-reviewer`，`feat/plan-c-reasoning` → 已併入 `main` `4e812e7`）。新增可注入的推理邊界（`soc_agent/reasoning.py`：`LLMClient` + `Investigator`/`PlaybookGenerator`/`Critic` Protocols + Pydantic 模型 + `parse_json`）、三個推理器（`soc_agent/reasoners/`：規則式/模板/確定性**預設**保留原 stub 行為，加 LLM 後端）、`AnthropicLLMClient` 轉接器、**封閉式 rubric 評分反思迴圈**（critique issues 回饋進 playbook 重生），離線評估（`eval/reasoning_eval.py`：verdict 準確率 + LLM-as-judge rubric + 收斂）。`IncidentState` 只加一個附加鍵 `rationale`。安全審查抓到並修掉一個 **二階提示注入 laundering**（critique 回饋原本在 `<<<CONTEXT>>>` 分隔區外，已移進區內）。測試 51 → 85 全綠。

---

## 怎麼把專案跑起來（驗證環境還在）

```bash
cd "/Users/joseph/NTHU/114_02/114_02semester_LLM Security System/term_project"
uv sync                                   # 同步依賴（langgraph, pydantic, pytest）
uv run pytest -q                          # 應該 85 passed
uv run python -m soc_agent run data/sample_alerts/ssh_bruteforce.json   # 跑完整路徑
uv run python -m soc_agent run data/sample_alerts/info_heartbeat.json   # 跑低風險旁路
```

---

## 程式結構（已完成的骨架）

```
soc_agent/
    state.py        # IncidentState (TypedDict 契約) + Alert (Pydantic) + MAX_CRITIQUE_ITERATIONS=3
    nodes.py        # 9 個確定性 stub 節點 ← 計畫 A–D 的替換點
    routing.py      # route_after_triage(低風險旁路) + route_after_critique(反思迴圈)
    graph.py        # build_graph() 組裝 StateGraph
    __main__.py     # CLI: python -m soc_agent run <alert.json>
data/sample_alerts/ # ssh_bruteforce.json(高風險) + info_heartbeat.json(低風險)
soc_agent/classifier.py   # 計畫 A：Classifier 邊界（ClassificationResult + Protocol + RuleBasedClassifier）
soc_agent/classifiers/    # 計畫 A：OllamaClassifier + 共用 LLM 信任邊界（prompts.py）
soc_agent/reasoning.py    # 計畫 C：LLMClient + Investigator/PlaybookGenerator/Critic Protocols + Pydantic 模型 + parse_json
soc_agent/reasoners/      # 計畫 C：investigator/playbook/critic（預設+LLM）+ anthropic_client 轉接器
eval/                     # 計畫 A：triage_eval.py + zero_shot.py；計畫 C：reasoning_eval.py（verdict/rubric/收斂）
tests/              # 85 個測試（骨架 + 計畫 A：classifier/triage_injection/ingest_iocs/ollama/triage_eval + 計畫 C：reasoning/investigator/playbook_reasoner/critic/reasoning_nodes/anthropic_client/reasoning_eval）
```

流程：`ingest → triage → [route] → enrich → investigate → attack_mapping → playbook → [critique 迴圈] → human_approval → report`
- `[route]`：低風險告警直接旁路到 human_approval
- `[critique 迴圈]`：劇本不完整就回頭重生 playbook，stub 設計成剛好迴圈一次

---

## 下次從哪開始（建議順序）

**計畫 A、C 整合邊界皆已完成。下一步可選：**
1. **為計畫 D 寫實作計畫**（最後一個未動的子系統）：`human_approval` 的 LangGraph interrupt 人工關卡、提示注入韌性評估、Demo UI、報告整合。走 brainstorming → writing-plans → subagent 驅動執行。
2. **計畫 A／C 的 LLM／訓練軌**（邊界已就緒，下游零改動）：
   - A：LoRA 微調 + GGUF + `ollama create`、整理 GUIDE 資料集到 `data/triage/`、跑 `eval/triage_eval.py` 出消融數字（計畫 A spec §8）。
   - C：把真 Anthropic client 經 `AnthropicLLMClient` 注入 `build_graph(investigator=…, playbook_gen=…, critic=…)`、跑 `eval/reasoning_eval.py` 出 verdict 準確率／rubric／收斂數字（計畫 C spec §9）。
3. **計畫 B**：組員 2 接續把 enrich/attack_mapping 換成真實工具呼叫。

各子系統替換對應 stub 節點，彼此獨立、可並行（4 位成員一人一個）：

| 計畫 | 負責人 | 替換的 stub | 狀態 / 重點 |
|---|---|---|---|
| **A（P1）** | — | `nodes.ingest` + `nodes.triage` | ✅ 整合邊界完成（可注入 `Classifier`、`OllamaClassifier`、`eval/`）。剩研究軌：LoRA 微調 + 資料集 + 真實消融數字 |
| **B（P2）** | 組員 2 | `nodes.enrich` + `nodes.attack_mapping` | 🟡 prototype 已起手：兩節點會吃輸入但仍回**確定性 mock**。下一步換成真實威脅情資工具呼叫（abuse.ch / AbuseIPDB）+ 用 `data/enterprise-attack.json` 做檢索式 MITRE 對應 |
| **C（P3）** | — | `nodes.investigate` + `nodes.playbook` + `nodes.critique` | ✅ 整合邊界完成（可注入 `Investigator`/`PlaybookGenerator`/`Critic`、`AnthropicLLMClient`、封閉反思迴圈、`eval/reasoning_eval.py`）。剩 LLM 軌：接真 client + 真實評估數字 |
| **D（P4）** | — | `nodes.human_approval` | ⬜ LangGraph interrupt 人工關卡、提示注入韌性評估、Demo UI、報告整合 |

替換邊界很乾淨：改 `nodes.py` 裡的函式（必要時加可注入的協作者），`IncidentState` 是穩定契約、新增欄位採「只增不改」。計畫 A、C 已示範乾淨做法：把 LLM／外部呼叫抽到可注入的介面後面（Protocol + 確定性預設 + Pydantic 驗證輸出 + 失敗退回預設），測試注入替身、保持離線。

**啟動方式**：下次回來可以說「為計畫 D 寫實作計畫」或「開始計畫 A／C 的 LLM 訓練軌」。

---

## 重要設計決策（審查時確認過，別again 翻案）

1. **`IncidentState["alert"]` 用 `dict[str, Any]` 而非 `Alert` 模型**：LangGraph 把 state 序列化成純 dict，模型不能直接放進去。`ingest` 節點用 `Alert.model_validate()` 在入口驗證。這是正確的 LangGraph 模式。
2. **`Alert.timestamp` 用 `str`**：便於 JSON round-trip 與符合告警來源格式。
3. **編排主腦用雲端 API、只有 triage 節點用微調本地模型**：同時滿足「本地模型 + 微調 + 時間可控」，微調只鎖定「告警分類」這個窄任務。
4. **架構選 B（單圖多節點 + 反思迴圈），不是多代理 Supervisor（C）**：3 週時間風險可控，仍完整展示 LangGraph 價值。

---

## 待辦 / 前瞻備註（給計畫 B/D 與 A/C LLM 軌實作者）

- **計畫 A 研究軌注意**：整合邊界已就緒，接微調模型時 (1) 把訓練好的模型 `ollama create` 後，在 CLI／組裝處注入 `OllamaClassifier(ollama_client, "soc-triage")`（目前 `build_graph()` 預設規則式）；(2) 評估資料放 `data/triage/*.jsonl`（格式：每行 `{"alert": {...}, "expected": {"alert_type":..., "severity":...}}`）；(3) 用 `eval/triage_eval.py` 的 `ablation()` 跑微調 vs `ZeroShotClassifier` 消融；(4) `ClassificationResult.confidence` 目前不寫入 `IncidentState`（只供評估）——若路由要用，再走「只增不改」加欄位。(5) 提醒：`ingest` 的 IOC regex 已防 ReDoS（有界標籤 + `_MAX_MESSAGE_LEN` 截斷），改 regex 時別退回巢狀量詞。
- **計畫 B 注意**：`enrich` / `attack_mapping` 雖然已會吃輸入，但回的是寫死的確定性 mock；換成真實工具呼叫時，記得 (1) 外部 API 結果落地快取以利重現、(2) 測試維持離線（patch / 注入），(3) `attack_techniques` 目前存「裸技術 ID」（如 `"T1110"`）以通過 `"T1110" in list` 的成員檢查——若要改成 `"T1110 - Brute Force"` 形式，需同步調整 `tests/test_cli.py`。STIX 來源已在 `data/enterprise-attack.json`。可參考計畫 A 的「可注入介面 + 確定性預設 + 離線測試」做法。
- **計畫 C LLM 軌注意**：邊界已就緒。接真模型時 (1) 把 `anthropic.Anthropic()` 經 `AnthropicLLMClient(client, "claude-...")` 包好，分別注入 `LLMInvestigator`/`LLMPlaybookGenerator`/`LLMCritic`，再傳進 `build_graph(investigator=…, playbook_gen=…, critic=…)`（CLI 預設仍走確定性）；(2) `LLMCritic` 的 `complete` 由 rubric 門檻（`_RUBRIC_PASS=4`）重算、不信任模型旗標——別退回直接信任 LLM；(3) **未捕捉的 transport/SDK 例外**：reasoner 的 `except (KeyError, TypeError, ValueError)` 只擋輸出解析錯誤，接真 client 時要處理 `ConnectionError` 等網路例外與畸形回應（`IndexError`/`AttributeError`）；(4) playbook 重生的 critique 回饋已放進 `<<<CONTEXT>>>` 區段內（安全修補），別搬回區外。
- **計畫 D 注意（報告）**：計畫 C 已把研判理由寫進 `state["rationale"]`，但 `report` 節點的 `final_report` 還沒帶出來；計畫 D 補一行 `"rationale": state.get("rationale", "")` 即可surfacing。
- **計畫 D 注意**：`investigate` 預設只在 `high/critical → true_positive`；低風險旁路時 `final_report["verdict"]` 目前是 `None`（跳過 investigate）。要決定這是不是預期 sentinel，或改成預設 `"unknown"`。
- **CLI**：`run()` 目前對壞掉的告警 JSON 會丟出 Pydantic `ValidationError` 原始 traceback；要不要加友善錯誤訊息可在計畫 D 處理。
- **資料**：spec 規劃以 **Microsoft GUIDE / Security Incident Prediction** 公開資料集為主錨（含真實 TP/FP 分流標籤），支撐 P1 微調與 P3 研判。所有外部 API 查詢結果記得落地快取以利重現。

---

## 相關文件位置

- 設計 spec：`docs/superpowers/specs/2026-05-24-soc-incident-response-agent-design.md`（+ `.pdf`、`assets/soc-agent-flow.png`）
- 計畫 0：`docs/superpowers/plans/2026-05-24-soc-agent-foundation.md`
- 計畫 A spec：`docs/superpowers/specs/2026-05-26-plan-a-triage-classifier-design.md`
- 計畫 A plan：`docs/superpowers/plans/2026-05-26-plan-a-triage-classifier.md`
- 計畫 C spec：`docs/superpowers/specs/2026-05-26-plan-c-reasoning-playbook-design.md`
- 計畫 C plan：`docs/superpowers/plans/2026-05-26-plan-c-reasoning-playbook.md`
- handout 翻譯：`docs/期末專題說明_繁體中文翻譯.md`
- 必做清單：`docs/期末專題_必做項目清單.md`

## 課程里程碑提醒

- 第 14 週：個人進度報告（3 頁起、6 頁達優異）
- 第 15 週：個人進度報告（評估指標、微調腳本）
- 第 16 週：團隊最終整合報告 + PoC 成果物
