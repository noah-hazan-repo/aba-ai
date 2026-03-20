# Tools

## Scripts

All scripts are in `/workspace/scripts/`. Run them with `python3`.

### check_hours.py
Queries BigQuery for current month BCBA hours. Returns JSON with each provider's status.
No arguments needed.

### send_email.py
Sends an email from kavanainsights@gmail.com.
Args: `--to <email> --subject "<subject>" --body "<body>" [--reply-to <message_id>]`

### check_inbox.py
Fetches unread emails from kavanainsights@gmail.com.
Returns JSON array of messages with sender, subject, body, message_id, thread_id.

### update_state.py
Updates reminder tracking state.
Args: `--action <pause|unpause|record_reminder|flag_review> --provider-id <id> [--until <date>] [--note "<note>"]`

## Data Files

- `/workspace/data/reminder_state.json` — Reminder tracking state
- `/workspace/data/provider_emails.json` — BCBA email addresses (provider_id -> email mapping)
