from fastapi import APIRouter, HTTPException
from models.schemas import SingleOCRValidationRequest, SingleOCRValidationResponse

router = APIRouter()


@router.post("/validate-ocr", response_model=SingleOCRValidationResponse)
async def validate_ocr(request: SingleOCRValidationRequest):
    """
    Validates Odoo OCR extracted amount against employee's claimed amount.

    Architecture v3.0: Single OCR source (Odoo only)

    Risk Levels (WithoutTextractContext.txt:257-263):
    - MATCH: Perfect match (< 0.01 difference)
    - LOW: Small discrepancy (0.01 - 5.00 CHF)
    - MEDIUM: Moderate discrepancy (5.01 - 50.00 CHF)
    - HIGH: Large discrepancy (50.01 - 100.00 CHF)
    - CRITICAL: Very large discrepancy (> 100 CHF) or OCR failed
    """

    try:
        odoo_amt = request.odoo_output.total_amount
        claimed_amt = request.employee_claim

        # ============================================
        # HANDLE OCR FAILURE (WithoutTextractContext.txt:268-277)
        # ============================================
        if odoo_amt is None:
            return SingleOCRValidationResponse(
                invoice_id=request.invoice_id,
                odoo_amount=None,
                verified_amount=None,
                employee_reported_amount=claimed_amt,
                amount_matched=False,
                discrepancy_message="Odoo OCR failed to extract amount - manual review required",
                discrepancy_amount=None,
                risk_level="CRITICAL",
                currency=request.currency,
            )

        # ============================================
        # VALIDATE AMOUNT (HARD-CODED LOGIC - NO AI)
        # ============================================
        tolerance = 0.01
        amount_matched = abs(odoo_amt - claimed_amt) < tolerance

        if amount_matched:
            # FIX 1: Return "MATCH" not "LOW" (WithoutTextractContext.txt:281-289)
            return SingleOCRValidationResponse(
                invoice_id=request.invoice_id,
                odoo_amount=odoo_amt,
                verified_amount=odoo_amt,
                employee_reported_amount=claimed_amt,
                amount_matched=True,
                discrepancy_message=None,
                discrepancy_amount=0.0,
                risk_level="MATCH",  # CORRECTED
                currency=request.currency,
            )
        else:
            # Mismatch detected
            discrepancy = abs(odoo_amt - claimed_amt)

            # ============================================
            # RISK ASSESSMENT (WithoutTextractContext.txt:295-303)
            # ============================================
            if discrepancy > 100:
                risk = "CRITICAL"
            elif discrepancy > 50:
                risk = "HIGH"  # FIX 2: Proper assignment (was stray literal)
            elif discrepancy > 5:
                risk = "MEDIUM"
            else:
                risk = "LOW"

            return SingleOCRValidationResponse(
                invoice_id=request.invoice_id,
                odoo_amount=odoo_amt,
                verified_amount=odoo_amt,
                employee_reported_amount=claimed_amt,
                amount_matched=False,
                discrepancy_message=f"Value in invoice as per AG is {odoo_amt:.2f}, not {claimed_amt:.2f} as reported",
                discrepancy_amount=round(discrepancy, 2),
                risk_level=risk,
                currency=request.currency,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR validation failed: {str(e)}")
