"""
Mock policy store for Phase 1 (Simulates Confluence)
Will be replaced with real Confluence API in Phase 2

This module provides:
- Policy data structures
- Mock policy definitions
- In-memory caching
- Helper functions for policy lookups
"""

import time
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class EnrichmentRules(BaseModel):
    """Rules for automatic category enrichment"""

    time_based: Optional[List[Dict[str, Any]]] = None
    vendor_keywords: Optional[List[str]] = None


class ValidationRules(BaseModel):
    """Rules for policy compliance validation"""

    max_amount: float
    currency: str = "CHF"
    requires_receipt: bool = True
    requires_attendees: Optional[bool] = None
    max_age_days: Optional[int] = 90
    approved_vendors: Optional[List[str]] = None


class CategoryDefinition(BaseModel):
    """Complete category definition with enrichment and validation rules"""

    name: str
    aliases: List[str] = []
    enrichment_rules: EnrichmentRules
    validation_rules: ValidationRules


class PolicyData(BaseModel):
    """Complete policy data structure (represents one Confluence page)"""

    company_id: str
    effective_date: str
    categories: List[CategoryDefinition]
    default_category: str = "Other"
    cache_ttl: int = 86400  # 24 hours in seconds


# ============================================================================
# MOCK POLICY DATA (Simulates Confluence Content)
# In Phase 2, this will be fetched from Confluence API
# ============================================================================

MOCK_POLICIES = {
    "hashgraph_inc": PolicyData(
        company_id="hashgraph_inc",
        effective_date="2025-01-01",
        default_category="Other",
        categories=[
            # -------- MEALS --------
            CategoryDefinition(
                name="Meals",
                aliases=["Food", "Dining", "Restaurant", "Food & Beverage"],
                enrichment_rules=EnrichmentRules(
                    time_based=[
                        {"start_hour": 7, "end_hour": 10, "subcategory": "Breakfast"},
                        {"start_hour": 12, "end_hour": 15, "subcategory": "Lunch"},
                        {"start_hour": 18, "end_hour": 22, "subcategory": "Dinner"},
                    ],
                    vendor_keywords=[
                        "restaurant",
                        "cafe",
                        "bistro",
                        "diner",
                        "pizzeria",
                        "bakery",
                        "brasserie",
                        "eatery",
                        "food",
                        "dining",
                        "mcdonald",
                        "burger",
                        "starbucks",
                        "subway",
                    ],
                ),
                validation_rules=ValidationRules(
                    max_amount=50.0,
                    currency="CHF",
                    requires_receipt=True,
                    requires_attendees=False,
                    max_age_days=90,
                ),
            ),
            # -------- ACCOMMODATION --------
            CategoryDefinition(
                name="Accommodation",
                aliases=["Hotel", "Lodging", "Rooms", "Stay"],
                enrichment_rules=EnrichmentRules(
                    vendor_keywords=[
                        "hotel",
                        "motel",
                        "resort",
                        "inn",
                        "airbnb",
                        "hostel",
                        "marriott",
                        "hilton",
                        "hyatt",
                        "ibis",
                        "novotel",
                        "radisson",
                        "sheraton",
                    ]
                ),
                validation_rules=ValidationRules(
                    max_amount=200.0,
                    currency="CHF",
                    requires_receipt=True,
                    requires_attendees=False,
                    max_age_days=90,
                ),
            ),
            # -------- TRAVEL --------
            CategoryDefinition(
                name="Travel",
                aliases=["Transportation", "Transit", "Transport"],
                enrichment_rules=EnrichmentRules(
                    vendor_keywords=[
                        "uber",
                        "lyft",
                        "taxi",
                        "cab",
                        "railway",
                        "airline",
                        "airport",
                        "bus",
                        "train",
                        "flight",
                        "metro",
                        "sbb",
                        "swiss",
                        "lufthansa",
                        "easyjet",
                    ]
                ),
                validation_rules=ValidationRules(
                    max_amount=150.0,
                    currency="CHF",
                    requires_receipt=True,
                    requires_attendees=False,
                    max_age_days=90,
                ),
            ),
            # -------- OFFICE SUPPLIES --------
            CategoryDefinition(
                name="Office Supplies",
                aliases=["Supplies", "Stationery", "Office"],
                enrichment_rules=EnrichmentRules(
                    vendor_keywords=[
                        "staples",
                        "office",
                        "supplies",
                        "stationery",
                        "depot",
                        "amazon",
                        "paperworld",
                    ]
                ),
                validation_rules=ValidationRules(
                    max_amount=100.0,
                    currency="CHF",
                    requires_receipt=False,  # Small supplies don't need receipt
                    max_age_days=60,
                ),
            ),
            # -------- CLIENT ENTERTAINMENT --------
            CategoryDefinition(
                name="Client Entertainment",
                aliases=["Entertainment", "Client Meals", "Business Dinner"],
                enrichment_rules=EnrichmentRules(
                    vendor_keywords=[]  # Usually needs manual categorization
                ),
                validation_rules=ValidationRules(
                    max_amount=300.0,
                    currency="CHF",
                    requires_receipt=True,
                    requires_attendees=True,  # MUST list client names
                    max_age_days=90,
                ),
            ),
            # -------- PARKING --------
            CategoryDefinition(
                name="Parking",
                aliases=["Parking Fee", "Garage"],
                enrichment_rules=EnrichmentRules(
                    vendor_keywords=["parking", "garage", "parkhaus"]
                ),
                validation_rules=ValidationRules(
                    max_amount=30.0,
                    currency="CHF",
                    requires_receipt=False,
                    max_age_days=90,
                ),
            ),
        ],
    ),
    # Can add more companies here
    "demo_company": PolicyData(
        company_id="demo_company",
        effective_date="2025-01-01",
        default_category="Uncategorized",
        categories=[
            CategoryDefinition(
                name="Food",  # Different name than "Meals"
                aliases=["Meals"],
                enrichment_rules=EnrichmentRules(
                    vendor_keywords=["restaurant", "cafe"]
                ),
                validation_rules=ValidationRules(
                    max_amount=75.0,  # Different limit
                    currency="CHF",
                    requires_receipt=True,
                ),
            )
        ],
    ),
}

