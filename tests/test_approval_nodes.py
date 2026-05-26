from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from soc_agent import nodes
from soc_agent.approval import ApprovalDecision, InterruptApprovalPolicy
from soc_agent.graph import build_graph

HIGH = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "brute force",
    "indicators": ["203.0.113.45"],
    "raw": {},
}


class RejectingPolicy:
    def decide(self, state):
        return ApprovalDecision(approved=False, reason="denied by test")


def test_human_approval_default_auto_approves():
    out = nodes.human_approval({})
    assert out["approved"] is True
    assert out["approval_reason"] == "auto-approved"


def test_human_approval_uses_injected_policy():
    out = nodes.human_approval({}, policy=RejectingPolicy())
    assert out["approved"] is False
    assert out["approval_reason"] == "denied by test"


def test_build_graph_default_runs_to_completion():
    result = build_graph().invoke({"alert": HIGH, "critique_iterations": 0})
    assert result["final_report"]["approved"] is True
    assert result["final_report"]["approval_reason"] == "auto-approved"


def test_build_graph_injected_rejecting_policy():
    result = build_graph(approval_policy=RejectingPolicy()).invoke(
        {"alert": HIGH, "critique_iterations": 0}
    )
    assert result["approved"] is False
    assert result["final_report"]["approved"] is False
    assert result["final_report"]["approval_reason"] == "denied by test"


def test_interrupt_policy_pauses_then_resumes():
    saver = MemorySaver()
    graph = build_graph(approval_policy=InterruptApprovalPolicy(), checkpointer=saver)
    config = {"configurable": {"thread_id": "t1"}}
    paused = graph.invoke({"alert": HIGH, "critique_iterations": 0}, config)
    assert "final_report" not in paused
    final = graph.invoke(Command(resume={"approved": False, "reason": "looks risky"}), config)
    assert final["approved"] is False
    assert final["approval_reason"] == "looks risky"
    assert final["final_report"]["approved"] is False
