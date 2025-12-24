"""
Pytest configuration for Confluence integration tests
"""

import pytest
import os
from dotenv import load_dotenv
from endpoints.policyStore import invalidate_cache

# Load environment at module level
load_dotenv()


@pytest.fixture(scope="session", autouse=True)
def verify_confluence_config():
    """Verify Confluence credentials are configured"""
    required_vars = [
        "CONFLUENCE_URL",
        "CONFLUENCE_USERNAME",
        "CONFLUENCE_API_TOKEN",
        "CONFLUENCE_SPACE_KEY",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        pytest.fail(
            f"\n❌ Missing Confluence environment variables: {', '.join(missing)}\n"
            f"Please set them in your .env file or environment"
        )

    print(f"\n✓ Confluence configured:")
    print(f"  URL: {os.getenv('CONFLUENCE_URL')}")
    print(f"  Space: {os.getenv('CONFLUENCE_SPACE_KEY')}")
    print(f"  Username: {os.getenv('CONFLUENCE_USERNAME')}")


@pytest.fixture(autouse=True)
def clear_policy_cache():
    """Clear policy cache before each test to force fresh Confluence fetch"""
    invalidate_cache()
    yield


@pytest.fixture(scope="session")
def confluence_client():
    """Get Confluence client instance for testing"""
    from utils.confluence_client import get_confluence_client

    return get_confluence_client()
