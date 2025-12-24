from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# ============================================
# OCR SCHEMAS (NO CHANGES NEEDED)
# ============================================


class OCRRequest(BaseModel):
    image_base64: str
    invoice_id: str
    filename: Optional[str] = None


class OCRResponse(BaseModel):
    invoice_id: str
    vendor: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = "CHF"
    line_items: List[Dict[str, Any]] = []
    confidence: Optional[float] = None


class OdooOCRRequest(BaseModel):
    expense_line_id: int
    odoo_url: str
    odoo_db: str
    odoo_username: str
    odoo_password: str


class OdooOCRResponse(BaseModel):
    invoice_id: str
    vendor: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None  # ✅ Added time field
    total_amount: Optional[float] = None
    currency: Optional[str] = "CHF"
    line_items: List[Dict[str, Any]] = []
    source: str = "odoo_ocr"


# ============================================
# VALIDATION SCHEMAS (UPDATED FOR SINGLE OCR)
# ============================================


class SingleOCRValidationRequest(BaseModel):  # RENAMED from DualOCRValidationRequest
    """Request for single OCR validation (Odoo only)"""

    odoo_output: OdooOCRResponse  # ✅ Only Odoo OCR
    employee_claim: float
    invoice_id: str
    currency: str = "CHF"


class SingleOCRValidationResponse(BaseModel):  # RENAMED from DualOCRValidationResponse
    """Response for single OCR validation"""

    invoice_id: str
    # ❌ REMOVED: textract_amount: Optional[float] = None
    odoo_amount: Optional[float] = None
    verified_amount: Optional[float] = None
    employee_reported_amount: float
    # ❌ REMOVED: ocr_consensus: bool
    # ❌ REMOVED: ocr_mismatch_message: Optional[str] = None
    amount_matched: bool
    discrepancy_message: Optional[str] = None
    discrepancy_amount: Optional[float] = None
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    currency: str


# ============================================
# TOTAL CALCULATION (UPDATED REFERENCE)
# ============================================


class TotalCalculationRequest(BaseModel):
    individual_validations: List[SingleOCRValidationResponse]  # UPDATED type
    employee_reported_total: float
    currency: str = "CHF"


class TotalCalculationResponse(BaseModel):
    calculated_total: float
    employee_reported_total: float
    matched: bool
    discrepancy_amount: Optional[float] = None
    discrepancy_message: Optional[str] = None
    currency: str


# ============================================
# ENRICHMENT & POLICY SCHEMAS (NO CHANGES)
# ============================================


class EnrichCategoryRequest(BaseModel):
    vendor: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    existing_category: Optional[str] = None
    invoice_id: str
    company_id: str = "hashgraph_inc"


class EnrichCategoryResponse(BaseModel):
    invoice_id: str
    suggested_category: str
    confidence: float
    rule_matched: str
    fallback_used: bool


class PolicyFetchRequest(BaseModel):
    company_id: str = "hashgraph_inc"
    categories: Optional[List[str]] = Field(
        default=None, description="Optional: Filter specific categories"
    )


class PolicyViolation(BaseModel):
    rule: str
    message: str
    severity: str = "ERROR"


class PolicyValidationRequest(BaseModel):
    category: str
    amount: float
    currency: str = "CHF"
    vendor: Optional[str] = None
    has_receipt: bool = True
    has_attendees: Optional[bool] = None
    invoice_age_days: Optional[int] = None
    company_id: str = "hashgraph_inc"


class PolicyValidationResponse(BaseModel):
    compliant: bool
    violations: List[PolicyViolation]
    category_found: bool
    max_amount: Optional[float] = None


# ============================================
# REPORTING SCHEMAS (UPDATED REFERENCE)
# ============================================


class ReportFormatterRequest(BaseModel):
    expense_sheet_id: int
    expense_sheet_name: str
    employee_name: str
    single_ocr_validations: List[SingleOCRValidationResponse]
    total_validation: TotalCalculationResponse
    categories: Optional[List[str]] = None
    policy_validations: Optional[List[PolicyValidationResponse]] = None


class ReportFormatterResponse(BaseModel):
    formatted_comment: str
    html_comment: str


# ============================================
# ODOO INTEGRATION SCHEMAS (NO CHANGES)
# ============================================


class OdooCommentRequest(BaseModel):
    expense_sheet_id: int
    comment_html: str
    odoo_url: str
    odoo_db: str
    odoo_username: str
    odoo_password: str


class OdooCommentResponse(BaseModel):
    success: bool
    message_id: Optional[int] = None
    error: Optional[str] = None


class OdooExpenseFetchRequest(BaseModel):
    expense_sheet_id: int
    odoo_url: str
    odoo_db: str
    odoo_username: str
    odoo_password: str


# ============================================
# POLICY DATA MODELS (NO CHANGES)
# ============================================


class EnrichmentRules(BaseModel):
    """Rules for automatic category enrichment"""

    time_based: Optional[List[Dict[str, Any]]] = None
    vendor_keywords: Optional[List[str]] = None


class ValidationRules(BaseModel):
    """Rules for policy compliance validation"""

    max_amount: float
    currency: str = "CHF"
    requires_receipt: bool = True
    requires_attendees: Optional[bool] = None
    max_age_days: Optional[int] = 90
    approved_vendors: Optional[List[str]] = None


class CategoryDefinition(BaseModel):
    """Complete category definition with enrichment and validation rules"""

    name: str
    aliases: List[str] = []
    enrichment_rules: EnrichmentRules
    validation_rules: ValidationRules


class PolicyData(BaseModel):
    """Complete policy data structure (represents one Confluence page)"""

    company_id: str
    effective_date: str
    categories: List[CategoryDefinition]
    default_category: str = "Other"
    cache_ttl: int = 86400  # 24 hours in seconds
