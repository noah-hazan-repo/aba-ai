#!/usr/bin/env python3
"""Check kavanainsights@gmail.com inbox for unread replies to hour reminders."""

import base64
import json
import os
import sys
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly", "https://www.googleapis.com/auth/gmail.modify"]
CREDS_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TOKEN_PATH = os.path.join(CREDS_DIR, "gmail_token.json")
CLIENT_SECRET_PATH = os.path.join(CREDS_DIR, "client_secret.json")


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


def get_body(payload) -> str:
    """Extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        if part.get("parts"):
            result = get_body(part)
            if result:
                return result
    return ""


def main():
    service = get_gmail_service()

    # Fetch unread messages in inbox
    results = service.users().messages().list(
        userId="me",
        q="is:unread in:inbox",
        maxResults=20,
    ).execute()

    messages = results.get("messages", [])
    if not messages:
        print(json.dumps({"messages": [], "count": 0}))
        return

    output = []
    for msg_ref in messages:
        msg = service.users().messages().get(userId="me", id=msg_ref["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}

        body = get_body(msg["payload"])

        output.append({
            "message_id": msg["id"],
            "thread_id": msg["threadId"],
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "in_reply_to": headers.get("in-reply-to", ""),
            "body": body[:2000],  # Truncate very long bodies
        })

    print(json.dumps({"messages": output, "count": len(output)}, indent=2))


if __name__ == "__main__":
    main()
