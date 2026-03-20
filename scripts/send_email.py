#!/usr/bin/env python3
"""Send an email from kavanainsights@gmail.com via Gmail API."""

import argparse
import base64
import json
import sys
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import os

SCOPES = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.modify"]
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
TOKEN_PATH = os.path.join(DATA_DIR, "gmail_token.json")
CLIENT_SECRET_PATH = os.path.join(DATA_DIR, "client_secret.json")
SENDER = "kavanainsights@gmail.com"


def get_gmail_service():
    """Authenticate and return Gmail API service."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def send_email(to: str, subject: str, body: str, reply_to_message_id: str = None, thread_id: str = None):
    """Send an email, optionally as a reply to an existing thread."""
    service = get_gmail_service()

    message = MIMEText(body)
    message["to"] = to
    message["from"] = SENDER
    message["subject"] = subject

    if reply_to_message_id:
        message["In-Reply-To"] = reply_to_message_id
        message["References"] = reply_to_message_id

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    email_body = {"raw": raw}

    if thread_id:
        email_body["threadId"] = thread_id

    sent = service.users().messages().send(userId="me", body=email_body).execute()
    print(json.dumps({"status": "sent", "message_id": sent["id"], "thread_id": sent.get("threadId")}))


def main():
    parser = argparse.ArgumentParser(description="Send email via Gmail API")
    parser.add_argument("--to", required=True, help="Recipient email address")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--body", required=True, help="Email body text")
    parser.add_argument("--reply-to", help="Message-ID to reply to")
    parser.add_argument("--thread-id", help="Gmail thread ID for threading")
    args = parser.parse_args()

    send_email(args.to, args.subject, args.body, args.reply_to, args.thread_id)


if __name__ == "__main__":
    main()
