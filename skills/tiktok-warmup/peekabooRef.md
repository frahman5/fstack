# Peekaboo Fallback Reference

Use this when Claude Code's `request_access` / computer-use tools fail due to macOS permissions issues.
Peekaboo is a separate CLI tool with its own permissions context — it often works when computer-use doesn't.

---

## Step 0 — Verify / Install Peekaboo

```bash
# Check if installed
which peekaboo || brew tap steipete/tap && brew install peekaboo

# Verify macOS permissions are granted
peekaboo permissions status --json
```

The JSON output must show `"isGranted": true` for **both** `Screen Recording` and `Accessibility`.

If either is missing: output one line explaining which permission is missing and where to grant it
(`System Settings > Privacy & Security > Screen Recording / Accessibility`), mark all sessions
failed with error "Peekaboo fallback unavailable — missing macOS permission: [Screen Recording|Accessibility]",
write an Agent Messages record, and send a Telegram escalation.

---

## Command Mapping (computer-use → Peekaboo CLI)

All commands below target the cloud phone window (`com.wails.mlxdsk`). Swap `--app` for
`"Multilogin X App"` when interacting with the Multilogin UI instead.

### Screenshot

```bash
# Capture the phone window and save to disk
peekaboo image --app "com.wails.mlxdsk" --path /tmp/phone_ss.png
# Then Read /tmp/phone_ss.png to see the screen
```

Use this wherever computer-use `screenshot()` would be called. Read the saved file after each capture.

### Single click

```bash
# computer-use: left_click(x, y)
peekaboo click --coords x,y --app "com.wails.mlxdsk"
```

### Swipe / drag (e.g. scroll TikTok videos)

```bash
# computer-use: left_click_drag(from_x, from_y, to_x, to_y)
# Swipe UP to advance to next video (fast flick ~300ms)
peekaboo swipe --from-coords 660,500 --to-coords 660,250 --app "com.wails.mlxdsk" --duration 300 --profile human

# Swipe UP medium pace
peekaboo swipe --from-coords 660,480 --to-coords 660,280 --app "com.wails.mlxdsk" --duration 500 --profile human

# Swipe UP slow drag
peekaboo swipe --from-coords 660,550 --to-coords 660,300 --app "com.wails.mlxdsk" --duration 900 --profile human

# Swipe DOWN to go back (rewatch)
peekaboo swipe --from-coords 660,270 --to-coords 660,520 --app "com.wails.mlxdsk" --duration 400 --profile human
```

Vary `--from-coords`, `--to-coords`, and `--duration` per the Swipe Physics Rules in `computerUseRef.md`.

### Open app drawer (swipe up from bottom of phone)

```bash
peekaboo swipe --from-coords 660,580 --to-coords 660,300 --app "com.wails.mlxdsk" --duration 400 --profile human
```

### Type text

```bash
# computer-use: type("some text")
# First click the target field to focus it
peekaboo click --coords x,y --app "com.wails.mlxdsk"
# Then type (--wpm 120 mimics human speed)
peekaboo type "your text here" --app "com.wails.mlxdsk" --wpm 120
```

### Clear a text field then type

```bash
peekaboo click --coords x,y --app "com.wails.mlxdsk"
peekaboo hotkey --keys "cmd,a" --app "com.wails.mlxdsk"
peekaboo press delete --app "com.wails.mlxdsk"
peekaboo type "new text" --app "com.wails.mlxdsk" --wpm 120
```

### Press special keys

```bash
# computer-use: key("BackSpace")
peekaboo press delete --app "com.wails.mlxdsk"

# computer-use: key("Return")
peekaboo press return --app "com.wails.mlxdsk"

# computer-use: key("Escape")
peekaboo press escape --app "com.wails.mlxdsk"
```

### Bring phone window to front

```bash
# computer-use: open_application("phone_launcher_darwin_arm64")
peekaboo app switch --to "phone_launcher_darwin_arm64"
```

### Bring Multilogin to front

```bash
peekaboo app switch --to "Multilogin X App"
```

### Launch Multilogin (if not running)

```bash
peekaboo app launch "Multilogin X App" --wait-until-ready
```

---

## Full Session Execution Flow (Peekaboo mode)

Follow all the same steps in `computerUseRef.md`, but substitute every computer-use primitive
with the Peekaboo equivalents above. The interaction loop is:

1. `peekaboo image --app "com.wails.mlxdsk" --path /tmp/phone_ss.png` → Read `/tmp/phone_ss.png`
2. Decide what action to take based on what you see
3. Execute the action (`peekaboo click`, `peekaboo swipe`, `peekaboo type`, etc.)
4. Wait the appropriate amount of time (use `sleep` via Bash for pauses)
5. Repeat from step 1

### Waiting / pausing

```bash
sleep 5    # 5-second pause (use for page loads, animation, etc.)
sleep 15   # mid-session pause (simulate looking away)
sleep 30   # longer pause
```

### Checking Multilogin profile status

After clicking to start a profile, take a screenshot of the Multilogin window and look for:
- Red stop button (■) → phone is running
- Minutes counter decreasing → confirmed running
- Play button still showing (▶) → not started

```bash
peekaboo image --app "Multilogin X App" --path /tmp/ml_ss.png
# Then Read /tmp/ml_ss.png
```

---

## Stopping the Cloud Phone

Click the red stop button on the profile row in Multilogin:

```bash
peekaboo app switch --to "Multilogin X App"
peekaboo image --app "Multilogin X App" --path /tmp/ml_ss.png
# Read and locate the stop button (■) for the profile row, then:
peekaboo click --coords x,y --app "Multilogin X App"
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `peekaboo: command not found` | Run install command in Step 0 |
| Permission denied in `permissions status` | Grant in System Settings, re-run skill |
| Click lands in the wrong place | Re-take screenshot, re-read coordinates — window may have moved |
| Swipe doesn't advance TikTok video | Increase swipe distance or reduce `--duration` (faster flick) |
| Type does nothing | Ensure you clicked the target field first to focus it |
| Phone window not visible in screenshot | Run `peekaboo app switch --to "phone_launcher_darwin_arm64"` then retry |
