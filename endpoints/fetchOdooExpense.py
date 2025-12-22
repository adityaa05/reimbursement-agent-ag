from fastapi import APIRouter, HTTPException
import requests
from models.schemas import OdooExpenseFetchRequest

router = APIRouter()


@router.post("/fetch-odoo-expense")
async def fetch_odoo_expense(request: OdooExpenseFetchRequest):
    """
    Fetch expense sheet data from Odoo
    Returns expense lines with amounts and attachments
    """
    try:
        # Authenticate
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
            raise HTTPException(status_code=401, detail="Odoo authentication failed")

        cookies = auth_response.cookies

        # Fetch expense sheet
        read_url = f"{request.odoo_url}/web/dataset/call_kw"
        read_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "hr.expense.sheet",
                "method": "read",
                "args": [[request.expense_sheet_id]],
                "kwargs": {
                    "fields": [
                        "name",
                        "employee_id",
                        "state",
                        "total_amount",
                        "expense_line_ids",
                        "currency_id",
                    ]
                },
            },
            "id": 1,
        }

        sheet_response = requests.post(read_url, json=read_payload, cookies=cookies)
        sheet_data = sheet_response.json().get("result", [{}])[0]

        # Fetch expense lines
        line_ids = sheet_data.get("expense_line_ids", [])

        lines_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "hr.expense",
                "method": "read",
                "args": [line_ids],
                "kwargs": {
                    "fields": [
                        "name",
                        "product_id",
                        "total_amount",
                        "date",
                        "attachment_ids",
                        "description",
                    ]
                },
            },
            "id": 2,
        }

        lines_response = requests.post(read_url, json=lines_payload, cookies=cookies)
        lines_data = lines_response.json().get("result", [])

        # Fetch attachments for each line
        for line in lines_data:
            attachment_ids = line.get("attachment_ids", [])
            if attachment_ids:
                att_payload = {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": {
                        "model": "ir.attachment",
                        "method": "read",
                        "args": [attachment_ids],
                        "kwargs": {"fields": ["name", "datas", "mimetype"]},
                    },
                    "id": 3,
                }

                att_response = requests.post(
                    read_url, json=att_payload, cookies=cookies
                )
                line["attachments"] = att_response.json().get("result", [])

        return {"expense_sheet": sheet_data, "expense_lines": lines_data}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch Odoo data: {str(e)}"
        )
