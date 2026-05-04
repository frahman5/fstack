# Execute Warmups

> **Portability note:** This skill is shared across multiple repos via `frahman5/fstack`. Keep it repo-agnostic: never hardcode absolute repo paths, never reference `scripts/` directories in any consuming repo. The warmup script (`tiktok-warmup-poc.py`) lives inside this skill directory and is invoked relative to wherever the skill is installed (`.agents/skills/tiktok-warmup/`). The only path that varies per-machine is `.env.cli`, which the script discovers automatically via upward directory walk.

Semi-automated TikTok warmup runner. You (the agent) plan the day, launch sessions, and rely on Faiyam for manual debugging (CAPTCHAs, re-logins, stuck Multilogin profiles). No scheduler, no Airtable "Scheduled Sessions" table — just decide what's needed right now and run it.

**Reference files (read before starting):**

- `.claude/skills/tiktok-warmup/browserWarmupRef.md` — session protocol details
- `.claude/skills/tiktok-warmup/multiloginRef.md` — profile IDs, launcher API
- `.claude/skills/tiktok-warmup/airtableRef.md` — Accounts + Session Log table schemas
- `.claude/skills/tiktok-warmup/runtimeLearnings.md` — operational gotchas (READ THIS, it has hard-won lessons)

---

## Design principles

