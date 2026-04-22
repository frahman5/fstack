# Computer-Use Execution Reference

How to operate a single TikTok warmup session via computer-use. Used by the executor and for manual runs.

**Always read `runtimeLearnings.md` before executing any session** — it contains lessons from previous runs that make execution more reliable.

> **Fallback:** If `request_access` fails for any reason, do NOT mark the session failed immediately.
> Instead, switch to the Peekaboo CLI fallback — see `peekabooRef.md` for the full command mapping
> and session execution flow. Peekaboo has its own macOS permissions context and is independent of
> Claude Code's computer-use system.

---

## Prerequisites
- Multilogin desktop app is installed and running on this Mac
- The target profile already exists in Multilogin (mobile cloud phone OR browser profile)
- TikTok is already installed on the cloud phone (mobile only)

> **Browser vs Mobile:** See the **Browser-Based Warmup** section at the bottom of this file.
> Browser profiles avoid cloud phone fingerprint/sensor detection issues that cause rapid bans.
> Use browser profiles for new accounts (weeks 1–2). Mobile profiles are reserved for accounts
> that have passed the initial warmup phase or where browser TikTok is insufficient.

---

## Multilogin Warmup Schedule (REQUIRED — follow this, not the old mood system for new accounts)

Based on Multilogin's official guide. Do NOT rush past these weekly limits — TikTok flags spikes.

| Week | Session length | Videos watched | Likes/session | Follows/session | Comments |
|------|---------------|----------------|---------------|-----------------|----------|
| 1 (days 1–7) | 15–20 min | 30–50 | **5–8 max** | **2–3 max** | **None** |
| 2 (days 8–14) | 20–30 min | 30–50 | 10–15 | 5–8 | 2–3 thoughtful |
| 3–4 (days 15–28) | 30–45 min | 50+ | 15–20 | 8–12 | 5–8 quality |
| Week 5+ | Full engagement | — | — | — | — |

**Before first content post**, account must have accumulated: 100+ videos watched, 50+ likes, 20+ follows, 10+ comments, consistent daily login history.

**Ban-triggering patterns to avoid at all costs:**
- Liking 50 videos in 5 minutes
- Following 100 accounts on day 1
- Searching / commenting in Week 1
- Mechanical timing (actions at perfectly regular intervals)
- Posting before week 3

---

## Step 1: Launch the Cloud Phone

1. **Request computer-use access** for both:
   - `Multilogin X App` — the main app where you select and start profiles
   - `phone_launcher_darwin_arm64` — the cloud phone window (bundle ID: `com.wails.mlxdsk`). This is a **separate process** and MUST be in your allowlist or it will be invisible in screenshots.
2. Open the Multilogin desktop app (if not already open)
3. Make sure you're on the **Mobile** tab (not Browser)
4. Find the target profile by name
5. Select the profile's **checkbox** (left side of the row), then press **Cmd+Enter** to start it
6. **Handle the "Install apps from the phone" modal:** If visible:
   - Click **"Never show this again"** checkbox at bottom-left
   - Click **"Understood"** to dismiss
   - If the dialog keeps reappearing, close Multilogin entirely and reopen it — this resets the dialog state
7. **Handle the survey popup:** "How easy was it to get started?" — click **X** to dismiss
8. **Verify the profile is running:** The play button (▶) should change to a red stop button (■). The Minutes counter should start decreasing.
9. **Bring the phone window to front:** Use `open_application` with `phone_launcher_darwin_arm64`, or click on it
10. Wait for the Android home screen to fully load (up to 45 seconds from step 5)
11. If the phone window does not appear after 45 seconds → mark session failed, error = "Cloud phone failed to load after 45s"

**Key technical details:**
- Cloud phone window process: `phone_launcher_darwin_arm64` (bundle ID: `com.wails.mlxdsk`)
- Phone screen area: x 540–800, y 130–640
- The phone window title bar shows "MULTILOGIN" + the profile ID
- Right sidebar tools: Folder, Timer, Rotate, Screenshot, Upload, Export, Camera, More, Apps

---

## Step 2: Open TikTok

1. Swipe up from bottom of phone screen to open app drawer (`left_click_drag` y:580→y:300, x≈660)
2. Tap the TikTok icon (single quick tap — never long-press)
3. Wait up to 20s for TikTok to load
4. If TikTok shows a login screen → mark failed, error = "TikTok logged out — [Account Name] needs manual re-login"

