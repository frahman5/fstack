# Cron Job Reference — Remote Claude Agent on Hetzner

## Architecture

```
Hetzner CX33 (Ubuntu)
  └── cron (3x/day)
        └── run-warmups.sh
              └── claude -p --model claude-opus-4-5 ...
                    └── executeWarmupsServerRef.md (the warmup skill)
                          └── Logs to Supabase
                          └── Sends Telegram updates
```

The agent runs headlessly on the server using Multilogin X browser profiles + Xvfb display (:99).

## Server setup (one-time)

### 1. Provision server
Hetzner CX33 (4 vCPU, 8GB RAM) is sufficient for 4-6 accounts in parallel.

```bash
# On the server
apt update && apt upgrade -y
apt install -y python3-pip xvfb x11vnc novnc websockify curl
pip3 install supabase anthropic
```

### 2. Install Claude Code CLI
```bash
npm install -g @anthropic-ai/claude-code
# Authenticate
claude auth login
```

### 3. Start persistent Xvfb display
```bash
# /etc/systemd/system/xvfb.service
[Unit]
Description=Xvfb virtual display
After=network.target

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1920x1080x24
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
systemctl enable xvfb && systemctl start xvfb
```

### 4. Start x11vnc for noVNC access (for manual debugging)
```bash
# /etc/systemd/system/x11vnc.service
[Unit]
Description=x11vnc VNC server
After=xvfb.service

[Service]
ExecStart=/usr/bin/x11vnc -display :99 -forever -shared -rfbport 5900 -nopw -o /var/log/x11vnc.log
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
```bash
systemctl enable x11vnc && systemctl start x11vnc
```

### 5. Start noVNC web proxy
```bash
websockify --web /usr/share/novnc 6080 localhost:5900 &
```

Access at: `http://<server-ip>:6080/vnc.html` — use this to manually handle CAPTCHAs.

## run-warmups.sh

Create at `/root/your-repo/scripts/warmup/run-warmups.sh`:

```bash
#!/bin/bash
set -e

REPO_DIR="/root/your-repo"
LOG_FILE="/var/log/warmup-$(date +%Y%m%d-%H%M%S).log"

cd "$REPO_DIR"
source .env.cli

export DISPLAY=:99

echo "[$(date)] Starting warmup run" | tee -a "$LOG_FILE"

claude -p \
  --model claude-opus-4-5 \
  --max-turns 80 \
  "Load the warmup skill from .claude/skills/tiktok-warmup/SKILL.md and execute the server executor protocol (executeWarmupsServerRef.md)." \
  >> "$LOG_FILE" 2>&1

echo "[$(date)] Warmup run complete" | tee -a "$LOG_FILE"
```

```bash
chmod +x scripts/warmup/run-warmups.sh
```

## Cron schedule

```bash
crontab -e
```

Add (times are UTC):
```cron
0 9  * * * /root/your-repo/scripts/warmup/run-warmups.sh
0 15 * * * /root/your-repo/scripts/warmup/run-warmups.sh
0 21 * * * /root/your-repo/scripts/warmup/run-warmups.sh
```

Three runs/day gives each account 2-3 sessions spread across the day, which mimics natural usage patterns.

## Env vars needed on server

```
# .env.cli on the server
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SLACK_WEBHOOK_URL=           # if using Slack
MLX_AUTOMATION_TOKEN=        # Multilogin X API token
AGENTMAIL_API_KEY=            # for TikTok OTP emails
OP_SERVICE_ACCOUNT_TOKEN=    # 1Password service account
```

## Monitoring

- **Logs**: `/var/log/warmup-*.log` on server
- **Telegram**: agent sends start + end messages each run
- **Dashboard**: see adminDashboardRef.md for the web UI

## Manual intervention (CAPTCHAs, re-logins)

When TikTok shows a CAPTCHA or requires re-login:
1. Open noVNC: `http://<server-ip>:6080/vnc.html`
2. The Multilogin browser will be visible — solve the CAPTCHA manually
3. The agent will continue automatically once the blocker is cleared (it polls and waits up to 60s)

If the agent already escalated via Telegram (gave up), restart the affected session manually.
