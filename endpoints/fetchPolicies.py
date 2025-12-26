import time
from typing import Optional
from fastapi import APIRouter, HTTPException

from models.schemas import PolicyFetchRequest, PolicyData
from endpoints.policyStore import get_policy, invalidate_cache, get_all_categories

router = APIRouter()


@router.post("/fetch-policies")
async def fetch_policies(request: PolicyFetchRequest) -> PolicyData:
    """Fetch company policies from policy store with optional category filtering."""
    try:
        policy_data = get_policy(request.company_id)

        if request.categories:
            filtered_categories = [
                cat
                for cat in policy_data.categories
                if cat.name in request.categories
                or any(alias in request.categories for alias in cat.aliases)
            ]

            policy_data = PolicyData(
                company_id=policy_data.company_id,
                effective_date=policy_data.effective_date,
                categories=filtered_categories,
                default_category=policy_data.default_category,
                cache_ttl=policy_data.cache_ttl,
            )

        return policy_data

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch policies: {str(e)}"
        )


@router.post("/invalidate-policy-cache")
async def invalidate_policy_cache(company_id: Optional[str] = None):
    """Manually invalidate policy cache."""
    invalidate_cache(company_id)
    return {
        "success": True,
        "message": f"Cache invalidated for {company_id or 'all companies'}",
        "timestamp": time.time(),
    }


@router.get("/list-categories")
async def list_categories(company_id: str = "hashgraph_inc"):
    """Get list of all available categories for a company."""
    try:
        categories = get_all_categories(company_id)
        return {
            "company_id": company_id,
            "categories": categories,
            "count": len(categories),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list categories: {str(e)}"
        )
