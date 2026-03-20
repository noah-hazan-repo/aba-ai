#!/usr/bin/env python3
"""Mark Gmail messages as read after processing."""

import argparse
import json
import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CREDS_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
TOKEN_PATH = os.path.join(CREDS_DIR, "gmail_token.json")
CLIENT_SECRET_PATH = os.path.join(CREDS_DIR, "client_secret.json")


def get_gmail_service():
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message-id", required=True, help="Gmail message ID to mark as read")
    args = parser.parse_args()

    service = get_gmail_service()
    service.users().messages().modify(
        userId="me",
        id=args.message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()

    print(json.dumps({"status": "marked_read", "message_id": args.message_id}))


if __name__ == "__main__":
    main()
