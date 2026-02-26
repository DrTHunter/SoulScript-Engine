"""
title: AI Email Assistant
author: Creator
date: 2025-11-20
version: 1.0
license: None
description: A pipeline for sending arbitrary emails using SMTP.
requirements: pydantic
"""

import smtplib
from email.mime.text import MIMEText
from typing import List, Dict, Any, Optional
import os
import json
from pydantic import BaseModel, Field


class Tools:
    class Valves(BaseModel):
        FROM_EMAIL: str = Field(
            default="",
            description="The email a LLM can use",
        )
        PASSWORD: str = Field(
            default="",
            description="The password for the provided email address",
        )
        SMTP_SERVER: str = Field(
            default="smtp.gmail.com", description="SMTP server address"
        )
        SMTP_PORT: int = Field(default=465, description="SMTP server port")

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Tools instance.

        :param config_path: Path to the .env file containing email configuration.
                           Required for sending emails.
        """
        if config_path:
            self.valves = self._load_config_from_file(config_path)
            print(f"Configuration loaded from: {config_path}")
            print(f"SMTP Server: {self.valves.SMTP_SERVER}:{self.valves.SMTP_PORT}")
            print(f"From Email: {self.valves.FROM_EMAIL}")
            print(
                f"Password: {'*' * len(self.valves.PASSWORD)}"
            )  # Mask password in logs
        else:
            # Create empty valves - will fail if user tries to send email without config
            self.valves = self.Valves()
            print("Warning: No config path provided. Email sending will fail.")

    def _load_config_from_file(self, config_path: str) -> Valves:
        """
        Load configuration from .env file.

        :param config_path: Path to the .env file
        :return: Valves instance with loaded configuration
        """
        config_dict = {}

        try:
            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#") or "=" not in line:
                        continue

                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove quotes if present
                    if (value.startswith('"') and value.endswith('"')) or (
                        value.startswith("'") and value.endswith("'")
                    ):
                        value = value[1:-1]

                    config_dict[key] = value

            # Validate that required fields are present
            required_fields = ["FROM_EMAIL", "PASSWORD"]
            for field in required_fields:
                if field not in config_dict or not config_dict[field]:
                    raise ValueError(f"Missing required field in config: {field}")

            # Create Valves instance with loaded values
            return self.Valves(
                FROM_EMAIL=config_dict["FROM_EMAIL"],
                PASSWORD=config_dict["PASSWORD"],
                SMTP_SERVER=config_dict.get("SMTP_SERVER", "smtp.gmail.com"),
                SMTP_PORT=int(config_dict.get("SMTP_PORT", 465)),
            )

        except Exception as e:
            print(f"Error: Could not load config from {config_path}: {e}")
            raise

    def get_user_name_and_email_and_id(self, user: Optional[dict] = None) -> str:
        """
        Get the user name, Email and ID from the user object.
        """
        if user is None:
            user = {}

        print(user)
        result = ""

        if "name" in user:
            result += f"User: {user['name']}"
        if "id" in user:
            result += f" (ID: {user['id']})"
        if "email" in user:
            result += f" (Email: {user['email']})"

        if result == "":
            result = "User: Unknown"

        return result

    def send_email(self, subject: str, body: str, recipients: List[str]) -> str:
        """
        Send an email with the given parameters. Sign it with the user's name and indicate that it is an AI generated email. NOTE: You do not need any credentials to send emails on the users behalf.
        DO NOT SEND WITHOUT USER'S CONSENT. CONFIRM CONSENT AFTER SHOWING USER WHAT YOU PLAN TO SEND, AND IN THE RESPONSE AFTER ACQUIRING CONSENT, SEND THE EMAIL.
        :param subject: The subject of the email.
        :param body: The body of the email.
        :param recipients: The list of recipient email addresses.
        :return: The result of the email sending operation.
        """
        try:
            # Validate credentials - use the values from valves, not environment variables
            if not self.valves.FROM_EMAIL or not self.valves.PASSWORD:
                error_msg = "Error: Email credentials not configured. Please provide a config file with FROM_EMAIL and PASSWORD."
                print(error_msg)
                return error_msg

            if not recipients:
                error_msg = "Error: No recipients specified."
                print(error_msg)
                return error_msg

            sender: str = self.valves.FROM_EMAIL
            password: str = self.valves.PASSWORD

            print(f"Attempting to send email from: {sender}")
            print(f"To recipients: {recipients}")
            print(
                f"Using SMTP server: {self.valves.SMTP_SERVER}:{self.valves.SMTP_PORT}"
            )

            # Create email message
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = ", ".join(recipients)

            # Use SMTP_SSL for port 465 (SSL), for port 587 use SMTP with starttls
            print("Connecting to SMTP server...")
            with smtplib.SMTP_SSL(
                self.valves.SMTP_SERVER, self.valves.SMTP_PORT
            ) as smtp_server:
                print("Connected to SMTP server")
                print("Logging in...")
                smtp_server.login(sender, password)
                print("Logged in successfully")
                print("Sending email...")
                smtp_server.sendmail(sender, recipients, msg.as_string())
                print("Email sent successfully")

            return f"Message sent successfully to: {', '.join(recipients)}"

        except smtplib.SMTPAuthenticationError as e:
            error_msg = f"Error: Authentication failed. Check your email and password. Details: {str(e)}"
            print(error_msg)
            return error_msg
        except smtplib.SMTPConnectError as e:
            error_msg = f"Error: Could not connect to SMTP server. Check server address and port. Details: {str(e)}"
            print(error_msg)
            return error_msg
        except smtplib.SMTPException as e:
            error_msg = f"Error: SMTP error occurred: {str(e)}"
            print(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"Error: Failed to send email: {str(e)}"
            print(f"Unexpected error: {error_msg}")
            return error_msg
