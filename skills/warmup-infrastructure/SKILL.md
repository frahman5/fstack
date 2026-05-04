---
name: warmup-infrastructure
description: End-to-end setup guide for the TikTok account warmup monitoring stack — Supabase action logging, remote Claude cron job, Telegram/Slack alerting, and a Next.js admin health dashboard. Load this skill when setting up this infrastructure in a new repo.
license: MIT
metadata:
  author: frahman5
  version: '1.0.0'
---

# Warmup Infrastructure Skill

Sets up the full monitoring and observability stack for TikTok account warmup systems. This skill is repo-agnostic — run it in any repo that operates TikTok warmup accounts to get the full stack stood up.

## What this covers

| Component | Reference |
|-----------|-----------|
| Supabase schema + Python logger | [supabaseRef.md](supabaseRef.md) |
| Remote cron job (Claude agent on Hetzner) | [cronRef.md](cronRef.md) |
| Telegram escalations + progress updates | [telegramRef.md](telegramRef.md) |
| Slack notifications | [slackRef.md](slackRef.md) |
| Next.js admin health dashboard (Vercel) | [adminDashboardRef.md](adminDashboardRef.md) |

## Setup order

Run these in order when bootstrapping a new instance:

1. **Supabase** — create the `warmup_actions` table, get service role key → `supabaseRef.md`
2. **Telegram** — create/reuse bot, get chat ID → `telegramRef.md`
3. **Slack** — create incoming webhook for the target workspace → `slackRef.md`
4. **Cron job** — configure and start the remote Claude agent → `cronRef.md`
5. **Admin dashboard** — deploy the Next.js app to Vercel → `adminDashboardRef.md`
