import re
import requests
from fastapi import APIRouter, HTTPException

from models.schemas import OdooOCRRequest, OdooOCRResponse

router = APIRouter()


@router.post("/odoo-ocr", response_model=OdooOCRResponse)
async def odoo_ocr(request: OdooOCRRequest):
    """Extract invoice data using Odoo's built-in OCR."""
    try:
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
                        "name",
                        "total_amount",
                        "date",
                        "product_id",
                        "currency_id",
                        "description",
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

        currency = "CHF"
        if line_data.get("currency_id"):
            if (
                isinstance(line_data["currency_id"], list)
                and len(line_data["currency_id"]) > 1
            ):
                currency = line_data["currency_id"][1]

        name = line_data.get("name", "")
        desc = line_data.get("description", "")

        if isinstance(name, bool):
            name = ""
        if isinstance(desc, bool):
            desc = ""

        vendor_raw = f"{name} {desc}".strip()

        vendor_clean = vendor_raw.replace("\n", " ").replace("\r", " ")
        vendor_clean = re.sub(r"\s+", " ", vendor_clean)
        vendor_clean = re.sub(r"[^\w\s-]", "", vendor_clean, flags=re.UNICODE)
        vendor_clean = re.sub(r"\s+", " ", vendor_clean).strip()

        print(f"[ODOO OCR] Vendor extraction:")
        print(f"  Raw: '{vendor_raw[:50]}'")
        print(f"  Cleaned: '{vendor_clean[:50]}'")

        line_items = []
        print(f"[ODOO OCR] Line items not available in hr.expense model")
        print(f"[ODOO OCR] Total amount: {line_data.get('total_amount')} {currency}")

        return OdooOCRResponse(
            invoice_id=f"odoo-{line_data['id']}",
            vendor=vendor_clean,
            date=line_data.get("date"),
            total_amount=line_data.get("total_amount"),
            currency=currency,
            line_items=line_items,
            source="odoo_ocr",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Odoo OCR failed: {str(e)}")
