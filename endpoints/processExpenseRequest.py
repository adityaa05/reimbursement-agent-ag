import time
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

from utils.logger import logger, set_correlation_id
from endpoints.fetchOdooExpense import fetch_odoo_expense
from endpoints.odooOCR import odoo_ocr
from endpoints.OCRValidator import validate_ocr
from endpoints.calculateTotal import calculate_total
from models.schemas import (
    OdooExpenseFetchRequest,
    OdooOCRRequest,
    SingleOCRValidationRequest,
    TotalCalculationRequest,
)

router = APIRouter()


class InvoiceVerificationResult(BaseModel):
    invoice_number: int
    invoice_id: str
    vendor: Optional[str] = None
    ocr_amount: Optional[float] = None
    claimed_amount: float
    verified_amount: Optional[float] = None
    amount_matched: bool
    risk_level: str
    discrepancy_message: Optional[str] = None
    category: str = "Unknown"
    category_confidence: float = 0.0
    policy_compliant: bool = True
    policy_violations: List[Dict[str, Any]] = []
    currency: str = "CHF"  # <--- ADDED FIELD


class VerificationOnlyResponse(BaseModel):
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
    high_risk_invoices: int
    error: Optional[str] = None


@router.post("/verify-expenses-only", response_model=VerificationOnlyResponse)
async def verify_expenses_only(
    expense_sheet_id: int = Body(..., description="ID of the expense sheet"),
    odoo_url: str = Body(..., description="Odoo URL"),
    odoo_db: str = Body(..., description="Odoo Database Name"),
    odoo_username: str = Body(..., description="Odoo Username"),
    odoo_password: str = Body(..., description="Odoo Password"),
    company_id: str = Body("hashgraph_inc", description="Company ID"),
):
    """
    Agent 1 Tool: Verifies expenses (OCR + Math).
    Includes defensive coding to prevent crashes on missing Odoo fields.
    """
    start_time = time.time()
    set_correlation_id(f"verify_only_{expense_sheet_id}")

    try:
        logger.info(f"Starting verification-only workflow for Sheet {expense_sheet_id}")

        # 1. Fetch from Odoo
        fetch_request = {
            "expense_sheet_id": expense_sheet_id,
            "odoo_url": odoo_url,
            "odoo_db": odoo_db,
            "odoo_username": odoo_username,
            "odoo_password": odoo_password,
        }

        expense_data = await fetch_odoo_expense(
            OdooExpenseFetchRequest(**fetch_request)
        )

        sheet_info = expense_data.get("expense_sheet", {})
        expense_lines = expense_data.get("expense_lines", [])

        employee_data = sheet_info.get("employee_id", [])
        employee_name = (
            employee_data[1]
            if isinstance(employee_data, list) and len(employee_data) > 1
            else "Unknown"
        )
        expense_name = sheet_info.get("name", "Unknown")

        if not expense_lines:
            logger.warning(f"No expense lines found for Sheet {expense_sheet_id}")
            raise HTTPException(status_code=404, detail="No expense lines found")

        logger.info(
            f"Fetched {len(expense_lines)} lines. Starting Invoice Processing..."
        )

        # 2. Run OCR & Math Validation (Loop)
        invoice_results = []
        ocr_validations_for_total = []
        amount_mismatches = 0
        high_risk_count = 0

        for idx, line in enumerate(expense_lines):
            line_id = line.get("id", "Unknown")
            try:
                # OCR Request
                ocr_req = OdooOCRRequest(
                    expense_line_id=line_id,
                    odoo_url=odoo_url,
                    odoo_db=odoo_db,
                    odoo_username=odoo_username,
                    odoo_password=odoo_password,
                )
                ocr_result = await odoo_ocr(ocr_req)

                # Safe Amount Extraction: Use total_amount as fallback
                claimed_amount = line.get("total_amount", 0.0)

                curr_raw = line.get("currency_id")
                currency_code = (
                    curr_raw[1]
                    if isinstance(curr_raw, list) and len(curr_raw) > 1
                    else "CHF"
                )

                # Validation Request
                val_req = SingleOCRValidationRequest(
                    odoo_output=ocr_result,
                    employee_claim=claimed_amount,
                    invoice_id=str(line_id),
                    currency=currency_code,
                )
                val_result = await validate_ocr(val_req)

                ocr_validations_for_total.append(val_result)

                if not val_result.amount_matched:
                    amount_mismatches += 1
                if val_result.risk_level == "HIGH":
                    high_risk_count += 1

                invoice_results.append(
                    InvoiceVerificationResult(
                        invoice_number=idx + 1,
                        invoice_id=str(line_id),
                        vendor=val_result.odoo_amount
                        and ocr_result.vendor
                        or line.get("name"),
                        ocr_amount=val_result.verified_amount,
                        claimed_amount=claimed_amount,
                        verified_amount=val_result.verified_amount,
                        amount_matched=val_result.amount_matched,
                        risk_level=val_result.risk_level,
                        discrepancy_message=val_result.discrepancy_message,
                        category="Unknown",
                        category_confidence=0.0,
                        policy_compliant=True,
                        policy_violations=[],
                        currency=currency_code,  # <--- ASSIGN CURRENCY
                    )
                )

            except Exception as e:
                logger.error(f"Failed to process line {line_id}: {str(e)}")
                invoice_results.append(
                    InvoiceVerificationResult(
                        invoice_number=idx + 1,
                        invoice_id=str(line_id),
                        vendor="Processing Error",
                        claimed_amount=line.get("total_amount", 0.0),
                        amount_matched=False,
                        risk_level="HIGH",
                        discrepancy_message=f"System Error: {str(e)}",
                        currency="CHF",  # Default currency on error
                    )
                )

        logger.info("Invoice Processing Complete. Calculating Totals...")

        # 3. Calculate Total
        try:
            safe_total = sum(l.get("total_amount", 0.0) for l in expense_lines)

            total_req = TotalCalculationRequest(
                individual_validations=ocr_validations_for_total,
                employee_reported_total=safe_total,
                currency="CHF",
            )
            total_validation = await calculate_total(total_req)
        except Exception as e:
            logger.error(f"Total Calculation Failed: {str(e)}")

            class FallbackTotal:
                calculated_total = 0.0
                employee_reported_total = 0.0
                matched = False
                discrepancy_amount = 0.0

            total_validation = FallbackTotal()

        execution_time = time.time() - start_time

        return VerificationOnlyResponse(
            success=True,
            expense_sheet_id=expense_sheet_id,
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

    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(f"Critical Verification Failure: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Verification Failed: {str(e)}")
