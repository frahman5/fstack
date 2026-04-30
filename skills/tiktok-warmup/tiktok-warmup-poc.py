"""
TikTok Browser Warmup — Humanized sessions via Multilogin X + Playwright

Each session is meta-randomized: random duration, random subset of available
actions, and random probability weights. This prevents TikTok from building
a behavioral signature across accounts.

Usage:
    python3 scripts/tiktok-warmup-poc.py                      # random Flooently profile
    python3 scripts/tiktok-warmup-poc.py --profile sebastian   # by name (partial match)
    python3 scripts/tiktok-warmup-poc.py --profile-id 5c69...  # by exact ID
    python3 scripts/tiktok-warmup-poc.py --duration 15         # override duration (minutes)
"""

import os
import sys
import json
import uuid
import random
import time
import argparse
import requests
from playwright.sync_api import sync_playwright, Page

# Local: Supabase action logger (lives next to this script in the skill dir)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from supabase_logger import SupabaseLogger
except Exception:
    SupabaseLogger = None  # logging disabled if module fails to import

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Auto-load .env.cli — walk up from script location to find it (works from any depth)
def _find_env_cli():
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        candidate = os.path.join(d, ".env.cli")
        if os.path.exists(candidate):
            return candidate
        d = os.path.dirname(d)
    return None
_env_file = _find_env_cli()
if _env_file and os.path.exists(_env_file):
    with open(_env_file) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip())

# ---------------------------------------------------------------------------
# Profile registry — all Multilogin browser profiles
# ---------------------------------------------------------------------------
FLOOENTLY_FOLDER = "1c5615aa-fae3-4184-a2a3-37226bd48b38"
BLAZE_FOLDER = "db07d2e1-4d3c-44fa-8a7f-7cc406410181"

PROFILES = {
    # Flooently folder — active
    "tiktok,flooently_spanish":     {"id": "5c69580d-d860-43cc-bb46-7fa96a3ffa50", "folder": FLOOENTLY_FOLDER, "country": "Costa Rica",   "op_item": "TikTok - Sebastian Vargas"},
    "tiktok,flooently_italian":     {"id": "aed6f242-f7e1-46f2-9a97-7ac1e578fe3e", "folder": FLOOENTLY_FOLDER, "country": "Italy",         "op_item": "TikTok - Giulia Romano"},
    "tiktok,flooently_portuguese1": {"id": "0163b253-bbce-416c-83e5-e9f29f569dfe", "folder": FLOOENTLY_FOLDER, "country": "Brazil",        "op_item": "TikTok - Flooently Portuguese"},
    "tiktok,flooently_french":      {"id": "24a5332c-dc93-4bb8-bec8-6d48afc2362e", "folder": FLOOENTLY_FOLDER, "country": "France",        "op_item": "TikTok - Flooently French"},
    # Flooently folder — legacy (no active Airtable account yet)
    "tiktok,lucia_gonzalez":        {"id": "827e8057-d3be-47b9-831a-5be49a86ef12", "folder": FLOOENTLY_FOLDER, "country": "Uruguay",       "op_item": "TikTok - Lucia Gonzalez"},
    "tiktok,andres_morales":        {"id": "6ffeda6b-b371-446c-93cc-7d915882e19e", "folder": FLOOENTLY_FOLDER, "country": "Ecuador",       "op_item": "TikTok - Andres Morales"},
    "tiktok,isabella_restrepo":     {"id": "5aef5a09-dde8-496a-9b78-5bc51d58aea5", "folder": FLOOENTLY_FOLDER, "country": "Colombia",     "op_item": "TikTok - Isabella Restrepo"},
    "tiktok,diego_herrera":         {"id": "9516da5c-701c-4a8d-9d21-6bb2d0b923dd", "folder": FLOOENTLY_FOLDER, "country": "Mexico",        "op_item": "TikTok - Diego Herrera"},
    # Blaze folder — active
    "tiktok,blazemoney_agents":     {"id": "91eea3ec-40bd-4022-b5ee-a7b46fd0fb8c", "folder": BLAZE_FOLDER,    "country": "US (New York)", "op_item": "TikTok - Diego Salazar"},
    "tiktok,blazemoney_latam":      {"id": "c94312b1-afd4-42fa-9041-15e547fda62a", "folder": BLAZE_FOLDER,    "country": "Mexico",        "op_item": "TikTok - Sofia Reyes"},
    "tiktok,blaze__money":          {"id": "6d55410a-de14-4933-87e1-aca1e7b674ae", "folder": BLAZE_FOLDER,    "country": "Any",           "op_item": "TikTok - Blaze Money"},
    "tiktok,blazemoney_stables":    {"id": "e06de76a-2025-47db-a458-687bdcf6e35c", "folder": BLAZE_FOLDER,    "country": "Any",           "op_item": "TikTok - Blaze Money Stables"},
}

MLX_TOKEN = os.environ.get("MLX_AUTOMATION_TOKEN", "") or os.environ.get("MULTILOGIN_API_KEY", "")

# ---------------------------------------------------------------------------
# Meta-randomness: generate a unique session personality
# ---------------------------------------------------------------------------

# All possible activities the system knows about
ALL_ACTIVITIES = [
    # --- TikTok activities ---
    "scroll_fyp",         # Watch videos on For You Page
    "browse_explore",     # Browse Explore/trending page
    "browse_following",   # Browse Following feed
    "watch_live",         # Watch a live stream briefly
    "check_inbox",        # Open messages
    "check_activity",     # Check notifications
    "check_my_profile",   # Visit own profile
    "visit_creator",      # Deep-dive on a creator's profile
    "do_search",          # Search for content
    "read_comments",      # Open and scroll through comments on current video
    "click_hashtag",      # Click a hashtag to explore related content
    "idle_distraction",   # Pause (distracted)
    "navigate_to_fyp",    # Transition back to FYP
    # --- Non-TikTok noise (human realism) ---
    "browse_other_site",  # Visit Reddit, Instagram, YouTube, news, etc.
    "idle_away",          # Leave browser entirely — just dead time, no mouse
    "random_mouse_noise", # Aimless mouse movements, useless clicks, tab fidgeting
    "long_abandon",       # Navigate away and completely forget about the browser for 5-10 min
]

# Activities that are always available (core navigation)
CORE_ACTIVITIES = {"scroll_fyp", "browse_explore", "idle_distraction", "navigate_to_fyp"}

# Sites a human might visit between TikTok sessions
OTHER_SITES = [
    # Social media
    {"url": "https://www.instagram.com/", "name": "Instagram", "scroll": True},
    {"url": "https://www.reddit.com/", "name": "Reddit", "scroll": True},
    {"url": "https://www.youtube.com/", "name": "YouTube", "scroll": True},
    {"url": "https://twitter.com/", "name": "X/Twitter", "scroll": True},
    # News / general
    {"url": "https://news.google.com/", "name": "Google News", "scroll": True},
    {"url": "https://www.bbc.com/mundo", "name": "BBC Mundo", "scroll": True},
    {"url": "https://www.cnn.com/", "name": "CNN", "scroll": True},
    {"url": "https://www.espn.com/", "name": "ESPN", "scroll": True},
    # Utility / random
    {"url": "https://www.google.com/", "name": "Google", "scroll": False},
    {"url": "https://www.amazon.com/", "name": "Amazon", "scroll": True},
    {"url": "https://www.weather.com/", "name": "Weather", "scroll": False},
    {"url": "https://www.wikipedia.org/", "name": "Wikipedia", "scroll": False},
    {"url": "https://mail.google.com/", "name": "Gmail", "scroll": False},
]


