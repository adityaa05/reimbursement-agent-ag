import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from utils.logger import logger, set_correlation_id
from endpoints.fetchOdooExpense import fetch_odoo_expense
from endpoints.odooOCR import odoo_ocr
from endpoints.OCRValidator import validate_ocr
from endpoints.calculateTotal import calculate_total
from endpoints.enrichCategory import enrich_category
from endpoints.policyValidator import validate_policy
from endpoints.formatReport import format_report
from models.schemas import (
    OdooExpenseFetchRequest,
    OdooOCRRequest,
    SingleOCRValidationRequest,
    TotalCalculationRequest,
    EnrichCategoryRequest,
    PolicyValidationRequest,
    ReportFormatterRequest,
)

router = APIRouter()


class ProcessExpenseVerificationRequest(BaseModel):
    """Request for verification workflow."""

    expense_sheet_id: int
    odoo_url: str
    odoo_db: str
    odoo_username: str
    odoo_password: str
    company_id: str = "hashgraph_inc"


class InvoiceVerificationResult(BaseModel):
    """Result for a single invoice."""

    invoice_number: int
    invoice_id: str
    vendor: Optional[str]
    ocr_amount: Optional[float]
    claimed_amount: float
    verified_amount: Optional[float]
    amount_matched: bool
    risk_level: str
    discrepancy_message: Optional[str]
    category: str
    category_confidence: float
    policy_compliant: bool
    policy_violations: List[Dict[str, Any]]


class ProcessExpenseVerificationResponse(BaseModel):
    """Complete expense verification result."""

    success: bool
    expense_sheet_id: int
    employee_name: str
    expense_sheet_name: str
    total_invoices: int
    execution_time_seconds: float
    invoices: List[InvoiceVerificationResult]
    calculated_total: float
    employee_reported_total: float
    total_matched: bool
    total_discrepancy: Optional[float]
    amount_mismatches: int
    policy_violations: int
    high_risk_invoices: int
    html_report: str
    plain_report: str
    error: Optional[str]


