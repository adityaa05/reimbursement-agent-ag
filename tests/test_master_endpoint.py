#!/usr/bin/env python3
"""Test master endpoint"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://localhost:8000"

ODOO_CONFIG = {
    "odoo_url": os.getenv("ODOO_URL"),
    "odoo_db": os.getenv("ODOO_DB"),
    "odoo_username": os.getenv("ODOO_USERNAME"),
    "odoo_password": os.getenv("ODOO_PASSWORD"),
}

TEST_EXPENSE_SHEET_ID = 393  # Use your real test ID

print("\n" + "=" * 70)
print("MASTER ENDPOINT TEST - Complete Workflow")
print("=" * 70)

print(f"\nProcessing expense sheet: {TEST_EXPENSE_SHEET_ID}")
print("This will:")
print("  1. Fetch expense from Odoo")
print("  2. Extract OCR data")
print("  3. Validate amounts")
print("  4. Calculate totals")
print("  5. Enrich categories")
print("  6. Validate policies")
print("  7. Format report")
print("  8. Post comment to Odoo")

response = requests.post(
    f"{BASE_URL}/process-expense-request",
    json={
        "expense_sheet_id": TEST_EXPENSE_SHEET_ID,
        **ODOO_CONFIG,
        "company_id": "hashgraph_inc",
    },
    timeout=120,  # Allow 2 minutes for complete workflow
)

if response.status_code == 200:
    result = response.json()

    print(f"\n{'='*70}")
    print("✅ WORKFLOW COMPLETE")
    print(f"{'='*70}")

    print(f"\nEmployee: {result['employee_name']}")
    print(f"Total Invoices: {result['total_invoices']}")
    print(f"Execution Time: {result['execution_time_seconds']:.2f}s")

    print(f"\n--- TOTALS ---")
    print(f"Calculated: {result['calculated_total']:.2f} CHF")
    print(f"Reported:   {result['employee_reported_total']:.2f} CHF")
    print(f"Match: {'✅ YES' if result['total_matched'] else '❌ NO'}")

    if result["total_discrepancy"]:
        print(f"Discrepancy: {result['total_discrepancy']:.2f} CHF")

    print(f"\n--- SUMMARY ---")
    print(f"Amount Mismatches: {result['amount_mismatches']}")
    print(f"Policy Violations: {result['policy_violations']}")
    print(f"High Risk Invoices: {result['high_risk_invoices']}")

    print(f"\n--- INVOICES ---")
    for inv in result["invoices"]:
        status = "✅" if inv["amount_matched"] else "❌"
        policy_status = "✅" if inv["policy_compliant"] else "❌"

        print(f"\nInvoice {inv['invoice_number']}: {inv['vendor']}")
        print(
            f"  Amount: {status} {inv['ocr_amount']:.2f} (claimed: {inv['claimed_amount']:.2f})"
        )
        print(f"  Risk: {inv['risk_level']}")
        print(f"  Category: {inv['category']} ({inv['category_confidence']:.0%})")
        print(f"  Policy: {policy_status} {len(inv['policy_violations'])} violation(s)")

        if inv["discrepancy_message"]:
            print(f"  ⚠️  {inv['discrepancy_message']}")

        for violation in inv["policy_violations"]:
            print(f"  ⚠️  {violation['severity']}: {violation['message']}")

    print(f"\n--- COMMENT POSTING ---")
    if result["comment_posted"]:
        print(f"✅ Comment posted successfully (ID: {result['comment_id']})")
        print(f"   Check Odoo expense sheet for verification report")
    else:
        print(f"❌ Comment posting failed")

    print(f"\n{'='*70}\n")

else:
    print(f"\n❌ ERROR: HTTP {response.status_code}")
    print(response.text)
