import pytest
from pydantic import ValidationError

from soc_agent.approval import (
    ApprovalDecision,
    ApprovalPolicy,
    AutoApprovePolicy,
    InterruptApprovalPolicy,
)


def test_approval_decision_validates():
    d = ApprovalDecision(approved=False, reason="risky")
    assert d.approved is False
    assert d.reason == "risky"


def test_approval_decision_requires_approved():
    with pytest.raises(ValidationError):
        ApprovalDecision(reason="no approved field")


def test_auto_approve_policy_approves():
    d = AutoApprovePolicy().decide({})
    assert d.approved is True
    assert d.reason == "auto-approved"


def test_interrupt_policy_maps_valid_resume():
    d = InterruptApprovalPolicy._to_decision({"approved": False, "reason": "looks malicious"})
    assert d.approved is False
    assert d.reason == "looks malicious"


def test_interrupt_policy_rejects_malformed_resume():
    d = InterruptApprovalPolicy._to_decision("garbage")
    assert d.approved is False
    assert "rejected by default" in d.reason


def test_interrupt_policy_rejects_missing_approved_key():
    d = InterruptApprovalPolicy._to_decision({"reason": "only reason"})
    assert d.approved is False


def test_interrupt_policy_rejects_coerced_truthy_approved():
    # 鬆散型別的 UI 可能送字串/整數；strict 驗證須拒絕、保守駁回，不得誤放行
    for bad in ({"approved": "true"}, {"approved": 1}, {"approved": "yes"}):
        d = InterruptApprovalPolicy._to_decision(bad)
        assert d.approved is False, f"{bad!r} must NOT auto-approve"


def test_policies_satisfy_protocol():
    assert isinstance(AutoApprovePolicy(), ApprovalPolicy)
    assert isinstance(InterruptApprovalPolicy(), ApprovalPolicy)
