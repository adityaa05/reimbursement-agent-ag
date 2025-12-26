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

policy_cache: Dict[str, tuple[PolicyData, float]] = {}
_last_known_good: Dict[str, PolicyData] = {}


def get_policy(company_id: str, use_fallback: bool = True) -> PolicyData:
    """Get policy from Confluence with fallback strategy."""
    cache_key = f"policy_{company_id}"
    now = time.time()

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

    try:
        logger.info("Fetching policy from Confluence", company_id=company_id)
        client = get_confluence_client()

        index_data = client.get_policy_index()
        categories = []

        for policy_row in index_data:
            category_name = policy_row.get("Category", "").strip()
            if not category_name:
                continue

            try:
                details = client.get_category_details(category_name)
            except Exception as e:
                logger.warning(
                    "Could not load category details",
                    category=category_name,
                    error=str(e),
                )
                continue

            aliases_str = policy_row.get("Aliases", "")
            aliases = [a.strip() for a in aliases_str.split(",")] if aliases_str else []

            if details.get("aliases"):
                aliases.extend(details["aliases"])
            aliases = list(set(aliases))

            validation_rules = ValidationRules(
                max_amount=float(policy_row.get("Max Amount", 0)),
                currency=policy_row.get("Currency", "CHF"),
                requires_receipt=(policy_row.get("Receipt Required", "Yes") == "Yes"),
                requires_attendees=(
                    policy_row.get("Attendees Required", "No") == "Yes"
                ),
                max_age_days=int(policy_row.get("Max Age Days", 90)),
            )

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

            enrichment_rules = EnrichmentRules(
                time_based=details.get("enrichment_rules", {}).get("time_based"),
                vendor_keywords=details.get("enrichment_rules", {}).get(
                    "vendor_keywords"
                ),
            )

            category_def = CategoryDefinition(
                name=category_name,
                aliases=aliases,
                enrichment_rules=enrichment_rules,
                validation_rules=validation_rules,
            )

            categories.append(category_def)

            logger.debug(
                "Loaded policy category",
                category=category_name,
                max_amount=validation_rules.max_amount,
                vendor_keywords_count=len(enrichment_rules.vendor_keywords or []),
                time_rules_count=len(enrichment_rules.time_based or []),
            )

            if enrichment_rules.vendor_keywords:
                logger.debug(
                    f"  Keywords for {category_name}",
                    sample_keywords=enrichment_rules.vendor_keywords[:10],
                    total_count=len(enrichment_rules.vendor_keywords),
                )
            else:
                logger.warning(
                    f"WARNING: No vendor keywords defined for {category_name}",
                    category=category_name,
                )

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
                        max_amount=100.0,
                        currency="CHF",
                        requires_receipt=True,
                        requires_attendees=False,
                        max_age_days=90,
                    ),
                )
            )

        _validate_policy_data(categories)

        policy_data = PolicyData(
            company_id=company_id,
            effective_date="2024-01-01",
            categories=categories,
            default_category="Other",
            cache_ttl=86400,
        )

        policy_cache[cache_key] = (policy_data, now)
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

        if cache_key in policy_cache:
            cached_data, timestamp = policy_cache[cache_key]
            age_hours = (now - timestamp) / 3600

            if age_hours < 168:
                logger.warning(
                    "Using STALE cache - Degraded mode",
                    company_id=company_id,
                    cache_age_hours=round(age_hours, 2),
                    degradation_level="MEDIUM",
                )
                return cached_data

        if use_fallback and cache_key in _last_known_good:
            logger.error(
                "Using LAST-KNOWN-GOOD policy - Critical degradation",
                company_id=company_id,
                degradation_level="CRITICAL",
            )
            return _last_known_good[cache_key]

        logger.warning(
            "Confluence unavailable and no cache - using Config-Based Fallback",
            company_id=company_id,
            degradation_level="SAFE_MODE",
        )
        return _load_fallback_policy_from_config(company_id)


def _validate_policy_data(categories: List[CategoryDefinition]):
    """Validate loaded policy data for completeness."""
    if not categories:
        raise ValueError("Policy must contain at least one category")

    has_vendor_keywords = False

    for cat in categories:
        if not cat.validation_rules:
            logger.warning(f"Category {cat.name} missing validation rules")
            continue

        if cat.validation_rules.max_amount <= 0:
            logger.warning(
                f"Category {cat.name} has invalid max_amount: {cat.validation_rules.max_amount}"
            )

        if cat.enrichment_rules.vendor_keywords:
            has_vendor_keywords = True

            valid_keywords = [
                k for k in cat.enrichment_rules.vendor_keywords if k.strip()
            ]

            if len(valid_keywords) < len(cat.enrichment_rules.vendor_keywords):
                logger.warning(
                    f"Category {cat.name} has empty vendor keywords",
                    total=len(cat.enrichment_rules.vendor_keywords),
                    valid=len(valid_keywords),
                )

        if cat.enrichment_rules.time_based:
            for time_rule in cat.enrichment_rules.time_based:
                if "start_hour" not in time_rule or "end_hour" not in time_rule:
                    logger.warning(
                        f"Category {cat.name} has invalid time rule",
                        rule=time_rule,
                    )

    if not has_vendor_keywords:
        logger.warning(
            "WARNING: NO categories have vendor keywords defined - enrichment will always fail!"
        )


def _load_fallback_policy_from_config(company_id: str) -> PolicyData:
    """Load fallback policy from config file."""
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

        categories = []
        for cat_dict in policy_dict["categories"]:
            enrichment_dict = cat_dict.get("enrichment_rules", {})
            enrichment_rules = EnrichmentRules(
                time_based=enrichment_dict.get("time_based"),
                vendor_keywords=enrichment_dict.get("vendor_keywords"),
            )

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
            cache_ttl=0,
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
    """Manually invalidate policy cache."""
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
    """Find category by name or alias with case-insensitive matching."""
    category_lower = category_name.lower().strip()

    for cat in policy.categories:
        if cat.name.lower() == category_lower:
            return cat
        if any(alias.lower() == category_lower for alias in cat.aliases):
            return cat

    return None


def matches_time_rule(time_str: str, time_rule: Dict[str, Any]) -> bool:
    """Check if time matches rule."""
    try:
        hour = int(time_str.split(":")[0])
        return time_rule["start_hour"] <= hour <= time_rule["end_hour"]
    except:
        return False


def matches_vendor_keywords(vendor: str, keywords: List[str]) -> bool:
    """Check if vendor contains keywords."""
    if not vendor:
        return False
    vendor_lower = vendor.lower()
    return any(keyword.lower() in vendor_lower for keyword in keywords)


def get_all_categories(company_id: str) -> List[str]:
    """Get list of all category names."""
    policy = get_policy(company_id)
    return [cat.name for cat in policy.categories]


def get_category_max_amount(company_id: str, category_name: str) -> Optional[float]:
    """Quick lookup for max amount."""
    policy = get_policy(company_id)
    cat = find_category_by_name(policy, category_name)
    return cat.validation_rules.max_amount if cat else None
