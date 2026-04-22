#!/usr/bin/env python3
"""
TikTok Warmup Coverage Calculator
===================================
Reads Airtable data from three temp files and outputs a coverage report as JSON.

Usage:
    python3 coverage.py --now "2026-04-14T22:05:14Z" \
        --accounts /tmp/tk_accounts.json \
        --log /tmp/tk_session_log.json \
        --scheduled /tmp/tk_scheduled.json

Output (stdout): JSON coverage report per account.

The planner (plannerRef.md) is responsible for:
  1. Fetching data via Airtable MCP tools
  2. Writing each result to the expected temp file paths
  3. Running this script
  4. Reading the JSON output to decide which sessions to create
"""

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta


# ── UTC offsets for April 2026 ────────────────────────────────────────────────
# Mexico City → CDT (UTC-5) after first Sunday in April (Apr 5, 2026)
# Chile/Santiago → standard/winter (UTC-4) after DST ends first Sunday in April
# All others → no DST, fixed offset
UTC_OFFSETS = {
    "America/Bogota":                    -5,
    "America/Lima":                      -5,
    "America/Guayaquil":                 -5,
    "America/Mexico_City":               -5,   # CDT in April
    "America/Costa_Rica":                -6,
    "America/Montevideo":                -3,
    "America/Argentina/Buenos_Aires":    -3,
    "America/Santiago":                  -4,   # winter (standard) in April
}

COUNTRY_FALLBACK = {
    "Mexico":      -5,
    "Colombia":    -5,
    "Argentina":   -3,
    "Venezuela":   -4,
    "Peru":        -5,
    "Chile":       -4,
    "Ecuador":     -5,
    "Uruguay":     -3,
    "Costa Rica":  -6,
}


def get_offset(account_row: dict) -> int:
    """Return integer UTC offset for an account, with fallback to country."""
    tz = account_row.get("timezone", "")
    if tz in UTC_OFFSETS:
        return UTC_OFFSETS[tz]
    # Parse numeric string like "-5" or "-3"
    raw = account_row.get("utc_offset", "")
    if raw:
        try:
            return int(str(raw).split()[0].split("(")[0])
        except (ValueError, IndexError):
            pass
    country = account_row.get("country", "")
    return COUNTRY_FALLBACK.get(country, -5)


def local_date(utc_ts: str, offset_hours: int) -> str:
    """Convert a UTC ISO timestamp to a local date string (YYYY-MM-DD)."""
    dt = datetime.fromisoformat(utc_ts.replace("Z", "+00:00"))
    local = dt + timedelta(hours=offset_hours)
    return local.date().isoformat()


def parse_accounts(data: dict) -> list[dict]:
    """Extract active accounts from Airtable list_records_for_table response."""
    accounts = []
    for rec in data.get("records", []):
        f = rec.get("cellValuesByFieldId", {})
        active = f.get("fldTRC4UyWNTwi7VP", False)
        if not active:
            continue
        accounts.append({
            "name":       f.get("fldmrNwWerD8PM5qh", ""),
            "country":    f.get("fldwz3PYTWl0j8uH0", ""),
            "timezone":   f.get("fldczl7hFNqxhRgCo", ""),
            "utc_offset": f.get("fldPEQveQPPM93uu6", ""),
        })
    return accounts


def parse_session_log(data: dict) -> list[dict]:
    """Extract relevant fields from Session Log records."""
    rows = []
    for rec in data.get("records", []):
        f = rec.get("cellValuesByFieldId", {})
        ts = f.get("fldGckcL5Qc5vcug9", "")
        if not ts:
            continue
        rows.append({
            "account": f.get("fldlUusi4GgT4n3oS", ""),
            "ts_utc":  ts,
            "error":   f.get("fldWHqaARjy1nsg4E", ""),
        })
    return rows


def parse_scheduled(data: dict, now_utc: datetime) -> list[dict]:
    """Extract future scheduled sessions (status=scheduled or needs-retry, planned_time > now)."""
    rows = []
    for rec in data.get("records", []):
        f = rec.get("cellValuesByFieldId", {})
        status = f.get("fldwv7pim7ejWJmAt", {})
        if isinstance(status, dict):
            status = status.get("name", "")
        if status not in ("scheduled", "needs-retry"):
            continue
        planned = f.get("fldvlgjfBLRpc2aup", "")
        if not planned:
            continue
        planned_dt = datetime.fromisoformat(planned.replace("Z", "+00:00"))
        if planned_dt <= now_utc:
            continue
        rows.append({
            "account":    f.get("fldw78znLH2oRJWYT", ""),
            "planned_utc": planned,
        })
    return rows


def calculate_coverage(accounts, session_log, scheduled, now_utc: datetime) -> list[dict]:
    """
    For each active account return:
      - successful_days: list of local dates with at least one successful session
      - failed_days: list of local dates with ONLY failed sessions
      - future_scheduled_days: list of distinct local dates with a future scheduled session
      - total_coverage: len(successful_days) + len(future_scheduled_days)
      - days_needed: max(0, 7 - total_coverage)
      - local_now: current local datetime (ISO string)
      - offset: integer UTC offset
    """
    report = []

    for acct in accounts:
        name = acct["name"]
        offset = get_offset(acct)

        # Session log: group by local date, track whether any success exists
        date_has_success: dict[str, bool] = {}
        for row in session_log:
            if row["account"] != name:
                continue
            ld = local_date(row["ts_utc"], offset)
            has_error = bool(row.get("error", ""))
            if not has_error:
                date_has_success[ld] = True
            elif ld not in date_has_success:
                date_has_success[ld] = False

        successful_days = sorted(d for d, ok in date_has_success.items() if ok)
        failed_days     = sorted(d for d, ok in date_has_success.items() if not ok)

        # Future scheduled sessions
        future_dates: set[str] = set()
        for row in scheduled:
            if row["account"] != name:
                continue
            future_dates.add(local_date(row["planned_utc"], offset))
        future_scheduled_days = sorted(future_dates)

        total_coverage = len(successful_days) + len(future_scheduled_days)
        days_needed    = max(0, 7 - total_coverage)

        local_now = now_utc + timedelta(hours=offset)

        report.append({
            "account":               name,
            "country":               acct["country"],
            "offset":                offset,
            "local_now":             local_now.isoformat(),
            "local_hour":            local_now.hour,
            "successful_days":       successful_days,
            "failed_days":           failed_days,
            "future_scheduled_days": future_scheduled_days,
            "total_coverage":        total_coverage,
            "days_needed":           days_needed,
            "needs_sessions":        days_needed > 0,
        })

    return report


def main():
    parser = argparse.ArgumentParser(description="TikTok Warmup Coverage Calculator")
    parser.add_argument("--now",       required=True, help="Current UTC time ISO string")
    parser.add_argument("--accounts",  required=True, help="Path to accounts JSON file")
    parser.add_argument("--log",       required=True, help="Path to session log JSON file")
    parser.add_argument("--scheduled", required=True, help="Path to scheduled sessions JSON file")
    args = parser.parse_args()

    now_utc = datetime.fromisoformat(args.now.replace("Z", "+00:00"))

    with open(args.accounts)  as f: accounts_data  = json.load(f)
    with open(args.log)       as f: log_data        = json.load(f)
    with open(args.scheduled) as f: scheduled_data  = json.load(f)

    accounts  = parse_accounts(accounts_data)
    log       = parse_session_log(log_data)
    scheduled = parse_scheduled(scheduled_data, now_utc)

    report = calculate_coverage(accounts, log, scheduled, now_utc)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