def generate_session_personality(warmup_week: int = 1, duration_override: float = None, niche_mode: bool = False, session_mode: str = "BALANCED"):
    """Generate a unique session configuration with meta-randomness.

    Returns a dict with:
        duration_min: how long this session will be
        available_activities: which activities are enabled
        weights: probability weights for each activity
        max_likes, max_follows, max_comments, max_searches: engagement caps
        watch_style: parameters for video watch duration distribution

    When niche_mode is True, weights are biased toward on-topic activities
    (do_search, click_hashtag, visit_creator) so at least ~50%% of session
    time is spent priming the FYP algorithm on the account's niche.

    session_mode further tunes weights based on the daily running niche %%:
        NICHE_PUSH    — daily niche <70%%; amplify niche-driving activities
        BALANCED      — daily niche 70-90%%; keep current mix
        NOISE_INJECT  — daily niche >90%%; inject randomness to avoid over-tuning
    """
    # In NOISE_INJECT we override niche_mode so the base ranges stay neutral
    effective_niche_mode = niche_mode and session_mode != "NOISE_INJECT"
    # A) Random duration: 5-63 minutes, weighted toward 10-30 min
    if duration_override:
        duration = duration_override
    else:
        # Use a beta distribution to weight toward the middle range
        # beta(2, 3) peaks around 0.4 of the range → ~28 min
        raw = random.betavariate(2, 3)
        duration = 5 + raw * 58  # 5 to 63 minutes

    # B) Random action subset — always keep core, randomly drop others
    available = set(CORE_ACTIVITIES)
    optional = [a for a in ALL_ACTIVITIES if a not in CORE_ACTIVITIES]

    # Each optional activity has a chance of being included in this session
    # On average ~60-80% of optionals are available, but it varies
    inclusion_rate = random.uniform(0.45, 0.90)
    for activity in optional:
        if random.random() < inclusion_rate:
            available.add(activity)

    # Sometimes force-exclude a major activity to create variety
    # ~20% chance we just don't do FYP at all (explore-heavy session)
    # ~15% chance we don't visit any creators
    # ~10% chance we don't check inbox/activity at all
    if random.random() < 0.12 and "scroll_fyp" in available:
        available.discard("scroll_fyp")
    if random.random() < 0.15:
        available.discard("visit_creator")
    if random.random() < 0.10:
        available.discard("check_inbox")
        available.discard("check_activity")

    # C) Random probability weights for available activities.
    # In niche mode, on-topic priming activities (do_search, click_hashtag,
    # visit_creator) get a significant boost and external-site distractions
    # get dampened — target: ≥50% of session time on-niche.
    weights = {}
    for activity in available:
        if activity == "scroll_fyp":
            weights[activity] = random.uniform(0.20, 0.55)
        elif activity == "browse_explore":
            weights[activity] = random.uniform(0.08, 0.30)
        elif activity == "browse_following":
            weights[activity] = random.uniform(0.03, 0.15)
        elif activity == "watch_live":
            weights[activity] = random.uniform(0.01, 0.06)
        elif activity == "check_inbox":
            weights[activity] = random.uniform(0.02, 0.10)
        elif activity == "check_activity":
            weights[activity] = random.uniform(0.02, 0.08)
        elif activity == "check_my_profile":
            weights[activity] = random.uniform(0.02, 0.10)
        elif activity == "visit_creator":
            weights[activity] = random.uniform(0.08, 0.22) if effective_niche_mode else random.uniform(0.02, 0.10)
        elif activity == "do_search":
            weights[activity] = random.uniform(0.18, 0.35) if effective_niche_mode else random.uniform(0.01, 0.08)
        elif activity == "read_comments":
            weights[activity] = random.uniform(0.02, 0.08)
        elif activity == "click_hashtag":
            weights[activity] = random.uniform(0.08, 0.18) if effective_niche_mode else random.uniform(0.01, 0.06)
        elif activity == "idle_distraction":
            weights[activity] = random.uniform(0.05, 0.18)
        elif activity == "navigate_to_fyp":
            weights[activity] = random.uniform(0.03, 0.12)
        # --- Non-TikTok noise (dampened in niche mode to preserve on-topic time) ---
        elif activity == "browse_other_site":
            weights[activity] = random.uniform(0.01, 0.04) if effective_niche_mode else random.uniform(0.03, 0.12)
        elif activity == "idle_away":
            weights[activity] = random.uniform(0.01, 0.04) if effective_niche_mode else random.uniform(0.02, 0.08)
        elif activity == "random_mouse_noise":
            weights[activity] = random.uniform(0.02, 0.07)
        elif activity == "long_abandon":
            weights[activity] = random.uniform(0.005, 0.015) if effective_niche_mode else random.uniform(0.01, 0.04)

    # Apply session_mode multipliers before normalizing.
    # NICHE_PUSH: amplify search/hashtag/creator, suppress noise.
    # NOISE_INJECT: amplify FYP/explore/off-platform, suppress niche-driving.
    if session_mode == "NICHE_PUSH":
        _boost = {"do_search": 1.6, "click_hashtag": 1.5, "visit_creator": 1.3}
        _cut   = {"browse_other_site": 0.35, "idle_away": 0.35, "long_abandon": 0.25, "browse_explore": 0.55}
        for _act, _m in _boost.items():
            if _act in weights: weights[_act] = min(weights[_act] * _m, 0.55)
        for _act, _m in _cut.items():
            if _act in weights: weights[_act] *= _m
    elif session_mode == "NOISE_INJECT":
        _boost = {"scroll_fyp": 1.3, "browse_explore": 1.7, "browse_other_site": 2.2,
                  "idle_away": 2.0, "long_abandon": 1.8, "idle_distraction": 1.5}
        _cut   = {"do_search": 0.15, "click_hashtag": 0.15, "visit_creator": 0.35}
        for _act, _m in _boost.items():
            if _act in weights: weights[_act] *= _m
        for _act, _m in _cut.items():
            if _act in weights: weights[_act] *= _m

    # Normalize weights to sum to 1
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}

    # Engagement limits based on warmup week.
    # Week 1 normally forbids searches (the Multilogin guide's most conservative
    # baseline), but when we're explicitly priming a niche we allow 1-2 on-topic
    # searches — the strongest FYP signal available. Still well below the
    # "active user" threshold.
    if warmup_week <= 1:
        max_likes = random.randint(3, 8)
        max_follows = random.randint(1, 3)
        max_comments = 0
        max_searches = random.randint(1, 3) if session_mode == "NICHE_PUSH" else (random.randint(1, 2) if effective_niche_mode else 0)
    elif warmup_week <= 2:
        max_likes = random.randint(8, 15)
        max_follows = random.randint(3, 8)
        max_comments = random.randint(1, 3)
        max_searches = random.randint(2, 4) if niche_mode else random.randint(1, 3)
    else:
        max_likes = random.randint(12, 22)
        max_follows = random.randint(5, 12)
        max_comments = random.randint(3, 8)
        max_searches = random.randint(3, 6) if niche_mode else random.randint(2, 5)

    # Randomize the video watch duration distribution too
    watch_style = {
        "quick_skip_pct": random.uniform(0.20, 0.50),     # 2-5s
        "partial_watch_pct": random.uniform(0.20, 0.40),   # 5-15s
        "full_watch_pct": random.uniform(0.10, 0.25),      # 15-30s
        # remainder = loved it (30-70s)
        "quick_range": (random.uniform(1.5, 3), random.uniform(4, 7)),
        "partial_range": (random.uniform(4, 7), random.uniform(10, 18)),
        "full_range": (random.uniform(12, 20), random.uniform(25, 45)),
        "loved_range": (random.uniform(25, 40), random.uniform(50, 75)),
    }

    # Random starting page — not always FYP
    start_pages = ["fyp"] * 6 + ["explore"] * 3 + ["following"] * 1
    start_page = random.choice(start_pages)
    if start_page == "following" and "browse_following" not in available:
        start_page = "fyp"

    return {
        "duration_min": round(duration, 1),
        "available_activities": sorted(available),
        "weights": weights,
        "max_likes": max_likes,
        "max_follows": max_follows,
        "max_comments": max_comments,
        "max_searches": max_searches,
        "watch_style": watch_style,
        "start_page": start_page,
        "warmup_week": warmup_week,
    }


# ---------------------------------------------------------------------------
# Humanized typing & pausing
# ---------------------------------------------------------------------------
def human_type(page: Page, selector: str, text: str):
    """Type text like a human — variable speed, occasional typos and corrections."""
    page.click(selector)
    time.sleep(random.uniform(0.3, 0.8))

    i = 0
    while i < len(text):
        char = text[i]
        if random.random() < 0.08 and char.isalpha():
            wrong = chr(ord(char) + random.choice([-1, 1]))
            page.keyboard.type(wrong, delay=random.randint(50, 120))
            time.sleep(random.uniform(0.15, 0.4))
            page.keyboard.press("Backspace")
            time.sleep(random.uniform(0.1, 0.3))
        delay = random.randint(40, 180)
        if random.random() < 0.05:
            time.sleep(random.uniform(0.5, 1.5))
        page.keyboard.type(char, delay=delay)
        i += 1
    time.sleep(random.uniform(0.3, 1.0))


def human_pause(min_s=1.0, max_s=3.0):
    time.sleep(random.uniform(min_s, max_s))


# ---------------------------------------------------------------------------
# TikTok Session — all activities
# ---------------------------------------------------------------------------

