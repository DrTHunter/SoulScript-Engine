"""Email tool — lets agents send emails via SMTP or a FastAPI email service.

Supports multiple email accounts stored in config/settings.json under
"tool_config.email".  Each account can have its own SMTP credentials,
signature, and be designated as:

  - **default**: the fallback account for outgoing mail
  - **user_email**: the account that belongs to the human operator
  - **agent_default**: automatically used when a specific agent sends mail

Sending modes:
  1. Direct SMTP (preferred) — uses account credentials stored locally.
  2. API relay — forwards through an optional FastAPI email-service backend.

Actions:
  - send:     Send an email (requires subject, body, recipients)
  - status:   List configured accounts and check connectivity
  - accounts: List all configured email accounts
"""

import json
import os
import smtplib
import uuid
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
_DEFAULT_API_BASE_URL = os.environ.get(
    "EMAIL_API_URL", "http://127.0.0.1:8000"
)

_DEFAULT_TIMEOUT = 30  # seconds

# Path to settings file (resolved relative to project root)
_SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "settings.json"


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------

def _load_settings() -> Dict[str, Any]:
    """Load full settings.json."""
    if not _SETTINGS_FILE.exists():
        return {}
    try:
        with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(settings: Dict[str, Any]) -> None:
    """Persist settings.json."""
    _SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)


def _load_tool_config() -> Dict[str, Any]:
    """Load email config from settings.json."""
    return _load_settings().get("tool_config", {}).get("email", {})


def get_effective_config() -> Dict[str, Any]:
    """Return the merged config (defaults + user overrides). Used by the UI."""
    saved = _load_tool_config()
    # Mask passwords in accounts for display
    accounts = saved.get("accounts", [])
    safe_accounts = []
    for acct in accounts:
        a = dict(acct)
        if a.get("password"):
            a["password_set"] = True
            a["password"] = "••••••••"
        else:
            a["password_set"] = False
        safe_accounts.append(a)
    return {
        "api_base_url": saved.get("api_base_url", _DEFAULT_API_BASE_URL),
        "timeout": saved.get("timeout", _DEFAULT_TIMEOUT),
        "require_confirmation": saved.get("require_confirmation", True),
        "accounts": safe_accounts,
    }


# ---------------------------------------------------------------------------
# Account management helpers  (used by API routes and the tool itself)
# ---------------------------------------------------------------------------

def get_accounts() -> List[Dict[str, Any]]:
    """Return all email accounts (passwords masked)."""
    cfg = _load_tool_config()
    accounts = cfg.get("accounts", [])
    # Return copies with masked passwords for display
    safe = []
    for acct in accounts:
        a = dict(acct)
        if a.get("password"):
            a["password_set"] = True
            a["password"] = "••••••••"
        else:
            a["password_set"] = False
        safe.append(a)
    return safe


def get_accounts_raw() -> List[Dict[str, Any]]:
    """Return all email accounts WITH real passwords (internal use only)."""
    cfg = _load_tool_config()
    return cfg.get("accounts", [])


def get_account_by_id(account_id: str) -> Optional[Dict[str, Any]]:
    """Lookup a single account by id (with real password)."""
    for acct in get_accounts_raw():
        if acct.get("id") == account_id:
            return acct
    return None


def get_default_account() -> Optional[Dict[str, Any]]:
    """Return the account marked as default, or the first account."""
    accounts = get_accounts_raw()
    for acct in accounts:
        if acct.get("is_default"):
            return acct
    return accounts[0] if accounts else None


def get_user_account() -> Optional[Dict[str, Any]]:
    """Return the account marked as user_email."""
    for acct in get_accounts_raw():
        if acct.get("is_user_email"):
            return acct
    return None


def get_agent_default_account(agent_name: str) -> Optional[Dict[str, Any]]:
    """Return the account assigned as default for a specific agent."""
    for acct in get_accounts_raw():
        if acct.get("agent_default") == agent_name:
            return acct
    return None


