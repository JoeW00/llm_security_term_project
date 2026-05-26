# CLAUDE.md

自主式 SOC Tier-1 事件回應代理（LLM 資安期末專題）。LangGraph 狀態機把一條
事件回應流程串起來：`ingest → triage → [route] → enrich → investigate →
attack_mapping → playbook → [critique 迴圈] → human_approval → report`。
目前是確定性 walking skeleton（計畫 0 已完成），接下來把 9 個 stub 節點換成
真實實作（計畫 A–D）。

## 常用指令

```bash
uv sync                                  # 同步依賴（langgraph, pydantic, pytest, ruff）
uv run pytest -q                         # 跑測試（應 25 passed，快速且離線）
uv run ruff format .                     # 格式化
uv run ruff check .                      # lint
uv run python -m soc_agent run data/sample_alerts/ssh_bruteforce.json  # 高風險：完整路徑
uv run python -m soc_agent run data/sample_alerts/info_heartbeat.json  # 低風險：旁路
```

## 程式結構

```
soc_agent/
    state.py     # IncidentState (TypedDict 契約) + Alert (Pydantic) + MAX_CRITIQUE_ITERATIONS=3
    nodes.py     # 9 個節點 ← 計畫 A–D 的替換點
    routing.py   # route_after_triage(低風險旁路) + route_after_critique(反思迴圈)
    graph.py     # build_graph() 組裝 StateGraph
    __main__.py  # CLI 入口
data/sample_alerts/  # ssh_bruteforce.json(高風險) + info_heartbeat.json(低風險)
tests/               # 25 個測試
```

## 核心契約（最重要）

- **`IncidentState`（`state.py`）是 4 位成員共用的資料契約。** 改它會波及所有
  子系統與測試 —— 視為高風險變更，務必謹慎（已設保護 hook 要求確認）。
- **每個節點回傳「部分狀態更新」**（只回傳它更新的鍵的 `dict`），**絕不**回傳
  整個 state，也不要原地修改 `state`。LangGraph 會自動合併。
- 節點寫入的鍵必須存在於 `IncidentState`，且型別符合（如 `Severity`、
  `Verdict` 的 `Literal`）。新增鍵要先加進 `state.py`。
- **critique 反思迴圈必須會終止**：`critique_iterations` 遞增，達
  `MAX_CRITIQUE_ITERATIONS`（3）或 `complete` 時離開。
- `human_approval` 是處置動作前的安全閘門 —— 不要讓代理在核准前行動。

## 計畫 A–D：stub → 真實實作

| 節點 | 計畫 | 換成 |
|------|------|------|
| `triage` | A | 微調本地分類器 |
| `enrich` / `attack_mapping` | B | 真實威脅情資工具呼叫 / 檢索式 MITRE ATT&CK 對應 |
| `investigate` / `playbook` / `critique` | C / D | LLM 研判、劇本生成、反思迴圈 |

## 慣例

- Python 3.12、`uv` 管理依賴、Pydantic v2、LangGraph。
- 每個 `.py` 檔頂端 `from __future__ import annotations`；型別註記必填。
- Docstring 用繁體中文（沿用現有風格）。
- ruff line-length=100，select E/F/I/UP。
- **LLM 節點安全**：告警欄位（`message`、`raw`、`indicators`）是**不可信輸入**，
  不要把原始告警文字直接塞進 system prompt；LLM 輸出在進入 `IncidentState`
  前要用 Pydantic 驗證。實作後請用 `security-reviewer` subagent 審查。
- 測試必須離線、確定性（LLM/網路呼叫要可注入或 patch）。

## 工具

- `/new-node` skill：新增或替換節點的標準流程（含模板與檢查清單）。
- `/run-alert` skill：把樣本告警跑完整條流程並印出結果。
- subagents：`security-reviewer`（LLM 信任邊界、prompt injection）、
  `langgraph-reviewer`（契約 / 路由 / 迴圈正確性）。
- hooks：編輯 `soc_agent/`、`tests/` 後自動 `ruff format` + `pytest`；
  編輯 `state.py` 或樣本告警前會要求確認。

## Git

- 主分支 `main`，已推到 GitHub（Private）。
- 推送需用 `JoeW00` 帳號：`gh auth switch --user JoeW00`。
