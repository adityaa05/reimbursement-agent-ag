from fastapi import APIRouter, HTTPException
from models.schemas import ReportFormatterRequest, ReportFormatterResponse


router = APIRouter()


@router.post("/format-report", response_model=ReportFormatterResponse)
async def format_report(request: ReportFormatterRequest):
    try:
        lines = []
        lines.append(f"<p><strong>Automated Verification Report</strong></p>")
        lines.append(f"<p>Hi Manager,</p>")
        lines.append(
            f"<p>Please find below findings for expense: <strong>{request.expense_sheet_name}</strong></p>"
        )
        lines.append(f"<p>Employee: <strong>{request.employee_name}</strong></p>")
        lines.append("<br/>")

        # Single OCR Verification Section
        lines.append("<p><strong>OCR Verification:</strong></p>")
        lines.append("<ul>")

        for idx, validation in enumerate(request.single_ocr_validations, 1):
            # Show amount validation status
            if validation.amount_matched:
                lines.append(f"<li>Invoice {idx}: No issue found (Match)</li>")
            else:
                lines.append(
                    f"<li>Invoice {idx}: {validation.discrepancy_message} [{validation.risk_level} RISK]</li>"
                )

        lines.append("</ul>")

        # Total validation
        lines.append("<p><strong>Total Verification:</strong></p>")
        if request.total_validation.matched:
            lines.append("<p>Total verified correct</p>")
        else:
            lines.append(f"<p>{request.total_validation.discrepancy_message}</p>")

        # Policy Compliance section
        if request.policy_validations:
            lines.append("<br/>")
            lines.append("<p><strong>Policy Compliance:</strong></p>")
            lines.append("<ul>")

            for idx, (policy, category) in enumerate(
                zip(request.policy_validations, request.categories or []), 1
            ):
                if policy.compliant:
                    lines.append(
                        f"<li><strong>Invoice {idx} [{category}]:</strong> Compliant to policy (Max: {policy.max_amount} CHF)</li>"
                    )
                else:
                    lines.append(
                        f"<li><strong>Invoice {idx} [{category}]:</strong> {len(policy.violations)} violation(s)</li>"
                    )
                    lines.append("<ul>")
                    for violation in policy.violations:
                        lines.append(
                            f"<li>{violation.severity}: {violation.message}</li>"
                        )
                    lines.append("</ul>")

            lines.append("</ul>")

        lines.append("<br/>")

        # Overall summary
        lines.append("<p><strong>Overall Summary:</strong></p>")
        issues = []

        mismatched_count = sum(
            1 for v in request.single_ocr_validations if not v.amount_matched
        )
        if mismatched_count > 0:
            issues.append(f"{mismatched_count} invoice(s) with amount mismatch")

        if not request.total_validation.matched:
            issues.append("total amount incorrect")

        # Include policy violations in summary
        if request.policy_validations:
            policy_violations = sum(
                1 for p in request.policy_validations if not p.compliant
            )
            if policy_violations > 0:
                issues.append(f"{policy_violations} invoice(s) with policy violations")

        if issues:
            lines.append(f"<p>Issues found: {', '.join(issues)}</p>")
        else:
            lines.append("<p>All invoices verified successfully, no issues found</p>")

        html_comment = "\n".join(lines)

        # Plain text version
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
