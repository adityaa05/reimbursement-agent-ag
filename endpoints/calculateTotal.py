from fastapi import APIRouter, HTTPException
from models.schemas import TotalCalculationRequest, TotalCalculationResponse

router = APIRouter()


@router.post("/calculate-total", response_model=TotalCalculationResponse)
async def calculate_total(request: TotalCalculationRequest):
    # Calculate total and validate Pure arithmetic
    try:
        # Sum all verified amounts (hard-coded arithmetic)
        calculated_total = sum(
            [
                validation.verified_amount
                for validation in request.individual_validations
            ]
        )

        reported_total = request.employee_reported_total

        # Hard-coded comparison logic
        if abs(calculated_total - reported_total) < 0.01:
            return TotalCalculationResponse(
                calculated_total=calculated_total,
                employee_reported_total=reported_total,
                matched=True,
                discrepancy_amount=0.0,
                discrepancy_message=None,
                currency=request.currency,
            )
        else:
            discrepancy = abs(calculated_total - reported_total)

            # Exact message format from PRD
            message = f"Total is incorrect by {discrepancy:.2f} {request.currency}, should be {calculated_total:.2f} {request.currency}"

            return TotalCalculationResponse(
                calculated_total=calculated_total,
                employee_reported_total=reported_total,
                matched=False,
                discrepancy_amount=discrepancy,
                discrepancy_message=message,
                currency=request.currency,
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Total calculation failed: {str(e)}"
        )
