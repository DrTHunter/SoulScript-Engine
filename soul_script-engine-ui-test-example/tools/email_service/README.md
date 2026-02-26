# Email Service — SMTP Email Relay (Local Python)

**Required by:** `email` tool  
**Default URL:** `http://127.0.0.1:8000`  
**Type:** Local FastAPI service (no Docker required)

---

## What is it?

A lightweight FastAPI service that sends emails via SMTP on behalf of the
agents. It reads email account credentials from the main runtime config
(`config/settings.json`) and supports multi-account sending.

The `email` tool in the runtime can also send directly via SMTP without
this relay, but the relay can be useful for running email as a standalone
microservice or from the included WebUI.

---

## Setup

### 1. Install dependencies

```bash
cd tools/email_service
pip install -r requirements.txt
```

### 2. Configure accounts

Email accounts are managed from the **Dashboard → Tools → Email Accounts**
panel. They are stored in `config/settings.json` under
`tool_config.email.accounts`.

Each account stores:
- **Label** — friendly name (e.g. "Work Gmail")
- **Email address** — the from address
- **Password / App Password** — SMTP credential
- **SMTP server & port** — e.g. `smtp.gmail.com:587`
- **Signature** — appended to outgoing emails
- **Default** — whether this is the default send account
- **User email** — marks one account as the user's primary email
- **Agent default** — assigns an account to a specific agent

> **Gmail users:** generate an [App Password](https://myaccount.google.com/apppasswords)
> (requires 2FA enabled) and use that instead of your regular password.

### 3. Run the service

```bash
cd tools/email_service
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Or use the included batch file (Windows):

```bash
run_email_service.bat
```

### 4. Verify

```bash
curl http://127.0.0.1:8000/docs
```

Opens the auto-generated Swagger UI.

---

## Files

| File | Description |
|------|-------------|
| `main.py` | FastAPI app — routes for sending email |
| `webui.py` | Tools class — SMTP logic, config loading |
| `email_service.py` | Standalone email helper functions |
| `email.env` | Legacy env-based config (fallback) |
| `requirements.txt` | Python dependencies |
| `run_email_service.bat` | Windows batch launcher |
| `tools_webui_original.py` | Original reference implementation |

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/send-email` | POST | Send an email via SMTP |
| `/docs` | GET | Swagger UI |

### Example — Send Email

```bash
curl -X POST http://127.0.0.1:8000/send-email \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Test",
    "body": "Hello from agent-runtime!",
    "recipients": ["someone@example.com"]
  }'
```

---

## Security Notes

- **Never commit `email.env`** — it may contain raw SMTP passwords.
  The `.gitignore` in this folder excludes it.
- Prefer managing accounts via the Dashboard, which stores them in
  `config/settings.json` (also excluded from version control).
- Use App Passwords (not your main password) for Gmail / Google Workspace.
