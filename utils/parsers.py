def parse_amount(amount_str):
    # Parse amount string to float
    if not amount_str:
        return None

    cleaned = amount_str.replace("CHF", "").replace("$", "").replace("€", "").strip()
    cleaned = cleaned.replace("'", "").replace(",", "")

    try:
        return float(cleaned)
    except:
        return None