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
    assert report.manipulation_rate == 0.0
    assert report.total >= 1


def test_list_and_load_sample_alerts():
    samples = list_sample_alerts()
    assert len(samples) == 2
    alert = load_alert(samples[0])
    assert "category" in alert