---

## TikTok OTP Handling

If TikTok requests a verification code:
```bash
source /Users/faiyamrahman/Development/TranslationKeyboard/.env.cli

# Poll for the OTP email — retry every 10s, up to 60s total
agentmail inboxes:messages list --inbox-id tiktok@agentmail.to
```
Find the most recent TikTok message, retrieve it, extract the 6-digit code, and type it into the phone. If no email arrives within 60s → mark failed, error = "TikTok OTP email did not arrive within 60s".

---

## Session Moods

Each session has a mood that determines browsing behavior. The executor picks the mood — execution details for each:

**passive** — FYP only, slow casual scroll
- FYP only. 6-10 videos, 8-60s each. Like 1-4. No follows, no comment. Duration: 7-12 min.

**explorer** — Discover + FYP
- Discover tab → 2-3 search terms from account's Search Terms field. Watch 4-6 videos per search. Back to FYP for remaining time. Like ~1 in 4. Maybe 1 follow. Maybe 1 comment in Spanish. Duration: 12-18 min.

**fyp** — FYP with active engagement
- FYP. Like ~1 in 3-4 videos. Follow 1-2 creators. Leave 1 comment in Spanish. Tap a creator profile to browse 10-15s. Duration: 15-22 min.

**rabbit-hole** — Deep dive on one creator
- Discover → 1 search → find a creator → watch 4-6 of their videos → follow them → back to FYP for 5-8 min. 1 comment. Duration: 15-25 min.

**doomscroll** — Long deep session
- Phase 1 (~15 min): Deep FYP — some videos 60-90s, some skipped at 5s. Replay 2-3 videos.
- Phase 2 (~10 min): 2-3 searches from Search Terms pool, 5-7 videos per search.
- Like ~1 in 3. Follow 3-5 creators. 1-2 comments in Spanish. Duration: 25-35 min total.

**burst** — Fast check-in
- FYP only. 4-7 videos, 10-30s each. 0-1 likes. No searches, no comment. Duration: under 8 min.

---

## Searching for Niche Content (explorer / rabbit-hole / doomscroll)

1. Tap the **Discover** icon (compass, 2nd from left in bottom nav)
2. Pull 2-3 search terms from the account's **Search Terms** field in Airtable — pick randomly, never the same ones two sessions in a row
   - Fallback if field is empty: "aprender idiomas", "tips para estudiar", or account's country + "cultura"
3. Tap the search bar, type the term, tap Search or a suggestion
4. Tap the **Videos** tab in results
5. Watch 4-6 videos:
   - Random duration 6-25s each (vary — some short, some nearly full)
   - Like 2-3 of them
   - On 1-2 videos, swipe away after only 2-4s (real users do this)
6. Go back to search → repeat with a different term
7. Do 2-3 different searches total

---

## Swipe Physics Rules (CRITICAL — apply every session)

TikTok's fraud detection tracks swipe velocity, acceleration, and uniformity. A bot that swipes the same way every time gets flagged.

**Speed — vary constantly:**
- ~40% fast flick (impatient) — quick upward swipe covering most of the screen
- ~35% medium — normal casual scroll
- ~25% slow drag — hesitating, not sure if you want to leave

**Start position — never the same twice:**
- Sometimes start from bottom third of screen
- Sometimes start from middle of screen

**Length — vary it:**
- Some swipes: 80% of screen height
- Some swipes: 50-60% (short swipe feels more natural)
- Occasionally: very short swipe that barely moves, then complete it — like a fumbled gesture

**Go back sometimes:**
- Every 8-12 videos: swipe DOWN to go back and rewatch 3-8 seconds before swiping up again. Real users do this constantly. One of the strongest human signals.

**Pauses — mandatory:**
- After every 3-6 videos: stop scrolling for 10-30s (vary each time). Simulate looking away.
- Occasionally pause mid-video as if something caught your attention
- Once per session: pause 45-90s (simulate getting a notification or putting the phone down)

**Never:**
- Swipe at perfectly regular intervals (e.g. exactly every 15s)
- Always start swipes from the same screen position
- Always use the same swipe speed
- Like every nth video mechanically

---

## Behavioral Rules

