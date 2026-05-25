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
