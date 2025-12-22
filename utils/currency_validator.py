from typing import Optional
from utils.currency_detect import is_no_decimal_currency


def is_reasonable_expense_amount(amount: float, currency: Optional[str] = None) -> bool:
    if amount is None:
        return False

    # Currencies with no decimal places (use larger numbers)
    if currency and is_no_decimal_currency(currency):
        MIN_AMOUNT = 100  # e.g., 100 JPY = ~0.70 USD
        MAX_AMOUNT = 10000000  # e.g., 10M JPY = ~70,000 USD
    else:
        # Standard currencies (most of the world)
        MIN_AMOUNT = 0.50  # Minimum expense (any currency)
        MAX_AMOUNT = 100000  # Maximum employee expense (any currency)

    return MIN_AMOUNT <= amount <= MAX_AMOUNT


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
    if is_no_decimal_currency(currency):
        return (100, 10000000)
    else:
        return (0.50, 100000)
