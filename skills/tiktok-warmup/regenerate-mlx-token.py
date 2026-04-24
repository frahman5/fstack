"""Regenerate the Multilogin no-expiry automation token.
Pulls password from 1Password (Claude-Accessible vault), signs in, switches to
Flooently workspace, generates no_exp automation token, writes to .env.cli.
"""
import os, sys, json, re, subprocess, hashlib, urllib3, requests
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ENV_FILE = os.environ.get("ENV_FILE", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.cli"))
WORKSPACE_ID = "76207486-0efb-4220-ad4f-c877333b1859"
# Email is pulled from the 1Password "Multilogin" item's username field — do not
# hardcode here (the account owner of the Flooently workspace is currently
# faiyam@flooently.com, but this can change).


def load_env():
    for line in open(ENV_FILE):
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def op_get(item, vault, field):
    r = subprocess.run(
        ["op", "item", "get", item, "--vault", vault, "--fields", field, "--reveal"],
        capture_output=True, text=True, timeout=20,
    )
    if r.returncode != 0:
        raise SystemExit(f"op failed: {r.stderr}")
    return r.stdout.strip()


def main():
    load_env()
    # Pull both username and password in one call (fewer op invocations)
    creds = op_get("Multilogin", "TikTok", "username,password")
    email, password = creds.split(",", 1)
    email = email.strip()
    password = password.strip()
    md5 = hashlib.md5(password.encode()).hexdigest()

    # Step 1
    r = requests.post("https://api.multilogin.com/user/signin",
                      json={"email": email, "password": md5},
                      headers={"Accept": "application/json"}, timeout=30)
    d = r.json()
    if "data" not in d:
        raise SystemExit(f"signin failed: {r.text}")
    initial, refresh = d["data"]["token"], d["data"]["refresh_token"]

    # Step 2
    r = requests.post("https://api.multilogin.com/user/refresh_token",
                      headers={"Authorization": f"Bearer {initial}", "Accept": "application/json"},
                      json={"email": email, "refresh_token": refresh, "workspace_id": WORKSPACE_ID},
                      timeout=30)
    d = r.json()
    if "data" not in d:
        raise SystemExit(f"workspace refresh failed: {r.text}")
    ws_token = d["data"]["token"]

    # Step 3
    r = requests.get("https://api.multilogin.com/workspace/automation_token",
                     params={"expiration_period": "no_exp"},
                     headers={"Authorization": f"Bearer {ws_token}", "Accept": "application/json"},
                     timeout=30)
    d = r.json()
    if "data" not in d:
        raise SystemExit(f"automation_token generation failed: {r.text}")
    new_token = d["data"]["token"]
    print(f"Got no_exp token (length {len(new_token)})")

    # Write to .env.cli
    with open(ENV_FILE) as f:
        content = f.read()
    if re.search(r"^MULTILOGIN_API_KEY=", content, flags=re.M):
        content = re.sub(r"^MULTILOGIN_API_KEY=.*$", f"MULTILOGIN_API_KEY={new_token}", content, count=1, flags=re.M)
    else:
        content = content.rstrip() + f"\nMULTILOGIN_API_KEY={new_token}\n"
    with open(ENV_FILE, "w") as f:
        f.write(content)
    print("Wrote MULTILOGIN_API_KEY to .env.cli")


if __name__ == "__main__":
    main()
