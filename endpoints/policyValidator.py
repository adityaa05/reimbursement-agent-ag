from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional
from models.schemas import (
    BatchPolicyValidationRequest,
    BatchPolicyValidationResponse,
    PolicyValidationResponse,
    PolicyViolation,
    PolicyData,
)
from utils.logger import logger
from endpoints.policyStore import get_policy

router = APIRouter()


@router.post("/validate-policies-batch", response_model=BatchPolicyValidationResponse)
async def validate_policies_batch(request: BatchPolicyValidationRequest = Body(...)):
    """
    Agent 3 Tool: Validates expenses against company rules.
    FIX: Generates detailed, manager-friendly violation messages matching PRD.
    """
    try:
        logger.info(
            f"Validating policies for sheet {request.expense_sheet_id}, invoices: {len(request.invoices)}"
        )

        # 1. Fetch Rules
        policy_data = get_policy(request.company_id)
        if not policy_data:
            logger.error(f"No policy data found for {request.company_id}")
            # Fail safe: return compliant if no policy found (or handle as error)
            return BatchPolicyValidationResponse(policy_validations=[])

        validation_results = []

        for invoice in request.invoices:
            violations = []
            category_rules = None

            # 2. Find Category Rules
            # Case-insensitive search
            found_cat = next(
                (
                    c
                    for c in policy_data.categories
                    if c.name.lower() == invoice.category.lower()
                ),
                None,
            )

            # Handle Unknown Category
            if not found_cat:
                if invoice.category.lower() == "unknown":
                    violations.append(
                        PolicyViolation(
                            rule_id="CATEGORY_UNKNOWN",
                            message="Vendor could not be recognized. Manual categorization required.",
                            severity="BLOCKING",
                        )
                    )
                else:
                    # If category exists in invoice but not in policy, default to generic rules if needed
                    # For now, we flag it.
                    violations.append(
                        PolicyViolation(
                            rule_id="CATEGORY_UNSUPPORTED",
                            message=f"Category '{invoice.category}' is not defined in company policy.",
                            severity="WARNING",
                        )
                    )
            else:
                category_rules = found_cat.validation_rules

            # 3. Validate Rules (if category found)
            if category_rules:
                # Rule A: Max Amount Limit
                if (
                    category_rules.max_amount > 0
                    and invoice.amount > category_rules.max_amount
                ):
                    # PRD Format: "Our policy states maximum capping on X is Y, and this is for Z"
                    msg = (
                        f"Our policy states maximum capping on {found_cat.name} is "
                        f"{category_rules.max_amount:.2f} {category_rules.currency}, "
                        f"and this is for {invoice.amount:.2f} {invoice.currency}"
                    )
                    violations.append(
                        PolicyViolation(
                            rule_id="MAX_AMOUNT_EXCEEDED",
                            message=msg,
                            severity="WARNING",
                        )
                    )

                # Rule B: Receipt Requirement
                # Only check if the amount is significant (e.g. > 0)
                if (
                    category_rules.requires_receipt
                    and not invoice.has_receipt
                    and invoice.amount > 0
                ):
                    violations.append(
                        PolicyViolation(
                            rule_id="RECEIPT_MISSING",
                            message=f"Receipt required for {found_cat.name} expenses, but none detected.",
                            severity="ERROR",
                        )
                    )

            # 4. Build Response for this Invoice
            validation_results.append(
                PolicyValidationResponse(
                    compliant=(len(violations) == 0),
                    violations=violations,
                    category_found=(found_cat is not None),
                    max_amount=category_rules.max_amount if category_rules else None,
                )
            )

        return BatchPolicyValidationResponse(policy_validations=validation_results)

    except Exception as e:
        logger.error(f"Policy validation failed: {str(e)}")
        # Return empty list or basic error structure to keep workflow alive
        return BatchPolicyValidationResponse(policy_validations=[])
