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

    def __init__(
        self,
        thread_id: str,
        *,
        build: Callable[..., Any] = build_graph,
        reasoners: dict[str, Any] | None = None,
    ) -> None:
        self._graph = build(
            approval_policy=InterruptApprovalPolicy(),
            checkpointer=MemorySaver(),
            **(reasoners or {}),
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
