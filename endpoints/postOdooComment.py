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
    FIXED: Uses 'subtype_id' to force HTML rendering without 'content_subtype'.
    """
    try:
        logger.info(f"Posting comment to Odoo sheet {expense_sheet_id}")

        common = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/common")
        uid = common.authenticate(odoo_db, odoo_username, odoo_password, {})

        if not uid:
            raise HTTPException(status_code=401, detail="Odoo Authentication Failed")

        models = xmlrpc.client.ServerProxy(f"{odoo_url}/xmlrpc/2/object")

        # 1. Fetch the correct Subtype ID for "Discussions" (HTML enabled)
        # We use 'xmlid_to_res_id' which is safer than searching by name "Discussions"
        try:
            subtype_id = models.execute_kw(
                odoo_db,
                uid,
                odoo_password,
                "ir.model.data",
                "xmlid_to_res_id",
                ["mail.mt_comment"],
            )
        except Exception:
            # Fallback: If XML ID fails, search by name (English)
            subtype_search = models.execute_kw(
                odoo_db,
                uid,
                odoo_password,
                "mail.message.subtype",
                "search",
                [[("name", "=", "Discussions")]],
                {"limit": 1},
            )
            subtype_id = subtype_search[0] if subtype_search else False

        # 2. Post the Message
        post_values = {
            "body": comment_html,
            "message_type": "comment",
        }

        # Only add subtype_id if we successfully found it
        if subtype_id:
            post_values["subtype_id"] = subtype_id

        message_id = models.execute_kw(
            odoo_db,
            uid,
            odoo_password,
            "hr.expense.sheet",
            "message_post",
            [expense_sheet_id],
            post_values,
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
