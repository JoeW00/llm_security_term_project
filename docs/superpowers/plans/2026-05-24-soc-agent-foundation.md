# SOC 事件回應代理 — 基礎骨架（計畫 0）實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立一個端到端可執行的 LangGraph 「walking skeleton」：用確定性 stub 節點把完整事件回應流程串起來，鎖定 4 位成員共用的 `IncidentState` 契約，並提供可重現的真實樣本告警與 CLI。

**Architecture:** `StateGraph` 以 `IncidentState`（TypedDict）為狀態，節點函式回傳部分狀態更新。`add_conditional_edges` 實作兩個分支：triage 後的「低風險旁路」與 critique 後的「反思迴圈」。所有節點為 stub（無 LLM、無網路），計畫 A–D 再各自替換。Pydantic 負責輸入告警與結構化輸出的驗證。

**Tech Stack:** Python 3.12、uv、LangGraph、Pydantic v2、pytest。

---

## 檔案結構

```
pyproject.toml                       # 修改：加依賴 + build-system + pytest 設定
soc_agent/
    __init__.py                      # 套件標記
    state.py                         # IncidentState (TypedDict) + Alert (Pydantic) + 常數
    nodes.py                         # 9 個 stub 節點函式
    routing.py                       # 2 個條件邊函式
    graph.py                         # build_graph() -> 已編譯的圖
    __main__.py                      # CLI：python -m soc_agent run <alert.json>
data/sample_alerts/
    ssh_bruteforce.json              # 高嚴重度真實樣本（走完整路徑）
    info_heartbeat.json              # 低嚴重度樣本（走旁路）
tests/
    test_state.py
    test_alerts_load.py
    test_nodes.py
    test_routing.py
    test_graph.py
    test_cli.py
```

每個檔案單一職責：`state.py` 是所有人依賴的資料契約；`nodes.py` 是各子系統的替換點；`routing.py` 是圖的控制流；`graph.py` 是組裝；`__main__.py` 是執行入口。

---

## Task 1：專案 scaffolding 與依賴

**Files:**
- Modify: `pyproject.toml`
- Create: `soc_agent/__init__.py`

- [ ] **Step 1：將 `pyproject.toml` 改成以下內容**

```toml
[project]
name = "term-project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "langgraph>=0.2.0",
    "pydantic>=2.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["soc_agent"]

[dependency-groups]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2：建立套件標記檔 `soc_agent/__init__.py`**

```python
"""自主式 SOC Tier-1 事件回應代理（PoC）。"""

__version__ = "0.1.0"
```

- [ ] **Step 3：同步依賴並驗證套件可被安裝/匯入**

Run: `uv sync && uv run python -c "import soc_agent; print(soc_agent.__version__)"`
Expected: 輸出 `0.1.0`（且 langgraph、pydantic、pytest 已安裝）

- [ ] **Step 4：Commit**

```bash
git add pyproject.toml uv.lock soc_agent/__init__.py
git commit -m "chore: scaffold soc_agent package with langgraph + pydantic + pytest"
```

---

## Task 2：狀態契約 `state.py`

**Files:**
- Create: `soc_agent/state.py`
- Test: `tests/test_state.py`

- [ ] **Step 1：寫失敗測試 `tests/test_state.py`**

```python
from soc_agent.state import Alert, IncidentState, MAX_CRITIQUE_ITERATIONS


def test_alert_validates_and_defaults():
    alert = Alert(
        source="wazuh",
        timestamp="2026-05-20T03:14:22Z",
        category="authentication",
        message="failed logins",
    )
    assert alert.severity == "medium"
    assert alert.indicators == []
    assert alert.raw == {}


def test_alert_round_trips_to_dict():
    alert = Alert(
        source="wazuh", timestamp="t", category="auth",
        severity="high", message="m", indicators=["1.2.3.4"],
    )
    dumped = alert.model_dump()
    assert dumped["severity"] == "high"
    assert dumped["indicators"] == ["1.2.3.4"]


def test_incident_state_is_partial():
    state: IncidentState = {"alert": {}, "critique_iterations": 0}
    assert state["critique_iterations"] == 0


def test_max_critique_iterations_is_positive():
    assert MAX_CRITIQUE_ITERATIONS >= 1
```

- [ ] **Step 2：執行測試，確認失敗**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'soc_agent.state'`

- [ ] **Step 3：實作 `soc_agent/state.py`**

