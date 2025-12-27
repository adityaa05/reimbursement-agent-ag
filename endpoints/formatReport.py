from fastapi import APIRouter, HTTPException, Body
from models.schemas import (
    ReportFormatterRequest,
    ReportFormatterResponse,
    TotalCalculationResponse,
)
from utils.logger import logger

router = APIRouter()


@router.post("/generate-report", response_model=ReportFormatterResponse)
async def generate_report(request: ReportFormatterRequest = Body(...)):
    """
    Generates a PRD-Compliant Text Report for Odoo.
    Format matches: 'Hi Manager, Please find below findings...'
    """
    try:
        logger.info(f"Generating PRD Report for Sheet {request.expense_sheet_id}")

        # --- 1. Auto-Calculate Totals (Safety Net) ---
        if not request.total_validation:
            logger.warning(
                "Agent 4 input missing 'total_validation'. Calculating internally."
            )
            calc_total = sum(
                i.verified_amount or 0.0 for i in request.single_ocr_validations
            )
            rept_total = sum(
                i.employee_reported_amount or 0.0
                for i in request.single_ocr_validations
            )

            request.total_validation = TotalCalculationResponse(
                calculated_total=round(calc_total, 2),
                employee_reported_total=round(rept_total, 2),
                matched=abs(calc_total - rept_total) < 0.05,
                discrepancy_amount=round(rept_total - calc_total, 2),
                currency="CHF",
            )
        totals = request.total_validation

        # --- 2. Build 'OCR Verification' Section ---
        ocr_lines = []
        amount_mismatch_count = 0

        for idx, invoice in enumerate(request.single_ocr_validations, 1):
            if invoice.amount_matched:
                ocr_lines.append(f"Invoice {idx}: No issue found")
            else:
                amount_mismatch_count += 1
                # Format: "Value in invoice as per AG is X, not Y as reported"
                ag_val = (
                    f"{invoice.verified_amount:.2f}"
                    if invoice.verified_amount is not None
                    else "0.00"
                )
                rep_val = f"{invoice.employee_reported_amount:.2f}"
                ocr_lines.append(
                    f"Invoice {idx}: Value in invoice as per AG is {ag_val}, not {rep_val} as reported"
                )

        # Total Line
        if totals.matched:
            total_line = f"Total: Matches reported amount ({totals.currency} {totals.calculated_total:.2f})"
        else:
            diff = abs(totals.discrepancy_amount or 0.0)
            total_line = f"Total: Total is incorrect by {diff:.2f} {totals.currency}, should be {totals.calculated_total:.2f} {totals.currency}"

        # --- 3. Build 'Policy Report' Section ---
        policy_lines = []
        policy_violation_count = 0

        # Ensure policy list matches invoice list size
        policies = request.policy_validations or []

        # Iterate through invoices (using index) to match PRD format "Invoice 1...", "Invoice 2..."
        for idx in range(1, len(request.single_ocr_validations) + 1):
            # Check if we have a corresponding policy result
            if idx <= len(policies):
                res = policies[idx - 1]
                if res.compliant:
                    policy_lines.append(f"Invoice {idx}: Compliant to policy")
                else:
                    policy_violation_count += 1
                    # Combine all violation messages for this invoice
                    reasons = "; ".join([v.message for v in res.violations])
                    policy_lines.append(f"Invoice {idx}: {reasons}")
            else:
                policy_lines.append(f"Invoice {idx}: No policy check performed")

        # --- 4. Build 'Overall Summary' ---
        summary_parts = []
        if amount_mismatch_count > 0:
            summary_parts.append(
                f"{amount_mismatch_count} invoice(s) have amount mismatch"
            )

        if policy_violation_count > 0:
            summary_parts.append(
                f"{policy_violation_count} invoice(s) have policy violations"
            )

        if not summary_parts:
            summary_text = "All invoices verified and compliant."
        else:
            summary_text = " while ".join(summary_parts) + "."

        # --- 5. Assemble Final Report String ---
        final_report = (
            f"Hi Manager,\n"
            f"Please find below findings\n\n"
            f"OCR Verification:\n"
            f"{chr(10).join(ocr_lines)}\n"  # chr(10) is newline
            f"{total_line}\n\n"
            f"Policy Report:\n"
            f"{chr(10).join(policy_lines)}\n\n"
            f"Overall Summary: {summary_text.capitalize()}"
        )

        return ReportFormatterResponse(
            formatted_comment=final_report,
            html_comment=final_report,  # Send as text so Odoo renders newlines correctly
        )

    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        return ReportFormatterResponse(
            formatted_comment="Error", html_comment=f"Error generating report: {str(e)}"
        )
