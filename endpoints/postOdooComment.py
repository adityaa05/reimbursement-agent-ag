import xmlrpc.client
from fastapi import APIRouter, HTTPException, Body
from models.schemas import OdooCommentResponse
from utils.logger import logger

router = APIRouter()


@router.post("/post-odoo-comment", response_model=OdooCommentResponse)
async def post_odoo_comment(
    expense_sheet_id: int = Body(...),
    comment_html: str = Body(...),
    odoo_url: str = Body(...),
    odoo_db: str = Body(...),
    odoo_username: str = Body(...),
    odoo_password: str = Body(...),
):
    """
    Agent 5 Tool: Post comment to Odoo.
    CRITICAL FIX: Removed ALL unsupported parameters (content_subtype, subtype_xmlid).
    """
    try:
        logger.info(f"Posting comment to Odoo sheet {expense_sheet_id}")

        common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
        uid = common.authenticate(odoo_db, odoo_username, odoo_password, {})

        if not uid:
            raise HTTPException(status_code=401, detail="Odoo Authentication Failed")

        models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")

        # ✅ CRITICAL FIX: Only use the MINIMAL supported parameters
        message_id = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            "hr.expense.sheet",
            "message_post",
            [expense_sheet_id],
            {
                "body": comment_html,
                "message_type": "comment",
                # ❌ REMOVED: "content_subtype": "html" (NOT SUPPORTED)
                # ❌ REMOVED: "subtype_xmlid" (NOT SUPPORTED)
            },
        )

        logger.info(f"Successfully posted comment. Message ID: {message_id}")
        return OdooCommentResponse(success=True, message_id=message_id)

    except xmlrpc.client.Fault as fault:
        error_msg = f"Odoo API Fault: {fault.faultString}"
        logger.error(f"Failed to post comment: {error_msg}")
        return OdooCommentResponse(success=False, error=error_msg)

    except Exception as e:
        logger.error(f"Failed to post comment: {str(e)}")
        return OdooCommentResponse(success=False, error=str(e))