```python
"""共享狀態契約：所有節點讀寫 IncidentState，所有子系統依賴此檔。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

# critique 反思迴圈的最大迭代次數，超過即強制進入人工核准，避免無限迴圈。
MAX_CRITIQUE_ITERATIONS = 3

Severity = Literal["low", "medium", "high", "critical"]
Verdict = Literal["true_positive", "false_positive", "unknown"]


class Alert(BaseModel):
    """正規化後的資安告警，是本系統的輸入單元。"""

    source: str
    timestamp: str
    category: str
    severity: Severity = "medium"
    message: str
    indicators: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class IncidentState(TypedDict, total=False):
    """LangGraph 的共享狀態。total=False：節點只回傳要更新的鍵。"""

    alert: dict[str, Any]
    alert_type: str
    severity: Severity
    iocs: list[str]
    enrichment: dict[str, Any]
    verdict: Verdict
    confidence: float
    attack_techniques: list[str]
    playbook: dict[str, Any]
    critique: dict[str, Any]
    critique_iterations: int
    approved: bool
    final_report: dict[str, Any]
```

- [ ] **Step 4：執行測試，確認通過**

Run: `uv run pytest tests/test_state.py -v`
Expected: 4 passed

- [ ] **Step 5：Commit**

```bash
git add soc_agent/state.py tests/test_state.py
git commit -m "feat: add IncidentState contract and Alert schema"
```

---

## Task 3：真實樣本告警 fixture

**Files:**
- Create: `data/sample_alerts/ssh_bruteforce.json`
- Create: `data/sample_alerts/info_heartbeat.json`
- Test: `tests/test_alerts_load.py`

- [ ] **Step 1：寫失敗測試 `tests/test_alerts_load.py`**

```python
import json
from pathlib import Path

import pytest

from soc_agent.state import Alert

ALERT_DIR = Path(__file__).parents[1] / "data" / "sample_alerts"
FIXTURES = sorted(ALERT_DIR.glob("*.json"))


def test_fixtures_present():
    assert FIXTURES, "expected sample alert JSON files under data/sample_alerts/"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_sample_alert_validates(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    alert = Alert.model_validate(data)
    assert alert.source
    assert alert.message
```

- [ ] **Step 2：執行測試，確認失敗**

Run: `uv run pytest tests/test_alerts_load.py -v`
Expected: FAIL，`test_fixtures_present` 斷言失敗（目錄為空）

- [ ] **Step 3：建立 `data/sample_alerts/ssh_bruteforce.json`**

```json
{
  "source": "wazuh",
  "timestamp": "2026-05-20T03:14:22Z",
  "category": "authentication",
  "severity": "high",
  "message": "sshd: 84 failed login attempts for user root from 203.0.113.45",
  "indicators": ["203.0.113.45", "root"],
  "raw": {"rule_id": "5712", "agent": "web-prod-01", "src_port": 41122}
}
```

- [ ] **Step 4：建立 `data/sample_alerts/info_heartbeat.json`**

```json
{
  "source": "wazuh",
  "timestamp": "2026-05-20T03:15:00Z",
  "category": "system",
  "severity": "low",
  "message": "agent heartbeat received from web-prod-01",
  "indicators": [],
  "raw": {"rule_id": "1002", "agent": "web-prod-01"}
}
```

- [ ] **Step 5：執行測試，確認通過**

Run: `uv run pytest tests/test_alerts_load.py -v`
Expected: 3 passed（1 個 present + 2 個 parametrize）

- [ ] **Step 6：Commit**

```bash
git add data/sample_alerts/ tests/test_alerts_load.py
git commit -m "feat: add real-shaped sample alert fixtures"
```

---

## Task 4：Stub 節點 `nodes.py`

**Files:**
- Create: `soc_agent/nodes.py`
- Test: `tests/test_nodes.py`

- [ ] **Step 1：寫失敗測試 `tests/test_nodes.py`**

