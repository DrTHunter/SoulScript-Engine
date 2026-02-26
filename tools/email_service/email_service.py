import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, validator
import uvicorn

# Pydantic models for Tools class
class ToolsValves(BaseModel)
    FROM_EMAIL str = Field(
        default=,
        description=The email a LLM can use,
    )
    PASSWORD str = Field(
        default=,
        description=The password for the provided email address,
    )
    SMTP_SERVER str = Field(
        default=smtp.gmail.com, description=SMTP server address
    )
    SMTP_PORT int = Field(default=465, description=SMTP server port)

class Tools
    def __init__(self, config_path Optional[str] = None)
        
        Initialize Tools instance.

        param config_path Path to the .env file containing email configuration.
                           Required for sending emails.
        
        if config_path
            self.valves = self._load_config_from_file(config_path)
            print(fConfiguration loaded from {config_path})
            print(fSMTP Server {self.valves.SMTP_SERVER}{self.valves.SMTP_PORT})
            print(fFrom Email {self.valves.FROM_EMAIL})
            print(
                fPassword {''  len(self.valves.PASSWORD)}
            )  # Mask password in logs
        else
            # Create empty valves - will fail if user tries to send email without config
            self.valves = ToolsValves()
            print(Warning No config path provided. Email sending will fail.)

    def _load_config_from_file(self, config_path str) - ToolsValves
        
        Load configuration from .env file.

        param config_path Path to the .env file
        return Valves instance with loaded configuration
        
        config_dict = {}

        try
            with open(config_path, r) as f
                for line in f
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith(#) or = not in line
                        continue

                    key, value = line.split(=, 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('') and value.endswith('')) or (
                        value.startswith(') and value.endswith(')
                    )
                        value = value[1-1]

                    config_dict[key] = value

            # Validate that required fields are present
            required_fields = [FROM_EMAIL, PASSWORD]
            for field in required_fields
                if field not in config_dict or not config_dict[field]
                    raise ValueError(fMissing required field in config {field})

            # Create Valves instance with loaded values
            return ToolsValves(
                FROM_EMAIL=config_dict[FROM_EMAIL],
                PASSWORD=config_dict[PASSWORD],
                SMTP_SERVER=config_dict.get(SMTP_SERVER, smtp.gmail.com),
                SMTP_PORT=int(config_dict.get(SMTP_PORT, 465)),
            )

        except Exception as e
            print(fError Could not load config from {config_path} {e})
            raise

    def get_user_name_and_email_and_id(self, user Optional[dict] = None) - str
        
        Get the user name, Email and ID from the user object.
        
        if user is None
            user = {}

        print(user)
        result = 

        if name in user
            result += fUser {user['name']}
        if id in user
            result += f (ID {user['id']})
        if email in user
            result += f (Email {user['email']})

        if result == 
            result = User Unknown

        return result

    def send_email(self, subject str, body str, recipients List[str]) - str
        """
        Send an email with the given parameters.

        Sign it with the user's name and indicate that it is an AI-generated email.
        NOTE: You do not need any credentials to send emails on the user's behalf.
        DO NOT SEND WITHOUT USER'S CONSENT. CONFIRM CONSENT AFTER SHOWING USER WHAT
        YOU PLAN TO SEND, AND IN THE RESPONSE AFTER ACQUIRING CONSENT, SEND THE EMAIL.

        :param subject: The subject of the email.
        :param body: The body of the email.
        :param recipients: The list of recipient email addresses.
        :return: The result of the email sending operation.
        """
        try
            # Validate credentials - use the values from valves, not environment variables
            if not self.valves.FROM_EMAIL or not self.valves.PASSWORD
                error_msg = Error Email credentials not configured. Please provide a config file with FROM_EMAIL and PASSWORD.
                print(error_msg)
                return error_msg

            if not recipients
                error_msg = Error No recipients specified.
                print(error_msg)
                return error_msg

            sender str = self.valves.FROM_EMAIL
            password str = self.valves.PASSWORD

            print(fAttempting to send email from {sender})
            print(fTo recipients {recipients})
            print(
                fUsing SMTP server {self.valves.SMTP_SERVER}{self.valves.SMTP_PORT}
            )

            # Create email message
            msg = MIMEText(body)
            msg[Subject] = subject
            msg[From] = sender
            msg[To] = , .join(recipients)

            # Use SMTP_SSL for port 465 (SSL), for port 587 use SMTP with starttls
            print(Connecting to SMTP server...)
            with smtplib.SMTP_SSL(
                self.valves.SMTP_SERVER, self.valves.SMTP_PORT
            ) as smtp_server
                print(Connected to SMTP server)
                print(Logging in...)
                smtp_server.login(sender, password)
                print(Logged in successfully)
                print(Sending email...)
                smtp_server.sendmail(sender, recipients, msg.as_string())
                print(Email sent successfully)

            return fMessage sent successfully to {', '.join(recipients)}

        except smtplib.SMTPAuthenticationError as e
            error_msg = fError Authentication failed. Check your email and password. Details {str(e)}
            print(error_msg)
            return error_msg
        except smtplib.SMTPConnectError as e
            error_msg = fError Could not connect to SMTP server. Check server address and port. Details {str(e)}
            print(error_msg)
            return error_msg
        except smtplib.SMTPException as e
            error_msg = fError SMTP error occurred {str(e)}
            print(error_msg)
            return error_msg
        except Exception as e
            error_msg = fError Failed to send email {str(e)}
            print(fUnexpected error {error_msg})
            return error_msg

# FastAPI Application
app = FastAPI(title=Email Service, description=Local email sending service)

# Initialize Tools instance with your config path
CONFIG_PATH = Path(r"C:\Users\user\OneDrive\Desktop\Library\Orion Forge\tools\email.env")
tools = Tools(config_path=CONFIG_PATH)

# Pydantic model for request validation
class EmailRequest(BaseModel)
    subject str
    body str
    recipients List[str]

    @validator('subject')
    def subject_non_empty(cls, v)
        if not v or not v.strip()
            raise ValueError('Subject cannot be empty')
        return v.strip()

    @validator('body')
    def body_non_empty(cls, v)
        if not v or not v.strip()
            raise ValueError('Body cannot be empty')
        return v.strip()

    @validator('recipients')
    def recipients_non_empty(cls, v)
        if not v or len(v) == 0
            raise ValueError('Recipients list cannot be empty')
        return v

@app.post(send_email)
async def send_email(email_request EmailRequest)
    
    Send email endpoint that accepts subject, body, and recipients list.
    
    try
        # Send email using your Tools class
        result = tools.send_email(
            subject=email_request.subject,
            body=email_request.body,
            recipients=email_request.recipients
        )
        
        # Check if the email was sent successfully
        if successfully in result.lower()
            return {
                status ok,
                message Email sent successfully,
                details {
                    subject email_request.subject,
                    recipients email_request.recipients,
                    result result
                }
            }
        else
            raise HTTPException(
                status_code=500, 
                detail=fFailed to send email {result}
            )
            
    except HTTPException
        raise
    except Exception as e
        raise HTTPException(
            status_code=500, 
            detail=fUnexpected error {str(e)}
        )

@app.get()
async def root()
    Health check endpoint
    return {status Email service is running}

@app.get(server-status)
async def server_status()
    Check server configuration
    try
        # Check if tools are properly configured
        has_credentials = bool(tools.valves.FROM_EMAIL and tools.valves.PASSWORD)
        
        return {
            server_configured has_credentials,
            from_email tools.valves.FROM_EMAIL if has_credentials else Not configured,
            smtp_server tools.valves.SMTP_SERVER,
            smtp_port tools.valves.SMTP_PORT,
            using_tools_class True
        }
    except Exception as e
        return {
            server_configured False,
            error str(e),
            using_tools_class True
        }

@app.get(tools-status)
async def tools_status()
    Check Tools class configuration
    try
        return {
            tools_initialized True,
            from_email tools.valves.FROM_EMAIL,
            smtp_server tools.valves.SMTP_SERVER,
            smtp_port tools.valves.SMTP_PORT,
            config_path CONFIG_PATH
        }
    except Exception as e
        return {
            tools_initialized False,
            error str(e)
        }

if __name__ == __main__
    uvicorn.run(app, host=127.0.0.1, port=8000)