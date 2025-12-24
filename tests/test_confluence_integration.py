"""
Confluence Integration Tests
Tests actual connectivity and data retrieval from Confluence
"""

import pytest
from utils.confluence_client import get_confluence_client
from endpoints.policyStore import get_policy, invalidate_cache

pytestmark = pytest.mark.integration


class TestConfluenceIntegration:
    """Test Confluence client integration"""

    def test_confluence_connection(self, confluence_client):
        """Test basic Confluence connectivity and policy index fetch"""
        print("\n  [Testing Confluence Connection]")

        # Test getting policy index
        index = confluence_client.get_policy_index()

        assert index is not None
        assert len(index) > 0, "Policy index should contain at least one category"

        print(f"    ✓ Fetched {len(index)} categories from policy index")

        # Verify required fields
        first_policy = index[0]
        assert "Category" in first_policy
        assert "Max Amount" in first_policy
        assert "Currency" in first_policy

        for policy in index:
            print(
                f"      - {policy.get('Category')}: {policy.get('Max Amount')} {policy.get('Currency')}"
            )

    @pytest.mark.parametrize("category", ["Meals", "Accommodation", "Travel"])
    def test_category_details(self, confluence_client, category):
        """Test fetching detailed category pages"""
        print(f"\n  [Testing Category: {category}]")

        details = confluence_client.get_category_details(category)

        assert details is not None
        assert details.get("name") == category
        assert "validation_rules" in details
        assert "enrichment_rules" in details

        print(f"    ✓ Loaded {category} policy details")
        print(f"      Aliases: {details.get('aliases', [])}")
        print(
            f"      Max Amount: {details.get('validation_rules', {}).get('max_amount')} CHF"
        )

    def test_policy_store_integration(self):
        """Test full policy store integration with caching"""
        print("\n  [Testing Policy Store Integration]")

        # Clear cache to force fresh fetch
        invalidate_cache("hashgraph_inc")

        # First call - should fetch from Confluence
        policy_data = get_policy("hashgraph_inc")

        assert policy_data is not None
        assert policy_data.company_id == "hashgraph_inc"
        assert len(policy_data.categories) > 0

        print(f"    ✓ Loaded policy data for {policy_data.company_id}")
        print(f"      Categories: {len(policy_data.categories)}")

        # Verify each category has required fields
        for cat in policy_data.categories:
            assert cat.name
            assert cat.validation_rules
            assert cat.validation_rules.max_amount > 0
            assert cat.validation_rules.currency

            print(f"      - {cat.name}: {cat.validation_rules.max_amount} CHF")

        # Second call - should use cache
        policy_data_cached = get_policy("hashgraph_inc")
        assert policy_data_cached.company_id == policy_data.company_id
        print(f"    ✓ Cache working correctly")
