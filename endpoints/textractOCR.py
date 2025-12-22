from fastapi import APIRouter, HTTPException
import base64
from config import textract_client
from models.schemas import OCRRequest, OCRResponse
from utils.parsers import parse_amount

router = APIRouter()


@router.post("/textract-ocr", response_model=OCRResponse)
async def textract_ocr(request: OCRRequest):
    try:
        # Decode base64 image
        image_bytes = base64.b64decode(request.image_base64)

        # Call Textract
        response = textract_client.analyze_expense(Document={"Bytes": image_bytes})

        # Parse response
        expense_docs = response.get("ExpenseDocuments", [])
        if not expense_docs:
            raise HTTPException(
                status_code=400, detail="No expense data found in image"
            )

        doc = expense_docs[0]
        summary_fields = doc.get("SummaryFields", [])

        extracted_data = {
            "invoice_id": request.invoice_id,
            "vendor": None,
            "date": None,
            "time": None,
            "total_amount": None,
            "currency": "CHF",
            "line_items": [],
        }

        total_candidates = []

        # Extract fields
        for field in summary_fields:
            field_type = field.get("Type", {}).get("Text", "")
            field_value = field.get("ValueDetection", {}).get("Text", "")
            label_text = field.get("LabelDetection", {}).get("Text", "")
            confidence = field.get("ValueDetection", {}).get("Confidence", 0)

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

        chf_total = None
        eur_total = None
        fallback_total = None

        for candidate in total_candidates:
            label_upper = (candidate["label"] or "").upper()
            value_upper = (candidate["value"] or "").upper()

            if "CHF" in label_upper or "CHF" in value_upper:
                chf_total = candidate["amount"]
            elif "EUR" in label_upper or "EUR" in value_upper:
                eur_total = candidate["amount"]
            else:
                if fallback_total is None:
                    fallback_total = candidate["amount"]

        # Prioritize: CHF > fallback > EUR
        if chf_total is not None:
            extracted_data["total_amount"] = chf_total
            extracted_data["currency"] = "CHF"
        elif fallback_total is not None:
            extracted_data["total_amount"] = fallback_total
            extracted_data["currency"] = "CHF"
        elif eur_total is not None:
            extracted_data["total_amount"] = eur_total
            extracted_data["currency"] = "EUR"

        # Extract line items
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

        return OCRResponse(**extracted_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Textract OCR failed: {str(e)}")