class TikTokSession:
    def __init__(self, page: Page, personality: dict, search_terms: list, profile_name: str = "", op_item: str = None, logger=None):
        self.page = page
        self.p = personality  # session personality
        self.search_terms = search_terms
        self.profile_name = profile_name  # used for re-login mid-session
        self.op_item = op_item             # 1Password item name for credential lookup
        self.logger = logger               # SupabaseLogger or None
        self.likes_given = 0
        self.follows_given = 0
        self.comments_left = 0
        self.searches_done = 0
        self.videos_watched = 0
        self.niche_videos = 0   # videos confirmed on-niche this session
        self.start_time = time.time()
        self.current_location = "unknown"
        self.ended_early = False
        self.end_reason = ""
        self.login_modals_seen = 0

    def _emit(self, action_type, **metadata):
        """Send an action to Supabase. Silently noop if logger is None."""
        if self.logger:
            try:
                self.logger.log(action_type, **metadata)
            except Exception:
                pass

    def _check_niche_video(self) -> bool:
        """Quick DOM check: does the current video have niche-relevant hashtags?"""
        if not self.search_terms:
            return False
        try:
            tags = self.page.query_selector_all('a[href*="/tag/"]')
            if not tags:
                return False
            combined = " ".join(
                ((el.inner_text() or "") + " " + (el.get_attribute("href") or "")).lower()
                for el in tags[:10]
            )
            # Any word (>2 chars) from any niche term appearing in the combined tag text/hrefs counts
            for term in self.search_terms:
                words = [w for w in term.lower().split() if len(w) > 2]
                if any(w in combined for w in words):
                    return True
            return False
        except Exception:
            return False

    def _recheck_login_after_nav(self):
        """Called after returning to TikTok from an external site. If the session
        was logged out (cookies cleared, CSRF, etc.), attempt re-login once.
        If that fails, flag the session to end early so we don't waste time
        scrolling a logged-out feed."""
        try:
            if _is_logged_in(self.page, navigate=False):
                return
            print("  ⚠ Session appears logged out after navigation — attempting re-login")
            try:
                ensure_login(self.page, self.profile_name, self.op_item)
                print("  ✓ Re-login successful")
            except Exception as e:
                print(f"  ✗ Re-login failed: {e}")
                self.ended_early = True
                self.end_reason = "logged out mid-session, re-login failed"
        except Exception as e:
            print(f"  Login recheck error: {e}")

    @property
    def elapsed_minutes(self):
        return (time.time() - self.start_time) / 60

    @property
    def session_over(self):
        return self.ended_early or self.elapsed_minutes >= self.p["duration_min"]

    def _ensure_focus(self):
        """Click body to ensure keyboard focus for arrow keys."""
        try:
            self.page.click("body", timeout=2000)
        except Exception:
            pass

    def _pick_watch_duration(self):
        """Pick watch duration using this session's randomized style."""
        ws = self.p["watch_style"]
        roll = random.random()
        if roll < ws["quick_skip_pct"]:
            return random.uniform(*ws["quick_range"])
        elif roll < ws["quick_skip_pct"] + ws["partial_watch_pct"]:
            return random.uniform(*ws["partial_range"])
        elif roll < ws["quick_skip_pct"] + ws["partial_watch_pct"] + ws["full_watch_pct"]:
            return random.uniform(*ws["full_range"])
        else:
            return random.uniform(*ws["loved_range"])

    def _like_current_video(self):
        if self.likes_given >= self.p["max_likes"]:
            return
        print("    ♥ Liking video")
        try:
            self.page.keyboard.press("l")
            self.likes_given += 1
            self._emit("like", location=self.current_location, url=self.page.url)
            human_pause(0.5, 1.5)
        except Exception:
            pass

    def _follow_current_creator(self):
        if self.follows_given >= self.p["max_follows"]:
            return
        print("    + Following creator")
        # Multiple selectors — TikTok ships UI changes frequently and we need
        # multilingual coverage (Spanish/Italian/French/Portuguese accounts).
        selectors = [
            '[data-e2e="feed-follow"]',
            '[data-e2e="browse-follow"]',
            '[data-e2e="follow-button"]',
            'button[aria-label*="Follow" i]',
            'button[aria-label*="Seguir" i]',
            'button[aria-label*="Seguire" i]',
            'button[aria-label*="Suivre" i]',
            'button:has-text("Follow"):not(:has-text("Following"))',
            'button:has-text("Seguir"):not(:has-text("Siguiendo"))',
            'button:has-text("Segui"):not(:has-text("Seguito"))',
            'button:has-text("Suivre"):not(:has-text("Suivi"))',
        ]
        try:
            follow_btn = None
            matched_selector = None
            for sel in selectors:
                try:
                    follow_btn = self.page.query_selector(sel)
                    if follow_btn:
                        matched_selector = sel
                        break
                except Exception:
                    continue
            if follow_btn:
                follow_btn.click()
                self.follows_given += 1
                self._emit("follow", location=self.current_location, url=self.page.url, selector=matched_selector)
                human_pause(1, 3)
            else:
                # Important telemetry: the script tried to follow but couldn't find the button.
                # The audit agent uses these to know when the selector list needs updating.
                self._emit("follow_skipped", reason="no_button_found", location=self.current_location, url=self.page.url)
        except Exception as e:
            self._emit("follow_skipped", reason=f"exception:{type(e).__name__}", location=self.current_location)

    # --- Navigation ---

    def navigate_to_fyp(self):
        print("  → Navigating to FYP")
        self.page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=15000)
        self.current_location = "fyp"
        human_pause(2, 5)
        self._ensure_focus()

    def navigate_to_explore(self):
        print("  → Navigating to Explore")
        self.page.goto("https://www.tiktok.com/explore", wait_until="domcontentloaded", timeout=15000)
        self.current_location = "explore"
        human_pause(2, 5)

    def navigate_to_following(self):
        print("  → Navigating to Following")
        self.page.goto("https://www.tiktok.com/following", wait_until="domcontentloaded", timeout=15000)
        self.current_location = "following"
        human_pause(2, 5)
        self._ensure_focus()

    # --- Activities ---

    def _next_video(self):
        """Move to next video — randomly use keyboard shortcut or on-screen button."""
        method = random.choice(["keyboard", "keyboard", "keyboard", "arrow_button"])
        if method == "keyboard":
            self.page.keyboard.press("ArrowDown")
        else:
            # Click the down-arrow button on screen (right side of video)
            try:
                down_btn = self.page.query_selector('[data-e2e="arrow-right"], [data-e2e="arrow-down"]')
                if down_btn:
                    down_btn.click()
                else:
                    self.page.keyboard.press("ArrowDown")
            except Exception:
                self.page.keyboard.press("ArrowDown")

    def _prev_video(self):
        """Go to previous video — randomly use keyboard or on-screen button."""
        method = random.choice(["keyboard", "keyboard", "arrow_button"])
        if method == "keyboard":
            self.page.keyboard.press("ArrowUp")
        else:
            try:
                up_btn = self.page.query_selector('[data-e2e="arrow-left"], [data-e2e="arrow-up"]')
                if up_btn:
                    up_btn.click()
                else:
                    self.page.keyboard.press("ArrowUp")
            except Exception:
                self.page.keyboard.press("ArrowUp")

    def _pause_video(self):
        """Pause/unpause the current video (spacebar or click)."""
        print("    ⏸ Pausing video")
        try:
            # Click the video area to pause (TikTok toggles on click)
            self.page.click('[data-e2e="browse-video"], video', timeout=2000)
            pause_duration = random.uniform(2, 12)
            time.sleep(pause_duration)
            # Unpause
            self.page.click('[data-e2e="browse-video"], video', timeout=2000)
        except Exception:
            pass

    def _bookmark_video(self):
        """Bookmark/save the current video."""
        print("    🔖 Bookmarking video")
        try:
            bookmark_btn = self.page.query_selector('[data-e2e="undefined-icon"], [data-e2e="browse-save"], [data-e2e="video-save"]')
            if bookmark_btn:
                bookmark_btn.click()
                human_pause(0.5, 1.5)
        except Exception:
            pass

    def _comment_on_video(self):
        """Leave a brief comment on the current video (~5% chance externally)."""
        if self.comments_left >= self.p["max_comments"]:
            return
        print("    💬 Commenting on video")
        # Bilingual comments — mix of English and Spanish, natural and short
        comments = [
            # Spanish
            "jajaja", "que genial", "me encanta", "increíble",
            "buenísimo", "esto es lo mejor", "verdad", "sí!!!",
            "qué lindo", "pura vida", "me identifico", "tal cual",
            "no puede ser", "demasiado bueno", "necesito más de esto",
            "facts", "wow esto es real", "justo lo que necesitaba ver",
            # English
            "lol", "this is so good", "no way", "love this",
            "haha amazing", "wait what", "need more of this",
            "exactly", "so true", "this is fire", "underrated",
            "yooo", "obsessed", "the accuracy", "finally someone said it",
            "i can't", "real talk", "vibes", "W",
            # Spanglish / mixed
            "too good jaja", "literally me", "noo jajaja",
        ]
        comment = random.choice(comments)
        comment_btn_selectors = [
            '[data-e2e="comment-icon"]',
            '[data-e2e="browse-comment"]',
            '[data-e2e="feed-comment"]',
            'button[aria-label*="Comment" i]',
            'button[aria-label*="Comentario" i]',
            'button[aria-label*="Commento" i]',
            'button[aria-label*="Commentaire" i]',
        ]
        input_selectors = [
            '[data-e2e="comment-input"]',
            'div[contenteditable="true"][data-tt*="comment" i]',
            'div[contenteditable="true"]',
        ]
        try:
            comment_btn = None
            for sel in comment_btn_selectors:
                try:
                    comment_btn = self.page.query_selector(sel)
                    if comment_btn:
                        break
                except Exception:
                    continue
            if not comment_btn:
                self._emit("comment_skipped", reason="no_comment_button", location=self.current_location, url=self.page.url)
                return
            comment_btn.click()
            human_pause(1, 3)
            comment_input = None
            for sel in input_selectors:
                try:
                    comment_input = self.page.query_selector(sel)
                    if comment_input:
                        break
                except Exception:
                    continue
            if not comment_input:
                self._emit("comment_skipped", reason="no_input_found", location=self.current_location, url=self.page.url)
                self.page.keyboard.press("Escape")
                return
            comment_input.click()
            human_pause(0.5, 1)
            for char in comment:
                self.page.keyboard.type(char, delay=random.randint(50, 150))
                if random.random() < 0.03:
                    time.sleep(random.uniform(0.3, 1))
            human_pause(0.5, 1.5)
            self.page.keyboard.press("Enter")
            self.comments_left += 1
            self._emit("comment", text=comment, location=self.current_location, url=self.page.url)
            human_pause(1, 3)
            self.page.keyboard.press("Escape")
            human_pause(0.5, 1)
        except Exception as e:
            self._emit("comment_skipped", reason=f"exception:{type(e).__name__}", location=self.current_location)

    def scroll_fyp(self):
        if self.current_location != "fyp":
            self.navigate_to_fyp()
        self._ensure_focus()

        num_videos = random.randint(3, 15)
        print(f"  ▶ Scrolling FYP — watching ~{num_videos} videos")
        for i in range(num_videos):
            if self.session_over:
                break
            watch_time = self._pick_watch_duration()
            print(f"    Watching video {i+1}/{num_videos} for {watch_time:.0f}s")
            time.sleep(watch_time)
            self.videos_watched += 1
            niche_match = self._check_niche_video()
            if niche_match:
                self.niche_videos += 1
            self._emit("video_watch", location=self.current_location, watch_time_s=round(watch_time, 1), niche_match=niche_match, url=self.page.url)

            # --- Micro-interactions during/after watching ---
            # Probabilities scale with warmup week — newer accounts engage less.
            # Wk1: very light. Wk2+: more active to give TikTok stronger signals.
            wk = self.p.get("warmup_week", 2)
            like_p   = 0.15 if wk <= 1 else 0.20
            follow_p = 0.03 if wk <= 1 else 0.07   # was 0.03 — only 1 follow in 10 days observed
            comment_p = 0.0 if wk <= 1 else 0.08   # was 0.04 — 0 comments in 10 days observed
            if random.random() < like_p:
                self._like_current_video()
            if random.random() < follow_p:
                self._follow_current_creator()
            if random.random() < comment_p:
                self._comment_on_video()
            # Bookmark (~5%)
            if random.random() < 0.05:
                self._bookmark_video()
            # Pause the video mid-watch (~8%)
            if random.random() < 0.08:
                self._pause_video()
            # Scroll back up to rewatch (~10%)
            if random.random() < 0.10 and i > 0:
                print("    ↑ Scrolling back up")
                self._prev_video()
                time.sleep(random.uniform(3, 8))
                self._next_video()
                human_pause(1, 2)

            # Move to next video (varied method)
            self._next_video()
            human_pause(0.3, 1.5)

    def browse_explore(self):
        if self.current_location != "explore":
            self.navigate_to_explore()
        print("  ▶ Browsing Explore page")
        for _ in range(random.randint(3, 10)):
            if self.session_over:
                break
            self.page.keyboard.press("ArrowDown")
            human_pause(1.5, 4)

        if random.random() < 0.4:
            print("    Clicking a trending topic")
            try:
                cards = self.page.query_selector_all('a[href*="/tag/"], a[href*="/discover/"]')
                if cards:
                    random.choice(cards[:10]).click()
                    human_pause(3, 6)
                    for _ in range(random.randint(2, 6)):
                        if self.session_over:
                            break
                        time.sleep(self._pick_watch_duration())
                        self.videos_watched += 1
                        self.page.keyboard.press("ArrowDown")
                        human_pause(0.5, 2)
                    self.page.go_back()
                    human_pause(1, 3)
            except Exception:
                pass

    def browse_following(self):
        if self.current_location != "following":
            self.navigate_to_following()
        self._ensure_focus()
        num_videos = random.randint(2, 8)
        print(f"  ▶ Browsing Following feed — {num_videos} videos")
        for i in range(num_videos):
            if self.session_over:
                break
            watch_time = self._pick_watch_duration()
            print(f"    Watching following video {i+1}/{num_videos} for {watch_time:.0f}s")
            time.sleep(watch_time)
            self.videos_watched += 1
            if random.random() < 0.20:
                self._like_current_video()
            self.page.keyboard.press("ArrowDown")
            human_pause(0.3, 1.5)

    def watch_live(self):
        print("  ▶ Checking out LIVE")
        self.page.goto("https://www.tiktok.com/live", wait_until="domcontentloaded", timeout=15000)
        self.current_location = "live"
        human_pause(3, 6)
        # Try to click into a live stream
        try:
            streams = self.page.query_selector_all('a[href*="/live/"]')
            if streams:
                random.choice(streams[:5]).click()
                watch = random.uniform(20, 90)
                print(f"    Watching live stream for {watch:.0f}s")
                time.sleep(watch)
                self.page.go_back()
                human_pause(1, 3)
            else:
                print("    No live streams found, moving on")
        except Exception:
            pass

    def check_inbox(self):
        print("  ▶ Checking inbox")
        self.page.goto("https://www.tiktok.com/messages", wait_until="domcontentloaded", timeout=15000)
        self.current_location = "inbox"
        time.sleep(random.uniform(3, 10))
        for _ in range(random.randint(0, 3)):
            self.page.keyboard.press("ArrowDown")
            human_pause(1, 3)

    def check_activity(self):
        print("  ▶ Checking notifications")
        # Activity/notifications — try sidebar icon
        try:
            self.page.click('a[href*="/activity"], [data-e2e="inbox-tab"]', timeout=3000)
        except Exception:
            # No direct URL for activity, just skip
            print("    Could not open activity tab")
            return
        self.current_location = "activity"
        time.sleep(random.uniform(3, 8))
        for _ in range(random.randint(0, 4)):
            self.page.keyboard.press("ArrowDown")
            human_pause(1, 3)

    def check_my_profile(self):
        print("  ▶ Browsing own profile")
        navigated = False
        for sel in ['[data-e2e="nav-profile"]', 'a[href*="/@"]']:
            try:
                self.page.click(sel, timeout=3000)
                navigated = True
                break
            except Exception:
                continue
        self.current_location = "my_profile"
        human_pause(3, 6)
        time.sleep(random.uniform(3, 8))
        for _ in range(random.randint(1, 4)):
            self.page.keyboard.press("ArrowDown")
            human_pause(1, 3)

    def visit_creator(self):
        """Click into a creator's profile from the current video."""
        print("  ▶ Visiting a creator's profile")
        try:
            avatar = self.page.query_selector('[data-e2e="browse-username"], [data-e2e="video-author-avatar"]')
            if avatar:
                avatar.click()
                self.current_location = "creator"
                human_pause(3, 6)
                vids = random.randint(2, 8)
                print(f"    Watching {vids} videos on their profile")
                for _ in range(vids):
                    if self.session_over:
                        break
                    self.page.keyboard.press("ArrowDown")
                    time.sleep(self._pick_watch_duration())
                    self.videos_watched += 1
                    if random.random() < 0.2:
                        self._like_current_video()
                if random.random() < 0.15:
                    self._follow_current_creator()
                self.page.go_back()
                human_pause(1, 3)
        except Exception:
            pass

    def do_search(self):
        if self.searches_done >= self.p["max_searches"]:
            self.browse_explore()
            return
        term = random.choice(self.search_terms) if self.search_terms else "trending"
        print(f"  ▶ Searching: '{term}'")
        self.page.goto(f"https://www.tiktok.com/search?q={term.replace(' ', '+')}", wait_until="domcontentloaded", timeout=15000)
        self.current_location = "search_results"
        human_pause(2, 4)
        self.searches_done += 1
        self._emit("search", query=term)

        for i in range(random.randint(3, 8)):
            if self.session_over:
                break
            watch_time = self._pick_watch_duration()
            print(f"    Watching search result {i+1} for {watch_time:.0f}s")
            time.sleep(watch_time)
            self.videos_watched += 1
            self._emit("video_watch", location="search_results", watch_time_s=round(watch_time, 1), niche_match=True, url=self.page.url)
            self.niche_videos += 1  # search results are on-niche by definition
            if random.random() < 0.2:
                self._like_current_video()
            self.page.keyboard.press("ArrowDown")
            human_pause(0.5, 2)

    def read_comments(self):
        """Open the comment section on the current video and scroll through."""
        print("  ▶ Reading comments on current video")
        try:
            # Try clicking the comment icon
            comment_btn = self.page.query_selector('[data-e2e="comment-icon"], [data-e2e="browse-comment"]')
            if comment_btn:
                comment_btn.click()
                human_pause(2, 4)
                # Scroll through comments
                for _ in range(random.randint(3, 10)):
                    if self.session_over:
                        break
                    self.page.keyboard.press("ArrowDown")
                    human_pause(1.5, 4)
                # Close comments by pressing Escape or clicking away
                self.page.keyboard.press("Escape")
                human_pause(0.5, 1.5)
        except Exception:
            pass

    def click_hashtag(self):
        """Click a hashtag on the current video to explore related content.
        In niche mode, falls back to navigating directly to a niche-themed tag URL
        when no hashtag is found on the current video (prevents wasted cycles)."""
        print("  ▶ Clicking a hashtag")
        try:
            tags = self.page.query_selector_all('a[href*="/tag/"]')
            if tags:
                random.choice(tags[:5]).click()
                human_pause(3, 6)
            elif self.search_terms:
                # Niche fallback: pick a term, strip spaces, navigate to the tag page
                term = random.choice(self.search_terms)
                slug = term.replace(" ", "").replace("-", "").lower()[:40]
                print(f"    No hashtags on video — browsing #{slug} directly")
                self.page.goto(f"https://www.tiktok.com/tag/{slug}", wait_until="domcontentloaded", timeout=15000)
                human_pause(3, 5)
            else:
                print("    No hashtags found on current video")
                return
            self.current_location = "hashtag"
            self._ensure_focus()
            for _ in range(random.randint(2, 5)):
                if self.session_over:
                    break
                time.sleep(self._pick_watch_duration())
                self.videos_watched += 1
                self.page.keyboard.press("ArrowDown")
                human_pause(0.5, 2)
            try:
                self.page.go_back()
            except Exception:
                pass
            human_pause(1, 3)
        except Exception:
            pass

    def idle_distraction(self):
        duration = random.uniform(8, 50)
        print(f"  ▶ [idle] Pausing for {duration:.0f}s (distracted)")
        time.sleep(duration)

    # --- Non-TikTok noise (human realism) ---

    def browse_other_site(self):
        """Visit a random non-TikTok website, browse briefly, then come back."""
        site = random.choice(OTHER_SITES)
        print(f"  ▶ 🌍 Leaving TikTok — visiting {site['name']}")
        try:
            self.page.goto(site["url"], wait_until="domcontentloaded", timeout=15000)
        except Exception:
            # Site may block or timeout — that's fine, human would just shrug
            print(f"    Site slow/blocked, moving on")
            self.page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=15000)
            self.current_location = "fyp"
            return

        self.current_location = "other_site"
        human_pause(2, 5)

        # Browse the site for a bit
        browse_time = random.uniform(10, 75)
        print(f"    Browsing {site['name']} for {browse_time:.0f}s")

        if site["scroll"]:
            # Scroll around like a human would
            scroll_actions = random.randint(3, 12)
            per_scroll_time = browse_time / scroll_actions
            for _ in range(scroll_actions):
                self.page.keyboard.press("ArrowDown")
                time.sleep(max(1, per_scroll_time + random.uniform(-1, 1)))
                # Occasionally scroll back up
                if random.random() < 0.15:
                    self.page.keyboard.press("ArrowUp")
                    time.sleep(random.uniform(1, 3))
                # Random click on something (probably nothing useful)
                if random.random() < 0.1:
                    try:
                        links = self.page.query_selector_all("a")
                        if links and len(links) > 5:
                            random.choice(links[2:min(20, len(links))]).click()
                            time.sleep(random.uniform(3, 10))
                            self.page.go_back()
                            time.sleep(random.uniform(1, 3))
                    except Exception:
                        pass
        else:
            # Just sit on the page for a bit (checking email, weather, etc.)
            time.sleep(browse_time)

        # Come back to TikTok
        print(f"    Returning to TikTok")
        self.page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=15000)
        self.current_location = "fyp"
        human_pause(2, 4)
        _, login_modal = dismiss_popups(self.page)
        if login_modal:
            self.login_modals_seen += 1
            if self.login_modals_seen >= 2:
                self.ended_early = True
                self.end_reason = "session not logged in — multiple login modals detected"
        self._recheck_login_after_nav()
        self._ensure_focus()
        human_pause(1, 3)

    def idle_away(self):
        """Leave the browser entirely — pure dead time, no interaction at all.
        Simulates the user putting their phone down, going to get coffee, etc."""
        duration = random.uniform(30, 120)
        print(f"  ▶ 💤 Away from browser for {duration:.0f}s (gone)")
        time.sleep(duration)

    def long_abandon(self):
        """Navigate to some other site and just abandon the browser for 5-10 minutes.
        Like a human who opened Reddit, got a phone call, and forgot about the laptop."""
        site = random.choice(OTHER_SITES)
        print(f"  ▶ 🚶 Abandoning browser on {site['name']} for a while")
        try:
            self.page.goto(site["url"], wait_until="domcontentloaded", timeout=15000)
        except Exception:
            pass
        self.current_location = "other_site"
        duration = random.uniform(5 * 60, 10 * 60)  # 5-10 minutes
        print(f"    Gone for {duration / 60:.1f} minutes...")
        time.sleep(duration)
        # Come back to TikTok
        print(f"    Back — returning to TikTok")
        self.page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=15000)
        self.current_location = "fyp"
        human_pause(2, 4)
        _, login_modal = dismiss_popups(self.page)
        if login_modal:
            self.login_modals_seen += 1
            if self.login_modals_seen >= 2:
                self.ended_early = True
                self.end_reason = "session not logged in — multiple login modals detected"
        self._recheck_login_after_nav()
        self._ensure_focus()
        human_pause(2, 5)

    def random_mouse_noise(self):
        """Aimless mouse movements, useless clicks, tab fidgeting.
        The kind of thing a human does when they're bored or thinking."""
        print("  ▶ 🖱️ Random mouse noise / fidgeting")
        actions = random.randint(3, 10)
        for _ in range(actions):
            roll = random.random()
            if roll < 0.35:
                # Random mouse movement to nowhere useful
                x = random.randint(100, 1100)
                y = random.randint(100, 700)
                try:
                    self.page.mouse.move(x, y)
                except Exception:
                    pass
                time.sleep(random.uniform(0.3, 1.5))
            elif roll < 0.55:
                # Click somewhere harmless (empty space, margin)
                x = random.choice([random.randint(10, 50), random.randint(800, 1200)])
                y = random.randint(100, 700)
                try:
                    self.page.mouse.click(x, y)
                except Exception:
                    pass
                time.sleep(random.uniform(0.5, 2))
            elif roll < 0.70:
                # Scroll a tiny bit then back
                try:
                    self.page.keyboard.press("ArrowDown")
                    time.sleep(random.uniform(0.5, 1.5))
                    self.page.keyboard.press("ArrowUp")
                except Exception:
                    pass
                time.sleep(random.uniform(0.3, 1))
            elif roll < 0.85:
                # Hover over something in the sidebar
                y = random.randint(100, 500)
                try:
                    self.page.mouse.move(30, y)
                except Exception:
                    pass
                time.sleep(random.uniform(1, 4))
            else:
                # Just wait — staring at screen doing nothing
                time.sleep(random.uniform(1, 5))

        human_pause(1, 3)


