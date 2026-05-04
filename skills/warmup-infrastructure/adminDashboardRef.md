# Admin Dashboard Reference — Warmup Health (Next.js + Vercel)

## What it shows

Per-account health cards answering "is this account properly warm?":
- Status badge: Healthy / Needs attention / Inactive
- 7-day activity grid (colored by session quality)
- Niche % bar vs target (week 1: ≥85%, week 2+: ≥50%)
- Avg videos/session
- Expandable detail: session history table + daily breakdown

## Source

The dashboard lives in `flooently-admin/` inside the Flooently repo. To set it up for a new repo:

### Step 1 — Copy the Next.js app

Copy the entire `flooently-admin/` directory from the Flooently repo into your new repo. It's a standalone Next.js app with no dependencies on the parent repo.

### Step 2 — Configure your accounts

Edit `src/app/api/warmup/route.ts`. Find `ACCOUNT_CONFIGS` at the top and replace with your accounts:

```typescript
const ACCOUNT_CONFIGS = [
  { slug: "tiktok,your_account_1", label: "Label 1", color: "#7C71D9" },
  { slug: "tiktok,your_account_2", label: "Label 2", color: "#4CAF50" },
  // add more as needed
];
```

- `slug` must match the `account_slug` values your warmup script logs to Supabase
- `label` is the short human name shown on the card (language, niche, etc.)
- `color` is the accent color for that account's card

### Step 3 — Deploy to Vercel

```bash
cd your-admin-dir
npm install
vercel link --scope your-vercel-team --project your-project-name
vercel env add SUPABASE_URL production
vercel env add SUPABASE_SERVICE_ROLE_KEY production
printf "your-password" | vercel env add ADMIN_PASSWORD production
vercel deploy --prod
```

### Step 4 — Add custom domain

```bash
vercel domains add admin.yourdomain.com
```

Then add an A record in your DNS: `admin → 76.76.21.21`

### Step 5 — Disable Vercel SSO protection (for preview URLs)

By default Vercel team projects require Vercel login on `.vercel.app` URLs. To use Basic Auth instead:

```bash
# Get your token
TOKEN=$(python3 -c "import json; d=json.load(open('$HOME/Library/Application Support/com.vercel.cli/auth.json')); print(d['token'])")

# Get your project ID from .vercel/project.json
PROJECT_ID=$(python3 -c "import json; print(json.load(open('.vercel/project.json'))['projectId'])")
TEAM_ID=$(python3 -c "import json; print(json.load(open('.vercel/project.json'))['orgId'])")

curl -s -X PATCH "https://api.vercel.com/v9/projects/${PROJECT_ID}?teamId=${TEAM_ID}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"ssoProtection": null}'
```

## Auth

The dashboard uses HTTP Basic Auth (middleware.ts). Username: anything. Password: whatever you set as `ADMIN_PASSWORD`.

The service role key is **never exposed to the browser** — all Supabase fetches happen server-side in the Route Handler (`/api/warmup`).

## Health thresholds (hardcoded in route.ts)

```typescript
const nicheTarget = warmupDay !== null && warmupDay <= 7 ? 85 : 50;
```

- Days 1-7: ≥85% niche content → healthy
- Day 8+: ≥50% niche content → healthy
- No activity for 3+ days → inactive
- Active but below niche target or sparse activity → warning

Adjust these thresholds directly in `route.ts` if your warmup protocol differs.

## Local dev

```bash
cd your-admin-dir
cp .env.example .env.local
# fill in SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
npm run dev -- --port 3003
# open http://localhost:3003
```

No ADMIN_PASSWORD needed locally (middleware passes through when env var is unset).
