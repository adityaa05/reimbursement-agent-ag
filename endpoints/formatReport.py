from fastapi import APIRouter, HTTPException
from models.schemas import ReportFormatterRequest, ReportFormatterResponse

router = APIRouter()


@router.post("/format-report", response_model=ReportFormatterResponse)
async def format_report(request: ReportFormatterRequest):
    # Template-based formatting with exact message
    try:
        # Build report using hard-coded template
        lines = []
        lines.append(f"<p>Hi Manager,</p>")
        lines.append(
            f"<p>Please find below findings for expense: <strong>{request.expense_sheet_name}</strong></p>"
        )
        lines.append(f"<p>Employee: <strong>{request.employee_name}</strong></p>")
        lines.append("<br/>")

        # OCR Verification section
        lines.append("<p><strong>OCR Verification:</strong></p>")
        lines.append("<ul>")

        for idx, validation in enumerate(request.ocr_validations, 1):
            if validation.matched:
                lines.append(f"<li>Invoice {idx}:No issue found</li>")
            else:
                # Use EXACT message from validator
                lines.append(f"<li>Invoice {idx}:{validation.discrepancy_message}</li>")

        lines.append("</ul>")

        # Total validation
        lines.append("<p><strong>Total Verification:</strong></p>")
        if request.total_validation.matched:
            lines.append("<p>Total verified correct</p>")
        else:
            # Use EXACT message from calculator
            lines.append(f"<p>{request.total_validation.discrepancy_message}</p>")

        lines.append("<br/>")

        # Overall summary
        lines.append("<p><strong>Overall Summary:</strong></p>")
        issues = []

        mismatched_count = sum(1 for v in request.ocr_validations if not v.matched)
        if mismatched_count > 0:
            issues.append(f"{mismatched_count} invoice(s) with amount mismatch")

        if not request.total_validation.matched:
            issues.append("total amount incorrect")

        if issues:
            lines.append(f"<p>Issues found: {', '.join(issues)}</p>")
        else:
            lines.append("<p>All invoices verified successfully, no issues found</p>")

        html_comment = "\n".join(lines)

        # Also create plain text version
        plain_text = html_comment.replace("<p>", "").replace("</p>", "\n")
        plain_text = plain_text.replace("<ul>", "").replace("</ul>", "")
        plain_text = plain_text.replace("<li>", "- ").replace("</li>", "\n")
        plain_text = plain_text.replace("<strong>", "").replace("</strong>", "")
        plain_text = plain_text.replace("<br/>", "\n")

        return ReportFormatterResponse(
            formatted_comment=plain_text, html_comment=html_comment
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Report formatting failed: {str(e)}"
        )
