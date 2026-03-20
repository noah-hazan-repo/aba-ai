#!/bin/bash
set -e

echo "=== Kavana Bot Setup ==="
echo ""

# 1. Install OpenClaw
echo "Step 1: Installing OpenClaw..."
if ! command -v openclaw &> /dev/null; then
    npm install -g openclaw
    echo "OpenClaw installed."
else
    echo "OpenClaw already installed."
fi

# 2. Install Python dependencies
echo ""
echo "Step 2: Installing Python dependencies..."
pip3 install -r workspace/scripts/requirements.txt

# 3. Check for Google Cloud credentials
echo ""
echo "Step 3: Checking Google Cloud setup..."
if ! command -v gcloud &> /dev/null; then
    echo "WARNING: gcloud CLI not found. Install it from https://cloud.google.com/sdk/docs/install"
    echo "Then run: gcloud auth application-default login"
else
    echo "gcloud CLI found."
    echo "Make sure you're authenticated: gcloud auth application-default login"
fi

# 4. Check for Gmail credentials
echo ""
echo "Step 4: Gmail API setup..."
if [ ! -f workspace/data/client_secret.json ]; then
    echo "MISSING: workspace/data/client_secret.json"
    echo ""
    echo "To set this up:"
    echo "  1. Go to https://console.cloud.google.com/apis/credentials"
    echo "  2. Select project: total-care-aba-462720"
    echo "  3. Click '+ CREATE CREDENTIALS' > 'OAuth client ID'"
    echo "  4. Application type: 'Desktop app'"
    echo "  5. Name it 'Kavana Bot'"
    echo "  6. Download the JSON and save it as: workspace/data/client_secret.json"
    echo "  7. Enable the Gmail API: https://console.cloud.google.com/apis/library/gmail.googleapis.com"
    echo ""
else
    echo "client_secret.json found."
fi

# 5. First-run Gmail auth (generates token)
echo ""
echo "Step 5: Gmail authentication..."
if [ ! -f workspace/data/gmail_token.json ]; then
    if [ -f workspace/data/client_secret.json ]; then
        echo "Running first-time Gmail auth (browser will open)..."
        python3 workspace/scripts/check_inbox.py || echo "Auth flow complete — re-run if needed."
    else
        echo "Skipping — need client_secret.json first (see Step 4)."
    fi
else
    echo "Gmail token already exists."
fi

# 6. Provider email mapping
echo ""
echo "Step 6: Provider emails..."
echo "Edit workspace/data/provider_emails.json with your BCBA provider_id -> email mappings."

# 7. Initialize data directory
echo ""
echo "Step 7: Initializing data directory..."
mkdir -p workspace/data

# 8. Set up OpenClaw cron jobs
echo ""
echo "Step 8: Setting up cron jobs..."
echo "After OpenClaw gateway is running, add these cron jobs:"
echo ""
echo '  # Daily hours check at 8am ET'
echo '  openclaw cron add \'
echo '    --name "daily-hours-check" \'
echo '    --cron "0 8 * * 1-5" \'
echo '    --tz "America/New_York" \'
echo '    --session "session:kavana-hours" \'
echo '    --message "Run the daily hours check. Query BigQuery, review results, and send reminders to BCBAs who are behind pace. Check reminder_state.json before sending to avoid duplicates and respect pauses."'
echo ""
echo '  # Inbox monitoring every 10 minutes'
echo '  openclaw cron add \'
echo '    --name "inbox-monitor" \'
echo '    --cron "*/10 6-20 * * 1-5" \'
echo '    --tz "America/New_York" \'
echo '    --session "session:kavana-inbox" \'
echo '    --message "Check the inbox for new unread emails. Process each reply appropriately — acknowledge, respond, pause reminders, or flag for review as needed. Mark processed emails as read."'
echo ""

echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Complete Gmail API setup (Step 4 above if not done)"
echo "  2. Populate workspace/data/provider_emails.json"
echo "  3. Start OpenClaw: openclaw gateway start"
echo "  4. Add the cron jobs (Step 8 commands above)"