@router.post(
    "/process-expense-verification", response_model=ProcessExpenseVerificationResponse
)
async def process_expense_verification(request: ProcessExpenseVerificationRequest):
    """
    Verification endpoint that orchestrates the complete expense verification process
    and returns report data without posting to Odoo.
    """
    start_time = time.time()
    try:
        set_correlation_id(request.expense_sheet_id)
        logger.info(
            "Starting expense verification workflow (no posting)",
            expense_sheet_id=request.expense_sheet_id,
            company_id=request.company_id,
        )

        logger.info("Step 1: Fetching expense data from Odoo")
        fetch_request = OdooExpenseFetchRequest(
            expense_sheet_id=request.expense_sheet_id,
            odoo_url=request.odoo_url,
            odoo_db=request.odoo_db,
            odoo_username=request.odoo_username,
            odoo_password=request.odoo_password,
        )

        expense_data = await fetch_odoo_expense(fetch_request)
        expense_sheet = expense_data.get("expense_sheet", {})
        expense_lines = expense_data.get("expense_lines", [])

        employee_info = expense_sheet.get("employee_id", [None, "Unknown"])
        employee_name = (
            employee_info[1] if isinstance(employee_info, list) else "Unknown"
        )

        expense_name = expense_sheet.get("name", "Unknown")
        employee_total = expense_sheet.get("total_amount", 0.0)
        currency = "CHF"

        logger.info(
            "Expense data fetched",
            employee=employee_name,
            total_invoices=len(expense_lines),
            employee_total=employee_total,
        )

        if not expense_lines:
            raise HTTPException(
                status_code=400,
                detail=f"No expense lines found for expense sheet {request.expense_sheet_id}",
            )

        logger.info("Step 2: Extracting OCR data for all invoices")
        ocr_results = []
        for idx, line in enumerate(expense_lines):
            line_id = line.get("id")
            claimed_amount = line.get("total_amount", 0.0)
            logger.info(
                f"Processing invoice {idx + 1}/{len(expense_lines)}",
                line_id=line_id,
                claimed_amount=claimed_amount,
            )

            ocr_request = OdooOCRRequest(
                expense_line_id=line_id,
                odoo_url=request.odoo_url,
                odoo_db=request.odoo_db,
                odoo_username=request.odoo_username,
                odoo_password=request.odoo_password,
            )

            ocr_result = await odoo_ocr(ocr_request)
            ocr_results.append(
                {
                    "ocr_data": ocr_result,
                    "claimed_amount": claimed_amount,
                    "invoice_number": idx + 1,
                }
            )
        logger.info(f"OCR extraction complete for {len(ocr_results)} invoices")

        logger.info("Step 3: Validating amounts (hard-coded logic)")
        validation_results = []
        for ocr_data in ocr_results:
            invoice_num = ocr_data["invoice_number"]
            validation_request = SingleOCRValidationRequest(
                odoo_output=ocr_data["ocr_data"],
                employee_claim=ocr_data["claimed_amount"],
                invoice_id=f"INV-{invoice_num}",
                currency=currency,
            )

            validation_result = await validate_ocr(validation_request)
            validation_results.append(validation_result)
            logger.info(
                f"Invoice {invoice_num} validated",
                matched=validation_result.amount_matched,
                risk_level=validation_result.risk_level,
            )

        logger.info("Step 4: Calculating total (pure math)")
        total_request = TotalCalculationRequest(
            individual_validations=validation_results,
            employee_reported_total=employee_total,
            currency=currency,
        )

        total_validation = await calculate_total(total_request)
        logger.info(
            "Total calculation complete",
            calculated=total_validation.calculated_total,
            reported=total_validation.employee_reported_total,
            matched=total_validation.matched,
        )

        logger.info("Step 5: Enriching categories (Confluence policies)")
        enriched_categories = []
        for idx, ocr_data in enumerate(ocr_results):
            invoice_num = ocr_data["invoice_number"]
            ocr_result = ocr_data["ocr_data"]

            product_info = expense_lines[idx].get("product_id", [None, None])
            existing_category = (
                product_info[1]
                if isinstance(product_info, list) and len(product_info) > 1
                else None
            )

            enrich_request = EnrichCategoryRequest(
                vendor=ocr_result.vendor,
                date=ocr_result.date,
                time=ocr_result.time,
                total_amount=ocr_result.total_amount,
                existing_category=existing_category,
                invoice_id=f"INV-{invoice_num}",
                company_id=request.company_id,
            )

            category_result = await enrich_category(enrich_request)
            enriched_categories.append(category_result)
            logger.info(
                f"Invoice {invoice_num} categorized",
                category=category_result.suggested_category,
                confidence=category_result.confidence,
            )

        logger.info("Step 6: Validating policy compliance (rule engine)")
        policy_validations = []
        for idx, (validation, category) in enumerate(
            zip(validation_results, enriched_categories)
        ):
            invoice_num = idx + 1
            policy_request = PolicyValidationRequest(
                category=category.suggested_category,
                amount=(
                    validation.verified_amount if validation.verified_amount else 0.0
                ),
                currency=currency,
                vendor=ocr_results[idx]["ocr_data"].vendor,
                has_receipt=True,
                invoice_age_days=15,
                company_id=request.company_id,
            )

            policy_result = await validate_policy(policy_request)
            policy_validations.append(policy_result)
            logger.info(
                f"Invoice {invoice_num} policy check",
                compliant=policy_result.compliant,
                violations=len(policy_result.violations),
            )

        logger.info("Step 7: Formatting report (template)")
        report_request = ReportFormatterRequest(
            expense_sheet_id=request.expense_sheet_id,
            expense_sheet_name=expense_name,
            employee_name=employee_name,
            single_ocr_validations=validation_results,
            total_validation=total_validation,
            categories=[c.suggested_category for c in enriched_categories],
            policy_validations=policy_validations,
        )

        report = await format_report(report_request)
        logger.info("Report formatted successfully")

        logger.info("Step 8: Returning report data (AgenticGenie will post)")

        invoice_results = []
        for idx in range(len(expense_lines)):
            invoice_results.append(
                InvoiceVerificationResult(
                    invoice_number=idx + 1,
                    invoice_id=f"INV-{idx + 1}",
                    vendor=ocr_results[idx]["ocr_data"].vendor,
                    ocr_amount=ocr_results[idx]["ocr_data"].total_amount,
                    claimed_amount=ocr_results[idx]["claimed_amount"],
                    verified_amount=validation_results[idx].verified_amount,
                    amount_matched=validation_results[idx].amount_matched,
                    risk_level=validation_results[idx].risk_level,
                    discrepancy_message=validation_results[idx].discrepancy_message,
                    category=enriched_categories[idx].suggested_category,
                    category_confidence=enriched_categories[idx].confidence,
                    policy_compliant=policy_validations[idx].compliant,
                    policy_violations=[
                        {"rule": v.rule, "message": v.message, "severity": v.severity}
                        for v in policy_validations[idx].violations
                    ],
                )
            )

        amount_mismatches = sum(1 for v in validation_results if not v.amount_matched)
        policy_violations_count = sum(1 for p in policy_validations if not p.compliant)
        high_risk_count = sum(
            1 for v in validation_results if v.risk_level in ["HIGH", "CRITICAL"]
        )

        execution_time = time.time() - start_time

        logger.info(
            "Expense verification complete (report ready for posting)",
            execution_time=f"{execution_time:.2f}s",
            amount_mismatches=amount_mismatches,
            policy_violations=policy_violations_count,
        )

        return ProcessExpenseVerificationResponse(
            success=True,
            expense_sheet_id=request.expense_sheet_id,
            employee_name=employee_name,
            expense_sheet_name=expense_name,
            total_invoices=len(expense_lines),
            execution_time_seconds=round(execution_time, 2),
            invoices=invoice_results,
            calculated_total=total_validation.calculated_total,
            employee_reported_total=total_validation.employee_reported_total,
            total_matched=total_validation.matched,
            total_discrepancy=total_validation.discrepancy_amount,
            amount_mismatches=amount_mismatches,
            policy_violations=policy_violations_count,
            high_risk_invoices=high_risk_count,
            html_report=report.html_comment,
            plain_report=report.formatted_comment,
            error=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            "Expense verification failed",
            expense_sheet_id=request.expense_sheet_id,
            error=str(e),
            execution_time=f"{execution_time:.2f}s",
        )

        return ProcessExpenseVerificationResponse(
            success=False,
            expense_sheet_id=request.expense_sheet_id,
            employee_name="Unknown",
            expense_sheet_name="Unknown",
            total_invoices=0,
            execution_time_seconds=round(execution_time, 2),
            invoices=[],
            calculated_total=0.0,
            employee_reported_total=0.0,
            total_matched=False,
            total_discrepancy=None,
            amount_mismatches=0,
            policy_violations=0,
            high_risk_invoices=0,
            html_report="",
            plain_report="",
            error=str(e),
        )


