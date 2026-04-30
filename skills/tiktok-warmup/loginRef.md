# TikTok Login — Do This Yourself, Don't Delegate

**Critical rule**: Login is an agentic task. Never pass it off to a Python script
that can't see the screen. Your Python scripts can handle mechanical stuff
(scrolling, searching, clicking known elements) but login flows fail in ways
that require judgment — captchas, silent bounces, unexpected modals, email OTPs,
rate-limit interstitials. Do it yourself, verify visually, THEN hand off to
Python for the mechanical warmup.

---

## Procedural: where to get credentials and OTPs

### TikTok account credentials → 1Password

> **NEVER ask the user for login credentials or permission to fetch them.**
> All logins are in 1Password and accessible autonomously via the service token.
> Just run the command below and proceed.

Each TikTok account has a 1Password item in the **Tiktok** vault (accessible via `OP_SERVICE_ACCOUNT_TOKEN`).

```bash
# CORRECT: inline the token — do NOT use source + --account
TOKEN=$(grep OP_SERVICE_ACCOUNT_TOKEN /path/to/.env.cli | cut -d= -f2-)
OP_SERVICE_ACCOUNT_TOKEN=$TOKEN op item get "TikTok - <Account Name>" \
  --vault "Tiktok" --reveal
```

- `username` → the sign-in email (e.g., `giuliaromano97@proton.me`)
- `password` → the cleartext password
- **Do NOT add `--account <id>`** — that forces interactive user auth and breaks the service token flow. Inline `OP_SERVICE_ACCOUNT_TOKEN=<token>` before the `op` command.
- The service token sees the `Tiktok` vault — use `--vault "Tiktok"` always.

Item names as of 2026-04-17:
- `TikTok - Sebastian Vargas` (handle @espanol.desde.cero)
- `TikTok - Giulia Romano` (handle @flooently_italian)
- `TikTok - Sofia Reyes` (handle @blazemoney_latam)
- `TikTok - Diego Salazar` (handle @blazemoney_agents)

### TikTok email OTPs → AgentMail shared inbox (most accounts)

Most accounts forward TikTok verification mail to `tiktok@agentmail.to`.
Retrieve codes via the AgentMail CLI (already authed via `AGENTMAIL_API_KEY` in `.env.cli`):

```bash
# List messages — find the one with "TikTok" in the subject, most recent
agentmail inboxes:messages list --inbox-id tiktok@agentmail.to

# Fetch a specific message by ID (body contains the 6-digit code)
agentmail inboxes:messages retrieve --inbox-id tiktok@agentmail.to \
  --message-id "<message-id>"
```

Poll up to 60 seconds for an OTP after you trigger it. If no email lands in
60s → mark the session failed, TikTok didn't actually send one, or the forward
chain is broken (escalate).

### Exception: flooently_french → Tuta desktop app

`flooentlyfrench@tuta.com` uses **Tuta** which cannot forward to AgentMail (E2E
encryption, no external forwarding). OTPs must be read directly from the Tuta
desktop app.

**Before starting any flooently_french session, launch the Tuta app:**

```bash
open -a "Tuta Mail"
```

Then wait a few seconds for it to load and sync. When TikTok sends an OTP:
1. Use `agent-device` (or AppleScript) to bring Tuta to the foreground and read the inbox
2. Find the TikTok verification email and extract the 6-digit code
3. Enter it in TikTok

If Tuta fails to launch or the email doesn't arrive within 90s, mark the session
failed with error `"Tuta OTP unavailable"` and escalate via Telegram.

### Multilogin API token

In `.env.cli` as `MULTILOGIN_API_KEY`. If you hit `EXPIRED_JWT_TOKEN` or
`UNAUTHORIZED_REQUEST`, **run the regenerator, don't ask for manual help**:

```bash
python3 scripts/regenerate-mlx-token.py
```

This pulls the Multilogin master-account email+password from 1Password
(`Multilogin` item, Claude-Accessible vault, `--account QBMXQBMBTJHH7EHLVRVAJEPGNI`), signs in, switches to the
Flooently workspace, generates a `no_exp` automation token, writes it back.
~5 seconds.

---

## Agentic: how to actually log an account in

Assume you already started the profile with `scripts/warmup/session.py start <slug>`
(so the Multilogin Mimic browser is up and the CDP port is stashed in
`/tmp/warmup_state/<slug>.json`).

### Step 1 — Confirm logged-out visually

Take a screenshot and **actually look at it**:

