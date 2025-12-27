import time
from typing import List, Optional, Any, Dict
from fastapi import APIRouter, Body
from pydantic import BaseModel

from utils.logger import logger
from models.schemas import (
    ReportFormatterRequest,
    SingleOCRValidationResponse,
    TotalCalculationResponse,
    PolicyValidationResponse,
    PolicyViolation,
)

# ✅ CRITICAL FIX: Import 'generate_report' but alias it to 'format_report'
# This matches the actual function name in formatReport.py while keeping your code logic intact.
from endpoints.formatReport import generate_report as format_report

router = APIRouter()


class ReportGenerationResponse(BaseModel):
    success: bool
    html_report: str
    plain_report: str
    execution_time_seconds: float
    error: Optional[str]


@router.post("/generate-report", response_model=ReportGenerationResponse)
async def generate_report(
    expense_sheet_id: int = Body(...),
    expense_sheet_name: str = Body(...),
    employee_name: str = Body(...),
    single_ocr_validations: List[Dict[str, Any]] = Body(...),
    # Made optional to handle cases where Agent 4 misses it (handled by format_report logic)
    total_validation: Optional[Dict[str, Any]] = Body(None),
    categories: List[str] = Body(...),
    policy_validations: Optional[List[Dict[str, Any]]] = Body(None),
):
    """
    Agent 4 Tool: Report Generation.
    Refactored to accept explicit arguments matching Agentic Genie.
    """
    start_time = time.time()
    try:
        logger.info(f"Generating report for expense_sheet_id={expense_sheet_id}")

        # Reconstruct Models
        ocr_objs = [SingleOCRValidationResponse(**v) for v in single_ocr_validations]

        # Handle optional total_validation
        total_obj = None
        if total_validation:
            total_obj = TotalCalculationResponse(**total_validation)

        # Handle optional policy_validations
        policy_objs = []
        if policy_validations:
            for p in policy_validations:
                violations = [PolicyViolation(**v) for v in p.get("violations", [])]
                policy_objs.append(
                    PolicyValidationResponse(
                        compliant=p["compliant"],
                        violations=violations,
                        category_found=p["category_found"],
                        max_amount=p.get("max_amount"),
                    )
                )

        report_request = ReportFormatterRequest(
            expense_sheet_id=expense_sheet_id,
            expense_sheet_name=expense_sheet_name,
            employee_name=employee_name,
            single_ocr_validations=ocr_objs,
            total_validation=total_obj,
            categories=categories,
            policy_validations=policy_objs,
        )

        # Call the logic from formatReport.py
        report = await format_report(report_request)
        execution_time = time.time() - start_time

        return ReportGenerationResponse(
            success=True,
            html_report=report.html_comment,
            plain_report=report.formatted_comment,
            execution_time_seconds=round(execution_time, 2),
            error=None,
        )

    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        return ReportGenerationResponse(
            success=False,
            html_report="",
            plain_report="",
            execution_time_seconds=0.0,
            error=str(e),
        )