def save_account(account_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update an email account.  Returns the saved account."""
    settings = _load_settings()
    if "tool_config" not in settings:
        settings["tool_config"] = {}
    if "email" not in settings["tool_config"]:
        settings["tool_config"]["email"] = {}
    email_cfg = settings["tool_config"]["email"]
    accounts: list = email_cfg.setdefault("accounts", [])

    acct_id = account_data.get("id")

    # If password field is the masked placeholder, keep the old password
    if account_data.get("password") in ("••••••••", ""):
        for existing in accounts:
            if existing.get("id") == acct_id:
                account_data["password"] = existing.get("password", "")
                break

    if acct_id:
        # Update existing
        for i, existing in enumerate(accounts):
            if existing.get("id") == acct_id:
                accounts[i] = account_data
                break
        else:
            # id provided but not found — treat as new
            accounts.append(account_data)
    else:
        # New account
        account_data["id"] = f"acct_{uuid.uuid4().hex[:8]}"
        accounts.append(account_data)

    # Enforce uniqueness of is_default
    if account_data.get("is_default"):
        for acct in accounts:
            if acct["id"] != account_data["id"]:
                acct["is_default"] = False

    # Enforce uniqueness of is_user_email
    if account_data.get("is_user_email"):
        for acct in accounts:
            if acct["id"] != account_data["id"]:
                acct["is_user_email"] = False

    # Enforce uniqueness of agent_default (one account per agent)
    agent = account_data.get("agent_default", "")
    if agent:
        for acct in accounts:
            if acct["id"] != account_data["id"] and acct.get("agent_default") == agent:
                acct["agent_default"] = ""

    _save_settings(settings)
    return account_data


def delete_account(account_id: str) -> bool:
    """Delete an email account by id.  Returns True if found and deleted."""
    settings = _load_settings()
    email_cfg = settings.get("tool_config", {}).get("email", {})
    accounts: list = email_cfg.get("accounts", [])
    new_accounts = [a for a in accounts if a.get("id") != account_id]
    if len(new_accounts) == len(accounts):
        return False
    email_cfg["accounts"] = new_accounts
    settings.setdefault("tool_config", {})["email"] = email_cfg
    _save_settings(settings)
    return True


# ---------------------------------------------------------------------------
# Direct SMTP sending
# ---------------------------------------------------------------------------

def _send_via_smtp(
    account: Dict[str, Any],
    subject: str,
    body: str,
    recipients: List[str],
    append_signature: bool = True,
) -> str:
    """Send email directly via SMTP using account credentials."""
    email_addr = account.get("email", "")
    password = account.get("password", "")
    smtp_server = account.get("smtp_server", "smtp.gmail.com")
    smtp_port = int(account.get("smtp_port", 465))
    signature = account.get("signature", "")
    display_name = account.get("label", "")

    if not email_addr or not password:
        return json.dumps({"error": "Account credentials incomplete (missing email or password)."})

    # Build message body with optional signature
    full_body = body
    if append_signature and signature:
        full_body += f"\n\n--\n{signature}"

    msg = MIMEMultipart()
    if display_name:
        msg["From"] = f"{display_name} <{email_addr}>"
    else:
        msg["From"] = email_addr
    msg["To"] = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(full_body, "plain"))

    try:
        if smtp_port == 587:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=30)

        server.login(email_addr, password)
        server.sendmail(email_addr, recipients, msg.as_string())
        server.quit()

        return json.dumps({
            "status": "sent",
            "message": f"Email sent successfully from {email_addr}.",
            "details": {
                "from": email_addr,
                "subject": subject,
                "recipients": recipients,
            },
        })
    except smtplib.SMTPAuthenticationError as e:
        return json.dumps({"error": f"Authentication failed for {email_addr}: {e}"})
    except smtplib.SMTPException as e:
        return json.dumps({"error": f"SMTP error: {e}"})
    except Exception as e:
        return json.dumps({"error": f"Failed to send email: {e}"})


# ---------------------------------------------------------------------------
# Tool class (follows runtime tool protocol)
# ---------------------------------------------------------------------------

class EmailTool:
    """Send emails through configured email accounts (SMTP or API relay)."""

    def __init__(self):
        self._session = requests.Session()

    @staticmethod
    def definition() -> Dict[str, Any]:
        return {
            "name": "email",
            "description": (
                "Send emails through configured email accounts. "
                "Use action 'send' to compose and send an email. "
                "Use action 'status' to check configured accounts and server health. "
                "Use action 'accounts' to list available email accounts. "
                "Always confirm recipient addresses with the user before sending "
                "unless they were explicitly provided."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["send", "status", "accounts"],
                        "description": (
                            "'send' — compose and send an email. "
                            "'status' — check email configuration and server health. "
                            "'accounts' — list available email accounts."
                        ),
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line (required for 'send').",
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body text (required for 'send').",
                    },
                    "recipients": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "List of recipient email addresses (required for 'send'). "
                            "Must be valid email addresses."
                        ),
                    },
                    "account_id": {
                        "type": "string",
                        "description": (
                            "Optional: ID of the email account to send from. "
                            "If omitted, uses the agent's default account, "
                            "then the global default, then the first account."
                        ),
                    },
                    "confirmation": {
                        "type": "string",
                        "description": (
                            "When require_confirmation is enabled, set this to 'confirmed' "
                            "after the user has approved the email content and recipients. "
                            "First call send without this field to preview, then call again "
                            "with confirmation='confirmed' to actually send."
                        ),
                    },
                },
                "required": ["action"],
            },
        }

    def execute(self, arguments: Dict[str, Any], agent_name: str = "") -> str:
        action = arguments.get("action", "status")

        if action == "status":
            return self._check_status()
        elif action == "send":
            return self._send_email(arguments, agent_name=agent_name)
        elif action == "accounts":
            return self._list_accounts()
        else:
            return json.dumps({"error": f"Unknown action: {action}"})

    # ---- accounts listing ----
    def _list_accounts(self) -> str:
        """List all configured email accounts (passwords masked)."""
        accounts = get_accounts()
        if not accounts:
            return json.dumps({
                "accounts": [],
                "message": "No email accounts configured. Add accounts in the Tools page.",
            })
        return json.dumps({"accounts": accounts, "total": len(accounts)})

    # ---- status ----
    def _check_status(self) -> str:
        """Check email accounts and optional API server health."""
        cfg = get_effective_config()
        base_url = cfg["api_base_url"]
        timeout = cfg["timeout"]
        accounts = get_accounts()

        result: Dict[str, Any] = {
            "accounts_configured": len(accounts),
            "accounts": accounts,
        }

        # Check optional API server connectivity
        try:
            resp = self._session.get(f"{base_url}/", timeout=timeout)
            resp.raise_for_status()
            result["api_server_running"] = True
            result["api_server_url"] = base_url
        except Exception:
            result["api_server_running"] = False
            result["api_server_note"] = (
                "API relay server not running (not required — "
                "emails are sent directly via SMTP when accounts are configured)."
            )

        return json.dumps(result)

    # ---- send ----
    def _send_email(self, arguments: Dict[str, Any], agent_name: str = "") -> str:
        """Send an email using the best available account."""
        subject = (arguments.get("subject") or "").strip()
        body = (arguments.get("body") or "").strip()
        recipients = arguments.get("recipients", [])
        account_id = (arguments.get("account_id") or "").strip()
        confirmation = (arguments.get("confirmation") or "").strip().lower()

        # Validate required fields
        if not subject:
            return json.dumps({"error": "Email subject is required."})
        if not body:
            return json.dumps({"error": "Email body is required."})
        if not recipients or not isinstance(recipients, list):
            return json.dumps({"error": "At least one recipient email address is required."})

        # Basic email format validation
        invalid = [r for r in recipients if "@" not in r or "." not in r]
        if invalid:
            return json.dumps({
                "error": f"Invalid email address(es): {', '.join(invalid)}",
            })

        # Resolve which account to use
        account = None
        if account_id:
            account = get_account_by_id(account_id)
            if not account:
                return json.dumps({"error": f"Email account '{account_id}' not found."})
        else:
            # Try agent default → global default → first account
            if agent_name:
                account = get_agent_default_account(agent_name)
            if not account:
                account = get_default_account()

        if not account:
            return json.dumps({
                "error": "No email accounts configured. Add an account in the Tools page.",
            })

        # Confirmation gate
        cfg = get_effective_config()
        if cfg.get("require_confirmation", True) and confirmation != "confirmed":
            preview_from = account.get("email", "unknown")
            sig = account.get("signature", "")
            return json.dumps({
                "gate": "awaiting_confirmation",
                "message": (
                    "Email ready to send. Please confirm with the user before sending. "
                    "Show them the details below, and if approved, call this tool again "
                    "with confirmation='confirmed'."
                ),
                "preview": {
                    "from_account": account.get("label", preview_from),
                    "from_email": preview_from,
                    "subject": subject,
                    "body": body,
                    "recipients": recipients,
                    "signature": sig if sig else "(none)",
                },
            })

        # ── Send via direct SMTP (preferred) ──
        return _send_via_smtp(account, subject, body, recipients)

    # ---- legacy API relay (fallback) ----
    def _send_via_api(self, subject: str, body: str, recipients: List[str]) -> str:
        """Fallback: send through the FastAPI email service."""
        cfg = get_effective_config()
        base_url = cfg["api_base_url"]
        timeout = cfg["timeout"]

        try:
            self._session.get(f"{base_url}/", timeout=timeout)
        except requests.exceptions.ConnectionError:
            return json.dumps({
                "error": f"Cannot connect to email server at {base_url}.",
            })

        payload = {"subject": subject, "body": body, "recipients": recipients}
        try:
            resp = self._session.post(
                f"{base_url}/send_email",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            if resp.status_code == 200:
                return json.dumps({
                    "status": "sent",
                    "message": "Email sent successfully via API relay.",
                    "details": resp.json(),
                })
            else:
                detail = "Unknown error"
                try:
                    detail = resp.json().get("detail", detail)
                except Exception:
                    detail = resp.text[:200]
                return json.dumps({
                    "status": "failed",
                    "error": f"Failed to send email: {detail}",
                    "http_status": resp.status_code,
                })
        except requests.exceptions.Timeout:
            return json.dumps({"error": f"Email server timed out after {timeout}s."})
        except Exception as exc:
            return json.dumps({"error": f"Error sending email: {str(exc)}"})
