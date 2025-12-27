from utils.confluence_client import ConfluenceClient
from atlassian import Confluence

from config import (
    CONFLUENCE_URL,
    CONFLUENCE_USERNAME,
    CONFLUENCE_API_TOKEN,
    CONFLUENCE_SPACE_KEY,
)


def list_all_pages():
    print(f"Connecting to Confluence: {CONFLUENCE_URL}")
    print(f"Space Key: {CONFLUENCE_SPACE_KEY}")
    
    # Your custom client doesn't take parameters
    client = ConfluenceClient()
    
    # Use the atlassian library directly for listing pages
    confluence = Confluence(
        url=CONFLUENCE_URL,
        username=CONFLUENCE_USERNAME,
        password=CONFLUENCE_API_TOKEN
    )
    
    # Fetch all pages in the space
    try:
        pages = confluence.get_all_pages_from_space(
            space=CONFLUENCE_SPACE_KEY, start=0, limit=50
        )
        
        print("\n✅ Found the following pages:")
        print("------------------------------------------------")
        for p in pages:
            print(f"• \"{p['title']}\" (ID: {p['id']})")
        print("------------------------------------------------")
    except Exception as e:
        print(f"\n❌ Error fetching pages: {e}")


if __name__ == "__main__":
    list_all_pages()
