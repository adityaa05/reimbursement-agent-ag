"""
Minimal Output Workflow Test - Focus on Verification Results
Only shows essential data needed for manual verification against Odoo
"""

import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
BASE_URL = "http://localhost:8000"
ODOO_CONFIG = {
    "odoo_url": os.getenv("ODOO_URL"),
    "odoo_db": os.getenv("ODOO_DB"),
    "odoo_username": os.getenv("ODOO_USERNAME"),
    "odoo_password": os.getenv("ODOO_PASSWORD"),
}
TEST_EXPENSE_SHEET_ID = 542
COMPANY_ID = "hashgraph_inc"

if not all(ODOO_CONFIG.values()):
    print("ERROR: Missing Odoo credentials in .env file")
    exit(1)


def call_endpoint(endpoint, payload):
    """Make HTTP POST request - silent operation"""
    try:
        response = requests.post(f"{BASE_URL}{endpoint}", json=payload, timeout=60)
        response.raise_for_status()
        return True, response.json()
    except Exception as e:
        return False, str(e)


print("\n" + "=" * 80)
print("EXPENSE VERIFICATION TEST")
print("=" * 80)

# STEP 1: Fetch expense data
print("\nFetching expense sheet from Odoo...")
success, expense_data = call_endpoint(
    "/fetch-odoo-expense", {"expense_sheet_id": TEST_EXPENSE_SHEET_ID, **ODOO_CONFIG}
)

if not success:
    print(f"FAILED: {expense_data}")
    exit(1)

employee_info = expense_data.get("expense_sheet", {}).get(
    "employee_id", [None, "Unknown"]
)
employee_name = employee_info[1] if isinstance(employee_info, list) else "Unknown"
expense_name = expense_data.get("expense_sheet", {}).get("name", "Unknown")
expense_lines = expense_data.get("expense_lines", [])

print(f"Employee: {employee_name}")
print(f"Expense Sheet: {expense_name}")
print(f"Total Invoices: {len(expense_lines)}")

# STEP 2 & 3: Dual OCR Processing (Silent)
print("\nRunning OCR extraction...")
textract_results = []
odoo_results = []

for idx, line in enumerate(expense_lines, 1):
    attachments = line.get("attachments", [])
    if not attachments:
        textract_results.append(None)
        odoo_results.append(None)
        continue

    attachment = attachments[0]
    success, textract_result = call_endpoint(
        "/textract-ocr",
        {
            "image_base64": attachment.get("datas", ""),
            "invoice_id": f"INV-{idx}",
            "filename": attachment.get("name", f"invoice_{idx}.pdf"),
        },
    )
    textract_results.append(textract_result if success else None)

    success, odoo_result = call_endpoint(
        "/odoo-ocr", {"expense_line_id": line.get("id"), **ODOO_CONFIG}
    )
    odoo_results.append(odoo_result if success else None)

# STEP 4: Validate OCR
print("Validating amounts...")
validation_results = []

print("\n" + "=" * 80)
print("AMOUNT VERIFICATION RESULTS")
print("=" * 80)
print(
    f"{'#':<4} {'Textract':<12} {'Odoo':<12} {'Claimed':<12} {'Currency':<10} {'Status':<15} {'Issue'}"
)
print("-" * 80)

for idx in range(len(expense_lines)):
    if not textract_results[idx] or not odoo_results[idx]:
        validation_results.append(None)
        print(
            f"{idx+1:<4} {'N/A':<12} {'N/A':<12} {'N/A':<12} {'N/A':<10} {'SKIPPED':<15} No attachment"
        )
        continue

    success, result = call_endpoint(
        "/validate-ocr",
        {
            "textract_output": textract_results[idx],
            "odoo_output": odoo_results[idx],
            "employee_claim": expense_lines[idx].get("total_amount", 0),
            "invoice_id": f"INV-{idx+1}",
            "currency": "CHF",
        },
    )

    if success:
        v = result
        t_amt = f"{v['textract_amount']:.2f}" if v["textract_amount"] else "FAIL"
        o_amt = f"{v['odoo_amount']:.2f}" if v["odoo_amount"] else "FAIL"
        c_amt = f"{v['employee_reported_amount']:.2f}"
        curr = v.get("currency", "CHF")

        status = "OK"
        issue = ""

        if not v["ocr_consensus"]:
            status = "OCR MISMATCH"
            issue = f"Textract={t_amt}, Odoo={o_amt}"

        if not v["amount_matched"]:
            status = "AMOUNT WRONG"
            issue = f"Verified={v['verified_amount']:.2f}, Claimed={c_amt}"

        print(
            f"{idx+1:<4} {t_amt:<12} {o_amt:<12} {c_amt:<12} {curr:<10} {status:<15} {issue}"
        )
        validation_results.append(result)

# STEP 5: Calculate Total
print("\nCalculating total...")
employee_total = expense_data.get("expense_sheet", {}).get("total_amount", 0)

