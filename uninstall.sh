#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
SETTINGS_FILE="$HOME/.claude/settings.json"

echo ""
echo "  Claude Buddy Uninstaller"
echo "  ========================"
echo ""

# ── Stop running daemon ────────────────────────────────────────────────────

if pkill -f "buddy.py daemon" 2>/dev/null; then
    echo "  Stopped running daemon."
fi

# ── Remove hooks from settings.json ────────────────────────────────────────

if [ -f "$SETTINGS_FILE" ]; then
    echo "  Removing hooks from $SETTINGS_FILE..."

    python3 - "$SCRIPT_DIR" "$SETTINGS_FILE" << 'PYTHON_SCRIPT'
import json
import sys
import os

install_dir = sys.argv[1]
settings_file = sys.argv[2]

if not os.path.exists(settings_file):
    sys.exit(0)

with open(settings_file, "r") as f:
    try:
        settings = json.load(f)
    except json.JSONDecodeError:
        sys.exit(0)

if "hooks" not in settings:
    sys.exit(0)

commands_to_remove = [
    f"bash {install_dir}/start-daemon.sh",
    f"bash {install_dir}/notify.sh approval",
    f"bash {install_dir}/notify.sh done",
]

for event in list(settings["hooks"].keys()):
    hooks_list = settings["hooks"][event]
    filtered = []
    for hook in hooks_list:
        if isinstance(hook, dict):
            if hook.get("command") in commands_to_remove:
                continue
            # Check nested format
            nested = hook.get("hooks", [])
            if nested:
                nested_filtered = [nh for nh in nested if not (isinstance(nh, dict) and nh.get("command") in commands_to_remove)]
                if nested_filtered:
                    hook["hooks"] = nested_filtered
                    filtered.append(hook)
                continue
        filtered.append(hook)

    if filtered:
        settings["hooks"][event] = filtered
    else:
        del settings["hooks"][event]

if not settings["hooks"]:
    del settings["hooks"]

with open(settings_file, "w") as f:
    json.dump(settings, f, indent=2)

print("  Hooks removed.")
PYTHON_SCRIPT
fi

# ── Remove install directory ───────────────────────────────────────────────

echo ""
read -rp "  Remove $SCRIPT_DIR? This deletes all Claude Buddy files. [y/N] " yn
yn="${yn:-N}"
if [[ "$yn" =~ ^[Yy]$ ]]; then
    rm -rf "$SCRIPT_DIR"
    echo "  Removed $SCRIPT_DIR"
else
    echo "  Kept $SCRIPT_DIR"
fi

echo ""
echo "  Claude Buddy uninstalled."
echo ""
