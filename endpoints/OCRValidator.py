from fastapi import APIRouter, HTTPException
from models.schemas import DualOCRValidationRequest, DualOCRValidationResponse

router = APIRouter()


@router.post("/validate-ocr", response_model=DualOCRValidationResponse)
async def validate_ocr(request: DualOCRValidationRequest):
    # Step 1: Check if Textract and Odoo OCR agree; Step 2: Compare consensus amount with employee claim
    try:
        textract_amt = request.textract_output.total_amount
        odoo_amt = request.odoo_output.total_amount
        claimed_amt = request.employee_claim

        # Handle missing OCR data
        if textract_amt is None and odoo_amt is None:
            raise HTTPException(
                status_code=400,
                detail="Both OCR engines failed to extract amount - manual review required",
            )

        # Handle single OCR failure - Textract missing
        if textract_amt is None:
            amount_matched = abs(odoo_amt - claimed_amt) < 0.01
            return DualOCRValidationResponse(
                invoice_id=request.invoice_id,
                textract_amount=None,
                odoo_amount=odoo_amt,
                verified_amount=odoo_amt,
                employee_reported_amount=claimed_amt,
                ocr_consensus=False,
                ocr_mismatch_message="Textract OCR failed - using Odoo OCR only",
                amount_matched=amount_matched,
                discrepancy_message=(
                    f"Value in invoice as per AG is {odoo_amt:.2f}, not {claimed_amt:.2f} as reported"
                    if not amount_matched
                    else None
                ),
                discrepancy_amount=(
                    abs(odoo_amt - claimed_amt) if not amount_matched else 0.0
                ),
                risk_level="HIGH",
                currency=request.currency,
            )

        # Handle single OCR failure - Odoo missing
        if odoo_amt is None:
            amount_matched = abs(textract_amt - claimed_amt) < 0.01
            return DualOCRValidationResponse(
                invoice_id=request.invoice_id,
                textract_amount=textract_amt,
                odoo_amount=None,
                verified_amount=textract_amt,
                employee_reported_amount=claimed_amt,
                ocr_consensus=False,
                ocr_mismatch_message="Odoo OCR failed - using Textract OCR only",
                amount_matched=amount_matched,
                discrepancy_message=(
                    f"Value in invoice as per AG is {textract_amt:.2f}, not {claimed_amt:.2f} as reported"
                    if not amount_matched
                    else None
                ),
                discrepancy_amount=(
                    abs(textract_amt - claimed_amt) if not amount_matched else 0.0
                ),
                risk_level="MEDIUM",
                currency=request.currency,
            )

        # STEP 1: Check OCR consensus
        ocr_tolerance = 0.01
        ocr_consensus = abs(textract_amt - odoo_amt) < ocr_tolerance

        if ocr_consensus:
            verified_amount = textract_amt
            ocr_mismatch_message = None
            base_risk = "LOW"
        else:
            verified_amount = textract_amt
            ocr_mismatch_message = f"OCR disagreement detected: Textract={textract_amt:.2f}, Odoo={odoo_amt:.2f}"
            base_risk = "MEDIUM"

        # STEP 2: Compare verified amount with claim
        claim_tolerance = 0.01
        amount_matched = abs(verified_amount - claimed_amt) < claim_tolerance

        if amount_matched:
            discrepancy_message = None
            discrepancy_amount = 0.0
            final_risk = base_risk
        else:
            discrepancy_amount = abs(verified_amount - claimed_amt)
            discrepancy_message = f"Value in invoice as per AG is {verified_amount:.2f}, not {claimed_amt:.2f} as reported"

            # Risk escalation
            if discrepancy_amount > 50:
                final_risk = "CRITICAL"
            elif discrepancy_amount > 10:
                final_risk = "HIGH"
            elif not ocr_consensus:
                final_risk = "HIGH"
            else:
                final_risk = "MEDIUM"

        return DualOCRValidationResponse(
            invoice_id=request.invoice_id,
            textract_amount=textract_amt,
            odoo_amount=odoo_amt,
            verified_amount=verified_amount,
            employee_reported_amount=claimed_amt,
            ocr_consensus=ocr_consensus,
            ocr_mismatch_message=ocr_mismatch_message,
            amount_matched=amount_matched,
            discrepancy_message=discrepancy_message,
            discrepancy_amount=discrepancy_amount,
            risk_level=final_risk,
            currency=request.currency,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Dual OCR validation failed: {str(e)}"
        )
