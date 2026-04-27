# Nightly Audit Agent

Runs daily at **02:00 ET** in Claude remote execution. Pulls the last 24h of
warmup activity, identifies patterns the warmup process should adapt to, and
writes changes back into the skill so the next executor run automatically
benefits.

This is the closing loop of the system: **logs → analysis → skill changes →
next run uses updated skill**.

---

## What the agent does (in order)

### 1. Setup
- `cd` to a working clone of the consuming repo (the one that has `.env.cli` with
  `AIRTABLE_ACCESS_TOKEN`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`)
- Source `.env.cli`
- Resolve Airtable schema via `resolve_airtable_schema.py`
- Get current UTC

### 2. Pull yesterday's data

**From Supabase `warmup_actions`** — last 24h:
```bash
URL=$SUPABASE_URL
KEY=$SUPABASE_SERVICE_ROLE_KEY
SINCE=$(date -u -v-24H +"%Y-%m-%dT%H:%M:%SZ")
curl -s "$URL/rest/v1/warmup_actions?timestamp=gte.$SINCE&order=timestamp.asc&limit=10000" \
  -H "apikey: $KEY" -H "Authorization: Bearer $KEY"
```

**From Airtable `Session Log`** — last 24h: per-account roll-up (use the executor's existing query pattern).

### 3. Per-account analysis

For each active account, compute over the 24h window:
- `videos_watched`, `niche_pct` (from `video_watch` actions)
- `likes_actual`, `follows_actual`, `comments_actual`
- `follow_skipped_count`, `comment_skipped_count` (selector failures)
- `error_rate` (sessions with errors / total sessions)
- `health_score_trend` (today vs yesterday)

### 4. Pattern detection (decide what to change)

Apply these rules. Each rule is a `(condition, action)` pair. An "action" is
either an edit to a skill file, a Pending Action note for the account, or both.

| Pattern | Action |
|---------|--------|
| `follow_skipped_count > 5 × follows_actual` for >2 accounts | **Skill edit**: TikTok's follow button selector likely changed. Append a note to `runtimeLearnings.md` and add new candidate selectors to `_follow_current_creator` in `tiktok-warmup-poc.py`. Auto-merge. |
| Same for comments | Same pattern, applied to `_comment_on_video` |
| `niche_pct < 0.40` for ≥3 sessions on a single account | **Pending Action**: `<account>: niche % crashed to <X>% — refresh search terms before next run` |
| `health_score < 50` and dropping ≥10 points day-over-day | **Pending Action**: `<account>: health score collapsed (Xx→Xy). Pause for 24h to let TikTok normalize.` |
| `consecutive errors ≥ 5` for an account in a single day | **Skill edit**: append the error pattern + recovery to `runtimeLearnings.md`. Surface as Pending Action: `<account>: hit 5+ consecutive errors today — review before next run` |
| `follows_actual = 0` AND `videos_watched > 50` AND wk ≥ 2 | **Pending Action**: `<account>: 0 follows despite 50+ videos — check follow selector on next run` |
| `comments_actual = 0` AND wk ≥ 2 for ≥3 days running | **Pending Action**: `<account>: zero comments for 3+ days — bump comment frequency or fix selector` |
| New error category seen ≥3× in 24h not in `runtimeLearnings.md` | **Skill edit**: add a new entry to `runtimeLearnings.md` describing the symptom + suggested recovery. Auto-merge. |

### 5. Apply changes

For **skill edits**:
1. Use `Edit` tool to make the change in `.agents/skills/tiktok-warmup/<file>`
2. `cd .agents/skills/tiktok-warmup` and commit + push to fstack:
   ```bash
   git checkout -b "audit/$(date -u +%Y-%m-%d)"
   git add -A
   git commit -m "audit: <one-line summary of what changed and why>"
   git push -u origin HEAD
   gh pr create --title "Nightly audit $(date -u +%Y-%m-%d)" --body "..."
   ```
3. **Auto-merge** if the change is small (≤30 lines) and matches a "safe template":
   - Adding a new selector to a list
   - Appending a `runtimeLearnings.md` entry
   - Adding a new entry to `auditLogs.md`
   Otherwise leave the PR open for human review.

For **Pending Action** notes:
- PATCH the account row in Airtable: `{"fields": {"Pending Action": "<note>"}}`

### 6. Write to `auditLogs.md`

Append a single dated entry. Format from the file's preamble:

```markdown
## 2026-04-26T02:00:00Z

**Observation**: tiktok,flooently_spanish: 0 follows in 245 video_watch actions; follow_skipped_count=187 — selector almost always missing.

**Change made**: Added 2 new candidate selectors to `_follow_current_creator`:
`[data-e2e="recommend-card-follow-button"]` and `button:has-text("Follow"):has(svg.lucide-user-plus)`. Auto-merged PR #234.

**Files touched**: `tiktok-warmup-poc.py`, `auditLogs.md`

**Per-account actions written**: tiktok,flooently_spanish (selector check note)
```

If no actions were taken, still write an entry: `**No changes needed** — all metrics within target ranges.`

### 7. Notify Faiyam

If any Pending Actions were written OR a non-auto-merged PR exists, send a Telegram escalation summarizing what needs human review. Use the `curl` recipe in CLAUDE.md.

---

## Bounds (do not violate)

- **Never edit a file outside `.agents/skills/tiktok-warmup/`** — this includes Python scripts and `.md` references in that dir
- **Never delete code or content** — only append, or extend lists/selectors
- **Never auto-merge a change > 30 lines** — open as PR for human review
- **Never write a Pending Action longer than 200 chars** — keep them actionable
- **Never make changes if the 24h window had < 3 successful sessions** (insufficient signal)
