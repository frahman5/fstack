# Session Design — Task Mix by Week

How to compose the per-account task queue for a warmup session. The right mix
depends heavily on **warmup week**: early weeks need strong, explicit niche
signals because the FYP algorithm hasn't been primed yet; later weeks can lean
more on `scroll_fyp` because the algorithm itself starts serving on-niche
content.

## Guiding principle: ≥50% niche-explicit in early weeks

**Every session's total time should be ≥50% on-niche content** (search results,
niche hashtag feeds, niche-creator deep dives). In week 1 day 1–3, the
account's `/foryou` serves mostly generic random content, so `scroll_fyp`
counts toward the "random" budget, not niche. Don't over-weight it early.

Measure niche ratio empirically from the Session Log activities list — sum
`duration_min` of the niche-explicit task types below divided by total session
time. Target ≥50%.

## Task types (explicit-niche vs ambient)

| Script | Niche-explicit? | Notes |
|--------|-----------------|-------|
| `niche_search.py` | ✅ yes — 100% on-niche | Uses search URL + on-topic search results |
| `browse_hashtag.py` | ✅ yes — 100% on-niche | Scrolls `/tag/<slug>` feed, all tagged content |
| `deep_dive_creator.py` | ✅ yes **when the creator was reached from a niche search/tag** | Avatar click from FYP is NOT niche; from niche search result IS |
| `scroll_fyp.py` | ❌ no, in weeks 1–2 | Random FYP content until the algorithm adapts. After ~week 2, starts serving niche |

## Recommended task queues

### Week 1 (days 1–7): niche priming heavy

Goal: establish a strong behavioral fingerprint on the niche fast so the FYP
starts serving on-topic within 1–2 weeks.

| Task | Duration | Why |
|------|----------|-----|
| `niche_search` (term A) | ~3 min / 5 videos | Search-dwell is the strongest FYP signal |
| `browse_hashtag` (slugified term B) | ~4 min / max-likes 2 | 100% on-niche videos + watch time |
| `deep_dive_creator` (on a niche creator from the last task) | ~2 min / 3–4 vids / +follow | Niche-creator follow is a durable signal |
| `browse_hashtag` (slugified term C) | ~3 min / max-likes 1 | Diversify the niche signal across hashtags |
| `scroll_fyp` | 2 min max / max-likes 1 | Brief observation of how FYP is reacting |

Total: ~14 min, ≥85% on-niche.

Week 1 caps: 5–8 likes, 2–3 follows, 0 comments, 1–2 searches. Honor these.

### Week 2 (days 8–14): still mostly niche, start mixing

| Task | Duration |
|------|----------|
| `niche_search` (term A) | ~3 min |
| `browse_hashtag` (term B) | ~3 min |
| `scroll_fyp` (FYP should have ~30% niche by now) | ~4–5 min |
| `deep_dive_creator` | ~2 min |
| `browse_following` (if any niche creators followed) | ~2 min |

### Week 3+ (day 15+): FYP-driven with periodic niche refreshes

Once FYP is primarily niche-driven, flip the ratio — most time on `scroll_fyp`,
occasional explicit tasks to refresh signals and prevent drift.

| Task | Duration |
|------|----------|
| `scroll_fyp` | ~6–8 min (primary) |
| `niche_search` (term A) | ~2–3 min |
| `click_hashtag` / `visit_creator` (from FYP — algorithmic creators now) | ~2 min |
| `scroll_fyp` cooldown | ~3 min |

## Picking search terms and hashtag slugs

The Airtable `Search Terms` field holds a stable pool of ~12–15 niche-relevant queries per account (set at adoption time via `adoptAccountRef.md` Step 11). Every session draws from this pool — **but never verbatim the same string twice.** Apply fuzzing so TikTok's pattern-detection doesn't flag us for repeating identical queries.

### Mix ratios per session

When picking which term to use for a given `niche_search` call, apply fuzzing with roughly this distribution:

