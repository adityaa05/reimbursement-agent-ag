import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()

ODOO_URL = os.getenv("ODOO_URL")
DATABASE = os.getenv("DATABASE")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")


def authenticate():
    """Authenticate once and return session info"""
    url = f"{ODOO_URL}/web/session/authenticate"
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {"db": DATABASE, "login": USERNAME, "password": PASSWORD},
    }

    response = requests.post(url=url, json=payload)
    result = response.json()

    if "error" in result:
        print(f"Authentication failed: {result['error']}")
        return None

    session_id = response.cookies.get("session_id")
    uid = result["result"]["uid"]

    print(f"User ID: {uid}")
    print(f"Session ID: {session_id}")

    return {"uid": uid, "session_id": session_id, "cookies": response.cookies}


def call_odoo_method(auth, model, method, args, kwargs=None):
    """Call Odoo method using existing session (no re-authentication)"""
    if kwargs is None:
        kwargs = {}

    url = f"{ODOO_URL}/web/dataset/call_kw"
    payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {"model": model, "method": method, "args": args, "kwargs": kwargs},
        "id": 1,
    }

    response = requests.post(url, json=payload, cookies=auth["cookies"])
    result = response.json()

    if "error" in result:
        print(f"Error: {result['error']}")
        return None

    return result.get("result")


def fetch_expense_sheets(auth):
    """Fetch expense sheets using existing session"""
    expense_ids = call_odoo_method(
        auth=auth,
        model="hr.expense.sheet",
        method="search",
        args=[[["state", "in", ["submit", "approve"]]]],
        kwargs={"limit": 10},
    )

    if not expense_ids:
        print("No expense sheets found")
        return

    print(f"Found {len(expense_ids)} expense sheets: {expense_ids}")

    expense_data = call_odoo_method(
        auth=auth,
        model="hr.expense.sheet",
        method="read",
        args=[expense_ids[:1]],
        kwargs={
            "fields": [
                "name",
                "employee_id",
                "state",
                "total_amount",
                "expense_line_ids",
                "currency_id",
            ]
        },
    )

    print("Expense Sheet Details:")
    print(json.dumps(expense_data, indent=2))

    return expense_data


def fetch_expense_lines(auth, expense_line_ids):
    """Fetch individual expense lines using existing session"""
    print(f"Fetching {len(expense_line_ids)} expense lines...")

    expense_lines = call_odoo_method(
        auth=auth,
        model="hr.expense",
        method="read",
        args=[expense_line_ids],
        kwargs={
            "fields": [
                "name",
                "product_id",
                "total_amount",
                "date",
                "attachment_ids",
                "description",
            ]
        },
    )

    print("Expense Lines:")
    print(json.dumps(expense_lines, indent=2))

    return expense_lines


def post_comment_to_expense(auth, expense_sheet_id, comment_body):
    print(f"Posting comment to expense sheet {expense_sheet_id}")
    result = call_odoo_method(
        auth=auth,
        model="hr.expense.sheet",
        method="message_post",
        args=[expense_sheet_id],
        kwargs={
            "body": comment_body,
            "message_type": "comment",
            "subtype_xmlid": "mail.mt_comment",
        },
    )

    if result:
        print(f"Comment posted successfully! Message ID: {result}")
    else:
        print("Failed to post comment")
    return result


def download_attachments(auth, attachment_ids):
    print(f"Downloading {len(attachment_ids)} attachments")
    attachments = call_odoo_method(
        auth=auth,
        model="ir.attachment",
        method="read",
        args=[attachment_ids],
        kwargs={"fields": ["name", "datas", "mimetype", "file_size"]},
    )

    downloaded_files = []
    for attachment in attachments:
        print(f"Attachment: {attachment['name']}")
        print(f"Type: {attachment['mimetype']}")
        print(f"Size: {attachment['file_size']} bytes")

        # 'datas' field contains base64-encoded file content
        if attachment.get("datas"):
            import base64

            file_content = base64.b64decode(attachment["datas"])

            # saving to disk for now
            filename = f"downloads/{attachment['name']}"
            import os

            os.makedirs("downloads", exist_ok=True)

            with open(filename, "wb") as f:
                f.write(file_content)

            print(f"Downloaded to: {filename}")

            downloaded_files.append(
                {
                    "filename": attachment["name"],
                    "content": file_content,
                    "mimetype": attachment["mimetype"],
                }
            )

    return downloaded_files


def collect_all_attachment_ids(expense_lines):
    """Collect all attachment IDs from expense lines"""
    all_attachment_ids = []
    for line in expense_lines:
        if line.get("attachment_ids"):
            all_attachment_ids.extend(line["attachment_ids"])
    return all_attachment_ids


if __name__ == "__main__":
    auth = authenticate()

    if auth:
        expense_sheets = fetch_expense_sheets(auth)

        if expense_sheets and len(expense_sheets) > 0:
            line_ids = expense_sheets[0]["expense_line_ids"]
            fetch_expense_lines(auth, line_ids)

            sheet_id = expense_sheets[0]["id"]
            expense_lines = fetch_expense_lines(auth, line_ids)

            attachment_ids = collect_all_attachment_ids(expense_lines)

            # Ask user if they want to download attachments
            if attachment_ids:
                print(f"\n{'='*60}")
                print(
                    f"Found {len(attachment_ids)} attachment(s) in this expense report."
                )
                print(f"Attachment IDs: {attachment_ids}")

                download_choice = (
                    input("\nDo you want to download these attachments? (yes/no): ")
                    .strip()
                    .lower()
                )

                if download_choice in ["yes", "y"]:
                    downloaded = download_attachments(auth, attachment_ids)
                    print(
                        f"Successfully downloaded {len(downloaded)} file(s) to ./downloads/"
                    )
                else:
                    print("Skipping download.")
            else:
                print("No attachments found for this expense report.")

        test_comment = """
            <p><strong>Automated Verification Report</strong></p>
            <p>Hi Manager,</p>
            <p>Please find below findings:</p>
            <p><strong>OCR Verification:</strong></p>
            <ul>
                <li>Invoice 1: No issue found</li>
                <li>Invoice 2: Value in invoice as per AG is 34.90, not 33.90 as reported</li>
            </ul>
            <p><strong>Policy Report:</strong></p>
            <ul>
                <li>Invoice 1: Compliant to policy</li>
                <li>Invoice 2: Compliant to policy</li>
            </ul>
            """

        post_comment_to_expense(auth, sheet_id, test_comment)
