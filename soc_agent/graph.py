"""組裝 SOC 事件回應狀態機並回傳已編譯的圖。"""

from __future__ import annotations

import functools

from langgraph.graph import END, START, StateGraph

from soc_agent import nodes
from soc_agent.classifier import Classifier
from soc_agent.reasoning import Critic, Investigator, PlaybookGenerator
from soc_agent.routing import route_after_critique, route_after_triage
from soc_agent.state import IncidentState


def build_graph(
    classifier: Classifier | None = None,
    investigator: Investigator | None = None,
    playbook_gen: PlaybookGenerator | None = None,
    critic: Critic | None = None,
):
    """連接所有節點與條件邊，回傳 compiled graph。可選注入 triage 分類器與 C 計畫推理器。"""
    builder = StateGraph(IncidentState)

    triage_node = (
        nodes.triage
        if classifier is None
        else functools.partial(nodes.triage, classifier=classifier)
    )
    investigate_node = (
        nodes.investigate
        if investigator is None
        else functools.partial(nodes.investigate, investigator=investigator)
    )
    playbook_node = (
        nodes.playbook
        if playbook_gen is None
        else functools.partial(nodes.playbook, generator=playbook_gen)
    )
    critique_node = (
        nodes.critique if critic is None else functools.partial(nodes.critique, critic=critic)
    )

    builder.add_node("ingest", nodes.ingest)
    builder.add_node("triage", triage_node)
    builder.add_node("enrich", nodes.enrich)
    builder.add_node("investigate", investigate_node)
    builder.add_node("attack_mapping", nodes.attack_mapping)
    builder.add_node("playbook", playbook_node)
    builder.add_node("critique", critique_node)
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
