from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import boto3
import os
from dotenv import load_dotenv
import base64

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

extract = boto3.client(
    "textract",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
)


class OCRRequest(BaseModel):
    # Request to extract invoice data using Textract
    image_base64: str
    invoice_id: str
    filename: Optional[str] = None


class OCRResponse(BaseModel):
    # Textract OCR output
    invoice_id: str
    vendor: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    total_amount: Optional[float] = None
    currency: Optional[str] = "CHF"
    line_items: List[Dict[str, Any]] = []
    confidence: Optional[float] = None


class OCRValidationRequest(BaseModel):
    # Request to validate OCR outputs
    textract_amount: float
    odoo_claimed_amount: float
    invoice_id: str
    currency: str = "CHF"


class OCRValidationResponse(BaseModel):
    # Validation result
    invoice_id: str
    verified_amount: float
    employee_reported_amount: float
    matched: bool
    discrepancy_message: Optional[str] = None
    discrepancy_amount: Optional[float] = None
    currency: str


def parse_amount(amount_str):
    # Parse amount string to float
    if not amount_str:
        return None

    cleaned = amount_str.replace("CHF", "").replace("$", "").replace("€", "").strip()
    cleaned = cleaned.replace("'", "").replace(",", "")

    try:
        return float(cleaned)
    except:
        return None


@app.get("/")
async def root():
    # Health check endpoint
    return {
        "status": "running",
        "service": "Reimbursement Bot",
    }


@app.post("/textract-ocr", response_model=OCRResponse)
async def textract_ocr(request: OCRRequest):

    try:
        # Decode base64 image
        image_bytes = base64.b64decode(request.image_base64)

        # Call Textract
        response = extract.analyze_expense(Document={"Bytes": image_bytes})

        # Parse response
        expense_docs = response.get("ExpenseDocuments", [])
        if not expense_docs:
            raise HTTPException(
                status_code=400, detail="No expense data found in image"
            )

        doc = expense_docs[0]
        summary_fields = doc.get("SummaryFields", [])

        extracted_data = {
            "invoice_id": request.invoice_id,
            "vendor": None,
            "date": None,
            "time": None,
            "total_amount": None,
            "currency": "CHF",
            "line_items": [],
        }

        # Extract fields
        for field in summary_fields:
            field_type = field.get("Type", {}).get("Text", "")
            field_value = field.get("ValueDetection", {}).get("Text", "")
            confidence = field.get("ValueDetection", {}).get("Confidence", 0)

            if field_type in ["VENDOR_NAME", "RECEIVER_NAME"]:
                extracted_data["vendor"] = field_value
            elif field_type == "INVOICE_RECEIPT_DATE":
                extracted_data["date"] = field_value
            elif field_type == "TOTAL":
                extracted_data["total_amount"] = parse_amount(field_value)

        # Extract line items
        line_items_groups = doc.get("LineItemGroups", [])
        for group in line_items_groups:
            for item in group.get("LineItems", []):
                line_item = {}
                for field in item.get("LineItemExpenseFields", []):
                    field_type = field.get("Type", {}).get("Text", "")
                    field_value = field.get("ValueDetection", {}).get("Text", "")

                    if field_type == "ITEM":
                        line_item["description"] = field_value
                    elif field_type == "PRICE":
                        line_item["amount"] = parse_amount(field_value)

                if line_item:
                    extracted_data["line_items"].append(line_item)

        return OCRResponse(**extracted_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Textract OCR failed: {str(e)}")


@app.post("/validate-ocr", response_model=OCRValidationResponse)
async def validate_ocr(request: OCRValidationRequest):
    # Compares Textract amount with employee-claimed amount
    try:
        textract_amt = request.textract_amount
        claimed_amt = request.odoo_claimed_amount

        if abs(textract_amt - claimed_amt) < 0.01:  # Tolerance: 0.01 CHF
            # Amounts match
            return OCRValidationResponse(
                invoice_id=request.invoice_id,
                verified_amount=textract_amt,
                employee_reported_amount=claimed_amt,
                matched=True,
                discrepancy_message=None,
                discrepancy_amount=0.0,
                currency=request.currency,
            )
        else:
            # Discrepancy detected
            discrepancy = abs(textract_amt - claimed_amt)

            # Format exact message as required by PRD
            message = f"Value in invoice as per AG is {textract_amt:.2f}, not {claimed_amt:.2f} as reported"

            return OCRValidationResponse(
                invoice_id=request.invoice_id,
                verified_amount=textract_amt,
                employee_reported_amount=claimed_amt,
                matched=False,
                discrepancy_message=message,
                discrepancy_amount=discrepancy,
                currency=request.currency,
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")
