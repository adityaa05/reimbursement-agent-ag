"""import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

load_dotenv()

# Test basic connectivity
url = f"{os.getenv('CONFLUENCE_URL')}/rest/api/content"
auth = HTTPBasicAuth(
    os.getenv("CONFLUENCE_USERNAME"), os.getenv("CONFLUENCE_API_TOKEN")
)

params = {"spaceKey": "THG", "type": "page", "expand": "body.storage", "limit": 25}

response = requests.get(url, auth=auth, params=params)
print(f"Status Code: {response.status_code}")

if response.status_code == 200:
    data = response.json()
    print(f"Successfully connected to Confluence")
    print(f"Found {len(data['results'])} pages in THG space")

    for page in data["results"]:
        print(f"  - {page['title']} (ID: {page['id']})")
else:
    print(f"Connection failed: {response.text}")
"""

"""
Test Confluence integration
"""

import os
from dotenv import load_dotenv
from utils.confluence_client import get_confluence_client
from endpoints.policyStore import get_policy, invalidate_cache

load_dotenv()


def test_confluence_connection():
    """Test basic Confluence connectivity"""
    print("=" * 60)
    print("TEST 1: Confluence Connection")
    print("=" * 60)

    client = get_confluence_client()

    # Test getting policy index
    try:
        index = client.get_policy_index()
        print(f"Successfully fetched policy index")
        print(f"Found {len(index)} categories:")
        for policy in index:
            print(
                f"  - {policy.get('Category')}: {policy.get('Max Amount')} {policy.get('Currency')}"
            )
    except Exception as e:
        print(f"Failed to fetch policy index: {e}")


def test_category_details():
    """Test fetching detailed category pages"""
    print("\n" + "=" * 60)
    print("TEST 2: Category Details")
    print("=" * 60)

    client = get_confluence_client()

    categories_to_test = ["Meals", "Accommodation", "Travel"]

    for category in categories_to_test:
        try:
            details = client.get_category_details(category)
            print(f"\n{category} Policy:")
            print(f"  Aliases: {details.get('aliases')}")
            print(
                f"  Vendor Keywords: {len(details.get('enrichment_rules', {}).get('vendor_keywords', []))} keywords"
            )
            print(
                f"  Time Rules: {len(details.get('enrichment_rules', {}).get('time_based', []))} rules"
            )
            print(
                f"  Max Amount: {details.get('validation_rules', {}).get('max_amount')} CHF"
            )
        except Exception as e:
            print(f"Failed to fetch {category}: {e}")


def test_policy_store_integration():
    """Test full policy store integration"""
    print("\n" + "=" * 60)
    print("TEST 3: Policy Store Integration")
    print("=" * 60)

    # Clear cache to force fresh fetch
    invalidate_cache("hashgraph_inc")

    try:
        policy_data = get_policy("hashgraph_inc")

        print(f"Successfully loaded policy data")
        print(f"Company: {policy_data.company_id}")
        print(f"Effective Date: {policy_data.effective_date}")
        print(f"Categories: {len(policy_data.categories)}")

        for cat in policy_data.categories:
            print(f"\n    {cat.name}")
            print(f"     Max Amount: {cat.validation_rules.max_amount} CHF")
            print(f"     Receipt Required: {cat.validation_rules.requires_receipt}")
            print(f"     Attendees Required: {cat.validation_rules.requires_attendees}")
            print(
                f"     Aliases: {', '.join(cat.aliases[:3])}{'...' if len(cat.aliases) > 3 else ''}"
            )

    except Exception as e:
        print(f"Failed to load policy: {e}")


if __name__ == "__main__":
    print("\nCONFLUENCE INTEGRATION TEST SUITE\n")

    # Check environment
    if not os.getenv("CONFLUENCE_URL"):
        print("ERROR: CONFLUENCE_URL not set in .env file")
        print("Please complete Confluence setup first!")
        exit(1)

    test_confluence_connection()
    test_category_details()
    test_policy_store_integration()

    print("\n" + "=" * 60)
    print("All tests complete!")
    print("=" * 60)
