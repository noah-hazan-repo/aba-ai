#!/usr/bin/env python3
"""Inbox monitor: check for replies, use Claude to interpret and respond."""

import json
import os
import sys
from datetime import date

import anthropic

sys.path.insert(0, os.path.dirname(__file__))
from check_inbox import main as get_inbox
from send_email import send_email, get_gmail_service
from update_state import load_state, save_state, ensure_provider
from mark_read import get_gmail_service as get_mark_service

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def capture_inbox() -> dict:
    """Run check_inbox and capture the JSON output."""
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        get_inbox()
    raw = f.getvalue()
    lines = raw.split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("{"))
    return json.loads("\n".join(lines[start:]))


def mark_as_read(message_id: str):
    """Mark a Gmail message as read."""
    service = get_gmail_service()
    service.users().messages().modify(
        userId="me",
        id=message_id,
        body={"removeLabelIds": ["UNREAD"]},
    ).execute()


def process_reply(message: dict, state: dict) -> dict | None:
    """Use Claude to interpret a reply and decide on action."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are Kavana, the operations assistant for Total Care ABA. You sent BCBA providers email reminders about their monthly billing hours (target: 30 hrs/month). Someone has replied.

Analyze this email and decide how to respond.

From: {message['from']}
Subject: {message['subject']}
Date: {message['date']}
Body:
{message['body'][:1500]}

Determine:
1. Is this a human reply to one of our reminders, or is it spam/marketing/automated?
2. If human reply, what's the appropriate response?

Categories:
- "sessions_scheduled": They say they have sessions coming up → acknowledge positively
- "pto_leave": They're on PTO, sick, or leave → acknowledge, note return date if given
- "billing_issue": Hours aren't showing correctly → suggest contacting supervisor or billing team
- "need_help": Need more clients/sessions → suggest reaching out to clinical director
- "frustrated": Unhappy about reminders → apologize, explain purpose briefly, flag for review
- "out_of_office": Auto-reply → note return date
- "acknowledgment": Simple "ok" / "thanks" / "got it" → no response needed
- "not_a_reply": Spam, marketing, automated email, not related to our reminders → ignore
- "other": Anything else → provide helpful response, flag for review

Return JSON:
{{
  "category": "one of the categories above",
  "is_reply_to_reminder": true/false,
  "needs_response": true/false,
  "response_subject": "Re: ...",
  "response_body": "response text if needed",
  "should_pause": true/false,
  "pause_until": "YYYY-MM-DD or null",
  "should_flag_review": true/false,
  "flag_note": "note for human review if flagged"
}}

Return ONLY the JSON, no other text."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])
    return json.loads(text)


def extract_sender_email(from_header: str) -> str:
    """Extract email address from 'Name <email>' format."""
    if "<" in from_header:
        return from_header.split("<")[1].rstrip(">").strip()
    return from_header.strip()


def main():
    print(f"Checking inbox at {date.today().isoformat()}...")
    inbox = capture_inbox()
    messages = inbox.get("messages", [])

    if not messages:
        print("No unread messages.")
        return

    print(f"Found {len(messages)} unread messages.")
    state = load_state()

    for msg in messages:
        sender = extract_sender_email(msg["from"])
        print(f"\n  Processing: {msg['subject']} (from {sender})")

        try:
            action = process_reply(msg, state)
        except Exception as e:
            print(f"    ERROR interpreting message: {e}")
            continue

        print(f"    Category: {action['category']}")

        if not action["is_reply_to_reminder"]:
            print(f"    Not a reply to our reminders — skipping.")
            mark_as_read(msg["message_id"])
            continue

        # Send response if needed
        if action["needs_response"] and action.get("response_body"):
            try:
                send_email(
                    sender,
                    action["response_subject"],
                    action["response_body"],
                    reply_to_message_id=msg["message_id"],
                    thread_id=msg["thread_id"],
                )
                print(f"    Sent response.")
            except Exception as e:
                print(f"    ERROR sending response: {e}")

        # Pause reminders if needed
        if action.get("should_pause"):
            # Try to find provider by email
            for pid, pdata in state.get("providers", {}).items():
                pass  # We don't have email->provider mapping in state
            # Just log it for now
            print(f"    Pause requested until {action.get('pause_until')} for {sender}")
            state.setdefault("paused_emails", {})[sender] = {
                "until": action.get("pause_until"),
                "reason": action.get("flag_note", "Requested pause"),
            }

        # Flag for review if needed
        if action.get("should_flag_review"):
            state.setdefault("flagged_for_review", []).append({
                "date": date.today().isoformat(),
                "from": sender,
                "subject": msg["subject"],
                "note": action.get("flag_note", ""),
            })
            print(f"    Flagged for human review: {action.get('flag_note')}")

        mark_as_read(msg["message_id"])
        print(f"    Marked as read.")

    save_state(state)
    print(f"\nDone processing inbox.")


if __name__ == "__main__":
    main()
