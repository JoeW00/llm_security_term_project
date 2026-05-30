import pytest

from soc_agent.reasoners.ollama_client import OllamaLLMClient
from soc_agent.reasoning import LLMClient, LLMClientError


class StubClient:
    """測試替身：回傳預設 response，或拋例外。"""

    def __init__(self, response=None, raises=False):
        self._response = response
        self._raises = raises
        self.last_call = None

    def generate(self, *, model, system, prompt):
        self.last_call = {"model": model, "system": system, "prompt": prompt}
        if self._raises:
            raise RuntimeError("ollama down")
        return {"response": self._response}


def test_complete_returns_text():
    client = StubClient(response='{"verdict": "true_positive"}')
    llm = OllamaLLMClient(client, model="qwen2.5:7b")
    out = llm.complete(system="sys", prompt="usr")
    assert out == '{"verdict": "true_positive"}'
    assert client.last_call["model"] == "qwen2.5:7b"


def test_failure_normalized_to_llm_client_error():
    llm = OllamaLLMClient(StubClient(raises=True), model="qwen2.5:7b")
    with pytest.raises(LLMClientError):
        llm.complete(system="sys", prompt="usr")


def test_empty_response_raises_llm_client_error():
    llm = OllamaLLMClient(StubClient(response=None), model="qwen2.5:7b")
    with pytest.raises(LLMClientError):
        llm.complete(system="sys", prompt="usr")


def test_satisfies_llm_client_protocol():
    assert isinstance(OllamaLLMClient(StubClient(response="x"), model="m"), LLMClient)
