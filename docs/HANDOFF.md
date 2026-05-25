# 專案接手筆記（HANDOFF）

> 最後更新：2026-05-25
> 下次回來請先讀這份，就知道從哪裡開始。

---

## 一句話現況

LangGraph 版「自主式 SOC Tier-1 事件回應代理」的**基礎骨架（計畫 0）已完成並合併到 `master`**，25 個測試全綠、CLI 可跑。接下來是把 9 個 stub 節點換成真實實作（計畫 A–D）。

---

## 現在做到哪

| 項目 | 狀態 |
|---|---|
| 期末 handout 繁中翻譯 + 必做清單 | ✅ 完成（`docs/`） |
| 設計 spec（含 Mermaid 流程圖 + PDF） | ✅ 完成 |
| 計畫 0：基礎骨架實作計畫 | ✅ 完成 |
| 計畫 0：實作（7 個 task，Subagent 驅動 + 雙重審查） | ✅ 完成、已合併 `master` |
| 計畫 A–D（四個子系統） | ⬜ 尚未開始 |

**git 狀態**：在 `master`，最新是 merge commit `9990126`。功能分支已刪。**尚未設定 git remote**（還沒推上 GitHub）。

---

## 怎麼把專案跑起來（驗證環境還在）

```bash
cd "/Users/joseph/NTHU/114_02/114_02semester_LLM Security System/term_project"
uv sync                                   # 同步依賴（langgraph, pydantic, pytest）
uv run pytest -q                          # 應該 25 passed
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
tests/              # 25 個測試（state/alerts/nodes/routing/graph/cli）
```

流程：`ingest → triage → [route] → enrich → investigate → attack_mapping → playbook → [critique 迴圈] → human_approval → report`
- `[route]`：低風險告警直接旁路到 human_approval
- `[critique 迴圈]`：劇本不完整就回頭重生 playbook，stub 設計成剛好迴圈一次

---

## 下次從哪開始（建議順序）

**下一步：為計畫 A 寫實作計畫，然後同樣用 Subagent 驅動執行。**

四個子系統各自替換對應 stub 節點，彼此獨立、可並行（4 位成員一人一個）：

| 計畫 | 負責人 | 替換的 stub | 重點 |
|---|---|---|---|
| **A（P1）** | — | `nodes.ingest` + `nodes.triage` | 整理告警資料集、LoRA 微調本地分類器（Ollama）、與雲端 zero-shot 做消融比較 |
| **B（P2）** | — | `nodes.enrich` + `nodes.attack_mapping` | 威脅情資工具呼叫（abuse.ch / AbuseIPDB）、MITRE ATT&CK 檢索對應 |
| **C（P3）** | — | `nodes.investigate` + `nodes.playbook` + `nodes.critique` | LLM 研判 TP/FP、生成劇本、真實反思批判 |
| **D（P4）** | — | `nodes.human_approval` | LangGraph interrupt 人工關卡、提示注入韌性評估、Demo UI |

替換邊界很乾淨：改 `nodes.py` 裡的函式 + `graph.py` 的一行 `add_node`，不動其他檔案。`IncidentState` 是穩定契約，新增欄位採「只增不改」。

**啟動方式**：下次回來可以說「為計畫 A 寫實作計畫」，會走 brainstorming（如需要）→ writing-plans → subagent 驅動執行的流程。

---

## 重要設計決策（審查時確認過，別again 翻案）

1. **`IncidentState["alert"]` 用 `dict[str, Any]` 而非 `Alert` 模型**：LangGraph 把 state 序列化成純 dict，模型不能直接放進去。`ingest` 節點用 `Alert.model_validate()` 在入口驗證。這是正確的 LangGraph 模式。
2. **`Alert.timestamp` 用 `str`**：便於 JSON round-trip 與符合告警來源格式。
3. **編排主腦用雲端 API、只有 triage 節點用微調本地模型**：同時滿足「本地模型 + 微調 + 時間可控」，微調只鎖定「告警分類」這個窄任務。
4. **架構選 B（單圖多節點 + 反思迴圈），不是多代理 Supervisor（C）**：3 週時間風險可控，仍完整展示 LangGraph 價值。

---

## 待辦 / 前瞻備註（給計畫 A–C 實作者）

- **計畫 C 注意**：`investigate` stub 目前只測了 `high → true_positive`；真實實作要補 `critical`、`low/unknown` 分支的測試與行為。
- **計畫 C 注意**：低風險旁路時 `final_report["verdict"]` 目前是 `None`（因為跳過了 investigate）。要決定這是不是預期 sentinel，或改成預設 `"unknown"`。
- **CLI**：`run()` 目前對壞掉的告警 JSON 會丟出 Pydantic `ValidationError` 原始 traceback；要不要加友善錯誤訊息可在計畫 D 處理。
- **資料**：spec 規劃以 **Microsoft GUIDE / Security Incident Prediction** 公開資料集為主錨（含真實 TP/FP 分流標籤），支撐 P1 微調與 P3 研判。所有外部 API 查詢結果記得落地快取以利重現。

---

## 相關文件位置

- 設計 spec：`docs/superpowers/specs/2026-05-24-soc-incident-response-agent-design.md`（+ `.pdf`、`assets/soc-agent-flow.png`）
- 計畫 0：`docs/superpowers/plans/2026-05-24-soc-agent-foundation.md`
- handout 翻譯：`docs/期末專題說明_繁體中文翻譯.md`
- 必做清單：`docs/期末專題_必做項目清單.md`

## 課程里程碑提醒

- 第 14 週：個人進度報告（3 頁起、6 頁達優異）
- 第 15 週：個人進度報告（評估指標、微調腳本）
- 第 16 週：團隊最終整合報告 + PoC 成果物