# ============================================================================
# IN-MEMORY CACHE
# Phase 2: Replace with DynamoDB or Redis
# ============================================================================

policy_cache: Dict[str, tuple[PolicyData, float]] = {}


def get_policy(company_id: str) -> PolicyData:
    """
    Get policy from cache or fetch from store

    Phase 1: Fetches from MOCK_POLICIES dict
    Phase 2: Will call Confluence API

    Args:
        company_id: Company identifier (e.g., "hashgraph_inc")

    Returns:
        PolicyData object with all categories and rules
    """
    cache_key = f"policy_{company_id}"

    # Check cache first
    if cache_key in policy_cache:
        cached_data, timestamp = policy_cache[cache_key]
        # Check if cache is still valid (24 hours = 86400 seconds)
        if time.time() - timestamp < 86400:
            print(f"[CACHE HIT] Using cached policy for {company_id}")
            return cached_data

    print(f"[CACHE MISS] Fetching policy for {company_id}")

    # Fetch from mock store (Phase 1)
    # In Phase 2: Replace with Confluence API call
    if company_id not in MOCK_POLICIES:
        print(f"[WARNING] Company {company_id} not found, using default")
        company_id = "hashgraph_inc"

    policy_data = MOCK_POLICIES[company_id]

    # Cache it with current timestamp
    policy_cache[cache_key] = (policy_data, time.time())

    return policy_data


def invalidate_cache(company_id: Optional[str] = None):
    """
    Manually invalidate policy cache

    Useful for:
    - Testing policy changes
    - Manual refresh after Confluence updates
    - Debugging

    Args:
        company_id: Specific company to invalidate, or None for all
    """
    if company_id:
        cache_key = f"policy_{company_id}"
        if cache_key in policy_cache:
            del policy_cache[cache_key]
            print(f"[CACHE] Invalidated cache for {company_id}")
    else:
        # Clear entire cache
        policy_cache.clear()
        print(f"[CACHE] Cleared all policy cache")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def find_category_by_name(
    policy: PolicyData, category_name: str
) -> Optional[CategoryDefinition]:
    """
    Find category definition by name or alias (case-insensitive)

    Args:
        policy: PolicyData object
        category_name: Category name to search for

    Returns:
        CategoryDefinition if found, None otherwise
    """
    category_lower = category_name.lower().strip()

    for cat in policy.categories:
        # Check main name
        if cat.name.lower() == category_lower:
            return cat

        # Check aliases
        if any(alias.lower() == category_lower for alias in cat.aliases):
            return cat

    return None


def matches_time_rule(time_str: str, time_rule: Dict[str, Any]) -> bool:
    """
    Check if invoice time matches a time-based enrichment rule

    Args:
        time_str: Time string from invoice (e.g., "19:30", "14:25")
        time_rule: Rule dict with start_hour and end_hour

    Returns:
        True if time falls within rule's hour range
    """
    try:
        # Extract hour from time string (handles "HH:MM" format)
        hour = int(time_str.split(":")[0])

        # Check if hour falls within rule range (inclusive)
        return time_rule["start_hour"] <= hour <= time_rule["end_hour"]
    except:
        return False


def matches_vendor_keywords(vendor: str, keywords: List[str]) -> bool:
    """
    Check if vendor name contains any of the policy keywords (case-insensitive)

    Args:
        vendor: Vendor name from invoice
        keywords: List of keywords from policy

    Returns:
        True if any keyword found in vendor name
    """
    if not vendor:
        return False

    vendor_lower = vendor.lower()
    return any(keyword.lower() in vendor_lower for keyword in keywords)


def get_all_categories(company_id: str) -> List[str]:
    """
    Get list of all category names for a company

    Useful for dropdown menus or validation
    """
    policy = get_policy(company_id)
    return [cat.name for cat in policy.categories]


def get_category_max_amount(company_id: str, category_name: str) -> Optional[float]:
    """
    Quick lookup for max amount of a specific category
    """
    policy = get_policy(company_id)
    cat = find_category_by_name(policy, category_name)
    return cat.validation_rules.max_amount if cat else None
