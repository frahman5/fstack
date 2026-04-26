# Nightly Audit Protocol

> **Portability note:** This skill is shared across repos via `frahman5/fstack`. Never hardcode absolute paths or repo-specific identifiers. Use `git rev-parse --show-toplevel` to find the repo root.

Runs nightly (or on-demand) to check the health of all TikTok warmup accounts and the warmup system. Produces a summary report, sends a Telegram escalation if anything is actionable, and appends a dated entry to `auditLogs.md`.

This is a **read-and-report** workflow, not an execution workflow. It does not launch warmup sessions — that's `/execute-warmups`. The audit's job is to surface problems, gaps, and anomalies so the human can act on them.

---

## Pre-flight

```bash
source "$(git rev-parse --show-toplevel)/.env.cli" 2>/dev/null || true
echo "AIRTABLE_ACCESS_TOKEN: ${AIRTABLE_ACCESS_TOKEN:+SET}"
echo "TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN:+SET}"
echo "TELEGRAM_CHAT_ID: ${TELEGRAM_CHAT_ID:+SET}"
```

If `AIRTABLE_ACCESS_TOKEN` is missing, note it and continue — report what you can from local files. Do not abort.

---

## STEP 1 — Resolve Airtable schema

```bash
source "$(git rev-parse --show-toplevel)/.env.cli" 2>/dev/null || true
eval "$(python3 "$(git rev-parse --show-toplevel)/.agents/skills/tiktok-warmup/resolve_airtable_schema.py" --print-env)" 2>/dev/null
```

If the resolver fails (wrong brand in cwd, token restricted, network blocked), note "Airtable resolver unavailable — proceeding with local cache only" and continue with whatever local files are available (`scripts/warmup/accounts.json`, work logs, etc.).

---

## STEP 2 — Pull active accounts

If Airtable is accessible, query the Accounts table:

```bash
curl -s -G \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  --data-urlencode "filterByFormula=AND({Active}=TRUE())" \
  --data-urlencode "fields[]=Name" \
  --data-urlencode "fields[]=TikTok Username" \
  --data-urlencode "fields[]=Brand" \
  --data-urlencode "fields[]=Warmup Start Date" \
  --data-urlencode "fields[]=Multilogin Profile ID" \
  --data-urlencode "fields[]=TikTok Email" \
  --data-urlencode "fields[]=Paused Until" \
  --data-urlencode "fields[]=Pause Reason" \
  --data-urlencode "fields[]=Search Terms" \
  --data-urlencode "fields[]=Email Recovery" \
  "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE"
```

If Airtable is unavailable, use `scripts/warmup/accounts.json` as the account list and note that live account state is unknown.

For each account compute:
- `warmup_day` = `(today_utc - warmup_start_date).days + 1`
- `warmup_week` = `((warmup_day - 1) // 7) + 1`

---

## STEP 3 — Pull recent session logs

If Airtable is accessible, query Session Log for rows in the last 48h:

```bash
SINCE=$(python3 -c "from datetime import datetime, timedelta, timezone; print((datetime.now(timezone.utc) - timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M:%S.000Z'))")
curl -s -G \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  --data-urlencode "filterByFormula=IS_AFTER({Timestamp UTC}, \"$SINCE\")" \
  --data-urlencode "pageSize=100" \
  --data-urlencode "fields[]=Account Name" \
  --data-urlencode "fields[]=Warmup Day" \
  --data-urlencode "fields[]=Duration (min)" \
  --data-urlencode "fields[]=Error" \
  --data-urlencode "fields[]=FYP Niche %" \
  --data-urlencode "fields[]=Timestamp UTC" \
  "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_SESSION_LOG_TABLE"
```

For each account compute:
- `last_session_utc` — timestamp of the most recent session log row
- `hours_since_last_session` — how long since last session
- `minutes_done_last_24h` — sum of Duration (min) for rows in the last 24h
- `error_sessions_last_24h` — count of rows where Error is non-blank

If Airtable is unavailable, estimate from local files (git log, work logs in `docs/core/workLog/`).

---

## STEP 4 — Audit checks

Run these checks on every active account. Severity levels: **CRITICAL**, **WARN**, **INFO**.

### 4a. Warmup gap check (CRITICAL if > 24h, WARN if 12–24h)

For each account, compute `hours_since_last_session`.

- **> 36h** → CRITICAL: account missed at least one full warmup day
- **24–36h** → WARN: close to missing a day
- **< 24h** → OK

When gap > 36h, also note:
- How many full days were missed (approximately)
- Per `executeWarmupsRef.md`: rest days are waived when days are missed — account can run every day until caught up

### 4b. Account health check

| Check | Severity |
|-------|----------|
| `Search Terms` empty | CRITICAL |
| `Warmup Start Date` empty | CRITICAL |
| `Multilogin Profile ID` empty | WARN |
| `TikTok Email` empty | WARN |
| `Email Recovery` ≠ "Backed Up" | WARN |
| accounts.json `_last_refreshed_utc` > 24h | WARN |

