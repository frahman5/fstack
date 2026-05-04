# Supabase Reference — Warmup Action Logging

## Schema

Create this table in your Supabase project (SQL editor or Table editor):

```sql
create table warmup_actions (
  id            bigserial primary key,
  session_id    text not null,
  account_slug  text not null,
  action_type   text not null,
  timestamp     timestamptz not null default now(),
  warmup_day    int,
  warmup_week   int,
  metadata      jsonb default '{}'::jsonb
);

create index on warmup_actions (account_slug, timestamp desc);
create index on warmup_actions (session_id);
```

## action_type values

| value | when logged | metadata fields |
|-------|-------------|-----------------|
| `session_start` | warmup session begins | `{}` |
| `session_end` | warmup session completes | `duration_min`, `videos_watched`, `likes` |
| `video_watch` | each video viewed | `niche_match` (bool), `source` (`fyp`\|`search`) |

## Niche match logic

- `source = "search"` → always `niche_match: true` (search results are by definition on-topic)
- `source = "fyp"` → `niche_match: true` only if hashtag or caption contains a target keyword for the account's niche (scraped from the DOM during warmup)

## account_slug format

`"platform,account_handle"` — e.g. `"tiktok,flooently_spanish"`. This namespaces accounts so one Supabase table can hold data for multiple platforms/businesses.

## Python logger

Copy `supabase_logger.py` into your repo (e.g. `scripts/warmup/supabase_logger.py`):

```python
import os
import uuid
from datetime import datetime, timezone
from supabase import create_client

class SupabaseLogger:
    def __init__(self):
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.client = create_client(url, key)
        self._buffer = []

    def log(self, session_id: str, account_slug: str, action_type: str,
            warmup_day: int | None = None, warmup_week: int | None = None,
            metadata: dict | None = None):
        self._buffer.append({
            "session_id": session_id,
            "account_slug": account_slug,
            "action_type": action_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warmup_day": warmup_day,
            "warmup_week": warmup_week,
            "metadata": metadata or {},
        })

    def flush(self):
        if not self._buffer:
            return
        self.client.table("warmup_actions").insert(self._buffer).execute()
        self._buffer = []

    def new_session_id(self) -> str:
        return str(uuid.uuid4())
```

Usage in a warmup script:

```python
logger = SupabaseLogger()
sid = logger.new_session_id()

logger.log(sid, "tiktok,my_account", "session_start", warmup_day=3, warmup_week=1)
# ... do warmup ...
logger.log(sid, "tiktok,my_account", "video_watch", metadata={"niche_match": True, "source": "fyp"})
logger.log(sid, "tiktok,my_account", "session_end", metadata={"duration_min": 22.5, "videos_watched": 18, "likes": 2})
logger.flush()
```

## Required env vars

```
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=sb_secret_...
```

Store these in `.env.cli` (or `.env`) and load before running any warmup script. Also add them as Vercel env vars for the dashboard.

## Deps

```bash
pip install supabase
```
