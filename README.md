# aba-ai

BCBA hours monitoring bot powered by OpenClaw. Tracks monthly billing hours from BigQuery and sends email reminders to BCBAs falling behind the 30 hrs/month target.

## Setup

```bash
chmod +x setup.sh
./setup.sh
```

## Prerequisites

- Node.js (for OpenClaw)
- Python 3.10+
- Google Cloud project `total-care-aba-462720` with:
  - BigQuery API enabled
  - Gmail API enabled
  - OAuth desktop credentials for `kavanainsights@gmail.com`
- `gcloud` CLI authenticated (`gcloud auth application-default login`)

## Configuration

1. **Gmail credentials**: Save OAuth client JSON as `workspace/data/client_secret.json`
2. **Provider emails**: Edit `workspace/data/provider_emails.json` with provider_id -> email mappings
3. **BigQuery**: Ensure your gcloud auth has access to `total-care-aba-462720.silver.billing_vw`

## Cron Jobs

After `openclaw gateway start`:

```bash
# Daily hours check (weekdays 8am ET)
openclaw cron add \
  --name "daily-hours-check" \
  --cron "0 8 * * 1-5" \
  --tz "America/New_York" \
  --session "session:kavana-hours" \
  --message "Run the daily hours check. Query BigQuery, review results, and send reminders to BCBAs who are behind pace."

# Inbox monitoring (every 10 min, weekdays 6am-8pm ET)
openclaw cron add \
  --name "inbox-monitor" \
  --cron "*/10 6-20 * * 1-5" \
  --tz "America/New_York" \
  --session "session:kavana-inbox" \
  --message "Check the inbox for new unread emails. Process each reply appropriately."
```

## Architecture

```
BigQuery (billing_vw) --> check_hours.py --> OpenClaw Agent --> send_email.py --> Gmail
                                                  ^
Gmail Inbox --> check_inbox.py -------------------|
                                                  |
                          update_state.py <-------|
```
