# Adopting an Externally-Created TikTok Account

Walkthrough for integrating a TikTok account that was created and/or warmed up by someone else (e.g. a Fiverr freelancer) into our Multilogin + Airtable warmup pipeline. Work through each step in order, waiting for the user to confirm before moving on.

**This is different from `/create-tiktok`.** That command creates a new account from scratch and we control every credential from the start. Here, a third party created the account and currently still has the credentials. Taking exclusive ownership is the first priority.

**Reference files (read before starting):**
- `airtableRef.md` — REST API usage + resolver (NO MCP, ever)
- `accountCreationRef.md` — 1Password conventions
- `multiloginRef.md` — profile creation/launch API
- `loginRef.md` — TikTok login procedure
- `sessionDesignRef.md` — maintenance vs. initial warmup modes, search-term generation prompt

---

## STEP 0 — Create a project folder with a `todo.md`

**Before doing anything else**, create a project folder to track this adoption durably. The chat is ephemeral; `todo.md` is the resumable state.

1. Determine a slug for the folder — prefer the persona/brand name, lowercased and hyphenated: `blaze-money-crypto`, `maria-fuentes`, etc.
2. Create the folder: `docs/projects/adopt-<slug>/`
3. Inside it, create `todo.md` with the checklist from the end of this doc, plus a header noting persona name, handle, brand, date started, and freelancer/source details.
4. **As you progress through the steps, update `todo.md` in real time** — flip `[ ]` → `[x]` when a step completes. Add short inline notes for anything non-obvious (UUIDs, decisions, blockers).
5. Continue narrating progress in chat. The todo file is durable state, not a replacement for communication.

If a `docs/projects/adopt-<slug>/` already exists (resuming an interrupted adoption), read the existing `todo.md` first, confirm the remaining work with the user, then continue from the first unchecked step.

---

## STEP 1 — Gather what the freelancer handed over

Confirm the user has the following from the freelancer. If any are missing, block until obtained.

**Must-haves:**
- [ ] TikTok handle (e.g. `@blazemoney_crypto`)
- [ ] TikTok password (freelancer's current credential)
- [ ] Email used to register TikTok (e.g. `farahjob@outlook.com`)
- [ ] Email account password
- [ ] Country/region the account is tied to (proxy geo must match)

**Nice-to-haves:**
- [ ] Any phone number linked to the account (for 2FA)
- [ ] Persona details: display name, bio, profile photo, DOB
- [ ] Warmup history summary: niche, duration, notable issues
- [ ] Screenshot of current FYP (to sanity-check the niche was actually warmed)

Also ask:
- **Brand?** — inferred from repo by default (blaze-platform → Blaze, Flooently repo → Flooently). Override if different.
- **Persona name** for 1Password and Airtable Name field (e.g. "Blaze Money Crypto")

---

## STEP 2 — Take exclusive ownership of the email account

**Do this first.** If the freelancer still has the email, they can reset the TikTok password at any time.

1. Log into the email account using the freelancer's credentials.
2. **Change the password immediately** to something only we generate.
3. Save the new credentials to 1Password as `"<Provider> - <Persona Name>"` (e.g. `"Live - Blaze Money Crypto"` for Outlook/Hotmail).

---

## STEP 3 — Configure email forwarding to AgentMail

OTPs from TikTok need to land in the right AgentMail inbox so `fetch_otp.py` can retrieve them.

1. Target AgentMail inbox by brand:
   - **Blaze** → `tiktokblaze@agentmail.to`
   - **Flooently** → `tiktok@agentmail.to`
2. In the email provider's settings, configure forwarding:
   - **Outlook/Live:** Settings → Mail → Forwarding → enable + address + keep inbox copy
   - **Gmail:** Settings → Forwarding and POP/IMAP → add + verify + forward all
   - **Proton:** Settings → Mail → Forwarding → add address (paid plan required)
   - **Yahoo:** Settings → More Settings → Mailboxes → Forwarding
3. **Test with a sentinel email** before trusting the chain. Send a test email to the new account and confirm it lands in AgentMail within 1–2 minutes.

---

## STEP 4 — Provision the Multilogin browser profile

Create a new browser profile in Multilogin with a proxy matching the persona's country. Fingerprint (OS, timezone, locale) should also match.

1. Open Multilogin desktop or use the API (`multiloginRef.md`)
2. Create a new Browser profile (not Mobile)
3. **Proxy:** residential from the persona's country
4. **Fingerprint:** auto-generated, timezone/locale matched to proxy geo
5. **Name:** `<TikTok Handle> (TikTok)` — e.g. `blazemoney_crypto (TikTok)`
6. Save and capture the **profile UUID** (needed for Airtable)

---

## STEP 5 — Run the cookie robot on the new profile

Before logging into TikTok, give the profile a realistic browsing history via Multilogin's built-in cookie robot.

1. Profile settings → Cookie Robot
2. Default site pool, ≥30 min duration
3. Wait for completion (long-running — pause the adoption here and return when done)

---

## STEP 6 — Log into TikTok through the Multilogin profile

1. Launch the Multilogin profile via the launcher API
2. Connect via Playwright/CDP or drive the browser window manually
3. Go to `https://www.tiktok.com/login`
4. Enter the **freelancer's original TikTok credentials** (don't change them yet)
5. Handle verification if prompted:
   - **Email OTP** → check AgentMail via `fetch_otp.py`
   - **SMS OTP** → blocked unless freelancer shares the code or disables SMS 2FA
   - **CAPTCHA** → user solves manually (see `loginRef.md`)
