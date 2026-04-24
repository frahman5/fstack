# Airtable Reference

## 🚨 HARD RULE: REST API only, never the MCP

**Never use the Airtable MCP (`mcp__claude_ai_Airtable__*`).** Always use the Airtable REST API with `$AIRTABLE_ACCESS_TOKEN` from `.env.cli`. If the token is rejected, rotate it — do not fall back to MCP.

**Why:** MCP returns unfiltered cross-brand data (e.g. Flooently accounts bleeding into Blaze queries), costs extra round-trips, and has been flaky. The REST API with explicit `filterByFormula` gives precise, repeatable queries.

## Base discovery (no hardcoded IDs)

The skill is shared across repos (blaze-platform, Flooently). Each repo has its own Airtable base with the same schema. **Base IDs, table IDs, and field IDs all vary per repo** — we auto-discover them at runtime instead of hardcoding.

### How it works

`.agents/skills/tiktok-warmup/resolve_airtable_schema.py` finds the right base by schema fingerprint — a base qualifies if it has both `Accounts` and `Session Log` tables with the canonical fields listed below. If multiple bases match (e.g. Blaze and Flooently bases in the same workspace), it disambiguates by brand — detects the current repo's brand from cwd and looks for an `Accounts` row tagged that brand.

Result is cached at `scripts/warmup/airtable-schema-cache.json` (gitignored). Subsequent runs are instant.

### Using the resolver

At the start of any workflow that touches Airtable:

```bash
source .env.cli
eval "$(python3 .agents/skills/tiktok-warmup/resolve_airtable_schema.py --print-env)"
```

After this, the following env vars are set:

| Var | Example |
|-----|---------|
| `AIRTABLE_BASE_ID` | `appfTuMpiXafoRNJG` |
| `AIRTABLE_BRAND` | `Blaze` |
| `AIRTABLE_ACCOUNTS_TABLE` | `tbljagCt5kJaBPNUl` |
| `AIRTABLE_SESSION_LOG_TABLE` | `tbluS09ymOa9oBDwA` |
| `AIRTABLE_SCHEDULED_SESSIONS_TABLE` | (if present) |
| `AIRTABLE_AGENT_MESSAGES_TABLE` | (if present) |
| `AIRTABLE_MANUAL_WARMUP_LOG_TABLE` | (if present) |

Field IDs are NOT exported as env vars — they're in the cache JSON under `tables.<Table Name>.fields.<Field Name>`. To read one in bash:

```bash
jq -r '.tables.Accounts.fields["TikTok Username"]' scripts/warmup/airtable-schema-cache.json
```

Python scripts can just load the JSON directly.

### If discovery fails

- **"No base matched the TikTok warmup schema"** — token doesn't have access to the warmup base. Add the right base under **Access** at https://airtable.com/create/tokens.
- **"Multiple bases match ... none have accounts tagged Brand=X"** — the schema matches in multiple bases but no accounts are brand-tagged. Tag at least one account in the intended base with the current brand, then rerun.
- **"Ambiguous: multiple bases match schema AND have brand rows"** — two bases both have accounts tagged the same brand. Pick one and remove access to the other in the token, or add `AIRTABLE_BASE_ID=...` to `.env.cli` to override discovery.

### To force re-discovery

```bash
python3 .agents/skills/tiktok-warmup/resolve_airtable_schema.py --refresh
```

Useful when:
- Token changed
- Schema changed (new table or renamed field)
- You just connected the token to a new base and want to adopt it

## Canonical API calls

Once env vars are loaded:

List active Blaze accounts:

```bash
curl -s -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  --data-urlencode "filterByFormula=AND({Active}=TRUE(),{Brand}=\"$AIRTABLE_BRAND\")" \
  --get "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE"
```

Create a Session Log row (field names accepted for create/update):

```bash
curl -s -X POST "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_SESSION_LOG_TABLE" \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"Account Name":"Farah Job","Duration (min)":0,"Session Kind":"maintenance-skip"}}'
```

Update a record:

