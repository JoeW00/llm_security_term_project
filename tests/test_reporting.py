from soc_agent import nodes
from soc_agent.reporting import render_markdown

FULL = {
    "alert_type": "authentication",
    "severity": "high",
    "verdict": "true_positive",
    "approved": True,
    "approval_reason": "looks valid",
    "rationale": "84 failed logins from one IP",
    "attack_techniques": ["T1110"],
    "playbook": {
        "containment": ["isolate host"],
        "eradication": ["reset creds"],
        "recovery": ["monitor"],
    },
}


def test_render_markdown_includes_core_fields():
    md = render_markdown(FULL)
    assert md.startswith("# ")
    assert "true_positive" in md
    assert "84 failed logins from one IP" in md  # rationale
    assert "T1110" in md
    assert "isolate host" in md  # playbook step
    assert "looks valid" in md  # approval reason


def test_render_markdown_handles_missing_fields():
    md = render_markdown({})
    assert isinstance(md, str)
    assert "# " in md


def test_report_node_surfaces_rationale_and_markdown():
    out = nodes.report(
        {
            "alert_type": "authentication",
            "severity": "high",
            "verdict": "true_positive",
            "rationale": "why TP",
            "attack_techniques": ["T1110"],
            "playbook": {"containment": []},
            "approved": True,
            "approval_reason": "ok by analyst",
        }
    )
    fr = out["final_report"]
    assert fr["verdict"] == "true_positive"
    assert fr["rationale"] == "why TP"
    assert fr["approval_reason"] == "ok by analyst"
    assert "markdown" in fr
    assert "T1110" in fr["markdown"]
