# Claude Buddy

An always-on-top approval widget for Claude Code on macOS.

When Claude Code requests tool permissions, instead of switching to the terminal to approve or deny, a floating chip appears at the top-right of your screen showing the risk level and plain-English description of what Claude is about to do.

![Claude Buddy](docs/assets/screenshot.png)

## Features

* Floating chip stays visible across all virtual desktops
* Risk levels: low (green), medium (yellow), high (red)
* Plain-English intent -- know what Claude is actually doing before you approve
* Approve, Deny, or jump directly to the terminal session
* Supports multiple simultaneous Claude Code sessions

## Requirements

* macOS
* Python 3.6+ (the installer will check and help you install it)

## Setup

```bash
git clone https://github.com/aviaddantz/claude-buddy.git
bash claude-buddy/install.sh
```

The installer handles everything: Python check, PyQt6, and Claude Code hook configuration. It will ask where you want to install (default: `~/claude-buddy`).

Start Claude Code and the widget launches automatically.

## Uninstall

```bash
bash ~/claude-buddy/uninstall.sh
```

## Manual controls

```bash
python3 ~/Development/nudge/buddy.py daemon  # start manually
python3 ~/Development/nudge/buddy.py show
python3 ~/Development/nudge/buddy.py hide
```

Logs: `/tmp/claude-buddy.log`

## How it works

Two processes talk via Unix socket and named pipes:

* `notify.sh` -- reads the permission request from Claude Code, classifies the tool into a risk level and intent string, sends it to the daemon
* `buddy.py` -- runs the UI, displays the chip, writes the approve/deny decision back

## Contributing

PRs welcome. Open an issue first for anything beyond small fixes.
