from soc_agent import nodes
from soc_agent.enrichment import EnrichmentResult
from soc_agent.graph import build_graph

ALERT = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "brute force from 203.0.113.45",
    "indicators": ["203.0.113.45"],
    "raw": {},
}


class FakeEnricher:
    def enrich(self, iocs):
        return {i: EnrichmentResult(ioc=i, source="fake", malicious=True, score=0.99) for i in iocs}


def test_enrich_uses_injected_enricher():
    out = nodes.enrich({"iocs": ["203.0.113.45"]}, enricher=FakeEnricher())
    assert out["enrichment"]["203.0.113.45"]["source"] == "fake"


def test_enrich_default_is_static():
    out = nodes.enrich({"iocs": ["203.0.113.45"]})
    assert "203.0.113.45" in out["enrichment"]
    assert out["enrichment"]["203.0.113.45"]["source"] == "AbuseIPDB"


def test_build_graph_injects_enricher_end_to_end():
    result = build_graph(enricher=FakeEnricher()).invoke({"alert": ALERT, "critique_iterations": 0})
    assert result["enrichment"]["203.0.113.45"]["source"] == "fake"
