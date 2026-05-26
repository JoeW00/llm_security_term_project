import json

from eval.reasoning_eval import convergence_stats, judge_playbook, verdict_metrics
from soc_agent.reasoning import RubricScores


def test_verdict_metrics_accuracy_and_precision_recall():
    pairs = [
        ("true_positive", "true_positive"),  # TP
        ("true_positive", "false_positive"),  # FN
        ("false_positive", "false_positive"),  # TN
        ("false_positive", "true_positive"),  # FP
    ]
    m = verdict_metrics(pairs)
    assert m["accuracy"] == 0.5
    assert m["precision"] == 0.5
    assert m["recall"] == 0.5


def test_convergence_stats():
    stats = convergence_stats([1, 2, 3, 2], cap=3)
    assert stats["mean_iterations"] == 2.0
    assert stats["pct_converged"] == 1.0


def test_convergence_stats_counts_non_converged():
    stats = convergence_stats([1, 3, 3], cap=2)
    assert stats["pct_converged"] == 1 / 3


class StubJudge:
    def __init__(self, response):
        self._response = response

    def complete(self, *, system, prompt):
        return self._response


def test_judge_playbook_returns_rubric_scores():
    judge = StubJudge(json.dumps({"coverage": 4, "executability": 3, "safety": 5}))
    scores = judge_playbook(judge, {"containment": ["x"], "eradication": [], "recovery": []})
    assert isinstance(scores, RubricScores)
    assert scores.coverage == 4
