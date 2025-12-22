from fastapi import APIRouter, HTTPException
import base64
from collections import Counter
from config import textract_client
from models.schemas import OCRRequest, OCRResponse
from utils.parsers import parse_amount
from utils.textract_scorer import (
    build_candidate_from_field,
    filter_candidates,
    select_best_candidate,
)
from utils.currency_validator import is_reasonable_expense_amount

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
            # Return None instead of failing - let Odoo OCR handle it
            return OCRResponse(
                invoice_id=request.invoice_id,
                vendor=None,
                date=None,
                time=None,
                total_amount=None,
                currency="CHF",  # Default
                line_items=[],
            )

        doc = expense_docs[0]
        summary_fields = doc.get("SummaryFields", [])

        extracted_data = {
            "invoice_id": request.invoice_id,
            "vendor": None,
            "date": None,
            "time": None,
            "total_amount": None,
            "currency": "CHF",  # Will be overridden
            "line_items": [],
        }

        total_candidates = []
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
                parsed_amount = parse_amount(field_value)

                # Build candidate with currency detection
                candidate = build_candidate_from_field(
                    field_value=field_value,
                    label_text=label_text,
                    confidence=confidence,
                    amount=parsed_amount,
                )

                total_candidates.append(candidate)

        print(
            f"[TEXTRACT] Found {len(total_candidates)} candidates for {request.invoice_id}"
        )

        # Detect company currency (default CHF, can be configured)
        # TODO: Make this configurable per client via environment variable
        company_currency = "CHF"

        # Auto-detect most common currency from invoice
        all_detected_currencies = []
        for candidate in total_candidates:
            all_detected_currencies.extend(candidate["currencies"])

        if all_detected_currencies:
            currency_counts = Counter(all_detected_currencies)
            most_common = currency_counts.most_common(1)[0][0]
            # Only log if different from company currency
            if most_common != company_currency and currency_counts[most_common] > 1:
                print(f"[TEXTRACT] Invoice primarily in {most_common}")

        # Filter and score candidates
        valid_candidates = filter_candidates(total_candidates, company_currency)

        if not valid_candidates:
            print(f"[TEXTRACT] No valid candidates found after filtering")
            print(f"[TEXTRACT] Candidates analyzed: {len(total_candidates)}")
            return OCRResponse(
                invoice_id=request.invoice_id,
                vendor=extracted_data["vendor"],
                date=extracted_data["date"],
                time=None,
                total_amount=None,
                currency=company_currency,
                line_items=[],
            )

        # Pick the winner
        winner = select_best_candidate(valid_candidates)

        if not winner:
            print(f"[TEXTRACT] No winner selected")
            return OCRResponse(
                invoice_id=request.invoice_id,
                vendor=extracted_data["vendor"],
                date=extracted_data["date"],
                time=None,
                total_amount=None,
                currency=company_currency,
                line_items=[],
            )

        selected_amount = winner["amount"]
        selected_currency = winner["detected_currency"]

        print(
            f"[TEXTRACT] SELECTED: {selected_amount} {selected_currency} (score={winner['score']:.1f})"
        )

        # One last check with detected currency
        if not is_reasonable_expense_amount(selected_amount, selected_currency):
            print(
                f"[TEXTRACT] Final check FAILED: {selected_amount} {selected_currency}"
            )
            selected_amount = None
            selected_currency = company_currency

        extracted_data["total_amount"] = selected_amount
        extracted_data["currency"] = selected_currency

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
        print(f"[TEXTRACT] CRITICAL ERROR: {str(e)}")
        # Return empty result instead of crashing - let Odoo OCR handle it
        return OCRResponse(
            invoice_id=request.invoice_id,
            vendor=None,
            date=None,
            time=None,
            total_amount=None,
            currency="CHF",
            line_items=[],
        )
