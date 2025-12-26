import re
from typing import List, Optional, Any, Dict
from models.schemas import (
    PolicyData,
    PolicyCategory,
    PolicyValidationRequest,
    PolicyValidationResponse,
    PolicyViolation,
)


def find_category_by_name(
    policy_data: PolicyData, category_name: str
) -> Optional[PolicyCategory]:
    """Finds a category in the policy data by name or alias."""
    if not category_name:
        return None

    category_name_norm = category_name.lower().strip()

    for cat in policy_data.categories:
        if cat.name.lower() == category_name_norm:
            return cat
        if category_name_norm in [alias.lower() for alias in cat.aliases]:
            return cat

    return None


def matches_vendor_keywords(vendor: str, keywords: List[str]) -> bool:
    """Checks if the vendor string contains any of the keywords."""
    if not vendor or not keywords:
        return False

    vendor_norm = vendor.lower()
    for kw in keywords:
        if kw.lower() in vendor_norm:
            return True
    return False


def validate_single_invoice_logic(
    request: PolicyValidationRequest, policy_data: PolicyData
) -> PolicyValidationResponse:
    """
    Validates a single invoice against the policy data.
    Used by both the batch validator (Agent 3) and the legacy full-process endpoint.
    """
    category_def = find_category_by_name(policy_data, request.category)
    violations = []

    # 1. Category Existence Check
    if not category_def:
        return PolicyValidationResponse(
            compliant=False,
            violations=[
                PolicyViolation(
                    rule_id="CATEGORY_UNKNOWN",
                    description=f"Category '{request.category}' not found in policy.",
                    severity="BLOCKING",
                )
            ],
            category_found=False,
            max_amount=None,
        )

    # 2. Maximum Amount Check
    if (
        category_def.validation_rules.max_amount
        and request.amount > category_def.validation_rules.max_amount
    ):
        violations.append(
            PolicyViolation(
                rule_id="MAX_AMOUNT_EXCEEDED",
                description=f"Amount {request.amount:.2f} {request.currency} exceeds limit of {category_def.validation_rules.max_amount:.2f} {category_def.validation_rules.currency}",
                severity="WARNING",
            )
        )

    # 3. Receipt Required Check
    if category_def.validation_rules.requires_receipt and not request.has_receipt:
        violations.append(
            PolicyViolation(
                rule_id="RECEIPT_MISSING",
                description=f"Receipt is required for {category_def.name}.",
                severity="BLOCKING",
            )
        )

    # 4. Invoice Age Check
    if request.invoice_age_days is not None:
        # Default to 90 days if not specified in category, generic fallback
        max_age = getattr(category_def.validation_rules, "max_age_days", 90)
        if request.invoice_age_days > max_age:
            violations.append(
                PolicyViolation(
                    rule_id="INVOICE_TOO_OLD",
                    description=f"Invoice is {request.invoice_age_days} days old (Max: {max_age}).",
                    severity="WARNING",
                )
            )

    return PolicyValidationResponse(
        compliant=(len(violations) == 0),
        violations=violations,
        category_found=True,
        max_amount=category_def.validation_rules.max_amount,
    )
