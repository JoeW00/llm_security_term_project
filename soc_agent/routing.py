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