```python
from soc_agent import nodes

SAMPLE = {
    "source": "wazuh", "timestamp": "t", "category": "authentication",
    "severity": "high", "message": "m", "indicators": ["203.0.113.45"], "raw": {},
}


def test_ingest_normalizes_and_extracts_iocs():
    out = nodes.ingest({"alert": SAMPLE})
    assert out["alert"]["category"] == "authentication"
    assert out["iocs"] == ["203.0.113.45"]


def test_triage_sets_type_and_severity():
    out = nodes.triage({"alert": SAMPLE})
    assert out["alert_type"] == "authentication"
    assert out["severity"] == "high"


def test_enrich_builds_entry_per_ioc():
    out = nodes.enrich({"iocs": ["203.0.113.45"]})
    assert "203.0.113.45" in out["enrichment"]


def test_investigate_high_severity_is_true_positive():
    out = nodes.investigate({"severity": "high"})
    assert out["verdict"] == "true_positive"


def test_attack_mapping_returns_techniques():
    out = nodes.attack_mapping({})
    assert out["attack_techniques"]


def test_playbook_has_three_phases():
    out = nodes.playbook({})
    assert set(out["playbook"]) == {"containment", "eradication", "recovery"}


def test_critique_incomplete_then_complete():
    first = nodes.critique({"critique_iterations": 0})
    assert first["critique_iterations"] == 1
    assert first["critique"]["complete"] is False
    second = nodes.critique({"critique_iterations": 1})
    assert second["critique_iterations"] == 2
    assert second["critique"]["complete"] is True


def test_human_approval_approves():
    assert nodes.human_approval({})["approved"] is True


def test_report_compiles_summary():
    out = nodes.report({
        "alert_type": "authentication", "severity": "high",
        "verdict": "true_positive", "attack_techniques": ["T1110"],
        "playbook": {"containment": []}, "approved": True,
    })
    assert out["final_report"]["verdict"] == "true_positive"
    assert out["final_report"]["approved"] is True
```

- [ ] **Step 2：執行測試，確認失敗**

Run: `uv run pytest tests/test_nodes.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'soc_agent.nodes'`

- [ ] **Step 3：實作 `soc_agent/nodes.py`**

```python
"""Stub 節點：確定性、無 LLM、無網路。計畫 A–D 各自替換對應節點。"""

from __future__ import annotations

from typing import Any

from soc_agent.state import Alert, IncidentState


def ingest(state: IncidentState) -> dict[str, Any]:
    """驗證並正規化原始告警，萃取初始 IOC 清單。"""
    alert = Alert.model_validate(state["alert"])
    return {"alert": alert.model_dump(), "iocs": list(alert.indicators)}


def triage(state: IncidentState) -> dict[str, Any]:
    """STUB：由正規化告警推導類型與嚴重度。計畫 A 換成微調本地分類器。"""
    alert = state["alert"]
    return {
        "alert_type": alert.get("category", "unknown"),
        "severity": alert.get("severity", "medium"),
    }


def enrich(state: IncidentState) -> dict[str, Any]:
    """STUB：假裝查詢每個 IOC 的威脅情資。計畫 B 換成真實工具呼叫。"""
    enrichment = {ioc: {"reputation": "unknown"} for ioc in state.get("iocs", [])}
    return {"enrichment": enrichment}


def investigate(state: IncidentState) -> dict[str, Any]:
    """STUB：判定真偽。計畫 C 換成 LLM 研判。"""
    severity = state.get("severity", "medium")
    verdict = "true_positive" if severity in ("high", "critical") else "unknown"
    return {"verdict": verdict, "confidence": 0.5}


def attack_mapping(state: IncidentState) -> dict[str, Any]:
    """STUB：對應 MITRE ATT&CK 技術。計畫 B 換成檢索式對應。"""
    return {"attack_techniques": ["T1110"]}  # T1110 = Brute Force（佔位）


def playbook(state: IncidentState) -> dict[str, Any]:
    """STUB：產生三階段處置劇本。計畫 C 換成 LLM 生成。"""
    return {
        "playbook": {
            "containment": ["isolate affected host"],
            "eradication": ["reset compromised credentials"],
            "recovery": ["restore service and monitor"],
        }
    }


def critique(state: IncidentState) -> dict[str, Any]:
    """STUB：反思劇本完整性。

    骨架階段刻意確定性：第一輪標記為不完整（強制回頭重生一次），之後標記
    完整。計畫 C 換成真實 LLM 批判。
    """
    iterations = state.get("critique_iterations", 0) + 1
    complete = iterations >= 2
    return {
        "critique_iterations": iterations,
        "critique": {
            "complete": complete,
            "notes": "ok" if complete else "needs containment detail",
        },
    }


def human_approval(state: IncidentState) -> dict[str, Any]:
    """STUB：自動核准。計畫 D 換成 LangGraph interrupt 人工關卡。"""
    return {"approved": True}


def report(state: IncidentState) -> dict[str, Any]:
    """彙整最終結構化事件報告。"""
    return {
        "final_report": {
            "alert_type": state.get("alert_type"),
            "severity": state.get("severity"),
            "verdict": state.get("verdict"),
            "attack_techniques": state.get("attack_techniques", []),
            "playbook": state.get("playbook", {}),
            "approved": state.get("approved", False),
        }
    }
```

- [ ] **Step 4：執行測試，確認通過**

Run: `uv run pytest tests/test_nodes.py -v`
Expected: 9 passed