| Mode | Share | What it looks like |
|------|-------|--------------------|
| **Verbatim** — use the pool term as-is | ~50% | `"USDC a pesos"` → `"USDC a pesos"` |
| **Minor typo** — single-char edit | ~20% | `"USDC a pesos"` → `"USDC a peos"` (skip letter) or `"USDC a peso"` (missing s) |
| **Word reorder / micro-paraphrase** | ~15% | `"USDC a pesos"` → `"pesos a USDC"` or `"cambiar USDC a pesos"` |
| **Semantic cousin** — related term not in pool | ~10% | `"USDC a pesos"` → `"stablecoin a pesos"` or `"dolar digital LATAM"` |
| **Language flip** (bilingual accounts only) | ~5% | `"USDC a pesos"` → `"USDC to pesos"` |

Realistic typo patterns for a desktop QWERTY keyboard: adjacent-key swaps (`usdc`→`usdv`), doubled letters (`USDC`→`USDCC`), missed letter (`stablecoin`→`stablecon`), transposed letters (`crypto`→`crytpo`). Avoid unrealistic typos (swapping letters that aren't adjacent on the keyboard).

### Execution

The agent applies fuzzing at plan time (in `/execute-warmups` Step 4), not inside the Python scripts. For each session that includes a `niche_search` task:

1. Pick a term from the Airtable pool (rotate — don't repeat the same pool-term within a 7-day window if possible)
2. Roll for fuzzing mode per the distribution above
3. Apply the fuzz, producing the actual search string
4. Pass it to `niche_search.py` as `--term "<fuzzed string>"`
5. Log the actual string used in Session Log `Searches Done` so we can audit variation

### What NOT to do

- ❌ Cache the fuzzed versions into Airtable — pool terms are inputs, fuzzing is stateless per session
- ❌ Use the same fuzzed variant twice in one session
- ❌ Apply fuzzing to `browse_hashtag` inputs (hashtags must slugify cleanly; fuzzing breaks the `slugify()` mapping)
- ❌ Introduce typos so extreme the query returns no results (TikTok returning zero videos is a worse signal than a repeated exact query)

### Regenerating the pool

If an account's Search Terms pool is exhausted, stale, or clearly mismatched with the current FYP niche, regenerate via the canonical LLM prompt:

```bash
claude -p --model claude-sonnet-4-6 "Generate 12–15 varied TikTok search queries a real creator in this niche would plausibly search for. Match the language to the audience. Return ONLY the queries as a comma-separated list, nothing else.

Niche: <the Niche Description field from Airtable>"
```

Match language to the FYP (Spanish for LATAM accounts, English for US, etc). Pass different terms to `niche_search` and `browse_hashtag` in the same session — `browse_hashtag` will `slugify()` the term (lowercase, alphanum-only, max 40 chars) to form a valid tag URL.

## What `scroll_fyp` is still for

- **Week 3+ primary activity**, as noted.
- **End-of-session cooldown** in early weeks (2 min) to observe the FYP's
  current state and let the algorithm record watch time on whatever it's
  serving.
- **Never the majority of a week-1 session.**

## Anti-patterns

- ❌ Two `scroll_fyp` calls totaling >5 min in week 1 — starves niche budget.
- ❌ `deep_dive_creator` from a fresh `/foryou` avatar click in week 1 — you
  just gave the FYP your watch time on a random creator. Always chain
  `deep_dive_creator` AFTER `niche_search` or `browse_hashtag` so the creator
  you dive on was surfaced by a niche-relevant query.
- ❌ Commenting or search-spamming in week 1 — caps exist for a reason.

## Example: 14-minute Week 1 session for Sofia Reyes (LatAm fintech niche)

```bash
python3 niche_search.py sofia --term "cross-border payments Latin America" --max-videos 5 --max-likes 1
python3 browse_hashtag.py sofia --term "digital nomad latam" --minutes 4 --max-likes 2
python3 deep_dive_creator.py sofia --max-videos 4 --follow
python3 browse_hashtag.py sofia --term "usd to cop" --minutes 3 --max-likes 1
python3 scroll_fyp.py sofia --minutes 2 --max-likes 1
```

Expected niche ratio: ~86% (12 min niche / 14 min total).
Expected engagement: 4–5 likes, 1 follow, 1 search. Under all Week 1 caps.
