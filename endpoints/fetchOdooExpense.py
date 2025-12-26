import requests
import json
from fastapi import APIRouter, HTTPException
from models.schemas import OdooExpenseFetchRequest
from utils.logger import logger

router = APIRouter()


@router.post("/fetch-odoo-expense")
async def fetch_odoo_expense(request: OdooExpenseFetchRequest):
    """Fetch expense sheet data from Odoo including expense lines and attachments."""
    try:
        # 1. Authenticate
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
            error_msg = (
                auth_result["error"].get("data", {}).get("message", "Auth Failed")
            )
            logger.error(f"Odoo Auth Error: {json.dumps(auth_result)}")
            raise HTTPException(
                status_code=401, detail=f"Odoo Auth Failed: {error_msg}"
            )

        cookies = auth_response.cookies
        read_url = f"{request.odoo_url}/web/dataset/call_kw"

        # 2. Fetch Sheet (Header)
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
                    ]
                },
            },
            "id": 1,
        }

        sheet_response = requests.post(read_url, json=read_payload, cookies=cookies)
        sheet_result = sheet_response.json()

        if "error" in sheet_result:
            error_msg = (
                sheet_result["error"].get("data", {}).get("message", "Unknown Error")
            )
            raise HTTPException(status_code=400, detail=f"Odoo Read Error: {error_msg}")

        result_list = sheet_result.get("result", [])
        if not result_list:
            logger.warning(
                f"Expense Sheet {request.expense_sheet_id} not found or empty."
            )
            return {"expense_sheet": {}, "expense_lines": []}

        sheet_data = result_list[0]
        line_ids = sheet_data.get("expense_line_ids", [])

        if not line_ids:
            return {"expense_sheet": sheet_data, "expense_lines": []}

        # 3. Fetch Lines (Details) - REMOVED 'unit_amount'
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
                        "total_amount",  # We will use this instead
                        "currency_id",
                        "date",
                        "attachment_ids",
                        "description",
                    ]
                },
            },
            "id": 2,
        }

        lines_response = requests.post(read_url, json=lines_payload, cookies=cookies)
        lines_result = lines_response.json()

        if "error" in lines_result:
            error_msg = (
                lines_result["error"].get("data", {}).get("message", "Unknown Error")
            )
            raise HTTPException(
                status_code=400, detail=f"Odoo Lines Error: {error_msg}"
            )

        lines_data = lines_result.get("result", [])

        # 4. Fetch Attachments
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

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Fetch Odoo Exception: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Fetch Failed: {str(e)}")