- [ ] **Step 5：Commit**

```bash
git add soc_agent/nodes.py tests/test_nodes.py
git commit -m "feat: add deterministic stub nodes for the incident pipeline"
```

---

## Task 5：條件邊 `routing.py`

**Files:**
- Create: `soc_agent/routing.py`
- Test: `tests/test_routing.py`

- [ ] **Step 1：寫失敗測試 `tests/test_routing.py`**

```python
from soc_agent.routing import route_after_critique, route_after_triage
from soc_agent.state import MAX_CRITIQUE_ITERATIONS


def test_low_severity_bypasses_to_approval():
    assert route_after_triage({"severity": "low"}) == "human_approval"


def test_high_severity_goes_to_enrich():
    assert route_after_triage({"severity": "high"}) == "enrich"


def test_critique_loops_when_incomplete_and_under_cap():
    state = {"critique": {"complete": False}, "critique_iterations": 1}
    assert route_after_critique(state) == "playbook"


def test_critique_proceeds_when_complete():
    state = {"critique": {"complete": True}, "critique_iterations": 1}
    assert route_after_critique(state) == "human_approval"


def test_critique_proceeds_at_iteration_cap():
    state = {"critique": {"complete": False}, "critique_iterations": MAX_CRITIQUE_ITERATIONS}
    assert route_after_critique(state) == "human_approval"
```

- [ ] **Step 2：執行測試，確認失敗**

Run: `uv run pytest tests/test_routing.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'soc_agent.routing'`

- [ ] **Step 3：實作 `soc_agent/routing.py`**

```python
"""條件邊函式：回傳下一個節點名稱（對應 graph.py 的分支對照表）。"""

from __future__ import annotations

from soc_agent.state import MAX_CRITIQUE_ITERATIONS, IncidentState


def route_after_triage(state: IncidentState) -> str:
    """低嚴重度告警跳過調查，直接進入人工核准。"""
    if state.get("severity", "medium") == "low":
        return "human_approval"
    return "enrich"


def route_after_critique(state: IncidentState) -> str:
    """劇本不完整且未達迭代上限時回頭重生，否則進入人工核准。"""
    critique = state.get("critique", {})
    iterations = state.get("critique_iterations", 0)
    if critique.get("complete") or iterations >= MAX_CRITIQUE_ITERATIONS:
        return "human_approval"
    return "playbook"
```

- [ ] **Step 4：執行測試，確認通過**

Run: `uv run pytest tests/test_routing.py -v`
Expected: 5 passed

- [ ] **Step 5：Commit**

```bash
git add soc_agent/routing.py tests/test_routing.py
git commit -m "feat: add triage bypass and critique loop routing"
```

---

## Task 6：圖組裝 `graph.py`

**Files:**
- Create: `soc_agent/graph.py`
- Test: `tests/test_graph.py`

- [ ] **Step 1：寫失敗測試 `tests/test_graph.py`**

```python
from soc_agent.graph import build_graph

HIGH = {
    "source": "wazuh", "timestamp": "t", "category": "authentication",
    "severity": "high", "message": "brute force", "indicators": ["203.0.113.45"], "raw": {},
}
LOW = {
    "source": "wazuh", "timestamp": "t", "category": "system",
    "severity": "low", "message": "heartbeat", "indicators": [], "raw": {},
}


def test_graph_compiles():
    assert build_graph() is not None


def test_full_path_produces_report_and_loops_once():
    graph = build_graph()
    result = graph.invoke({"alert": HIGH, "critique_iterations": 0})
    assert result["final_report"]["verdict"] == "true_positive"
    # critique 強制回頭重生剛好一次：0 -> 1(不完整) -> 2(完整)
    assert result["critique_iterations"] == 2
    assert result["enrichment"]  # 完整調查路徑有跑到 enrich


def test_low_severity_bypasses_investigation():
    graph = build_graph()
    result = graph.invoke({"alert": LOW, "critique_iterations": 0})
    assert result["final_report"]["approved"] is True
    assert "enrichment" not in result  # 旁路跳過了 enrich
```

- [ ] **Step 2：執行測試，確認失敗**

Run: `uv run pytest tests/test_graph.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'soc_agent.graph'`

- [ ] **Step 3：實作 `soc_agent/graph.py`**

