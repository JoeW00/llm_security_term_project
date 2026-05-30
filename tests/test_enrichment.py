import pytest
from pydantic import ValidationError

from soc_agent.enrichment import (
    Enricher,
    EnrichmentResult,
    StaticEnricher,
    classify_ioc,
)


def test_classify_ioc_types():
    assert classify_ioc("203.0.113.45") == "ip"
    assert classify_ioc("evil.example.com") == "domain"
    assert (
        classify_ioc("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855") == "hash"
    )
    assert classify_ioc("http://bad.example/x") == "url"
    assert classify_ioc("root") == "unknown"


def test_enrichment_result_rejects_bad_score():
    with pytest.raises(ValidationError):
        EnrichmentResult(ioc="x", source="s", score=1.5)


def test_static_enricher_builds_entry_per_ioc():
    out = StaticEnricher().enrich(["203.0.113.45", "evil.example.com"])
    assert out["203.0.113.45"].ioc_type == "ip"
    assert out["203.0.113.45"].source == "AbuseIPDB"
    assert out["evil.example.com"].source == "VirusTotal"


def test_static_enricher_satisfies_protocol():
    assert isinstance(StaticEnricher(), Enricher)
