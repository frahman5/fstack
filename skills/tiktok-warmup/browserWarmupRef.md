# Browser Warmup Protocol

Humanized TikTok warmup sessions via Multilogin browser profiles + Playwright.
Preferred over mobile cloud phones for Weeks 1-2 (avoids sensor fingerprint detection).

## Why This Approach Avoids Bot Detection

Multilogin browser profiles are purpose-built **antidetect browsers**, not regular Chrome with spoofed headers. Understanding this is critical — our Playwright automation rides on top of a browser that is already solving the hardware/fingerprint detection problem at every layer:

**What Multilogin handles for us (we don't need to worry about these):**

- **Canvas fingerprinting**: Each profile adds "random but consistent noise" to canvas rendering, making the fingerprint statistically unique but stable across sessions. Not disabled — that's a red flag — but subtly altered.
- **WebGL/WebGPU fingerprinting**: Masks the GPU vendor and renderer strings. Reports plausible hardware (e.g., "Apple M2 Max") that matches the profile's declared OS.
- **AudioContext fingerprinting**: Tweaks the audio processing stack at the browser level with persistent noise, so each profile produces a unique but consistent audio fingerprint.
- **Navigator/User-Agent**: Sets a coherent set of navigator properties (user-agent, platform, hardwareConcurrency, oscpu) that are internally consistent. Mismatches between these values are a major detection signal — Multilogin ensures they all agree.
- **Font fingerprinting**: Provides an OS-appropriate font list (not your real installed fonts) and consistent font metrics.
- **WebRTC IP masking**: Detects the profile's proxy IP and feeds it back as the WebRTC IP, preventing the real IP from leaking through WebRTC.
- **Timezone/geolocation**: Auto-aligns timezone and geolocation coordinates with the proxy's geographic location, with random offset for natural variation.
- **Screen resolution**: Sets a plausible random resolution from the fingerprint builder.
- **Media devices**: Controls the reported number of cameras/microphones/speakers.
- **Port scan protection**: Hides actually open ports from websites.
- **TCP/IP passive fingerprinting**: Masks OS-level TCP/IP stack characteristics.
- **Session isolation**: Each profile has its own cookies, localStorage, history, and fingerprint — completely isolated from other profiles.
- **Persistent identity**: All fingerprint noise is deterministic per profile — the same canvas noise, audio noise, and WebGL output every session. This means TikTok sees a "returning user with the same device" each time, not a new random fingerprint.

**What WE are responsible for (behavioral detection):**

Multilogin solves the *device identity* problem. Our Playwright script must solve the *behavioral* problem — making the browsing pattern look human:
- Natural timing and randomness in all actions
- Keyboard navigation (ArrowDown/Up) instead of synthetic scroll events
- Human-like typing with variable speed and typos
- Varied session activities (not just one repetitive action)
- Realistic engagement ratios (don't like 50 videos in 2 minutes)
- Random idle pauses simulating real human distraction

**Why browser profiles beat cloud phones for Weeks 1-2:**
Cloud phones run real Android but TikTok's mobile app checks accelerometer/gyroscope sensor data in real-time. Cloud phones produce flat/synthetic sensor streams that are statistically distinguishable from real devices. The web browser doesn't expose sensor APIs at all, eliminating this entire detection vector.

## POC Script

The working POC lives at `scripts/tiktok-warmup-poc.py`. Run with:

```bash
python3 -u scripts/tiktok-warmup-poc.py
```

The script self-loads `.env.cli` — **never prepend `source .env.cli &&`**.

## Login Check (runs automatically before every session)

`ensure_login(page, profile_name)` is called right after Playwright connects. It:
1. Navigates to `tiktok.com` and checks for logged-in indicators (`[data-e2e="nav-profile"]`, upload icon)
2. If not logged in: fetches email + password from 1Password via `op item get "TikTok - <name>"` CLI
   - Flooently personas → **Personal** vault; Blaze personas → **Marketing** vault
3. Fills the email login form at `/login/phone-or-email/email`
4. If TikTok shows an OTP prompt: polls `tiktok@agentmail.to` via AgentMail CLI (60s timeout)
5. Verifies login succeeded — raises `Exception` on failure so the executor marks the session failed

Screenshots are saved to `/tmp/tiktok_login_*.png` on any login attempt for debugging.

## How It Works

1. Start a Multilogin browser profile via the launcher API (`automation_type=playwright`)
2. Connect Playwright to the running Mimic browser via CDP (`chromium.connect_over_cdp`)
3. Navigate to `https://www.tiktok.com/foryou`
4. Run a randomized session of weighted activities (Markov chain)
5. Stop the profile when done

## TikTok Web Interface (as of April 2026)

**Left sidebar navigation:**
- For You (FYP) — main video feed
- Explore — trending content, categories
- Following — content from followed accounts
- Friends — friend activity
- LIVE — live streams
- Messages — DMs
- Activity — notifications
- Upload — create content
- Profile — own profile page
- More — settings, etc.

**Video page elements:**
- Creator username + avatar (clickable to visit profile)
- Like button (heart) — also keyboard shortcut `L`
- Comment button — opens comment panel
- Bookmark button — save for later
- Share button — opens share dialog
- Music/sound name (clickable to see other videos with same sound)
- Hashtags (clickable to explore tag)
- Follow button on creator
- Up/Down arrow buttons on right side to navigate between videos

## Navigation Rules

**ALWAYS use URL-based navigation** — TikTok's sidebar uses dynamic classes/icons that break with CSS selectors. Reliable URLs:

| Page | URL |
|------|-----|
| FYP (For You) | `https://www.tiktok.com/foryou` |
| Explore | `https://www.tiktok.com/explore` |
| Following feed | `https://www.tiktok.com/following` |
| LIVE | `https://www.tiktok.com/live` |
| Messages | `https://www.tiktok.com/messages` |
| Search results | `https://www.tiktok.com/search?q=<term>` |

For Profile: try selector `[data-e2e="nav-profile"]` or `a[href*="/@"]` first, then fallback to sidebar icons.

## Scrolling / Video Navigation Rules

**NEVER use mouse scroll/drag.** TikTok can detect synthetic scroll events.

**Use a MIX of navigation methods** — vary between and within sessions:
- `ArrowDown` / `ArrowUp` keyboard shortcuts (~75% of the time)
- On-screen arrow buttons (~25% of the time)

After navigating to a video page, **click the body/video area** to ensure keyboard focus.

## Video Micro-Interactions

While watching a video on FYP, randomly perform micro-interactions:
- **Like** (~15%) — keyboard `L` key
- **Follow** (~3%) — click Follow button
- **Comment** (~4%, respects weekly limits) — generic Spanish comments
- **Bookmark** (~5%) — click save button
- **Pause video** (~8%) — click video to pause, wait 2-12s, click to unpause
- **Scroll back up** (~10%) — rewatch previous video

## Human-Like Typing

When typing (search, comments), simulate real human behavior:
- Variable keystroke delay (40-180ms per char)
- ~8% typo rate (wrong key → pause → backspace → correct)
- Occasional mid-word thinking pauses (0.5-1.5s)
- Sometimes pick a suggested search instead of typing the full term

## Meta-Randomness (Session Personality)

**Every session generates a unique "personality"** at startup via `generate_session_personality()`. This prevents TikTok from building a behavioral signature across accounts.

### A) Random session duration
- Range: 5 to 63 minutes (beta distribution, weighted toward 10-30 min)
- Override with `--duration` CLI flag

### B) Random action subset
- 13 total activities available; core always enabled, optionals have 45-90% inclusion rate
- ~12% chance FYP scrolling excluded entirely (explore-heavy session)
- ~15% chance creator visits excluded

### C) Random probability weights
- Each activity gets a random weight within its range, normalized to sum to 1.0

### D) Random watch style
- Quick skip / partial / full / loved-it percentages randomized per session
- Duration ranges jittered too

### E) Random starting page
- 60% FYP, 30% Explore, 10% Following

## All Available Activities

| Activity | Description |
|----------|-------------|
| `scroll_fyp` | Watch 3-15 videos on FYP with varied navigation methods |
| `browse_explore` | Browse trending/explore, click into topics |
| `browse_following` | Watch content from followed accounts |
| `watch_live` | Join a live stream for 20-90s |
| `check_inbox` | Open messages, look around |
| `check_activity` | Check notifications |
| `check_my_profile` | Visit own profile |
| `visit_creator` | Deep-dive on a creator's profile (2-8 videos) |
| `do_search` | Search and browse results |
| `read_comments` | Open comment section, scroll through |
| `click_hashtag` | Click hashtag to explore related content |
| `idle_distraction` | Pause 8-50s (distracted) |
| `navigate_to_fyp` | Transition back to FYP |

## Video Watch Duration Distribution

Mimics real human attention patterns:

| Behavior | Probability | Duration |
|----------|------------|----------|
| Quick skip | 35% | 2-5s |
| Watched a bit | 30% | 5-12s |
| Watched most | 20% | 12-25s |
| Loved it / rewatch | 15% | 25-60s |

## Weekly Engagement Limits (browser profiles)

| Week | Session length | Likes/session | Follows/session | Comments | Searches |
|------|---------------|---------------|-----------------|----------|----------|
| 1 (days 1-7) | 15-20 min | 5-8 max | 2-3 max | None | None |
| 2 (days 8-14) | 20-30 min | 10-15 | 5-8 | 2-3 | 2-3 |
| 3-4 (days 15-28) | 30-45 min | 15-20 | 8-12 | 5-8 | 3-5 |
| Week 5+ | full engagement | — | — | — | — |

## Session Behavioral Rules

- **Never mechanical intervals** — every pause, watch time, and transition has random jitter
- **Scroll back up** ~10% of the time to rewatch a previous video
- **Creator rabbit holes** ~6% of the time — click into a creator's profile, watch 2-6 of their videos
- **Long pauses** every few activities — 10-45s of doing nothing (distracted)
- **Vary the session start** — don't always start with FYP. Sometimes start with Explore or Profile.
- **Max 25 likes per session** regardless of week
- **Never post content before Week 3**

## Error Recovery

On any error during an activity:
1. Log the error
2. Navigate back to FYP via URL (`page.goto("https://www.tiktok.com/foryou")`)
3. Click body to restore keyboard focus
4. Continue with the next random activity

## Stopping the Session

1. Session timer expires → print summary stats
2. Take final screenshot for debugging
3. Stop the Multilogin profile via launcher API
4. Log results to Airtable (Session Log + Scheduled Sessions)
