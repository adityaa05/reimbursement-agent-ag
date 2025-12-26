import time
import re
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException

from models.schemas import (
    PolicyData,
    PolicyCategory,
    EnrichmentRules,
    ValidationRules,
    PolicyFetchRequest,
)
from utils.confluence_client import ConfluenceClient
from utils.logger import logger
from config import CONFLUENCE_SPACE_KEY, CONFLUENCE_POLICY_PAGE_TITLE

router = APIRouter()

# In-memory cache
_policy_cache: Dict[str, PolicyData] = {}
_last_fetch_time: Dict[str, float] = {}
CACHE_TTL = 3600  # 1 hour

# --- FALLBACK POLICY (Safety Net) ---
# Used if Confluence is unreachable. Matches your V1.1 Policy + Simplified Meals logic.
DEFAULT_FALLBACK_POLICY = PolicyData(
    company_id="hashgraph_inc",
    effective_date="2024-01-01",
    categories=[
        PolicyCategory(
            name="Meals",
            aliases=[
                "Lunch",
                "Dinner",
                "Breakfast",
                "Food",
                "Restaurant",
                "Cafe",
                "Snacks",
            ],
            enrichment_rules=EnrichmentRules(
                vendor_keywords=["restaurant", "cafe", "food", "dinner", "lunch"]
            ),
            validation_rules=ValidationRules(
                max_amount=50.0, currency="CHF", requires_receipt=True
            ),
        ),
        PolicyCategory(
            name="Accommodation",
            aliases=["Hotel", "Airbnb", "Lodging", "Resort", "Motel"],
            enrichment_rules=EnrichmentRules(
                vendor_keywords=["hotel", "airbnb", "lodging"]
            ),
            validation_rules=ValidationRules(
                max_amount=200.0, currency="CHF", requires_receipt=True
            ),
        ),
        PolicyCategory(
            name="Client Entertainment",
            aliases=["Business Dinner", "Client Lunch", "Hosting", "Representation"],
            enrichment_rules=EnrichmentRules(vendor_keywords=["client", "hosting"]),
            validation_rules=ValidationRules(
                max_amount=300.0,
                currency="CHF",
                requires_receipt=True,
                requires_attendees=True,
            ),
        ),
        PolicyCategory(
            name="Public Transport",
            aliases=["Train", "Bus", "Tram", "SBB", "Taxi", "Uber", "Flight"],
            enrichment_rules=EnrichmentRules(
                vendor_keywords=["uber", "sbb", "train", "taxi"]
            ),
            validation_rules=ValidationRules(
                max_amount=150.0, currency="CHF", requires_receipt=True
            ),
        ),
        PolicyCategory(
            name="Parking",
            aliases=["Garage", "Parking Lot", "Valet"],
            enrichment_rules=EnrichmentRules(vendor_keywords=["parking", "garage"]),
            validation_rules=ValidationRules(
                max_amount=30.0, currency="CHF", requires_receipt=False
            ),
        ),
        PolicyCategory(
            name="Mileage",
            aliases=["Personal Car", "Private Vehicle", "Gas"],
            enrichment_rules=EnrichmentRules(vendor_keywords=["mileage", "gas"]),
            validation_rules=ValidationRules(
                max_amount=500.0, currency="CHF", requires_receipt=False
            ),
        ),
        PolicyCategory(
            name="Gifts",
            aliases=["Host Gift", "Stay with Friends", "Flowers"],
            enrichment_rules=EnrichmentRules(vendor_keywords=["gift", "flower"]),
            validation_rules=ValidationRules(
                max_amount=60.0, currency="CHF", requires_receipt=True
            ),
        ),
    ],
)


def parse_currency(amount_str: str) -> float:
    """Helper to parse currency strings like '50 CHF' or '$50.00'."""
    if not amount_str:
        return 0.0
    # Remove non-numeric chars except dot
    clean_str = re.sub(r"[^\d.]", "", str(amount_str))
    try:
        return float(clean_str)
    except ValueError:
        return 0.0