success, total_calc = call_endpoint(
    "/calculate-total",
    {
        "individual_validations": [v for v in validation_results if v],
        "employee_reported_total": employee_total,
        "currency": "CHF",
    },
)

print("\n" + "=" * 80)
print("TOTAL VERIFICATION")
print("=" * 80)
print(f"System Calculated: {total_calc['calculated_total']:.2f} CHF")
print(f"Employee Claimed:  {total_calc['employee_reported_total']:.2f} CHF")
print(f"Match: {'YES' if total_calc['matched'] else 'NO'}")
if not total_calc["matched"]:
    print(f"Discrepancy: {total_calc['discrepancy_amount']:.2f} CHF")

# STEP 6: Enrich Categories (Silent)
print("\nEnriching categories...")
enriched_categories = []

for idx, textract_result in enumerate(textract_results):
    if not textract_result:
        enriched_categories.append("Other")
        continue

    product_info = expense_lines[idx].get("product_id", [None, None])
    existing_category = (
        product_info[1]
        if isinstance(product_info, list) and len(product_info) > 1
        else None
    )

    success, result = call_endpoint(
        "/enrich-category",
        {
            "vendor": textract_result.get("vendor"),
            "date": textract_result.get("date"),
            "time": textract_result.get("time"),
            "existing_category": existing_category,
            "invoice_id": f"INV-{idx+1}",
            "company_id": COMPANY_ID,
        },
    )

    if success:
        enriched_categories.append(result["suggested_category"])
    else:
        enriched_categories.append("Other")

# STEP 7: Fetch Policies (Silent)
print("Fetching policies...")
success, policies = call_endpoint("/fetch-policies", {"company_id": COMPANY_ID})

# STEP 8: Validate Policies
print("Validating policy compliance...")
policy_validations = []

print("\n" + "=" * 80)
print("POLICY COMPLIANCE")
print("=" * 80)
print(
    f"{'#':<4} {'Category':<20} {'Amount':<12} {'Limit':<12} {'Status':<15} {'Violation'}"
)
print("-" * 80)

for idx, category in enumerate(enriched_categories):
    if idx >= len(validation_results) or not validation_results[idx]:
        continue

    validation = validation_results[idx]

    success, result = call_endpoint(
        "/validate-policy",
        {
            "category": category,
            "amount": validation.get("verified_amount", 0),
            "currency": "CHF",
            "vendor": None,
            "has_receipt": True,
            "has_attendees": None,
            "invoice_age_days": 15,
            "company_id": COMPANY_ID,
        },
    )

    if success:
        amt = f"{validation.get('verified_amount', 0):.2f}"
        limit = f"{result['max_amount']:.2f}" if result["max_amount"] else "N/A"
        status = "COMPLIANT" if result["compliant"] else "VIOLATED"
        violation = ""

        if not result["compliant"] and result["violations"]:
            violation = result["violations"][0]["message"][:50]

        print(
            f"{idx+1:<4} {category:<20} {amt:<12} {limit:<12} {status:<15} {violation}"
        )
        policy_validations.append(result)

# STEP 9: Format Report (Silent)
print("\nGenerating report...")
success, report_data = call_endpoint(
    "/format-report",
    {
        "expense_sheet_id": TEST_EXPENSE_SHEET_ID,
        "expense_sheet_name": expense_name,
        "employee_name": employee_name,
        "dual_ocr_validations": [v for v in validation_results if v],
        "total_validation": total_calc,
        "categories": enriched_categories,
        "policy_validations": policy_validations,
    },
)

# STEP 10: Post to Odoo (Silent)
print("Posting to Odoo...")
if report_data:
    success, result = call_endpoint(
        "/post-odoo-comment",
        {
            "expense_sheet_id": TEST_EXPENSE_SHEET_ID,
            "comment_html": report_data.get("html_comment", ""),
            **ODOO_CONFIG,
        },
    )

# SUMMARY
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

valid_validations = [v for v in validation_results if v]
ocr_disagreements = sum(1 for v in valid_validations if not v["ocr_consensus"])
amount_mismatches = sum(1 for v in valid_validations if not v["amount_matched"])
policy_violations = sum(1 for p in policy_validations if not p["compliant"])

print(f"Total Invoices Processed: {len(valid_validations)}")
print(f"OCR Disagreements: {ocr_disagreements}")
print(f"Amount Mismatches: {amount_mismatches}")
print(f"Total Calculation: {'CORRECT' if total_calc['matched'] else 'INCORRECT'}")
print(f"Policy Violations: {policy_violations}")

print("\n" + "=" * 80)
print("NEXT STEPS:")
print("=" * 80)
print("1. Open Odoo expense sheet in browser")
print("2. Compare amounts above with invoice attachments")
print("3. Verify categories make sense")
print("4. Check Odoo chatter for posted report")
print("=" * 80 + "\n")
