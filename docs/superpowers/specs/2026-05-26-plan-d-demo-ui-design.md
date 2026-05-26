# 計畫 D 後續：Demo UI（Streamlit）設計 spec

> 建立日期：2026-05-26
> 範圍：計畫 D 延伸——人機協作核准流程的互動式 Demo UI（計畫 D 主 spec 已將其列為另案）
> 對應：既有 LangGraph 圖 + `InterruptApprovalPolicy` 人工關卡 + 注入韌性評估

---

## 1. 目標與範圍

把已完成的 SOC 代理包成一個**互動式 Streamlit Demo**：載入告警 → 跑圖（在人工核准關卡
以 LangGraph `interrupt` 暫停）→ 顯示報告預覽 → 人工核准／駁回 + 理由 → 顯示最終報告；
另含一個**提示注入韌性面板**，視覺化 P4 的資安亮點。

**決策（brainstorming 已確認）**：
1. **框架：Streamlit**（spec 首選；適合多步驟核准儀表板）。
2. **後端：確定性預設**（rule-based/template/deterministic）——完全離線、免 API key、Demo 可靠。
   人工核准關卡與後端無關；日後可切到 live LLM（A/C LLM 軌）。
3. **範圍：核准 Demo + 注入面板**。

**核心原則：可測試 controller + 輕量 view。** Streamlit 每次互動會重跑整個腳本，故圖 +
checkpointer + thread 狀態必須跨重跑存活（放 `st.session_state`）。把編排邏輯抽到
**不依賴 streamlit** 的 `demo/controller.py`（可離線單元測試，重用既有已測的 interrupt 流程），
`demo/app.py` 只是薄薄的 view（手動執行驗證，不單元測試）。

**不在範圍**：live LLM 串接、登入授權、部署／hosting、把執行結果落地存檔。

---

## 2. 模組佈局

```
demo/
    __init__.py
    controller.py     # 新增：IncidentSession（start/resume）+ injection_report + 樣本告警輔助；不 import streamlit
    app.py            # 新增：Streamlit view（薄層，放 session_state、渲染）
tests/
    test_demo_controller.py   # 新增：離線、不 import streamlit
pyproject.toml        # 修改：新增可選 [dependency-groups] demo = ["streamlit>=1.30"]
```

`demo/` 與 `eval/` 一樣靠 `pythonpath = ["."]`（已設）在測試中可匯入。

---

## 3. Controller（`demo/controller.py`）

不依賴 streamlit；只用 `soc_agent` 與 `eval`，可離線單元測試。

- **`IncidentSession(thread_id: str, *, build=build_graph)`**：以
  `build(approval_policy=InterruptApprovalPolicy(), checkpointer=MemorySaver())` 建一次圖，
  config 固定為 `{"configurable": {"thread_id": thread_id}}`，圖 + checkpointer 在物件內存活。
  - **`start(alert: dict) -> PendingApproval`**：`graph.invoke({"alert": alert,
    "critique_iterations": 0}, config)`。每條路徑都會抵達 `human_approval`，故必定在此暫停。
    回傳 `PendingApproval`，內含**核准前的狀態快照**（移除 `__interrupt__` 後的 channel 值：
    verdict / severity / rationale / attack_techniques / playbook）與 interrupt payload，
    讓 view 可用既有 `render_markdown` 渲染**報告預覽**。
  - **`resume(approved: bool, reason: str) -> dict`**：`graph.invoke(Command(resume=
    {"approved": approved, "reason": reason}), config)`，回傳最終 `final_report`（含 Markdown）。
- **`PendingApproval`（dataclass）**：`{state: dict, payload: dict}`。`state` 為核准前快照
  （供 `render_markdown` 預覽），`payload` 為 interrupt 送給人工的內容。
- **`injection_report(build=build_graph) -> InjectionReport`**：以確定性圖為 runner
  （`lambda a: build().invoke({"alert": a, "critique_iterations": 0})["final_report"]`），對
  `eval.injection_eval.default_corpus()` 跑 `run_injection_suite`。確定性後端無視注入 →
  manipulation_rate 0.0，示範「確定性管線不可被操控；LLM 軌才是注入韌性的戰場」。
- **`list_sample_alerts() -> list[Path]`**：列出 `data/sample_alerts/*.json`。
- **`load_alert(path: str | Path) -> dict`**：讀單筆告警 JSON。

---

## 4. View（`demo/app.py`，Streamlit；薄層、手動驗證）

- **Sidebar**：選 `data/sample_alerts/` 樣本或上傳告警 JSON；「Run」按鈕。
- **主區—事件流程**：按 Run → `IncidentSession.start`（存進 `st.session_state`）→ 以
  `render_markdown(pending.state)` 顯示報告預覽 + verdict/severity/playbook → 顯示
  **核准 / 駁回** 控制 + 理由輸入框 → 按下後 `resume(approved, reason)` → 顯示最終報告
  Markdown + approved / 理由。
- **注入面板**（expander 或分頁）：「Run injection suite」按鈕 → 顯示
  `injection_report()` 的 total / manipulated / **manipulation rate**。
- 例外：`load_alert` 對壞 JSON 顯示友善錯誤，不讓整頁崩潰。

---

## 5. 相依與啟動

- `streamlit` 放**可選** dependency group：`[dependency-groups] demo = ["streamlit>=1.30"]`。
  核心測試套件在未安裝 streamlit 下仍可全跑（controller 與測試**都不 import streamlit**）。
- 啟動：`uv run --group demo streamlit run demo/app.py`。

---

## 6. 測試策略（離線、確定性，全不 import streamlit）

`tests/test_demo_controller.py`：
- `IncidentSession.start(alert)` 會暫停並回傳 `PendingApproval`，其 `state` 含核准前的
  verdict/severity（高風險告警 → verdict=true_positive），`payload` 含 interrupt 內容。
- `IncidentSession.resume(approved=False, reason=...)` → `final_report["approved"] is False`
  且帶出 `approval_reason`。
- `IncidentSession.resume(approved=True, reason="")` → `final_report["approved"] is True`。
- `injection_report()` → `manipulation_rate == 0.0`、`total == len(default_corpus())`。
- `list_sample_alerts()` 列出兩個內建樣本；`load_alert` 讀回 dict。

`demo/app.py` 不單元測試——以 `uv run --group demo streamlit run demo/app.py` 手動驗證。

---

## 7. 建置順序（TDD）

1. `demo/controller.py`（`IncidentSession` + `PendingApproval` + `injection_report` + 樣本輔助）
   + `tests/test_demo_controller.py`。
2. `demo/app.py`（Streamlit view）+ pyproject 加 `demo` group（手動驗證；不單元測試）。
3. 跑 `langgraph-reviewer`（確認 controller 的 interrupt/resume 用法與既有契約一致）。

---

## 8. 相關文件

- 計畫 D spec / plan：`docs/superpowers/specs/2026-05-26-plan-d-approval-security-design.md`、
  `docs/superpowers/plans/2026-05-26-plan-d-approval-security.md`
- 核准邊界：`soc_agent/approval.py`（`InterruptApprovalPolicy`）
- 報告渲染：`soc_agent/reporting.py`（`render_markdown`）
- 注入評估：`eval/injection_eval.py`（`default_corpus`、`run_injection_suite`）
- 圖：`soc_agent/graph.py`（`build_graph(approval_policy=…, checkpointer=…)`）
