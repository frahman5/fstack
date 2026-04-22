---
name: tiktok-warmup
description: Warms up TikTok accounts for Flooently + Blaze using Multilogin browser profiles. Use when running warmup sessions, creating new TikTok accounts, managing credentials, or reviewing session design. Triggers on /execute-warmups and any TikTok account management tasks.
license: MIT
metadata:
  author: frahman5
  version: '1.0.0'
---

# TikTok Warmup Skill

Warms up TikTok accounts for Flooently + Blaze using Multilogin browser profiles. Targets Spanish learners across Latin America.

**This is now a semi-manual system.** Faiyam runs `/execute-warmups` (see `prompts/execute-warmups.md`) when ready to warm up. The agent plans today's sessions, runs them in parallel across accounts, and relies on Faiyam for manual debugging (CAPTCHAs, re-logins, weird modals). No background scheduler, no cron — just a slash command.

## Reference Files

| File | Purpose |
|------|---------|
| [multiloginRef.md](multiloginRef.md) | **Multilogin X API reference** — auth, workspace IDs, profile IDs, how to start/stop profiles, Playwright connection. |
| [browserWarmupRef.md](browserWarmupRef.md) | **Browser warmup protocol** — humanized Playwright sessions on tiktok.com via Multilogin browser profiles. Preferred approach. |
| [loginRef.md](loginRef.md) | **TikTok login procedure** — do this yourself agentically, never delegate to ensure_login.py. Covers where creds live (1Password Claude-Accessible vault), OTP retrieval (AgentMail), captcha handling, and the visual login-verification checklist. |
| [sessionDesignRef.md](sessionDesignRef.md) | **How to compose the per-account task queue.** Target 50%+ niche-explicit time in early weeks. Recommended task mixes by week, anti-patterns, working example for Sofia. Read this when building a queue for any /execute-warmups run. |
| [accountsRef.md](accountsRef.md) | **Account registry auto-refresh protocol.** Accounts live in Airtable; scripts read from scripts/warmup/accounts.json. The agent refreshes the cache at step 2 of every /execute-warmups run so new/removed accounts propagate automatically with no code edits. |
| [airtableRef.md](airtableRef.md) | Airtable base/table/field IDs - Accounts + Session Log are the two tables we use. |
| [computerUseRef.md](computerUseRef.md) | Mobile cloud phone warmup - computer-use based. Used only for late-stage weeks or special cases. |
| [peekabooRef.md](peekabooRef.md) | Peekaboo CLI fallback - used when request_access fails for cloud phone sessions. |
| [runtimeLearnings.md](runtimeLearnings.md) | Operational learnings from live sessions - **read before every execution**. |
| [accountCreationRef.md](accountCreationRef.md) | How to create TikTok accounts and store credentials in 1Password. |

## Protocols

- **Run today's warmups (the main thing)**: trigger /execute-warmups (see prompts/execute-warmups.md). Reads runtimeLearnings.md + browserWarmupRef.md + multiloginRef.md + airtableRef.md.
- **Run a one-off browser warmup session**: read multiloginRef.md + browserWarmupRef.md + runtimeLearnings.md, then invoke scripts/tiktok-warmup-poc.py.
- **Run a mobile warmup session** (rare): read multiloginRef.md + computerUseRef.md + runtimeLearnings.md.
- **Create a new TikTok account**: trigger `/create-tiktok` (see `prompts/create-tiktok.md` in the consuming repo). Reads `accountCreationRef.md`.
- **Multilogin API operations**: read multiloginRef.md.

## Design philosophy

Target 30-90 min of warmup per account per day, split into 2-4 sessions of 15-30 min each. Rest days in weeks 1-2 are natural (deterministic per account). The Scheduled Sessions Airtable table is deprecated - we log results directly to Session Log.
