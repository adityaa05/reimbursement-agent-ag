from fastapi import APIRouter, HTTPException
from models.schemas import EnrichCategoryRequest, EnrichCategoryResponse
from utils.policy_helpers import (
    matches_time_rule,
    matches_vendor_keywords,
    find_category_by_name,
)
from endpoints.policyStore import get_policy

router = APIRouter()


@router.post("/enrich-category", response_model=EnrichCategoryResponse)
async def enrich_category(request: EnrichCategoryRequest):
    """
    Enrich missing invoice category using POLICY-DRIVEN rules

    Phase 1: Uses mock policy store
    Phase 2: Uses Confluence-fetched policies

    NO HARD-CODED CATEGORIES - All rules dynamically loaded from policy

    Rules applied in order:
    1. User-provided category (validate against policy)
    2. Time-based rules (from policy enrichment_rules)
    3. Vendor keyword rules (from policy enrichment_rules)
    4. Default category (from policy)
    """
    try:
        # Fetch policy rules
        company_id = request.company_id
        policy_data = get_policy(company_id)

        # STEP 1: If category already exists, validate it against policy
        if request.existing_category:
            category_def = find_category_by_name(policy_data, request.existing_category)
            if category_def:
                return EnrichCategoryResponse(
                    invoice_id=request.invoice_id,
                    suggested_category=category_def.name,
                    confidence=1.0,
                    rule_matched="USER_PROVIDED",
                    fallback_used=False,
                )
            else:
                # User provided invalid category, continue with enrichment
                print(
                    f"[WARNING] User category '{request.existing_category}' not in policy for {company_id}"
                )

        # STEP 2: Apply enrichment rules from policy (NO HARD-CODED RULES)
        for category_def in policy_data.categories:
            enrichment_rules = category_def.enrichment_rules

            # RULE A: Time-based classification (DYNAMIC RULES FROM POLICY)
            if request.time and enrichment_rules.time_based:
                for time_rule in enrichment_rules.time_based:
                    if matches_time_rule(request.time, time_rule):
                        return EnrichCategoryResponse(
                            invoice_id=request.invoice_id,
                            suggested_category=category_def.name,
                            confidence=0.95,
                            rule_matched=f"TIME_BASED_{time_rule.get('subcategory', 'UNKNOWN').upper()}",
                            fallback_used=False,
                        )

            # RULE B: Vendor-based classification (DYNAMIC KEYWORDS FROM POLICY)
            if request.vendor and enrichment_rules.vendor_keywords:
                if matches_vendor_keywords(
                    request.vendor, enrichment_rules.vendor_keywords
                ):
                    return EnrichCategoryResponse(
                        invoice_id=request.invoice_id,
                        suggested_category=category_def.name,
                        confidence=0.90,
                        rule_matched=f"VENDOR_TYPE_{category_def.name.upper().replace(' ', '_')}",
                        fallback_used=False,
                    )

        # STEP 3: FALLBACK - Use default category from policy
        return EnrichCategoryResponse(
            invoice_id=request.invoice_id,
            suggested_category=policy_data.default_category,
            confidence=0.50,
            rule_matched="DEFAULT_FALLBACK",
            fallback_used=True,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Category enrichment failed: {str(e)}"
        )
