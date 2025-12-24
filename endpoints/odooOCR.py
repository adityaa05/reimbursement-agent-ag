from fastapi import APIRouter, HTTPException
import requests
from models.schemas import OdooOCRRequest, OdooOCRResponse

router = APIRouter()


@router.post("/odoo-ocr", response_model=OdooOCRResponse)
async def odoo_ocr(request: OdooOCRRequest):
    # Extract invoice data using Odoo's built-in OCR
    try:
        # Authenticate with Odoo
        auth_url = f"{request.odoo_url}/web/session/authenticate"
        auth_payload = {
            "jsonrpc": "2.0",
            "params": {
                "db": request.odoo_db,
                "login": request.odoo_username,
                "password": request.odoo_password,
            },
        }

        auth_response = requests.post(auth_url, json=auth_payload)
        auth_result = auth_response.json()

        if "error" in auth_result:
            raise HTTPException(
                status_code=401,
                detail=f"Odoo authentication failed: {auth_result['error']}",
            )

        cookies = auth_response.cookies

        # Read expense line with OCR fields
        read_url = f"{request.odoo_url}/web/dataset/call_kw"
        read_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "hr.expense",
                "method": "read",
                "args": [[request.expense_line_id]],
                "kwargs": {
                    "fields": [
                        "id",
                        "name",  # Vendor/description (OCR populated)
                        "total_amount",  # Amount extracted by Odoo OCR
                        "date",  # Date (OCR populated)
                        "product_id",  # Category
                        "currency_id",  # Currency
                        "description",  # Additional notes
                    ]
                },
            },
            "id": 1,
        }

        line_response = requests.post(read_url, json=read_payload, cookies=cookies)
        line_result = line_response.json()

        if "error" in line_result:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to read expense line: {line_result['error']}",
            )

        line_data = line_result.get("result", [{}])[0]

        if not line_data:
            raise HTTPException(
                status_code=404,
                detail=f"Expense line {request.expense_line_id} not found",
            )

        # Extract currency
        currency = "CHF"  # Default
        if line_data.get("currency_id"):
            # currency_id format: [id, "code"]
            if (
                isinstance(line_data["currency_id"], list)
                and len(line_data["currency_id"]) > 1
            ):
                currency = line_data["currency_id"][1]

        # Determine vendor name (Combine name and description to catch keywords)
        name = line_data.get("name", "")
        desc = line_data.get("description", "")
        
        # Handle Odoo returning False for empty fields
        if isinstance(name, bool): name = ""
        if isinstance(desc, bool): desc = ""
        
        vendor_name = f"{name} {desc}".strip()

        # Return OCR data (Odoo auto-populates these fields from invoice scan)
        return OdooOCRResponse(
            invoice_id=f"odoo-{line_data['id']}",
            vendor=vendor_name,
            date=line_data.get("date"),
            total_amount=line_data.get("total_amount"),
            currency=currency,
            line_items=[],  # Odoo doesn't break down line items
            source="odoo_ocr",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Odoo OCR failed: {str(e)}")
