#!/usr/bin/env python3
"""
Compare the connected Airtable + Supabase environments against the canonical
schema (canonicalSchema.json). Run as the first step of every executor
invocation. Exits non-zero on drift so downstream tooling refuses to run
until the schema matches.

Usage:
  python3 validate_schema.py                # validate, report, exit code 0/1
  python3 validate_schema.py --apply        # auto-apply additive fixes (new fields/columns)
  python3 validate_schema.py --json         # machine-readable output

Required env vars (from .env.cli):
  AIRTABLE_ACCESS_TOKEN, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY

Discovers the Airtable base via .agents/skills/tiktok-warmup/resolve_airtable_schema.py
(so it works repo-agnostically across Flooently/Blaze/etc).
"""

import argparse, json, os, subprocess, sys, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_PATH = os.path.join(HERE, "canonicalSchema.json")


def _load_env_cli():
    """Walk up from cwd to find .env.cli, return (key, value) dict."""
    cwd = os.getcwd()
    for _ in range(8):
        p = os.path.join(cwd, ".env.cli")
        if os.path.exists(p):
            out = {}
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        out[k.strip()] = v.strip()
            return out
        parent = os.path.dirname(cwd)
        if parent == cwd: break
        cwd = parent
    return {}


def _http(url, headers=None, method="GET", body=None):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    if body is not None:
        req.data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8") or "{}")


def _resolve_airtable_base(env):
    """Use the resolver script to get the right base ID."""
    try:
        out = subprocess.check_output(
            ["python3", os.path.join(HERE, "resolve_airtable_schema.py"), "--print-env"],
            env={**os.environ, **env},
            text=True, timeout=20,
        )
        result = {}
        for line in out.strip().split("\n"):
            line = line.strip()
            if line.startswith("export "): line = line[7:]
            if "=" in line:
                k, v = line.split("=", 1)
                result[k] = v.strip().strip('"').strip("'")
        return result.get("AIRTABLE_BASE_ID")
    except Exception as e:
        print(f"  ⚠ Could not resolve Airtable base: {e}", file=sys.stderr)
        return None


def validate_airtable(canonical, env, apply_fixes=False):
    drift = []
    token = env.get("AIRTABLE_ACCESS_TOKEN")
    if not token:
        return [{"severity": "error", "msg": "AIRTABLE_ACCESS_TOKEN missing in .env.cli"}]
    base_id = _resolve_airtable_base(env)
    if not base_id:
        return [{"severity": "error", "msg": "Could not resolve Airtable base ID"}]

    status, data = _http(
        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables",
        headers={"Authorization": f"Bearer {token}"},
    )
    if status != 200:
        return [{"severity": "error", "msg": f"Airtable Meta API HTTP {status}: {data}"}]

    actual_tables = {t["name"]: t for t in data.get("tables", [])}
    canonical_tables = canonical.get("airtable", {}).get("tables", {})

    for table_name, table_def in canonical_tables.items():
        if table_name not in actual_tables:
            drift.append({"severity": "error", "kind": "missing_table", "table": table_name,
                          "fix": f"Create table '{table_name}' in Airtable base {base_id}"})
            continue
        actual_table = actual_tables[table_name]
        actual_fields = {f["name"]: f for f in actual_table["fields"]}
        canonical_fields = {f["name"]: f for f in table_def["fields"]}

        for fname, fdef in canonical_fields.items():
            if fname not in actual_fields:
                fix = (f"Add field '{fname}' (type: {fdef['type']}) to table '{table_name}' in Airtable. "
                       f"Or rerun with --apply.")
                drift.append({"severity": "error", "kind": "missing_field",
                              "table": table_name, "field": fname, "type": fdef["type"], "fix": fix})
                if apply_fixes:
                    body = {"name": fname, "type": fdef["type"]}
                    if "options" in fdef and fdef["type"] == "singleSelect":
                        body["options"] = {"choices": [{"name": c} for c in fdef["options"]["choices"]]}
                    s, r = _http(
                        f"https://api.airtable.com/v0/meta/bases/{base_id}/tables/{actual_table['id']}/fields",
                        headers={"Authorization": f"Bearer {token}"}, method="POST", body=body,
                    )
                    drift[-1]["applied"] = (s == 200)
            else:
                actual = actual_fields[fname]
                if actual["type"] != fdef["type"]:
                    drift.append({"severity": "warn", "kind": "type_mismatch",
                                  "table": table_name, "field": fname,
                                  "actual": actual["type"], "expected": fdef["type"],
                                  "fix": "Fix type manually in the Airtable UI (destructive — auto-apply not supported)"})

        # Extra fields are info-only — don't block runs, but surface so we can clean them up
        extras = set(actual_fields) - set(canonical_fields)
        for x in extras:
            drift.append({"severity": "info", "kind": "extra_field", "table": table_name, "field": x,
                          "fix": "Field exists in Airtable but not in canonical schema. "
                                 "Either add to canonicalSchema.json or remove from Airtable."})
    return drift


