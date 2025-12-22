from typing import Optional
from utils.currency_detect import is_no_decimal_currency


def is_reasonable_expense_amount(amount: float, currency: Optional[str] = None) -> bool:
    """
    FIXED: More permissive limits to reduce Textract failures

    Old limits: 0.50 - 100,000
    New limits: 0.01 - 1,000,000
    """
    if amount is None:
        return False

    # Currencies with no decimal places (use larger numbers)
    if currency and is_no_decimal_currency(currency):
        MIN_AMOUNT = 1  # e.g., 1 JPY = ~0.007 USD (very small)
        MAX_AMOUNT = 100000000  # e.g., 100M JPY = ~700,000 USD (large corporate)
    else:
        # FIXED: More permissive for standard currencies
        MIN_AMOUNT = 0.01  # Was 0.50, now accept even tiny amounts
        MAX_AMOUNT = 1000000  # Was 100,000, now accept large expenses (flights, hotels)

    is_valid = MIN_AMOUNT <= amount <= MAX_AMOUNT

    if not is_valid:
        print(
            f"[VALIDATOR] Amount {amount} {currency} outside range [{MIN_AMOUNT}, {MAX_AMOUNT}]"
        )

    return is_valid


def calculate_currency_priority(currency: str, company_currency: str = "CHF") -> int:
    if currency == company_currency:
        return 100  # Company currency always wins

    # Major stable currencies get higher priority
    major_currencies = {
        "USD": 95,
        "EUR": 90,
        "GBP": 85,
        "CHF": 100,
        "JPY": 80,
        "CNY": 75,
        "INR": 70,
        "AUD": 70,
        "CAD": 70,
        "SGD": 70,
        "HKD": 65,
    }

    return major_currencies.get(currency, 50)  # Default priority


def validate_currency_code(currency: str) -> bool:
    from utils.currency_detect import ISO_4217_CURRENCIES

    return currency in ISO_4217_CURRENCIES


def get_min_max_for_currency(currency: str) -> tuple:
    """FIXED: Return new permissive limits"""
    if is_no_decimal_currency(currency):
        return (1, 100000000)
    else:
        return (0.01, 1000000)  # Was (0.50, 100000)
