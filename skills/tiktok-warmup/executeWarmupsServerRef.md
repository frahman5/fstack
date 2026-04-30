# Execute Warmups — Server Mode

Server-mode override for `executeWarmupsRef.md`. Run this protocol (not the base one) when executing from the remote warmup server. Everything is identical to `executeWarmupsRef.md` except the sections below.

---

## Overridden design principle

**Original principle #4:** "Lean on the human — ask Faiyam and wait."

**Server-mode principle #4:** Never block waiting for a human. On any failure, stop the affected profile (releasing its cloud lock), send a Telegram escalation, mark the account failed for this run, and continue with the remaining accounts. Faiyam will resolve via noVNC or his laptop's Multilogin desktop on his own time.

---

## Telegram escalation helper

Use this pattern for all alerts. Replace `<MESSAGE>` with the message text. Attach screenshots via `--form` when available.

```bash
# Text-only alert
curl -s -X POST "https://api.telegram.org/bot8645212775:AAGY4HuJmSn9d_S9ld9nU5KpGca2_SBF598/sendMessage" \
  -d "chat_id=5043064976" \
  --data-urlencode "text=<MESSAGE>"

# Alert with screenshot attached
curl -s -X POST "https://api.telegram.org/bot8645212775:AAGY4HuJmSn9d_S9ld9nU5KpGca2_SBF598/sendPhoto" \
  -F "chat_id=5043064976" \
  -F "caption=<MESSAGE>" \
  -F "photo=@/tmp/warmup_issue.png"
```

**noVNC link to include in all alerts:** `http://100.96.234.61:6080/vnc.html` (accessible from any Tailscale-connected device).

---

## Overridden screenshot command

**For CAPTCHA and login failures: the Python script already handles the Telegram photo.**
`tiktok-warmup-poc.py` takes a `page.screenshot()` (browser content, not desktop) and sends it to Telegram before raising the exception. Do NOT take a desktop screenshot for these cases — it will show the Multilogin profile manager with the browser already closed, which is useless.

Only use the desktop screenshot command for outages, profile start failures, and other cases where no browser screenshot exists:

```bash
DISPLAY=:99 import -window root /tmp/warmup_issue.png
convert /tmp/warmup_issue.png -resize '1800x1800>' /tmp/warmup_issue.png
```

---

## Overridden STEP 5c — failure handling

When a session fails, hangs, or hits a blocking issue, do NOT wait for human input. Instead:

### CAPTCHA / login failure

The Python script already sent a Telegram photo (browser screenshot + noVNC link) before raising. Do NOT take a desktop screenshot or send another Telegram message — it will be a duplicate showing the Multilogin manager with the browser closed.

1. Stop the profile via API to release the cloud lock:
   ```bash
   curl -sf -X GET "https://launcher.mlx.yt:45001/api/v1/profile/stop/p/<PROFILE_ID>" \
     -H "Authorization: Bearer $MLX_AUTOMATION_TOKEN"
   ```
2. Write Session Log row with `Error = "CAPTCHA or login failure — see Telegram for screenshot"`.
3. Move on to the next account.

### Proxy refresh needed (`PROXY_REFRESH_NEEDED`)

1. Stop the profile via API.
2. Send Telegram:
   ```
   🌐 Proxy refresh needed — tiktok,<handle>

   Open Multilogin on your laptop → find the profile → click "Get new IP".
   Session skipped. Next run will retry.
   noVNC: http://100.96.234.61:6080/vnc.html
   ```
3. Write Session Log row with `Error = "PROXY_REFRESH_NEEDED — requires manual proxy rotation"`.
4. Move on.

### Logged out (TikTok showing login page)

Auto-attempt re-login via 1Password credentials per `browserWarmupRef.md`. This is fully automated — no change from base protocol. Only escalate if re-login fails after the automated attempt:

```
🔐 Re-login failed — tiktok,<handle>

Automated re-login attempt failed. Credentials may be wrong in 1Password.
noVNC: http://100.96.234.61:6080/vnc.html
```

Then stop profile (via API), write Session Log error row (`Error = "Re-login failed — see Telegram for screenshot"`), move on. The Python script sends the Telegram photo — do NOT take a separate desktop screenshot.

### TikTok 24h lockout (`TIKTOK_LOCKOUT_24H`)

Same auto-pause logic as base protocol (update Airtable `Paused Until` + `Pause Reason`), plus send Telegram:

```
🔒 TikTok lockout — tiktok,<handle>

Account auto-paused for 24h. Check credentials in 1Password before it unpauses.
Unpauses: <timestamp>
```

### Multilogin outage (`Team: Unavailable`)

Send Telegram:
```
🛑 Multilogin outage detected

Launcher API not responding on warmup-poc. Aborting run.
Check status.multilogin.com
noVNC: http://100.96.234.61:6080/vnc.html
```
Abort all remaining sessions cleanly. Write failed Session Log rows for any accounts that hadn't started yet with `Error = "Multilogin outage"`.

### Profile start failure (CDP refused, browser didn't launch)

1. Stop profile via API.
2. Send Telegram:
   ```
   ⚠️ Profile failed to start — tiktok,<handle>

   Browser didn't launch in time (CDP connection refused).
   noVNC: http://100.96.234.61:6080/vnc.html
   ```
3. Write Session Log error row, move on.

---

## Overridden STEP 7 — skip git commit

Skip Step 7 entirely on the server. Git commits for `runtimeLearnings.md` updates happen on the laptop. If you learn something new during a server run, append to `runtimeLearnings.md` but do NOT commit — the next laptop-side pull will pick it up.

---

## Run start notification

At the very beginning of a run (after pre-flight passes), send one Telegram message so Faiyam knows a run started:

```
🤖 Warmup run started — <N> accounts, <M> total sessions
Accounts: tiktok,<handle1>, tiktok,<handle2>, ...
```

And one at the end:

```
✅ Warmup run complete
  Completed: <N> sessions across <M> accounts
  Failed: <K> sessions (see above for details)
  Total time: <X> min
```

If the run aborted early (Multilogin outage, pre-flight failure), send:
```
❌ Warmup run aborted — <reason>
```
