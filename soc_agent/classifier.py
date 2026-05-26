"""分類邊界：可注入的告警分流分類器契約與離線預設實作。

`triage` 節點透過 `Classifier` 介面取得 `ClassificationResult`。正式環境注入
Ollama 後端，測試注入替身，裸呼叫退回確定性的 `RuleBasedClassifier`。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from soc_agent.state import Severity


class ClassificationResult(BaseModel):
    """分類器的唯一輸出型別；任何實作都必須回傳本型別（已驗證）。"""

    alert_type: str
    severity: Severity = "medium"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


@runtime_checkable
class Classifier(Protocol):
    """結構型介面：吃一筆告警 dict，回傳已驗證的分類結果。"""

    def classify(self, alert: dict[str, Any]) -> ClassificationResult: ...


class RuleBasedClassifier:
    """確定性、離線的預設分類器：取告警既有欄位，缺值時安全退回。"""

    def classify(self, alert: dict[str, Any]) -> ClassificationResult:
        return ClassificationResult(
            alert_type=alert.get("category") or "unknown",
            severity=alert.get("severity") or "medium",
            confidence=1.0,
        )
