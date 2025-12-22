import requests
import base64
import json

# Your downloaded invoice
invoice_path = "downloads/signal-2025-09-25-160356.jpeg"

# Read and encode image
with open(invoice_path, "rb") as f:
    image_bytes = f.read()
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

# Step 1: Call Textract OCR
print("Step 1: Extracting invoice data with Textract...")
ocr_response = requests.post(
    "http://localhost:8000/textract-ocr",
    json={
        "image_base64": image_base64,
        "invoice_id": "INV-1324",
        "filename": "signal-2025-09-25-160356.jpeg",
    },
)

ocr_data = ocr_response.json()
print(json.dumps(ocr_data, indent=2))

# Step 2: Validate against Odoo claimed amount
print("\nStep 2: Validating against claimed amount...")
validation_response = requests.post(
    "http://localhost:8000/validate-ocr",
    json={
        "textract_amount": ocr_data["total_amount"],
        "odoo_claimed_amount": 137.5,  # From Odoo
        "invoice_id": "INV-1324",
        "currency": "CHF",
    },
)

validation_data = validation_response.json()
print(json.dumps(validation_data, indent=None))


if validation_data["matched"]:
    print("RESULT: Invoice amount matches claimed amount")
else:
    print("RESULT: Discrepancy detected!")
    print(f"   {validation_data['discrepancy_message']}")
