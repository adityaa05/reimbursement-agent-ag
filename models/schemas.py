from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


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
    time: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = "CHF"
    line_items: List[Dict[str, Any]] = []
    source: str = "odoo_ocr"


class SingleOCRValidationRequest(BaseModel):
    """Request for single OCR validation (Odoo only)."""

    odoo_output: OdooOCRResponse
    employee_claim: float
    invoice_id: str
    currency: str = "CHF"


class SingleOCRValidationResponse(BaseModel):
    """Response for single OCR validation."""

    invoice_id: str
    odoo_amount: Optional[float] = None
    verified_amount: Optional[float] = None
    employee_reported_amount: float
    amount_matched: bool
    discrepancy_message: Optional[str] = None
    discrepancy_amount: Optional[float] = None
    risk_level: str
    currency: str


class TotalCalculationRequest(BaseModel):
    individual_validations: List[SingleOCRValidationResponse]
    employee_reported_total: float
    currency: str = "CHF"


class TotalCalculationResponse(BaseModel):
    calculated_total: float
    employee_reported_total: float
    matched: bool
    discrepancy_amount: Optional[float] = None
    discrepancy_message: Optional[str] = None
    currency: str


class EnrichCategoryRequest(BaseModel):
    vendor: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    total_amount: Optional[float] = None
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


class EnrichmentRules(BaseModel):
    """Rules for automatic category enrichment."""

    time_based: Optional[List[Dict[str, Any]]] = None
    vendor_keywords: Optional[List[str]] = None


class ValidationRules(BaseModel):
    """Rules for policy compliance validation."""

    max_amount: float
    currency: str = "CHF"
    requires_receipt: bool = True
    requires_attendees: Optional[bool] = None
    max_age_days: Optional[int] = 90
    approved_vendors: Optional[List[str]] = None


# --- RENAMED TO MATCH UTILS/POLICY_HELPERS.PY ---
class PolicyCategory(BaseModel):
    """Complete category definition with enrichment and validation rules."""

    name: str
    aliases: List[str] = []
    enrichment_rules: EnrichmentRules
    validation_rules: ValidationRules


class PolicyData(BaseModel):
    """Complete policy data structure."""

    company_id: str
    effective_date: str
    categories: List[PolicyCategory]  # Uses PolicyCategory
    default_category: str = "Other"
    cache_ttl: int = 86400


class InvoiceWithCategory(BaseModel):
    """Input for batch policy validation (from Agent 2)."""

    invoice_number: int
    category: str
    amount: float
    currency: str = "CHF"
    vendor: Optional[str] = None
    has_receipt: bool = True
    invoice_age_days: Optional[int] = 15

    # NEW: Safety configuration to allow the AI to be slightly messy
    class Config:
        populate_by_name = True
        extra = "ignore"  # Ignore if AI adds random extra fields like "reasoning"


class BatchPolicyValidationRequest(BaseModel):
    expense_sheet_id: int
    company_id: str = "hashgraph_inc"
    invoices: List[InvoiceWithCategory]


class BatchPolicyValidationResponse(BaseModel):
    policy_validations: List[PolicyValidationResponse]
