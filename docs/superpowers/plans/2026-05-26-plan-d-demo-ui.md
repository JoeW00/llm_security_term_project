# Plan D Demo UI (Streamlit) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an interactive Streamlit demo over the existing SOC agent — load an alert, run the graph pausing at the human-approval gate (LangGraph `interrupt`), show a report preview, approve/reject with a reason, show the final report — plus a prompt-injection resilience panel.

**Architecture:** A streamlit-free, unit-testable `demo/controller.py` (`IncidentSession` wrapping `build_graph(approval_policy=InterruptApprovalPolicy(), checkpointer=MemorySaver())` for start/resume, plus an injection-report helper and sample-alert helpers) and a thin `demo/app.py` Streamlit view that holds controller objects in `st.session_state`. Deterministic backend (offline, no API key). Streamlit is an optional dependency group, so the core test suite stays green without it.

**Tech Stack:** Python 3.12, LangGraph (`interrupt`/`Command`/`MemorySaver`), Streamlit (optional group), pytest, ruff, uv.

---

## Background for the implementer

- The SOC agent is a compiled LangGraph. `build_graph(...)` (`soc_agent/graph.py`) accepts `approval_policy` and `checkpointer`. With `InterruptApprovalPolicy()` (`soc_agent/approval.py`) + a `MemorySaver` checkpointer, `graph.invoke({...}, config)` PAUSES at `human_approval` (every route reaches it). The first invoke returns a dict containing `__interrupt__` (a tuple of `Interrupt` objects, each with a `.value` = the payload from `interrupt(payload)`) and NOT `final_report`. Resume with `graph.invoke(Command(resume=value), config)` using the SAME `config` (`{"configurable": {"thread_id": ...}}`).
- `soc_agent/reporting.py::render_markdown(report: dict) -> str` renders a report dict to Markdown (tolerates missing/odd fields).
- `eval/injection_eval.py` has `default_corpus()` and `run_injection_suite(runner, cases) -> InjectionReport{total, manipulated, manipulation_rate, manipulated_names}`. The `runner` maps an alert → a result dict (use `final_report`, which has `verdict`/`approved`).
- `data/sample_alerts/` has `ssh_bruteforce.json` (high) and `info_heartbeat.json` (low).
- A post-edit hook auto-runs `ruff format` + `pytest` after edits under `soc_agent/`/`tests/`. It does NOT cover `demo/` for pytest, but you must still run `uv run ruff check --fix .` then `uv run ruff check .` before committing (must print "All checks passed!"). Non-test `.py` files start with `from __future__ import annotations`; test files do NOT. Type hints; Traditional Chinese docstrings; ruff line-length=100 (E/F/I/UP). ruff `E731` forbids `x = lambda ...` — use nested `def`.
- `demo/` is importable in tests because `pyproject.toml` has `pythonpath = ["."]` (it already exists, from Plan A). `eval/` is importable the same way.
- **Critical:** `demo/controller.py` and `tests/test_demo_controller.py` must NOT import `streamlit` — only `demo/app.py` may. This keeps the test suite runnable without streamlit installed.
- Baseline: `uv run pytest -q` shows **107 passed**. You are on branch `feat/plan-d-demo-ui`. Commit after every task.

### Final file structure this plan produces

```
demo/
    __init__.py        # NEW (Task 1)
    controller.py      # NEW (Task 1): IncidentSession, PendingApproval, injection_report, sample helpers
    app.py             # NEW (Task 2): Streamlit view (thin; not unit-tested)
pyproject.toml         # MODIFY (Task 2): add [dependency-groups] demo = ["streamlit>=1.30"]
tests/
    test_demo_controller.py   # NEW (Task 1)
```

---

## Task 1: Demo controller (streamlit-free, unit-tested)

**Files:**
- Create: `demo/__init__.py`
- Create: `demo/controller.py`
- Test: `tests/test_demo_controller.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_demo_controller.py`:

```python
from demo.controller import (
    IncidentSession,
    PendingApproval,
    injection_report,
    list_sample_alerts,
    load_alert,
)

HIGH = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "brute force",
    "indicators": ["203.0.113.45"],
    "raw": {},
}


def test_start_pauses_with_preapproval_snapshot():
    pending = IncidentSession("t-start").start(HIGH)
    assert isinstance(pending, PendingApproval)
    # paused at human_approval: verdict computed, report NOT yet produced
    assert pending.state["verdict"] == "true_positive"
    assert "final_report" not in pending.state
    assert pending.payload  # interrupt payload present


def test_resume_reject():
    session = IncidentSession("t-reject")
    session.start(HIGH)
    fr = session.resume(approved=False, reason="looks risky")
    assert fr["approved"] is False
    assert fr["approval_reason"] == "looks risky"


def test_resume_approve():
    session = IncidentSession("t-approve")
    session.start(HIGH)
    fr = session.resume(approved=True)
    assert fr["approved"] is True


def test_injection_report_robust_baseline():
    report = injection_report()
    # deterministic backend ignores injected instructions -> not manipulable
    assert report.manipulation_rate == 0.0
    assert report.total >= 1


def test_list_and_load_sample_alerts():
    samples = list_sample_alerts()
    assert len(samples) == 2
    alert = load_alert(samples[0])
    assert "category" in alert
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_demo_controller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'demo'`.

