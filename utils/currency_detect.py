import re
from typing import List, Optional

ISO_4217_CURRENCIES = {
    # A
    "AED",
    "AFN",
    "ALL",
    "AMD",
    "ANG",
    "AOA",
    "ARS",
    "AUD",
    "AWG",
    "AZN",
    # B
    "BAM",
    "BBD",
    "BDT",
    "BGN",
    "BHD",
    "BIF",
    "BMD",
    "BND",
    "BOB",
    "BRL",
    "BSD",
    "BTN",
    "BWP",
    "BYN",
    "BZD",
    # C
    "CAD",
    "CDF",
    "CHF",
    "CLP",
    "CNY",
    "COP",
    "CRC",
    "CUP",
    "CVE",
    "CZK",
    # D
    "DJF",
    "DKK",
    "DOP",
    "DZD",
    # E
    "EGP",
    "ERN",
    "ETB",
    "EUR",
    # F
    "FJD",
    "FKP",
    # G
    "GBP",
    "GEL",
    "GGP",
    "GHS",
    "GIP",
    "GMD",
    "GNF",
    "GTQ",
    "GYD",
    # H
    "HKD",
    "HNL",
    "HRK",
    "HTG",
    "HUF",
    # I
    "IDR",
    "ILS",
    "IMP",
    "INR",
    "IQD",
    "IRR",
    "ISK",
    # J
    "JEP",
    "JMD",
    "JOD",
    "JPY",
    # K
    "KES",
    "KGS",
    "KHR",
    "KMF",
    "KPW",
    "KRW",
    "KWD",
    "KYD",
    "KZT",
    # L
    "LAK",
    "LBP",
    "LKR",
    "LRD",
    "LSL",
    "LYD",
    # M
    "MAD",
    "MDL",
    "MGA",
    "MKD",
    "MMK",
    "MNT",
    "MOP",
    "MRU",
    "MUR",
    "MVR",
    "MWK",
    "MXN",
    "MYR",
    "MZN",
    # N
    "NAD",
    "NGN",
    "NIO",
    "NOK",
    "NPR",
    "NZD",
    # O
    "OMR",
    # P
    "PAB",
    "PEN",
    "PGK",
    "PHP",
    "PKR",
    "PLN",
    "PYG",
    # Q
    "QAR",
    # R
    "RON",
    "RSD",
    "RUB",
    "RWF",
    # S
    "SAR",
    "SBD",
    "SCR",
    "SDG",
    "SEK",
    "SGD",
    "SHP",
    "SLL",
    "SOS",
    "SPL",
    "SRD",
    "STN",
    "SYP",
    "SZL",
    # T
    "THB",
    "TJS",
    "TMT",
    "TND",
    "TOP",
    "TRY",
    "TTD",
    "TVD",
    "TWD",
    "TZS",
    # U
    "UAH",
    "UGX",
    "USD",
    "UYU",
    "UZS",
    # V
    "VEF",
    "VES",
    "VND",
    "VUV",
    # W
    "WST",
    # X
    "XAF",
    "XCD",
    "XDR",
    "XOF",
    "XPF",
    # Y
    "YER",
    # Z
    "ZAR",
    "ZMW",
    "ZWD",
}

# Currency symbols mapping (comprehensive)
CURRENCY_SYMBOLS = {
    "$": ["USD", "AUD", "CAD", "NZD", "HKD", "SGD", "MXN", "ARS", "CLP", "COP"],
    "€": ["EUR"],
    "£": ["GBP", "FKP", "GIP", "IMP", "JEP", "SHP"],
    "¥": ["JPY", "CNY"],
    "₹": ["INR"],
    "₨": ["PKR", "LKR", "NPR", "MUR", "SCR"],
    "₱": ["PHP"],
    "₩": ["KRW"],
    "₽": ["RUB"],
    "₴": ["UAH"],
    "₦": ["NGN"],
    "₡": ["CRC"],
    "₪": ["ILS"],
    "₺": ["TRY"],
    "₵": ["GHS"],
    "₸": ["KZT"],
    "₮": ["MNT"],
    "₾": ["GEL"],
    "₼": ["AZN"],
    "₫": ["VND"],
    "៛": ["KHR"],
    "₭": ["LAK"],
    "₲": ["PYG"],
    "﷼": ["IRR", "OMR", "QAR", "SAR", "YER"],
    "Fr": ["CHF", "CDF", "BIF", "DJF", "GNF", "KMF", "RWF"],
    "R": ["ZAR"],
    "R$": ["BRL"],
    "kr": ["SEK", "NOK", "DKK", "ISK"],
    "Kč": ["CZK"],
    "zł": ["PLN"],
    "lei": ["RON"],
    "Ft": ["HUF"],
}

