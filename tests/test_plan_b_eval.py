from eval.attack_mapping_eval import coverage, mapping_ablation
from eval.enrich_eval import enrich_summary
from soc_agent.attack import KeywordAttackMapper
from soc_agent.enrichment import StaticEnricher

RECORDS = [
    {"query": "84 failed login brute force", "expected": "T1110"},
    {"query": "ransomware signature match", "expected": "T1204"},
]


def test_coverage_counts_hits():
    assert coverage(KeywordAttackMapper(), RECORDS) == 1.0


def test_mapping_ablation_runs_multiple():
    out = mapping_ablation({"keyword": KeywordAttackMapper()}, RECORDS)
    assert out["keyword"] == 1.0


def test_enrich_summary_counts_malicious():
    summary = enrich_summary(StaticEnricher(), ["203.0.113.45", "evil.example.com"])
    assert summary["total"] == 2
    assert summary["malicious"] == 2
    assert "AbuseIPDB" in summary["by_source"]
