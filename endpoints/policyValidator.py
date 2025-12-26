from typing import List
from fastapi import APIRouter, HTTPException
from models.schemas import (
    PolicyValidationRequest,
    PolicyValidationResponse,
    PolicyViolation,
    BatchPolicyValidationRequest,
    BatchPolicyValidationResponse,
)
from endpoints.policyStore import get_policy, find_category_by_name

router = APIRouter()


def validate_single_invoice_logic(
    policy_data,
    category: str,
    amount: float,
    currency: str,
    vendor: str,
    has_receipt: bool,
    invoice_age_days: int,
) -> PolicyValidationResponse:
    category_def = find_category_by_name(policy_data, category)

    if not category_def:
        return PolicyValidationResponse(
            compliant=False,
            violations=[
                PolicyViolation(
                    rule="CATEGORY_NOT_FOUND",
                    message=f"Category '{category}' not found in company policy",
                    severity="ERROR",
                )
            ],
            category_found=False,
            max_amount=None,
        )

    violations = []
    rules = category_def.validation_rules

    if amount > rules.max_amount:
        violations.append(
            PolicyViolation(
                rule="EXCEEDS_MAX_AMOUNT",
                message=f"Our policy states maximum capping on {category_def.name} is {rules.max_amount} {rules.currency}, and this is for {currency} {amount:.2f}",
                severity="ERROR",
            )
        )

    if rules.requires_receipt and not has_receipt:
        violations.append(
            PolicyViolation(
                rule="MISSING_RECEIPT",
                message=f"Receipt is required for {category_def.name} expenses",
                severity="ERROR",
            )
        )

    if rules.max_age_days and invoice_age_days is not None:
        if invoice_age_days > rules.max_age_days:
            violations.append(
                PolicyViolation(
                    rule="INVOICE_TOO_OLD",
                    message=f"Invoice is {invoice_age_days} days old, exceeds {rules.max_age_days} day limit",
                    severity="WARNING",
                )
            )

    if rules.approved_vendors and vendor:
        vendor_approved = any(
            approved.lower() in vendor.lower() for approved in rules.approved_vendors
        )
        if not vendor_approved:
            violations.append(
                PolicyViolation(
                    rule="UNAPPROVED_VENDOR",
                    message=f"Vendor '{vendor}' is not in approved vendor list for {category_def.name}",
                    severity="WARNING",
                )
            )

    return PolicyValidationResponse(
        compliant=(len(violations) == 0),
        violations=violations,
        category_found=True,
        max_amount=rules.max_amount,
    )


@router.post("/validate-policy", response_model=PolicyValidationResponse)
async def validate_policy(request: PolicyValidationRequest):
    """Single invoice validation (Legacy)."""
    try:
        policy_data = get_policy(request.company_id)
        return validate_single_invoice_logic(
            policy_data,
            request.category,
            request.amount,
            request.currency,
            request.vendor,
            request.has_receipt,
            request.invoice_age_days,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Policy validation failed: {str(e)}"
        )


@router.post("/validate-policies-batch", response_model=BatchPolicyValidationResponse)
async def validate_policies_batch(request: BatchPolicyValidationRequest):
    """Agent 3 Endpoint: Batch validation using AI categories."""
    try:
        policy_data = get_policy(request.company_id)
        results = []
        for invoice in request.invoices:
            validation = validate_single_invoice_logic(
                policy_data,
                invoice.category,
                invoice.amount,
                invoice.currency,
                invoice.vendor,
                invoice.has_receipt,
                invoice.invoice_age_days,
            )
            results.append(validation)
        return BatchPolicyValidationResponse(policy_validations=results)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Batch validation failed: {str(e)}"
        )
