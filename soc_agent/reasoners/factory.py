"""建構 live LLM reasoner 的工廠：取 LLM client（雲端 Anthropic 或地端 ollama），
包成三個推理器。

`import anthropic` / `import ollama` 皆為延遲匯入（僅在對應工廠內），核心測試無需安裝。
"""

from __future__ import annotations

import os
from typing import Any

from soc_agent.reasoners.anthropic_client import AnthropicLLMClient
from soc_agent.reasoners.critic import LLMCritic
from soc_agent.reasoners.investigator import LLMInvestigator
from soc_agent.reasoners.ollama_client import OllamaLLMClient
from soc_agent.reasoners.playbook import LLMPlaybookGenerator
from soc_agent.reasoning import LLMClient

_DEFAULT_MODEL = "claude-sonnet-4-6"
_DEFAULT_OLLAMA_MODEL = "qwen2.5:7b"


def anthropic_llm_client(
    model: str = _DEFAULT_MODEL, *, max_tokens: int = 1024
) -> AnthropicLLMClient:
    """從 `ANTHROPIC_API_KEY` 建 Anthropic client 並包成 `AnthropicLLMClient`。

    缺金鑰或未安裝 anthropic 套件時，丟帶清楚訊息的 RuntimeError。
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY 未設定；live LLM 需要它（export ANTHROPIC_API_KEY=...）。"
        )
    try:
        import anthropic
    except ImportError as exc:
        raise RuntimeError(
            "未安裝 anthropic 套件；請以 `uv run --group llm ...` 執行或安裝 anthropic。"
        ) from exc
    return AnthropicLLMClient(anthropic.Anthropic(), model=model, max_tokens=max_tokens)


def ollama_llm_client(model: str = _DEFAULT_OLLAMA_MODEL) -> OllamaLLMClient:
    """建一個查地端 ollama 的 LLMClient（全本地、無金鑰）。缺 ollama 套件時丟清楚 RuntimeError。"""
    try:
        import ollama
    except ImportError as exc:
        raise RuntimeError(
            "未安裝 ollama 套件；地端 LLM 需要它（uv run --group eval ...）。"
        ) from exc
    return OllamaLLMClient(ollama, model=model)


def llm_reasoners(client: LLMClient) -> dict[str, Any]:
    """把一個 LLMClient 包成三個 LLM reasoner；鍵名對齊 build_graph 參數。"""
    return {
        "investigator": LLMInvestigator(client),
        "playbook_gen": LLMPlaybookGenerator(client),
        "critic": LLMCritic(client),
    }
