"""
Policy Store - Now fetches from Confluence (Phase 2)
Maintains same interface, but replaces mock data with real Confluence data
"""

import time
from typing import Dict, List, Any, Optional
from models.schemas import (
    PolicyData,
    EnrichmentRules,
    ValidationRules,
    CategoryDefinition,
)
from utils.confluence_client import get_confluence_client

# In-memory cache (same as before)
policy_cache: Dict[str, tuple[PolicyData, float]] = {}


def get_policy(company_id: str) -> PolicyData:
    """
    Get policy from Confluence (cached with 24hr TTL)

    Phase 2 Implementation:
    - Fetches from Confluence API
    - Parses policy pages
    - Caches for 24 hours
    """
    cache_key = f"policy_{company_id}"

    # Check cache first
    if cache_key in policy_cache:
        cached_data, timestamp = policy_cache[cache_key]
        if time.time() - timestamp < 86400:  # 24 hours
            print(f"[CACHE HIT] Using cached policy for {company_id}")
            return cached_data

    print(f"[CACHE MISS] Fetching policy from Confluence for {company_id}")

    # Fetch from Confluence
    try:
        client = get_confluence_client()

        # Step 1: Get policy index
        index_data = client.get_policy_index()

        # Step 2: Build category definitions
        categories = []

        for policy_row in index_data:
            category_name = policy_row.get("Category", "").strip()

            if not category_name:
                continue

            # Fetch detailed page for this category
            try:
                details = client.get_category_details(category_name)
            except Exception as e:
                print(f"[WARNING] Could not load details for {category_name}: {e}")
                continue

            # Parse aliases
            aliases_str = policy_row.get("Aliases", "")
            aliases = [a.strip() for a in aliases_str.split(",")] if aliases_str else []

            # Merge with page aliases
            if details.get("aliases"):
                aliases.extend(details["aliases"])
            aliases = list(set(aliases))  # Remove duplicates

            # Build validation rules
            validation_rules = ValidationRules(
                max_amount=float(policy_row.get("Max Amount", 0)),
                currency=policy_row.get("Currency", "CHF"),
                requires_receipt=(policy_row.get("Receipt Required", "Yes") == "Yes"),
                requires_attendees=(
                    policy_row.get("Attendees Required", "No") == "Yes"
                ),
                max_age_days=int(policy_row.get("Max Age Days", 90)),
            )

            # Override with detailed rules if available
            if details.get("validation_rules"):
                detailed_rules = details["validation_rules"]
                if "max_amount" in detailed_rules:
                    validation_rules.max_amount = detailed_rules["max_amount"]
                if "requires_receipt" in detailed_rules:
                    validation_rules.requires_receipt = detailed_rules[
                        "requires_receipt"
                    ]
                if "requires_attendees" in detailed_rules:
                    validation_rules.requires_attendees = detailed_rules[
                        "requires_attendees"
                    ]

            # Build enrichment rules
            enrichment_rules = EnrichmentRules(
                time_based=details.get("enrichment_rules", {}).get("time_based"),
                vendor_keywords=details.get("enrichment_rules", {}).get(
                    "vendor_keywords"
                ),
            )

            # Create category definition
            category_def = CategoryDefinition(
                name=category_name,
                aliases=aliases,
                enrichment_rules=enrichment_rules,
                validation_rules=validation_rules,
            )

            categories.append(category_def)
            print(
                f"[CONFLUENCE] Loaded policy: {category_name} (max: {validation_rules.max_amount} CHF)"
            )

        # Build policy data
        policy_data = PolicyData(
            company_id=company_id,
            effective_date="2024-01-01",  # Could parse from Confluence
            categories=categories,
            default_category="Other",
            cache_ttl=86400,
        )

        # Cache it
        policy_cache[cache_key] = (policy_data, time.time())

        print(f"[CONFLUENCE] Successfully loaded {len(categories)} policies")
        return policy_data

    except Exception as e:
        print(f"[ERROR] Failed to fetch from Confluence: {e}")
        print(f"[FALLBACK] Using empty policy set")

        # Return minimal fallback
        return PolicyData(
            company_id=company_id,
            effective_date="2024-01-01",
            categories=[],
            default_category="Other",
        )


# Keep all helper functions the same
def invalidate_cache(company_id: Optional[str] = None):
    """Manually invalidate policy cache"""
    if company_id:
        cache_key = f"policy_{company_id}"
        if cache_key in policy_cache:
            del policy_cache[cache_key]
            print(f"[CACHE] Invalidated cache for {company_id}")
    else:
        policy_cache.clear()
        print(f"[CACHE] Cleared all policy cache")


def find_category_by_name(
    policy: PolicyData, category_name: str
) -> Optional[CategoryDefinition]:
    """Find category by name or alias (case-insensitive)"""
    category_lower = category_name.lower().strip()

    for cat in policy.categories:
        if cat.name.lower() == category_lower:
            return cat
        if any(alias.lower() == category_lower for alias in cat.aliases):
            return cat

    return None


def matches_time_rule(time_str: str, time_rule: Dict[str, Any]) -> bool:
    """Check if time matches rule"""
    try:
        hour = int(time_str.split(":")[0])
        return time_rule["start_hour"] <= hour <= time_rule["end_hour"]
    except:
        return False


def matches_vendor_keywords(vendor: str, keywords: List[str]) -> bool:
    """Check if vendor contains keywords"""
    if not vendor:
        return False
    vendor_lower = vendor.lower()
    return any(keyword.lower() in vendor_lower for keyword in keywords)


def get_all_categories(company_id: str) -> List[str]:
    """Get list of all category names"""
    policy = get_policy(company_id)
    return [cat.name for cat in policy.categories]


def get_category_max_amount(company_id: str, category_name: str) -> Optional[float]:
    """Quick lookup for max amount"""
    policy = get_policy(company_id)
    cat = find_category_by_name(policy, category_name)
    return cat.validation_rules.max_amount if cat else None
