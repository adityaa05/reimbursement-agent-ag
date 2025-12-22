from fastapi import APIRouter, HTTPException
from models.schemas import OCRValidationRequest, OCRValidationResponse

router = APIRouter()


@router.post("/validate-ocr", response_model=OCRValidationResponse)
async def validate_ocr(request: OCRValidationRequest):
    # Compares Textract amount with employee-claimed amount
    try:
        textract_amt = request.textract_amount
        claimed_amt = request.odoo_claimed_amount

        if abs(textract_amt - claimed_amt) < 0.01:  # Tolerance: 0.01 CHF
            # Amounts match
            return OCRValidationResponse(
                invoice_id=request.invoice_id,
                verified_amount=textract_amt,
                employee_reported_amount=claimed_amt,
                matched=True,
                discrepancy_message=None,
                discrepancy_amount=0.0,
                currency=request.currency,
            )
        else:
            # Discrepancy detected
            discrepancy = abs(textract_amt - claimed_amt)

            # Format exact message as required by PRD
            message = f"Value in invoice as per AG is {textract_amt:.2f}, not {claimed_amt:.2f} as reported"

            return OCRValidationResponse(
                invoice_id=request.invoice_id,
                verified_amount=textract_amt,
                employee_reported_amount=claimed_amt,
                matched=False,
                discrepancy_message=message,
                discrepancy_amount=discrepancy,
                currency=request.currency,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