- [ ] **Step 3a: Create `demo/__init__.py`**

```python
"""互動式 Demo（Streamlit）：controller 不依賴 streamlit、可離線測試。"""

from __future__ import annotations
```

- [ ] **Step 3b: Create `demo/controller.py`**

```python
"""Demo 編排 controller：包裝既有圖的 interrupt 人工核准流程 + 注入評估。

不依賴 streamlit，可離線單元測試。view（app.py）把 IncidentSession 放進 session_state。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from eval.injection_eval import InjectionReport, default_corpus, run_injection_suite
from soc_agent.approval import InterruptApprovalPolicy
from soc_agent.graph import build_graph

_SAMPLE_DIR = Path(__file__).resolve().parents[1] / "data" / "sample_alerts"


@dataclass
class PendingApproval:
    """核准關卡暫停時的內容：核准前狀態快照 + interrupt payload。"""

    state: dict[str, Any]
    payload: dict[str, Any]


class IncidentSession:
    """一次互動式事件回應：start 在人工關卡暫停，resume 帶人工決策續跑。"""

    def __init__(self, thread_id: str, *, build: Callable[..., Any] = build_graph) -> None:
        self._graph = build(
            approval_policy=InterruptApprovalPolicy(), checkpointer=MemorySaver()
        )
        self._config = {"configurable": {"thread_id": thread_id}}

    def start(self, alert: dict[str, Any]) -> PendingApproval:
        paused = self._graph.invoke({"alert": alert, "critique_iterations": 0}, self._config)
        interrupts = paused.get("__interrupt__") or []
        payload = interrupts[0].value if interrupts else {}
        state = {k: v for k, v in paused.items() if k != "__interrupt__"}
        return PendingApproval(state=state, payload=payload)

    def resume(self, approved: bool, reason: str = "") -> dict[str, Any]:
        final = self._graph.invoke(
            Command(resume={"approved": approved, "reason": reason}), self._config
        )
        return final["final_report"]


def injection_report(build: Callable[..., Any] = build_graph) -> InjectionReport:
    """以確定性圖為 runner，對預設對抗性語料跑注入韌性評估。"""

    def runner(alert: dict[str, Any]) -> dict[str, Any]:
        return build().invoke({"alert": alert, "critique_iterations": 0})["final_report"]

    return run_injection_suite(runner, default_corpus())


def list_sample_alerts() -> list[Path]:
    """列出 data/sample_alerts/ 下的告警 JSON 檔。"""
    return sorted(_SAMPLE_DIR.glob("*.json"))


def load_alert(path: str | Path) -> dict[str, Any]:
    """讀取單筆告警 JSON。"""
    with open(path, encoding="utf-8") as f:
        return json.load(f)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_demo_controller.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint then commit**

```bash
uv run ruff check --fix .
uv run ruff check .   # must print: All checks passed!
git add demo/__init__.py demo/controller.py tests/test_demo_controller.py
git commit -m "feat: add streamlit-free demo controller (interrupt session + injection report)

Co-creating with artificial intelligence."
```

---

## Task 2: Streamlit view + optional dependency group

**Files:**
- Create: `demo/app.py`
- Modify: `pyproject.toml` (add the `demo` dependency group)

**Note:** `demo/app.py` is a UI glue layer — it is NOT unit-tested (Streamlit scripts are verified by running them). Verification here is: ruff clean, syntax/import-structure valid, and the full pytest suite still green (app.py is not imported by any test).

- [ ] **Step 1: Add the optional `demo` dependency group to `pyproject.toml`**

In `pyproject.toml`, change the `[dependency-groups]` section so it reads:

```toml
[dependency-groups]
dev = ["pytest>=8.0", "ruff>=0.6"]
demo = ["streamlit>=1.30"]
```

- [ ] **Step 2: Create `demo/app.py`**

```python
"""Streamlit Demo：互動式 SOC 事件回應 + 人工核准關卡 + 注入韌性面板。

啟動：uv run --group demo streamlit run demo/app.py
"""

from __future__ import annotations

import json
import uuid

import streamlit as st

