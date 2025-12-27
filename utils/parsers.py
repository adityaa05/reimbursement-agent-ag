import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from models.schemas import PolicyCategory, ValidationRules, EnrichmentRules
from utils.logger import logger


def parse_policy_html(html_content: str) -> List[PolicyCategory]:
    """
    Legacy parser for the main policy page (Limits, Rules).
    Expects tables defining category rules.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    categories = []

    # Locate the policy table
    table = soup.find("table")
    if not table:
        logger.warning("No policy table found in HTML.")
        return []

    rows = table.find_all("tr")
    # Skip header row
    for row in rows[1:]:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        cat_name = cols[0].get_text(strip=True)
        limit_str = cols[1].get_text(strip=True)
        currency = cols[2].get_text(strip=True) or "CHF"
        receipt_req = cols[3].get_text(strip=True).lower() == "yes"

        # Parse Max Amount
        try:
            max_amt = float(re.sub(r"[^\d.]", "", limit_str))
        except ValueError:
            max_amt = 0.0

        categories.append(
            PolicyCategory(
                name=cat_name,
                aliases=[cat_name.lower()],
                enrichment_rules=EnrichmentRules(vendor_keywords=[]),
                validation_rules=ValidationRules(
                    max_amount=max_amt, currency=currency, requires_receipt=receipt_req
                ),
            )
        )

    return categories


def parse_keyword_master_list(
    html_content: str, existing_categories: List[PolicyCategory]
) -> List[PolicyCategory]:
    """
    NEW: Parses the 'Vendor Keywords Master List' page.
    Matches the format: Header (Category) -> Paragraph (Comma-separated keywords).
    """
    soup = BeautifulSoup(html_content, "html.parser")

    # Map your Confluence headers to your System Category Names
    # Update this map if your headers change!
    HEADER_MAP = {
        "Meals / Food & Beverage": "Meals",
        "Accommodation / Hotels": "Accommodation",
        "Travel / Transportation": "Public Transport",  # Covers Train/Bus
        "Parking": "Parking",
        "Office Supplies / Equipment": "Office Supplies",
        "Client Entertainment": "Client Entertainment",
    }

    # We loop through all standard headers (h1-h6) looking for category sections
    current_category = None

    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p"]):
        text = element.get_text(strip=True)

        # 1. Is this a Category Header?
        if element.name.startswith("h"):
            # Check if this header matches one of our known categories
            for key, sys_cat in HEADER_MAP.items():
                if key.lower() in text.lower():
                    current_category = sys_cat
                    break

        # 2. Is this a Keyword Block? (Paragraph under a header)
        elif element.name == "p" and current_category:
            # Split by comma, clean whitespace, ignore empty strings
            raw_keywords = [k.strip().lower() for k in text.split(",") if k.strip()]

            # Find the category object in our list and update it
            for cat in existing_categories:
                if cat.name == current_category:
                    if not cat.enrichment_rules.vendor_keywords:
                        cat.enrichment_rules.vendor_keywords = []

                    # Add new keywords (avoid duplicates)
                    new_kws = [
                        k
                        for k in raw_keywords
                        if k not in cat.enrichment_rules.vendor_keywords
                    ]
                    cat.enrichment_rules.vendor_keywords.extend(new_kws)

                    logger.info(
                        f"Added {len(new_kws)} keywords to '{current_category}'"
                    )

    return existing_categories
