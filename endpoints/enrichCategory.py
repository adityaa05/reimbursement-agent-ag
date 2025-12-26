import re
from typing import Optional
from fastapi import APIRouter, HTTPException

from models.schemas import EnrichCategoryRequest, EnrichCategoryResponse
from utils.policy_helpers import (
    matches_time_rule,
    matches_vendor_keywords,
    find_category_by_name,
)
from endpoints.policyStore import get_policy

router = APIRouter()


class EnhancedEnrichCategoryRequest(EnrichCategoryRequest):
    """Enhanced request with total_amount for semantic analysis."""

    total_amount: Optional[float] = None


@router.post("/enrich-category", response_model=EnrichCategoryResponse)
async def enrich_category(request: EnhancedEnrichCategoryRequest):
    """Category enrichment using vendor keywords and time-based rules."""
    try:
        company_id = request.company_id
        policy_data = get_policy(company_id)

        print(f"\n[ENRICH] ===== Processing Invoice {request.invoice_id} =====")
        print(f"[ENRICH] Vendor: {request.vendor}")
        print(f"[ENRICH] Amount: {request.total_amount}")
        print(f"[ENRICH] Time: {request.time}")
        print(f"[ENRICH] Date: {request.date}")
        print(f"[ENRICH] Existing Category: {request.existing_category}")

        print(f"\n[ENRICH] === LOADED POLICY SUMMARY ===")
        print(f"[ENRICH] Policy has {len(policy_data.categories)} categories")
        for cat in policy_data.categories:
            keywords_count = len(cat.enrichment_rules.vendor_keywords or [])
            time_rules_count = len(cat.enrichment_rules.time_based or [])
            print(f"[ENRICH] {cat.name}:")
            print(f"[ENRICH]   - Vendor Keywords: {keywords_count}")
            if keywords_count > 0:
                sample = cat.enrichment_rules.vendor_keywords[:5]
                print(f"[ENRICH]     Sample: {sample}")
            else:
                print(f"[ENRICH]     WARNING: NO KEYWORDS DEFINED")
            print(f"[ENRICH]   - Time Rules: {time_rules_count}")
            if time_rules_count > 0:
                print(f"[ENRICH]     Rules: {cat.enrichment_rules.time_based}")

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
                    f"[ENRICH] WARNING: User category '{request.existing_category}' not in policy, enriching..."
                )

        if request.vendor:
            print(f"\n[ENRICH] === PASS 1: Checking Vendor Keywords (Priority #1) ===")
            print(f"[ENRICH] Input vendor string: '{request.vendor}'")

            vendor_normalized = request.vendor.lower().strip()
            vendor_normalized = vendor_normalized.replace("\n", " ").replace("\r", " ")
            vendor_normalized = re.sub(r"\s+", " ", vendor_normalized)
            vendor_normalized = re.sub(
                r"[^\w\s]", " ", vendor_normalized, flags=re.UNICODE
            )

            vendor_normalized = re.sub(r"\s+", " ", vendor_normalized).strip()
            print(f"[ENRICH] Normalized vendor: '{vendor_normalized}'")

            for category_def in policy_data.categories:
                enrichment_rules = category_def.enrichment_rules

                if not enrichment_rules.vendor_keywords:
                    print(
                        f"[ENRICH] Skipping {category_def.name} - no keywords defined"
                    )
                    continue

                print(f"\n[ENRICH] Trying category: {category_def.name}")
                print(
                    f"[ENRICH] Keywords ({len(enrichment_rules.vendor_keywords)}): {enrichment_rules.vendor_keywords[:10]}..."
                )

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
                    print(f"[ENRICH] No match in {category_def.name}")

        else:
            print(f"\n[ENRICH] WARNING: No vendor provided, skipping vendor matching")

        if request.time:
            print(f"\n[ENRICH] === PASS 2: Checking Time Rules (no vendor match) ===")
            print(f"[ENRICH] Input time: {request.time}")

            for category_def in policy_data.categories:
                enrichment_rules = category_def.enrichment_rules

                if not enrichment_rules.time_based:
                    continue

                print(f"\n[ENRICH] Trying category: {category_def.name}")
                print(f"[ENRICH] Time rules: {enrichment_rules.time_based}")

                for time_rule in enrichment_rules.time_based:
                    if matches_time_rule(request.time, time_rule):
                        print(
                            f"[ENRICH] TIME MATCH FOUND: {category_def.name} ({time_rule})"
                        )
                        return EnrichCategoryResponse(
                            invoice_id=request.invoice_id,
                            suggested_category=category_def.name,
                            confidence=0.75,
                            rule_matched=f"TIME_BASED_{time_rule.get('subcategory', 'UNKNOWN').upper()}",
                            fallback_used=False,
                        )

        else:
            print(
                f"\n[ENRICH] WARNING: No time provided, skipping time-based enrichment"
            )

        print(
            f"\n[ENRICH] WARNING: No rules matched, using fallback: {policy_data.default_category}"
        )

        print(f"[ENRICH] WARNING: ENRICHMENT FAILED - CHECK CONFLUENCE KEYWORDS!")

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
        print(f"[ENRICH] ERROR: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Category enrichment failed: {str(e)}"
        )
