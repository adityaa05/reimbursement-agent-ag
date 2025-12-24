from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import ALL endpoint routers
from endpoints.fetchOdooExpense import router as fetch_router

# from endpoints.textractOCR import router as textract_router
from endpoints.odooOCR import router as odoo_ocr_router
from endpoints.OCRValidator import router as validator_router
from endpoints.calculateTotal import router as total_router
from endpoints.enrichCategory import router as enrich_router
from endpoints.policyValidator import router as validate_policy_router
from endpoints.formatReport import router as report_router
from endpoints.postOdooComment import router as comment_router
from endpoints.fetchPolicies import router as fetch_policies_router

app = FastAPI(
    title="Expense Reimbursement API - Phase 1",
    description="Hard-coded validation endpoints for AgenticGenie",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register ALL routers with tags
app.include_router(fetch_router, tags=["Odoo Integration"])
# app.include_router(textract_router, tags=["OCR"])
app.include_router(odoo_ocr_router, tags=["OCR"])
app.include_router(validator_router, tags=["Validation"])
app.include_router(total_router, tags=["Validation"])
app.include_router(enrich_router, tags=["Enrichment"])
app.include_router(validate_policy_router, tags=["Policy"])
app.include_router(report_router, tags=["Reporting"])
app.include_router(comment_router, tags=["Odoo Integration"])
app.include_router(fetch_policies_router, tags=["Policy"])


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "Expense Reimbursement API",
        "version": "1.0.0",
        "phase": "Phase 1 - Development (Policy-Driven)",
        "endpoints": {
            "fetch": "/fetch-odoo-expense",
            # "textract_ocr": "/textract-ocr",
            "zoho_ocr": "/zoho-ocr",
            "validate_dual_ocr": "/validate-ocr",
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
