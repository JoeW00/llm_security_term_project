"""人工核准邊界：可注入的核准政策 + 決策模型。

預設自動核准（保留骨架行為、離線跑到底）；互動模式用 LangGraph interrupt 暫停等待人工。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from langgraph.types import interrupt
from pydantic import BaseModel

from soc_agent.state import IncidentState


class ApprovalDecision(BaseModel):
    """人工核准決策：是否核准 + 理由。"""

    approved: bool
    reason: str = ""


@runtime_checkable
class ApprovalPolicy(Protocol):
    """核准政策介面：讀唯讀 state，回傳核准決策。"""

    def decide(self, state: IncidentState) -> ApprovalDecision: ...


class AutoApprovePolicy:
    """確定性預設：一律自動核准（保留骨架行為，不需 checkpointer）。"""

    def decide(self, state: IncidentState) -> ApprovalDecision:
        return ApprovalDecision(approved=True, reason="auto-approved")


class InterruptApprovalPolicy:
    """互動模式：以 LangGraph interrupt 暫停等待人工核准/駁回 + 理由。

    需圖以 checkpointer 編譯。resume 值經 ApprovalDecision 驗證；畸形時保守駁回，
    不因不可信／畸形輸入誤放行。
    """

    def decide(self, state: IncidentState) -> ApprovalDecision:
        response = interrupt(self._payload(state))
        return self._to_decision(response)

    @staticmethod
    def _payload(state: IncidentState) -> dict[str, Any]:
        return {
            "verdict": state.get("verdict"),
            "severity": state.get("severity"),
            "rationale": state.get("rationale", ""),
            "playbook": state.get("playbook", {}),
        }

    @staticmethod
    def _to_decision(response: Any) -> ApprovalDecision:
        # strict=True：只接受真正的 bool，拒絕 "true"/1/"yes" 等寬鬆強制轉換，
        # 確保安全閘門不因鬆散型別的人工 UI 輸入而誤放行。
        try:
            return ApprovalDecision.model_validate(response, strict=True)
        except (TypeError, ValueError):
            return ApprovalDecision(
                approved=False, reason="invalid approval response; rejected by default"
            )
