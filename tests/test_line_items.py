#!/usr/bin/env python3
"""Test Odoo OCR line item extraction"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

ODOO_CONFIG = {
    "odoo_url": os.getenv("ODOO_URL"),
    "odoo_db": os.getenv("ODOO_DB"),
    "odoo_username": os.getenv("ODOO_USERNAME"),
    "odoo_password": os.getenv("ODOO_PASSWORD"),
}

# Test with a known expense line that has multiple items
TEST_EXPENSE_LINE_ID = 1211  # Replace with real ID from your system

response = requests.post(
    "http://localhost:8000/odoo-ocr",
    json={"expense_line_id": TEST_EXPENSE_LINE_ID, **ODOO_CONFIG},
)

result = response.json()

print("\n" + "=" * 60)
print("ODOO OCR LINE ITEM EXTRACTION TEST")
print("=" * 60)

print(f"\nVendor: {result.get('vendor')}")
print(f"Date: {result.get('date')}")
print(f"Total: {result.get('total_amount')} {result.get('currency')}")

line_items = result.get("line_items", [])
print(f"\nLine Items: {len(line_items)}")

if line_items:
    print("\n" + "-" * 60)
    for idx, item in enumerate(line_items, 1):
        print(f"{idx}. {item['description']}")
        print(f"   Quantity: {item['quantity']}")
        print(f"   Unit Price: {item['unit_price']}")
        print(f"   Total: {item['total']}")
        print("-" * 60)
else:
    print("\n⚠️  NO LINE ITEMS EXTRACTED")
    print("Check Odoo API response structure")
