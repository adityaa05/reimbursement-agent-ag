from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from models.schemas import BatchEnrichmentRequest, BatchEnrichmentResponse
from utils.logger import logger
from endpoints.policyStore import get_policy
from utils.policy_helpers import find_category_by_name

router = APIRouter()


@router.post("/enrich-categories-batch", response_model=BatchEnrichmentResponse)
async def enrich_categories_batch(request: BatchEnrichmentRequest = Body(...)):
    """
    Agent 2 Tool: Hybrid Categorization.

    Priority 1: Strict Keyword Match from Policy (Dynamic).
    Priority 2: Agent 2's Semantic Suggestion (for edge cases).
    Priority 3: Default/Unknown.
    """
    try:
        logger.info(
            f"Categorizing {len(request.invoices)} invoices for Sheet {request.expense_sheet_id}"
        )

        policy_data = get_policy(request.company_id or "hashgraph_inc")
        enriched_results = []

        for inv in request.invoices:
            vendor_lower = (inv.vendor or "").lower()
            assigned_category = "Unknown"
            confidence_score = 0.0

            # 1. Strict Keyword Check (Priority)
            for cat in policy_data.categories:
                rules = cat.enrichment_rules
                if rules and rules.vendor_keywords:
                    if any(k.lower() in vendor_lower for k in rules.vendor_keywords):
                        assigned_category = cat.name
                        confidence_score = 0.95
                        break

            # 2. Semantic Fallback (Edge Cases)
            # If keywords failed, check if Agent 2 provided a valid suggestion
            if assigned_category == "Unknown" and inv.ai_suggested_category:
                # Verify the suggestion exists in our Policy
                found_cat = find_category_by_name(
                    policy_data, inv.ai_suggested_category
                )
                if found_cat:
                    assigned_category = found_cat.name
                    confidence_score = (
                        0.80  # AI is slightly less confident than strict keywords
                    )
                    logger.info(
                        f"Using AI suggestion '{assigned_category}' for vendor '{inv.vendor}'"
                    )

            # 3. Default Fallback
            if assigned_category == "Unknown" and policy_data.default_category:
                assigned_category = policy_data.default_category
                confidence_score = 0.5

            enriched_results.append(
                {
                    "invoice_id": inv.invoice_id,
                    "vendor": inv.vendor,
                    "amount": inv.amount,
                    "category": assigned_category,
                    "confidence": confidence_score,
                }
            )

        return BatchEnrichmentResponse(enriched_invoices=enriched_results)

    except Exception as e:
        logger.error(f"Batch enrichment failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
