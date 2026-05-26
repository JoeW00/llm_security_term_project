import pytest

from soc_agent.reasoners.anthropic_client import AnthropicLLMClient
from soc_agent.reasoning import LLMClientError


class FakeContentBlock:
    def __init__(self, text):
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeContentBlock(text)]


class FakeMessages:
    def __init__(self, text):
        self._text = text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return FakeResponse(self._text)


class FakeSDKClient:
    def __init__(self, text):
        self.messages = FakeMessages(text)


def test_complete_extracts_text_and_maps_args():
    sdk = FakeSDKClient("hello world")
    client = AnthropicLLMClient(sdk, model="claude-opus-4-7")
    out = client.complete(system="SYS", prompt="USER")
    assert out == "hello world"
    kwargs = sdk.messages.last_kwargs
    assert kwargs["model"] == "claude-opus-4-7"
    assert kwargs["system"] == "SYS"
    assert kwargs["messages"] == [{"role": "user", "content": "USER"}]
    assert "max_tokens" in kwargs


class _RaisingMessages:
    def create(self, **kwargs):
        raise ConnectionError("network down")


class _RaisingSDK:
    def __init__(self):
        self.messages = _RaisingMessages()


class _EmptyResponse:
    content = []


class _EmptyMessages:
    def create(self, **kwargs):
        return _EmptyResponse()


class _EmptySDK:
    def __init__(self):
        self.messages = _EmptyMessages()


def test_complete_raises_llmclienterror_on_transport_error():
    client = AnthropicLLMClient(_RaisingSDK(), model="m")
    with pytest.raises(LLMClientError):
        client.complete(system="s", prompt="p")


def test_complete_raises_llmclienterror_on_empty_content():
    client = AnthropicLLMClient(_EmptySDK(), model="m")
    with pytest.raises(LLMClientError):
        client.complete(system="s", prompt="p")
