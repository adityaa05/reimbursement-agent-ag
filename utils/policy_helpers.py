from typing import Dict, Any, List, Optional
import re


def matches_time_rule(time_str: str, time_rule: Dict[str, Any]) -> bool:
    """
    Check if time matches a time-based rule

    Examples:
        "19:30" with rule {start_hour: 18, end_hour: 22} → True
        "07:45" with rule {start_hour: 7, end_hour: 10} → True
    """
    try:
        # Handle different time formats: "19:30", "7:30 PM", "19:30:00"
        time_clean = time_str.strip().split()[0]  # Remove AM/PM if present
        hour = int(time_clean.split(":")[0])

        return time_rule["start_hour"] <= hour <= time_rule["end_hour"]
    except (ValueError, IndexError, KeyError):
        return False


def matches_vendor_keywords(vendor: str, keywords: List[str]) -> bool:
    """
    FIXED: Enhanced vendor keyword matching with comprehensive normalization

    Critical fixes applied:
    1. Newline removal (\n, \r)
    2. Multiple space collapse
    3. Special character handling
    4. Case-insensitive partial matching
    5. Debug logging for troubleshooting

    Examples:
        ✅ "Mercure\nHOTELS" + ["hotel", "mercure"] → TRUE
        ✅ "ALLRESTO FLUGHAFEN MUe >" + ["allresto"] → TRUE
        ✅ "freenow" + ["uber", "taxi", "freenow"] → TRUE
        ✅ "Münchner Stubn" + ["münchner", "restaurant"] → TRUE

    Args:
        vendor: Vendor name from invoice (may contain newlines, special chars)
        keywords: List of keywords from Confluence policy

    Returns:
        True if any keyword found in vendor name, False otherwise
    """

    # ================================================================
    # VALIDATION: Check for empty inputs
    # ================================================================
    if not vendor or not keywords:
        print(f"[ENRICH] ⚠️  Empty input detected")
        print(f"  Vendor: {repr(vendor)}")
        print(f"  Keywords: {keywords if keywords else 'None'}")
        return False

    # ================================================================
    # STEP 1: Normalize vendor string (CRITICAL FIX)
    # ================================================================

    # Convert to lowercase for case-insensitive matching
    vendor_normalized = vendor.lower().strip()

    # Remove newlines and carriage returns
    # BEFORE: "Mercure\nHOTELS" → AFTER: "Mercure HOTELS"
    vendor_normalized = vendor_normalized.replace("\n", " ").replace("\r", " ")

    # Collapse multiple spaces into single space
    # BEFORE: "ALLRESTO  FLUGHAFEN   " → AFTER: "ALLRESTO FLUGHAFEN"
    vendor_normalized = re.sub(r"\s+", " ", vendor_normalized)

    # Remove special characters but keep alphanumeric, spaces, accented chars
    # BEFORE: "ALLRESTO FLUGHAFEN MUe >" → AFTER: "ALLRESTO FLUGHAFEN MUe"
    # Note: Using re.UNICODE to preserve "Münchner", "café", etc.
    vendor_normalized = re.sub(r"[^\w\s]", " ", vendor_normalized, flags=re.UNICODE)

    # Collapse spaces again after special char removal
    vendor_normalized = re.sub(r"\s+", " ", vendor_normalized).strip()

    # ================================================================
    # DEBUG LOGGING: Show what we're comparing
    # ================================================================
    print(f"[ENRICH] Checking vendor: '{vendor_normalized[:60]}'")
    print(
        f"[ENRICH] Against {len(keywords)} keywords: {keywords[:10]}{'...' if len(keywords) > 10 else ''}"
    )

    # ================================================================
    # STEP 2: Check each keyword with partial matching
    # ================================================================
    for keyword in keywords:
        # Normalize keyword same way
        keyword_normalized = keyword.lower().strip()

        # Partial match - keyword can appear anywhere in vendor name
        # Example: "hotel" matches in "mercure hotel"
        if keyword_normalized in vendor_normalized:
            print(f"[ENRICH] ✅ MATCH FOUND: '{keyword_normalized}' found in vendor")
            return True

    # ================================================================
    # NO MATCH: Log for debugging
    # ================================================================
    print(f"[ENRICH] ❌ No keyword match found for '{vendor_normalized[:40]}'")
    print(f"[ENRICH]    Tried {len(keywords)} keywords, none matched")

    return False


def find_category_by_name(policy_data, category_name: str) -> Optional[Any]:
    """
    Find category by name or alias in policy data

    Performs case-insensitive matching against:
    - Exact category name
    - Category aliases

    Examples:
        "Meals" → finds "Meals" category
        "meals" → finds "Meals" category
        "Food" → finds "Meals" category (if "Food" is alias)
        "Dining" → finds "Meals" category (if "Dining" is alias)

    Args:
        policy_data: PolicyData object with categories
        category_name: Name or alias to search for

    Returns:
        CategoryDefinition if found, None otherwise
    """
    if not category_name:
        return None

    category_lower = category_name.lower()

    for cat in policy_data.categories:
        # Check exact name match (case-insensitive)
        if cat.name.lower() == category_lower:
            return cat

        # Check aliases (case-insensitive)
        if any(alias.lower() == category_lower for alias in cat.aliases):
            return cat

    return None