from demo.controller import (
    IncidentSession,
    injection_report,
    list_sample_alerts,
    load_alert,
)
from soc_agent.reporting import render_markdown

st.set_page_config(page_title="SOC Agent Demo", layout="wide")
st.title("自主式 SOC Tier-1 事件回應代理")

# --- Sidebar：選告警 ---
st.sidebar.header("告警輸入")
samples = list_sample_alerts()
sample_names = [p.name for p in samples]
choice = st.sidebar.selectbox("選擇樣本告警", ["（上傳檔案）", *sample_names])
uploaded = st.sidebar.file_uploader("或上傳告警 JSON", type="json")

alert: dict | None = None
if choice != "（上傳檔案）":
    alert = load_alert(samples[sample_names.index(choice)])
elif uploaded is not None:
    try:
        alert = json.load(uploaded)
    except json.JSONDecodeError as exc:
        st.sidebar.error(f"JSON 解析失敗：{exc}")

if st.sidebar.button("Run", disabled=alert is None) and alert is not None:
    session = IncidentSession(thread_id=str(uuid.uuid4()))
    st.session_state["pending"] = session.start(alert)
    st.session_state["session"] = session
    st.session_state.pop("final_report", None)

# --- 主區：核准流程 ---
pending = st.session_state.get("pending")
final_report = st.session_state.get("final_report")

if pending is not None and final_report is None:
    st.subheader("報告預覽（待人工核准）")
    st.markdown(render_markdown(pending.state))
    reason = st.text_input("核准／駁回理由", key="reason")
    col_ok, col_no = st.columns(2)
    if col_ok.button("✅ 核准"):
        st.session_state["final_report"] = st.session_state["session"].resume(True, reason)
        st.rerun()
    if col_no.button("❌ 駁回"):
        st.session_state["final_report"] = st.session_state["session"].resume(False, reason)
        st.rerun()

if final_report is not None:
    st.subheader("最終事件報告")
    st.markdown(final_report.get("markdown", ""))
    st.json({k: v for k, v in final_report.items() if k != "markdown"})

# --- 注入韌性面板 ---
with st.expander("提示注入韌性評估"):
    if st.button("Run injection suite"):
        report = injection_report()
        st.metric("Manipulation rate", f"{report.manipulation_rate:.0%}")
        st.write(f"total={report.total}, manipulated={report.manipulated}")
        if report.manipulated_names:
            st.write("被操控案例：", report.manipulated_names)
```

- [ ] **Step 3: Verify lint + syntax + suite**

Run each and confirm:

```bash
uv run ruff check --fix .
uv run ruff check .                              # must print: All checks passed!
uv run python -c "import ast; ast.parse(open('demo/app.py').read())"   # syntax OK, no output
uv run pytest -q                                 # all pass (app.py not imported by tests)
```

Expected: ruff clean; the `ast.parse` command exits silently (valid syntax); pytest all green.

- [ ] **Step 4: Manual smoke (optional, not required to pass the task)**

If you want to eyeball it: `uv run --group demo streamlit run demo/app.py` then open the local URL, pick `ssh_bruteforce.json`, click Run, see the preview, reject with a reason, see the final report; open the injection panel and run the suite (rate should be 0%). This is manual — do not block the task on it in a headless environment.

- [ ] **Step 5: Commit**

```bash
git add demo/app.py pyproject.toml
git commit -m "feat: add Streamlit demo view + optional demo dependency group

Co-creating with artificial intelligence."
```

---

## Task 3: LangGraph review

**No code changes — run the project's review subagent.**

- [ ] **Step 1: LangGraph review**

Dispatch the `langgraph-reviewer` subagent over `demo/controller.py`. Verify: the `IncidentSession` interrupt/resume usage matches LangGraph's contract (compile-with-checkpointer, `invoke` then `Command(resume=...)` on the same `thread_id` config); `start()` correctly extracts the interrupt payload + pre-approval snapshot without mutating graph state; `injection_report`'s runner uses the default (auto-approve, no-checkpointer) graph so it runs to completion; nothing in `demo/` weakens or bypasses the `human_approval` safety gate. Confirm `demo/controller.py` does not import `streamlit`.

- [ ] **Step 2: Address findings**

Fix any issues raised (write a failing test first for behavioral bugs), re-run `uv run pytest -q`, and commit each fix.

---

## Notes / deferred (NOT this plan)

- Live LLM backend toggle in the UI (A/C LLM track): inject `AnthropicLLMClient`-backed reasoners into `IncidentSession`'s `build`.
- Auth, multi-user sessions, persisting runs to disk, deployment/hosting.
- Real before/after-defense injection numbers (needs the live LLM as the `injection_report` runner).
```
