"""
Strategy:
1. Try AWS Textract's semantic fields (TOTAL, AMOUNT_PAID, INVOICE_TOTAL)
2. Fallback to geometric analysis (largest amount at bottom-right)
3. Final fallback to simple "largest amount wins"
"""

from fastapi import APIRouter, HTTPException
import base64
from collections import Counter
from config import textract_client
from models.schemas import OCRRequest, OCRResponse
from utils.parsers import parse_amount
from utils.currency_detect import detect_currency_from_text


router = APIRouter()


def extract_amount_semantic(summary_fields):
    """
    Try to extract amount using AWS Textract's semantic understanding
    Checks multiple field types, not just "TOTAL"
    """
    # Priority order of field types (most reliable first)
    PRIORITY_FIELDS = [
        "TOTAL",
        "INVOICE_TOTAL",
        "AMOUNT_PAID",
        "AMOUNT_DUE",
        "SUBTOTAL",
        "AMOUNT",
    ]

    candidates_by_type = {}

    for field in summary_fields:
        field_type = field.get("Type", {}).get("Text", "")
        field_value = field.get("ValueDetection", {}).get("Text", "")
        confidence = field.get("ValueDetection", {}).get("Confidence", 0)
        label_text = field.get("LabelDetection", {}).get("Text", "")

        amount = parse_amount(field_value)

        if amount and amount > 0:
            if field_type not in candidates_by_type:
                candidates_by_type[field_type] = []

            candidates_by_type[field_type].append(
                {
                    "amount": amount,
                    "confidence": confidence,
                    "label": label_text,
                    "value": field_value,
                    "type": field_type,
                }
            )

    # Try each priority field type in order
    for field_type in PRIORITY_FIELDS:
        if field_type in candidates_by_type:
            # Get highest confidence candidate of this type
            candidates = candidates_by_type[field_type]
            best = max(candidates, key=lambda x: x["confidence"])

            print(
                f"[TEXTRACT] Semantic extraction: Found {best['amount']} via {field_type} (confidence={best['confidence']:.1f}%)"
            )
            return best["amount"], detect_currency_from_text(
                best["value"] + " " + best["label"]
            )

    print(f"[TEXTRACT] Semantic extraction: No priority fields found")
    return None, []


def extract_amount_geometric(textract_response):
    """
    UNIVERSAL FALLBACK: Use geometry to find the total

    Key insight: Invoice totals are usually:
    - At the BOTTOM of the page (high Y coordinate)
    - On the RIGHT side (high X coordinate)
    - The LARGEST amount on the page

    This works for ANY language, ANY format!
    """
    blocks = textract_response.get("Blocks", [])
    candidates = []

    print(f"[TEXTRACT] Geometric extraction: Analyzing {len(blocks)} blocks")

    for block in blocks:
        if block["BlockType"] != "LINE":
            continue

        text = block.get("Text", "")
        amount = parse_amount(text)

        if not amount or amount < 0.01:
            continue

        # Get position on page (0-1 scale, where 0,0 is top-left)
        geometry = block.get("Geometry", {}).get("BoundingBox", {})
        top = geometry.get("Top", 0)  # 0 = top, 1 = bottom
        left = geometry.get("Left", 0)  # 0 = left, 1 = right
        confidence = block.get("Confidence", 0)

        # Calculate intelligent score
        # Totals are typically at bottom-right and are the largest number
        position_score = (1 - top) * 30  # Prefer bottom (max 30 points)
        alignment_score = left * 20  # Prefer right-aligned (max 20 points)
        size_score = min(amount / 100, 40)  # Prefer larger amounts (max 40 points)
        confidence_score = confidence / 10  # Confidence bonus (max 10 points)

        total_score = position_score + alignment_score + size_score + confidence_score

        currencies = detect_currency_from_text(text)

        candidates.append(
            {
                "amount": amount,
                "text": text,
                "position": (top, left),
                "confidence": confidence,
                "score": total_score,
                "currencies": currencies,
            }
        )

    if not candidates:
        print(f"[TEXTRACT] Geometric extraction: No candidates found")
        return None, []

    # Sort by score and show top 3
    candidates.sort(key=lambda x: x["score"], reverse=True)

    print(f"[TEXTRACT] Geometric extraction: Found {len(candidates)} candidates")
    for idx, c in enumerate(candidates[:3], 1):
        print(
            f"  {idx}. {c['amount']} at pos({c['position'][0]:.2f}, {c['position'][1]:.2f}) score={c['score']:.1f}"
        )

    best = candidates[0]
    print(
        f"[TEXTRACT] Geometric extraction: Selected {best['amount']} (score={best['score']:.1f})"
    )

    return best["amount"], best["currencies"]


