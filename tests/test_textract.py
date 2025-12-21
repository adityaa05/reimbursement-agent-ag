import boto3
import os
from dotenv import load_dotenv
import json

load_dotenv()

textract = boto3.client(
    "textract",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)


def extract_invoice_data(image_path):
    print(f"Analyzing invoice: {image_path}")

    # Read image file
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()

    # Call Textract with TABLES and FORMS analysis
    response = textract.analyze_expense(Document={"Bytes": image_bytes})

    print("\nTextract Response:")
    print(json.dumps(response, indent=2, default=str))

    # Extract expense documents (invoices)
    expense_docs = response.get("ExpenseDocuments", [])

    if not expense_docs:
        print("No expense data found")
        return None

    # Parse first document
    doc = expense_docs[0]
    summary_fields = doc.get("SummaryFields", [])

    # Extract key fields
    extracted_data = {
        "vendor": None,
        "date": None,
        "time": None,
        "total_amount": None,
        "currency": None,
        "line_items": [],
    }

    total_candidates = []

    # Parse summary fields
    for field in summary_fields:
        field_type = field.get("Type", {}).get("Text", "")
        field_value = field.get("ValueDetection", {}).get("Text", "")

        # 🔍 Also check the label text for currency hints
        label_text = field.get("LabelDetection", {}).get("Text", "")

        if field_type in ["VENDOR_NAME", "RECEIVER_NAME"]:
            extracted_data["vendor"] = field_value
        elif field_type == "INVOICE_RECEIPT_DATE":
            extracted_data["date"] = field_value
        elif field_type == "TOTAL":
            total_candidates.append(
                {
                    "value": field_value,
                    "label": label_text,
                    "amount": parse_amount(field_value),
                }
            )
        elif field_type == "CURRENCY":
            extracted_data["currency"] = field_value

    chf_total = None
    eur_total = None
    fallback_total = None

    for candidate in total_candidates:
        label_upper = candidate["label"].upper() if candidate["label"] else ""
        value_upper = candidate["value"].upper() if candidate["value"] else ""

        # Check if CHF is mentioned in label or value
        if "CHF" in label_upper or "CHF" in value_upper:
            chf_total = candidate["amount"]
            print(
                f"Found CHF total: {chf_total} (from '{candidate['label']}': '{candidate['value']}')"
            )
        elif "EUR" in label_upper or "EUR" in value_upper:
            eur_total = candidate["amount"]
            print(
                f"Found EUR total: {eur_total} (from '{candidate['label']}': '{candidate['value']}')"
            )
        else:
            # Store as fallback if no currency marker
            if fallback_total is None:
                fallback_total = candidate["amount"]

    # Prioritize: CHF > fallback > EUR
    if chf_total is not None:
        extracted_data["total_amount"] = chf_total
        extracted_data["currency"] = "CHF"
    elif fallback_total is not None:
        extracted_data["total_amount"] = fallback_total
        extracted_data["currency"] = (
            extracted_data["currency"] or "CHF"
        )  # Default to CHF
    elif eur_total is not None:
        extracted_data["total_amount"] = eur_total
        extracted_data["currency"] = "EUR"

    # Parse line items
    line_items_groups = doc.get("LineItemGroups", [])
    for group in line_items_groups:
        for item in group.get("LineItems", []):
            line_item = {}
            for field in item.get("LineItemExpenseFields", []):
                field_type = field.get("Type", {}).get("Text", "")
                field_value = field.get("ValueDetection", {}).get("Text", "")

                if field_type == "ITEM":
                    line_item["description"] = field_value
                elif field_type == "PRICE":
                    line_item["amount"] = parse_amount(field_value)

            if line_item:
                extracted_data["line_items"].append(line_item)

    print("\nExtracted Data:")
    print(json.dumps(extracted_data, indent=2))

    return extracted_data


def parse_amount(amount_str):

    if not amount_str:
        return None

    cleaned = amount_str.replace("CHF", "").replace("$", "").replace("€", "").strip()

    try:
        return float(cleaned)
    except:
        return None


if __name__ == "__main__":
    invoice_path = "downloads/signal-2025-09-25-160356.jpeg"

    if os.path.exists(invoice_path):
        result = extract_invoice_data(invoice_path)

        if result:
            print(f"Vendor: {result['vendor']}")
            print(f"Date: {result['date']}")
            print(f"Textract Amount: {result['total_amount']} {result['currency']}")
            print(f"Odoo Claimed Amount: 137.5 CHF")

            # comparison
            if result["total_amount"]:
                if abs(result["total_amount"] - 137.5) < 0.01:
                    print("\nAmount MATCHES - No discrepancy")
                else:
                    print(f"\nAmount MISMATCH!")
                    print(f"   Textract found: {result['total_amount']}")
                    print(f"   Employee claimed: 137.5")
                    print(f"   Discrepancy: {abs(result['total_amount'] - 137.5):.2f}")
    else:
        print(f"Invoice not found: {invoice_path}")
        print("Please run odoo_connection_test.py first to download invoice")
