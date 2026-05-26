from soc_agent import nodes

SAMPLE = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "m",
    "indicators": ["203.0.113.45"],
    "raw": {},
}


def test_ingest_normalizes_and_extracts_iocs():
    out = nodes.ingest({"alert": SAMPLE})
    assert out["alert"]["category"] == "authentication"
    assert out["iocs"] == ["203.0.113.45"]


def test_triage_sets_type_and_severity():
    out = nodes.triage({"alert": SAMPLE})
    assert out["alert_type"] == "authentication"
    assert out["severity"] == "high"


def test_enrich_builds_entry_per_ioc():
    out = nodes.enrich({"iocs": ["203.0.113.45"]})
    assert "203.0.113.45" in out["enrichment"]


def test_investigate_high_severity_is_true_positive():
    out = nodes.investigate({"severity": "high"})
    assert out["verdict"] == "true_positive"


def test_attack_mapping_returns_techniques():
    out = nodes.attack_mapping({})
    assert out["attack_techniques"]


def test_playbook_has_three_phases():
    out = nodes.playbook({})
    assert set(out["playbook"]) == {"containment", "eradication", "recovery"}


def test_critique_incomplete_then_complete():
    first = nodes.critique({"critique_iterations": 0})
    assert first["critique_iterations"] == 1
    assert first["critique"]["complete"] is False
    second = nodes.critique({"critique_iterations": 1})
    assert second["critique_iterations"] == 2
    assert second["critique"]["complete"] is True


def test_human_approval_approves():
    assert nodes.human_approval({})["approved"] is True


def test_report_compiles_summary():
    out = nodes.report(
        {
            "alert_type": "authentication",
            "severity": "high",
            "verdict": "true_positive",
            "attack_techniques": ["T1110"],
            "playbook": {"containment": []},
            "approved": True,
        }
    )
    assert out["final_report"]["verdict"] == "true_positive"
    assert out["final_report"]["approved"] is True
