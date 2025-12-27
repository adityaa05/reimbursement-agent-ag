import time
from typing import Optional
from fastapi import APIRouter

from utils.confluence_client import ConfluenceClient
from utils.parsers import parse_policy_html, parse_keyword_master_list
from utils.logger import logger
from models.schemas import PolicyData, PolicyCategory, ValidationRules, EnrichmentRules
from config import (
    CONFLUENCE_URL,
    CONFLUENCE_USERNAME,
    CONFLUENCE_API_TOKEN,
    CONFLUENCE_SPACE_KEY,
)

router = APIRouter()

# UPDATED: Exact Titles from your diagnostic script
KEYWORD_PAGE_TITLE = "Vendor Keywords Master List"
MAIN_POLICY_TITLE = "Policy API Index - Machine Readable"


def get_policy_from_confluence(company_id: str) -> Optional[PolicyData]:
    """
    Fetches Policy Rules AND Vendor Keywords independently.
    """
    client = ConfluenceClient(
        url=CONFLUENCE_URL, username=CONFLUENCE_USERNAME, api_token=CONFLUENCE_API_TOKEN
    )

    categories = []

    # --- ATTEMPT 1: Fetch Main Policy (Rules) ---
    try:
        logger.info(f"Attempting to fetch Main Policy: '{MAIN_POLICY_TITLE}'")
        main_page = client.get_page_content(
            space_key=CONFLUENCE_SPACE_KEY, title=MAIN_POLICY_TITLE
        )

        if main_page:
            categories = parse_policy_html(main_page)
            logger.info(f"Parsed {len(categories)} categories from Main Policy.")
        else:
            logger.warning(f"Main Policy '{MAIN_POLICY_TITLE}' returned empty content.")

    except Exception as e:
        logger.warning(
            f"Could not fetch Main Policy '{MAIN_POLICY_TITLE}'. Continuing... Error: {e}"
        )

    # Fallback buckets if Main Policy failed
    if not categories:
        logger.info(
            "Initializing default category buckets (Main Policy was missing/failed)."
        )
        categories = [
            PolicyCategory(
                name="Meals",
                aliases=[],
                enrichment_rules=EnrichmentRules(),
                validation_rules=ValidationRules(max_amount=50.0),
            ),
            PolicyCategory(
                name="Accommodation",
                aliases=[],
                enrichment_rules=EnrichmentRules(),
                validation_rules=ValidationRules(max_amount=200.0),
            ),
            PolicyCategory(
                name="Public Transport",
                aliases=[],
                enrichment_rules=EnrichmentRules(),
                validation_rules=ValidationRules(max_amount=100.0),
            ),
            PolicyCategory(
                name="Parking",
                aliases=[],
                enrichment_rules=EnrichmentRules(),
                validation_rules=ValidationRules(max_amount=50.0),
            ),
            PolicyCategory(
                name="Client Entertainment",
                aliases=[],
                enrichment_rules=EnrichmentRules(),
                validation_rules=ValidationRules(max_amount=100.0),
            ),
            PolicyCategory(
                name="Office Supplies",
                aliases=[],
                enrichment_rules=EnrichmentRules(),
                validation_rules=ValidationRules(max_amount=50.0),
            ),
            PolicyCategory(
                name="Other",
                aliases=[],
                enrichment_rules=EnrichmentRules(),
                validation_rules=ValidationRules(max_amount=50.0),
            ),
        ]

    # --- ATTEMPT 2: Fetch Keyword List (Enrichment) ---
    try:
        logger.info(f"Attempting to fetch Keyword List: '{KEYWORD_PAGE_TITLE}'")
        keyword_page = client.get_page_content(
            space_key=CONFLUENCE_SPACE_KEY, title=KEYWORD_PAGE_TITLE
        )

        if keyword_page:
            categories = parse_keyword_master_list(keyword_page, categories)
            logger.info(
                f"Successfully enriched categories with keywords from '{KEYWORD_PAGE_TITLE}'."
            )
        else:
            logger.error(f"Keyword Page '{KEYWORD_PAGE_TITLE}' returned empty content.")

    except Exception as e:
        logger.error(f"Could not fetch Keyword Page '{KEYWORD_PAGE_TITLE}'. Error: {e}")

    return PolicyData(
        company_id=company_id,
        effective_date=time.strftime("%Y-%m-%d"),
        categories=categories,
    )