# ---------------------------------------------------------------------------
# Session orchestrator
# ---------------------------------------------------------------------------

def run_session(page: Page, personality: dict, search_terms: list, profile_name: str = "", op_item: str = None, logger=None):
    """Run a humanized TikTok session driven by the generated personality."""
    session = TikTokSession(page, personality, search_terms, profile_name=profile_name, op_item=op_item, logger=logger)
    p = personality

    # Emit session start
    session._emit("session_start",
                  duration_target_min=p.get("duration_min"),
                  start_page=p.get("start_page"),
                  max_likes=p.get("max_likes"),
                  max_follows=p.get("max_follows"),
                  max_comments=p.get("max_comments"),
                  max_searches=p.get("max_searches"),
                  niche_terms_count=len(search_terms))

    print(f"\n{'='*60}")
    print(f"SESSION PERSONALITY")
    print(f"  Duration: {p['duration_min']} min")
    print(f"  Activities: {', '.join(p['available_activities'])}")
    print(f"  Start page: {p['start_page']}")
    print(f"  Limits: {p['max_likes']}L / {p['max_follows']}F / {p['max_comments']}C / {p['max_searches']}S")
    top3 = sorted(p['weights'].items(), key=lambda x: -x[1])[:3]
    print(f"  Top weights: {', '.join(f'{k}={v:.0%}' for k,v in top3)}")
    print(f"{'='*60}")

    # Navigate to starting page
    start = p["start_page"]
    if start == "explore":
        print("\n🌐 Starting on Explore...")
        page.goto("https://www.tiktok.com/explore", wait_until="domcontentloaded", timeout=30000)
        session.current_location = "explore"
    elif start == "following":
        print("\n🌐 Starting on Following...")
        page.goto("https://www.tiktok.com/following", wait_until="domcontentloaded", timeout=30000)
        session.current_location = "following"
    else:
        print("\n🌐 Starting on FYP...")
        page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=30000)
        session.current_location = "fyp"

    human_pause(3, 7)
    page.screenshot(path="/tmp/tiktok_initial.png")
    print("  Screenshot: /tmp/tiktok_initial.png")
    session._ensure_focus()

    # Build the activity dispatch table (only available activities)
    dispatch = {
        "scroll_fyp": session.scroll_fyp,
        "browse_explore": session.browse_explore,
        "browse_following": session.browse_following,
        "watch_live": session.watch_live,
        "check_inbox": session.check_inbox,
        "check_activity": session.check_activity,
        "check_my_profile": session.check_my_profile,
        "visit_creator": session.visit_creator,
        "do_search": session.do_search,
        "read_comments": session.read_comments,
        "click_hashtag": session.click_hashtag,
        "idle_distraction": session.idle_distraction,
        "navigate_to_fyp": session.navigate_to_fyp,
        # Non-TikTok noise
        "browse_other_site": session.browse_other_site,
        "idle_away": session.idle_away,
        "random_mouse_noise": session.random_mouse_noise,
        "long_abandon": session.long_abandon,
    }

    activity_names = list(p["weights"].keys())
    activity_weights = [p["weights"][a] for a in activity_names]

    activity_count = 0
    screenshot_interval = random.randint(4, 8)  # take debug screenshot every N activities

    while not session.session_over:
        activity_count += 1
        chosen = random.choices(activity_names, weights=activity_weights, k=1)[0]
        elapsed = session.elapsed_minutes
        print(f"\n[{elapsed:.1f}m / {p['duration_min']}m] Activity #{activity_count}: {chosen}")

        # Close any extra tabs TikTok may have opened (external links, etc.) — keep only page.
        for extra in list(page.context.pages):
            if extra != page:
                try:
                    extra.close()
                except Exception:
                    pass

        # Defensively dismiss any modals/popups that may have appeared (onboarding prompts,
        # sign-up CTAs, cookie banners). Safe to call even if nothing is open.
        _, login_modal = dismiss_popups(page)
        if login_modal:
            session.login_modals_seen += 1
            if session.login_modals_seen >= 2:
                session.ended_early = True
                session.end_reason = "session not logged in — multiple login modals detected"

        try:
            dispatch[chosen]()
        except Exception as e:
            print(f"  ⚠ Error during {chosen}: {e}")
            try:
                page.goto("https://www.tiktok.com/foryou", wait_until="domcontentloaded", timeout=15000)
                session.current_location = "fyp"
                human_pause(2, 4)
                session._ensure_focus()
            except Exception:
                pass

        # Debug screenshot periodically
        if activity_count % screenshot_interval == 0:
            try:
                page.screenshot(path=f"/tmp/tiktok_mid_{activity_count}.png")
                print(f"  📸 Mid-session screenshot: /tmp/tiktok_mid_{activity_count}.png")
            except Exception:
                pass

        human_pause(1, 3)

    # Session summary
    page.screenshot(path="/tmp/tiktok_final.png")
    _niche_pct = round(session.niche_videos / max(session.videos_watched, 1), 3)
    results = {
        "duration_min": round(session.elapsed_minutes, 1),
        "target_duration_min": p["duration_min"],
        "videos_watched": session.videos_watched,
        "niche_videos": session.niche_videos,
        "fyp_niche_pct": _niche_pct,
        "likes": session.likes_given,
        "follows": session.follows_given,
        "comments": session.comments_left,
        "searches": session.searches_done,
        "activities": activity_count,
        "available_activities": p["available_activities"],
        "start_page": p["start_page"],
    }

    print(f"\n{'='*60}")
    print(f"SESSION COMPLETE")
    print(f"  Duration: {results['duration_min']} min (target: {p['duration_min']})")
    print(f"  Videos watched: {results['videos_watched']}")
    print(f"  Niche: {_niche_pct:.0%} ({session.niche_videos}/{session.videos_watched} videos on-niche)")
    print(f"  Likes: {results['likes']} / Follows: {results['follows']}")
    print(f"  Comments: {results['comments']} / Searches: {results['searches']}")
    print(f"  Activities: {results['activities']}")
    print(f"  Final screenshot: /tmp/tiktok_final.png")
    print(f"{'='*60}")

    # Emit session end + flush remaining buffered actions
    session._emit("session_end", **results)
    if logger:
        try:
            logger.flush()
        except Exception:
            pass

    return results


