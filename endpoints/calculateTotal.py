from fastapi import APIRouter, HTTPException
from models.schemas import TotalCalculationRequest, TotalCalculationResponse
from utils.logger import logger, log_endpoint_call
import time

router = APIRouter()


@router.post("/calculate-total", response_model=TotalCalculationResponse)
async def calculate_total(request: TotalCalculationRequest):
    """
    Calculate total with short-circuit on CRITICAL failures.

    Per spec: Avoid redundant processing when OCR fails.
    Architecture v3.0: Uses SingleOCRValidationResponse objects
    Pure arithmetic - ZERO AI dependency
    """
    start_time = time.time()

    try:
        # ============================================
        # SHORT-CIRCUIT: Check for CRITICAL failures first
        # ============================================
        critical_invoices = [
            v for v in request.individual_validations if v.risk_level == "CRITICAL"
        ]

        if critical_invoices:
            logger.warning(
                "Short-circuiting total calculation due to CRITICAL failures",
                critical_count=len(critical_invoices),
                invoice_ids=[v.invoice_id for v in critical_invoices],
            )

            result = TotalCalculationResponse(
                calculated_total=0.0,
                employee_reported_total=request.employee_reported_total,
                matched=False,
                discrepancy_amount=None,
                discrepancy_message=f"Unable to calculate total: {len(critical_invoices)} invoice(s) have CRITICAL OCR failures requiring manual review",
                currency=request.currency,
            )

            # Log execution
            duration = (time.time() - start_time) * 1000
            log_endpoint_call(
                endpoint="/calculate-total",
                inputs={
                    "invoices_count": len(request.individual_validations),
                    "employee_reported_total": request.employee_reported_total,
                },
                outputs={
                    "matched": result.matched,
                    "critical_failures": len(critical_invoices),
                },
                duration_ms=duration,
            )

            return result

        # ============================================
        # NORMAL CALCULATION: Sum all verified amounts
        # ============================================
        calculated_total = sum(
            validation.verified_amount
            for validation in request.individual_validations
            if validation.verified_amount is not None
        )

        reported_total = request.employee_reported_total

        # ============================================
        # COMPARE TOTALS (with floating-point tolerance)
        # ============================================
        tolerance = 0.01
        # Round to handle floating-point precision issues
        matched = round(abs(calculated_total - reported_total), 2) <= tolerance

        if matched:
            result = TotalCalculationResponse(
                calculated_total=round(calculated_total, 2),
                employee_reported_total=reported_total,
                matched=True,
                discrepancy_amount=0.0,
                discrepancy_message=None,
                currency=request.currency,
            )
        else:
            discrepancy = abs(calculated_total - reported_total)
            result = TotalCalculationResponse(
                calculated_total=round(calculated_total, 2),
                employee_reported_total=reported_total,
                matched=False,
                discrepancy_amount=round(discrepancy, 2),
                discrepancy_message=f"Total is incorrect by {discrepancy:.2f} {request.currency}, should be {calculated_total:.2f} {request.currency}",
                currency=request.currency,
            )

        # Log execution
        duration = (time.time() - start_time) * 1000
        log_endpoint_call(
            endpoint="/calculate-total",
            inputs={
                "invoices_count": len(request.individual_validations),
                "employee_reported_total": request.employee_reported_total,
            },
            outputs={
                "calculated_total": result.calculated_total,
                "matched": result.matched,
                "discrepancy_amount": result.discrepancy_amount,
            },
            duration_ms=duration,
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Total calculation failed",
            error=str(e),
            invoices_count=(
                len(request.individual_validations)
                if request.individual_validations
                else 0
            ),
        )
        raise HTTPException(
            status_code=500, detail=f"Total calculation failed: {str(e)}"
        )
