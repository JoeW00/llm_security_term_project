"""共享狀態契約：所有節點讀寫 IncidentState，所有子系統依賴此檔。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

# critique 反思迴圈的最大迭代次數，超過即強制進入人工核准，避免無限迴圈。
MAX_CRITIQUE_ITERATIONS = 3

Severity = Literal["low", "medium", "high", "critical"]
Verdict = Literal["true_positive", "false_positive", "unknown"]


class Alert(BaseModel):
    """正規化後的資安告警，是本系統的輸入單元。"""

    source: str
    timestamp: str
    category: str
    severity: Severity = "medium"
    message: str
    indicators: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class IncidentState(TypedDict, total=False):
    """LangGraph 的共享狀態。total=False：節點只回傳要更新的鍵。"""

    alert: dict[str, Any]
    alert_type: str
    severity: Severity
    iocs: list[str]
    enrichment: dict[str, Any]
    verdict: Verdict
    confidence: float
    rationale: str
    attack_techniques: list[str]
    playbook: dict[str, Any]
    critique: dict[str, Any]
    critique_iterations: int
    approved: bool
    final_report: dict[str, Any]
