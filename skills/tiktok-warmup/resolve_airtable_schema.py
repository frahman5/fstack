#!/usr/bin/env python3
"""Resolve the TikTok warmup Airtable base for the current repo.

Auto-discovers the base by schema matching. If multiple bases match, disambiguates
by brand (infers brand from cwd: blaze-platform → Blaze, Flooently → Flooently).

Caches the result at scripts/warmup/airtable-schema-cache.json so subsequent runs
are zero-latency until the cache is invalidated.

Usage:
  python3 resolve_airtable_schema.py              # ensure cache, print human summary
  python3 resolve_airtable_schema.py --print-env  # emit `export` lines for `eval`
  python3 resolve_airtable_schema.py --refresh    # force re-discovery

Requires $AIRTABLE_ACCESS_TOKEN in the environment. The token needs these scopes:
  - data.records:read
  - workspacesAndBases:read
  - schema.bases:read
and must have access to the workspace/base containing the TikTok warmup tables.
"""

import json
import os
import pathlib
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone


def _repo_root():
    """Find the git repo root so the script works regardless of where it ships."""
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
        )
        return pathlib.Path(out.decode().strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not in a git repo — fall back to user cache dir.
        return pathlib.Path.home() / ".cache" / "tiktok-warmup"


REPO_ROOT = _repo_root()
CACHE_PATH = REPO_ROOT / "scripts" / "warmup" / "airtable-schema-cache.json"

# Schema fingerprint: a base is considered a "TikTok warmup base" if it has
# both of these tables AND each has all listed fields. Kept minimal — just
# enough to uniquely identify a warmup base among unrelated ones. Avoid
# requiring fields that might get renamed (e.g. Username vs TikTok Username).
REQUIRED_SCHEMA = {
    "Accounts": ["Name", "Brand", "Active", "Warmup Start Date"],
    "Session Log": ["Account Name", "Duration (min)", "Timestamp UTC"],
}

# All tables we want to cache IDs for (superset of REQUIRED_SCHEMA — includes
# supporting tables that may or may not exist in a given base).
TABLES_OF_INTEREST = {
    "Accounts",
    "Session Log",
    "Scheduled Sessions",
    "Agent Messages",
    "Manual Warmup Log",
}


def detect_brand():
    cwd_lower = os.getcwd().lower()
    if "blaze-platform" in cwd_lower:
        return "Blaze"
    if "flooently" in cwd_lower:
        return "Flooently"
    return None


def _get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def list_bases(token):
    return _get("https://api.airtable.com/v0/meta/bases", token).get("bases", [])


def get_base_tables(base_id, token):
    return _get(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables", token
    ).get("tables", [])


def schema_matches(tables):
    return not schema_mismatch_reason(tables)


def schema_mismatch_reason(tables):
    """Return a short string describing why the schema doesn't match, or '' if it does."""
    by_name = {t["name"]: t for t in tables}
    for required_table, required_fields in REQUIRED_SCHEMA.items():
        if required_table not in by_name:
            return f"missing table '{required_table}'"
        field_names = {f["name"] for f in by_name[required_table]["fields"]}
        missing = [rf for rf in required_fields if rf not in field_names]
        if missing:
            return f"table '{required_table}' missing field(s): {missing}"
    return ""


def build_table_map(tables):
    result = {}
    for t in tables:
        if t["name"] in TABLES_OF_INTEREST:
            result[t["name"]] = {
                "id": t["id"],
                "fields": {f["name"]: f["id"] for f in t["fields"]},
            }
    return result


def has_brand_rows(base_id, accounts_table_id, brand, token):
    formula = urllib.parse.quote(f'{{Brand}}="{brand}"')
    url = (
        f"https://api.airtable.com/v0/{base_id}/{accounts_table_id}"
        f"?maxRecords=1&filterByFormula={formula}"
    )
    try:
        data = _get(url, token)
        return len(data.get("records", [])) > 0
    except urllib.error.HTTPError:
        return False


def discover(token, brand):
    bases = list_bases(token)
    if not bases:
        raise RuntimeError(
            "Token has no accessible bases. Check the Access section at "
            "https://airtable.com/create/tokens."
        )

    candidates = []
    diagnostics = []  # (base_name, reason) for every non-matching base
    for b in bases:
        try:
            tables = get_base_tables(b["id"], token)
        except urllib.error.HTTPError as e:
            diagnostics.append((b["name"], f"schema fetch failed (HTTP {e.code})"))
            continue
        reason = schema_mismatch_reason(tables)
        if not reason:
            candidates.append({"base": b, "tables": tables})
        else:
            diagnostics.append((b["name"], reason))

    if not candidates:
        diag_lines = "\n  ".join(f"- {name}: {reason}" for name, reason in diagnostics)
        raise RuntimeError(
            f"No base matched the TikTok warmup schema. Per-base reasons:\n  {diag_lines}\n"
            f"Required: Accounts + Session Log tables with fields: "
            f"{REQUIRED_SCHEMA}."
        )

    if len(candidates) == 1:
        return candidates[0]

    # Multiple matches — disambiguate by checking which base has accounts
    # with the current repo's brand.
    brand_matches = []
    for c in candidates:
        accounts_id = next(t["id"] for t in c["tables"] if t["name"] == "Accounts")
        if has_brand_rows(c["base"]["id"], accounts_id, brand, token):
            brand_matches.append(c)

    if len(brand_matches) == 1:
        return brand_matches[0]

    if len(brand_matches) > 1:
        names = [c["base"]["name"] for c in brand_matches]
        raise RuntimeError(
            f"Ambiguous: multiple bases match schema AND have brand '{brand}' rows: {names}"
        )

    # No brand-tagged rows in any candidate — unresolvable automatically.
    names = [c["base"]["name"] for c in candidates]
    raise RuntimeError(
        f"Multiple bases match schema but none have accounts tagged "
        f"Brand='{brand}'. Candidates: {names}. Tag at least one account with "
        f"the brand, or set AIRTABLE_BASE_ID in .env.cli manually."
    )


def write_cache(base_id, base_name, brand, table_map):
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_generated_utc": datetime.now(timezone.utc).isoformat(),
        "base_id": base_id,
        "base_name": base_name,
        "brand": brand,
        "tables": table_map,
    }
    CACHE_PATH.write_text(json.dumps(payload, indent=2))