- **Never like more than 25 videos in a single session**
- **Never follow more than 4 accounts in a single session**
- **Never leave identical comments across accounts or sessions**
- **Vary session length** — some sessions 14 min, some 23 min, never exactly the same
- **Don't rush** — watch videos for meaningful durations, not just the minimum
- **Tap a creator profile** once or twice per session even if you don't follow them — browse 10-15s then go back
- **Let a video play almost completely** (>80% watched) at least 2-3 times per session — very strong engagement signal

---

## Step 5: Wrap Up

1. Press the Android home button to exit TikTok (don't force-close it)
2. Wait 5-10 seconds on the home screen
3. Take a final screenshot

**Stop the cloud phone:**
Click the red stop button (■) on this account's profile row in Multilogin.

---

## Session Report

After the session, record:
1. Which searches were done and in what order
2. Total videos watched
3. Videos liked
4. Accounts followed
5. Comment left (yes/no + text)
6. Times swiped back to rewatch
7. Long pauses taken (>20s)
8. Estimated % of FYP that was Spanish learning content
9. Total session length

---

## Browser-Based Warmup (tiktok.com via Multilogin Browser Profile)

Use this for accounts in **weeks 1–2** of warmup, and any time mobile cloud phone profiles are getting flagged. Browser profiles sidestep cloud phone sensor-fingerprint detection (missing accelerometer/gyroscope noise) — the main cause of rapid mobile bans.

### Step 1: Launch the browser profile

1. Request computer-use access for `Multilogin X App`
2. In Multilogin, click the **Browser** tab (top-left)
3. Find the target account's browser profile by name
4. Click the **▶ play button** on the profile row (or select checkbox + Cmd+Enter)
5. A Chromium browser window will open — bring it to front with `open_application("Mimic")` or by clicking it
6. Wait for the browser to load (~5–10 seconds)

> Note: The Multilogin browser process name may be `Mimic` or similar. Take a screenshot after launch to confirm it opened and note the window title.

### Step 2: Navigate to TikTok

1. Click the address bar in the browser
2. Type `https://www.tiktok.com` and press Return
3. Wait for TikTok to load (~5–10 seconds)
4. **Check login state**: Look for the account avatar/username in the top-right. If not logged in → log in with the account credentials (or mark session as needs-retry if credentials aren't available).

### Step 3: Verify login

After TikTok loads:
- Logged in: avatar/profile icon visible top-right with account name
- Logged out: "Log in" button visible top-right

If logged out → mark session needs-retry, write Agent Messages, send Telegram.

### Step 4: Browse the For You Page (Week 1 behavior)

TikTok web FYP shows a vertical feed of videos. Interact like a human:

**Watching videos:**
- Let each video auto-play — don't immediately scroll away
- Watch for 8–30 seconds (vary), then scroll down to next
- Occasionally let a video play nearly fully (strong engagement signal)
- Scroll down using mouse wheel or Page Down key
- Every 5–8 videos: pause 10–25 seconds (simulate looking away from screen)
- Once per session: pause 45–90 seconds

**Scrolling:**
- Use mouse wheel to scroll — vary scroll speed and distance
- Sometimes scroll quickly (impatient skip), sometimes slowly (absorbed in video)
- Occasionally scroll back up slightly to rewatch 3–8 seconds, then scroll down again

**Liking (Week 1: 5–8 max per session):**
- Click the heart icon on the right sidebar of the video
- Only like videos that are genuinely relevant to the account's niche
- Space likes out — don't like 3 in a row

**Following (Week 1: 2–3 max per session):**
- Click the creator's avatar → opens their profile page
- Browse 10–15 seconds on their profile
- Click Follow
- Go back to FYP

**No searching, no commenting in Week 1.**

### Step 5: Wrap up

1. Let the last video play for a few more seconds, then stop scrolling
2. Close the TikTok tab (don't force-quit the browser)
3. Close/quit the Multilogin browser profile via Multilogin's stop button or close the window

### Browser-specific notes

- The browser window may show as "Mimic" in the application switcher — request access to it after it opens
- Mouse scroll events on tiktok.com are natural (no touch-event translation issues like mobile)
- The comment box on web appears below the video, accessible by scrolling right sidebar
- Web TikTok may prompt "Open in app" banners — dismiss these by clicking X
- If TikTok shows a CAPTCHA or verification → mark session needs-retry, write Agent Messages
