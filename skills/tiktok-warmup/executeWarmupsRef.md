# Execute Warmups

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
source /Users/faiyamrahman/conductor/workspaces/Flooently/managua-v1/.env.cli
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
curl -sf http://localhost:45001/api/v1/profile/list > /dev/null && echo "✅ Multilogin launcher OK" || echo "⚠ Multilogin launcher not responding — open the Multilogin desktop app"
```

**What each check catches:**
- Missing/wrong `OP_SERVICE_ACCOUNT_TOKEN` → auto-login will fail for any logged-out profile
- `TikTok` vault not found → the token is from the wrong 1Password account or lacks vault access (this broke warmups on 2026-04-22 after engineer onboarding split the 1Password accounts)
- Multilogin not running → all profile launches will fail immediately

If pre-flight fails, do NOT schedule any sessions. Fix the issue first, then re-invoke `/execute-warmups`.

---

## STEP 1 — Read context

1. Read `runtimeLearnings.md` (it has real bug fixes — do not skip).
2. Read `browserWarmupRef.md` (session mechanics).
3. Get current UTC time: `date -u +"%Y-%m-%dT%H:%M:%SZ"`.

---

## STEP 2 — Pull active accounts from Airtable

Use the Airtable MCP (`mcp__b7c70c01-304b-4dc7-9a2d-89d24f14ebb7__list_records_for_table`), **never curl/REST**.

- Base ID: `appfTuMpiXafoRNJG`
- Accounts table: `tbljagCt5kJaBPNUl`

Filter for `Active = true`. Pull fields: Name, Brand, Timezone, UTC Offset, Waking Start, Waking End, Warmup Start Date, Multilogin Profile ID, **Paused Until**, **Pause Reason**, **Search Terms** (`fldnFSwwpxVigKXel`).

**Filter out paused accounts immediately.** For each record where `Paused Until` is set and `Paused Until > now_utc`, drop it from the working set and print one line:

```
  Isabella Restrepo: PAUSED until 2026-04-18 02:57 UTC — TikTok login lockout. Skipping.
