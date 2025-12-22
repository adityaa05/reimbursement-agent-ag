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
    total_amount: Optional[float] = None
    currency: Optional[str] = "CHF"
    line_items: List[Dict[str, Any]] = []
    source: str = "odoo_ocr"


class DualOCRValidationRequest(BaseModel):
    textract_output: OCRResponse
    odoo_output: OdooOCRResponse
    employee_claim: float
    invoice_id: str
    currency: str = "CHF"


class DualOCRValidationResponse(BaseModel):
    invoice_id: str
    textract_amount: Optional[float] = None
    odoo_amount: Optional[float] = None
    verified_amount: Optional[float] = None
    employee_reported_amount: float

    ocr_consensus: bool
    ocr_mismatch_message: Optional[str] = None

    amount_matched: bool
    discrepancy_message: Optional[str] = None
    discrepancy_amount: Optional[float] = None

    risk_level: str
    currency: str


class TotalCalculationRequest(BaseModel):
    individual_validations: List[DualOCRValidationResponse]
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
    dual_ocr_validations: List[DualOCRValidationResponse]
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
