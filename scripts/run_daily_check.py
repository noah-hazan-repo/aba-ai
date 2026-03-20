#!/usr/bin/env python3
"""Daily orchestrator: check hours, use Claude to compose reminders, send emails."""

import json
import os
import sys
from datetime import date, timedelta

import anthropic

# Add parent dir so we can import shared helpers
sys.path.insert(0, os.path.dirname(__file__))
from check_hours import main as get_hours_report
from send_email import send_email
from update_state import load_state, save_state, ensure_provider

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")


def capture_hours_report() -> dict:
    """Run check_hours and capture the JSON output."""
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        get_hours_report()
    raw = f.getvalue()
    # Skip any non-JSON prefix lines (warnings)
    lines = raw.split("\n")
    start = next(i for i, l in enumerate(lines) if l.strip().startswith("{"))
    return json.loads("\n".join(lines[start:]))


def compose_reminder(provider: dict, report: dict, state: dict) -> dict | None:
    """Use Claude to compose a personalized reminder email."""
    reminders_sent = provider["reminders_sent_this_month"]
    remaining = report["remaining_business_days"]

    if provider["status"] in ("complete", "on_track"):
        return None
    if provider["is_paused"]:
        return None

    # Check if already reminded today
    provider_state = state.get("providers", {}).get(provider["provider_id"], {})
    reminders = provider_state.get("reminders_this_month", [])
    if reminders and reminders[-1].get("date") == date.today().isoformat():
        return None

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""You are Kavana, the operations assistant for Total Care ABA. Compose a brief, professional email reminder for a BCBA who is behind on their monthly billing hours.

Provider: {provider['first_name']} {provider['last_name']}
Email: {provider['email']}
Month: {report['month']}
Hours so far: {provider['mtd_hours']}
Target: {report['monthly_target']} hours
Hours still needed: {provider['hours_needed']}
Business days remaining: {remaining}
Required daily rate to hit target: {provider['required_daily_rate']} hrs/day
Status: {provider['status']}
Previous reminders this month: {reminders_sent}

Guidelines:
- If this is the first reminder (0 previous), be friendly and low-pressure
- If 1-2 previous reminders, be more specific with numbers
- If status is "critical" or 3+ reminders, be direct but still supportive
- Keep it concise (3-5 sentences in the body)
- Sign off as "Kavana, Total Care ABA Operations"
- Do NOT use emojis

Return JSON with exactly two fields:
{{"subject": "...", "body": "..."}}

Return ONLY the JSON, no other text."""

    response = client.messages.create(
        model="claude-sonnet-4-5-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    # Handle markdown code blocks
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:-1])
    return json.loads(text)


def main():
    today = date.today()
    if today.weekday() >= 5:
        print("Weekend — skipping.")
        return

    print(f"Running daily hours check for {today.isoformat()}...")
    report = capture_hours_report()
    state = load_state()

    behind = [p for p in report["providers"] if p["status"] in ("behind", "critical", "slightly_behind")]
    print(f"Found {len(behind)} BCBAs behind pace out of {len(report['providers'])} total.")

    sent_count = 0
    for provider in behind:
        if provider["is_paused"]:
            print(f"  Skipping {provider['first_name']} {provider['last_name']} (paused until {provider['paused_until']})")
            continue

        if not provider["email"]:
            print(f"  Skipping {provider['first_name']} {provider['last_name']} (no email)")
            continue

        email = compose_reminder(provider, report, state)
        if not email:
            print(f"  Skipping {provider['first_name']} {provider['last_name']} (already reminded today or on track)")
            continue

        try:
            send_email(provider["email"], email["subject"], email["body"])
            ensure_provider(state, provider["provider_id"])
            state["providers"][provider["provider_id"]]["reminders_this_month"].append({
                "date": today.isoformat(),
                "note": email["subject"],
            })
            save_state(state)
            sent_count += 1
            print(f"  Sent reminder to {provider['first_name']} {provider['last_name']} ({provider['email']})")
        except Exception as e:
            print(f"  ERROR sending to {provider['first_name']} {provider['last_name']}: {e}")

    print(f"\nDone. Sent {sent_count} reminders.")


if __name__ == "__main__":
    main()
