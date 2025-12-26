import time
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

from utils.logger import logger
from models.schemas import (
    ReportFormatterRequest,
    SingleOCRValidationResponse,
    TotalCalculationResponse,
    PolicyValidationResponse,
    PolicyViolation,
)
from endpoints.formatReport import format_report

router = APIRouter()

# --- REMOVED DUPLICATE POLICY BATCH LOGIC ---
# The /validate-policies-batch endpoint lives in endpoints/policyValidator.py
# using the strict BatchPolicyValidationRequest schema.


class ReportGenerationRequest(BaseModel):
    """Request for report generation."""

    expense_sheet_id: int
    expense_sheet_name: str
    employee_name: str
    single_ocr_validations: List[dict]
    total_validation: dict
    categories: List[str]
    policy_validations: List[dict]


class ReportGenerationResponse(BaseModel):
    """Response with formatted report."""

    success: bool
    html_report: str
    plain_report: str
    execution_time_seconds: float
    error: Optional[str]


@router.post("/generate-report", response_model=ReportGenerationResponse)
async def generate_report(request: ReportGenerationRequest):
    """
    Agent 4: Report Generation
    Generates formatted HTML/plain text report from all verification results.
    """
    start_time = time.time()
    try:
        logger.info(
            "Generating report",
            expense_sheet_id=request.expense_sheet_id,
            total_invoices=len(request.categories),
        )

        # Convert dicts back to Pydantic models for the formatter
        ocr_validations = [
            SingleOCRValidationResponse(**v) for v in request.single_ocr_validations
        ]

        total_validation = TotalCalculationResponse(**request.total_validation)

        policy_validations = []
        for p in request.policy_validations:
            violations = [PolicyViolation(**v) for v in p.get("violations", [])]
            policy_validations.append(
                PolicyValidationResponse(
                    compliant=p["compliant"],
                    violations=violations,
                    category_found=p["category_found"],
                    max_amount=p.get("max_amount"),
                )
            )

        report_request = ReportFormatterRequest(
            expense_sheet_id=request.expense_sheet_id,
            expense_sheet_name=request.expense_sheet_name,
            employee_name=request.employee_name,
            single_ocr_validations=ocr_validations,
            total_validation=total_validation,
            categories=request.categories,
            policy_validations=policy_validations,
        )

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
        execution_time = time.time() - start_time
        logger.error(
            "Report generation failed",
            expense_sheet_id=request.expense_sheet_id,
            error=str(e),
        )
        return ReportGenerationResponse(
            success=False,
            html_report="",
            plain_report="",
            execution_time_seconds=round(execution_time, 2),
            error=str(e),
        )
