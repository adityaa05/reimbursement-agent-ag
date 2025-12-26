import time
from fastapi import APIRouter, HTTPException

from models.schemas import SingleOCRValidationRequest, SingleOCRValidationResponse
from utils.logger import logger, log_endpoint_call
from utils.validators import validate_currency, normalize_amount, validate_amount

router = APIRouter()


@router.post("/validate-ocr", response_model=SingleOCRValidationResponse)
async def validate_ocr(request: SingleOCRValidationRequest):
    """Validates Odoo OCR extracted amount against employee's claimed amount."""
    start_time = time.time()
    try:
        currency = validate_currency(request.currency)
        claimed_amt = validate_amount(request.employee_claim, "employee_claim")
        odoo_amt = request.odoo_output.total_amount

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

        odoo_amt = normalize_amount(odoo_amt, currency)
        claimed_amt = normalize_amount(claimed_amt, currency)

        tolerance = 0.01
        amount_matched = round(abs(odoo_amt - claimed_amt), 2) <= tolerance

        if amount_matched:
            result = SingleOCRValidationResponse(
                invoice_id=request.invoice_id,
                odoo_amount=odoo_amt,
                verified_amount=odoo_amt,
                employee_reported_amount=claimed_amt,
                amount_matched=True,
                discrepancy_message=None,
                discrepancy_amount=0.0,
                risk_level="MATCH",
                currency=currency,
            )

        else:
            discrepancy = abs(odoo_amt - claimed_amt)

            if discrepancy > 100:
                risk = "CRITICAL"
            elif discrepancy > 50:
                risk = "HIGH"
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
