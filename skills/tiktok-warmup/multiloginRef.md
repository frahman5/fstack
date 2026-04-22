# Multilogin X API Reference

Reference file for all Multilogin X API interactions within the TikTok warmup skill.

## Official Documentation

**Help center (full API docs hub):** https://multilogin.com/help/en_US/api
**Postman collection:** https://documenter.getpostman.com/view/28533318/2s946h9Cv9

When you need endpoint details not covered here, fetch from the help center sub-pages:
- Token generation: `/help/en_US/postman/automation-token`
- Team member auth: `/help/en_US/postman/how-to-use-api-as-a-team-member-with-postman`
- Playwright example: `/help/en_US/puppeteer-selenium-and-playwright/playwright-automation-example`
- Getting IDs: `/help/en_US/postman/get-profile-folder-workspace-ids-postman`
- DevTools token: `/help/en_US/quick-solutions-with-developer-tools/retrieving-the-token`
- DevTools IDs: `/help/en_US/quick-solutions-with-developer-tools/retrieving-folder-workspace-ids`

---

## Base URLs

```
MLX_BASE        = "https://api.multilogin.com"
MLX_LAUNCHER    = "https://launcher.mlx.yt:45001/api/v1"
MLX_LAUNCHER_V2 = "https://launcher.mlx.yt:45001/api/v2"
```

The launcher resolves to `127.0.0.1:45001` — it's a local agent that must be running (Multilogin desktop app must be open).

---

## Authentication

### Credentials

Stored in `.env.cli`:
- `MULTILOGIN_API_KEY` — the no-expiry automation token for the Flooently workspace. The warmup script (`tiktok-warmup-poc.py`) reads this. (Historical alias: `MLX_AUTOMATION_TOKEN` — the script falls back to this for older envs.)
- `MLX_WORKSPACE_ID` — `76207486-0efb-4220-ad4f-c877333b1859`

Multilogin account credentials (email + password) live in **1Password → Claude-Accessible vault → "Multilogin" item**. Both `username` (the sign-in email) and `password` fields are stored there. As of 2026-04-17 the sign-in email is `faiyam@flooently.com` (the Flooently workspace owner), but do NOT hardcode — always pull from 1Password so it stays in sync with ownership changes.

### Using the automation token

```bash
source .env.cli
curl -H "Authorization: Bearer $MULTILOGIN_API_KEY" ...
```

The automation token has `isAutomation: true`, no expiry (when generated via `expiration_period=no_exp`), and higher rate limits. Use it for all API calls.

### Auto-regenerate the token (preferred)

When the token gets invalidated (master password change, revocation, etc.), **run the helper script — it handles the full 3-step OAuth dance, writes the fresh no-expiry token back to `.env.cli`, and takes ~5 seconds**:

```bash
python3 scripts/regenerate-mlx-token.py
```

