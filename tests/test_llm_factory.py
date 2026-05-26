import pytest

from soc_agent.graph import build_graph
from soc_agent.reasoners.factory import anthropic_llm_client, llm_reasoners

ALERT = {
    "source": "wazuh",
    "timestamp": "t",
    "category": "authentication",
    "severity": "high",
    "message": "brute force",
    "indicators": [],
    "raw": {},
}


class FakeLLMClient:
    def complete(self, *, system, prompt):
        return '{"verdict": "false_positive", "confidence": 0.2, "rationale": "x"}'


def test_llm_reasoners_returns_build_graph_keys():
    r = llm_reasoners(FakeLLMClient())
    assert set(r) == {"investigator", "playbook_gen", "critic"}


def test_llm_reasoners_wire_into_build_graph():
    graph = build_graph(**llm_reasoners(FakeLLMClient()))
    result = graph.invoke({"alert": ALERT, "critique_iterations": 0})
    assert result["final_report"] is not None


def test_anthropic_llm_client_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        anthropic_llm_client()
