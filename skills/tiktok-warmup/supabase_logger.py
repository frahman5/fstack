"""
Action emitter for the TikTok warmup script. Buffers actions in memory
and flushes batches to Supabase. Designed to fail silently — we never
want logging issues to break a warmup session.

Usage in tiktok-warmup-poc.py:
    from supabase_logger import SupabaseLogger
    logger = SupabaseLogger(account_slug="tiktok,flooently_spanish",
                            session_id="<uuid>",
                            warmup_day=10, warmup_week=2)
    logger.log("session_start", duration_target_min=15)
    logger.log("video_watch", video_id="...", niche_match=True)
    logger.log("like", creator_handle="@xxx")
    logger.flush()  # call at session end (also auto-flushes on buffer full)
"""

import os
import sys
import json
import uuid
import threading
from urllib import request as _urlreq
from urllib import error as _urlerr

_BATCH_SIZE = 25
_FLUSH_TIMEOUT_S = 8


def _load_env():
    """Read SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env.cli (walks up from cwd)."""
    cwd = os.getcwd()
    for _ in range(8):
        env_path = os.path.join(cwd, ".env.cli")
        if os.path.exists(env_path):
            url, key = None, None
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SUPABASE_URL="):
                        url = line.split("=", 1)[1].strip()
                    elif line.startswith("SUPABASE_SERVICE_ROLE_KEY="):
                        key = line.split("=", 1)[1].strip()
            return url, key
        parent = os.path.dirname(cwd)
        if parent == cwd:
            break
        cwd = parent
    return None, None


class SupabaseLogger:
    def __init__(self, account_slug, session_id=None, warmup_day=None, warmup_week=None):
        self.account_slug = account_slug
        self.session_id = session_id or str(uuid.uuid4())
        self.warmup_day = warmup_day
        self.warmup_week = warmup_week
        self._buffer = []
        self._lock = threading.Lock()
        self._url, self._key = _load_env()
        self._enabled = bool(self._url and self._key)
        if not self._enabled:
            print("  ⚠ SupabaseLogger disabled — SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing in .env.cli")

    def log(self, action_type, **metadata):
        if not self._enabled:
            return
        row = {
            "account_slug": self.account_slug,
            "session_id": self.session_id,
            "warmup_day": self.warmup_day,
            "warmup_week": self.warmup_week,
            "action_type": action_type,
            "metadata": metadata or {},
        }
        with self._lock:
            self._buffer.append(row)
            should_flush = len(self._buffer) >= _BATCH_SIZE
        if should_flush:
            self.flush()

    def flush(self):
        if not self._enabled:
            return
        with self._lock:
            if not self._buffer:
                return
            batch = self._buffer
            self._buffer = []
        try:
            data = json.dumps(batch).encode("utf-8")
            req = _urlreq.Request(
                f"{self._url}/rest/v1/warmup_actions",
                data=data,
                method="POST",
                headers={
                    "apikey": self._key,
                    "Authorization": f"Bearer {self._key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
            )
            with _urlreq.urlopen(req, timeout=_FLUSH_TIMEOUT_S) as resp:
                if resp.status not in (200, 201, 204):
                    print(f"  ⚠ SupabaseLogger flush bad status: {resp.status}", file=sys.stderr)
        except _urlerr.HTTPError as e:
            print(f"  ⚠ SupabaseLogger HTTPError: {e.code} {e.reason}", file=sys.stderr)
        except Exception as e:
            print(f"  ⚠ SupabaseLogger flush failed (silently): {type(e).__name__}: {e}", file=sys.stderr)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        try:
            self.flush()
        except Exception:
            pass
