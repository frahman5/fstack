# /create-tiktok

Interactive walkthrough for creating a new TikTok account and getting it ready for warmup. Work through each step in order, waiting for the user to confirm before moving to the next.

**Reference files (read before starting):**
- `.claude/skills/tiktok-warmup/accountCreationRef.md` — email providers, ProtonMail slot counts, 1Password conventions, Airtable fields
- `.claude/skills/tiktok-warmup/airtableRef.md` — base/table/field IDs

---

## STEP 1 — Gather account info

Ask the user:
1. What is the desired TikTok handle? (e.g. `@blazemoney_dinero`)
2. Which brand does this account belong to — **Blaze** or **Flooently**?
3. What is the persona name or account display name? (used for the 1Password entry title)

Wait for answers before proceeding.

---

## STEP 2 — Choose email address

Read `accountCreationRef.md` → **ProtonMail account reference** section to check available alias slots.

Decision flow (in order):
1. **ProtonMail alias** — if any account has slots remaining, propose adding an alias there. Tell the user which ProtonMail account has slots and ask them to add the alias in ProtonMail Settings → Identity → Email addresses → Add address.
2. **Yahoo.com** — if the user prefers a fresh identity or Proton slots are full, ask them to create a `@yahoo.com` address.
3. **Outlook.com** — fallback; create at signup.live.com, no phone required.

Also determine the **AgentMail inbox** based on the brand:
- Blaze accounts → check `accountCreationRef.md` for the current mapping (most Blaze accounts use `tiktokblaze@agentmail.to`, Flooently accounts use `tiktok@agentmail.to`)
- When in doubt, ask the user

Ask the user to:
- Create or confirm the email address
- Set up forwarding to the appropriate AgentMail inbox
- Tell you the final email address when done

Wait for the email address before proceeding.

---

## STEP 3 — Create 1Password entry

Read `accountCreationRef.md` → **1Password Setup** section for field conventions and password requirements.

Run:
```bash
export OP_SERVICE_ACCOUNT_TOKEN=$(grep OP_SERVICE_ACCOUNT_TOKEN .env.cli | cut -d= -f2-)
op item create \
  --category=Login \
  --title="TikTok - <Display Name>" \
  --vault="Claude-Accessible" \
  --url=https://www.tiktok.com \
  --generate-password="letters,digits,symbols,18" \
  "username=<email>" \
  "notesPlain=TikTok username: @<handle> (TBD — update after signup)"
```

**Verify the password contains at least one of `# ? ! @`.** If not, regenerate:
```bash
op item edit "TikTok - <Display Name>" --vault="Claude-Accessible" --generate-password="letters,digits,symbols,18"
```
Retry until the password passes. Reveal it to confirm:
```bash
op item get "TikTok - <Display Name>" --vault="Claude-Accessible" --reveal --fields password
```

If this account shares a ProtonMail account with another entry, add a note in `notesPlain` linking both entries.

Tell the user: "1Password entry created. Password is ready."

---

## STEP 4 — Create the TikTok account (user does this manually)

Guide the user through the signup flow:

1. Open the Multilogin browser profile for this account (or a clean browser)
2. Go to tiktok.com → **Sign up** → **Use phone or email** → **Email**
3. Enter the email from Step 2
4. Enter a realistic birthday (match persona if applicable)
5. On the password screen — open 1Password, copy the password from Step 3, paste it in
6. Enter the desired handle from Step 1
   - If TikTok rejects it, try adding a suffix like `_`, `.co`, or a short number
   - Note the final handle actually used

**OTP handling:** If TikTok sends a verification code to the email:
```bash
source .env.cli
agentmail inboxes:messages list --inbox-id <agentmail-inbox>
agentmail inboxes:messages retrieve --inbox-id <agentmail-inbox> --message-id "<id>"
```
Wait up to 60s polling every 10s. If no OTP arrives in 60s → stop and troubleshoot forwarding.

Ask the user: "Account created? What is the final handle TikTok accepted?"

Wait for confirmation and final handle before proceeding.