The script:
1. Fetches the Multilogin email + password from 1Password (`op item get Multilogin --vault Claude-Accessible`)
2. MD5-hashes the password (Multilogin's signin API requirement)
3. Signs in → refreshes into the Flooently workspace → generates a new `expiration_period=no_exp` automation token
4. Writes `MULTILOGIN_API_KEY=<token>` back to `.env.cli` in-place

No manual UI steps, no hardcoded credentials in the script, no token expiry blocker.

### Manual regeneration (fallback if the script breaks)

Same 3 steps as the script, reference only:

```bash
# Step 1: Sign in
SIGNIN=$(curl -s -X POST "https://api.multilogin.com/user/signin" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -d '{"email":"<email>","password":"<md5_hash>"}')
REFRESH_TOKEN=$(echo $SIGNIN | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['refresh_token'])")
INITIAL_TOKEN=$(echo $SIGNIN | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")

# Step 2: Switch to Flooently workspace via refresh token
WORKSPACE_TOKEN=$(curl -s -X POST "https://api.multilogin.com/user/refresh_token" \
  -H "Authorization: Bearer $INITIAL_TOKEN" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -d '{"email":"<email>","refresh_token":"'$REFRESH_TOKEN'","workspace_id":"76207486-0efb-4220-ad4f-c877333b1859"}')

# Step 3: Generate automation token (no expiry)
curl -s "https://api.multilogin.com/workspace/automation_token?expiration_period=no_exp" \
  -H "Authorization: Bearer $(echo $WORKSPACE_TOKEN | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['token'])")" \
  -H "Accept: application/json"
```

### Workspace context (background)

Ownership of the Flooently workspace has moved to `faiyam@flooently.com` (Business 300 plan). Sign-in uses that email. The legacy `faiyam@blaze.money` account may still exist as a manager but is not the current automation login.

---

## Workspace & Folder IDs

| Entity | ID |
|--------|---|
| Flooently workspace | `76207486-0efb-4220-ad4f-c877333b1859` |
| Flooently browser folder | `1c5615aa-fae3-4184-a2a3-37226bd48b38` |
| Blaze browser folder | `db07d2e1-4d3c-44fa-8a7f-7cc406410181` |
| Mobile default folder | `7947f94c-b9f6-499c-8bdf-e434e3654702` |

## Browser Profile IDs (Flooently folder)

Naming convention: `platform,handle` — matches Airtable account names and accounts.json.

| Account | Profile ID | Country/Proxy | 1Password Item |
|---------|-----------|---------------|----------------|
| `tiktok,flooently_spanish` | `5c69580d-d860-43cc-bb46-7fa96a3ffa50` | Costa Rica | TikTok - Sebastian Vargas |
| `tiktok,flooently_italian` | `aed6f242-f7e1-46f2-9a97-7ac1e578fe3e` | Italy | TikTok - Giulia Romano |
| `tiktok,flooently_portuguese1` | `0163b253-bbce-416c-83e5-e9f29f569dfe` | Brazil | TikTok - Flooently Portuguese |
| `tiktok,flooently_french` | `24a5332c-dc93-4bb8-bec8-6d48afc2362e` | France | TikTok - Flooently French |
| `tiktok,lucia_gonzalez` *(legacy)* | `827e8057-d3be-47b9-831a-5be49a86ef12` | Uruguay | TikTok - Lucia Gonzalez |
| `tiktok,andres_morales` *(legacy)* | `6ffeda6b-b371-446c-93cc-7d915882e19e` | Ecuador | TikTok - Andres Morales |
| `tiktok,isabella_restrepo` *(legacy)* | `5aef5a09-dde8-496a-9b78-5bc51d58aea5` | Colombia | TikTok - Isabella Restrepo |
| `tiktok,diego_herrera` *(legacy)* | `9516da5c-701c-4a8d-9d21-6bb2d0b923dd` | Mexico | TikTok - Diego Herrera |

Note: All Flooently profiles (including Giulia Romano) live in the Flooently folder `1c5615aa-fae3-4184-a2a3-37226bd48b38`. Earlier docs incorrectly listed Giulia at workspace root — confirmed in Multilogin API as of 2026-04-18.

## Browser Profile IDs (Blaze folder)

| Account | Profile ID | Country/Proxy | 1Password Item |
|---------|-----------|---------------|----------------|
| `tiktok,blazemoney_agents` | `91eea3ec-40bd-4022-b5ee-a7b46fd0fb8c` | US (New York) | TikTok - Diego Salazar |
| `tiktok,blazemoney_latam` | `c94312b1-afd4-42fa-9041-15e547fda62a` | Mexico | TikTok - Sofia Reyes |
| `tiktok,blaze__money` | `6d55410a-de14-4933-87e1-aca1e7b674ae` | Any | TikTok - Blaze Money |
| `tiktok,blazemoney_stables` | `e06de76a-2025-47db-a458-687bdcf6e35c` | Any | TikTok - Blaze Money Stables |

---

## Starting a Browser Profile with Playwright

```
GET https://launcher.mlx.yt:45001/api/v2/profile/f/{FOLDER_ID}/p/{PROFILE_ID}/start?automation_type=playwright&headless_mode=false
```

**Response:** `{ "data": { "port": 12345 } }`

**Connect Playwright (Python):**
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.connect_over_cdp(endpoint_url=f"http://127.0.0.1:{port}")
    context = browser.contexts[0]
    page = context.new_page()
    page.goto("https://www.tiktok.com")
```

**Connect Playwright (Node.js):**
```javascript
const { chromium } = require('playwright');
const browser = await chromium.connectOverCDP(`http://127.0.0.1:${port}`);
const context = browser.contexts()[0];
const page = await context.newPage();
```

> **Note:** Playwright for Stealthfox (Firefox) is NOT available. Only Mimic (Chromium) profiles support Playwright.

## Stopping a Profile

```
GET https://launcher.mlx.yt:45001/api/v1/profile/stop/p/{PROFILE_ID}
```

---

## Rate Limits

| Plan | RPM |
|------|-----|
| Business 300 (current) | 100 |

Shared across all team members in the workspace.

---

## Profile Management (less common operations)

### List profiles
```
POST https://api.multilogin.com/profile/search
Body: {"is_removed": false, "limit": 50, "offset": 0, "search_text": ""}
```

### List folders
```
GET https://api.multilogin.com/workspace/folders?folder_type=all
```

### Create a profile
```
POST https://api.multilogin.com/profile/create
```
Key fields: `name`, `folder_id`, `browser_type` (mimic/stealthfox), `os_type`, `core_version`, `parameters.proxy`, `parameters.flags`. Add `"times": N` for bulk creation (max 10).

### Other operations
See Postman collection for: profile update, clone, move, remove/restore, cookie import/export, folder CRUD, extension management, bookmark management, 2FA management.

---

## Cloud Phone Management

Cloud phones are created via the Multilogin dashboard UI only (no public API endpoint). Key details:
- Residential proxy required (no localhost)
- Android 12-15, device brands: Samsung/Google/Oppo/Redmi/OnePlus/vivo
- Cannot send/receive SMS
- Session data persists between uses
- Minutes: EUR 0.0065-0.0075/min depending on pack size

---

## Masking Flags

All profiles use these fingerprint masking settings:

| Flag | Value |
|------|-------|
| `navigator_masking` | `mask` |
| `audio_masking` | `mask` |
| `fonts_masking` | `mask` |
| `geolocation_masking` | `mask` |
| `geolocation_popup` | `prompt` |
| `graphics_masking` | `mask` |
| `graphics_noise` | `natural` |
| `canvas_noise` | `natural` |
| `localization_masking` | `mask` |
| `media_devices_masking` | `mask` |
| `ports_masking` | `mask` |
| `screen_masking` | `mask` |
| `timezone_masking` | `mask` |
| `webrtc_masking` | `natural` |
