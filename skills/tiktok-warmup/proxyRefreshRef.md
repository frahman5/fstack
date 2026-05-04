# Proxy Refresh Protocol

Automated proxy rotation for Multilogin browser profiles. Called by the executor
when `PROXY_REFRESH_NEEDED` is raised, or as a standalone operation.

## Ban risk lens — read before every refresh decision

**Changing a profile's IP is a TikTok trust signal. Every refresh is a risk event.**

Only refresh when you have a concrete reason (proxy failure, dead IP). Never refresh
preemptively, never rotate mid-session. The decision tree:

```
Proxy error on profile start?
  ├── YES, and ≥3 accounts failing simultaneously → provider outage.
  │     Do NOT rotate any of them. Alert Faiyam via Telegram. Wait 30–60 min.
  │
  └── YES, single account → rotate once, same country, sticky IP.
        If it fails again after one rotation → mark failed, move on.
```

**Non-refresh cases (do NOT rotate):**
- Profile launched successfully but TikTok returned an error → not a proxy issue
- Session was running fine, hit a CAPTCHA → not a proxy issue
- Login lockout (`Maximum number of attempts reached`) → pause 24h, don't rotate
- You're mid-session or the profile is currently running → stop session first, then decide

**Safe rotation conditions:**
- Profile is NOT running (stopped before rotation)
- Same country as the account's original proxy (never change geo)
- Sticky session type, IPTTL = 86400 (maximum stability after the rotation)
- At least 5 minutes of inactivity before the next session launch

---

## API: Generate Proxy

**Match the protocol to the existing profile.** All Flooently profiles use `socks5` (port 1080). If you generate `http` (port 8080) for a profile configured as `socks5`, the update will mismatch. `refresh_proxy.py` auto-detects the existing protocol via `POST /profile/search` before generating.

```
POST https://profile-proxy.multilogin.com/v1/proxy/connection_url
Authorization: Bearer <MLX_AUTOMATION_TOKEN>
Content-Type: application/json

{
  "country": "<2-letter ISO code>",   // e.g. "br", "it", "cr", "fr", "us"
  "sessionType": "sticky",
  "protocol": "socks5",              // or "http" — must match existing profile config
  "IPTTL": 86400,
  "count": 1
}
```

Response (201) — `data` is a **list** even when `count=1`:
```json
{
  "status": 200,
  "data": ["gate.multilogin.com:1080:<username>:<password>"]
}
```

Parse: `proxy_str = data[0]`, then `host, port, username, password = proxy_str.split(":")`.
Port is `1080` for socks5, `8080` for http.

---

## API: Update Profile Proxy

**Endpoint:** `POST https://api.multilogin.com/profile/update` (NOT `/profile/{uuid}` — that 501s on all methods)

**Key discovery:** The update API requires the full `parameters` block — you cannot update proxy alone. Use `fingerprint: {}` to preserve the existing fingerprint, and `startup_behavior: "recover"` (not "default" or "custom").

**Match the existing proxy protocol:** fetch the current profile config first via `POST /profile/search` to detect whether it uses `socks5` (port 1080) or `http` (port 8080). Generate the new proxy with the matching protocol. All Flooently profiles currently use `socks5`.

```
POST https://api.multilogin.com/profile/update
Authorization: Bearer <MLX_AUTOMATION_TOKEN>
Content-Type: application/json

{
  "profile_id": "<uuid>",
  "name": "<profile name from search>",
  "parameters": {
    "storage": {"is_local": false, "save_service_worker": true},
    "fingerprint": {},
    "flags": {
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
      "startup_behavior": "recover"
    },
    "proxy": {
      "host": "gate.multilogin.com",
      "type": "socks5",
      "port": 1080,
      "username": "<username from generate step>",
      "password": "<password from generate step>"
    }
  }
}
```

Success response: `{"status": {"error_code": "", "http_code": 200, "message": "Profile successfully updated"}, "data": null}`

Any non-200 should be treated as failure — do not retry the warmup session without a confirmed successful update.

**Note on Generate Proxy response format:** `data` is a list even when `count=1`. Parse as `data[0]` not `data`.

---

## Country codes by account

| Account slug | Country |
|---|---|
| `tiktok,flooently_portuguese1` | `br` |
| `tiktok,flooently_italian` | `it` |
| `tiktok,flooently_spanish` | `cr` |
| `tiktok,flooently_french` | `fr` |
| `tiktok,blazemoney_agents` | `us` |
| `tiktok,blazemoney_latam` | `mx` |
| `tiktok,lucia_gonzalez` | `uy` |
| `tiktok,andres_morales` | `ec` |
| `tiktok,isabella_restrepo` | `co` |
| `tiktok,diego_herrera` | `mx` |

---

## Standalone script

Run the refresh without starting a warmup session:

```bash
python3 .agents/skills/tiktok-warmup/refresh_proxy.py --account tiktok,flooently_portuguese1
```

Flags:
- `--account <slug>` — required. Uses the country table above.
- `--verify` — after refresh, starts the profile briefly, navigates to ipinfo.io, prints
  the current IP and country, then stops the profile. Confirms the rotation worked.
- `--dry-run` — print what would happen without calling any APIs.

---

## Full automated flow (used by executor)

The executor calls `refresh_proxy_for_account` from `refresh_proxy.py`, or runs the script directly:

```bash
python3 "$SKILL_DIR/refresh_proxy.py" --account <slug>
# exits 0 on success, 1 on failure
```

The function (`refresh_proxy_for_account` in `refresh_proxy.py`) does:
1. Look up country from the `ACCOUNTS` registry by slug or profile_id
2. Call `GET /profile/search` to detect the existing proxy protocol (socks5 vs http)
3. Call Generate Proxy API with matching protocol + `sessionType=sticky` + `IPTTL=86400`
4. Parse `data[0]` from the response list → `host:port:username:password`
5. Call `POST /profile/update` with full parameters block (storage + fingerprint={} + standard flags + new proxy)
6. Return `True` on 200, `False` otherwise

---

## Failure handling

| Failure | Action |
|---|---|
| Generate Proxy returns non-201 | Log error, return False — don't update the profile with bad creds |
| Profile update returns non-2xx | Log error, return False — proxy not changed, report to executor |
| Second consecutive proxy failure on same account | Mark session failed, do not retry again today. Tell Faiyam. |
| ≥3 accounts failing simultaneously | Outage mode — skip rotation for all, Telegram escalation |
