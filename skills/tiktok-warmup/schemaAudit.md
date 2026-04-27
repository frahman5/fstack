# Schema Audit (2026-04-25)

Audit of the Flooently base. Goal: cut field count down to the minimum the
warmup process actually needs. Lower field count = lower confusion = lower
chance of cross-workspace drift.

Methodology: pulled every record from Accounts (n=19) and Session Log (n=67)
via the REST API, computed `non_null_count` and `non_null_pct` per field,
then `grep`-counted skill-file references per field name.

---

## Accounts table — 37 fields → proposed 19 fields (cut 18)

### KEEP (19)

| Field | Why |
|-------|-----|
| Name | Internal record identifier |
| Type | Filter (`!= "Manual"`) |
| Username | Plan slug |
| Active | Filter |
| Brand | Filter |
| Country | Inferred from Multilogin proxy if missing; powers timezone fallback |
| Timezone | Local time computation |
| Waking Start | Session-time gating |
| Waking End | Session-time gating |
| Multilogin Profile ID | Required to launch profile |
| TikTok Email | OTP recipient |
| Warmup Start Date | Day/week computation |
| Notes | Free-form ops notes |
| Search Terms | Niche priming |
| Paused Until | Lockout pause |
| Pause Reason | Pause context |
| Niche Description | Auto-healed at runtime; used for term regen |
| Platform | Plan slug (`platform,handle`) |
| Email Recovery | Health audit |
| AgentMail Inbox | Auto-healed at runtime |
| Pending Action | Nightly audit → next executor run |
| Health Score | Computed each session |

### DROP (15)

| Field | Why |
|-------|-----|
| UTC Offset | Derivable from Timezone — having both is a footgun (drift) |
| TikTok Handle | Duplicate of Username |
| TikTok Password | Always 0% — passwords belong in 1Password, never Airtable |
| Display Name | Setup-time field, not used during warmup |
| Bio | Setup-time field, not used during warmup |
| Profile Photo | Setup-time field, not used during warmup |
| Manual Action | Replaced by `Pending Action` |
| Profile Setup Stage | Setup-time only, no warmup use |
| Warmup Day | Always derived from `Warmup Start Date + today` |
| Warmup Notes | Duplicate of `Notes` |
| Manual Warmup Log | 0% populated, abandoned table link |
| Expected Warmup Completion Date | 32% populated, never read by skill |
| Postiz Integration ID | Postiz isn't part of warmup workflow |
| Studio URL | 5% populated, never read |
| Account Status | 100% populated but never read; Active is the actual signal |

### CONSOLIDATE singleSelect options

The `Type` field has 5 choices but only 3 are needed:
- Drop: `mobile`, `browser` (lowercase legacy duplicates)
- Keep: `Multilogin - Mobile`, `Multilogin - Browser`, `Manual`

---

## Session Log table — 14 fields → proposed 9 fields (cut 5)

### KEEP (9)

| Field | Why |
|-------|-----|
| Timestamp UTC | Sort + window queries |
| Account Name | Filter |
| Warmup Day | Joined into per-account stats |
| Duration (min) | Daily total |
| Likes | Aggregate per session (also in Supabase, but cheap to keep here) |
| Follows | Same |
| FYP Niche % | Per-session niche measurement |
| Searches Done | Aggregate per session |
| Error | Failure detection |

### DROP (5)

| Field | Why |
|-------|-----|
| Session # Today | Derivable from row count where `Account Name=X AND date(Timestamp UTC)=today` |
| Mood | 36% populated, no longer used (legacy of personality system) |
| Comment Left | 1% populated; Supabase `warmup_actions` has full comment data |
| Comment Text | 1% populated; same |
| Rewatches | 24% populated, never read by skill |

---

## Supabase — keep `warmup_actions` as-is

Already minimal (8 columns, 5 indexes). No changes proposed.

---

## Migration plan (when you approve)

1. **Update `canonicalSchema.json`** — remove the dropped fields from the canonical
2. **Backup the Airtable base** — export to CSV or duplicate the base before any drops
3. **Drop the fields in Airtable UI** — Airtable's API won't drop fields, must be done manually
4. **Run `validate_schema.py`** — confirm no drift remains
5. **Update consumer code** — any skill file referencing dropped fields needs cleanup (`grep` for the field name and remove)

Each workspace using this skill should run the validator after pulling the updated `canonicalSchema.json` — they'll see what they need to drop locally.

---

## Open questions for you

1. **Setup-time fields** (Display Name, Bio, Profile Photo, Profile Setup Stage) — currently in Accounts. Should they move to a separate `Account Setup` table, or just live in the account adoption skill's checklist (no Airtable persistence)?
2. **Notes vs Warmup Notes** — confirm `Warmup Notes` can be dropped (only 3 rows have content)
3. **Postiz** — is this still part of any workflow? If yes, we keep `Postiz Integration ID`
4. **Account Status** — is this used by anything outside this skill? If only used by warmup, we drop it.