class VerificationOnlyRequest(BaseModel):
    """Request for verification without category enrichment or policy validation."""

    expense_sheet_id: int
    odoo_url: str
    odoo_db: str
    odoo_username: str
    odoo_password: str


class VerificationOnlyResponse(BaseModel):
    """Verification results without categories or policy validation."""

    success: bool
    expense_sheet_id: int
    employee_name: str
    expense_sheet_name: str
    total_invoices: int
    execution_time_seconds: float
    invoices: List[dict]
    calculated_total: float
    employee_reported_total: float
    total_matched: bool
    total_discrepancy: Optional[float]
    amount_mismatches: int
    high_risk_invoices: int
    error: Optional[str]


# -----


@router.post("/verify-expenses-only", response_model=VerificationOnlyResponse)
async def verify_expenses_only(request: VerificationOnlyRequest):
    """
    Agent 1: Verification only endpoint that performs OCR extraction and amount validation
    without category enrichment or policy validation.
    """
    start_time = time.time()
    try:
        set_correlation_id(request.expense_sheet_id)
        logger.info(
            "Starting verification-only workflow (no enrichment/policies)",
            expense_sheet_id=request.expense_sheet_id,
        )

        logger.info("Step 1: Fetching expense data from Odoo")
        fetch_request = OdooExpenseFetchRequest(
            expense_sheet_id=request.expense_sheet_id,
            odoo_url=request.odoo_url,
            odoo_db=request.odoo_db,
            odoo_username=request.odoo_username,
            odoo_password=request.odoo_password,
        )

        expense_data = await fetch_odoo_expense(fetch_request)
        expense_sheet = expense_data.get("expense_sheet", {})
        expense_lines = expense_data.get("expense_lines", [])

        employee_info = expense_sheet.get("employee_id", [None, "Unknown"])
        employee_name = (
            employee_info[1] if isinstance(employee_info, list) else "Unknown"
        )

        expense_name = expense_sheet.get("name", "Unknown")
        employee_total = expense_sheet.get("total_amount", 0.0)
        currency = "CHF"

        logger.info(
            "Expense data fetched",
            employee=employee_name,
            total_invoices=len(expense_lines),
            employee_total=employee_total,
        )

        if not expense_lines:
            raise HTTPException(
                status_code=400,
                detail=f"No expense lines found for expense sheet {request.expense_sheet_id}",
            )

        logger.info("Step 2: Extracting OCR data for all invoices")
        ocr_results = []
        for idx, line in enumerate(expense_lines):
            line_id = line.get("id")
            claimed_amount = line.get("total_amount", 0.0)
            logger.info(
                f"Processing invoice {idx + 1}/{len(expense_lines)}",
                line_id=line_id,
                claimed_amount=claimed_amount,
            )

            ocr_request = OdooOCRRequest(
                expense_line_id=line_id,
                odoo_url=request.odoo_url,
                odoo_db=request.odoo_db,
                odoo_username=request.odoo_username,
                odoo_password=request.odoo_password,
            )

            ocr_result = await odoo_ocr(ocr_request)
            ocr_results.append(
                {
                    "ocr_data": ocr_result,
                    "claimed_amount": claimed_amount,
                    "invoice_number": idx + 1,
                }
            )
        logger.info(f"OCR extraction complete for {len(ocr_results)} invoices")

        logger.info("Step 3: Validating amounts (hard-coded logic)")
        validation_results = []
        for ocr_data in ocr_results:
            invoice_num = ocr_data["invoice_number"]
            validation_request = SingleOCRValidationRequest(
                odoo_output=ocr_data["ocr_data"],
                employee_claim=ocr_data["claimed_amount"],
                invoice_id=f"INV-{invoice_num}",
                currency=currency,
            )

            validation_result = await validate_ocr(validation_request)
            validation_results.append(validation_result)
            logger.info(
                f"Invoice {invoice_num} validated",
                matched=validation_result.amount_matched,
                risk_level=validation_result.risk_level,
            )

        logger.info("Step 4: Calculating total (pure math)")
        total_request = TotalCalculationRequest(
            individual_validations=validation_results,
            employee_reported_total=employee_total,
            currency=currency,
        )

        total_validation = await calculate_total(total_request)
        logger.info(
            "Total calculation complete",
            calculated=total_validation.calculated_total,
            reported=total_validation.employee_reported_total,
            matched=total_validation.matched,
        )

        logger.info(
            "Verification complete - passing to Agent 2 for category enhancement"
        )

        invoice_results = []
        for idx in range(len(expense_lines)):
            invoice_results.append(
                {
                    "invoice_number": idx + 1,
                    "invoice_id": f"INV-{idx + 1}",
                    "vendor": ocr_results[idx]["ocr_data"].vendor,
                    "date": ocr_results[idx]["ocr_data"].date,
                    "time": ocr_results[idx]["ocr_data"].time,
                    "ocr_amount": ocr_results[idx]["ocr_data"].total_amount,
                    "claimed_amount": ocr_results[idx]["claimed_amount"],
                    "verified_amount": validation_results[idx].verified_amount,
                    "amount_matched": validation_results[idx].amount_matched,
                    "risk_level": validation_results[idx].risk_level,
                    "discrepancy_message": validation_results[idx].discrepancy_message,
                    "currency": currency,
                }
            )

        amount_mismatches = sum(1 for v in validation_results if not v.amount_matched)
        high_risk_count = sum(
            1 for v in validation_results if v.risk_level in ["HIGH", "CRITICAL"]
        )

        execution_time = time.time() - start_time

        logger.info(
            "Verification-only complete (ready for semantic enhancement)",
            execution_time=f"{execution_time:.2f}s",
            amount_mismatches=amount_mismatches,
        )

        return VerificationOnlyResponse(
            success=True,
            expense_sheet_id=request.expense_sheet_id,
            employee_name=employee_name,
            expense_sheet_name=expense_name,
            total_invoices=len(expense_lines),
            execution_time_seconds=round(execution_time, 2),
            invoices=invoice_results,
            calculated_total=total_validation.calculated_total,
            employee_reported_total=total_validation.employee_reported_total,
            total_matched=total_validation.matched,
            total_discrepancy=total_validation.discrepancy_amount,
            amount_mismatches=amount_mismatches,
            high_risk_invoices=high_risk_count,
            error=None,
        )

    except HTTPException:
        raise
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            "Verification-only failed",
            expense_sheet_id=request.expense_sheet_id,
            error=str(e),
            execution_time=f"{execution_time:.2f}s",
        )

        return VerificationOnlyResponse(
            success=False,
            expense_sheet_id=request.expense_sheet_id,
            employee_name="Unknown",
            expense_sheet_name="Unknown",
            total_invoices=0,
            execution_time_seconds=round(execution_time, 2),
            invoices=[],
            calculated_total=0.0,
            employee_reported_total=0.0,
            total_matched=False,
            total_discrepancy=None,
            amount_mismatches=0,
            high_risk_invoices=0,
            error=str(e),
        )
