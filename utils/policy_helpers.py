from typing import Dict, Any, List, Optional


def matches_time_rule(time_str: str, time_rule: Dict[str, Any]) -> bool:
    # Check if time matches a time-based rule

    try:
        # Handle different time formats: "19:30", "7:30 PM", "19:30:00"
        time_clean = time_str.strip().split()[0]  # Remove AM/PM if present
        hour = int(time_clean.split(":")[0])

        return time_rule["start_hour"] <= hour <= time_rule["end_hour"]
    except (ValueError, IndexError, KeyError):
        return False


def matches_vendor_keywords(vendor: str, keywords: List[str]) -> bool:
    # Check if vendor name contains any of the keywords

    if not vendor or not keywords:
        return False

    vendor_lower = vendor.lower()
    return any(keyword.lower() in vendor_lower for keyword in keywords)


def find_category_by_name(policy_data, category_name: str) -> Optional[Any]:
    # Find category by name or alias in policy data
    if not category_name:
        return None

    category_lower = category_name.lower()

    for cat in policy_data.categories:
        # Check exact name match
        if cat.name.lower() == category_lower:
            return cat

        # Check aliases
        if any(alias.lower() == category_lower for alias in cat.aliases):
            return cat

    return None