# ---------------------------------------------------------------------------
# Login check + auto-login
# ---------------------------------------------------------------------------

BLAZE_PROFILES = {"tiktok,blazemoney_agents", "tiktok,blazemoney_latam", "tiktok,blaze__money", "tiktok,blazemoney_stables"}

def _is_logged_in(page: Page, navigate: bool = True) -> bool:
    """Return True if TikTok shows CLEAR logged-in indicators.

    Logged-out users can still see FYP content, so presence of videos alone is
    NOT a logged-in signal. We require either a strict positive selector match OR
    the absence of all login CTAs (TikTok always shows a Log in button when logged out).

    If `navigate` is False, checks current page without navigating (for mid-session
    checks after returning from external sites).
    """
    try:
        if navigate:
            page.goto("https://www.tiktok.com/", wait_until="domcontentloaded", timeout=20000)
            time.sleep(random.uniform(4, 6))
        # Hard negative: redirected to login page
        if "/login" in page.url:
            return False
        # Hard negative: a "Log in" button is visible (sidebar, header, or prompt)
        # Logged-in users never see a prominent Log-in CTA.
        login_btn = page.query_selector(
            'a[href="/login"]:visible, [data-e2e="login-button"]:visible, button:has-text("Log in"):visible'
        )
        if login_btn:
            return False
        # Strict positive selectors — data-e2e attrs + href-based (covers DOM changes)
        strict_positive_selectors = [
            '[data-e2e="nav-profile"]',
            '[data-e2e="upload-icon"]',
            '[data-e2e="profile-icon"]',
            'a[href^="/@"][data-e2e="nav-profile"]',
            'a[href="/upload"]',
            'a[href^="/@"]',
            'a[href="/messages"]',    # Messages — only rendered for logged-in users
            'a[href="/activity"]',    # Activity — only rendered for logged-in users
            'a[href="/following"]',   # Following — only rendered for logged-in users
        ]
        for sel in strict_positive_selectors:
            if page.query_selector(sel):
                return True
        # JS fallback: scan all <a> hrefs for a user profile link (/@username)
        # TikTok renders these for the sidebar Profile link and Following accounts.
        try:
            hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href') || '')")
            if any(h.startswith("/@") or ("/@" in h and h.startswith("/")) for h in hrefs):
                return True
        except Exception:
            pass
        # Final fallback: if we're at tiktok.com root with no login button visible,
        # TikTok would always show a Log-in CTA when logged out — so absence = logged in.
        if page.url.rstrip("/") in ("https://www.tiktok.com", "https://www.tiktok.com/foryou"):
            return True
        return False
    except Exception as e:
        print(f"  Login check error: {e}")
        return False


