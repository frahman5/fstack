# Slack Reference — Warmup Notifications

## Purpose

Send warmup run summaries and escalation alerts to a Slack channel. Useful when the accounts belong to a business that already runs on Slack (vs. Telegram which is personal).

## Setup

### Create an incoming webhook
1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**
2. Name it (e.g. "Warmup Monitor"), pick your workspace
3. In the app settings → **Incoming Webhooks** → toggle on → **Add New Webhook to Workspace**
4. Pick the target channel (e.g. `#warmup-alerts`)
5. Copy the webhook URL: `https://hooks.slack.com/services/T.../B.../...`

### Store in env
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../...
```

## Sending messages

Simple text:
```bash
curl -s -X POST "${SLACK_WEBHOOK_URL}" \
  -H "Content-Type: application/json" \
  -d '{"text": "✅ Warmup run complete — 3/4 accounts healthy"}'
```

Rich block message (better formatting):
```bash
curl -s -X POST "${SLACK_WEBHOOK_URL}" \
  -H "Content-Type: application/json" \
  -d '{
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "*✅ Warmup run complete* — 2026-05-03 09:02 UTC\n\n• `@account_one` — Day 8 — 22m — niche 78% ✅\n• `@account_two` — Day 5 — CAPTCHA 🚨\n• `@account_three` — Day 12 — 31m — niche 52% ✅"
        }
      }
    ]
  }'
```

## Python helper

```python
import os, json, urllib.request

def slack_notify(message: str, webhook_url: str | None = None):
    url = webhook_url or os.environ["SLACK_WEBHOOK_URL"]
    payload = json.dumps({"text": message}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req)
```

No extra dependencies — uses stdlib only.

## Routing: Telegram vs Slack

Use **Telegram** for:
- Personal monitoring / escalations that need immediate attention
- The agent sending "I'm stuck, help me" messages

Use **Slack** for:
- Team-visible summaries in a business workspace
- End-of-run reports that a team should see
- When the accounts belong to a separate business with its own Slack
