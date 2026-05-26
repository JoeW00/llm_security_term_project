from eval.injection_eval import InjectionCase, default_corpus, inject, run_injection_suite
from eval.runtime_metrics import end_to_end_metrics


def test_inject_appends_payload_without_mutating():
    base = {"message": "hello"}
    out = inject(base, "EVIL", "message")
    assert out["message"] == "hello EVIL"
    assert base["message"] == "hello"  # original untouched


def test_default_corpus_nonempty_injection_cases():
    corpus = default_corpus()
    assert len(corpus) >= 1
    assert all(isinstance(c, InjectionCase) for c in corpus)


def test_robust_runner_zero_manipulation():
    def runner(alert):
        return {"verdict": "true_positive", "approved": True}

    report = run_injection_suite(runner, default_corpus())
    assert report.manipulation_rate == 0.0
    assert report.manipulated == 0


def test_manipulable_runner_detected():
    def runner(alert):
        return {"verdict": "false_positive", "approved": True}

    cases = default_corpus()
    report = run_injection_suite(runner, cases)
    assert report.manipulation_rate == 1.0
    assert report.manipulated == len(cases)
    assert report.manipulated_names


def test_end_to_end_metrics_keys():
    def runner(alert):
        return {"critique_iterations": 2, "final_report": {}}

    m = end_to_end_metrics(runner, {"x": 1})
    assert m["critique_iterations"] == 2
    assert m["latency_seconds"] >= 0.0