def dismiss_popups(page: Page) -> tuple:
    """Detect and close common TikTok modals (onboarding, sign-up prompts, cookie banners).
    Returns (dismissed_count, login_modal_seen) where login_modal_seen=True means a
    'Log in to TikTok' gating modal was detected — the session is not authenticated."""
    dismissed = 0
    login_modal_seen = False

    # Login-gated modal selectors — if any of these appear the session is not logged in
    login_modal_selectors = [
        '[data-e2e="login-modal-close"]',
        '[data-e2e="login-popup-close"]',
    ]
    for sel in login_modal_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click(timeout=2000)
                dismissed += 1
                login_modal_seen = True
                time.sleep(random.uniform(0.4, 1.0))
        except Exception:
            pass

    # "What would you like to watch on TikTok?" onboarding modal — click Log in
    if not login_modal_seen:
        try:
            _onboard_login = page.query_selector(
                'div[role="dialog"] button:has-text("Log in"), '
                'div[class*="modal" i] button:has-text("Log in")'
            )
            if _onboard_login and _onboard_login.is_visible():
                _onboard_login.click(timeout=3000)
                dismissed += 1
                login_modal_seen = True
                time.sleep(random.uniform(1, 2))
        except Exception:
            pass

    # Fallback text-based detection: login modal without a recognized close button
    if not login_modal_seen:
        try:
            dialog = page.query_selector('div[role="dialog"]')
            if dialog and dialog.is_visible():
                dialog_text = dialog.inner_text(timeout=1000).lower()
                if "log in to tiktok" in dialog_text or "sign up for tiktok" in dialog_text:
                    login_modal_seen = True
                    # Try Escape to dismiss it
                    page.keyboard.press("Escape")
                    dismissed += 1
                    time.sleep(random.uniform(0.3, 0.8))
        except Exception:
            pass

    # Common modal close-button selectors (TikTok uses several variations)
    close_selectors = [
        '[data-e2e="modal-close-inner-button"]',
        '[data-e2e="modal-close"]',
        'div[class*="Modal"] button[aria-label*="Close" i]',
        'div[class*="modal" i] svg[class*="close" i]',
        'button[aria-label*="Close" i]:visible',
        'button[aria-label*="Dismiss" i]:visible',
    ]
    for sel in close_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click(timeout=2000)
                dismissed += 1
                time.sleep(random.uniform(0.4, 1.0))
        except Exception:
            pass
    # Fallback: press Escape to dismiss anything modal-like
    try:
        overlay = page.query_selector('div[class*="Modal"], div[role="dialog"], div[class*="overlay" i]')
        if overlay and overlay.is_visible():
            page.keyboard.press("Escape")
            dismissed += 1
            time.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass
    if dismissed:
        suffix = " ⚠ login modal detected — session may not be authenticated" if login_modal_seen else ""
        print(f"  🗙 Dismissed {dismissed} popup(s){suffix}")
    return dismissed, login_modal_seen


def _get_credentials_from_1password(op_item: str):
    """Retrieve TikTok email + password from 1Password by item name."""
    import subprocess
    print(f"  Fetching credentials from 1Password: '{op_item}'")
    # OP_SERVICE_ACCOUNT_TOKEN is loaded from .env.cli at script startup.
    # The op CLI picks it up from the environment automatically — no --account
    # flag, no biometric prompt, no interactive sign-in required.
    import tempfile as _tf
    xdg = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/op-xdg-{os.getuid()}"
    os.makedirs(xdg, mode=0o700, exist_ok=True)
    op_env = {**os.environ, "XDG_RUNTIME_DIR": xdg}
    result = subprocess.run(
        ["op", "item", "get", op_item, "--vault", "Tiktok",
         "--fields", "username,password", "--reveal"],
        capture_output=True, text=True, timeout=20,
        env=op_env, stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        # Never prompt for permissions. If the service account token doesn't work,
        # fail immediately and tell the user to fix it manually.
        raise Exception(
            f"op CLI failed for '{op_item}' — check OP_SERVICE_ACCOUNT_TOKEN in .env.cli. "
            f"Manual login required via Multilogin. stderr: {result.stderr.strip()}"
        )
    parts = result.stdout.strip().split(",", 1)
    if len(parts) < 2:
        raise Exception(f"Unexpected 1Password output for '{op_item}': {result.stdout!r}")
    return parts[0].strip(), parts[1].strip()  # email, password


def _fetch_tiktok_otp(timeout_secs: int = 60) -> str:
    """Poll AgentMail for a TikTok OTP email; returns the 6-digit code or raises."""
    import subprocess
    import json as _json
    import re as _re

    agentmail_key = os.environ.get("AGENTMAIL_API_KEY", "")
    if not agentmail_key:
        raise Exception("AGENTMAIL_API_KEY not set — cannot fetch OTP")

    print("  Waiting for TikTok OTP email (up to 60s)...")
    deadline = time.time() + timeout_secs
    seen_ids = set()

    # Snapshot existing messages so we only look at NEW ones
    result = subprocess.run(
        ["agentmail", "inboxes:messages", "list", "--inbox-id", "tiktok@agentmail.to"],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "AGENTMAIL_API_KEY": agentmail_key},
    )
    if result.returncode == 0:
        try:
            for msg in _json.loads(result.stdout).get("messages", []):
                seen_ids.add(msg.get("id"))
        except Exception:
            pass

    while time.time() < deadline:
        time.sleep(10)
        result = subprocess.run(
            ["agentmail", "inboxes:messages", "list", "--inbox-id", "tiktok@agentmail.to"],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "AGENTMAIL_API_KEY": agentmail_key},
        )
        if result.returncode != 0:
            continue
        try:
            messages = _json.loads(result.stdout).get("messages", [])
        except Exception:
            continue
        for msg in messages:
            msg_id = msg.get("id")
            if msg_id in seen_ids:
                continue
            subject = (msg.get("subject") or "").lower()
            if "tiktok" not in subject and "verification" not in subject and "code" not in subject:
                continue
            # Retrieve full message body
            detail = subprocess.run(
                ["agentmail", "inboxes:messages", "retrieve",
                 "--inbox-id", "tiktok@agentmail.to", "--message-id", msg_id],
                capture_output=True, text=True, timeout=15,
                env={**os.environ, "AGENTMAIL_API_KEY": agentmail_key},
            )
            if detail.returncode != 0:
                continue
            match = _re.search(r"\b(\d{6})\b", detail.stdout)
            if match:
                print(f"  OTP received: {match.group(1)}")
                return match.group(1)
            seen_ids.add(msg_id)

    raise Exception("TikTok OTP email did not arrive within 60s")


