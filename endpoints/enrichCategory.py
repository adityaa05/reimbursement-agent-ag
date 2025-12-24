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
    FIXED: Enrich missing invoice category using POLICY-DRIVEN rules

    Changes from v1:
    1. Two-pass approach: Vendor keywords FIRST, then time rules
    2. Enhanced debug logging
    3. Better fallback strategy

    NO HARD-CODED CATEGORIES - All rules dynamically loaded from policy

    Rules applied in order (FIXED):
    1. User-provided category (validate against policy)
    2. **Vendor keyword rules** (PRIORITY #1 - checked across ALL categories)
    3. **Time-based rules** (PRIORITY #2 - only if no vendor match)
    4. Default category (from policy)
    """
    try:
        # Fetch policy rules
        company_id = request.company_id
        policy_data = get_policy(company_id)

        print(f"\n[ENRICH] ===== Processing Invoice {request.invoice_id} =====")
        print(f"[ENRICH] Vendor: {request.vendor}")
        print(f"[ENRICH] Time: {request.time}")
        print(f"[ENRICH] Existing Category: {request.existing_category}")
        print(f"[ENRICH] Policy has {len(policy_data.categories)} categories")

        # STEP 1: If category already exists, validate it against policy
        if request.existing_category:
            category_def = find_category_by_name(policy_data, request.existing_category)
            if category_def:
                print(f"[ENRICH] ✅ Using existing category: {category_def.name}")
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
                    f"[ENRICH] ⚠️  User category '{request.existing_category}' not in policy, enriching..."
                )

        # ================================================================
        # STEP 2: VENDOR KEYWORDS - HIGHEST PRIORITY (PASS 1)
        # Check ALL categories for vendor match BEFORE trying time rules
        # ================================================================

        if request.vendor:
            print(f"\n[ENRICH] === PASS 1: Checking Vendor Keywords ===")

            for category_def in policy_data.categories:
                enrichment_rules = category_def.enrichment_rules

                # Skip if no vendor keywords defined
                if not enrichment_rules.vendor_keywords:
                    continue

                print(f"\n[ENRICH] Trying category: {category_def.name}")
                print(f"[ENRICH]   Keywords: {enrichment_rules.vendor_keywords[:5]}...")

                # Check if vendor matches this category's keywords
                if matches_vendor_keywords(
                    request.vendor, enrichment_rules.vendor_keywords
                ):
                    print(f"[ENRICH] ✅✅✅ VENDOR MATCH FOUND: {category_def.name}")
                    return EnrichCategoryResponse(
                        invoice_id=request.invoice_id,
                        suggested_category=category_def.name,
                        confidence=0.90,
                        rule_matched=f"VENDOR_TYPE_{category_def.name.upper().replace(' ', '_')}",
                        fallback_used=False,
                    )
        else:
            print(f"\n[ENRICH] ⚠️  No vendor provided, skipping vendor matching")

        # ================================================================
        # STEP 3: TIME-BASED RULES - MEDIUM PRIORITY (PASS 2)
        # Only checked if NO vendor match was found
        # ================================================================

        if request.time:
            print(f"\n[ENRICH] === PASS 2: Checking Time Rules (no vendor match) ===")

            for category_def in policy_data.categories:
                enrichment_rules = category_def.enrichment_rules

                # Skip if no time rules defined
                if not enrichment_rules.time_based:
                    continue

                print(f"\n[ENRICH] Trying category: {category_def.name}")
                print(f"[ENRICH]   Time rules: {enrichment_rules.time_based}")

                # Check each time rule
                for time_rule in enrichment_rules.time_based:
                    if matches_time_rule(request.time, time_rule):
                        print(
                            f"[ENRICH] ✅ TIME MATCH FOUND: {category_def.name} ({time_rule})"
                        )
                        return EnrichCategoryResponse(
                            invoice_id=request.invoice_id,
                            suggested_category=category_def.name,
                            confidence=0.95,
                            rule_matched=f"TIME_BASED_{time_rule.get('subcategory', 'UNKNOWN').upper()}",
                            fallback_used=False,
                        )
        else:
            print(f"\n[ENRICH] ⚠️  No time provided, skipping time-based enrichment")

        # ================================================================
        # STEP 4: FALLBACK - Use default category from policy
        # ================================================================

        print(
            f"\n[ENRICH] ⚠️  No rules matched, using fallback: {policy_data.default_category}"
        )

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
        print(f"[ENRICH] ❌ ERROR: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Category enrichment failed: {str(e)}"
        )