def load_cache():
    if not CACHE_PATH.exists():
        return None
    try:
        return json.loads(CACHE_PATH.read_text())
    except json.JSONDecodeError:
        return None


def cache_still_valid(cache, token, brand):
    if not cache or cache.get("brand") != brand:
        return False
    try:
        tables = get_base_tables(cache["base_id"], token)
    except urllib.error.HTTPError:
        return False
    return schema_matches(tables)


def print_env(cache):
    print(f"export AIRTABLE_BASE_ID={cache['base_id']}")
    print(f"export AIRTABLE_BRAND={cache['brand']}")
    name_to_envvar = {
        "Accounts": "AIRTABLE_ACCOUNTS_TABLE",
        "Session Log": "AIRTABLE_SESSION_LOG_TABLE",
        "Scheduled Sessions": "AIRTABLE_SCHEDULED_SESSIONS_TABLE",
        "Agent Messages": "AIRTABLE_AGENT_MESSAGES_TABLE",
        "Manual Warmup Log": "AIRTABLE_MANUAL_WARMUP_LOG_TABLE",
    }
    for table_name, envvar in name_to_envvar.items():
        t = cache["tables"].get(table_name)
        if t:
            print(f"export {envvar}={t['id']}")


def main():
    args = sys.argv[1:]
    refresh = "--refresh" in args
    print_env_flag = "--print-env" in args

    token = os.environ.get("AIRTABLE_ACCESS_TOKEN")
    if not token:
        print("ERROR: AIRTABLE_ACCESS_TOKEN not set. source .env.cli first.", file=sys.stderr)
        sys.exit(1)

    brand = detect_brand()
    if brand is None:
        print(
            f"ERROR: cannot determine brand from cwd: {os.getcwd()}",
            file=sys.stderr,
        )
        sys.exit(1)

    cache = None if refresh else load_cache()
    if not cache_still_valid(cache, token, brand):
        print(f"# resolving Airtable base for brand={brand}...", file=sys.stderr)
        try:
            match = discover(token, brand)
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        base = match["base"]
        write_cache(base["id"], base["name"], brand, build_table_map(match["tables"]))
        cache = load_cache()
        print(f"# cached {base['name']} ({base['id']}) for brand={brand}", file=sys.stderr)

    if print_env_flag:
        print_env(cache)
    else:
        print(f"✅ Base: {cache.get('base_name', '?')} ({cache['base_id']})")
        print(f"   Brand: {cache['brand']}")
        print(f"   Tables cached: {', '.join(cache['tables'].keys())}")


if __name__ == "__main__":
    main()
