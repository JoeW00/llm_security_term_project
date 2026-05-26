import pytest
from pydantic import ValidationError

from soc_agent.classifier import ClassificationResult, Classifier, RuleBasedClassifier


def test_classification_result_accepts_valid_fields():
    result = ClassificationResult(alert_type="authentication", severity="high", confidence=0.9)
    assert result.alert_type == "authentication"
    assert result.severity == "high"
    assert result.confidence == 0.9


def test_classification_result_rejects_bad_severity():
    with pytest.raises(ValidationError):
        ClassificationResult(alert_type="x", severity="catastrophic")


def test_classification_result_rejects_out_of_range_confidence():
    with pytest.raises(ValidationError):
        ClassificationResult(alert_type="x", severity="low", confidence=1.5)


def test_rule_based_echoes_category_and_severity():
    clf = RuleBasedClassifier()
    result = clf.classify({"category": "authentication", "severity": "high"})
    assert result.alert_type == "authentication"
    assert result.severity == "high"


def test_rule_based_falls_back_on_missing_fields():
    clf = RuleBasedClassifier()
    result = clf.classify({})
    assert result.alert_type == "unknown"
    assert result.severity == "medium"


def test_rule_based_satisfies_classifier_protocol():
    assert isinstance(RuleBasedClassifier(), Classifier)
