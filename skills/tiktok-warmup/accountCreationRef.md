# TikTok Account Creation Reference

How to create a TikTok account for a persona and store credentials in 1Password.

## 1Password Setup (do this first)

Before creating the TikTok account, pre-create the 1Password entry so the password is ready to paste.

**Vault:**
- Always use the **Claude-Accessible** vault for all personas (both Blaze Money and Flooently).

**Field conventions:**
- **Title**: `TikTok - <Full Name>` (e.g. `TikTok - Valentina Ospina`)
- **Username field**: the persona's email address (what TikTok uses to log in)
- **Notes field**: `TikTok username: @<handle>` — the desired TikTok handle
- **Password**: generated (see requirements below)

**CLI command:**
```bash
op item create \
  --category=Login \
  --title="TikTok - <Full Name>" \
  --vault="Claude-Accessible" \
  --url=https://www.tiktok.com \
  --generate-password="letters,digits,symbols,18" \
  "username=<email>" \
  "notesPlain=TikTok username: @<tiktok_handle>"
```

**Password requirements (TikTok):**
- 8–20 characters
- At least 1 letter, 1 number, 1 special character from: `# ? ! @`
- `--generate-password="letters,digits,symbols,18"` satisfies this, but verify the generated password contains one of `# ? ! @` before using it
- If it doesn't, regenerate: `op item edit "<item title>" --generate-password="letters,digits,symbols,18"`

**After the TikTok account is created:**
- Update the entry title if needed
- Confirm the username field matches the actual handle used (TikTok sometimes rejects the requested handle)
- Mark the account Active in Airtable once TikTok signup is complete

## TikTok Account Creation Steps

1. Open the persona's Multilogin profile (Mobile → cloud phone, or Browser → Chromium)
2. Navigate to TikTok (app on cloud phone, or tiktok.com in browser)
3. Tap **Sign up** → **Use phone or email** → **Email**
4. Enter the persona's email (from Airtable `TikTok Email` field)
5. Enter birthday (use the persona's birth year, pick a realistic date)
6. On the password screen, open 1Password, copy the generated password from the pre-created entry, paste it in
7. Enter the username from Airtable (`TikTok Username` field) — if TikTok rejects it, append a short suffix (e.g. `.7`, `_mx`) and update both 1Password and Airtable
8. Skip phone verification if possible; complete email verification if required
9. After signup: update Airtable `TikTok Handle` field with the final username

## AgentMail Inboxes

We have two AgentMail inboxes for receiving TikTok OTPs:

| Inbox | Used for |
|-------|----------|
| `tiktok@agentmail.to` | All Flooently accounts + most Blaze accounts |
| `tiktokblaze@agentmail.to` | Blaze-specific accounts (blazemoneystables, giuseppeblanco, etc.) |

The Airtable `AgentMail Inbox` field (fldPOWWEdtQvbxbwg) tracks which inbox each account's email forwards to. When fetching OTPs, use the inbox from that field — don't assume `tiktok@agentmail.to`.

**Future intent:** split into `tiktokblaze@agentmail.to` and `tiktokflooently@agentmail.to` to keep brands cleanly separated.

## Email Providers

### Decision flow — pick email in this order

1. **Check ProtonMail accounts first** — each paid ProtonMail account supports up to 10 aliases. If any account has slots remaining, add an alias there (fastest, no phone verification).
2. **Outlook.com** — create a fresh account if you need a completely new identity or all Proton slots are full.
3. **Tuta** — fallback only; no external forwarding, so OTPs must be read from the Tuta app directly.

### ProtonMail account reference

We have (at least) two ProtonMail accounts. Always check slot count before creating a new Proton account.

**Account B — blazemoneystables account** (forwards to `tiktokblaze@agentmail.to`):
| Alias | TikTok account |
|-------|----------------|
| blazemoneystables@proton.me | @blazemoney_stables |
| giuseppeblanco@proton.me | (TBD) |
- **2 / 10 aliases used — 8 slots remaining**
- 1Password: both entries note "Same ProtonMail account as [other alias]"

**Account A — main Flooently/Blaze account** (forwards to `tiktok@agentmail.to`):
| Alias | TikTok account |
|-------|----------------|
| andresrestrepo9421@proton.me | andresrestrepo9421 |
| luciafontaine97@proton.me | luciafontaine97 |
| catalinasilva96@proton.me | cata_silva96 |
| sofiareyes9892@proton.me | blazemoney_latam |
| diegosalazar9531@proton.me | blazemoney_agents |
| s.vargas.1995@proton.me | flooently_spanish |
| giuliaromano97@proton.me | flooently_italian |
- **7 / 10 aliases used — 3 slots remaining** *(verify in ProtonMail settings)*
- Note: we don't yet have the login for Account A in 1Password — ask the user if needed.

> **Adding a ProtonMail alias:** Settings → Identity → Email addresses → Add address. Aliases share the same inbox and forwarding rule.

### Provider reference

- **ProtonMail** (`@proton.me`) — alias on existing Mail Plus account. Forwarding works. **Preferred for AgentMail OTP flow.**
- **Tuta** (`@tuta.com` / `@tutamail.com`) — alias on existing account. No forwarding — OTPs read from app directly. **Use only when Proton aliases are exhausted.**
- **Outlook.com** (`@outlook.com`) — create new account at signup.live.com. No phone required (CAPTCHA only), free forwarding. **Use when you need a fresh identity with no ties to existing accounts.**
- **Zoho** — **DO NOT USE** — requires phone at signup, our number has been used too many times.
- **mail.com** — **DO NOT USE** — captcha blocks signup.
- **Yandex** — **DO NOT USE** — SMS verification, codes don't reliably arrive.

> **Outlook.com forwarding:** Settings → Mail → Forwarding → enable to the appropriate AgentMail inbox (see table above). Keep a copy in inbox. No paid plan needed.

> **Tuta does NOT support external email forwarding.** E2E encryption by design. OTPs must be read from the Tuta desktop or web app. See loginRef.md for the `open -a "Tuta Mail"` flow.

## Airtable Fields to Update After Creation

| Field | Value |
|-------|-------|
| `TikTok Email` (`fldAkBrbwxveuSxzS`) | Email used to sign up |
| `TikTok Username` (`fldIObbRyfWyAo93t`) | Final @handle (without @) |
| `TikTok Handle` (`fldV2clNwT8EZtqyV`) | Same as username |
| `AgentMail Inbox` (`fldPOWWEdtQvbxbwg`) | Which AgentMail inbox the email forwards to (`tiktok@agentmail.to` or `tiktokblaze@agentmail.to`) |
| `Active` (`fldTRC4UyWNTwi7VP`) | true — triggers warmup scheduling |
| `Warmup Start Date` (`fldsSGOno5ZsABWdy`) | Today's date |
