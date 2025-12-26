import re
from typing import Dict, Any, List, Optional


def matches_time_rule(time_str: str, time_rule: Dict[str, Any]) -> bool:
    """Check if time matches a time-based rule."""
    try:
        time_clean = time_str.strip().split()[0]
        hour = int(time_clean.split(":")[0])
        return time_rule["start_hour"] <= hour <= time_rule["end_hour"]
    except (ValueError, IndexError, KeyError):
        return False


def matches_vendor_keywords(vendor: str, keywords: List[str]) -> bool:
    """
    Enhanced vendor keyword matching with comprehensive normalization.
    Supports case-insensitive partial matching with special character handling.
    """
    if not vendor or not keywords:
        print(f"[ENRICH] WARNING: Empty input detected")
        print(f" Vendor: {repr(vendor)}")
        print(f" Keywords: {keywords if keywords else 'None'}")
        return False

    # Normalize vendor string
    vendor_normalized = vendor.lower().strip()
    vendor_normalized = vendor_normalized.replace("\n", " ").replace("\r", " ")
    vendor_normalized = re.sub(r"\s+", " ", vendor_normalized)
    vendor_normalized = re.sub(r"[^\w\s]", " ", vendor_normalized, flags=re.UNICODE)
    vendor_normalized = re.sub(r"\s+", " ", vendor_normalized).strip()

    print(f"[ENRICH] Checking vendor: '{vendor_normalized[:60]}'")
    print(
        f"[ENRICH] Against {len(keywords)} keywords: {keywords[:10]}{'...' if len(keywords) > 10 else ''}"
    )

    # Check each keyword with partial matching
    for keyword in keywords:
        keyword_normalized = keyword.lower().strip()
        if keyword_normalized in vendor_normalized:
            print(f"[ENRICH] MATCH FOUND: '{keyword_normalized}' found in vendor")
            return True

    print(f"[ENRICH] No keyword match found for '{vendor_normalized[:40]}'")
    print(f"[ENRICH] Tried {len(keywords)} keywords, none matched")
    return False


def find_category_by_name(policy_data, category_name: str) -> Optional[Any]:
    """Find category by name or alias in policy data with case-insensitive matching."""
    if not category_name:
        return None

    category_lower = category_name.lower()

    for cat in policy_data.categories:
        if cat.name.lower() == category_lower:
            return cat
        if any(alias.lower() == category_lower for alias in cat.aliases):
            return cat

    return None
