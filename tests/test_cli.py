from pathlib import Path

import pytest

from soc_agent.__main__ import main, run

ALERT_PATH = str(Path(__file__).parents[1] / "data" / "sample_alerts" / "ssh_bruteforce.json")


def test_run_returns_final_report_dict():
    report = run(ALERT_PATH)
    assert report["verdict"] == "true_positive"
    assert report["approved"] is True
    assert "T1110" in report["attack_techniques"]


def test_run_default_is_deterministic():
    report = run(ALERT_PATH)
    assert report["verdict"] == "true_positive"


def test_run_llm_flag_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        run(ALERT_PATH, use_llm=True)


def test_main_llm_flag_is_wired(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        main(["run", ALERT_PATH, "--llm"])
