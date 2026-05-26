from soc_agent import nodes
from soc_agent.classifier import ClassificationResult
from soc_agent.graph import build_graph

ALERT = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "brute force",
    "indicators": [],
    "raw": {},
}


class FakeClassifier:
    """測試替身：忽略輸入，回傳固定結果。"""

    def classify(self, alert):
        return ClassificationResult(alert_type="malware", severity="critical", confidence=0.7)


def test_triage_uses_injected_classifier():
    out = nodes.triage({"alert": ALERT}, classifier=FakeClassifier())
    assert out["alert_type"] == "malware"
    assert out["severity"] == "critical"


def test_triage_default_is_rule_based():
    out = nodes.triage({"alert": ALERT})
    assert out["alert_type"] == "authentication"
    assert out["severity"] == "high"


def test_build_graph_injects_classifier_end_to_end():
    graph = build_graph(classifier=FakeClassifier())
    result = graph.invoke({"alert": ALERT, "critique_iterations": 0})
    # FakeClassifier forces severity=critical, so the full investigation path runs.
    assert result["alert_type"] == "malware"
    assert result["severity"] == "critical"
    assert result["final_report"]["verdict"] == "true_positive"
