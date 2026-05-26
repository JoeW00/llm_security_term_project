from pathlib import Path

from eval.triage_eval import ablation, evaluate, load_dataset
from soc_agent.classifier import RuleBasedClassifier

# 三筆記錄：RuleBasedClassifier 會 echo category，所以 alert_type 預測 = category。
RECORDS = [
    {
        "alert": {"category": "authentication", "severity": "high"},
        "expected": {"alert_type": "authentication", "severity": "high"},
    },
    {
        "alert": {"category": "malware", "severity": "critical"},
        "expected": {"alert_type": "malware", "severity": "critical"},
    },
    {
        "alert": {"category": "network", "severity": "low"},
        "expected": {"alert_type": "authentication", "severity": "low"},
    },  # alert_type 會被預測錯
]


def test_evaluate_accuracy_on_alert_type():
    metrics = evaluate(RuleBasedClassifier(), RECORDS, target="alert_type")
    # 2/3 正確（第三筆 category=network 但 expected=authentication）
    assert metrics.accuracy == 2 / 3


def test_evaluate_perfect_on_severity():
    metrics = evaluate(RuleBasedClassifier(), RECORDS, target="severity")
    assert metrics.accuracy == 1.0
    assert metrics.macro_f1 == 1.0


def test_confusion_matrix_counts():
    metrics = evaluate(RuleBasedClassifier(), RECORDS, target="alert_type")
    # expected=authentication 出現兩次：一次預測對(authentication)，一次預測成 network
    assert metrics.confusion["authentication"]["authentication"] == 1
    assert metrics.confusion["authentication"]["network"] == 1
    assert metrics.confusion["malware"]["malware"] == 1


def test_ablation_runs_multiple_classifiers():
    results = ablation({"rule": RuleBasedClassifier()}, RECORDS, target="severity")
    assert results["rule"].accuracy == 1.0


def test_load_dataset_reads_jsonl():
    path = Path(__file__).parents[1] / "data" / "triage" / "sample_holdout.jsonl"
    records = load_dataset(path)
    assert len(records) >= 1
    assert "alert" in records[0]
    assert "expected" in records[0]
