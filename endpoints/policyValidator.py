from fastapi import APIRouter, HTTPException
from models.schemas import (
    PolicyValidationRequest,
    PolicyValidationResponse,
    PolicyViolation,
)
from endpoints.policyStore import get_policy, find_category_by_name

router = APIRouter()


@router.post("/validate-policy", response_model=PolicyValidationResponse)
async def validate_policy(request: PolicyValidationRequest):
    """
    MISSION-CRITICAL: Validate expense against policy rules

    Uses policy data from policy store (Phase 1: mock, Phase 2: Confluence)
    ZERO AI involvement - pure rule engine with hard-coded logic

    Rules checked:
    1. Max amount limit (hard-coded comparison, dynamic limit from policy)
    2. Receipt requirement (hard-coded logic, dynamic rule from policy)
    3. Invoice age limit (hard-coded comparison, dynamic limit from policy)
    4. Approved vendors (hard-coded matching, dynamic list from policy)
    5. Attendees requirement (hard-coded check, dynamic rule from policy)
    """
    try:
        # Fetch policy rules (cached)
        policy_data = get_policy(request.company_id)

        # Find category definition in policy
        category_def = find_category_by_name(policy_data, request.category)

        if not category_def:
            return PolicyValidationResponse(
                compliant=False,
                category_found=False,
                violations=[
                    PolicyViolation(
                        rule="CATEGORY_NOT_FOUND",
                        message=f"Category '{request.category}' not found in company policy",
                        severity="ERROR",
                    )
                ],
                max_amount=None,
            )

        violations = []
        validation_rules = category_def.validation_rules

        # RULE 1: Check max amount (HARD-CODED COMPARISON, DYNAMIC LIMIT)
        if request.amount > validation_rules.max_amount:
            violations.append(
                PolicyViolation(
                    rule="EXCEEDS_MAX_AMOUNT",
                    message=f"Our policy states maximum capping on {category_def.name} is {validation_rules.max_amount} {validation_rules.currency}, and this is for {request.currency} {request.amount:.2f}",
                    severity="ERROR",
                )
            )

        # RULE 2: Check receipt requirement (HARD-CODED LOGIC, DYNAMIC RULE)
        if validation_rules.requires_receipt and not request.has_receipt:
            violations.append(
                PolicyViolation(
                    rule="MISSING_RECEIPT",
                    message=f"Receipt is required for {category_def.name} expenses",
                    severity="ERROR",
                )
            )

        # RULE 3: Check invoice age (HARD-CODED COMPARISON, DYNAMIC LIMIT)
        if validation_rules.max_age_days and request.invoice_age_days is not None:
            if request.invoice_age_days > validation_rules.max_age_days:
                violations.append(
                    PolicyViolation(
                        rule="INVOICE_TOO_OLD",
                        message=f"Invoice is {request.invoice_age_days} days old, exceeds {validation_rules.max_age_days} day limit",
                        severity="WARNING",
                    )
                )

        # RULE 4: Check approved vendors (HARD-CODED MATCHING, DYNAMIC LIST)
        if validation_rules.approved_vendors and request.vendor:
            vendor_approved = any(
                approved.lower() in request.vendor.lower()
                for approved in validation_rules.approved_vendors
            )
            if not vendor_approved:
                violations.append(
                    PolicyViolation(
                        rule="UNAPPROVED_VENDOR",
                        message=f"Vendor '{request.vendor}' is not in approved vendor list for {category_def.name}",
                        severity="WARNING",
                    )
                )

        # RULE 5: Check attendees requirement (HARD-CODED CHECK, DYNAMIC RULE)
        if validation_rules.requires_attendees is True:
            if request.has_attendees is None or not request.has_attendees:
                violations.append(
                    PolicyViolation(
                        rule="MISSING_ATTENDEES",
                        message=f"Client/attendee names are required for {category_def.name} expenses",
                        severity="ERROR",
                    )
                )

        return PolicyValidationResponse(
            compliant=(len(violations) == 0),
            violations=violations,
            category_found=True,
            max_amount=validation_rules.max_amount,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Policy validation failed: {str(e)}"
        )
