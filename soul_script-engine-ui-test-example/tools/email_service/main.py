import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, validator

# Import your Tools class from webui
from webui import Tools

# Initialize FastAPI app
app = FastAPI(title="Email Service", description="Local email sending service with multi-account support")

# Initialize Tools instance with your config path
_THIS_DIR = Path(__file__).resolve().parent
CONFIG_PATH = str(_THIS_DIR / "email.env")
tools = Tools(config_path=CONFIG_PATH)

# Path to agent-runtime settings for account lookup
_RUNTIME_SETTINGS = _THIS_DIR.parent.parent / "config" / "settings.json"


def _load_runtime_accounts():
    """Load email accounts from agent-runtime settings.json."""
    if not _RUNTIME_SETTINGS.exists():
        return []
    try:
        with open(_RUNTIME_SETTINGS, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tool_config", {}).get("email", {}).get("accounts", [])
    except Exception:
        return []


# Pydantic model for request validation
class EmailRequest(BaseModel):
    subject: str
    body: str
    recipients: List[str]
    account_id: Optional[str] = None
    from_email: Optional[str] = None
    password: Optional[str] = None
    smtp_server: Optional[str] = None
    smtp_port: Optional[int] = None
    signature: Optional[str] = None

    @validator('subject')
    def subject_non_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Subject cannot be empty')
        return v.strip()

    @validator('body')
    def body_non_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Body cannot be empty')
        return v.strip()

    @validator('recipients')
    def recipients_non_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Recipients list cannot be empty')
        return v


def _send_with_credentials(
    email_addr: str, password: str, smtp_server: str, smtp_port: int,
    subject: str, body: str, recipients: List[str],
    signature: str = "", display_name: str = ""
) -> dict:
    """Send email using explicit credentials."""
    full_body = body
    if signature:
        full_body += f"\n\n--\n{signature}"

    msg = MIMEMultipart()
    if display_name:
        msg["From"] = f"{display_name} <{email_addr}>"
    else:
        msg["From"] = email_addr
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(full_body, "plain"))

    if smtp_port == 587:
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
        server.ehlo()
        server.starttls()
    else:
        server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)

    server.login(email_addr, password)
    server.sendmail(email_addr, recipients, msg.as_string())
    server.quit()

    return {
        "status": "ok",
        "message": f"Email sent successfully from {email_addr}",
        "details": {
            "from": email_addr,
            "subject": subject,
            "recipients": recipients,
        }
    }


@app.post("/send_email")
async def send_email(email_request: EmailRequest):
    """
    Send email endpoint.  Supports:
      1. Explicit credentials in the request body (from_email, password, smtp_*)
      2. account_id referencing an agent-runtime saved account
      3. Fallback to the .env configured account
    """
    try:
        # Option 1: Explicit credentials in request
        if email_request.from_email and email_request.password:
            result = _send_with_credentials(
                email_addr=email_request.from_email,
                password=email_request.password,
                smtp_server=email_request.smtp_server or "smtp.gmail.com",
                smtp_port=email_request.smtp_port or 465,
                subject=email_request.subject,
                body=email_request.body,
                recipients=email_request.recipients,
                signature=email_request.signature or "",
            )
            return result

        # Option 2: account_id lookup from agent-runtime settings
        if email_request.account_id:
            accounts = _load_runtime_accounts()
            acct = next((a for a in accounts if a.get("id") == email_request.account_id), None)
            if not acct:
                raise HTTPException(status_code=404, detail=f"Account {email_request.account_id} not found")
            result = _send_with_credentials(
                email_addr=acct["email"],
                password=acct["password"],
                smtp_server=acct.get("smtp_server", "smtp.gmail.com"),
                smtp_port=int(acct.get("smtp_port", 465)),
                subject=email_request.subject,
                body=email_request.body,
                recipients=email_request.recipients,
                signature=acct.get("signature", ""),
                display_name=acct.get("label", ""),
            )
            return result

        # Option 3: Fallback to .env configured account via Tools class
        result = tools.send_email(
            subject=email_request.subject,
            body=email_request.body,
            recipients=email_request.recipients
        )
        if "successfully" in result.lower():
            return {
                "status": "ok",
                "message": "Email sent successfully",
                "details": {
                    "subject": email_request.subject,
                    "recipients": email_request.recipients,
                    "result": result
                }
            }
        else:
            raise HTTPException(status_code=500, detail=f"Failed to send email: {result}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "Email service is running", "multi_account": True}


@app.get("/server-status")
async def server_status():
    """Check server configuration"""
    try:
        has_credentials = bool(tools.valves.FROM_EMAIL and tools.valves.PASSWORD)
        accounts = _load_runtime_accounts()

        return {
            "server_configured": has_credentials or len(accounts) > 0,
            "from_email": tools.valves.FROM_EMAIL if has_credentials else "Not configured",
            "smtp_server": tools.valves.SMTP_SERVER,
            "smtp_port": tools.valves.SMTP_PORT,
            "using_tools_class": True,
            "runtime_accounts": len(accounts),
        }
    except Exception as e:
        return {
            "server_configured": False,
            "error": str(e),
            "using_tools_class": True
        }


@app.get("/accounts")
async def list_accounts():
    """List available accounts from agent-runtime settings."""
    accounts = _load_runtime_accounts()
    # Mask passwords
    safe = []
    for acct in accounts:
        a = dict(acct)
        a["password"] = "••••••••" if a.get("password") else ""
        safe.append(a)
    return {"accounts": safe, "total": len(safe)}


@app.get("/tools-status")
async def tools_status():
    """Check Tools class configuration"""
    try:
        return {
            "tools_initialized": True,
            "from_email": tools.valves.FROM_EMAIL,
            "smtp_server": tools.valves.SMTP_SERVER,
            "smtp_port": tools.valves.SMTP_PORT,
            "config_path": CONFIG_PATH
        }
    except Exception as e:
        return {
            "tools_initialized": False,
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)