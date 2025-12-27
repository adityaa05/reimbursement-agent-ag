import time
from typing import Optional
from fastapi import APIRouter, HTTPException

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

# Name of your Keyword Page
KEYWORD_PAGE_TITLE = "Vendor Keywords Master List"
MAIN_POLICY_TITLE = "Travel & Expense Policy"


def get_policy_from_confluence(company_id: str) -> Optional[PolicyData]:
    """
    Fetches Policy Rules AND Vendor Keywords from separate Confluence pages.
    """
    client = ConfluenceClient(
        url=CONFLUENCE_URL, username=CONFLUENCE_USERNAME, api_token=CONFLUENCE_API_TOKEN
    )

    try:
        # 1. Fetch Main Policy (Rules & Limits)
        main_page = client.get_page_content(
            space_key=CONFLUENCE_SPACE_KEY, title=MAIN_POLICY_TITLE
        )

        if main_page:
            categories = parse_policy_html(main_page)
            logger.info(f"Parsed {len(categories)} categories from Main Policy.")
        else:
            logger.warning(
                f"Main Policy '{MAIN_POLICY_TITLE}' not found. Using empty structure."
            )
            categories = [
                # Initialize default categories so we have buckets for keywords
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
                    name="Other",
                    aliases=[],
                    enrichment_rules=EnrichmentRules(),
                    validation_rules=ValidationRules(max_amount=50.0),
                ),
            ]

        # 2. Fetch Keyword Master List (Enrichment)
        keyword_page = client.get_page_content(
            space_key=CONFLUENCE_SPACE_KEY, title=KEYWORD_PAGE_TITLE
        )

        if keyword_page:
            logger.info(f"Fetching Keywords from '{KEYWORD_PAGE_TITLE}'...")
            categories = parse_keyword_master_list(keyword_page, categories)
        else:
            logger.error(f"Keyword Page '{KEYWORD_PAGE_TITLE}' not found!")

        return PolicyData(
            company_id=company_id,
            effective_date=time.strftime("%Y-%m-%d"),
            categories=categories,
        )

    except Exception as e:
        logger.error(f"Failed to fetch policy: {str(e)}")
        return None
