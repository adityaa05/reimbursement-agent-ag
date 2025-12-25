from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import time
from utils.logger import logger


# Import schemas
from models.schemas import (
    PolicyValidationRequest,
    PolicyValidationResponse,
    ReportFormatterRequest,
)
from endpoints.policyValidator import validate_policy
from endpoints.formatReport import format_report


router = APIRouter()


class PolicyValidationBatchRequest(BaseModel):
    """Request for batch policy validation"""

    expense_sheet_id: int
    invoices: List[dict]  # List of {invoice_number, category, amount, vendor, ...}
    company_id: str = "hashgraph_inc"


class PolicyValidationBatchResponse(BaseModel):
    """Response with all policy validations"""

    success: bool
    expense_sheet_id: int
    policy_validations: List[dict]  # List of PolicyValidationResponse
    total_violations: int
    execution_time_seconds: float
    error: Optional[str]


class ReportGenerationRequest(BaseModel):
    """Request for report generation"""

    expense_sheet_id: int
    expense_sheet_name: str
    employee_name: str
    single_ocr_validations: List[dict]  # From Agent 1
    total_validation: dict  # From Agent 1
    categories: List[str]  # From Agent 2 (AI enhanced)
    policy_validations: List[dict]  # From Agent 3


class ReportGenerationResponse(BaseModel):
    """Response with formatted report"""

    success: bool
    html_report: str
    plain_report: str
    execution_time_seconds: float
    error: Optional[str]


@router.post("/validate-policies-batch", response_model=PolicyValidationBatchResponse)
async def validate_policies_batch(request: PolicyValidationBatchRequest):
    """
    AGENT 3: Batch Policy Validation

    Takes AI-enhanced categories from Agent 2 and validates ALL invoices
    against company policies.

    Input: List of invoices with AI-enhanced categories
    Output: Policy validation results for each invoice
    """

    start_time = time.time()

    try:
        logger.info(
            "Starting batch policy validation",
            expense_sheet_id=request.expense_sheet_id,
            total_invoices=len(request.invoices),
        )

        policy_validations = []

        for invoice in request.invoices:
            # Build policy validation request
            policy_request = PolicyValidationRequest(
                category=invoice.get("category"),
                amount=invoice.get("amount", 0.0),
                currency=invoice.get("currency", "CHF"),
                vendor=invoice.get("vendor"),
                has_receipt=invoice.get("has_receipt", True),
                invoice_age_days=invoice.get("invoice_age_days", 15),
                company_id=request.company_id,
            )

            # Validate policy
            policy_result = await validate_policy(policy_request)

            # Convert to dict for JSON serialization
            policy_validations.append(
                {
                    "invoice_number": invoice.get("invoice_number"),
                    "compliant": policy_result.compliant,
                    "violations": [
                        {
                            "rule": v.rule,
                            "message": v.message,
                            "severity": v.severity,
                        }
                        for v in policy_result.violations
                    ],
                    "category_found": policy_result.category_found,
                    "max_amount": policy_result.max_amount,
                }
            )

            logger.info(
                f"Invoice {invoice.get('invoice_number')} policy validated",
                category=invoice.get("category"),
                compliant=policy_result.compliant,
                violations=len(policy_result.violations),
            )

        # Calculate summary
        total_violations = sum(1 for p in policy_validations if not p["compliant"])

        execution_time = time.time() - start_time

        logger.info(
            "Batch policy validation complete",
            total_invoices=len(request.invoices),
            total_violations=total_violations,
            execution_time=f"{execution_time:.2f}s",
        )

        return PolicyValidationBatchResponse(
            success=True,
            expense_sheet_id=request.expense_sheet_id,
            policy_validations=policy_validations,
            total_violations=total_violations,
            execution_time_seconds=round(execution_time, 2),
            error=None,
        )

    except Exception as e:
        execution_time = time.time() - start_time

        logger.error(
            "Batch policy validation failed",
            expense_sheet_id=request.expense_sheet_id,
            error=str(e),
        )

        return PolicyValidationBatchResponse(
            success=False,
            expense_sheet_id=request.expense_sheet_id,
            policy_validations=[],
            total_violations=0,
            execution_time_seconds=round(execution_time, 2),
            error=str(e),
        )


@router.post("/generate-report", response_model=ReportGenerationResponse)
async def generate_report(request: ReportGenerationRequest):
    """
    AGENT 4: Report Generation

    Takes all verification results and generates formatted HTML/plain text report.

    Input: Verification + Categories + Policy results
    Output: Formatted report ready for posting
    """

    start_time = time.time()

    try:
        logger.info(
            "Generating report",
            expense_sheet_id=request.expense_sheet_id,
            total_invoices=len(request.categories),
        )

        # Convert dict inputs back to proper schemas for formatReport
        from models.schemas import (
            SingleOCRValidationResponse,
            TotalCalculationResponse,
            PolicyValidationResponse,
            PolicyViolation,
        )

        # Rebuild validation objects
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

        # Generate report
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

        logger.info(
            "Report generated successfully",
            html_length=len(report.html_comment),
            execution_time=f"{execution_time:.2f}s",
        )

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