```python
"""組裝 SOC 事件回應狀態機並回傳已編譯的圖。"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from soc_agent import nodes
from soc_agent.routing import route_after_critique, route_after_triage
from soc_agent.state import IncidentState


def build_graph():
    """連接所有節點與條件邊，回傳 compiled graph。"""
    builder = StateGraph(IncidentState)

    builder.add_node("ingest", nodes.ingest)
    builder.add_node("triage", nodes.triage)
    builder.add_node("enrich", nodes.enrich)
    builder.add_node("investigate", nodes.investigate)
    builder.add_node("attack_mapping", nodes.attack_mapping)
    builder.add_node("playbook", nodes.playbook)
    builder.add_node("critique", nodes.critique)
    builder.add_node("human_approval", nodes.human_approval)
    builder.add_node("report", nodes.report)

    builder.add_edge(START, "ingest")
    builder.add_edge("ingest", "triage")
    builder.add_conditional_edges(
        "triage",
        route_after_triage,
        {"enrich": "enrich", "human_approval": "human_approval"},
    )
    builder.add_edge("enrich", "investigate")
    builder.add_edge("investigate", "attack_mapping")
    builder.add_edge("attack_mapping", "playbook")
    builder.add_edge("playbook", "critique")
    builder.add_conditional_edges(
        "critique",
        route_after_critique,
        {"playbook": "playbook", "human_approval": "human_approval"},
    )
    builder.add_edge("human_approval", "report")
    builder.add_edge("report", END)

    return builder.compile()
```

- [ ] **Step 4：執行測試，確認通過**

Run: `uv run pytest tests/test_graph.py -v`
Expected: 3 passed

- [ ] **Step 5：Commit**

```bash
git add soc_agent/graph.py tests/test_graph.py
git commit -m "feat: wire end-to-end LangGraph with bypass and reflection loop"
```

---

## Task 7：CLI 入口 `__main__.py`

**Files:**
- Create: `soc_agent/__main__.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1：寫失敗測試 `tests/test_cli.py`**

```python
from soc_agent.__main__ import run

ALERT_PATH = "data/sample_alerts/ssh_bruteforce.json"


def test_run_returns_final_report_dict():
    report = run(ALERT_PATH)
    assert report["verdict"] == "true_positive"
    assert report["approved"] is True
    assert "T1110" in report["attack_techniques"]
```

- [ ] **Step 2：執行測試，確認失敗**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'soc_agent.__main__'`

- [ ] **Step 3：實作 `soc_agent/__main__.py`**

```python
"""CLI 入口：uv run python -m soc_agent run <alert.json>。"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from soc_agent.graph import build_graph


def run(alert_path: str) -> dict[str, Any]:
    """讀取單筆告警 JSON，跑完整圖，回傳 final_report。"""
    with open(alert_path, encoding="utf-8") as f:
        alert = json.load(f)
    graph = build_graph()
    result = graph.invoke({"alert": alert, "critique_iterations": 0})
    return result["final_report"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="soc_agent")
    sub = parser.add_subparsers(dest="command", required=True)
    run_p = sub.add_parser("run", help="Run the agent on a single alert JSON file")
    run_p.add_argument("alert", help="Path to an alert JSON file")
    args = parser.parse_args(argv)

    if args.command == "run":
        report = run(args.alert)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4：執行測試，確認通過**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 1 passed

- [ ] **Step 5：手動端到端驗證 CLI**

Run: `uv run python -m soc_agent run data/sample_alerts/ssh_bruteforce.json`
Expected: 印出 JSON 報告，含 `"verdict": "true_positive"`、`"approved": true`、`"attack_techniques": ["T1110"]`

- [ ] **Step 6：執行整套測試，確認全綠**

Run: `uv run pytest -v`
Expected: 全部 passed（state 4 + alerts 3 + nodes 9 + routing 5 + graph 3 + cli 1 = 25）

- [ ] **Step 7：Commit**

```bash
git add soc_agent/__main__.py tests/test_cli.py
git commit -m "feat: add CLI entrypoint to run the agent on an alert file"
```

---

## 完成後的交接點

骨架完成後，4 位成員可並行各自的子系統計畫，各自替換對應 stub 節點而不互相阻擋：

- **計畫 A（P1）**：`nodes.triage` + `nodes.ingest` ← 微調本地分類器
- **計畫 B（P2）**：`nodes.enrich` + `nodes.attack_mapping` ← 威脅情資工具 + ATT&CK 檢索
- **計畫 C（P3）**：`nodes.investigate` + `nodes.playbook` + `nodes.critique` ← LLM 研判與生成
- **計畫 D（P4）**：`nodes.human_approval` ← LangGraph interrupt；加上提示注入評估與 Demo UI

`IncidentState` 是各計畫之間的穩定契約——新增欄位採「只增不改」原則，避免破壞他人節點。
