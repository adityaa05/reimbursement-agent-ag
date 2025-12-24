from fastapi import APIRouter, HTTPException
import requests
from models.schemas import OdooCommentRequest, OdooCommentResponse

router = APIRouter()


@router.post("/post-odoo-comment", response_model=OdooCommentResponse)
async def post_odoo_comment(request: OdooCommentRequest):
    """
    Post verification comment to Odoo expense sheet

    FIXED: Correct args format to avoid IndexError
    """
    try:
        # Step 1: Authenticate with Odoo
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
            return OdooCommentResponse(
                success=False, error=f"Authentication failed: {auth_result['error']}"
            )

        cookies = auth_response.cookies

        # Step 2: Post comment using message_post
        comment_url = f"{request.odoo_url}/web/dataset/call_kw"

        # CRITICAL FIX: Pass expense_sheet_id as first element of args array
        # This matches Odoo's expected format: method(id, **kwargs)
        comment_payload = {
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "hr.expense.sheet",
                "method": "message_post",
                "args": [request.expense_sheet_id],  # <-- FIXED: ID in args, not kwargs
                "kwargs": {
                    "body": request.comment_html,
                    "message_type": "comment",
                    "subtype_xmlid": "mail.mt_comment",
                },
            },
            "id": 1,
        }

        comment_response = requests.post(
            comment_url, json=comment_payload, cookies=cookies
        )
        comment_result = comment_response.json()

        if "error" in comment_result:
            return OdooCommentResponse(
                success=False,
                error=f"Comment posting failed: {comment_result['error']}",
            )

        message_id = comment_result.get("result")

        return OdooCommentResponse(success=True, message_id=message_id)

    except Exception as e:
        return OdooCommentResponse(success=False, error=str(e))