```bash
curl -s -X PATCH "https://api.airtable.com/v0/$AIRTABLE_BASE_ID/$AIRTABLE_ACCOUNTS_TABLE/$RECORD_ID" \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fields":{"TikTok Username":"blazemoneycrypto"}}'
```

Create a field via Meta API (needs `schema.bases:write`):

```bash
curl -s -X POST "https://api.airtable.com/v0/meta/bases/$AIRTABLE_BASE_ID/tables/$AIRTABLE_SESSION_LOG_TABLE/fields" \
  -H "Authorization: Bearer $AIRTABLE_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Session Kind","type":"singleSelect","options":{"choices":[{"name":"initial-warmup"},{"name":"maintenance-run"},{"name":"maintenance-skip"}]}}'
```

**Note: the API does not support deleting records programmatically.** Do deletes in the Airtable UI.

---

## Expected schema (required fields by table name)

The fingerprint resolver checks these table + field names. IDs below are the canonical Blaze-base values for reference, but **do not use them directly in code** — always resolve via the cache.

## Accounts table (`Accounts`)

Canonical Blaze-base ID: `tbljagCt5kJaBPNUl`

| Field ID | Name | Type |
|----------|------|------|
| fldmrNwWerD8PM5qh | Name | singleLineText |
| fldikxADa8PQjEuHj | Type | singleSelect: `Multilogin - Mobile` / `Multilogin - Browser` / `Manual` |
| fldIObbRyfWyAo93t | TikTok Username | singleLineText |
| fldTRC4UyWNTwi7VP | Active | checkbox |
| fld8CBhv8itI2Lipl | Brand | singleSelect: `Flooently` / `Blaze` |
| fldwz3PYTWl0j8uH0 | Country | singleLineText |
| fldczl7hFNqxhRgCo | Timezone | singleLineText (e.g. "America/Bogota") |
| fldPEQveQPPM93uu6 | UTC Offset | singleLineText (e.g. "-05:00") |
| fldw3ebuUJG3ewDt7 | Waking Start | singleLineText (e.g. "08:00") |
| fldjB8k02W1wscr65 | Waking End | singleLineText (e.g. "23:00") |
| fld9knhdqkuYzwCfJ | Multilogin Profile ID | singleLineText |
| fldAkBrbwxveuSxzS | TikTok Email | email |
| fldsSGOno5ZsABWdy | Warmup Start Date | date |
| fldnFSwwpxVigKXel | Search Terms | multilineText (comma-separated pool, ~15 terms) |
| fldgmSBLf57Uaqa5Y | Display Name | singleLineText |
| fldSHQzxUkiAgD9Th | Bio | singleLineText |
| fldggqUPec3SzGbfW | Profile Photo | singleLineText |
| fldCjyJhihKXxaTBe | Manual Action | multilineText |
| fldHRPY6TEYGc2UUd | Profile Setup Stage | singleSelect |
| fld8eGooYa0yNDf3x | Warmup Day | number |
| fldLIF7dov0zBT7iV | Manual Warmup Log | multipleRecordLinks → Manual Warmup Log table |
| fldmySQAr2mZjw6ne | Email Recovery | singleSelect: `Backed Up` / `Not Set Up` |
| (dynamic) | AgentMail Inbox | singleLineText — e.g. `tiktokblaze@agentmail.to` or `tiktok@agentmail.to`; blank = forwarding not yet active, use Tier 2 direct email fallback |

**Country → UTC offset fallback** (if UTC Offset field is blank):
- Mexico → -06:00 | Colombia → -05:00 | Argentina → -03:00
- Venezuela → -04:00 | Peru → -05:00 | Chile → -04:00 | Ecuador → -05:00
- Uruguay → -03:00 | Costa Rica → -06:00

---

## Scheduled Sessions table (`Scheduled Sessions`)

Canonical Blaze-base ID: `tbl6ZiOVDWlsWkAuk`

