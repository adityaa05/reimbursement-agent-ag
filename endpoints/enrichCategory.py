from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from models.schemas import BatchEnrichmentRequest, BatchEnrichmentResponse
from utils.logger import logger
from endpoints.policyStore import get_policy

router = APIRouter()


@router.post("/enrich-categories-batch", response_model=BatchEnrichmentResponse)
async def enrich_categories_batch(request: BatchEnrichmentRequest = Body(...)):
    """
    Agent 2 Tool: Dynamic Categorization.

    1. Fetches the ACTIVE Policy for the company (Confluence/DB/JSON).
    2. Uses the keywords defined in that Policy to categorize invoices.
    3. Zero hardcoded keywords in this file.
    """
    try:
        logger.info(
            f"Categorizing {len(request.invoices)} invoices for Sheet {request.expense_sheet_id}"
        )

        # 1. Fetch Dynamic Policy Data
        # This ensures we always use the latest rules from the Policy Store
        policy_data = get_policy(request.company_id or "hashgraph_inc")

        enriched_results = []

        for inv in request.invoices:
            vendor_lower = (inv.vendor or "").lower()
            assigned_category = "Unknown"  # Default if no rules match
            confidence_score = 0.0

            # 2. Iterate through DYNAMIC Policy Categories
            # We look for matches in the 'enrichment_rules' of the policy
            for cat in policy_data.categories:
                rules = cat.enrichment_rules

                # Check Vendor Keywords (from Policy)
                if rules and rules.vendor_keywords:
                    # Check if any keyword matches the vendor string
                    if any(k.lower() in vendor_lower for k in rules.vendor_keywords):
                        assigned_category = cat.name
                        confidence_score = 0.95
                        break  # Stop checking other categories if match found

            # 3. Fallback / "Other" Handling
            if assigned_category == "Unknown" and policy_data.default_category:
                assigned_category = policy_data.default_category
                confidence_score = 0.5

            # 4. Format Result
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
