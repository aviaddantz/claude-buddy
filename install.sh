#!/bin/bash
set -euo pipefail

echo ""
echo "  Claude Buddy Installer"
echo "  ======================"
echo ""
echo "  This will:"
echo "    1. Check for Python 3 and install if needed"
echo "    2. Install PyQt6 (the UI framework)"
echo "    3. Set up Claude Code hooks so Buddy launches automatically"
echo ""

# ── Python 3 check ─────────────────────────────────────────────────────────

if ! command -v python3 &>/dev/null; then
    echo "  Python 3 is required but not installed."
    echo ""
    if command -v brew &>/dev/null; then
        read -rp "  Install Python 3 via Homebrew? [Y/n] " yn
        yn="${yn:-Y}"
        if [[ "$yn" =~ ^[Yy]$ ]]; then
            brew install python3
        else
            echo "  Please install Python 3 from https://www.python.org/downloads/ and re-run this script."
            exit 1
        fi
    else
        echo "  Please install Python 3 from https://www.python.org/downloads/ and re-run this script."
        exit 1
    fi
fi

echo "  Found Python 3: $(python3 --version)"

# ── Install location ───────────────────────────────────────────────────────

DEFAULT_DIR="$HOME/claude-buddy"
echo ""
echo "  Where should Claude Buddy be installed?"
read -rp "  [$DEFAULT_DIR] " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_DIR}"

# Expand ~ if user typed it
INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"

# ── Clone or update ────────────────────────────────────────────────────────

if [ -d "$INSTALL_DIR/.git" ]; then
    echo ""
    echo "  Found existing installation at $INSTALL_DIR, updating..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    # If running from inside a cloned repo, copy instead of re-cloning
    SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
    if [ -f "$SCRIPT_DIR/buddy.py" ] && [ -f "$SCRIPT_DIR/notify.sh" ]; then
        if [ "$SCRIPT_DIR" != "$INSTALL_DIR" ]; then
            echo ""
            echo "  Copying from $SCRIPT_DIR to $INSTALL_DIR..."
            mkdir -p "$INSTALL_DIR"
            cp -R "$SCRIPT_DIR/." "$INSTALL_DIR/"
        fi
    else
        echo ""
        echo "  Cloning Claude Buddy to $INSTALL_DIR..."
        git clone https://github.com/aviaddantz/claude-buddy.git "$INSTALL_DIR"
    fi
fi

# ── PyQt6 ──────────────────────────────────────────────────────────────────

echo ""
echo "  Installing PyQt6..."
if ! pip3 install PyQt6 2>/dev/null; then
    echo "  Retrying with --user flag..."
    pip3 install --user PyQt6
fi

# ── Configure Claude Code hooks ────────────────────────────────────────────

echo ""
echo "  Configuring Claude Code hooks..."

SETTINGS_FILE="$HOME/.claude/settings.json"
mkdir -p "$HOME/.claude"

python3 - "$INSTALL_DIR" "$SETTINGS_FILE" << 'PYTHON_SCRIPT'
import json
import sys
import os

install_dir = sys.argv[1]
settings_file = sys.argv[2]

# Claude Code hooks schema: each event holds a list of { matcher, hooks: [ { type, command } ] }
# entries. The matcher is empty here so the hook runs for every tool / event.
hooks_to_add = {
    "SessionStart": {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": f"bash {install_dir}/start-daemon.sh"
            }
        ]
    },
    "PermissionRequest": {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": f"bash {install_dir}/notify.sh approval"
            }
        ]
    },
    "Stop": {
        "matcher": "",
        "hooks": [
            {
                "type": "command",
                "command": f"bash {install_dir}/notify.sh done"
            }
        ]
    }
}

# Load existing settings or start fresh
if os.path.exists(settings_file):
    with open(settings_file, "r") as f:
        try:
            settings = json.load(f)
        except json.JSONDecodeError:
            settings = {}
else:
    settings = {}

if "hooks" not in settings:
    settings["hooks"] = {}

for event, hook in hooks_to_add.items():
    if event not in settings["hooks"]:
        settings["hooks"][event] = []

    event_hooks = settings["hooks"][event]

    # New-format hook: { matcher, hooks: [ { type, command } ] }. Pull the
    # inner command so we can match it against entries written in either the
    # old flat format or the new nested format.
    hook_command = hook["hooks"][0]["command"]

    # Drop any prior entry (old flat OR new nested) that targets our command.
    # This also migrates users whose previous install wrote the old
    # { type, command } shape that Claude Code now rejects.
    def _matches_ours(existing):
        if not isinstance(existing, dict):
            return False
        if existing.get("command") == hook_command:
            return True
        for nh in existing.get("hooks", []):
            if isinstance(nh, dict) and nh.get("command") == hook_command:
                return True
        return False

    settings["hooks"][event] = [e for e in event_hooks if not _matches_ours(e)]
    settings["hooks"][event].append(hook)

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print("  Hooks configured successfully.")
PYTHON_SCRIPT

# ── Done ───────────────────────────────────────────────────────────────────

echo ""
echo "  Done! Claude Buddy installed to $INSTALL_DIR"
echo "  Hooks added to $SETTINGS_FILE"
echo ""
echo "  Next time you start Claude Code, Claude Buddy will appear automatically."
echo "  To start it right now:  bash $INSTALL_DIR/start-daemon.sh"
echo ""
