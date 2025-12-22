from typing import List, Dict, Any, Optional
from utils.currency_detect import has_total_keyword, detect_currency_from_text
from utils.currency_validator import (
    is_reasonable_expense_amount,
    calculate_currency_priority,
)


def score_candidate(candidate: Dict[str, Any], company_currency: str = "CHF") -> float:
    amount = candidate.get("amount")
    currencies = candidate.get("currencies", [])
    has_total = candidate.get("has_total_keyword", False)
    confidence = candidate.get("confidence", 0)
    detected_currency = candidate.get("detected_currency")

    score = 0.0

    # +50 points for company currency
    if detected_currency == company_currency:
        score += 50

    # +30 points for "TOTAL" keyword
    if has_total:
        score += 30

    # +20 points for high confidence
    if confidence >= 90:
        score += 20
    elif confidence >= 80:
        score += 10

    # +up to 20 points based on amount (larger amounts likely the total)
    if amount:
        score += min(amount / 100, 20)

    return score


def filter_candidates(
    candidates: List[Dict[str, Any]], company_currency: str = "CHF"
) -> List[Dict[str, Any]]:
    valid_candidates = []

    for candidate in candidates:
        amount = candidate.get("amount")
        currencies = candidate.get("currencies", [])
        confidence = candidate.get("confidence", 0)

        # Skip invalid amounts
        if amount is None:
            print(f"[TEXTRACT] Skipped NULL: label='{candidate.get('label')}'")
            continue

        # Determine currency for this candidate
        detected_currency = None
        if company_currency in currencies:
            detected_currency = company_currency
        elif currencies:
            # Pick highest priority currency
            currencies_with_priority = [
                (c, calculate_currency_priority(c, company_currency))
                for c in currencies
            ]
            detected_currency = max(currencies_with_priority, key=lambda x: x[1])[0]
        else:
            detected_currency = company_currency  # Assume company currency

        # Universal amount validation
        if not is_reasonable_expense_amount(amount, detected_currency):
            print(f"[TEXTRACT] Skipped unreasonable: {amount} {detected_currency}")
            continue

        # Filter low confidence
        if confidence < 70:
            print(
                f"[TEXTRACT] Skipped low confidence ({confidence}%): {amount} {detected_currency}"
            )
            continue

        # Calculate quality score
        candidate_with_currency = {**candidate, "detected_currency": detected_currency}
        quality_score = score_candidate(candidate_with_currency, company_currency)

        valid_candidates.append({**candidate_with_currency, "score": quality_score})

        print(
            f"[TEXTRACT] Valid: {amount} {detected_currency} (score={quality_score:.1f})"
        )

    return valid_candidates


def select_best_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    # Sort by score (highest first)
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Return winner
    return candidates[0]


def build_candidate_from_field(
    field_value: str, label_text: str, confidence: float, amount: Optional[float]
) -> Dict[str, Any]:
    # Detect currencies in BOTH label and value
    currencies_in_label = detect_currency_from_text(label_text)
    currencies_in_value = detect_currency_from_text(field_value)
    all_currencies = list(set(currencies_in_label + currencies_in_value))

    # Check if it has TOTAL keyword
    has_total = has_total_keyword(label_text)

    return {
        "value": field_value,
        "label": label_text or "",
        "amount": amount,
        "currencies": all_currencies,
        "has_total_keyword": has_total,
        "confidence": confidence,
    }
