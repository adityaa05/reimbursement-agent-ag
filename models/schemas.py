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