def ensure_login(page: Page, profile_name: str, op_item: str = None) -> None:
    """
    Verify TikTok is logged in. If not, attempt email login via 1Password credentials
    and AgentMail OTP handling. Raises on failure so the caller can mark the session failed.
    op_item: 1Password item name (e.g. "TikTok - Sebastian Vargas"). Falls back to
    "TikTok - {profile_name}" if not provided.
    """
    print("\n🔐 Checking TikTok login state...")
    if _is_logged_in(page):
        print("✓ Already logged in — proceeding.")
        return

    print("⚠ Not logged in. Attempting auto-login...")
    resolved_item = op_item or f"TikTok - {profile_name}"
    email, password = _get_credentials_from_1password(resolved_item)
    print(f"  Email: {email}")

    # Navigate to email login
    page.goto("https://www.tiktok.com/login/phone-or-email/email",
              wait_until="load", timeout=45000)
    time.sleep(random.uniform(4, 7))
    page.screenshot(path="/tmp/tiktok_login_start.png")


    # If TikTok redirected away from the login page, verify with a DOM check — TikTok
    # redirects both logged-in AND logged-out users away from /login, so URL alone is
    # not sufficient. A logged-out redirect just lands on /foryou without a session.
    # TikTok is a SPA; wait for one authenticated indicator (up to 12s) before deciding.
    if "/login" not in page.url:
        # Wait for the page to fully hydrate before checking login state
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        auth_selectors = [
            '[data-e2e="nav-profile"]',
            '[data-e2e="upload-icon"]',
            '[data-e2e="profile-icon"]',
            'a[href^="/@"]',
            'a[href="/upload"]',
        ]
        confirmed_logged_in = False
        for sel in auth_selectors:
            try:
                page.wait_for_selector(sel, timeout=4000)
                confirmed_logged_in = True
                break
            except Exception:
                pass
        if confirmed_logged_in:
            print("  ✓ Already logged in (TikTok redirected from login URL, DOM confirmed) — proceeding.")
            return
        # Hard check: is there a visible Log-in button? If yes, truly not logged in.
        login_btn = page.query_selector('a[href="/login"]:visible, button:has-text("Log in"):visible')
        if not login_btn:
            # No login button visible either — ambiguous state, but likely logged in with slow DOM.
            # Trust the redirect rather than re-running credentials, to avoid infinite loop.
            print("  ✓ Already logged in (TikTok redirect, no login-button found) — proceeding.")
            return
        # Visible login button → genuinely not logged in, proceed with credentials
        print("  ⚠ Redirected from login URL but login button visible — re-navigating to login form.")
        page.goto("https://www.tiktok.com/login/phone-or-email/email",
                  wait_until="load", timeout=45000)
        time.sleep(random.uniform(4, 7))
        page.screenshot(path="/tmp/tiktok_login_start.png")

    # Fill email — try multiple selectors in case TikTok changed the DOM
    email_sel = 'input[name="username"]'
    alt_sel = 'input[type="text"][placeholder]'
    try:
        page.wait_for_selector(email_sel, timeout=20000)
    except Exception:
        page.screenshot(path="/tmp/tiktok_login_start.png")
        # Fallback: try generic text input
        page.wait_for_selector(alt_sel, timeout=10000)
        email_sel = alt_sel
    human_type(page, email_sel, email)
    time.sleep(random.uniform(0.5, 1.2))

    # Fill password
    pw_sel = 'input[type="password"]'
    page.wait_for_selector(pw_sel, timeout=10000)
    human_type(page, pw_sel, password)
    time.sleep(random.uniform(0.5, 1.2))

    # Wait for login button to become enabled (CAPTCHA may be blocking it)
    login_btn = page.query_selector('button[data-e2e="login-button"]')
    if login_btn and not login_btn.is_enabled():
        print("  ⏸ Login button disabled — CAPTCHA blocking. Escalating and stopping session.")
        page.screenshot(path="/tmp/warmup_captcha.png")
        try:
            import subprocess as _sp2
            _sp2.run(["convert", "/tmp/warmup_captcha.png", "-resize", "1800x1800>", "/tmp/warmup_captcha.png"], timeout=5)
        except Exception:
            pass
        _rec = os.environ.get("_WARMUP_RECORDING_PATH", "")
        _captcha_msg = (
            f"🧩 CAPTCHA — {profile_name}\n\n"
            "Login button disabled (slider puzzle blocking login).\n"
            "Session is stopping — profile lock will be released.\n\n"
            "noVNC: http://100.96.234.61:6080/vnc.html\n\n"
            + (f"Recording: {_rec}\n\n" if _rec else "")
            + "Reply to this message once fixed — server will retry immediately."
        )
        try:
            import subprocess as _sp2
            _sp2.run([
                "curl", "-s", "-X", "POST",
                "https://api.telegram.org/bot8645212775:AAGY4HuJmSn9d_S9ld9nU5KpGca2_SBF598/sendPhoto",
                "-F", "chat_id=5043064976",
                "-F", f"caption={_captcha_msg}",
                "-F", "photo=@/tmp/warmup_captcha.png",
            ], timeout=15)
        except Exception:
            try:
                _sp2.run([
                    "curl", "-s", "-X", "POST",
                    "https://api.telegram.org/bot8645212775:AAGY4HuJmSn9d_S9ld9nU5KpGca2_SBF598/sendMessage",
                    "-d", "chat_id=5043064976",
                    "--data-urlencode", f"text={_captcha_msg}",
                ], timeout=10)
            except Exception:
                pass
        raise Exception("CAPTCHA — slider puzzle detected, session stopped immediately")

    # Submit
    if login_btn:
        login_btn.click()
    else:
        page.keyboard.press("Enter")
    time.sleep(random.uniform(4, 6))
    page.screenshot(path="/tmp/tiktok_login_after_submit.png")

    # Detect 24h lockout — "Maximum number of attempts reached. Try again later."
    # If we see this, do NOT retry: every retry extends the lockout window.
    # Raise with a recognizable tag so the executor auto-pauses the account for 24h.
    try:
        page_text = page.inner_text("body", timeout=2000).lower()
    except Exception:
        page_text = ""
    if "maximum number of attempts" in page_text or "try again later" in page_text:
        raise Exception(
            "TIKTOK_LOCKOUT_24H: TikTok login screen shows 'Maximum number of attempts reached. "
            "Try again later.' Account must be paused for 24h — do not retry. "
            "Screenshot: /tmp/tiktok_login_after_submit.png"
        )

    # Check for OTP prompt
    otp_sel = 'input[placeholder*="code"], input[name="code"], input[type="number"][maxlength="6"]'
    otp_input = page.query_selector(otp_sel)
    if otp_input:
        print("  OTP prompt detected — fetching from AgentMail...")
        otp = _fetch_tiktok_otp(timeout_secs=60)
        human_type(page, otp_sel, otp)
        time.sleep(random.uniform(1, 2))
        # Submit OTP
        submit = page.query_selector('button[type="submit"], button[data-e2e="login-button"]')
        if submit:
            submit.click()
        time.sleep(random.uniform(4, 6))

    page.screenshot(path="/tmp/tiktok_login_final.png")

    # Verify — if not logged in, escalate and stop immediately
    if not _is_logged_in(page):
        print("  ⏸ Auto-login did not succeed. Escalating and stopping session.")
        page.screenshot(path="/tmp/warmup_captcha.png")
        try:
            import subprocess as _sp
            _sp.run(["convert", "/tmp/warmup_captcha.png", "-resize", "1800x1800>", "/tmp/warmup_captcha.png"], timeout=5)
        except Exception:
            pass
        _rec2 = os.environ.get("_WARMUP_RECORDING_PATH", "")
        _login_fail_msg = (
            f"🧩 Login failed — {profile_name}\n\n"
            "Auto-login did not result in a logged-in session.\n"
            "Could be: CAPTCHA, wrong credentials, or unexpected TikTok flow.\n"
            "Screenshot shows current screen state.\n\n"
            "noVNC: http://100.96.234.61:6080/vnc.html\n\n"
            + (f"Recording: {_rec2}\n\n" if _rec2 else "")
            + "Reply to this message once fixed — server will retry immediately."
        )
        try:
            import subprocess as _sp
            _sp.run([
                "curl", "-s", "-X", "POST",
                "https://api.telegram.org/bot8645212775:AAGY4HuJmSn9d_S9ld9nU5KpGca2_SBF598/sendPhoto",
                "-F", "chat_id=5043064976",
                "-F", f"caption={_login_fail_msg}",
                "-F", "photo=@/tmp/warmup_captcha.png",
            ], timeout=15)
        except Exception:
            try:
                _sp.run([
                    "curl", "-s", "-X", "POST",
                    "https://api.telegram.org/bot8645212775:AAGY4HuJmSn9d_S9ld9nU5KpGca2_SBF598/sendMessage",
                    "-d", "chat_id=5043064976",
                    "--data-urlencode", f"text={_login_fail_msg}",
                ], timeout=10)
            except Exception:
                pass
        page.screenshot(path="/tmp/tiktok_login_final.png")
        raise Exception(
            "Auto-login failed (captcha, wrong credentials, or unexpected flow). "
            "Screenshots: /tmp/tiktok_login_*.png"
        )
    print("✓ Login successful.")


# ---------------------------------------------------------------------------
# Multilogin profile management
# ---------------------------------------------------------------------------

def _is_proxy_error(resp_text: str, error_code: str) -> bool:
    """Detect proxy-related failures in a launcher response.

    No public API exists for rotating Multilogin's built-in proxy IP, so the
    executor has to ask the human to click "Get new IP" in the desktop app.
    This helper surfaces the specific failure mode as a recognizable tag.
    """
    t = (resp_text or "").lower()
    c = (error_code or "").upper()
    proxy_markers = ("proxy", "tunnel", "connection refused", "connection timed out",
                     "unable to connect to proxy", "wrong proxy", "no route")
    code_markers = ("PROXY", "TUNNEL", "CONNECTION")
    return (
        any(m in t for m in proxy_markers)
        or any(m in c for m in code_markers)
    )



