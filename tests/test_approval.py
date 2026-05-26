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


def test_policies_satisfy_protocol():
    assert isinstance(AutoApprovePolicy(), ApprovalPolicy)
    assert isinstance(InterruptApprovalPolicy(), ApprovalPolicy)
