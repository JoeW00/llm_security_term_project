import pytest
from pydantic import ValidationError

from soc_agent.reasoning import (
    Critic,
    CritiqueModel,
    Investigation,
    Investigator,
    LLMClient,
    PlaybookGenerator,
    PlaybookModel,
    RubricScores,
    parse_json,
)


def test_investigation_validates_fields():
    inv = Investigation(verdict="true_positive", confidence=0.8, rationale="why")
    assert inv.verdict == "true_positive"
    assert inv.confidence == 0.8


def test_investigation_rejects_bad_verdict():
    with pytest.raises(ValidationError):
        Investigation(verdict="maybe", confidence=0.5)


def test_investigation_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        Investigation(verdict="unknown", confidence=2.0)


def test_playbook_model_requires_three_phases():
    pb = PlaybookModel(containment=["a"], eradication=["b"], recovery=["c"])
    assert pb.model_dump().keys() == {"containment", "eradication", "recovery"}


def test_rubric_scores_bounded():
    with pytest.raises(ValidationError):
        RubricScores(coverage=9, executability=3, safety=3)


def test_critique_model_defaults_issues_empty():
    c = CritiqueModel(complete=True, scores=RubricScores(coverage=5, executability=5, safety=5))
    assert c.issues == []


def test_parse_json_accepts_valid():
    inv = parse_json(
        '{"verdict": "false_positive", "confidence": 0.3, "rationale": "x"}', Investigation
    )
    assert isinstance(inv, Investigation)
    assert inv.verdict == "false_positive"


def test_parse_json_rejects_malformed():
    with pytest.raises(ValueError):
        parse_json("not json", Investigation)
    with pytest.raises(ValueError):
        parse_json('{"verdict": "nope"}', Investigation)


def test_protocols_are_runtime_checkable():
    for proto in (LLMClient, Investigator, PlaybookGenerator, Critic):
        assert hasattr(proto, "_is_runtime_protocol")