1. **Target 30–90 min/day per active account**, split into 2–4 sessions of ~15–30 min each. Random per account per day.
2. **Rest days are natural.** In the first 7 days of warmup, each account gets exactly 1 rest day — deterministic hash of `(accountName + weekNumber)` picks which weekday. On a rest day: skip the account entirely.
3. **Concurrent across accounts, sequential within an account.** Different Multilogin profiles don't conflict, so run 2–4 profiles in parallel. For a single account, wait 2–5 minutes between its sessions (natural gap).
4. **Lean on the human.** If anything unexpected happens (CAPTCHA, login failure, profile won't launch, weird modal) — screenshot, describe what you see, ask Faiyam what to do, and wait. Do NOT retry blindly, do NOT silently skip.
5. **Single pass.** One invocation of this command plans and executes today's remaining warmup. When it's done, summarize and exit. Faiyam reruns tomorrow (or later today if they want more).

---

## STEP 0 — Pre-flight environment check

Run this before anything else. If any check fails, stop and tell the user exactly what's broken — do not proceed.

```bash
# 1. .env.cli exists and has required keys
# .env.cli is discovered automatically by tiktok-warmup-poc.py (upward walk from skill dir)
# For manual checks, load it from wherever the consuming repo lives, e.g.:
# source "$(git rev-parse --show-toplevel)/.env.cli"
source "$(git rev-parse --show-toplevel)/.env.cli"
echo "MLX_AUTOMATION_TOKEN: ${MLX_AUTOMATION_TOKEN:0:8}..."
echo "OP_SERVICE_ACCOUNT_TOKEN: ${OP_SERVICE_ACCOUNT_TOKEN:0:8}..."

# 2. 1Password CLI can authenticate and the TikTok vault is accessible
OP_SERVICE_ACCOUNT_TOKEN=$OP_SERVICE_ACCOUNT_TOKEN op vault list --format=json | python3 -c "
import json,sys
vaults=[v['name'] for v in json.load(sys.stdin)]
print('Vaults:', vaults)
assert 'TikTok' in vaults, 'TikTok vault NOT found — OP token is wrong or lacks access'
print('✅ TikTok vault OK')
"

# 3. Multilogin launcher is running
curl -sf https://launcher.mlx.yt:45001/api/v1/profile/statuses -H "Authorization: Bearer $MLX_AUTOMATION_TOKEN" -k > /dev/null && echo "✅ Multilogin launcher OK" || echo "⚠ Multilogin launcher not responding — open the Multilogin desktop app"

# 4. Schema validation — confirm Airtable + Supabase match the canonical schema
python3 "$(git rev-parse --show-toplevel)/.agents/skills/tiktok-warmup/validate_schema.py"
```

**What each check catches:**
- Missing/wrong `OP_SERVICE_ACCOUNT_TOKEN` → auto-login will fail for any logged-out profile
- `TikTok` vault not found → the token is from the wrong 1Password account or lacks vault access (this broke warmups on 2026-04-22 after engineer onboarding split the 1Password accounts)
- Multilogin not running → all profile launches will fail immediately
- Schema validator non-zero exit → Airtable or Supabase has drifted from `canonicalSchema.json`. Drift can cause silent data corruption (e.g., writing to a field that was renamed). The validator prints exactly what to fix; re-run `python3 .../validate_schema.py --apply` for additive Airtable fixes (new fields). Schema type changes and Supabase DDL must be applied manually.

If pre-flight fails, do NOT schedule any sessions. Fix the issue first, then re-invoke `/execute-warmups`.

---

## STEP 1 — Read context

1. Read `runtimeLearnings.md` (it has real bug fixes — do not skip).
2. Read `browserWarmupRef.md` (session mechanics).
3. Read `auditLogs.md` — recent autonomous changes made by the nightly review agent. Skim the last 5 entries. If anything affects today's run (e.g. comment frequency was raised, search-term refresh logic was added), keep that context in mind during execution.
4. Get current UTC time: `date -u +"%Y-%m-%dT%H:%M:%SZ"`.

---

## STEP 2 — Pull active accounts from Airtable

Use the Airtable REST API with `$AIRTABLE_ACCESS_TOKEN` from `.env.cli`. **Never use the Airtable MCP** — see `airtableRef.md` for the canonical reason and API patterns.

First resolve the base and table IDs using the schema resolver:
```bash
source "$(git rev-parse --show-toplevel)/.env.cli"
eval "$(python3 "$(git rev-parse --show-toplevel)/.agents/skills/tiktok-warmup/resolve_airtable_schema.py" --print-env)"
```
This sets `$AIRTABLE_BASE_ID`, `$AIRTABLE_ACCOUNTS_TABLE`, `$AIRTABLE_SESSION_LOG_TABLE`.

Filter for `AND({Active}=TRUE(),{Brand}="$AIRTABLE_BRAND",{Type}!="Manual")`. Pull fields: Name, Brand, Timezone, UTC Offset, Waking Start, Waking End, Warmup Start Date, Multilogin Profile ID, **Paused Until**, **Pause Reason**, **Search Terms** (`fldnFSwwpxVigKXel`), **Type**, **Pending Action** (`fldJFDBUcxR1QOayB`), **Health Score** (`fldnIiB1TpkFOk5Qg`).

**Manual accounts are excluded entirely.** Accounts with `Type = "Manual"` are self-managed by the founder and never included in automated warmup runs. The filter above excludes them at the query level so they never appear in the health audit or plan.

### Pending Actions (from the nightly audit agent)

For each active account, check the `Pending Action` field. If non-empty, surface it prominently in the plan output **before** the daily session list — this is structured guidance from the nightly review agent that should shape today's run. Format:

```
🔔 Pending actions:
   tiktok,flooently_spanish: niche % dropped to 0% on Day 7 — refresh search terms before next run
   tiktok,flooently_italian: 0 comments in 5 days — bump comment frequency to ≥1/session this week
```

**Acting on the pending action:** the executor decides whether the action is auto-executable (e.g. "refresh search terms" → call Claude to regen, write back to Airtable) or requires Faiyam confirmation. If auto-executed, clear the `Pending Action` field via PATCH at the end of that account's run. If surfaced to Faiyam, leave the field in place until a human resolves it.

Print the current `Health Score` in the plan summary as a quick at-a-glance signal (e.g. `wk2, day10, health=82`). The score is updated at the end of each session by the executor (see Step 6).

**Filter out paused accounts immediately.** For each record where `Paused Until` is set and `Paused Until > now_utc`, drop it from the working set and print one line:

```
  Isabella Restrepo: PAUSED until 2026-04-18 02:57 UTC — TikTok login lockout. Skipping.
```

If `Paused Until ≤ now_utc`, the pause has expired — treat the account as normal (and optionally clear the fields via the REST API so the row is tidy).

**Email recovery check.** Also pull the `Email Recovery` field (`fldmySQAr2mZjw6ne`) for each account. For any account where this field is not `"Backed Up"`:
- Print a warning in the plan summary (e.g. `⚠️  Sofia Reyes: email recovery NOT backed up — fix before running`)
- Still include the account in the plan (don't block warmup), but make the warning prominent so Faiyam sees it and can act

Write the filtered-active set to `/tmp/tk_active.json` via Write tool (not heredoc). Do not persist account data anywhere in the repo — all runtime state lives under `/tmp/`. Use this to drive the plan.

**Auto-fill missing Multilogin Profile IDs.** For any active account where `Multilogin Profile ID` is blank:
1. Call `POST https://api.multilogin.com/profile/search` (body `{"search_text":"","is_removed":false,"limit":100,"offset":0}`) with `Authorization: Bearer $MLX_AUTOMATION_TOKEN`.
2. Match profiles by TikTok handle or account name — look for profile names containing the handle (e.g. `blazemoney_latam`) or the account name (e.g. `Sofia Reyes`). Only match profiles with `(TikTok)` in the name or that clearly correspond to a TikTok persona.
3. If a match is found: update the Airtable Accounts record via REST API (`fld9knhdqkuYzwCfJ`) with the found profile ID, then include the account in the plan as normal.
4. If no match is found: print a warning and skip that account (can't automate without a profile).
Run this lookup once per executor invocation, before computing the plan.

---

## STEP 2.5 — Account health audit

Before planning sessions, audit every active account for missing or inconsistent data. Surface issues to the user so they can fix them now rather than discovering them mid-run or (worse) from a silent skip.

Run these checks on each active account pulled from Airtable:

| Check | Severity | Action |
|-------|----------|--------|
| `Search Terms` is empty | **error** | Block this account — the warmup scripts need it. Prompt user to generate terms (see `adoptAccountRef.md` Step 11) |
| `Warmup Start Date` is empty | **error** | Block this account — mode determination needs it. Prompt user to set it |
| `Multilogin Profile ID` is empty | **error** | Block this account — cannot launch without it. Already handled by the auto-fill logic below, surface only if auto-fill also fails |
| `Timezone` is empty | **auto-heal** | Infer from Multilogin proxy country code, update Airtable (see below) |
| `TikTok Email` is empty | **warn** | Account can run but OTP flow will break if a re-login is needed |
| `AgentMail Inbox` is empty | **auto-heal** | Send a test email to the TikTok email via AgentMail, verify receipt, update Airtable if confirmed (see below) |
| `Email Recovery` ≠ "Backed Up" | **warn** | Account can run but recovery is uncertain |
| `Niche Description` is empty | **auto-heal** | Generate from Search Terms via `claude -p` and write back to Airtable (see below) |
| `Active=true` + account just created (< 1 day ago) | **info** | Just a heads-up that it's a brand-new account |

### Auto-healing Timezone

If `Timezone` is empty, infer it from the Multilogin profile's proxy username. The proxy username contains a `country-XX` segment (e.g. `country-br`, `country-mx`) — extract the 2-letter country code and map it to a timezone:

| Code | Timezone | UTC Offset |
|------|----------|------------|
| br | America/Sao_Paulo | -03:00 |
| mx | America/Mexico_City | -06:00 |
| co | America/Bogota | -05:00 |
| ar | America/Argentina/Buenos_Aires | -03:00 |
| ve | America/Caracas | -04:00 |
| pe | America/Lima | -05:00 |
| cl | America/Santiago | -04:00 |
| ec | America/Guayaquil | -05:00 |
| uy | America/Montevideo | -03:00 |
| cr | America/Costa_Rica | -06:00 |
| us | America/New_York | -05:00 |
| gb | Europe/London | +01:00 |
| de | Europe/Berlin | +02:00 |
| fr | Europe/Paris | +02:00 |
| it | Europe/Rome | +02:00 |
| es | Europe/Madrid | +02:00 |
| pt | Europe/Lisbon | +01:00 |

To get the proxy username, call `POST https://api.multilogin.com/profile/search` with the profile ID and read `proxy.username`. Extract country code with a regex: `country-([a-z]{2})`.

Update Airtable with `Timezone`, `UTC Offset`, and `Country` (full name) fields via REST PATCH. Print: `  🔧 auto-healed Timezone for <slug>: America/Sao_Paulo (inferred from proxy country-br)`. If the country code isn't in the table above, fall back to UTC, label it `[UTC — country code unknown]`, and surface a warning.

### Auto-healing AgentMail Inbox (forwarding verification)

If `AgentMail Inbox` is empty but `TikTok Email` is set, test whether that email already forwards to `tiktok@agentmail.to` — and if confirmed, write the field automatically.

**Step 1 — send a test email to the TikTok email address:**

```bash
AGENTMAIL_KEY=$(grep AGENTMAIL_KEY .env.cli | cut -d= -f2-)
curl -s -X POST "https://api.agentmail.to/v0/inboxes/tiktok@agentmail.to/messages/send" \
  -H "Authorization: Bearer $AGENTMAIL_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"to\":[\"$TIKTOK_EMAIL\"],\"subject\":\"AgentMail forwarding test\",\"text\":\"Automated forwarding check. Please ignore.\"}"
```

**Step 2 — wait up to 30s (poll every 5s), checking for the test email in AgentMail:**

```bash
# Look for a recent message in AgentMail where to[] contains TIKTOK_EMAIL
# and subject matches "AgentMail forwarding test" and created_at is within the last 60s
curl -s "https://api.agentmail.to/v0/inboxes/tiktok@agentmail.to/messages?limit=10" \
  -H "Authorization: Bearer $AGENTMAIL_KEY"
```

A message is confirmed if: `to` contains `$TIKTOK_EMAIL`, subject matches, and `created_at` is within the last 60 seconds.

**Step 3 — act on result:**

- **Forwarding confirmed:** update `AgentMail Inbox` field in Airtable to `tiktok@agentmail.to` via REST PATCH, print `  🔧 auto-healed AgentMail Inbox for <slug> (forwarding confirmed)`, treat account as healthy.
- **No message after 30s:** print `  ⚠️  <slug>: AgentMail Inbox missing and forwarding NOT confirmed for <tiktok_email> — set up email forwarding to tiktok@agentmail.to then re-run`. Leave the account in the working set (can still run; OTP flow just won't be automated).

**Note:** The test message sent FROM AgentMail will appear in AgentMail's own sent/inbox because it originated there. Filter for messages where `to[]` contains `$TIKTOK_EMAIL` (not `tiktok@agentmail.to`) to confirm the round-trip forward.

### Auto-healing Niche Description

If `Niche Description` is empty but `Search Terms` is set, generate and save it automatically — no user intervention needed.

```bash
NICHE=$(claude -p --model claude-haiku-4-5-20251001 --bare "Based on these TikTok search terms, write a 1–2 sentence niche description for this account's content focus. Be specific about audience and content style. Terms: <search_terms>")
```

Then write it back via the Airtable REST API:

```bash
curl -s -X PATCH "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE/$RECORD_ID" \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"fields\":{\"Niche Description\":\"$NICHE\"}}"
```

Print one line: `  🔧 auto-healed Niche Description for <slug>` and treat the account as fully healthy. Do this before the audit output block so the final status reflects the healed state.

**Output format** — print a single block summarizing the audit before the plan:

```
📋 Health audit (5 accounts):
   ✅ blazemoney_latam — clean
   ✅ blazemoney_agents — clean
   ⚠️  blazemoney_stables — Email Recovery: Not Set Up
   ❌ blazemoney_crypto — Search Terms missing, Warmup Start Date missing (BLOCKING: this account will be skipped)
   ❌ sofia_reyes — Warmup Start Date missing (BLOCKING)
```

**Handling errors:** accounts with error-level issues should be **removed from the working set** and NOT included in the day's plan. Tell the user explicitly which accounts got skipped and why. Don't silently move on — the user should decide whether to fix-and-rerun or proceed with what's left.

**Handling warnings:** accounts with warning-level issues stay in the working set. Just surface them in the audit output so the user sees them.

---

## STEP 3 — Pull today's Session Log

Query Session Log (`tbluS09ymOa9oBDwA`) for rows where `Timestamp UTC` is within the last 24h. Pull fields: Account Name, Duration (min), Videos Watched, FYP Niche % (`fldQHQm3TFzw1lZBC`), Error.

For each active account, compute:
- `minutes_done_today = sum(Duration (min))` across today's rows
- `daily_niche_pct` = weighted average: `Σ(fyp_niche_pct × videos_watched) / Σ(videos_watched)` — only include rows where `fyp_niche_pct` is set and Error is blank. If no qualifying rows exist, `daily_niche_pct = None`.

---

## STEP 4 — Plan each account

For every active account:

### 4a. Rest day check

**CRITICAL: Skip rest-day accounts. Do NOT run ANY session for an account whose rest day is today.** Rest days are deterministic per `(account_name, weekNumber)` hash — the calculation below tells you the rest day. If you skip this check and run a session on a rest day, you're violating TikTok's recommended cadence and risk the account. Double-check every account's rest day BEFORE adding it to the daily plan.

**Exception — missed days:** The rest day is only enforced if the account actually ran on every prior day of the current week. If the account was skipped on any earlier day this week (e.g. we didn't run warmups that night), the rest day is waived — the account needs to make up the missed time and shouldn't lose another day to rest on top of it.

```python
import hashlib
warmup_day = (today - warmup_start_date).days + 1
warmup_week = (warmup_day - 1) // 7 + 1

# Only enforce rest day in weeks 1-2 (weeks 3+ can run daily if desired)
if warmup_week <= 2:
    week_start = warmup_start_date + timedelta(days=(warmup_week - 1) * 7)
    h = int(hashlib.md5(f"{account_name}-{warmup_week}".encode()).hexdigest(), 16)
    rest_day_offset = h % 7   # 0..6
    rest_date = week_start + timedelta(days=rest_day_offset)
    if today == rest_date:
        # Only enforce rest if the account ran on every prior day this week.
        # "ran" = has at least one Session Log row with a timestamp on that calendar date (UTC).
        days_elapsed_this_week = (today - week_start).days  # number of days before today in this week
        session_dates_this_week = set(
            row["date"]  # date portion of Timestamp UTC field
            for row in session_log_rows
            if row["account_name"] == account_name
            and week_start <= row["date"] < today
        )
        days_with_sessions = len(session_dates_this_week)
        if days_with_sessions >= days_elapsed_this_week:
            # Ran every prior day — rest day stands
            print(f"  {account}: REST DAY (ran all {days_elapsed_this_week} prior days this week) — skip")
            continue
        else:
            # Missed at least one day — waive rest day so the account can make up time
            missed = days_elapsed_this_week - days_with_sessions
            print(f"  {account}: rest day waived — missed {missed} day(s) this week, needs to make up time")
```

### 4b. Decide today's target

Random uniform `30..90` minutes. Seed with `(account_name, today_date)` so the target is stable across reruns of the command on the same day:

```python
import random
rng = random.Random(f"{account_name}-{today_iso}")
daily_target_min = rng.randint(30, 90)
```

### 4c. Compute what's left

```python
remaining_min = max(0, daily_target_min - minutes_done_today)
```

If `remaining_min < 10`, the account is done for the day. Skip.

### 4d. Decide session length(s) for this run

Break `remaining_min` into individual sessions using **human-realistic durations: 2–90 minutes**, log-normally distributed. Most sessions are short (2–15 min quick checks), some are medium (15–35 min), and occasionally one runs long (35–90 min). This reflects how real people use TikTok. Weekly engagement *action* limits (likes, follows, comments, searches) still apply — only duration varies freely.

```python
import random, math

def random_session_duration(rng):
    # Log-normal: median ~10 min, skewed toward shorter, long tail to 90
    raw = rng.lognormvariate(math.log(10), 0.9)
    return max(2, min(90, round(raw)))

def break_into_sessions(remaining_min, account_name, today_iso, session_index=0):
    sessions = []
    rng = random.Random(f"{account_name}-{today_iso}-durations")
    left = remaining_min
    i = session_index
    while left >= 2:
        dur = min(random_session_duration(rng), left)
        sessions.append(dur)
        left -= dur
        i += 1
    return sessions
```

Result per account: `{"account": "...", "sessions_to_run": [{"duration_min": 7}, {"duration_min": 23}, ...], "scheduled_times_utc": [...], "warmup_week": N}`.

### 4e. Finalize session list

Compile the final list of sessions to run this invocation — one ordered queue per account. No RemoteTriggers, no CronCreate — everything runs in the current agent thread (Step 5).

For accounts that have already partially run today (some sessions logged), only include the remaining sessions.

Write the plan to `/tmp/tk_plan.json` and show Faiyam a summary:

Account display format in all plans and summaries: `platform,handle` (e.g. `tiktok,flooently_spanish`). Derived from the `Platform` + `Username` fields in Airtable. The Airtable `Name` field (e.g. "Sebastian Vargas") is the internal record name — never use it in plan output.

```
Plan for 2026-04-18:
  tiktok,flooently_spanish  (wk1, day 3): 40 min left → 4 sessions: 7min@14:30, 12min@16:45, 3min@19:10, 18min@21:00  [America/Costa_Rica local]
  tiktok,flooently_italian  (wk1, day 2): REST DAY — skip
  tiktok,blazemoney_latam   (wk1, day 4): 30 min left → 3 sessions: 5min@13:20, 22min@17:40, 3min@21:30  [America/Bogota local]
```

**Session times must be shown in two timezones side by side:**
1. **Faiyam's local time** — detect the machine's timezone at runtime (`date +"%Z %z"`) and use that as the primary reference
2. **Account's local time** — from the `Timezone` field in Airtable

Format: `Xmin@HH:MM<MachineZone>/HH:MM<AccountZone>` — e.g. `7min@23:13EDT/21:13CostaRica`

Compute start times by taking the current wall-clock time, adding sequential session durations plus the 2–5 min inter-session gaps. If `Timezone` is missing for an account (should be auto-healed above), fall back to UTC and label it `UTC`.

Print the plan and proceed immediately — no confirmation needed.

---

## STEP 5 — Execute sessions — single-thread monitoring loop

Run all sessions directly in this agent thread. **No RemoteTriggers. No CronCreate. You stay in the loop, watch what happens, and fix problems.**

**Launch pattern — concurrent across accounts, sequential within:**

1. For each account in the plan, launch its **first session** as a background Bash process. Each session runs:

```bash
# SKILL_DIR = wherever this skill is installed, e.g. .agents/skills/tiktok-warmup
# Generate one --session-id per session (uuidgen) so all action-log rows for that
# session group together in Supabase. The --account-slug + --warmup-day are
# required for the nightly audit agent to slice action logs per-account/per-day.
uv run --with playwright --with requests python3 -u \
  "$SKILL_DIR/tiktok-warmup-poc.py" \
  --profile "<platform,handle>" --week <N> --duration <D> \
  --niche-terms "<fuzzed_comma_separated_terms>" \
  --account-slug "<platform,handle>" \
  --session-id "$(uuidgen)" \
  --warmup-day <N> \
  [--daily-niche-pct <float>]   # omit if no prior successful sessions today
```

**Fuzzing rule for `--niche-terms`:** never pass the Airtable pool verbatim every run. Roughly: 50% verbatim, 20% minor typos, 15% reorder/paraphrase, 10% semantic cousin, 5% language flip. See `sessionDesignRef.md` for details.

**`--daily-niche-pct`:** before launching each session, query Session Log for today's successful rows for this account where FYP Niche % is set. Compute `Σ(fyp_niche_pct × videos_watched) / Σ(videos_watched)`. Omit the flag entirely if no qualifying rows exist.

2. **Poll every 60–90 seconds.** Check each running background process for output. Do NOT spam BashOutput — one poll per cycle. Between polls, wait with `sleep 60` or similar.

3. When a session produces JSON output, it's done — move to 5b. If it produces error output or hangs, move to 5c.

4. After each completed session for an account, wait a **random 2–5 min gap** (seeded on `account_name + session_index`) before launching the next session for that account. Other accounts continue running concurrently.

5. Continue until every account's queue is empty or Faiyam says stop.

### 5b. When a session finishes

Parse the JSON summary from stdout. Expected fields: `duration_min`, `videos_watched`, `niche_videos`, `fyp_niche_pct`, `likes`, `follows`, `comments`, `searches`, `activities`, `start_page`.

**Write a Session Log row** (resolve table ID via resolver, then use REST API):
- Timestamp UTC: session end time
- Account Name
- Warmup Day (computed earlier)
- Session # Today: count of prior Session Log rows today + 1
- Duration (min)
- **FYP Niche %** (`fldQHQm3TFzw1lZBC`): `fyp_niche_pct` from JSON (number field, e.g. `0.72`)
- Likes, Follows, Comment Left, Comment Text
- Searches Done (as **string**, even if just "0" or "3" — never int, see runtimeLearnings.md)
- Error: blank on success

Skip the old Scheduled Sessions table entirely — we're not using it anymore.

### 5b.1 — Recompute and write Health Score

After each successful Session Log row write, recompute the account's `Health Score` (0–100) using the helper script. Inputs come from the last 7 days of Session Log rows for that account:

- `niche_pct`     = weighted avg of `FYP Niche %` (weighted by Duration min)
- `follow_rate`   = total `Follows` / total `videos_watched` (videos_watched not in Session Log — derive from Supabase `warmup_actions` count where action_type='video_watch')
- `comment_rate`  = total `Comment Left` (count where TRUE) / total session count
- `consistency`   = (distinct days with ≥1 successful session) / (days since min(Warmup Start Date, today-7))
- `error_rate`    = (sessions with non-blank Error) / (total sessions)

Then call:

```bash
SCORE=$(python3 "$SKILL_DIR/compute_health_score.py" \
  --niche-pct $NICHE_PCT --follow-rate $FOLLOW_RATE \
  --comment-rate $COMMENT_RATE --consistency $CONSISTENCY --error-rate $ERROR_RATE)
```

PATCH the Accounts row:

```bash
curl -s -X PATCH "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE/$ACCOUNT_REC_ID" \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"fields\":{\"Health Score\":$SCORE}}"
```

The score is shown next to each account in the next plan summary so trends are visible at a glance.

### 5c. If the session failed / hung / got weird

**Do NOT silently retry or mark-and-move-on.** Instead:

1. Take a screenshot of whatever's on screen (Multilogin window, browser, etc.). Use `xcrun simctl` is not it — this is a Mac app. Use `screencapture -R<x>,<y>,<w>,<h> /tmp/warmup_issue.png` or `screencapture /tmp/warmup_issue.png` and then `sips -Z 1800 /tmp/warmup_issue.png`.
2. Read any screenshots the script dropped (e.g. `/tmp/tiktok_login_*.png`).
3. Tell Faiyam exactly what you observe:
   - "Lucia's session hit a CAPTCHA at minute 3. Screenshot at /tmp/warmup_issue.png. Can you solve it and tell me 'done'?"
   - "Sebastian's profile won't launch — Multilogin says Team: Unavailable. See runtimeLearnings.md — this usually means server-side outage. Stop here?"
   - "Diego Herrera appears logged out. TikTok is showing the login page. Want me to trigger the `ensure_login` flow, or will you do it manually?"
4. **Wait** for Faiyam's response. Do not proceed until they tell you what to do.

Common failure categories and what you can try after Faiyam confirms:

| Symptom | Recovery |
|---------|----------|
| CAPTCHA mid-session | Faiyam solves in the live browser → say "continue" → you re-run the session for that account |
| Logged out, no stored credentials | Fetch from 1Password per `browserWarmupRef.md`; if still blocked, Faiyam logs in manually then you re-run |
| **"Maximum number of attempts reached" on login** (TikTok 24h lockout) | **Automatically pause the account for 24h.** See "Lockout auto-pause" below. Do NOT retry — retrying extends the lockout and risks a flag. |
| **`PROXY_REFRESH_NEEDED` on profile launch** | Automated refresh. See "Proxy refresh" below. |
| Multilogin "Team: Unavailable" | Abort all sessions, tell Faiyam to wait for service recovery |
| Profile already running (stale) | Call `GET https://launcher.mlx.yt:45001/api/v1/profile/stop/p/{PROFILE_ID}` with `MLX_AUTOMATION_TOKEN`, then retry |
| Playwright CDP connection refused | Profile didn't actually start — check launcher response, retry once; if second failure, ask Faiyam |

### Proxy refresh (when profile launch fails with proxy error)

**Ban risk check first — read `proxyRefreshRef.md` before acting.** Rotating a proxy changes the account's IP, which is a TikTok trust signal. Only rotate for a genuine proxy failure, never preemptively.

**Simultaneous failure across ≥3 accounts = provider outage, NOT per-account issue.**
If ≥3 accounts raise `PROXY_REFRESH_NEEDED` within the same batch window (within 30s of each other), skip all rotations and send a Telegram escalation:
> "🚨 ESCALATION: Proxy outage — ≥3 accounts hit PROXY_REFRESH_NEEDED simultaneously. Likely Multilogin proxy provider issue. Skipping all sessions. Please check Multilogin status and retry in 30–60 min."
Then stop. Do not rotate any proxies during an outage.

**Single-account proxy failure — automated flow:**

The script raises `PROXY_REFRESH_NEEDED: ...` when the launcher returns a proxy-related error on profile start. When you see this for a single account:

1. **Stop the profile** (if not already stopped — it usually is since start failed).

2. **Run the automated refresh:**
   ```bash
   python3 "$SKILL_DIR/refresh_proxy.py" --account <slug>
   ```
   This calls the Generate Proxy API (same country, sticky, 86400s TTL) and updates the profile via the Multilogin API. It prints `✅ proxy rotated` on success or `❌` on failure.

3. If the script exits 0 (success): wait 10s for the proxy to propagate, then retry the session launch **once**.

4. If the retry also fails with `PROXY_REFRESH_NEEDED`: stop. Mark the session failed with `error = "Proxy still failing after automated refresh — possible provider outage or credential issue"`. Move to the next account. Do not retry again today for this account.

5. If `refresh_proxy.py` itself fails (exits non-zero): fall back to asking Faiyam:
   > "Automated proxy refresh failed for **<account>** (API error — see output above). Please open Multilogin, click 'Get new IP' on the profile's proxy row, wait ~10s, then reply 'ready'. Or reply 'skip' to skip this account today."

**Never rotate the same account's proxy more than once per executor run.**

### Lockout auto-pause (24h rule)

If the warmup script raises an exception containing `TIKTOK_LOCKOUT_24H` or the screenshot/error shows "Maximum number of attempts reached" on the TikTok login screen:

1. **Do NOT retry the login for this account.** Every retry extends TikTok's lockout window and looks more suspicious.
2. **Update the account in Airtable Accounts** (use REST API — resolve table ID via resolver):
   - `Paused Until` (fldHbm3Oq5MBlYqcZ): `now_utc + 24h` as ISO string, e.g. `2026-04-18T02:57:09.000Z`
   - `Pause Reason` (fldnMsGzer8SYUkX6): `TikTok login lockout — Maximum number of attempts reached (seen YYYY-MM-DD)`
3. Mark this run's session for that account as **failed** in Session Log with Error = `TikTok login lockout, account auto-paused until <timestamp>`.
4. Tell Faiyam:
   - Account name + when it will unpause
   - Possible causes: wrong credentials in 1Password, email mismatch between Proton inbox and the email TikTok was registered with, expired password.
   - Invite them to check before the unpause time.
5. Move on to the next account — do NOT re-queue this one today.

### 5d. Run next session for the same account (if any)

Once an account's first session completes successfully, wait a natural gap (random **2–5 min**) before launching its next session. Use `Bash` with a short `sleep` — do NOT block the other accounts that are still running or done.

The simplest pattern:
1. Track a per-account queue of sessions.
2. Each poll, if an account has no running session AND has more sessions in its queue AND its last session ended ≥2–5 min ago (use a seeded random gap), launch the next one in the background.
3. Continue until every account's queue is empty.

---

## STEP 6 — Final summary

When every account is done (queue empty OR Faiyam said stop):

1. Print a per-account summary: total minutes done today, sessions completed/failed, any accounts where Faiyam intervened.
2. If you learned anything new (new failure mode, new TikTok UI change, new gotcha) — append a dated section to `runtimeLearnings.md` **in this same session**, before exiting.

---

## STEP 7 — Commit learnings (optional)

If you edited any skill files or `runtimeLearnings.md` during this run, commit them as a normal change:

```bash
cd "$(git rev-parse --show-toplevel)"
git checkout -b warmup-learnings/$(date -u +%Y%m%d-%H%M)
git add .agents/skills/tiktok-warmup/
git commit -m "chore(tiktok-warmup): manual run $(date -u +%Y-%m-%d)"
git push -u origin HEAD
gh pr create --title "tiktok-warmup manual run $(date -u +%Y-%m-%d)" --body "Manual /execute-warmups run."
gh pr merge --merge --auto
```

Skip if no skill files changed.

---

## Hard rules (repeat of runtimeLearnings.md highlights)

- **Airtable: ALWAYS use the REST API with `$AIRTABLE_ACCESS_TOKEN`.** Never use the Airtable MCP — see `airtableRef.md`.
- **Never chain bash commands with `&&`** in this workflow — breaks unattended runs. Each bash call = one short command.
- **Never prepend `source .env.cli &&`** to the POC script. It loads the file itself.
- **Searches Done field = string.** Passing an int throws 422.
- **Always stop the profile in the `finally` block.** The POC script does this; if you see an `in_use_by` profile on startup, stop it before launching a new session for that account.
- **When in doubt, ask Faiyam.** This system is semi-manual on purpose.
