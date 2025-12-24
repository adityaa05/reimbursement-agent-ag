from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class ApprovalDecision(BaseModel):
    """Decision based on risk level and policy compliance"""

    action: str  # "AUTO_APPROVE", "APPROVE_WITH_NOTE", "MANAGER_REVIEW", "ESCALATE", "BLOCK"
    reason: str
    risk_level: str
    policy_compliant: bool
    requires_manual_review: bool
    escalation_notes: Optional[str] = None


class ApprovalRequest(BaseModel):
    expense_sheet_id: int
    amount_risk_level: str  # From OCRValidator
    policy_violations: List[dict]
    total_matched: bool


@router.post("/determine-approval", response_model=ApprovalDecision)
async def determine_approval(request: ApprovalRequest):
    """
    Determines approval action based on amount validation + policy compliance.

    Mapping (WithoutTextractContext.txt:257-263):
    - MATCH + compliant → AUTO_APPROVE
    - LOW + compliant → APPROVE_WITH_NOTE
    - MEDIUM → MANAGER_REVIEW
    - HIGH → ESCALATE
    - CRITICAL → BLOCK

    Policy violations override risk level (always escalate).
    """

    has_violations = len(request.policy_violations) > 0

    # Policy violations always escalate
    if has_violations:
        return ApprovalDecision(
            action="ESCALATE",
            reason=f"{len(request.policy_violations)} policy violation(s) detected",
            risk_level=request.amount_risk_level,
            policy_compliant=False,
            requires_manual_review=True,
            escalation_notes="Policy violations: "
            + ", ".join([v["message"] for v in request.policy_violations]),
        )

    # Amount-based workflow
    if request.amount_risk_level == "MATCH" and request.total_matched:
        return ApprovalDecision(
            action="AUTO_APPROVE",
            reason="All amounts verified and policy-compliant",
            risk_level="MATCH",
            policy_compliant=True,
            requires_manual_review=False,
        )

    elif request.amount_risk_level == "LOW":
        return ApprovalDecision(
            action="APPROVE_WITH_NOTE",
            reason="Minor discrepancy detected but within acceptable threshold",
            risk_level="LOW",
            policy_compliant=True,
            requires_manual_review=False,
            escalation_notes="Informational: Small amount difference noted",
        )

    elif request.amount_risk_level == "MEDIUM":
        return ApprovalDecision(
            action="MANAGER_REVIEW",
            reason="Moderate discrepancy requires manager review",
            risk_level="MEDIUM",
            policy_compliant=True,
            requires_manual_review=True,
            escalation_notes="Manager should verify discrepancy details",
        )

    elif request.amount_risk_level == "HIGH":
        return ApprovalDecision(
            action="ESCALATE",
            reason="Large discrepancy requires manual investigation",
            risk_level="HIGH",
            policy_compliant=True,
            requires_manual_review=True,
            escalation_notes="Investigation required for significant amount difference",
        )

    else:  # CRITICAL
        return ApprovalDecision(
            action="BLOCK",
            reason="Critical issue detected - manual investigation required",
            risk_level="CRITICAL",
            policy_compliant=True,
            requires_manual_review=True,
            escalation_notes="OCR extraction failed or extreme discrepancy",
        )