6. Confirm authenticated FYP. Screenshot to `docs/projects/adopt-<slug>/login-success.png`.

---

## STEP 7 — Rotate the TikTok password

With our session now established inside the Multilogin profile:

1. Settings → Privacy and Security → Password
2. Generate a new password only we know
3. Save to 1Password as `"TikTok - <Persona Name>"` (e.g. `"TikTok - Blaze Money Crypto"`)
4. Confirm the current session is still authenticated after the change

> Email-first (Step 2) + TikTok-second (Step 7) rotation order is deliberate. Reversing it leaves the freelancer able to reset via the email they still control.

---

## STEP 8 — Confirm the desired username and set the bio

Still inside the authenticated TikTok session, tune the account's public-facing identity to match our brand.

**Username (TikTok handle):**
- Confirm the handle matches what we want (persona-style or brand-style).
- If it doesn't, change via Settings → Account → Edit profile → Username. **TikTok limits username changes to once every 30 days.**
- If we change it, also update the Airtable `Username` field to match.

**Display name:**
- Confirm matches the desired display. Freelancers often leave it random.
- Change via Settings → Edit profile → Name.

**Bio:**
- **NEVER invent bios from scratch.** Pull patterns from existing Blaze/Flooently accounts' `Bio` field in Airtable (query via REST API, filtered by brand).
- Brand accounts use a consistent multi-line template:
  ```
  <tagline> <emoji>
  usdc • usdt • <third thing>
  blaze.money
  ```
- Persona accounts use a single-line city/interest template.
- Propose 2–3 options recombining existing wording and let the user pick.
- Update via Settings → Edit profile → Bio.

**Profile photo:**
- Keep if realistic. Replace if generic/AI/placeholder.

Screenshot the finished profile to `docs/projects/adopt-<slug>/profile-after.png`.

---

## STEP 9 — Verify the account looks legitimate

Quick sanity check while still in the Multilogin browser:

- [ ] FYP serves niche-relevant content (if freelancer claimed warmup)
- [ ] Profile photo, bio, display name match the persona
- [ ] Following count is reasonable (non-zero if warmed, not spam-inflated)
- [ ] Search returns results (no shadowban indicator)
- [ ] FYP scroll looks organic (video counts/engagement plausible)

If anything looks wrong, pause and flag to the user.

---

## STEP 10 — Create the Airtable Accounts record

Use the REST API with the resolver (see `airtableRef.md`). **Never use the Airtable MCP.**

```bash
source .env.cli
eval "$(python3 .agents/skills/tiktok-warmup/resolve_airtable_schema.py --print-env)"
curl -s -X POST "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE" \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fields":{
    "Name": "<Persona Name>",
    "Username": "<tiktok_handle>",
    "Display Name": "<public display name>",
    "Bio": "<the exact multi-line bio we set on TikTok>",
    "TikTok Email": "<email>",
    "Brand": "<Blaze|Flooently>",
    "Platform": "TikTok",
    "Type": "Multilogin - Browser",
    "Multilogin Profile ID": "<uuid>",
    "Country": "<Country>",
    "Timezone": "<IANA timezone>",
    "UTC Offset": "<offset>",
    "Waking Start": "08:00",
    "Waking End": "23:00",
    "AgentMail Inbox": "<tiktokblaze@agentmail.to | tiktok@agentmail.to>",
    "Email Recovery": "Backed Up",
    "Niche Description": "<what the account was warmed for, in plain English>",
    "Profile Setup Stage": "Bio added",
    "Active": false
  }}'
```

Keep `Active=false` for now. We flip it in Step 14.

`Warmup Start Date` and `Search Terms` are intentionally left out here — they get set in Steps 11 and 12.

---

## STEP 11 — Generate and set Search Terms

**Critical — do not skip.** The warmup scripts pull from this pool to pick niche-relevant search queries every session. Without Search Terms, the scripts fall back to nothing and niche signal collapses.

1. **Pull reference terms from sibling accounts** in the same brand with related niches (e.g. for a crypto account, look at `blazemoney_stables` and `blazemoney_agents`):

   ```bash
   curl -s -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
     --data-urlencode 'filterByFormula=AND({Brand}="Blaze",{Search Terms}!="")' \
     --data-urlencode "fields[]=Username" \
     --data-urlencode "fields[]=Niche Description" \
     --data-urlencode "fields[]=Search Terms" \
     --get "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE"
   ```

