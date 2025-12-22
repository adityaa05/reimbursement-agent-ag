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
    elif confidence >= 70:
        score += 5  # Still give some points for medium confidence

    # +up to 20 points based on amount (larger amounts likely the total)
    if amount:
        score += min(amount / 100, 20)

    return score


def filter_candidates(
    candidates: List[Dict[str, Any]], company_currency: str = "CHF"
) -> List[Dict[str, Any]]:
    """
    Filter and validate amount candidates

    FIXED: More permissive to reduce Textract failures
    - Lowered confidence threshold from 70% to 50%
    - Increased max amount from 100K to 1M
    - Better logging for debugging
    """
    valid_candidates = []

    print(f"[TEXTRACT] Filtering {len(candidates)} candidates...")

    for idx, candidate in enumerate(candidates, 1):
        amount = candidate.get("amount")
        currencies = candidate.get("currencies", [])
        confidence = candidate.get("confidence", 0)
        label = candidate.get("label", "")
        value = candidate.get("value", "")

        print(
            f"[TEXTRACT]   Candidate {idx}: amount={amount}, confidence={confidence}%, label='{label}', value='{value}'"
        )

        # Skip invalid amounts
        if amount is None:
            print(f"[TEXTRACT] Skipped (NULL amount)")
            continue

        # FIXED: More permissive minimum (was 0.50, now 0.01)
        if amount < 0.01:
            print(f"[TEXTRACT] Skipped (too small: {amount})")
            continue

        # FIXED: More permissive maximum (was 100K, now 1M)
        if amount > 1000000:
            print(f"[TEXTRACT] Skipped (too large: {amount})")
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

        # FIXED: Don't reject low confidence - just warn (was 70%, now 50%)
        if confidence < 50:
            print(f"[TEXTRACT] WARNING: Low confidence ({confidence}%), but keeping it")
            # Don't skip! Just warn and continue

        # Calculate quality score
        candidate_with_currency = {**candidate, "detected_currency": detected_currency}
        quality_score = score_candidate(candidate_with_currency, company_currency)

        valid_candidates.append({**candidate_with_currency, "score": quality_score})

        print(f"[TEXTRACT] VALID (score={quality_score:.1f})")

    print(
        f"[TEXTRACT] Result: {len(valid_candidates)} valid candidates out of {len(candidates)}"
    )
    return valid_candidates


def select_best_candidate(candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not candidates:
        print(f"[TEXTRACT] No candidates to select from!")
        return None

    # Sort by score (highest first)
    candidates.sort(key=lambda x: x.get("score", 0), reverse=True)

    # Show top 3 candidates
    print(f"[TEXTRACT] Top candidates:")
    for idx, c in enumerate(candidates[:3], 1):
        print(
            f"  {idx}. {c['amount']} {c['detected_currency']} (score={c['score']:.1f}, conf={c['confidence']}%)"
        )

    # Return winner
    winner = candidates[0]
    print(f"[TEXTRACT] Selected: {winner['amount']} {winner['detected_currency']}")
    return winner


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
