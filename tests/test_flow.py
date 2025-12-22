"""
Minimal Output Workflow Test
Shows only essential validation results for manual verification
"""

import requests
import json
import os
import time
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

# Validate credentials
if not all(ODOO_CONFIG.values()):
    print("ERROR: Missing Odoo credentials in .env file")
    exit(1)


def call_endpoint(endpoint, payload):
    """Make HTTP POST request - no output"""
    try:
        response = requests.post(f"{BASE_URL}{endpoint}", json=payload, timeout=60)
        response.raise_for_status()
        return True, response.json()
    except Exception as e:
        return False, str(e)


print("\n" + "=" * 80)
print("EXPENSE VERIFICATION TEST - MINIMAL OUTPUT")
print("=" * 80)

# STEP 1: Fetch expense data
print("\n[1/9] Fetching expense sheet from Odoo...")
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

print(f"OK - Found {len(expense_lines)} invoices for {employee_name}")
print(f"     Expense: {expense_name}")

# STEP 2 & 3: Dual OCR Processing
print("\n[2/9] Running Dual OCR (Textract + Odoo)...")
textract_results = []
odoo_results = []

for idx, line in enumerate(expense_lines, 1):
    attachments = line.get("attachments", [])
    if not attachments:
        print(f"     Invoice {idx}: No attachment - SKIPPED")
        textract_results.append(None)
        odoo_results.append(None)
        continue

    # Textract OCR
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

    # Odoo OCR
    success, odoo_result = call_endpoint(
        "/odoo-ocr", {"expense_line_id": line.get("id"), **ODOO_CONFIG}
    )
    odoo_results.append(odoo_result if success else None)

print(
    f"OK - Processed {len([r for r in textract_results if r])} Textract, {len([r for r in odoo_results if r])} Odoo"
)

# STEP 4: Validate OCR Consensus
print("\n[3/9] Validating OCR consensus...")
validation_results = []

print("\n" + "=" * 80)
print("DUAL OCR VALIDATION RESULTS")
print("=" * 80)
print(
    f"{'Invoice':<10} {'Textract':<12} {'Odoo':<12} {'Claimed':<12} {'Consensus':<12} {'Match':<8} {'Risk':<10}"
)
print("-" * 80)

for idx in range(len(expense_lines)):
    if not textract_results[idx] or not odoo_results[idx]:
        validation_results.append(None)
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
        textract_amt = (
            f"{v['textract_amount']:.2f}" if v["textract_amount"] else "FAILED"
        )
        odoo_amt = f"{v['odoo_amount']:.2f}" if v["odoo_amount"] else "FAILED"
        claimed_amt = f"{v['employee_reported_amount']:.2f}"
        consensus = "YES" if v["ocr_consensus"] else "NO"
        match = "YES" if v["amount_matched"] else "NO"
        risk = v["risk_level"]

        print(
            f"INV-{idx+1:<6} {textract_amt:<12} {odoo_amt:<12} {claimed_amt:<12} {consensus:<12} {match:<8} {risk:<10}"
        )

        if not v["amount_matched"]:
            print(f"         >>> ALERT: {v['discrepancy_message']}")

        validation_results.append(result)

# STEP 5: Calculate Total
print("\n[4/9] Calculating total amount...")
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
print("TOTAL AMOUNT VALIDATION")
print("=" * 80)
if success:
    print(f"Calculated Total:        {total_calc['calculated_total']:.2f} CHF")
    print(f"Employee Reported Total: {total_calc['employee_reported_total']:.2f} CHF")
    print(f"Match:                   {'YES' if total_calc['matched'] else 'NO'}")
    if not total_calc["matched"]:
        print(f"\n>>> ALERT: {total_calc['discrepancy_message']}")

# STEP 6: Enrich Categories
print("\n[5/9] Enriching categories...")
enriched_categories = []

print("\n" + "=" * 80)
print("CATEGORY ENRICHMENT RESULTS")
print("=" * 80)
print(
    f"{'Invoice':<10} {'Vendor':<25} {'Existing Category':<25} {'Suggested':<20} {'Confidence':<12}"
)
print("-" * 80)

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
        vendor = textract_result.get("vendor", "Unknown")[:24]
        existing = (existing_category or "None")[:24]
        suggested = result["suggested_category"]
        confidence = f"{result['confidence']:.2f}"

        print(
            f"INV-{idx+1:<6} {vendor:<25} {existing:<25} {suggested:<20} {confidence:<12}"
        )
        enriched_categories.append(suggested)
    else:
        enriched_categories.append("Other")

# STEP 7: Fetch Policies (minimal output)
print("\n[6/9] Fetching company policies...")
success, policies = call_endpoint("/fetch-policies", {"company_id": COMPANY_ID})
if success:
    print(f"OK - Loaded {len(policies['categories'])} policy categories")

# STEP 8: Validate Policies
print("\n[7/9] Validating policy compliance...")
policy_validations = []

print("\n" + "=" * 80)
print("POLICY COMPLIANCE VALIDATION")
print("=" * 80)
print(
    f"{'Invoice':<10} {'Category':<20} {'Amount':<12} {'Max Limit':<12} {'Compliant':<12}"
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
        amount = f"{validation.get('verified_amount', 0):.2f}"
        max_limit = f"{result['max_amount']:.2f}" if result["max_amount"] else "N/A"
        compliant = "YES" if result["compliant"] else "NO"

        print(
            f"INV-{idx+1:<6} {category:<20} {amount:<12} {max_limit:<12} {compliant:<12}"
        )

        if not result["compliant"] and result["violations"]:
            for violation in result["violations"]:
                print(f"         >>> {violation['severity']}: {violation['message']}")

        policy_validations.append(result)

# STEP 9: Format Report (minimal output)
print("\n[8/9] Formatting report...")
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
if success:
    print("OK - Report generated")

# STEP 10: Post to Odoo
print("\n[9/9] Posting comment to Odoo...")
if report_data:
    success, result = call_endpoint(
        "/post-odoo-comment",
        {
            "expense_sheet_id": TEST_EXPENSE_SHEET_ID,
            "comment_html": report_data.get("html_comment", ""),
            **ODOO_CONFIG,
        },
    )
    if success:
        print("OK - Comment posted to Odoo chatter")

# SUMMARY
print("\n" + "=" * 80)
print("TEST COMPLETE - SUMMARY")
print("=" * 80)

valid_validations = [v for v in validation_results if v]
ocr_disagreements = sum(1 for v in valid_validations if not v["ocr_consensus"])
amount_mismatches = sum(1 for v in valid_validations if not v["amount_matched"])
policy_violations = sum(1 for p in policy_validations if not p["compliant"])

print(f"Total Invoices:        {len(expense_lines)}")
print(f"Successfully Processed: {len(valid_validations)}")
print(f"OCR Disagreements:     {ocr_disagreements}")
print(f"Amount Mismatches:     {amount_mismatches}")
print(f"Total Match:           {'YES' if total_calc['matched'] else 'NO'}")
print(f"Policy Violations:     {policy_violations}")

print("\n" + "=" * 80)
print("MANUAL VERIFICATION CHECKLIST:")
print("=" * 80)
print("[ ] Check invoices with 'NO' consensus - verify which OCR is correct")
print("[ ] Check invoices with 'NO' match - verify actual invoice amounts")
print("[ ] Check total calculation matches your manual sum")
print("[ ] Check category enrichment makes sense for vendors")
print("[ ] Check Odoo chatter for posted report")
print("=" * 80 + "\n")
