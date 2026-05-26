from soc_agent.state import MAX_CRITIQUE_ITERATIONS, Alert, IncidentState


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
        source="wazuh",
        timestamp="t",
        category="auth",
        severity="high",
        message="m",
        indicators=["1.2.3.4"],
    )
    dumped = alert.model_dump()
    assert dumped["severity"] == "high"
    assert dumped["indicators"] == ["1.2.3.4"]


def test_incident_state_is_partial():
    state: IncidentState = {"alert": {}, "critique_iterations": 0}
    assert state["critique_iterations"] == 0


def test_max_critique_iterations_is_positive():
    assert MAX_CRITIQUE_ITERATIONS >= 1
