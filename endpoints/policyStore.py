"""
Policy Store - FIXED VERSION
Removed all hardcoded keyword injections and Safe Mode policies

Changes:
1. ❌ REMOVED: Hardcoded keyword augmentation (lines 192-221)
2. ✅ ADDED: Config-based fallback policy
3. ✅ ADDED: Comprehensive debug logging
4. ✅ ADDED: Policy validation on load
"""

import time
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from fastapi import HTTPException
from models.schemas import (
    PolicyData,
    EnrichmentRules,
    ValidationRules,
    CategoryDefinition,
)
from utils.confluence_client import get_confluence_client
from utils.logger import logger

# In-memory cache with timestamps
policy_cache: Dict[str, tuple[PolicyData, float]] = {}

# Last-known-good policy cache (never expires)
_last_known_good: Dict[str, PolicyData] = {}


def get_policy(company_id: str, use_fallback: bool = True) -> PolicyData:
    """
    Get policy from Confluence with fallback strategy.

    Degradation levels:
    1. Fresh data (< 24hrs): Normal operation
    2. Stale cache (24hrs - 7 days): Degraded mode, log warning
    3. Confluence offline + stale cache: Use last-known-good, flag critical
    4. No cache at all: Use config-based fallback policy

    Args:
        company_id: Company identifier
        use_fallback: Whether to use last-known-good fallback

    Returns:
        PolicyData object

    Raises:
        HTTPException: When no policy data is available
    """
    cache_key = f"policy_{company_id}"
    now = time.time()

    # ============================================
    # STEP 1: Check fresh cache (< 24 hours)
    # ============================================
    if cache_key in policy_cache:
        cached_data, timestamp = policy_cache[cache_key]
        age_hours = (now - timestamp) / 3600

        if age_hours < 24:
            logger.info(
                "Policy cache hit (fresh)",
                company_id=company_id,
                cache_age_hours=round(age_hours, 2),
            )
            return cached_data

    # ============================================
    # STEP 2: Try fetching from Confluence
    # ============================================
    try:
        logger.info("Fetching policy from Confluence", company_id=company_id)

        client = get_confluence_client()

        # Step 2a: Get policy index
        index_data = client.get_policy_index()

        # Step 2b: Build category definitions
        categories = []
        for policy_row in index_data:
            category_name = policy_row.get("Category", "").strip()
            if not category_name:
                continue

            # Fetch detailed page for this category
            try:
                details = client.get_category_details(category_name)
            except Exception as e:
                logger.warning(
                    "Could not load category details",
                    category=category_name,
                    error=str(e),
                )
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

            # ========================================================
            # ✅ ADDED: Debug logging for loaded categories
            # ========================================================
            logger.debug(
                "Loaded policy category",
                category=category_name,
                max_amount=validation_rules.max_amount,
                vendor_keywords_count=len(enrichment_rules.vendor_keywords or []),
                time_rules_count=len(enrichment_rules.time_based or []),
            )

            # Detailed keyword logging
            if enrichment_rules.vendor_keywords:
                logger.debug(
                    f"  Keywords for {category_name}",
                    sample_keywords=enrichment_rules.vendor_keywords[:10],
                    total_count=len(enrichment_rules.vendor_keywords),
                )
            else:
                logger.warning(
                    f"⚠️  No vendor keywords defined for {category_name}",
                    category=category_name,
                )

        
        # ========================================================
        # ENSURE "Other" CATEGORY EXISTS (Safe fallback)
        # ========================================================
        if not any(c.name == "Other" for c in categories):
            logger.info("Adding 'Other' fallback category (not in Confluence)")
            categories.append(
                CategoryDefinition(
                    name="Other",
                    aliases=["Miscellaneous", "General", "Uncategorized"],
                    enrichment_rules=EnrichmentRules(
                        vendor_keywords=[], time_based=None
                    ),
                    validation_rules=ValidationRules(
                        max_amount=100.0,  # Conservative default
                        currency="CHF",
                        requires_receipt=True,
                        requires_attendees=False,
                        max_age_days=90,
                    ),
                )
            )


        # ========================================================
        # ✅ VALIDATE POLICY DATA
        # ========================================================
        _validate_policy_data(categories)

        # Build policy data
        policy_data = PolicyData(
            company_id=company_id,
            effective_date="2024-01-01",
            categories=categories,
            default_category="Other",
            cache_ttl=86400,
        )

        # Cache for 24 hours
        policy_cache[cache_key] = (policy_data, now)

        # Also store as last-known-good (never expires)
        _last_known_good[cache_key] = policy_data

        logger.info(
            "Policy fetched from Confluence",
            company_id=company_id,
            categories_count=len(categories),
        )

        return policy_data

    except Exception as confluence_error:
        logger.warning(
            "Confluence fetch failed, attempting fallback",
            company_id=company_id,
            error=str(confluence_error),
        )

        # ============================================
        # FALLBACK STRATEGY
        # ============================================

        # Option 1: Use stale cache (24hrs - 7 days)
        if cache_key in policy_cache:
            cached_data, timestamp = policy_cache[cache_key]
            age_hours = (now - timestamp) / 3600

            if age_hours < 168:  # 7 days
                logger.warning(
                    "Using STALE cache - Degraded mode",
                    company_id=company_id,
                    cache_age_hours=round(age_hours, 2),
                    degradation_level="MEDIUM",
                )
                return cached_data

        # Option 2: Use last-known-good (no expiry)
        if use_fallback and cache_key in _last_known_good:
            logger.error(
                "Using LAST-KNOWN-GOOD policy - Critical degradation",
                company_id=company_id,
                degradation_level="CRITICAL",
            )
            return _last_known_good[cache_key]

        # Option 3: Use CONFIG-BASED FALLBACK (Safe Mode)
        logger.warning(
            "Confluence unavailable and no cache - using Config-Based Fallback",
            company_id=company_id,
            degradation_level="SAFE_MODE",
        )
        return _load_fallback_policy_from_config(company_id)