### 4c. System health check

| Check | Severity |
|-------|----------|
| Airtable REST API unreachable | CRITICAL |
| `accounts.json` missing | CRITICAL |
| `AIRTABLE_ACCESS_TOKEN` env var missing | CRITICAL |
| `TELEGRAM_BOT_TOKEN` env var missing | WARN |
| accounts.json stale (> 48h) | WARN |

### 4d. Pending work check

Check for files in `scripts/tmp/` that contain unlogged sessions:
```bash
ls -la "$(git rev-parse --show-toplevel)/scripts/tmp/"
```
If `airtable-pending-logs.md` exists and is non-empty, note it as WARN — sessions may not have been written to Airtable.

### 4e. Warmup trajectory check (INFO)

For each account, report current warmup phase:
- Days 1–5: Silent warmup (no posting)
- Days 6–10: Profile completion + first posts
- Days 11–21: Growth mode (daily posting)
- Days 21+: Ongoing operations

---

## STEP 5 — Compile report

Print a structured summary:

```
🔍 Nightly Warmup Audit — 2026-04-26 06:35 UTC
════════════════════════════════════════════════

🚨 CRITICAL (1):
  - ALL ACCOUNTS: Last warmup run was 2026-04-20 (6 days ago). 5+ missed days per account.
    → Run /execute-warmups immediately. Rest days are waived on missed-day weeks.

⚠️  WARN (2):
  - blazemoney_stables: Auto-login fix pending since 2026-04-20 (noted in workLog). Needs
    tiktok-warmup-poc.py fix before resuming automated sessions.
  - accounts.json stale (2026-04-18T20:50:00Z — 8 days old). Refresh at next run.

ℹ️  INFO (2):
  - scripts/tmp/airtable-pending-logs.md present — Day 3 sessions (2026-04-18/19) may not
    be logged to Airtable Session Log. Review and write if needed.
  - Airtable REST API unreachable from this harness environment (returns "Host not in
    allowlist"). Audit ran on local files only. Investigate token scope or IP allowlist.

📊 Warmup Status (estimates based on local data):
  tiktok,blazemoney_latam      Day 12 wk2 | Last run: Day  6 | Missed: ~5 days
  tiktok,blazemoney_agents     Day 12 wk2 | Last run: Day  6 | Missed: ~5 days
  tiktok,flooently_spanish     Day 11 wk2 | Last run: Day  5 | Missed: ~5 days
  tiktok,flooently_italian     Day 10 wk2 | Last run: Day  4 | Missed: ~5 days
  tiktok,blaze__money          Day  9 wk2 | Last run: Day  3 | Missed: ~5 days
  tiktok,blazemoney_stables    Day  9 wk2 | Last run: Day  3 | Missed: ~5 days ⚠️
  tiktok,flooently_portuguese1 Day  9 wk2 | Last run: Day  3 | Missed: ~5 days
```

---

## STEP 6 — Telegram escalation

Send a Telegram message if there are any CRITICAL or WARN items.

```python
import urllib.request, urllib.parse, json, os

bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

def send_telegram(text):
    if not bot_token or not chat_id:
        print("TELEGRAM credentials missing — skipping notification")
        return
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)
```

Message format (keep short for Telegram):

```
🔥 TikTok Warmup — Nightly Audit 2026-04-26

🚨 CRITICAL: 6-day warmup gap — all 7 accounts. Last run 2026-04-20.
⚠️  WARN: blazemoney_stables auto-login still unresolved.
⚠️  WARN: Airtable REST blocked from harness (host allowlist).

Action: Run /execute-warmups today. Fix stables auto-login first.
```

If no CRITICAL or WARN items: send a brief "✅ All clear" message.

---

## STEP 7 — Write audit log entry

Append a dated entry to `.agents/skills/tiktok-warmup/auditLogs.md` (in the consuming repo, not fstack). Use the format in that file.

---

## STEP 8 — Push findings to fstack (if needed)

If during the audit you identified changes needed in fstack skill files (new selectors, protocol corrections, new runtimeLearnings entries), push them as a PR per the instructions in `SKILL.md`. For small additive changes (≤ 30 lines), the PR can be auto-merged. For larger changes, leave it open for review.

If the only change is appending to `auditLogs.md`, that is a "safe template" change and can be auto-merged.

---

## Hard rules

- **Never delete code or data.** Add only.
- **Never retry a blocked account** (Paused Until > now) — log and skip.
- **When in doubt, escalate to Telegram** rather than silently proceeding.
- **Airtable: REST API only.** See `airtableRef.md`.
- **auditLogs.md lives in the consuming repo** (`.agents/skills/tiktok-warmup/`), not in fstack. It accumulates run history and should not be reset.
