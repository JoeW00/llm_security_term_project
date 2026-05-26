"""OllamaClassifier：呼叫本地 Ollama 微調模型做告警分流。

以可注入的 client 建構（測試 mock、正式注入 ollama 套件的 client），輸出經
信任邊界驗證；解析或驗證失敗時退回 RuleBasedClassifier 的確定性保守結果。
"""

from __future__ import annotations

from typing import Any, Protocol

from soc_agent.classifier import ClassificationResult, Classifier, RuleBasedClassifier
from soc_agent.classifiers.prompts import (
    TRIAGE_SYSTEM_PROMPT,
    build_triage_prompt,
    parse_classification,
)


class OllamaClient(Protocol):
    """最小 Ollama 介面：吃 model/system/prompt，回傳含 'response' 鍵的 dict。"""

    def generate(self, *, model: str, system: str, prompt: str) -> dict[str, Any]: ...


class OllamaClassifier:
    """呼叫 Ollama 微調模型；輸出經驗證，失敗退回規則式保守結果。"""

    def __init__(
        self,
        client: OllamaClient,
        model: str,
        fallback: Classifier | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._fallback = fallback or RuleBasedClassifier()

    def classify(self, alert: dict[str, Any]) -> ClassificationResult:
        try:
            raw = self._client.generate(
                model=self._model,
                system=TRIAGE_SYSTEM_PROMPT,
                prompt=build_triage_prompt(alert),
            )
            return parse_classification(raw["response"])
        except (KeyError, TypeError, ValueError):
            # 畸形輸出不得污染狀態：退回確定性保守結果。
            return self._fallback.classify(alert)
