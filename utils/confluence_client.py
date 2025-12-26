import os
import requests
from requests.auth import HTTPBasicAuth
import json
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

from config import (
    CONFLUENCE_URL,
    CONFLUENCE_USERNAME,
    CONFLUENCE_API_TOKEN,
    CONFLUENCE_SPACE_KEY,
)
from utils.logger import logger

# REMOVED unused imports from schemas to prevent crash
# If you need specific schemas later, import PolicyCategory, NOT CategoryDefinition


class ConfluenceClient:
    def __init__(self):
        self.base_url = CONFLUENCE_URL
        self.auth = HTTPBasicAuth(CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_page_by_title(self, space_key: str, title: str) -> Optional[Dict[str, Any]]:
        """Fetch page metadata by title."""
        url = f"{self.base_url}/rest/api/content"
        params = {
            "title": title,
            "spaceKey": space_key,
            "expand": "body.storage,version",
        }
        try:
            response = requests.get(
                url, auth=self.auth, headers=self.headers, params=params
            )
            response.raise_for_status()
            data = response.json()
            if data.get("results"):
                return data["results"][0]
            return None
        except Exception as e:
            logger.error(f"Error fetching Confluence page '{title}': {e}")
            return None

    def get_table_data(self, page_id: str) -> List[Dict[str, str]]:
        """
        Parses the first HTML table on a Confluence page into a list of dicts.
        """
        url = f"{self.base_url}/rest/api/content/{page_id}?expand=body.storage"
        try:
            response = requests.get(url, auth=self.auth, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            html_content = data.get("body", {}).get("storage", {}).get("value", "")

            if not html_content:
                return []

            soup = BeautifulSoup(html_content, "html.parser")
            table = soup.find("table")
            if not table:
                return []

            # Extract headers
            headers = []
            header_row = table.find("tr")
            if header_row:
                for th in header_row.find_all(["th", "td"]):  # sometimes headers are td
                    headers.append(th.get_text(strip=True))

            # Extract rows
            results = []
            for tr in table.find_all("tr")[1:]:  # Skip header
                cells = tr.find_all("td")
                if len(cells) != len(headers):
                    continue

                row_data = {}
                for i, cell in enumerate(cells):
                    # Clean up text (remove zero-width spaces etc)
                    text = cell.get_text(strip=True).replace("\u200b", "")
                    row_data[headers[i]] = text
                results.append(row_data)

            return results

        except Exception as e:
            logger.error(f"Error parsing table from page {page_id}: {e}")
            return []