def parse_bool(bool_str: str) -> bool:
    """Helper to parse boolean strings."""
    return str(bool_str).lower() in ("yes", "true", "1", "required")


def fetch_policy_from_confluence(company_id: str) -> PolicyData:
    """
    Fetches the policy table from Confluence and converts it to PolicyData.
    """
    logger.info(f"Fetching policy from Confluence for {company_id}")
    client = ConfluenceClient()

    try:
        # 1. Search for the page
        page = client.get_page_by_title(
            CONFLUENCE_SPACE_KEY, CONFLUENCE_POLICY_PAGE_TITLE
        )
        if not page:
            logger.error(f"Policy page '{CONFLUENCE_POLICY_PAGE_TITLE}' not found.")
            raise Exception("Page not found")

        # 2. Get table data
        table_data = client.get_table_data(page["id"])
        if not table_data:
            logger.warning("No table found in policy page.")
            return DEFAULT_FALLBACK_POLICY

        # 3. Map Table Rows to PolicyCategory objects
        categories = []
        for row in table_data:
            # Robust retrieval using normalized keys if possible
            cat_name = row.get("Category", "Unknown")
            aliases_str = row.get("Aliases", "")
            max_amt_str = row.get("Max Amount", "0")
            currency = row.get("Currency", "CHF")
            receipt_req = row.get("Receipt Required", "Yes")
            attendees_req = row.get("Attendees Required", "No")
            max_age_str = row.get("Max Age Days", "90")

            # Create Aliases List
            aliases = [a.strip() for a in aliases_str.split(",") if a.strip()]

            # Build Rules
            validation_rules = ValidationRules(
                max_amount=parse_currency(max_amt_str),
                currency=currency,
                requires_receipt=parse_bool(receipt_req),
                requires_attendees=parse_bool(attendees_req),
                max_age_days=int(parse_currency(max_age_str)),
                approved_vendors=[],
            )

            enrichment_rules = EnrichmentRules(vendor_keywords=aliases, time_based=[])

            cat_obj = PolicyCategory(
                name=cat_name,
                aliases=aliases,
                enrichment_rules=enrichment_rules,
                validation_rules=validation_rules,
            )
            categories.append(cat_obj)

        return PolicyData(
            company_id=company_id, effective_date="2024-01-01", categories=categories
        )

    except Exception as e:
        logger.error(f"Confluence fetch failed: {e}")
        raise e  # Re-raise to trigger fallback in get_policy


def get_policy(company_id: str = "hashgraph_inc") -> PolicyData:
    """
    Retrieves policy with caching logic and robust fallback.
    """
    now = time.time()

    # 1. Check Cache
    if company_id in _policy_cache:
        if now - _last_fetch_time.get(company_id, 0) < CACHE_TTL:
            return _policy_cache[company_id]

    # 2. Try Fetching Fresh
    try:
        data = fetch_policy_from_confluence(company_id)
        _policy_cache[company_id] = data
        _last_fetch_time[company_id] = now
        return data
    except Exception as e:
        logger.warning(f"Using Fallback Policy due to error: {e}")

        # 3. Fallback: Return Stale Cache OR Hardcoded Default
        if company_id in _policy_cache:
            return _policy_cache[company_id]

        return DEFAULT_FALLBACK_POLICY


@router.post("/fetch-policies")
async def fetch_policies_endpoint(request: PolicyFetchRequest):
    """
    Manually trigger a policy fetch/refresh (useful for testing).
    """
    try:
        # Force refresh by clearing cache for this company
        if request.company_id in _last_fetch_time:
            del _last_fetch_time[request.company_id]

        data = get_policy(request.company_id)

        # Filter if requested
        if request.categories:
            filtered_cats = [c for c in data.categories if c.name in request.categories]
            data.categories = filtered_cats

        return data
    except Exception as e:
        # Even manual fetch returns fallback if everything explodes, to keep API alive
        logger.error(f"Manual fetch exploded: {e}")
        return DEFAULT_FALLBACK_POLICY