# Currencies with no decimal places (large denominations)
NO_DECIMAL_CURRENCIES = {
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
}

# "TOTAL" keywords in multiple languages (comprehensive)
TOTAL_KEYWORDS = [
    # English
    "TOTAL",
    "AMOUNT",
    "SUM",
    "GRAND TOTAL",
    "NET TOTAL",
    "FINAL AMOUNT",
    "BALANCE DUE",
    "AMOUNT DUE",
    # German
    "BETRAG",
    "GESAMT",
    "GESAMTBETRAG",
    "SUMME",
    "ENDBETRAG",
    # French
    "MONTANT",
    "TOTAL",
    "SOMME",
    "MONTANT TOTAL",
    "SOLDE",
    # Italian
    "TOTALE",
    "IMPORTO",
    "SOMMA",
    "SALDO",
    # Spanish
    "TOTAL",
    "SUMA",
    "IMPORTE",
    "MONTO",
    # Portuguese
    "TOTAL",
    "MONTANTE",
    "SOMA",
    "SALDO",
    # Hindi/Indian
    "कुल",
    "राशि",
    "TOTAL",
    "AMOUNT",
    "रकम",
    # Chinese
    "总计",
    "总额",
    "合计",
    "金额",
    # Japanese
    "合計",
    "総額",
    "金額",
    # Arabic
    "المجموع",
    "المبلغ",
    "الإجمالي",
    # Russian
    "ИТОГО",
    "СУММА",
    "ВСЕГО",
    # Turkish
    "TOPLAM",
    "TUTAR",
    # Polish
    "SUMA",
    "RAZEM",
    "ŁĄCZNIE",
    # Dutch
    "TOTAAL",
    "BEDRAG",
    # Swedish/Norwegian/Danish
    "TOTALT",
    "BELOPP",
    "SUMMA",
    # Thai
    "รวม",
    "ยอดรวม",
    # Vietnamese
    "TỔNG",
    "TỔNG CỘNG",
    # Korean
    "합계",
    "총액",
    # Indonesian/Malay
    "JUMLAH",
    "TOTAL",
]


def detect_currency_from_text(text: str) -> List[str]:
    if not text:
        return []

    text_upper = text.upper()
    detected = []

    # Check for 3-letter ISO codes (most reliable)
    for code in ISO_4217_CURRENCIES:
        # Use word boundaries to avoid false matches
        # e.g., "INCH" shouldn't match "INR" + "CH"
        pattern = r"\b" + code + r"\b"
        if re.search(pattern, text_upper):
            detected.append(code)

    # Check for currency symbols
    for symbol, codes in CURRENCY_SYMBOLS.items():
        if symbol in text:
            detected.extend(codes)

    return list(set(detected))  # Remove duplicates


def has_total_keyword(text: str) -> bool:

    if not text:
        return False

    text_upper = text.upper()
    return any(keyword in text_upper for keyword in TOTAL_KEYWORDS)


def is_no_decimal_currency(currency: str) -> bool:

    return currency in NO_DECIMAL_CURRENCIES


def get_currency_display_name(currency_code: str) -> str:

    # Can expand this mapping as needed
    names = {
        "CHF": "Swiss Franc",
        "USD": "US Dollar",
        "EUR": "Euro",
        "GBP": "British Pound",
        "INR": "Indian Rupee",
        "JPY": "Japanese Yen",
        "CNY": "Chinese Yuan",
        "PKR": "Pakistani Rupee",
        "BDT": "Bangladeshi Taka",
        "NGN": "Nigerian Naira",
        "THB": "Thai Baht",
        "VND": "Vietnamese Dong",
    }
    return names.get(currency_code, currency_code)