| Field ID | Name | Type |
|----------|------|------|
| fldQB8ZUg0xJy5cGH | Session ID | singleLineText (primary key) |
| fldw78znLH2oRJWYT | Account Name | singleLineText |
| fldvlgjfBLRpc2aup | Planned Time (UTC) | dateTime |
| fldwv7pim7ejWJmAt | Status | singleSelect: `scheduled` / `running` / `completed` / `failed` / `skipped` / `needs-retry` |
| fldK3ZdWXfpwHhydp | Session Type | singleSelect: `burst-cluster` / `doomscroll` / `regular` |
| fldlD9Ekm5VxaKvPj | Cluster Info | singleLineText (e.g. "1 of 3") |
| fldcgaX0qGw6VWlmu | Actual Start (UTC) | dateTime |
| fldjGzkxjjFlDsI32 | Duration (min) | number |
| fld6tlOTkTpMKLiuq | Likes | number |
| fldwxkUDwureiGCeJ | Follows | number |
| fldt20AVQi77yUFD8 | Comment Left | checkbox |
| fldcAHdbBIThXC5Yo | Comment Text | singleLineText |
| fldKr8EHMbjFGzAb2 | Searches Done | singleLineText |
| fldPsgFIWiHXAR03z | Error | singleLineText |
| fld5eX6p511lve6Ka | Notes | singleLineText |

---

## Session Log table (`Session Log`)

Canonical Blaze-base ID: `tbluS09ymOa9oBDwA`

| Field ID | Name | Type |
|----------|------|------|
| fldGckcL5Qc5vcug9 | Timestamp UTC | dateTime |
| fldlUusi4GgT4n3oS | Account Name | singleLineText |
| fldAGlCfxRJLJE6NB | Warmup Day | number |
| fld4r6rSbhADxC5lk | Session # Today | number |
| fldXwZrc5w5oR0OIk | Mood | singleSelect: `passive` / `explorer` / `fyp` / `rabbit-hole` / `doomscroll` / `burst` |
| fldiowoint6Gohzzw | Duration (min) | number |
| fldQySoabhxMjtDiV | Likes | number |
| fldjlQ9xz0Wwwea9m | Follows | number |
| fldsrWgDulMBACpCT | Comment Left | checkbox |
| fldqYFV4prfupAZLC | Comment Text | singleLineText |
| fldQHQm3TFzw1lZBC | FYP Niche % | number — 0.0–1.0, populated by script; daily target 70–90% |
| fldtLSEqt4pkBwqyQ | Searches Done | singleLineText |
| fldiS0O5IvQYeIyRH | Rewatches | number |
| fldWHqaARjy1nsg4E | Error | singleLineText (blank = success) |

---

## Manual Warmup Log table (`Manual Warmup Log`)

Canonical Blaze-base ID: `tblyrJS8mr5clxqx1`

One row per manual warmup session. Linked to Accounts. Tracks all warmup activity on manually-managed accounts.

| Field ID | Name | Type |
|----------|------|------|
| fldeB89UwkJV4FgJt | Date | date (primary key) |
| fld3PxpYpy35W1QNd | Account | multipleRecordLinks → Accounts table |
| fldE2gOSwH0pFFPjv | Duration (min) | number |
| fldcg7MHP40VBoVoD | Activity Type | singleSelect |
| fld0n4K2JOERIsKnn | Warmup Day | number |
| fldpKYwOyZHGaImrK | Stage | singleSelect |
| fldkbv6VnxB8yA8VW | Notes | multilineText |

---

## Agent Messages table (`Agent Messages`)

Canonical Blaze-base ID: `tblNC6cauReYfeMm0`

| Field ID | Name | Type |
|----------|------|------|
| fld7fwTwwBbclbmlg | Message | singleLineText |
| fldYXAgKMNXVcTdPx | Timestamp UTC | dateTime |
| fldddewyBKvUiB1Do | Type | singleSelect: `action-needed` / `fyi` / `schema-change-needed` / `error-pattern` |
| fldO5BxoKxRxl1EVA | Status | singleSelect: `open` / `resolved` |
| fldmBZjO8aJE4A04f | Account | singleLineText |
| fldTmUGtz23DuKKLw | Session ID | singleLineText |
