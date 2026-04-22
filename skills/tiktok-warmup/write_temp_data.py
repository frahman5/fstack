#!/usr/bin/env python3
"""
Helper: read JSON from stdin, write to the file path given as first argument.

Usage:
    python3 write_temp_data.py /tmp/tk_accounts.json << 'JSON'
    {"records": [...]}
    JSON

This is used by the planner to dump Airtable MCP responses to temp files
so that coverage.py can read them. Never use the Write MCP tool for this —
it requires a prior Read and silently fails on new files.
"""
import json
import sys

if len(sys.argv) < 2:
    print("Usage: write_temp_data.py <output_path>", file=sys.stderr)
    sys.exit(1)

path = sys.argv[1]
data = json.load(sys.stdin)
with open(path, "w") as f:
    json.dump(data, f)
print(f"wrote {path}")
