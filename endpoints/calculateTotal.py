from fastapi import APIRouter, HTTPException
from models.schemas import TotalCalculationRequest, TotalCalculationResponse

router = APIRouter()


@router.post("/calculate-total", response_model=TotalCalculationResponse)
async def calculate_total(request: TotalCalculationRequest):
    """
    Calculates total from individual validations and compares with employee's reported total.

    Architecture v3.0: Uses SingleOCRValidationResponse objects
    Pure arithmetic - ZERO AI dependency
    """

    try:
        # Sum all verified amounts (hard-coded arithmetic)
        calculated_total = sum(
            validation.verified_amount
            for validation in request.individual_validations
            if validation.verified_amount is not None
        )

        reported_total = request.employee_reported_total

        # Compare totals (hard-coded tolerance)
        tolerance = 0.01
        matched = abs(calculated_total - reported_total) < tolerance

        if matched:
            return TotalCalculationResponse(
                calculated_total=round(calculated_total, 2),
                employee_reported_total=reported_total,
                matched=True,
                discrepancy_amount=0.0,
                discrepancy_message=None,
                currency=request.currency,
            )
        else:
            discrepancy = abs(calculated_total - reported_total)

            return TotalCalculationResponse(
                calculated_total=round(calculated_total, 2),
                employee_reported_total=reported_total,
                matched=False,
                discrepancy_amount=round(discrepancy, 2),
                discrepancy_message=f"Total is incorrect by {discrepancy:.2f} {request.currency}, should be {calculated_total:.2f} {request.currency}",
                currency=request.currency,
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Total calculation failed: {str(e)}"
        )
