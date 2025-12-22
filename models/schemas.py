from pydantic import BaseModel
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


class OCRValidationRequest(BaseModel):
    textract_amount: float
    odoo_claimed_amount: float
    invoice_id: str
    currency: str = "CHF"


class OCRValidationResponse(BaseModel):
    invoice_id: str
    verified_amount: float
    employee_reported_amount: float
    matched: bool
    discrepancy_message: Optional[str] = None
    discrepancy_amount: Optional[float] = None
    currency: str


class TotalCalculationRequest(BaseModel):
    individual_validations: List[OCRValidationResponse]
    employee_reported_total: float
    currency: str = "CHF"


class TotalCalculationResponse(BaseModel):
    calculated_total: float
    employee_reported_total: float
    matched: bool
    discrepancy_amount: Optional[float] = None
    discrepancy_message: Optional[str] = None
    currency: str


class ReportFormatterRequest(BaseModel):
    expense_sheet_id: int
    expense_sheet_name: str
    employee_name: str
    ocr_validations: List[OCRValidationResponse]
    total_validation: TotalCalculationResponse


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


class OdooOCRRequest(BaseModel):
    expense_line_id: int  # Odoo expense line ID
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
    source: str = "zoho_ocr"
    line_items: List[Dict[str, Any]] = []