def _validate_policy_data(categories: List[CategoryDefinition]):
    """
    Validate loaded policy data for completeness

    Checks:
    1. All categories have validation rules
    2. All categories have max_amount > 0
    3. At least one category has vendor keywords
    4. Time rules are properly formatted
    """
    if not categories:
        raise ValueError("Policy must contain at least one category")

    has_vendor_keywords = False

    for cat in categories:
        # Check validation rules
        if not cat.validation_rules:
            logger.warning(f"Category {cat.name} missing validation rules")
            continue

        if cat.validation_rules.max_amount <= 0:
            logger.warning(
                f"Category {cat.name} has invalid max_amount: {cat.validation_rules.max_amount}"
            )

        # Check enrichment rules
        if cat.enrichment_rules.vendor_keywords:
            has_vendor_keywords = True

            # Validate keywords are not empty strings
            valid_keywords = [
                k for k in cat.enrichment_rules.vendor_keywords if k.strip()
            ]
            if len(valid_keywords) < len(cat.enrichment_rules.vendor_keywords):
                logger.warning(
                    f"Category {cat.name} has empty vendor keywords",
                    total=len(cat.enrichment_rules.vendor_keywords),
                    valid=len(valid_keywords),
                )

        # Check time rules format
        if cat.enrichment_rules.time_based:
            for time_rule in cat.enrichment_rules.time_based:
                if "start_hour" not in time_rule or "end_hour" not in time_rule:
                    logger.warning(
                        f"Category {cat.name} has invalid time rule",
                        rule=time_rule,
                    )

    if not has_vendor_keywords:
        logger.warning(
            "⚠️  NO categories have vendor keywords defined - enrichment will always fail!"
        )


def _load_fallback_policy_from_config(company_id: str) -> PolicyData:
    """
    Load fallback policy from config file (NOT hardcoded)

    This replaces the old _get_default_policy() function
    """
    config_path = Path(__file__).parent.parent / "config" / "fallback_policy.json"

    try:
        logger.info("Loading fallback policy from config", path=str(config_path))

        if not config_path.exists():
            logger.error(
                "Fallback policy config file not found",
                path=str(config_path),
            )
            raise FileNotFoundError(
                f"Fallback policy config not found: {config_path}\n"
                f"Create config/fallback_policy.json with policy definitions"
            )

        with open(config_path) as f:
            policy_dict = json.load(f)

        # Parse into PolicyData object
        categories = []
        for cat_dict in policy_dict["categories"]:
            # Parse enrichment rules
            enrichment_dict = cat_dict.get("enrichment_rules", {})
            enrichment_rules = EnrichmentRules(
                time_based=enrichment_dict.get("time_based"),
                vendor_keywords=enrichment_dict.get("vendor_keywords"),
            )

            # Parse validation rules
            validation_dict = cat_dict.get("validation_rules", {})
            validation_rules = ValidationRules(
                max_amount=validation_dict.get("max_amount", 100.0),
                currency=validation_dict.get("currency", "CHF"),
                requires_receipt=validation_dict.get("requires_receipt", True),
                requires_attendees=validation_dict.get("requires_attendees", False),
                max_age_days=validation_dict.get("max_age_days", 90),
            )

            categories.append(
                CategoryDefinition(
                    name=cat_dict["name"],
                    aliases=cat_dict.get("aliases", []),
                    enrichment_rules=enrichment_rules,
                    validation_rules=validation_rules,
                )
            )

        policy_data = PolicyData(
            company_id=company_id,
            effective_date=policy_dict.get("effective_date", "2024-01-01"),
            categories=categories,
            default_category=policy_dict.get("default_category", "Other"),
            cache_ttl=0,  # Do not cache fallback
        )

        logger.info(
            "Fallback policy loaded from config",
            categories_count=len(categories),
        )

        return policy_data

    except FileNotFoundError:
        raise
    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in fallback policy config", error=str(e))
        raise ValueError(f"Invalid JSON in {config_path}: {e}")
    except Exception as e:
        logger.error("Failed to load fallback policy", error=str(e))
        raise


def invalidate_cache(company_id: Optional[str] = None):
    """Manually invalidate policy cache"""
    if company_id:
        cache_key = f"policy_{company_id}"
        if cache_key in policy_cache:
            del policy_cache[cache_key]
            logger.info("Cache invalidated", company_id=company_id)
    else:
        policy_cache.clear()
        logger.info("All policy cache cleared")


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