2. **Generate fresh terms for this account** using the canonical prompt from `sessionDesignRef.md`:

   ```bash
   claude -p --model claude-sonnet-4-6 "Generate 12-15 varied TikTok search queries a real creator in this niche would plausibly search for. Return ONLY the queries as a comma-separated list, nothing else.

   Niche: <the Niche Description field from Airtable>"
   ```

   Match the language of the target FYP (Spanish for LATAM accounts, English for US-focused accounts, etc.) — critical for keeping the signal consistent with what the FYP is already serving.

3. **Review with the user** before writing to Airtable. Offer to blend with sibling terms if appropriate.

4. PATCH the Airtable record:
   ```bash
   curl -s -X PATCH "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE/<recordId>" \
     -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"fields":{"Search Terms":"term1, term2, term3, ..."}}'
   ```

---

## STEP 12 — Decide the warmup mode and set `Warmup Start Date`

Most judgment-heavy step. Do we trust the freelancer's warmup?

**Option A — treat as brand new (conservative, default):**
- `Warmup Start Date = today`
- Account starts at initial-warmup day 1 with the full 7-day protocol
- Safest when freelancer quality is uncertain

**Option B — honor the freelancer's warmup (only if Step 9 passed cleanly):**
- `Warmup Start Date = today - 8 days` (or further back)
- Account lands in **maintenance mode** immediately (10–20 min/day, 70% probability to run)
- Use when FYP is clearly niche-warmed and the profile looks legitimate

**Option C — partial credit:**
- `Warmup Start Date = today - N days` where N < 7
- Runs a few initial-protocol days before transitioning to maintenance
- Middle-ground for lightly-warmed accounts

PATCH the record:
```bash
curl -s -X PATCH "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE/<recordId>" \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"Warmup Start Date":"YYYY-MM-DD"}}'
```

---

## STEP 13 — Connect the account to Postiz

Postiz handles automated content scheduling. Connect so posts can be scheduled to the new account.

1. Open Postiz web UI → **Integrations → Add Integration → TikTok**
2. **Authenticate from inside the Multilogin browser profile** (not your regular browser) — keeps the IP/fingerprint signature TikTok has seen before. Authenticating from a different environment can flag the account.
3. Complete OAuth flow
4. Verify in Postiz: account appears in Integrations list
5. Run `postiz integrations:list` → copy the integration ID
6. PATCH the Airtable record with the Postiz Integration ID:
   ```bash
   curl -s -X PATCH "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE/<recordId>" \
     -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"fields":{"Postiz Integration ID":"<id>"}}'
   ```

---

## STEP 14 — Activate the account

Flip `Active = true`. The account will be picked up by the next `/execute-warmups` run. Issues surface naturally through the first session — no separate verification run needed.

```bash
curl -s -X PATCH "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE/<recordId>" \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"Active":true}}'
```

Tell the user the account is live.

---

## `todo.md` template

Write this to `docs/projects/adopt-<slug>/todo.md` at Step 0. Update in real time as steps complete.

```markdown
# Adopt TikTok account: <Persona Name> (@<handle>)

**Brand**: <Blaze | Flooently>
**Source**: Fiverr / <other>
**Contract / freelancer ref**: <freelancer username or contract ID>
**Date started**: <YYYY-MM-DD>

---

## Checklist

- [ ]  1. Credentials gathered from freelancer
- [ ]  2. Email password rotated + saved to 1Password as "<Provider> - <Persona>"
- [ ]  3. Email forwarding to AgentMail tested
- [ ]  4. Multilogin browser profile created — UUID: ______________
- [ ]  5. Cookie robot run
- [ ]  6. Logged into TikTok via Multilogin profile
- [ ]  7. TikTok password rotated + saved to 1Password as "TikTok - <Persona>"
- [ ]  8. Username + display name + bio + profile photo set on TikTok
- [ ]  9. Account legitimacy verified (FYP, profile, following)
- [ ] 10. Airtable record created (Active=false) — recXXXXXXXXXXXXXX
- [ ] 11. Search Terms generated and written to Airtable (~12–15 niche-relevant queries)
- [ ] 12. Warmup mode decided (A/B/C) + Warmup Start Date set
- [ ] 13. Postiz integration connected + Postiz Integration ID written to Airtable
- [ ] 14. Active = true, ready for /execute-warmups

---

## Notes / decisions

- (free-form — track anything surprising, blockers, decisions made, credentials rotated at what time, etc.)
```

---

## Open questions (iterate over time)

1. **SMS 2FA blocker** — what's the escalation path if the freelancer controls the phone and won't disable 2FA?
2. **Mode-decision heuristics for Step 12** — eventually want a repeatable rule (e.g. "if N followers + X claimed warmup days → Option B").
3. **Profile photo / bio from freelancer** — keep or replace policy?
4. **Content audit** — delete freelancer's posts or keep them?
5. **Cookie robot duration** — 30 min is a guess; Multilogin docs may suggest better.
6. **Proxy provider per country** — quality varies; do we have preferred vendors?
