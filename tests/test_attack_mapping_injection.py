from soc_agent import nodes
from soc_agent.graph import build_graph

ALERT = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "84 failed login brute force from 203.0.113.45",
    "indicators": [],
    "raw": {},
}


class FakeMapper:
    def map(self, query):
        return ["T1566"]


def test_attack_mapping_uses_injected_mapper():
    out = nodes.attack_mapping(
        {"alert": ALERT, "alert_type": "authentication"}, mapper=FakeMapper()
    )
    assert out["attack_techniques"] == ["T1566"]


def test_attack_mapping_default_is_keyword():
    out = nodes.attack_mapping({"alert": ALERT, "alert_type": "authentication"})
    assert "T1110" in out["attack_techniques"]


def test_build_graph_injects_attack_mapper_end_to_end():
    result = build_graph(attack_mapper=FakeMapper()).invoke(
        {"alert": ALERT, "critique_iterations": 0}
    )
    assert result["final_report"]["attack_techniques"] == ["T1566"]
