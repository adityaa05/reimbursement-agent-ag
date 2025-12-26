import re
from typing import Optional
from fastapi import HTTPException

VALID_CURRENCIES = {
    "CHF",
    "USD",
    "EUR",
    "GBP",
    "JPY",
    "CNY",
    "INR",
    "AUD",
    "CAD",
    "SGD",
}


def validate_expense_request_id(expense_request_id: Optional[int]) -> int:
    """Validate expense_request_id is present and valid."""
    if expense_request_id is None:
        raise HTTPException(
            status_code=400, detail="Missing required field: expense_request_id"
        )

    if not isinstance(expense_request_id, int) or expense_request_id <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid expense_request_id: {expense_request_id}. Must be positive integer.",
        )

    return expense_request_id


def validate_currency(currency: str) -> str:
    """Validate and normalize currency code."""
    currency_upper = currency.upper().strip()
    if currency_upper not in VALID_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid currency code: {currency}. Must be valid ISO 4217 code.",
        )

    return currency_upper


def normalize_amount(amount: float, currency: str = "CHF") -> float:
    """Normalize amount with proper rounding based on currency type."""
    ZERO_DECIMAL_CURRENCIES = {"JPY", "KRW", "VND", "CLP", "ISK"}

    if currency in ZERO_DECIMAL_CURRENCIES:
        return round(amount, 0)
    else:
        return round(amount, 2)


def validate_amount(amount: Optional[float], field_name: str = "amount") -> float:
    """Validate amount is positive and reasonable."""
    if amount is None:
        raise HTTPException(
            status_code=400, detail=f"Missing required field: {field_name}"
        )

    if not isinstance(amount, (int, float)):
        raise HTTPException(
            status_code=400, detail=f"Invalid {field_name}: must be numeric"
        )

    if amount < 0:
        raise HTTPException(
            status_code=400, detail=f"Invalid {field_name}: must be non-negative"
        )

    if amount > 1_000_000:
        raise HTTPException(
            status_code=400, detail=f"Invalid {field_name}: exceeds maximum (1,000,000)"
        )

    return amount
