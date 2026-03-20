#!/usr/bin/env python3
"""Update reminder tracking state for BCBAs."""

import argparse
import json
import os
from datetime import date, datetime

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
STATE_PATH = os.path.join(DATA_DIR, "reminder_state.json")


def load_state() -> dict:
    """Load current state or return empty default."""
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {"providers": {}, "flagged_for_review": []}


def save_state(state: dict):
    """Save state to disk."""
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


def ensure_provider(state: dict, provider_id: str) -> dict:
    """Ensure provider entry exists in state."""
    if provider_id not in state["providers"]:
        state["providers"][provider_id] = {
            "reminders_this_month": [],
            "paused_until": None,
            "pause_reason": None,
            "current_month": date.today().strftime("%Y-%m"),
        }
    # Reset if new month
    provider = state["providers"][provider_id]
    current_month = date.today().strftime("%Y-%m")
    if provider.get("current_month") != current_month:
        provider["reminders_this_month"] = []
        provider["current_month"] = current_month
        # Check if pause has expired
        if provider.get("paused_until"):
            pause_date = date.fromisoformat(provider["paused_until"])
            if date.today() > pause_date:
                provider["paused_until"] = None
                provider["pause_reason"] = None
    return provider


def main():
    parser = argparse.ArgumentParser(description="Update BCBA reminder state")
    parser.add_argument("--action", required=True, choices=["pause", "unpause", "record_reminder", "flag_review", "status"])
    parser.add_argument("--provider-id", required=True, help="Provider ID")
    parser.add_argument("--until", help="Pause until date (YYYY-MM-DD)")
    parser.add_argument("--note", help="Note for review flag or pause reason")
    args = parser.parse_args()

    state = load_state()
    provider = ensure_provider(state, args.provider_id)

    if args.action == "pause":
        provider["paused_until"] = args.until
        provider["pause_reason"] = args.note or "Paused by agent"
        print(json.dumps({"status": "paused", "provider_id": args.provider_id, "until": args.until}))

    elif args.action == "unpause":
        provider["paused_until"] = None
        provider["pause_reason"] = None
        print(json.dumps({"status": "unpaused", "provider_id": args.provider_id}))

    elif args.action == "record_reminder":
        provider["reminders_this_month"].append({
            "date": date.today().isoformat(),
            "note": args.note or "",
        })
        print(json.dumps({
            "status": "recorded",
            "provider_id": args.provider_id,
            "total_reminders_this_month": len(provider["reminders_this_month"]),
        }))

    elif args.action == "flag_review":
        state["flagged_for_review"].append({
            "provider_id": args.provider_id,
            "date": date.today().isoformat(),
            "note": args.note or "",
        })
        print(json.dumps({"status": "flagged", "provider_id": args.provider_id}))

    elif args.action == "status":
        print(json.dumps({
            "provider_id": args.provider_id,
            "reminders_this_month": len(provider["reminders_this_month"]),
            "last_reminder": provider["reminders_this_month"][-1] if provider["reminders_this_month"] else None,
            "paused_until": provider["paused_until"],
            "pause_reason": provider["pause_reason"],
        }, indent=2))

    save_state(state)


if __name__ == "__main__":
    main()
