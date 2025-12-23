"""
Confluence API Client for THG Policy Retrieval
Replaces mock policy store with real Confluence integration
"""

import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
import json
import re
from bs4 import BeautifulSoup

load_dotenv()


class ConfluenceClient:
    """Client for fetching policy data from Confluence"""

    def __init__(self):
        self.base_url = os.getenv("CONFLUENCE_URL")
        self.username = os.getenv("CONFLUENCE_USERNAME")
        self.api_token = os.getenv("CONFLUENCE_API_TOKEN")
        self.space_key = os.getenv("CONFLUENCE_SPACE_KEY", "THG")
        self.auth = HTTPBasicAuth(self.username, self.api_token)

    def _make_request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to Confluence API"""
        url = f"{self.base_url}/rest/api/{endpoint}"
        response = requests.get(url, auth=self.auth, params=params)
        response.raise_for_status()
        return response.json()

    def get_page_by_title(self, title: str) -> Optional[Dict]:
        """Get page by title in space"""
        params = {
            "spaceKey": self.space_key,
            "title": title,
            "expand": "body.storage,metadata.labels",
        }
        result = self._make_request("content", params)

        if result.get("results"):
            return result["results"][0]
        return None

    def get_page_by_id(self, page_id: str) -> Dict:
        """Get page by ID with full content"""
        return self._make_request(
            f"content/{page_id}", {"expand": "body.storage,metadata.labels"}
        )

    def search_pages_by_label(self, label: str) -> List[Dict]:
        """Search pages by label"""
        cql = f'space = {self.space_key} AND label = "{label}"'
        params = {
            "cql": cql,
            "expand": "body.storage,metadata.labels",
            "limit": 100,
        }
        result = self._make_request("content/search", params)
        return result.get("results", [])

    def parse_policy_table(self, html_content: str) -> List[Dict[str, Any]]:
        """
        Parse policy table from Confluence HTML

        Expected format:
        | Category | Aliases | Max Amount | Currency | ... |
        """
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")

        for table in tables:
            headers = [
                th.get_text(strip=True) for th in table.find("tr").find_all("th")
            ]

            # Check if this is the policy table
            if "Category" in headers and "Max Amount" in headers:
                rows = []
                for tr in table.find_all("tr")[1:]:  # Skip header
                    cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                    row_dict = dict(zip(headers, cells))
                    rows.append(row_dict)
                return rows

        return []

    def extract_json_from_page(
        self, html_content: str, json_key: str = "Validation Logic"
    ) -> Optional[Dict]:
        """Extract JSON code blocks from page"""
        soup = BeautifulSoup(html_content, "html.parser")

        # Find JSON code blocks
        code_blocks = soup.find_all("code", class_="language-json")

        for block in code_blocks:
            try:
                return json.loads(block.get_text())
            except json.JSONDecodeError:
                continue

        return None

    def get_policy_index(self) -> List[Dict[str, Any]]:
        """
        Fetch Policy API Index page and parse table

        Returns list of category definitions
        """
        page = self.get_page_by_title("Policy API Index - Machine Readable")

        if not page:
            raise Exception("Policy API Index page not found in Confluence")

        html_content = page["body"]["storage"]["value"]
        policies = self.parse_policy_table(html_content)

        print(f"[CONFLUENCE] Loaded {len(policies)} policy categories from index")
        return policies

    def get_category_details(self, category_name: str) -> Dict[str, Any]:
        """
        Fetch detailed policy page for a category

        Returns enrichment rules, validation rules, etc.
        """
        # Try to find page by exact title
        page_title = f"{category_name} Policy"
        page = self.get_page_by_title(page_title)

        if not page:
            raise Exception(f"Policy page '{page_title}' not found")

        html_content = page["body"]["storage"]["value"]
        soup = BeautifulSoup(html_content, "html.parser")

        # Extract validation logic JSON
        validation_rules = self.extract_json_from_page(html_content, "Validation Logic")

        # Extract vendor keywords from table or list
        vendor_keywords = self._extract_vendor_keywords(soup)

        # Extract time-based rules from table
        time_based_rules = self._extract_time_rules(soup)

        # Extract aliases from metadata
        aliases = self._extract_aliases(soup)

        return {
            "name": category_name,
            "aliases": aliases,
            "validation_rules": validation_rules or {},
            "enrichment_rules": {
                "vendor_keywords": vendor_keywords,
                "time_based": time_based_rules,
            },
        }

    def _extract_vendor_keywords(self, soup: BeautifulSoup) -> List[str]:
        """Extract vendor keywords from page content"""
        keywords = []

        # Look for section with heading containing "Vendor Keywords"
        for heading in soup.find_all(["h2", "h3", "h4"]):
            if "Vendor Keywords" in heading.get_text():
                # Get next sibling (paragraph or list)
                next_elem = heading.find_next_sibling()
                if next_elem:
                    text = next_elem.get_text()
                    # Split by comma or newline
                    keywords = [
                        k.strip() for k in re.split(r"[,\n]", text) if k.strip()
                    ]
                break

        return keywords

    def _extract_time_rules(self, soup: BeautifulSoup) -> List[Dict]:
        """Extract time-based classification rules from table"""
        rules = []

        # Look for table with "Time Range" column
        for table in soup.find_all("table"):
            headers = [
                th.get_text(strip=True) for th in table.find("tr").find_all("th")
            ]

            if "Time Range" in headers and "Subcategory" in headers:
                for tr in table.find_all("tr")[1:]:
                    cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(cells) >= 2:
                        time_range = cells[0]  # e.g., "07:00 - 10:00"
                        subcategory = cells[1]  # e.g., "Breakfast"

                        # Parse time range
                        match = re.search(
                            r"(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})", time_range
                        )
                        if match:
                            start_hour = int(match.group(1))
                            end_hour = int(match.group(3))

                            rules.append(
                                {
                                    "start_hour": start_hour,
                                    "end_hour": end_hour,
                                    "subcategory": subcategory,
                                }
                            )
                break

        return rules

    def _extract_aliases(self, soup: BeautifulSoup) -> List[str]:
        """Extract category aliases from page"""
        aliases = []

        # Look for "Aliases:" line
        for p in soup.find_all("p"):
            text = p.get_text()
            if "Aliases:" in text:
                # Extract aliases after colon
                match = re.search(r"Aliases:\s*(.+)", text)
                if match:
                    aliases_str = match.group(1)
                    aliases = [a.strip() for a in aliases_str.split(",")]
                break

        return aliases


# Singleton instance
_client = None


def get_confluence_client() -> ConfluenceClient:
    """Get or create Confluence client singleton"""
    global _client
    if _client is None:
        _client = ConfluenceClient()
    return _client
