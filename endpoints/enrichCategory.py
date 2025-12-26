import re
from typing import Optional
from fastapi import APIRouter, HTTPException

from models.schemas import EnrichCategoryRequest, EnrichCategoryResponse
from utils.policy_helpers import matches_vendor_keywords, find_category_by_name
from endpoints.policyStore import get_policy

router = APIRouter()


class EnhancedEnrichCategoryRequest(EnrichCategoryRequest):
    """Enhanced request with total_amount for semantic analysis."""

    total_amount: Optional[float] = None


@router.post("/enrich-category", response_model=EnrichCategoryResponse)
async def enrich_category(request: EnhancedEnrichCategoryRequest):
    """
    Category enrichment using Vendor Keywords ONLY.
    (Time-based rules removed per PRD Constraint: Odoo OCR lacks reliable time data).
    """
    try:
        company_id = request.company_id
        policy_data = get_policy(company_id)

        print(f"\n[ENRICH] ===== Processing Invoice {request.invoice_id} =====")
        print(f"[ENRICH] Vendor: {request.vendor}")
        print(f"[ENRICH] Existing Category: {request.existing_category}")

        # 1. Use User-Provided Category if it exists and is valid
        if request.existing_category:
            category_def = find_category_by_name(policy_data, request.existing_category)
            if category_def:
                print(f"[ENRICH] Using existing category: {category_def.name}")
                return EnrichCategoryResponse(
                    invoice_id=request.invoice_id,
                    suggested_category=category_def.name,
                    confidence=1.0,
                    rule_matched="USER_PROVIDED",
                    fallback_used=False,
                )
            else:
                print(
                    f"[ENRICH] WARNING: User category '{request.existing_category}' not in policy."
                )

        # 2. Semantic/Keyword Matching (The Main Logic)
        if request.vendor:
            print(f"\n[ENRICH] === Checking Vendor Keywords ===")

            # Normalize vendor string for better matching
            vendor_normalized = request.vendor.lower().strip()
            print(f"[ENRICH] Normalized vendor: '{vendor_normalized}'")

            for category_def in policy_data.categories:
                enrichment_rules = category_def.enrichment_rules

                if not enrichment_rules.vendor_keywords:
                    continue

                if matches_vendor_keywords(
                    request.vendor, enrichment_rules.vendor_keywords
                ):
                    print(f"[ENRICH] VENDOR MATCH FOUND: {category_def.name}")
                    return EnrichCategoryResponse(
                        invoice_id=request.invoice_id,
                        suggested_category=category_def.name,
                        confidence=0.90,
                        rule_matched=f"VENDOR_TYPE_{category_def.name.upper().replace(' ', '_')}",
                        fallback_used=False,
                    )
        else:
            print(f"\n[ENRICH] WARNING: No vendor provided, skipping keyword matching")

        # 3. Fallback (Since Time-Based is removed)
        print(
            f"\n[ENRICH] No match found. Defaulting to: {policy_data.default_category}"
        )

        return EnrichCategoryResponse(
            invoice_id=request.invoice_id,
            suggested_category=policy_data.default_category,
            confidence=0.50,
            rule_matched="DEFAULT_FALLBACK",
            fallback_used=True,
        )

    except Exception as e:
        print(f"[ENRICH] ERROR: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Category enrichment failed: {str(e)}"
        )
