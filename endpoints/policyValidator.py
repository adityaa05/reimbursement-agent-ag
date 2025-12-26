from fastapi import APIRouter, HTTPException, Body
from typing import List
from models.schemas import (
    BatchPolicyValidationResponse,
    PolicyValidationResponse,
    PolicyValidationRequest,
    InvoiceWithCategory,
)
from utils.logger import logger
from utils.policy_helpers import validate_single_invoice_logic
from endpoints.policyStore import get_policy

router = APIRouter()


@router.post("/validate-policies-batch", response_model=BatchPolicyValidationResponse)
async def validate_policies_batch(
    expense_sheet_id: int = Body(...),
    invoices: List[InvoiceWithCategory] = Body(...),
    company_id: str = Body("hashgraph_inc"),
):
    """
    Agent 3 Tool: Validates policies for a batch of invoices.
    Refactored to accept explicit arguments.
    """
    try:
        logger.info(
            f"Validating policies for sheet {expense_sheet_id}, invoices: {len(invoices)}"
        )
        policy_data = get_policy(company_id)

        results = []
        for invoice in invoices:
            # Logic remains the same, just mapping inputs
            single_req = PolicyValidationRequest(
                category=invoice.category,
                amount=invoice.amount,
                currency=invoice.currency,
                vendor=invoice.vendor,
                has_receipt=invoice.has_receipt,
                invoice_age_days=invoice.invoice_age_days,
                company_id=company_id,
            )

            validation_result = validate_single_invoice_logic(single_req, policy_data)
            results.append(validation_result)

        return BatchPolicyValidationResponse(policy_validations=results)

    except Exception as e:
        logger.error(f"Policy batch validation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
