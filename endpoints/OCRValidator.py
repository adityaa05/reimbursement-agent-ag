from fastapi import APIRouter, HTTPException
from models.schemas import SingleOCRValidationRequest, SingleOCRValidationResponse
from utils.logger import logger, log_endpoint_call
from utils.validators import validate_currency, normalize_amount, validate_amount
import time

router = APIRouter()


@router.post("/validate-ocr", response_model=SingleOCRValidationResponse)
async def validate_ocr(request: SingleOCRValidationRequest):
    """
    Validates Odoo OCR extracted amount against employee's claimed amount.
    Architecture v3.0: Single OCR source (Odoo only)

    Risk Levels (WithoutTextractContext.txt:257-263):
    - MATCH: Perfect match (<= 0.01 difference)
    - LOW: Small discrepancy (0.01 - 5.00 CHF)
    - MEDIUM: Moderate discrepancy (5.01 - 50.00 CHF)
    - HIGH: Large discrepancy (50.01 - 100.00 CHF)
    - CRITICAL: Very large discrepancy (> 100 CHF) or OCR failed
    """
    start_time = time.time()

    try:
        # ============================================
        # INPUT VALIDATION
        # ============================================
        currency = validate_currency(request.currency)
        claimed_amt = validate_amount(request.employee_claim, "employee_claim")

        odoo_amt = request.odoo_output.total_amount

        # ============================================
        # HANDLE OCR FAILURE (WithoutTextractContext.txt:268-277)
        # ============================================
        if odoo_amt is None:
            result = SingleOCRValidationResponse(
                invoice_id=request.invoice_id,
                odoo_amount=None,
                verified_amount=None,
                employee_reported_amount=claimed_amt,
                amount_matched=False,
                discrepancy_message="Odoo OCR failed to extract amount - manual review required",
                discrepancy_amount=None,
                risk_level="CRITICAL",
                currency=currency,
            )

            # Log execution
            duration = (time.time() - start_time) * 1000
            log_endpoint_call(
                endpoint="/validate-ocr",
                inputs={
                    "invoice_id": request.invoice_id,
                    "employee_claim": request.employee_claim,
                },
                outputs={
                    "risk_level": result.risk_level,
                    "amount_matched": result.amount_matched,
                },
                duration_ms=duration,
            )

            return result

        # ============================================
        # NORMALIZE AMOUNTS
        # ============================================
        odoo_amt = normalize_amount(odoo_amt, currency)
        claimed_amt = normalize_amount(claimed_amt, currency)

        # ============================================
        # VALIDATE AMOUNT (HARD-CODED LOGIC - NO AI)
        # ============================================
        tolerance = 0.01
        # FIX: Round to 2 decimal places to handle floating-point precision
        amount_matched = round(abs(odoo_amt - claimed_amt), 2) <= tolerance

        if amount_matched:
            # FIX 1: Return "MATCH" not "LOW" (WithoutTextractContext.txt:281-289)
            result = SingleOCRValidationResponse(
                invoice_id=request.invoice_id,
                odoo_amount=odoo_amt,
                verified_amount=odoo_amt,
                employee_reported_amount=claimed_amt,
                amount_matched=True,
                discrepancy_message=None,
                discrepancy_amount=0.0,
                risk_level="MATCH",  # CORRECTED
                currency=currency,
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

            result = SingleOCRValidationResponse(
                invoice_id=request.invoice_id,
                odoo_amount=odoo_amt,
                verified_amount=odoo_amt,
                employee_reported_amount=claimed_amt,
                amount_matched=False,
                discrepancy_message=f"Value in invoice as per AG is {odoo_amt:.2f}, not {claimed_amt:.2f} as reported",
                discrepancy_amount=round(discrepancy, 2),
                risk_level=risk,
                currency=currency,
            )

        # Log execution
        duration = (time.time() - start_time) * 1000
        log_endpoint_call(
            endpoint="/validate-ocr",
            inputs={
                "invoice_id": request.invoice_id,
                "employee_claim": request.employee_claim,
            },
            outputs={
                "risk_level": result.risk_level,
                "amount_matched": result.amount_matched,
            },
            duration_ms=duration,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"OCR validation failed", invoice_id=request.invoice_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"OCR validation failed: {str(e)}")
