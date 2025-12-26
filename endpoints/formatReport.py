from fastapi import APIRouter, HTTPException

from models.schemas import ReportFormatterRequest, ReportFormatterResponse

router = APIRouter()


@router.post("/format-report", response_model=ReportFormatterResponse)
async def format_report(request: ReportFormatterRequest):
    """Generate formatted HTML and plain text verification report."""
    try:
        lines = []
        lines.append(f"<p>")

        lines.append(
            f"<p><strong>Automated Verification Report</strong><br>Hi Manager,"
        )
        lines.append(
            f"<br>Please find below findings for expense: <strong>{request.expense_sheet_name}</strong><br>Employee: <strong>{request.employee_name}</strong></p>"
        )

        lines.append("<p><strong>OCR Verification:</strong><br>")

        if request.total_validation.matched:
            lines.append(
                "<p><strong>Total Verification:</strong> Total verified correct"
            )
        else:
            lines.append(f"<p>{request.total_validation.discrepancy_message}")

        if request.policy_validations:
            lines.append("</p>")

            lines.append("<p><strong>Policy Compliance:</strong><br>")

        issues = []

        mismatched_count = sum(
            1 for v in request.single_ocr_validations if not v.amount_matched
        )

        if mismatched_count > 0:
            issues.append(f"{mismatched_count} invoice(s) with amount mismatch")

        if not request.total_validation.matched:
            issues.append("total amount incorrect")

        if request.policy_validations:
            policy_violations = sum(
                1 for p in request.policy_validations if not p.compliant
            )

            if policy_violations > 0:
                issues.append(f"{policy_violations} invoice(s) with policy violations")

        if issues:
            lines.append(
                f"<p><strong>Overall Summary:</strong> Issues found: {', '.join(issues)}"
            )
        else:
            lines.append("<p>All invoices verified successfully, no issues found")

        html_comment = "\n".join(lines)

        plain_text = html_comment.replace("<p>", "").replace("</p>", "\n")
        plain_text = plain_text.replace("<br>", "\n")
        plain_text = plain_text.replace("<strong>", "").replace("</strong>", "")

        return ReportFormatterResponse(
            formatted_comment=plain_text, html_comment=html_comment
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Report formatting failed: {str(e)}"
        )