```

If `Paused Until ≤ now_utc`, the pause has expired — treat the account as normal (and optionally clear the fields via Airtable MCP so the row is tidy).

**Email recovery check.** Also pull the `Email Recovery` field (`fldmySQAr2mZjw6ne`) for each account. For any account where this field is not `"Backed Up"`:
- Print a warning in the plan summary (e.g. `⚠️  Sofia Reyes: email recovery NOT backed up — fix before running`)
- Still include the account in the plan (don't block warmup), but make the warning prominent so Faiyam sees it and can act

Write the filtered-active set to `/tmp/tk_active.json` via Write tool (not heredoc). Use this to drive the plan.

**Auto-fill missing Multilogin Profile IDs.** For any active account where `Multilogin Profile ID` is blank:
1. Call `POST https://api.multilogin.com/profile/search` (body `{"search_text":"","is_removed":false,"limit":100,"offset":0}`) with `Authorization: Bearer $MLX_AUTOMATION_TOKEN`.
2. Match profiles by TikTok handle or account name — look for profile names containing the handle (e.g. `blazemoney_latam`) or the account name (e.g. `Sofia Reyes`). Only match profiles with `(TikTok)` in the name or that clearly correspond to a TikTok persona.
3. If a match is found: update the Airtable Accounts record via MCP (`fld9knhdqkuYzwCfJ`) with the found profile ID, then include the account in the plan as normal.
4. If no match is found: print a warning and skip that account (can't automate without a profile).
Run this lookup once per executor invocation, before computing the plan.

**Refresh the script-side accounts cache.** After filtering, also update
`scripts/warmup/accounts.json` so the Python task scripts see any new or
removed accounts:

1. For each account in the filtered-active set with a `Multilogin Profile ID`:
   - Look up its folder via `POST https://api.multilogin.com/profile/search`
     (body `{"search_text":"","is_removed":false,"limit":100,"offset":0}`) and match by profile ID
   - Generate a stable slug: lowercased first word of Name (e.g. "Sebastian Vargas"→`sebastian`, "Blaze Money"→`blaze_money`). If two accounts collide, extend to include the second word.
   - Include: `name`, `handle` (TikTok Username), `profile_id`, `folder_id`, `op_item` (`"TikTok - <Name>"`), `brand`, `tiktok_email`
2. Write the new JSON with `_last_refreshed_utc` set to now. Keep the fallback
   `ACCOUNTS` dict in `_common.py` in sync manually only when you need an
   offline safety net.

Full protocol: [`.claude/skills/tiktok-warmup/accountsRef.md`](.claude/skills/tiktok-warmup/accountsRef.md).

---

## STEP 2.5 — Account health audit

Before planning sessions, audit every active account for missing or inconsistent data. Surface issues to the user so they can fix them now rather than discovering them mid-run or (worse) from a silent skip.

Run these checks on each active account pulled from Airtable:

| Check | Severity | Action |
|-------|----------|--------|
| `Search Terms` is empty | **error** | Block this account — the warmup scripts need it. Prompt user to generate terms (see `adoptAccountRef.md` Step 11) |
| `Warmup Start Date` is empty | **error** | Block this account — mode determination needs it. Prompt user to set it |
| `Multilogin Profile ID` is empty | **error** | Block this account — cannot launch without it. Already handled by the auto-fill logic below, surface only if auto-fill also fails |
| `TikTok Email` is empty | **warn** | Account can run but OTP flow will break if a re-login is needed |
| `AgentMail Inbox` is empty | **warn** | Same — OTP retrieval won't route correctly |
| `Email Recovery` ≠ "Backed Up" | **warn** | Account can run but recovery is uncertain |
| `Niche Description` is empty | **warn** | Search-term regeneration will be harder later |
| `Active=true` + account just created (< 1 day ago) | **info** | Just a heads-up that it's a brand-new account |

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

### 4e. Schedule sessions across waking hours

**Do NOT run all sessions immediately.** Instead, distribute them randomly across the account's remaining waking hours today and schedule each one as a separate trigger via the `/schedule` skill (`CronCreate` + `RemoteTrigger`). This makes the day's activity look organic — short check-ins, longer doomscrolls, gaps of inactivity — rather than a mechanical burst.

**Scheduling rules:**
- Only schedule within the account's waking window (`Waking Start`–`Waking End` in local time). If no waking window is set, use 08:00–23:00 in UTC.
- Minimum gap between sessions for the same account: **20–60 min** (random, seeded).
- Spread sessions across the full remaining waking window — don't cluster them.
- Each scheduled trigger is a self-contained agent prompt (see below).

**Trigger prompt template for each session:**
```
Run one TikTok warmup session.

Account: <platform,handle>
Human name for Airtable: <human_name>
Duration: <D> minutes
Warmup week: <N> | Warmup day: <X> | Session # today: <Y> (<prior_count> sessions done before this one today)

Pre-run — compute daily niche %:
  Query Airtable Session Log (base appfTuMpiXafoRNJG, table tbluS09ymOa9oBDwA) for today's successful sessions
  where Account Name = "<human_name>" and Error is blank and FYP Niche % (fldQHQm3TFzw1lZBC) is set.
  daily_niche_pct = Σ(fyp_niche_pct × videos_watched) / Σ(videos_watched). If no qualifying rows, omit --daily-niche-pct.

Step 1 — Run (from /Users/faiyamrahman/conductor/workspaces/Flooently/douala):
  uv run --with playwright --with requests python3 -u .agents/skills/tiktok-warmup/tiktok-warmup-poc.py \
    --profile "<platform,handle>" --week <N> --duration <D> \
    --niche-terms "<comma_separated_search_terms>" \
    --daily-niche-pct <daily_niche_pct>   ← omit entirely if no prior data

  IMPORTANT: apply fuzzing to --niche-terms — never pass the Airtable pool terms verbatim every run.
  See sessionDesignRef.md "Picking search terms and hashtag slugs" for the fuzzing rules
  (roughly: 50% verbatim, 20% minor typos, 15% reorder/paraphrase, 10% semantic cousin, 5% language flip).
  The goal: TikTok sees varied, human-like queries, not identical strings repeated across sessions.

Step 2 — Parse JSON summary from stdout. Extract: duration_min, niche_videos, fyp_niche_pct, likes, follows,
  comments (bool), comment_text, searches (int), error.

Step 3 — Write Session Log row (base appfTuMpiXafoRNJG, table tbluS09ymOa9oBDwA):
  fldGckcL5Qc5vcug9 (Timestamp UTC): current UTC ISO
  fldlUusi4GgT4n3oS (Account Name): "<human_name>"
  fldAGlCfxRJLJE6NB (Warmup Day): <X>
  fld4r6rSbhADxC5lk (Session # Today): <Y>
  fldiowoint6Gohzzw (Duration min): actual duration from JSON
  fldQHQm3TFzw1lZBC (FYP Niche %): fyp_niche_pct from JSON (number, e.g. 0.72)
  fldQySoabhxMjtDiV (Likes): likes count
  fldjlQ9xz0Wwwea9m (Follows): follows count
  fldsrWgDulMBACpCT (Comment Left): true if comment posted
  fldqYFV4prfupAZLC (Comment Text): comment text if any
  fldtLSEqt4pkBwqyQ (Searches Done): searches as STRING (e.g. "2" not 2)
  fldWHqaARjy1nsg4E (Error): blank on success, error message on failure

Step 4 — On failure: populate Error field + send Telegram:
  curl -s -X POST "https://api.telegram.org/bot8645212775:AAGY4HuJmSn9d_S9ld9nU5KpGca2_SBF598/sendMessage" \
    -d "chat_id=5043064976&text=WARMUP FAILED: <platform,handle> session <Y> — <error summary>"
```

Write the full plan (with scheduled times) to `/tmp/tk_plan.json` and show Faiyam a summary:

Account display format in all plans and summaries: `platform,handle` (e.g. `tiktok,flooently_spanish`). Derived from the `Platform` + `Username` fields in Airtable. The Airtable `Name` field (e.g. "Sebastian Vargas") is the internal record name — never use it in plan output.

```
Plan for 2026-04-18:
  tiktok,flooently_spanish  (wk1, day 3): 40 min left → 4 sessions: 7min@14:30, 12min@16:45, 3min@19:10, 18min@21:00
  tiktok,flooently_italian  (wk1, day 2): REST DAY — skip
  tiktok,blazemoney_latam   (wk1, day 4): 30 min left → 3 sessions: 5min@13:20, 22min@17:40, 3min@21:30
```

**Before scheduling anything: ask Faiyam "looks good? (yes to proceed)"** and wait for confirmation.

---

## STEP 5 — Schedule all sessions via /schedule

Once Faiyam confirms the plan, use the `/schedule` skill to create one trigger per session. Each trigger fires at the planned UTC time and runs the self-contained agent prompt from Step 4e.

**Use `CronCreate` with a one-time cron expression** for the scheduled UTC time. For a session at 14:35 UTC on 2026-04-18: cron = `35 14 18 4 *`.

After creating all triggers, report back to Faiyam:
```
✅ Scheduled 14 sessions across 5 accounts for today.
   First fires at 13:20 UTC (tiktok,blazemoney_latam, 5 min)
   Last fires at 22:45 UTC (tiktok,blaze__money, 18 min)
   Results will be logged to Airtable Session Log automatically.
```

Then stop — no need to monitor. The triggers run independently. Faiyam can check Airtable Session Log for results, or wait for Telegram escalations on failures.

### 5a. Session trigger failures

Each trigger agent handles its own error reporting (Telegram escalation + Airtable Session Log error row). If Faiyam reports a failed session or wants to re-run one, manually invoke the trigger or run the script directly:

```bash
python3 -u .agents/skills/tiktok-warmup/tiktok-warmup-poc.py --profile "<handle>" --week <N> --duration <D>
```

Do NOT spam BashOutput — poll each shell every 60–90 seconds. Between polls, if you have nothing else to do, just wait (use `Bash` with a `sleep` of 60–90s, or use the Monitor tool if available).

### 5b. When a session finishes

Parse the JSON summary from stdout. Expected fields: `duration_min`, `videos_watched`, `niche_videos`, `fyp_niche_pct`, `likes`, `follows`, `comments`, `searches`, `activities`, `start_page`.

**Write a Session Log row** (`tbluS09ymOa9oBDwA`) via Airtable MCP:
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
| **`PROXY_REFRESH_NEEDED` on profile launch** | Semi-manual refresh. See "Proxy refresh" below. |
| Multilogin "Team: Unavailable" | Abort all sessions, tell Faiyam to wait for service recovery |
| Profile already running (stale) | Call `GET https://launcher.mlx.yt:45001/api/v1/profile/stop/p/{PROFILE_ID}` with `MLX_AUTOMATION_TOKEN`, then retry |
| Playwright CDP connection refused | Profile didn't actually start — check launcher response, retry once; if second failure, ask Faiyam |

### Proxy refresh (when profile launch fails with proxy error)

Multilogin's built-in proxy rotation is UI-only — there is no public API endpoint for "Get new IP." So this step is semi-manual.

The script (`.agents/skills/tiktok-warmup/tiktok-warmup-poc.py::start_profile`) raises `PROXY_REFRESH_NEEDED: ...` when the launcher returns a proxy-related error. When you see that exception in a session's stdout:

1. Do NOT mark the session failed yet. Tell Faiyam:
   > "Proxy error on **<account name>** profile launch. Please (1) open Multilogin, (2) find the profile, (3) click 'Get new IP' on its proxy row, (4) wait ~10s for the new IP to connect, (5) reply 'ready' here."
2. **Wait** for Faiyam's reply.
3. Retry the launch **once** (re-run the same Python command). If it works, continue normally.
4. If the retry also fails with `PROXY_REFRESH_NEEDED`, stop: mark the session failed with error = "Proxy still failing after refresh", tell Faiyam it's likely a deeper issue (proxy credential change, Multilogin proxy outage, account-specific config), and move to the next account.

Do not loop refresh→retry more than twice for a single account in one run.

### Lockout auto-pause (24h rule)

If the warmup script raises an exception containing `TIKTOK_LOCKOUT_24H` or the screenshot/error shows "Maximum number of attempts reached" on the TikTok login screen:

1. **Do NOT retry the login for this account.** Every retry extends TikTok's lockout window and looks more suspicious.
2. **Update the account in Airtable Accounts** (`tbljagCt5kJaBPNUl`):
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
2. Append a dated entry to `docs/core/workLog/growth/<YYYY-MM-DD>.md` (create if missing). One-liner per account. Example:
   ```
   [2026-04-17] Warmup run (manual via /execute-warmups)
     - Sebastian Vargas: 48 min (2 sessions), 0 issues
     - Lucia Gonzalez: rest day
     - Diego Salazar: 35 min (1 of 2 — CAPTCHA on 2nd, Faiyam solved, re-ran)
     - Sophia Reyes: 15 min (1 session)
   ```
3. If you learned anything new (new failure mode, new TikTok UI change, new gotcha) — append a dated section to `runtimeLearnings.md` **in this same session**, before exiting.

---

## STEP 7 — Commit learnings (optional)

If you edited any skill files or `runtimeLearnings.md` during this run, commit them as a normal change:

```bash
cd /Users/faiyamrahman/Development/Flooently
git checkout -b warmup-learnings/$(date -u +%Y%m%d-%H%M)
git add .claude/skills/tiktok-warmup/ docs/core/workLog/growth/
git commit -m "chore(tiktok-warmup): manual run $(date -u +%Y-%m-%d)"
git push -u origin HEAD
gh pr create --title "tiktok-warmup manual run $(date -u +%Y-%m-%d)" --body "Manual /execute-warmups run."
gh pr merge --merge --auto
```

Skip if no file changes. If only workLog changed and no skill edits, still commit — the growth log is the user's record.

---

## Hard rules (repeat of runtimeLearnings.md highlights)

- **Airtable: ALWAYS use the MCP.** Never curl, never REST, never load env vars for Airtable.
- **Never chain bash commands with `&&`** in this workflow — breaks unattended runs. Each bash call = one short command.
- **Never prepend `source .env.cli &&`** to the POC script. It loads the file itself.
- **Searches Done field = string.** Passing an int throws 422.
- **Always stop the profile in the `finally` block.** The POC script does this; if you see an `in_use_by` profile on startup, stop it before launching a new session for that account.
- **When in doubt, ask Faiyam.** This system is semi-manual on purpose.
