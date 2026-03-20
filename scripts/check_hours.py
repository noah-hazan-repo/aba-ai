#!/usr/bin/env python3
"""Query BigQuery for current month BCBA hours and calculate who's behind pace."""

import json
import os
import sys
from datetime import date, timedelta
from google.cloud import bigquery
from google.oauth2 import service_account


MONTHLY_TARGET = 30.0
PROJECT_ID = "total-care-aba-462720"
VIEW = "total-care-aba-462720.silver.billing_vw"
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
SA_KEY_PATH = os.path.join(DATA_DIR, "bq_service_account.json")
STATE_PATH = os.path.join(DATA_DIR, "reminder_state.json")


def business_days_in_range(start: date, end: date) -> int:
    """Count business days (Mon-Fri) between start and end inclusive."""
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            count += 1
        current += timedelta(days=1)
    return count


def get_month_boundaries(today: date) -> tuple[date, date]:
    """Return first and last day of the current month."""
    first = today.replace(day=1)
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return first, last


def main():
    today = date.today()
    month_start, month_end = get_month_boundaries(today)

    credentials = service_account.Credentials.from_service_account_file(
        SA_KEY_PATH, scopes=["https://www.googleapis.com/auth/bigquery"]
    )
    client = bigquery.Client(project=PROJECT_ID, credentials=credentials)

    query = f"""
    SELECT
        employee_id,
        provider_first_name,
        provider_last_name,
        SUM(time_worked_in_hours) AS mtd_hours
    FROM `{VIEW}`
    WHERE service_date >= '{month_start.isoformat()}'
      AND service_date <= '{today.isoformat()}'
      AND provider_type = 'BCBA'
    GROUP BY employee_id, provider_first_name, provider_last_name
    ORDER BY mtd_hours ASC
    """

    results = client.query(query).result()

    state = {}
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            state = json.load(f)

    total_biz_days = business_days_in_range(month_start, month_end)
    elapsed_biz_days = business_days_in_range(month_start, today)
    remaining_biz_days = business_days_in_range(today + timedelta(days=1), month_end)

    expected_pace = (MONTHLY_TARGET / total_biz_days) * elapsed_biz_days if total_biz_days > 0 else 0

    providers = []
    for row in results:
        mtd = float(row.mtd_hours or 0)
        if elapsed_biz_days > 0:
            daily_rate = mtd / elapsed_biz_days
            projected = mtd + (daily_rate * remaining_biz_days)
        else:
            daily_rate = 0
            projected = 0

        hours_needed = max(0, MONTHLY_TARGET - mtd)
        if remaining_biz_days > 0:
            required_daily_rate = hours_needed / remaining_biz_days
        else:
            required_daily_rate = float("inf") if hours_needed > 0 else 0

        if mtd >= MONTHLY_TARGET:
            status = "complete"
        elif projected >= MONTHLY_TARGET:
            status = "on_track"
        elif remaining_biz_days <= 5 and hours_needed > remaining_biz_days * 3:
            status = "critical"
        elif mtd < expected_pace * 0.7:
            status = "behind"
        else:
            status = "slightly_behind"

        pid = str(row.employee_id)
        provider_state = state.get("providers", {}).get(pid, {})
        paused_until = provider_state.get("paused_until")
        is_paused = bool(paused_until and date.fromisoformat(paused_until) >= today)
        reminders_sent = len(provider_state.get("reminders_this_month", []))

        providers.append({
            "provider_id": pid,
            "first_name": row.provider_first_name,
            "last_name": row.provider_last_name,
            "email": f"{row.provider_first_name.lower()}@totalcareaba.com",
            "mtd_hours": round(mtd, 2),
            "projected_hours": round(projected, 2),
            "hours_needed": round(hours_needed, 2),
            "required_daily_rate": round(required_daily_rate, 2),
            "status": status,
            "is_paused": is_paused,
            "paused_until": paused_until if is_paused else None,
            "reminders_sent_this_month": reminders_sent,
        })

    output = {
        "report_date": today.isoformat(),
        "month": today.strftime("%B %Y"),
        "monthly_target": MONTHLY_TARGET,
        "total_business_days": total_biz_days,
        "elapsed_business_days": elapsed_biz_days,
        "remaining_business_days": remaining_biz_days,
        "expected_pace_hours": round(expected_pace, 2),
        "providers": providers,
        "behind_count": sum(1 for p in providers if p["status"] in ("behind", "critical", "slightly_behind")),
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