def validate_supabase(canonical, env):
    drift = []
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not (url and key):
        return [{"severity": "error", "msg": "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing in .env.cli"}]

    status, data = _http(
        f"{url}/rest/v1/", headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    if status != 200:
        return [{"severity": "error", "msg": f"Supabase introspection HTTP {status}: {data}"}]

    defs = data.get("definitions", {})
    canonical_tables = canonical.get("supabase", {}).get("tables", {})
    for tname, tdef in canonical_tables.items():
        if tname not in defs:
            drift.append({"severity": "error", "kind": "missing_table", "table": tname,
                          "fix": f"Create table '{tname}' in Supabase. See canonicalSchema.json for DDL."})
            continue
        actual_props = defs[tname].get("properties", {})
        for col in tdef["columns"]:
            cname = col["name"]
            if cname not in actual_props:
                drift.append({"severity": "error", "kind": "missing_column",
                              "table": tname, "column": cname, "type": col["type"],
                              "fix": f"Run in Supabase SQL editor: alter table {tname} add column {cname} {col['type']};"})
    return drift


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Auto-apply additive Airtable fixes (new fields).")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output.")
    args = p.parse_args()

    if not os.path.exists(SCHEMA_PATH):
        print(f"❌ canonicalSchema.json not found at {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(2)
    canonical = json.load(open(SCHEMA_PATH))
    env = _load_env_cli()

    airtable_drift = validate_airtable(canonical, env, apply_fixes=args.apply)
    supabase_drift = validate_supabase(canonical, env)

    errors = [d for d in airtable_drift + supabase_drift if d.get("severity") == "error"]
    warnings = [d for d in airtable_drift + supabase_drift if d.get("severity") == "warn"]

    if args.json:
        print(json.dumps({"airtable": airtable_drift, "supabase": supabase_drift,
                          "ok": len(errors) == 0}, indent=2))
    else:
        if not airtable_drift and not supabase_drift:
            print("✅ Schema OK — Airtable and Supabase both match canonicalSchema.json")
        else:
            print("─── Airtable ───")
            for d in airtable_drift:
                icon = {"error": "❌", "warn": "⚠️ ", "info": "ℹ️ "}.get(d.get("severity"), "•")
                print(f"  {icon} {d.get('kind','?')}: {d.get('table','?')}.{d.get('field', d.get('column',''))} — {d.get('fix','')}")
            print("─── Supabase ───")
            for d in supabase_drift:
                icon = {"error": "❌", "warn": "⚠️ ", "info": "ℹ️ "}.get(d.get("severity"), "•")
                print(f"  {icon} {d.get('kind','?')}: {d.get('table','?')}.{d.get('column','')} — {d.get('fix','')}")
            if errors:
                print(f"\n❌ {len(errors)} error(s) — fix before running warmups.")
                sys.exit(1)
            if warnings:
                print(f"\n⚠️  {len(warnings)} warning(s) — review when convenient.")

if __name__ == "__main__":
    main()
