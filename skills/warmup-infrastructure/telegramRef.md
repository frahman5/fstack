# Telegram Reference — Escalations & Progress Updates

## Purpose

Two use cases:
1. **Escalations** — agent is stuck or needs a human decision, sends a message and stops
2. **Progress updates** — session start/end summaries so you can monitor from your phone

## Setup

### Create a bot (if not already done)
1. Message `@BotFather` on Telegram → `/newbot`
2. Give it a name and username (e.g. `@flooently_escalations_bot`)
3. Copy the bot token: `1234567890:AABBCCDDEEFFaabbccddeeff`

### Get your chat ID
1. Start a conversation with your bot (send it `/start`)
2. Run:
```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | python3 -m json.tool | grep '"id"' | head -5
```
3. The number under `"chat"` → `"id"` is your chat ID

### Store in env
```
TELEGRAM_BOT_TOKEN=1234567890:AABBCCDDEEFFaabbccddeeff
TELEGRAM_CHAT_ID=5043064976
```

## Sending messages

One-liner (use this in scripts and agent instructions):

```bash
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d "chat_id=${TELEGRAM_CHAT_ID}&text=<your message here>"
```

Or hardcode the token/chat_id if you prefer fewer env vars:

```bash
curl -s -X POST "https://api.telegram.org/bot8645212775:AAGY4HuJmSn9d_S9ld9nU5KpGca2_SBF598/sendMessage" \
  -d "chat_id=5043064976&text=🚨 ESCALATION: could not complete session for @flooently_spanish — CAPTCHA appeared"
```

## Escalation protocol for agents

Include this in your agent's system prompt / skill reference:

> When you cannot proceed — CAPTCHA, login failure, missing credentials, ambiguous requirements — send an escalation via Telegram and **stop**. Do not retry in a loop.
>
> ```bash
> curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
>   -d "chat_id=${TELEGRAM_CHAT_ID}&text=🚨 ESCALATION: [what you were doing] | [what broke] | [what's needed]"
> ```

## Progress update format

Good session summary message format (sent at end of each warmup run):

```
✅ Warmup run complete — 2026-05-03 09:02 UTC

@flooently_spanish — Day 8 — 22m — 18 videos — niche 78% ✅
@flooently_portuguese1 — Day 5 — 0m — CAPTCHA 🚨
@flooently_italian — Day 12 — 31m — 24 videos — niche 52% ✅
@flooently_french — Day 3 — 19m — 15 videos — niche 91% ✅
```

## Including screenshots (optional)

To send a screenshot of the browser state along with escalations:

```bash
# Take screenshot via Playwright / Xvfb
SCREENSHOT_PATH=/tmp/escalation.png

curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendPhoto" \
  -F "chat_id=${TELEGRAM_CHAT_ID}" \
  -F "photo=@${SCREENSHOT_PATH}" \
  -F "caption=🚨 Stuck on CAPTCHA for @flooently_spanish"
```
