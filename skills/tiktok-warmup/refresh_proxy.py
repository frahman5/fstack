#!/usr/bin/env python3
"""
Refresh the Multilogin proxy for a TikTok warmup account.

Usage:
    python3 refresh_proxy.py --account tiktok,flooently_portuguese1
    python3 refresh_proxy.py --account tiktok,flooently_portuguese1 --verify
    python3 refresh_proxy.py --account tiktok,flooently_portuguese1 --dry-run

See proxyRefreshRef.md for the full protocol and ban risk considerations.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Env loading — walk upward from this file to find .env.cli
# ---------------------------------------------------------------------------

def _load_env():
    here = Path(__file__).resolve().parent
    for candidate in [here, *here.parents]:
        env_file = candidate / ".env.cli"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())
            return

_load_env()

MLX_TOKEN = os.environ.get("MULTILOGIN_API_KEY") or os.environ.get("MLX_AUTOMATION_TOKEN", "")
MLX_BASE = "https://api.multilogin.com"
PROXY_API = "https://profile-proxy.multilogin.com/v1/proxy/connection_url"
LAUNCHER = "https://launcher.mlx.yt:45001/api/v1"
LAUNCHER_V2 = "https://launcher.mlx.yt:45001/api/v2"

# Standard masking flags — all profiles use these
STANDARD_FLAGS = {
    "audio_masking": "mask",
    "fonts_masking": "mask",
    "geolocation_masking": "mask",
    "geolocation_popup": "prompt",
    "graphics_masking": "mask",
    "graphics_noise": "natural",
    "localization_masking": "mask",
    "media_devices_masking": "mask",
    "navigator_masking": "mask",
    "ports_masking": "mask",
    "proxy_masking": "custom",
    "screen_masking": "mask",
    "timezone_masking": "mask",
    "webrtc_masking": "natural",
    "canvas_noise": "natural",
    "startup_behavior": "recover",  # 'custom' requires custom_start_urls; 'recover' is safe for updates
}

# ---------------------------------------------------------------------------
# Account registry (slug → profile_id, folder_id, country, proxy protocol)
# ---------------------------------------------------------------------------

FLOOENTLY_FOLDER = "1c5615aa-fae3-4184-a2a3-37226bd48b38"
BLAZE_FOLDER = "db07d2e1-4d3c-44fa-8a7f-7cc406410181"

ACCOUNTS = {
    "tiktok,flooently_portuguese1": {
        "profile_id": "0163b253-bbce-416c-83e5-e9f29f569dfe",
        "folder_id": FLOOENTLY_FOLDER,
        "country": "br",
        "name": "flooently_portuguese1 (TikTok)",
    },
    "tiktok,flooently_italian": {
        "profile_id": "aed6f242-f7e1-46f2-9a97-7ac1e578fe3e",
        "folder_id": FLOOENTLY_FOLDER,
        "country": "it",
        "name": "flooently_italian (TikTok)",
    },
    "tiktok,flooently_spanish": {
        "profile_id": "5c69580d-d860-43cc-bb46-7fa96a3ffa50",
        "folder_id": FLOOENTLY_FOLDER,
        "country": "cr",
        "name": "flooently_spanish (TikTok)",
    },
    "tiktok,flooently_french": {
        "profile_id": "24a5332c-dc93-4bb8-bec8-6d48afc2362e",
        "folder_id": FLOOENTLY_FOLDER,
        "country": "fr",
        "name": "flooently_french (TikTok)",
    },
    "tiktok,blazemoney_agents": {
        "profile_id": "91eea3ec-40bd-4022-b5ee-a7b46fd0fb8c",
        "folder_id": BLAZE_FOLDER,
        "country": "us",
        "name": "blazemoney_agents (TikTok)",
    },
    "tiktok,blazemoney_latam": {
        "profile_id": "c94312b1-afd4-42fa-9041-15e547fda62a",
        "folder_id": BLAZE_FOLDER,
        "country": "mx",
        "name": "blazemoney_latam (TikTok)",
    },
    "tiktok,lucia_gonzalez": {
        "profile_id": "827e8057-d3be-47b9-831a-5be49a86ef12",
        "folder_id": FLOOENTLY_FOLDER,
        "country": "uy",
        "name": "lucia_gonzalez (TikTok)",
    },
    "tiktok,andres_morales": {
        "profile_id": "6ffeda6b-b371-446c-93cc-7d915882e19e",
        "folder_id": FLOOENTLY_FOLDER,
        "country": "ec",
        "name": "andres_morales (TikTok)",
    },
    "tiktok,isabella_restrepo": {
        "profile_id": "5aef5a09-dde8-496a-9b78-5bc51d58aea5",
        "folder_id": FLOOENTLY_FOLDER,
        "country": "co",
        "name": "isabella_restrepo (TikTok)",
    },
    "tiktok,diego_herrera": {
        "profile_id": "9516da5c-701c-4a8d-9d21-6bb2d0b923dd",
        "folder_id": FLOOENTLY_FOLDER,
        "country": "mx",
        "name": "diego_herrera (TikTok)",
    },
}

# ---------------------------------------------------------------------------
# Core API calls
# ---------------------------------------------------------------------------

def _headers():
    return {
        "Authorization": f"Bearer {MLX_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_current_proxy(profile_id: str) -> dict | None:
    """Fetch the profile's current proxy config from the search API.
    Returns the proxy dict {host, port, type, username, password} or None.
    """
    try:
        resp = requests.post(
            f"{MLX_BASE}/profile/search",
            headers=_headers(),
            json={"search_text": profile_id, "is_removed": False, "limit": 1, "offset": 0},
            timeout=20,
        )
        if resp.status_code == 200:
            profiles = resp.json().get("data", {}).get("profiles") or []
            if profiles:
                return profiles[0].get("proxy")
    except Exception as e:
        print(f"  [get_current_proxy] failed: {e}")
    return None


def generate_proxy(country: str, protocol: str = "socks5", dry_run: bool = False) -> str | None:
    """Generate a new sticky residential proxy for the given country.
    Returns 'host:port:username:password' or None on failure.
    """
    payload = {
        "country": country,
        "sessionType": "sticky",
        "protocol": protocol,
        "IPTTL": 86400,
        "count": 1,
    }
    print(f"  [generate_proxy] requesting {protocol} proxy for country={country}")

    if dry_run:
        fake = f"gate.multilogin.com:{'1080' if protocol=='socks5' else '8080'}:dry_run_user:dry_run_pass"
        print(f"  [generate_proxy] DRY RUN → {fake}")
        return fake

    try:
        resp = requests.post(PROXY_API, headers=_headers(), json=payload, timeout=30)
    except Exception as e:
        print(f"  [generate_proxy] request error: {e}")
        return None

    print(f"  [generate_proxy] status={resp.status_code}")
    if resp.status_code not in (200, 201):
        print(f"  [generate_proxy] FAILED: {resp.text[:200]}")
        return None

    try:
        raw = resp.json().get("data", "")
        data = raw[0] if isinstance(raw, list) else raw
    except Exception:
        data = resp.text.strip().strip('"')

    if not data or data.count(":") < 3:
        print(f"  [generate_proxy] unexpected format: {data!r}")
        return None

    print(f"  [generate_proxy] ✅ new proxy: {data[:60]}...")
    return data


def update_profile_proxy(
    profile_id: str,
    profile_name: str,
    host: str,
    port: int,
    proxy_type: str,
    username: str,
    password: str,
    dry_run: bool = False,
) -> bool:
    """Update the Multilogin profile's proxy. Returns True on success.

    Endpoint: POST /profile/update
    Requires: profile_id, name, parameters.{storage, fingerprint, flags, proxy}
    fingerprint={} → keeps existing fingerprint (server fills it in)
    """
    payload = {
        "profile_id": profile_id,
        "name": profile_name,
        "parameters": {
            "storage": {"is_local": False, "save_service_worker": True},
            "fingerprint": {},
            "flags": STANDARD_FLAGS,
            "proxy": {
                "host": host,
                "type": proxy_type,
                "port": port,
                "username": username,
                "password": password,
            },
        },
    }
    print(f"  [update_profile] POST /profile/update — new {proxy_type}://{host}:{port}")

    if dry_run:
        print("  [update_profile] DRY RUN — skipping")
        return True

    try:
        resp = requests.post(
            f"{MLX_BASE}/profile/update",
            headers=_headers(),
            json=payload,
            timeout=30,
        )
    except Exception as e:
        print(f"  [update_profile] request error: {e}")
        return False

    print(f"  [update_profile] status={resp.status_code} body={resp.text[:200]}")
    if resp.status_code == 200:
        print("  [update_profile] ✅ proxy updated")
        return True

    print("  [update_profile] ❌ update failed")
    return False


def verify_proxy(profile_id: str, folder_id: str) -> None:
    """Start the profile briefly, check ipinfo.io to confirm the new IP, then stop."""
    print("\n  [verify] Starting profile to check new IP...")
    start_url = (
        f"{LAUNCHER_V2}/profile/f/{folder_id}/p/{profile_id}/start"
        "?automation_type=playwright&headless_mode=true"
    )
    try:
        resp = requests.get(start_url, headers=_headers(), verify=False, timeout=30)
    except Exception as e:
        print(f"  [verify] start request failed: {e}")
        return

    if resp.status_code != 200:
        print(f"  [verify] profile start failed: {resp.status_code} {resp.text[:200]}")
        return

    port = resp.json()["data"]["port"]
    print(f"  [verify] profile started on port {port}")

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            ctx = browser.contexts[0]
            page = ctx.new_page()
            page.goto("https://ipinfo.io/json", timeout=20000)
            body = page.text_content("body") or ""
            print(f"\n  [verify] IP info:\n{body}\n")
            page.close()
    except Exception as e:
        print(f"  [verify] playwright check failed: {e}")
    finally:
        stop_url = f"{LAUNCHER}/profile/stop/p/{profile_id}"
        requests.get(stop_url, headers=_headers(), verify=False, timeout=15)
        print("  [verify] profile stopped")


# ---------------------------------------------------------------------------
# Main refresh function (importable by tiktok-warmup-poc.py)
# ---------------------------------------------------------------------------

def refresh_proxy_for_account(slug: str, profile_id: str, folder_id: str, dry_run: bool = False) -> bool:
    """
    Refresh the Multilogin proxy for one account.
    Profile MUST be stopped before calling this.
    Returns True if successful, False otherwise.
    """
    account = ACCOUNTS.get(slug) or next(
        (a for a in ACCOUNTS.values() if a["profile_id"] == profile_id), None
    )
    if not account:
        print(f"  [refresh_proxy] no country mapping for {slug} — cannot rotate safely")
        return False

    country = account["country"]
    profile_name = account["name"]
    print(f"\n🔄 Refreshing proxy for {slug} (country={country})...")

    # Detect current proxy protocol from the live profile config
    current_proxy = get_current_proxy(profile_id) if not dry_run else None
    proxy_type = (current_proxy or {}).get("type", "socks5")
    print(f"  [refresh_proxy] current proxy type={proxy_type}")

    proxy_str = generate_proxy(country, protocol=proxy_type, dry_run=dry_run)
    if not proxy_str:
        print("  [refresh_proxy] ❌ proxy generation failed")
        return False

    parts = proxy_str.split(":")
    if len(parts) != 4:
        print(f"  [refresh_proxy] ❌ unexpected proxy format: {proxy_str!r}")
        return False

    host, port_str, username, password = parts
    try:
        port = int(port_str)
    except ValueError:
        print(f"  [refresh_proxy] ❌ non-integer port: {port_str!r}")
        return False

    success = update_profile_proxy(
        profile_id=profile_id,
        profile_name=profile_name,
        host=host,
        port=port,
        proxy_type=proxy_type,
        username=username,
        password=password,
        dry_run=dry_run,
    )
    if success:
        print(f"  [refresh_proxy] ✅ proxy rotated for {slug}")
    return success


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Refresh Multilogin proxy for a TikTok warmup account")
    parser.add_argument("--account", required=True, help="Account slug, e.g. tiktok,flooently_portuguese1")
    parser.add_argument("--verify", action="store_true", help="After refresh, start profile to confirm new IP via ipinfo.io")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without calling any write APIs")
    args = parser.parse_args()

    if not MLX_TOKEN:
        print("ERROR: MULTILOGIN_API_KEY (or MLX_AUTOMATION_TOKEN) not set. Check .env.cli")
        sys.exit(1)

    account = ACCOUNTS.get(args.account)
    if not account:
        print(f"ERROR: unknown account '{args.account}'. Known accounts:")
        for slug in ACCOUNTS:
            print(f"  {slug}")
        sys.exit(1)

    profile_id = account["profile_id"]
    folder_id = account["folder_id"]

    success = refresh_proxy_for_account(
        slug=args.account,
        profile_id=profile_id,
        folder_id=folder_id,
        dry_run=args.dry_run,
    )

    if success and args.verify and not args.dry_run:
        print("\n⏳ Waiting 5s for proxy to propagate before verification...")
        time.sleep(5)
        verify_proxy(profile_id, folder_id)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
