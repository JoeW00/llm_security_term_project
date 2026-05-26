"""ZeroShotClassifier：雲端零樣本分流基線，僅供消融比較。

以可注入的 chat client 建構，重用 soc_agent 的信任邊界（prompt + 驗證）；
雲端呼叫可 mock，使評估測試維持離線。失敗退回 RuleBasedClassifier。
"""

from __future__ import annotations

from typing import Any, Protocol

from soc_agent.classifier import ClassificationResult, Classifier, RuleBasedClassifier
from soc_agent.classifiers.prompts import (
    TRIAGE_SYSTEM_PROMPT,
    build_triage_prompt,
    parse_classification,
)


class ChatClient(Protocol):
    """最小雲端 chat 介面：吃 system/prompt，回傳模型輸出文字。"""

    def complete(self, *, system: str, prompt: str) -> str: ...


class ZeroShotClassifier:
    """雲端零樣本分類器（消融基線）；輸出經驗證，失敗退回規則式。"""

    def __init__(self, client: ChatClient, fallback: Classifier | None = None) -> None:
        self._client = client
        self._fallback = fallback or RuleBasedClassifier()

    def classify(self, alert: dict[str, Any]) -> ClassificationResult:
        try:
            text = self._client.complete(
                system=TRIAGE_SYSTEM_PROMPT,
                prompt=build_triage_prompt(alert),
            )
            return parse_classification(text)
        except (KeyError, TypeError, ValueError):
            return self._fallback.classify(alert)
