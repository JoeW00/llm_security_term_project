from soc_agent.reasoners.anthropic_client import AnthropicLLMClient


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