---

## STEP 5 — Initial scroll session (do this before any admin work)

While the user is still in the app, ask them to spend **5–10 minutes scrolling the For You page** before closing TikTok. This makes the account look human from day one and avoids the pattern of "account created, immediately abandoned".

Guide them:
- Scroll the For You page naturally — pause on videos for a few seconds, let some play through
- Follow 1–2 accounts that match the niche (e.g. for a LatAm finance account: personal finance creators, expat life, remittance tips)
- Like 2–3 videos that feel on-brand
- Do NOT post anything yet

Ask the user: "Done scrolling? Roughly how long did you spend?" Note the time in the Airtable record later.

Wait for confirmation before proceeding.

---

## STEP 6 — Update 1Password with final handle

```bash
export OP_SERVICE_ACCOUNT_TOKEN=$(grep OP_SERVICE_ACCOUNT_TOKEN .env.cli | cut -d= -f2-)
op item edit "TikTok - <Display Name>" \
  --vault="Claude-Accessible" \
  "notesPlain=TikTok username: @<final_handle>. Forwards to <agentmail-inbox>."
```

If the handle differed from what was requested, note that too.

---

## STEP 7 — Update ProtonMail account reference

If a ProtonMail alias was created in Step 2, update the alias count in `accountCreationRef.md` (the ProtonMail account reference section). Edit the file at `.agents/skills/tiktok-warmup/accountCreationRef.md`, increment the alias count for the relevant account, add a row to the alias table, then commit and push:

```bash
cd .agents/skills/tiktok-warmup
git add accountCreationRef.md
git commit -m "chore: add <email> alias to ProtonMail account reference"
git push
```

---

## STEP 8 — Create Airtable record

Use the Airtable MCP to create a new record in the Accounts table (base: `appfTuMpiXafoRNJG`, table: `tbljagCt5kJaBPNUl`) with these fields:

| Field | Value |
|-------|-------|
| Name | Display name (e.g. "BlazeDinero") |
| TikTok Email (`fldAkBrbwxveuSxzS`) | Email from Step 2 |
| TikTok Username (`fldIObbRyfWyAo93t`) | Final handle (without @) |
| TikTok Handle (`fldV2clNwT8EZtqyV`) | Same as username |
| AgentMail Inbox (`fldPOWWEdtQvbxbwg`) | `tiktok@agentmail.to` or `tiktokblaze@agentmail.to` |
| Active (`fldTRC4UyWNTwi7VP`) | false — set true at the end |
| Warmup Start Date (`fldsSGOno5ZsABWdy`) | Today's date |

---

## STEP 9 — Write the bio

Pull the bios of similar accounts from Airtable (filter by brand or niche) to use as reference. Propose 3 bio options following the format used by existing accounts. Wait for the user to pick one or request changes.

Do NOT write the bio to Airtable yet — confirm first.

---

## STEP 10 — Set niche description and search terms

Based on the account's language, geography, and cultural angle, propose:

1. **Niche Description** — one sentence describing the account's content niche and target audience (field `fldPfV1FhU1LKoSRC`)
2. **Search Terms** — 12–15 comma-separated plain-language TikTok search queries (field `fldnFSwwpxVigKXel`). No hashtags. Mix of languages matching the account's target audience. Match the format of existing accounts.

Show the proposed values and wait for approval before writing.

---

## STEP 11 — Write bio + niche to Airtable and mark Active

Once the user approves bio and search terms, write everything to Airtable in one update:
- Bio (if there's a bio field — check schema)
- Niche Description
- Search Terms
- Active → true
- Warmup Start Date → today

Confirm all fields were written successfully.

---

## STEP 12 — Summary

Print a clean summary:

```
✅ @<handle> is ready for warmup

Email:        <email> → <agentmail-inbox>
1Password:    TikTok - <Display Name>
Airtable:     <record ID> — Active, warmup starts today
Bio:          <bio line 1>
Search terms: <count> terms set
```

Remind the user: the account will be picked up automatically on the next `/execute-warmups` run.