```bash
python3 scripts/warmup/session.py screenshot <slug> --out /tmp/check_<slug>.png
```

Then Read `/tmp/check_<slug>.png`. Signs of logged-in:
- User avatar in top-right, no "Log in" button
- Sidebar includes **Messages, Activity, Friends** (logged-out users only see
  For You / Explore / Following / LIVE / Upload / Profile / More)
- Page title is "Watch trending videos for you | TikTok"

Signs of logged-out:
- Visible "Log in" button (top-right, or in the sidebar near the bottom)
- An onboarding "What would you like to watch on TikTok?" modal (3-of-3
  interest picker) — this modal blocks everything underneath
- Page title is "Sign up | TikTok"

The Python selector-based `is_logged_in` is a hint, not ground truth. If you
have any doubt, trust the screenshot.

### Step 2 — Dismiss any blocking modal

If you see the onboarding popup, dismiss it first (the close X in top-right of
the modal). You can use the helper:

```bash
python3 scripts/warmup/dismiss_popups.py <slug>
```

Or do it directly: find and click the X via Playwright. The selector
`[data-e2e="modal-close-inner-button"]` usually works.

### Step 3 — Navigate to email login

Write a short Python snippet (don't shell out to `ensure_login.py` — that's the
brittle path we're moving away from). Via CDP connection:

```python
page.goto("https://www.tiktok.com/login/phone-or-email/email",
          wait_until="load", timeout=45000)
time.sleep(5)  # let the SPA mount the form
page.screenshot(path="/tmp/login_form.png")
```

Then Read the screenshot. You should see:
- Title "Log in"
- Email or username field (placeholder: "Email or username")
- Password field
- Red "Log in" button (disabled until both fields have content)

If instead you see a captcha (slider puzzle, "drag the slider to fit the
puzzle", rotated image etc.) → jump to the captcha handler in Step 6.

### Step 4 — Fill + submit

Probe the DOM for the right input selectors — they change. Try in order:
- `input[name="username"]`
- `input[type="email"]`
- `input[placeholder*="Email" i]`
- `input[autocomplete="username"]`

And for password:
- `input[type="password"]`
- `input[name="password"]`

Use human-paced typing (per-keystroke 50–160ms delay) — don't dump the whole
string at once. Then click the red Log in button, or press Enter.

### Step 5 — Wait long enough, re-check

TikTok's login flow is multi-stage: the click fires → spinner shows → eventually
one of five outcomes:

1. **Success** → redirected to `/foryou`, sidebar updates with Messages/Activity/Friends, avatar in top-right
2. **Verify-identity modal** (most common) → "Verify it's really you" with an Email option. Proceed to Step 7.
3. **Captcha/puzzle** → modal appears with slider puzzle. Proceed to Step 6.
4. **Silent bounce** → back at `/foryou` still logged out, no error. TikTok's soft rate-limit. Back off.
5. **Spinner-then-server-error** → the Log in button spins for 15-30s, then switches back to an active Log in button with red text below the password field saying "Internal server error. Please try again later." **This is NOT always a transient — it's often a soft-block** (bot detection, rate limit, or geofence-related). Wait 3-5 minutes before any retry. If it fails the same way twice, stop.

**Wait at least 20 seconds** after submit before checking state. A 5-second wait
captures the spinner mid-flight and misreads the result. Then take another
screenshot and Read it. Don't trust selectors for this check — look at the image.

### Step 6 — Captcha handling

If you see any captcha (slider, rotated image, "I'm not a robot"):

- **First choice**: ask the user to solve it in the Multilogin browser window
  (they almost certainly have it open). Tell them clearly what screen you see.
  Wait for them to say "done", then re-take the screenshot and verify login
  completed.
- **Don't hammer retry**: every retry increases the chance of a 24-hour lockout
  ("Maximum number of attempts reached. Try again later."). If you see that
  error, stop immediately and follow the lockout-auto-pause procedure in
  `runtimeLearnings.md`.

### Step 7 — OTP handling (post-password, "Verify it's really you")

After submitting email+password, TikTok frequently throws up a "Verify it's really
you" modal offering an Email option. Then after you pick Email, it shows "Verify
identity" with an "Enter 6-digit code" field, a 60s resend countdown, and a Next
button. The 6-digit code arrives at `tiktok@agentmail.to` via Proton forwarding
within 10-60s. **Do NOT click "Resend code" repeatedly** — TikTok rate-limits
this aggressively and may trigger a 24h lockout.

**Clicking the "Email" option in the Verify modal (gotcha)**:
- The Email row is a clickable `<div>` with no `button`/`[role="button"]`/onclick
  attribute visible in the DOM. TikTok wires the click via React. 
- `.click(force=True)` **does NOT work** — the event doesn't register.
- `page.click('div.pc-home-items-l9mnww', timeout=5000)` **works** — the class
  name may rotate across TikTok deploys; fall back to clicking the innermost div
  that contains the text "Email" and the masked proton address.
- Coordinate clicks (e.g. `page.mouse.click(634, 470)`) are unreliable.

**Fetching the OTP from AgentMail** — there's a dedicated helper:

```bash
python3 scripts/warmup/fetch_otp.py --email <proton-address> --max-wait 90 --since-s 300
```

Returns JSON `{"code": "123456", "message_id": "...", "timestamp": "..."}` on
success, or `{"error": "..."}` on timeout. Match by `to`, `X-Pm-Forwarded-From`
header, or `X-Original-To` header. The subject pattern is `"<6digits> is your
6-digit code"` — extracted via `\b\d{6}\b`.

**Direct HTTP poll (if helper breaks)**:
```bash
source .env.cli
curl -s -H "Authorization: Bearer $AGENTMAIL_KEY" \
  "https://api.agentmail.to/v0/inboxes/tiktok@agentmail.to/messages?limit=10" \
  | python3 -m json.tool
```

**Filling the OTP code**: `input[placeholder*="6-digit" i]` or similar. Type with
human pacing (50-160ms per digit). Then click the "Next" button
(`button:has-text("Next")` — or sometimes "Verify" / "Continue").

**If no OTP lands within 90s — DO NOT retry** (see anti-patterns). The forward
chain is likely broken. Check:
- Proton email forwarding is active for THIS SPECIFIC proton address (see the
  "Email Proton Forwarding Mismatch" section below)
- The 1Password `username` field matches the actual proton address on the
  TikTok account (they've drifted before — see Diego's case in runtimeLearnings)

Escalate to the user; don't burn retry attempts.

### Email / Proton Forwarding Mismatch (2026-04-18)

**Scenario seen**: 1Password item `TikTok - Diego Salazar` has `username`
`diegosalazar9531@proton.me`, but the "Forwarding active" confirmation in
`tiktok@agentmail.to` came from **`degoalaz9531@proton.me`**. OTPs sent to
`diegosalazar9531@proton.me` never landed in `tiktok@agentmail.to` because
forwarding was only set up on the other address.

**Before relying on AgentMail OTP for a new account**, verify:
1. The proton address on record (1P + Airtable `TikTok Email`) exactly matches
   the one whose "Forwarding active" email appears in `tiktok@agentmail.to`.
2. If they don't match, either:
   a. Update the 1P / Airtable to the correct address, OR
   b. Set up forwarding on the account TikTok actually uses.
3. Consider adding a sentinel email test (e.g. send a test email to the 1P
   address from gmail, confirm it lands in tiktok@agentmail.to) before running
   a real warmup session.

---

## Verification: you ARE logged in when…

Take a screenshot. ALL of these must be true:
- URL is `/foryou` (not `/login` and not `/?lang=en` redirect)
- Page title is **not** "Sign up | TikTok"
- No "Log in" button visible anywhere
- Sidebar shows Messages, Activity, **and** Friends (logged-in-only links)
- `[data-e2e="nav-profile"]` href is `/@<realhandle>`, not `/@`

Only after you've confirmed this visually, hand off to the mechanical Python
task scripts (`niche_search.py`, `scroll_fyp.py`, etc.).

---

## Anti-patterns

- ❌ **Running `ensure_login.py` and trusting its JSON output.** Its selectors
  are hints, not ground truth. It gave false positives on logged-out sessions
  because TikTok caches the user's handle in the DOM after logout briefly.
  It's kept around as a quick state probe only.
- ❌ **Retrying login 3+ times after silent bounces.** Each attempt increases
  lockout risk. If 2 retries fail, stop and escalate to the user.
- ❌ **Waiting only 5 seconds after submit.** TikTok's red spinner button is
  typically mid-flight at 5s. Wait 20s minimum before you check result.
- ❌ **Assuming cookies persist across session gaps.** Multilogin preserves
  cookies across profile starts, BUT TikTok can invalidate server-side. Always
  re-verify login at the start of every new session.
