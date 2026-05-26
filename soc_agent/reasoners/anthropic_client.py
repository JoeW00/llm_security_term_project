"""AnthropicLLMClient：把注入的 Anthropic SDK client 包成 LLMClient。

不直接依賴 anthropic 套件（client 由外部注入），使測試離線。正式使用時傳入
`anthropic.Anthropic()` 實例即可。
"""

from __future__ import annotations

from typing import Any, Protocol

from soc_agent.reasoning import LLMClientError


class _Messages(Protocol):
    def create(self, **kwargs: Any) -> Any: ...


class _SDKClient(Protocol):
    messages: _Messages


class AnthropicLLMClient:
    """以 Anthropic messages API 實作 LLMClient.complete。"""

    def __init__(self, client: _SDKClient, model: str, max_tokens: int = 1024) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, *, system: str, prompt: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                system=system,
                max_tokens=self._max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as exc:  # 網路 / SDK / 空或非文字 content 一律正規化為 LLMClientError
            raise LLMClientError(str(exc)) from exc