def release_cloud_lock(folder_id: str, profile_id: str):
    """Release Multilogin cloud lock before starting a profile.
    Treats 200 and 404 as success — 404 means no lock existed.
    Best-effort: logs failures but does not raise.
    """
    workspace_id = os.environ.get("MLX_WORKSPACE_ID", "")
    if not workspace_id:
        print("  release_cloud_lock: MLX_WORKSPACE_ID not set, skipping lock release")
        return
    headers = {
        "Authorization": f"Bearer {MLX_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"profile_id": profile_id, "workspace_id": workspace_id, "folder_id": folder_id}
    try:
        resp = requests.delete(
            "https://api.multilogin.com/bpds/profile/lock",
            headers=headers,
            json=payload,
            timeout=10,
        )
        if resp.status_code in (200, 404):
            print(f"  Cloud lock released (status={resp.status_code})")
        else:
            print(f"  Cloud lock release returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"  Cloud lock release failed (non-fatal): {e}")


def start_profile(folder_id: str, profile_id: str):
    release_cloud_lock(folder_id, profile_id)
    headers = {"Authorization": f"Bearer {MLX_TOKEN}", "Accept": "application/json"}
    url = f"https://launcher.mlx.yt:45001/api/v2/profile/f/{folder_id}/p/{profile_id}/start?automation_type=playwright&headless_mode=false"
    print(f"Starting Multilogin profile {profile_id}...")
    resp = requests.get(url, headers=headers, verify=False)
    if resp.status_code == 200:
        port = resp.json()["data"]["port"]
        print(f"Profile started on port {port}")
        return port
    # Already running — retrieve the existing port
    try:
        err = resp.json()
        code = err.get("status", {}).get("error_code", "")
    except Exception:
        err = {}
        code = ""
    if code == "PROFILE_ALREADY_RUNNING":
        print("Profile already running — connecting to existing instance...")
        status_url = f"https://launcher.mlx.yt:45001/api/v1/profile/p/{profile_id}"
        sr = requests.get(status_url, headers=headers, verify=False)
        if sr.status_code == 200:
            port = sr.json()["data"]["port"]
            print(f"Connected on port {port}")
            return port
        # Fallback: scan OS process list for the CDP port — never restart a running profile
        # (restarting kills any active login session, forcing another CAPTCHA cycle)
        print("Could not get port from status — scanning process list for CDP port...")
        import subprocess as _ps_proc, re as _re
        try:
            ps_out = _ps_proc.check_output(["ps", "aux"], text=True)
            m = _re.search(
                r"--client-session-id=" + re.escape(profile_id) +
                r".*?--remote-debugging-port=(\d+)",
                ps_out
            )
            if not m:
                # Also try reversed order
                m = _re.search(
                    r"--remote-debugging-port=(\d+).*?--client-session-id=" + re.escape(profile_id),
                    ps_out
                )
            if m:
                port = int(m.group(1))
                print(f"Found CDP port {port} via process list — connecting.")
                return port
        except Exception as _e:
            print(f"  Process scan failed: {_e}")
        raise Exception(
            f"PROFILE_ALREADY_RUNNING but could not determine CDP port. "
            f"Please stop profile {profile_id} manually in Multilogin, then retry."
        )

    # Proxy-related failure — raise a recognizable tag so the executor can ask
    # the human to click "Get new IP" in Multilogin and then retry the launch.
    if _is_proxy_error(resp.text, code):
        raise Exception(
            f"PROXY_REFRESH_NEEDED: Multilogin launcher rejected the profile start with a "
            f"proxy error (code={code!r}). Open Multilogin, find profile {profile_id}, "
            f"click 'Get new IP' on its proxy, wait for the new IP to connect, then retry. "
            f"Raw response: {resp.text[:500]}"
        )

    raise Exception(
        f"Profile start failed (status={resp.status_code}, code={code!r}): {resp.text[:500]}"
    )


def stop_profile(profile_id: str):
    headers = {"Authorization": f"Bearer {MLX_TOKEN}", "Accept": "application/json"}
    url = f"https://launcher.mlx.yt:45001/api/v1/profile/stop/p/{profile_id}"
    print(f"\nStopping profile {profile_id}...")
    resp = requests.get(url, headers=headers, verify=False)
    if resp.status_code == 200:
        print("Profile stopped.")
    else:
        print(f"Error stopping: {resp.text}")


def resolve_profile(name_query: str = None, profile_id: str = None):
    """Find a profile by partial name match or exact ID."""
    if profile_id:
        for name, info in PROFILES.items():
            if info["id"] == profile_id:
                return name, info
        # Not in registry but use it anyway
        return "Unknown", {"id": profile_id, "folder": FLOOENTLY_FOLDER, "country": "Unknown"}

    if name_query:
        query = name_query.lower()
        for name, info in PROFILES.items():
            if query in name.lower():
                return name, info
        print(f"No profile matching '{name_query}'. Available: {', '.join(PROFILES.keys())}")
        sys.exit(1)

    # Random profile from Flooently folder
    name = random.choice(list(PROFILES.keys()))
    return name, PROFILES[name]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="TikTok Browser Warmup")
    parser.add_argument("--profile", type=str, help="Profile name (partial match)")
    parser.add_argument("--profile-id", type=str, help="Exact Multilogin profile ID")
    parser.add_argument("--duration", type=float, help="Override session duration (minutes)")
    parser.add_argument("--week", type=int, default=1, help="Warmup week (1-4+, affects engagement limits)")
    parser.add_argument("--niche-terms", type=str, default="",
                        help="Comma-separated niche search terms. When set, session biases "
                             "searches/hashtags/creator visits toward the niche so ≥50%% of "
                             "time is spent priming the FYP algorithm on-topic.")
    parser.add_argument("--daily-niche-pct", type=float, default=None,
                        help="Running daily niche %% (0.0–1.0) from prior sessions today. "
                             "Below 0.70 → NICHE_PUSH, above 0.90 → NOISE_INJECT, else BALANCED.")
    parser.add_argument("--account-slug", type=str, default="",
                        help="Account slug for action logging (e.g. 'tiktok,flooently_spanish'). "
                             "If omitted, action logging to Supabase is disabled.")
    parser.add_argument("--session-id", type=str, default="",
                        help="Stable session UUID (lets the audit agent group rows). "
                             "If omitted, one is generated per run.")
    parser.add_argument("--warmup-day", type=int, default=None, help="Day N since warmup start (for action logs).")
    args = parser.parse_args()

    if not MLX_TOKEN:
        print("ERROR: MLX_AUTOMATION_TOKEN (or MULTILOGIN_API_KEY) not set. Run: source .env.cli")
        sys.exit(1)

    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Resolve profile
    name, profile_info = resolve_profile(args.profile, args.profile_id)
    print(f"\n👤 Profile: {name} ({profile_info['country']})")
    print(f"   ID: {profile_info['id']}")

    # Niche terms drive the FYP priming — pulled from Airtable per-account.
    # Empty = no niche focus (fallback to exploration mode).
    if args.niche_terms:
        search_terms = [t.strip() for t in args.niche_terms.split(",") if t.strip()]
        print(f"  🎯 Niche priming mode — {len(search_terms)} search terms loaded")
    else:
        search_terms = []
        print("  ⚠ No --niche-terms provided — session will not prime a niche")

    # Determine session mode from daily running niche %
    _dnp = args.daily_niche_pct
    if _dnp is None:
        session_mode = "BALANCED"
        print(f"  📊 Session mode: BALANCED (no prior niche data today)")
    elif _dnp < 0.70:
        session_mode = "NICHE_PUSH"
        print(f"  📊 Session mode: NICHE_PUSH (daily niche {_dnp:.0%} < 70% target — amplifying niche activities)")
    elif _dnp > 0.90:
        session_mode = "NOISE_INJECT"
        print(f"  📊 Session mode: NOISE_INJECT (daily niche {_dnp:.0%} > 90% target — injecting randomness)")
    else:
        session_mode = "BALANCED"
        print(f"  📊 Session mode: BALANCED (daily niche {_dnp:.0%} in 70–90%% target range)")

    # Generate session personality (niche-aware when terms are provided)
    personality = generate_session_personality(
        warmup_week=args.week,
        duration_override=args.duration,
        niche_mode=bool(search_terms),
        session_mode=session_mode,
    )

    # Launch and run
    port = start_profile(profile_info["folder"], profile_info["id"])
    human_pause(3, 5)

    # Start screen recording (1fps timelapse of the Xvfb display)
    _rec_proc = None
    _rec_path = None
    try:
        import re as _re
        _rec_dir = "/opt/warmup/recordings"
        os.makedirs(_rec_dir, exist_ok=True)
        _safe_name = _re.sub(r"[^a-zA-Z0-9_-]", "_", name)
        _rec_path = f"{_rec_dir}/{_safe_name}_{int(time.time())}.mp4"
        _display = os.environ.get("DISPLAY", ":99")
        _rec_proc = subprocess.Popen(
            ["ffmpeg", "-y", "-f", "x11grab", "-video_size", "1920x1080",
             "-framerate", "1", "-i", _display,
             "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
             "-pix_fmt", "yuv420p", _rec_path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print(f"  📹 Recording: {_rec_path}")
    except Exception as _rec_err:
        print(f"  Recording start failed (non-fatal): {_rec_err}")

    # Expose recording path to login helpers so they can attach it to alerts
    os.environ["_WARMUP_RECORDING_PATH"] = _rec_path or ""

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.connect_over_cdp(
                endpoint_url=f"http://127.0.0.1:{port}",
                timeout=15000
            )
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
            page.set_viewport_size({"width": 1280, "height": 800})

            ensure_login(page, name, op_item=profile_info.get("op_item"))

            # Initialize action logger if account slug was provided
            logger = None
            if args.account_slug and SupabaseLogger is not None:
                session_id = args.session_id or str(uuid.uuid4())
                logger = SupabaseLogger(
                    account_slug=args.account_slug,
                    session_id=session_id,
                    warmup_day=args.warmup_day,
                    warmup_week=args.week,
                )
                print(f"  📡 Supabase action logging enabled — session_id={session_id}")

            results = run_session(page, personality, search_terms, profile_name=name, op_item=profile_info.get("op_item"), logger=logger)
            print(f"\nResults JSON: {json.dumps(results, indent=2)}")

        except Exception as e:
            print(f"\nFatal error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Stop recording, then clean up old recordings (> 7 days)
            if _rec_proc and _rec_proc.poll() is None:
                _rec_proc.terminate()
                try:
                    _rec_proc.wait(timeout=10)
                except Exception:
                    _rec_proc.kill()
            if _rec_path and os.path.exists(_rec_path):
                _size_mb = os.path.getsize(_rec_path) / 1_000_000
                print(f"  📹 Recording saved: {_rec_path} ({_size_mb:.1f} MB)")
                try:
                    import glob as _glob
                    import time as _t
                    _cutoff = _t.time() - 7 * 86400
                    for _old in _glob.glob("/opt/warmup/recordings/*.mp4"):
                        if os.path.getmtime(_old) < _cutoff:
                            os.remove(_old)
                except Exception:
                    pass
            stop_profile(profile_info["id"])


if __name__ == "__main__":
    main()
