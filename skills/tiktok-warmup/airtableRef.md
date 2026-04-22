# Airtable Reference

## How to access Airtable — ALWAYS use the MCP connector

**Never use curl, the Airtable REST API, or load env vars to access Airtable.** The Airtable MCP connector is already connected and requires no credentials. Use these MCP tools:

| Operation | MCP Tool |
|-----------|----------|
| Query / filter records | `mcp__claude_ai_Airtable__list_records_for_table` |
| Search records | `mcp__claude_ai_Airtable__search_records` |
| Create new records | `mcp__claude_ai_Airtable__create_records_for_table` |
| Update existing records | `mcp__claude_ai_Airtable__update_records_for_table` |
| Create field | `mcp__claude_ai_Airtable__create_field` |
| Get table schema | `mcp__claude_ai_Airtable__get_table_schema` |

**Note: The MCP does not support deleting records.** If deletion is needed, do it manually in the Airtable UI.

All tools take `base_id` and `table_id` (not table name) as parameters. Use the IDs in this file.

---

Base ID: `appfTuMpiXafoRNJG`

---

## Accounts table (tbljagCt5kJaBPNUl)

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

**Country → UTC offset fallback** (if UTC Offset field is blank):
- Mexico → -06:00 | Colombia → -05:00 | Argentina → -03:00
- Venezuela → -04:00 | Peru → -05:00 | Chile → -04:00 | Ecuador → -05:00
- Uruguay → -03:00 | Costa Rica → -06:00

---

## Scheduled Sessions table (tbl6ZiOVDWlsWkAuk)

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

## Session Log table (tbluS09ymOa9oBDwA)

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

## Manual Warmup Log table (tblyrJS8mr5clxqx1)

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

## Agent Messages table (tblNC6cauReYfeMm0)

| Field ID | Name | Type |
|----------|------|------|
| fld7fwTwwBbclbmlg | Message | singleLineText |
| fldYXAgKMNXVcTdPx | Timestamp UTC | dateTime |
| fldddewyBKvUiB1Do | Type | singleSelect: `action-needed` / `fyi` / `schema-change-needed` / `error-pattern` |
| fldO5BxoKxRxl1EVA | Status | singleSelect: `open` / `resolved` |
| fldmBZjO8aJE4A04f | Account | singleLineText |
| fldTmUGtz23DuKKLw | Session ID | singleLineText |
