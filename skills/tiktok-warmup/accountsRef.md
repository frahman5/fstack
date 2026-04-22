# Account Registry — Auto-Refresh Protocol

Accounts are **defined in Airtable** (`Accounts` table, `tbljagCt5kJaBPNUl`) and
**consumed by the warmup Python scripts** via a JSON cache at
`scripts/warmup/accounts.json`. The agent refreshes the cache at the start of
every warmup run so new accounts (and deactivations) show up automatically —
no code edits required.

## Data flow

```
Airtable Accounts table  →  (agent, via MCP)  →  accounts.json  →  (Python)  →  ACCOUNTS dict
```

The agent does the refresh because:
- The Python scripts don't have Airtable REST credentials in `.env.cli`
- CLAUDE.md mandates the MCP for Airtable access from the agent side
- Keeping the scripts "just read JSON" keeps them simple and offline-runnable

## When to refresh

**At step 2 of every `/execute-warmups` run**, right after reading the
`Accounts` table. Specifically, whenever you pull the active accounts, also:

1. Cross-reference with Multilogin's `POST /profile/search` to get each
   profile's `folder_id` (authoritative — some profiles live at workspace root
   rather than a named folder)
2. Generate a stable slug per account — use the **TikTok handle** (the
   `Username` / `fldIObbRyfWyAo93t` field in Airtable), lowercased as-is:
   `flooently_spanish`, `blazemoney_latam`, `blaze__money`, etc.
   The handle is already unique within the active set and maps 1:1 to the
   Multilogin profile.
3. Write the result to `scripts/warmup/accounts.json`

You should refresh if ANY of these conditions is true:
- `_last_refreshed_utc` in the JSON is more than 24 hours old
- You observe an account in Airtable that isn't in `accounts.json`
- An account in `accounts.json` is no longer Active in Airtable (removal)
- A profile ID changed (account recreated in Multilogin)

## JSON schema

```json
{
  "_generated_note": "...",
  "_last_refreshed_utc": "2026-04-18T06:45:00Z",
  "accounts": {
    "<slug>": {
      "name": "Display Name",
      "handle": "tiktok_handle_without_@",
      "profile_id": "<multilogin UUID>",
      "folder_id": "<multilogin folder UUID — can be workspace root>",
      "op_item": "TikTok - <Display Name>",
      "brand": "Flooently" | "Blaze",
      "tiktok_email": "<email TikTok has on file>"
    }
  }
}
```

Required fields for a script-usable account: `name`, `handle`, `profile_id`,
`folder_id`, `op_item`. Optional but useful: `brand`, `tiktok_email`, `_notes`.

## Writing the cache (agent procedure)

```
1. Query Airtable Accounts table where Active=true:
   mcp__claude_ai_Airtable__list_records_for_table with
   baseId=appfTuMpiXafoRNJG, tableId=tbljagCt5kJaBPNUl
   fields=[Name, TikTok Username, Multilogin Profile ID, TikTok Email,
          Brand, Active, Paused Until, Pause Reason]

2. Query Multilogin for folder assignments:
   curl -X POST https://api.multilogin.com/profile/search
   with {"is_removed":false,"limit":100,"offset":0}
   → build a map profile_id → folder_id

3. For each Active account:
   - Skip if Paused Until > now
   - Skip if Multilogin Profile ID is missing (brand-only stub)
   - Skip if the profile isn't found in Multilogin
   - Slug from name: lowercase, collapse whitespace to underscore, keep first
     2 words for disambiguation only if needed (usually first word is enough)
   - Verify the 1Password item "TikTok - <Name>" exists in Claude-Accessible
     vault. If missing, note an anomaly but still include the account (login
     may be configured via a different method)

4. Write scripts/warmup/accounts.json with the new _last_refreshed_utc

5. Proceed with the rest of /execute-warmups
```

## Brand/folder cheat sheet (for reference — always prefer dynamic lookup)

| Brand | Default folder | Notes |
|-------|----------------|-------|
| Flooently | `1c5615aa-fae3-4184-a2a3-37226bd48b38` | Sebastian is here |
| Blaze    | `db07d2e1-4d3c-44fa-8a7f-7cc406410181` | Sofia, Diego |
| Workspace root | `76207486-0efb-4220-ad4f-c877333b1859` | Giulia, Blaze Money — root-level profiles |

**Always verify folder_id via Multilogin API** — a new account may be created
at root rather than in the brand folder.

## Slug-collision handling

If two accounts have names where the first word matches (e.g. two "Diego"s),
extend the slug to the next word ("diego_salazar", "diego_martinez"). Preserve
existing slugs — if "diego" is already in use and a new "Diego Martinez" is
added, the new slug should be "diego_martinez", not a rename of the old.

## Email/OTP routing per account

Each account's `tiktok_email` tells you where TikTok sends OTPs. Verify the
forwarding chain into `tiktok@agentmail.to` before relying on `fetch_otp.py`:

- **proton.me accounts**: forwarding is set up per-account at Proton.me →
  lands in `tiktok@agentmail.to` with `X-Pm-Forwarded-From` header. All four
  personas are configured this way.
- **`faiyam@blaze.money` (Blaze Money brand account)**: user is configuring
  forwarding from Fastmail/business inbox → `tiktok@agentmail.to`. Until
  that's verified, a Blaze Money re-login OTP may land in the real business
  inbox only.

Run a sentinel check from Gmail → the `tiktok_email` and see if it lands in
`tiktok@agentmail.to` before trusting the chain for a new account.
