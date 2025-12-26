from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from endpoints.fetchOdooExpense import router as fetch_router
from endpoints.odooOCR import router as odoo_ocr_router
from endpoints.OCRValidator import router as validator_router
from endpoints.calculateTotal import router as total_router
from endpoints.enrichCategory import router as enrich_router
from endpoints.policyValidator import router as validate_policy_router
from endpoints.formatReport import router as report_router
from endpoints.postOdooComment import router as comment_router
from endpoints.fetchPolicies import router as fetch_policies_router
from endpoints.approvalRouter import router as approval_router
from endpoints.processExpenseRequest import router as process_router
from endpoints.agenticOrchestration import router as agentic_router

app = FastAPI(
    title="Expense Reimbursement API - Phase 1",
    description="Hard-coded validation endpoints for AgenticGenie",
    version="1.0.0",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoint routers
app.include_router(fetch_router, tags=["Odoo Integration"])
app.include_router(odoo_ocr_router, tags=["OCR"])
app.include_router(validator_router, tags=["Validation"])
app.include_router(total_router, tags=["Validation"])
app.include_router(enrich_router, tags=["Enrichment"])
app.include_router(validate_policy_router, tags=["Policy"])
app.include_router(report_router, tags=["Reporting"])
app.include_router(comment_router, tags=["Odoo Integration"])
app.include_router(fetch_policies_router, tags=["Policy"])
app.include_router(approval_router, tags=["Workflow"])
app.include_router(process_router, tags=["Master Endpoint"])
app.include_router(agentic_router, tags=["Agentic Workflow"])


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "Expense Reimbursement API",
        "version": "3.0.0",
        "master_endpoint": "/process-expense-request",
        "endpoints": {
            "master": "/process-expense-request (USE THIS)",
            "agentic_verification": "/verify-expenses-only (Agent 1)",
            "agentic_policy_validation": "/validate-policies-batch (Agent 3)",
            "agentic_report_generation": "/generate-report (Agent 4)",
            "fetch": "/fetch-odoo-expense",
            "ocr": "/odoo-ocr",
            "validate_ocr": "/validate-ocr",
            "calculate_total": "/calculate-total",
            "enrich_category": "/enrich-category",
            "fetch_policies": "/fetch-policies",
            "validate_policy": "/validate-policy",
            "format_report": "/format-report",
            "post_comment": "/post-odoo-comment",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


from fastapi import FastAPI

app = FastAPI()


@app.api_route("/empty-json", methods=["GET", "HEAD"])
async def empty_endpoint():
    return {}
