"""OllamaLLMClient：把注入的 ollama client 包成 LLMClient（地端推理後端）。

與 AnthropicLLMClient 對稱，但呼叫本地 ollama，使編排主腦可全本地、無金鑰執行
（告警不送出企業邊界，符合自託管 SOC 威脅模型）。client 由外部注入使測試離線；
正式使用傳入 `ollama` 模組或 `ollama.Client()` 即可。任何失敗或空回應正規化為
LLMClientError，由 reasoner 退回確定性預設。
"""

from __future__ import annotations

from typing import Any, Protocol

from soc_agent.reasoning import LLMClientError


class _OllamaClient(Protocol):
    """最小 ollama 介面：吃 model/system/prompt，回傳含 'response' 鍵的 dict。"""

    def generate(self, *, model: str, system: str, prompt: str) -> dict[str, Any]: ...


class OllamaLLMClient:
    """以本地 ollama generate API 實作 LLMClient.complete。"""

    def __init__(self, client: _OllamaClient, model: str) -> None:
        self._client = client
        self._model = model

    def complete(self, *, system: str, prompt: str) -> str:
        try:
            response = self._client.generate(model=self._model, system=system, prompt=prompt)
            text = response["response"]
            if not text:
                raise LLMClientError("LLM call failed")
            return text
        except LLMClientError:
            raise
        except Exception as exc:  # 網路 / 套件 / 空或缺鍵回應一律正規化
            # 訊息保持靜態（不回填後端例外字串）；`from exc` 在 traceback 保留原因。
            raise LLMClientError("LLM call failed") from exc