def extract_amount_simple(summary_fields):
    """
    SIMPLEST FALLBACK: Just pick the largest REASONABLE amount
    Rejects insane values (account numbers, reference IDs, etc.)
    """
    amounts = []

    for field in summary_fields:
        field_value = field.get("ValueDetection", {}).get("Text", "")
        amount = parse_amount(field_value)

        if amount and amount > 0:
            # SANITY CHECK: Reject amounts > 100,000 (likely not expense amounts)
            # Most business expenses are < 100K
            if amount > 100000:
                print(
                    f"[TEXTRACT] Simple extraction: Rejecting insane amount {amount} (likely account/ref number)"
                )
                continue

            # SANITY CHECK: Reject amounts < 0.01 (too small)
            if amount < 0.01:
                print(
                    f"[TEXTRACT] Simple extraction: Rejecting too-small amount {amount}"
                )
                continue

            currencies = detect_currency_from_text(field_value)
            amounts.append((amount, currencies))

    if amounts:
        best = max(amounts, key=lambda x: x[0])
        print(
            f"[TEXTRACT] Simple extraction: Picked largest reasonable amount {best[0]}"
        )
        return best[0], best[1]

    print(f"[TEXTRACT] Simple extraction: No reasonable amounts found")
    return None, []


@router.post("/textract-ocr", response_model=OCRResponse)
async def textract_ocr(request: OCRRequest):
    """
    Three-tier extraction strategy:
    1. Semantic: Use AWS Textract's field types (TOTAL, AMOUNT_PAID, etc.)
    2. Geometric: Use position analysis (bottom-right = total)
    3. Simple: Pick largest amount

    Works for ANY language, ANY format, ANY currency!
    """
    try:
        # Decode and convert image if needed
        image_bytes = base64.b64decode(request.image_base64)

        try:
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(image_bytes))
            if img.format not in ["JPEG", "PNG", "PDF"]:
                print(f"[TEXTRACT] Converting {img.format} to JPEG")
                buffer = io.BytesIO()
                if img.mode in ("RGBA", "LA", "P"):
                    img = img.convert("RGB")
                img.save(buffer, format="JPEG", quality=95)
                image_bytes = buffer.getvalue()
        except Exception as e:
            print(f"[TEXTRACT] Image conversion failed: {e}")

        # Call AWS Textract
        print(f"[TEXTRACT] ========== PROCESSING {request.invoice_id} ==========")
        print(f"[TEXTRACT] Image size: {len(image_bytes)} bytes")

        response = textract_client.analyze_expense(Document={"Bytes": image_bytes})

        # Debug: Check if Textract returned ANY data
        total_blocks = len(response.get("Blocks", []))
        print(f"[TEXTRACT] Textract returned {total_blocks} blocks")

        if total_blocks == 0:
            print(
                f"[TEXTRACT] WARNING: Textract returned ZERO blocks - image may be unsupported/corrupted"
            )

        expense_docs = response.get("ExpenseDocuments", [])
        if not expense_docs:
            print(f"[TEXTRACT] No ExpenseDocuments found")
            return OCRResponse(
                invoice_id=request.invoice_id,
                vendor=None,
                date=None,
                time=None,
                total_amount=None,
                currency="CHF",
                line_items=[],
            )

        doc = expense_docs[0]
        summary_fields = doc.get("SummaryFields", [])

        # Extract vendor and date
        vendor = None
        date = None
        for field in summary_fields:
            field_type = field.get("Type", {}).get("Text", "")
            field_value = field.get("ValueDetection", {}).get("Text", "")

            if field_type in ["VENDOR_NAME", "RECEIVER_NAME"]:
                vendor = field_value
            elif field_type == "INVOICE_RECEIPT_DATE":
                date = field_value

        # THREE-TIER UNIVERSAL EXTRACTION
        amount = None
        currencies = []

        # TIER 1: Try semantic extraction (most reliable)
        print(f"[TEXTRACT] TIER 1: Semantic extraction...")
        amount, currencies = extract_amount_semantic(summary_fields)

        # TIER 2: Try geometric extraction (works for any language)
        if not amount:
            print(f"[TEXTRACT] TIER 2: Geometric extraction...")
            amount, currencies = extract_amount_geometric(response)

        # TIER 3: Simple largest amount (last resort)
        if not amount:
            print(f"[TEXTRACT] TIER 3: Simple extraction...")
            amount, currencies = extract_amount_simple(summary_fields)

        # Determine currency
        company_currency = "CHF"
        if currencies:
            # Use most common detected currency
            currency_counts = Counter(currencies)
            detected_currency = currency_counts.most_common(1)[0][0]
        else:
            detected_currency = company_currency

        if amount:
            print(f"[TEXTRACT]  SUCCESS: {amount} {detected_currency}")
        else:
            print(f"[TEXTRACT]  FAILED: No amount found")

        return OCRResponse(
            invoice_id=request.invoice_id,
            vendor=vendor,
            date=date,
            time=None,
            total_amount=amount,
            currency=detected_currency,
            line_items=[],
        )

    except Exception as e:
        print(f"[TEXTRACT] CRITICAL ERROR: {str(e)}")
        return OCRResponse(
            invoice_id=request.invoice_id,
            vendor=None,
            date=None,
            time=None,
            total_amount=None,
            currency="CHF",
            line_items=[],
        )
