from soc_agent.__main__ import run

ALERT_PATH = "data/sample_alerts/ssh_bruteforce.json"


def test_run_returns_final_report_dict():
    report = run(ALERT_PATH)
    assert report["verdict"] == "true_positive"
    assert report["approved"] is True
    assert "T1110" in report["attack_techniques"]
