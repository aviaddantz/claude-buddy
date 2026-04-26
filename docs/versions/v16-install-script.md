# Claude Buddy v16 — Install Script

## What Changed from v15

Installing Claude Buddy required four manual steps: cloning to a specific hardcoded path, pip installing PyQt6, hand-editing settings.json to add hooks, and restarting Claude Code. Non-technical users couldn't set it up. Now it's two commands.

---

## Changes

### 1. install.sh
**Before:** No installer. Users followed a manual README with four steps including editing JSON by hand.
**After:** `bash claude-buddy/install.sh` handles everything: checks for Python 3 (offers Homebrew install if available), prompts for install location (default `~/claude-buddy`), installs PyQt6, and merges hooks into `~/.claude/settings.json` using Python for safe JSON manipulation. Idempotent on re-runs.

### 2. uninstall.sh
**Before:** No uninstaller. Users had to manually remove hooks from settings.json and delete files.
**After:** `bash uninstall.sh` removes the three Claude Buddy hooks from settings.json, kills any running daemon, and optionally deletes the install directory.

### 3. start-daemon.sh uses self-resolving paths
**Before:** Hardcoded `~/Development/nudge/buddy.py` path.
**After:** Resolves `SCRIPT_DIR` from the script's own location. Works from any install directory.

### 4. Hook schema fix (contributed by ufridman)
**Before:** install.sh wrote hooks in the flat format (`{type, command}`) which Claude Code rejects. Every fresh install was broken.
**After:** Hooks are written in the correct nested format (`{matcher, hooks: [{type, command}]}`). Also auto-migrates users who ran the broken installer.

### 5. README simplified
**Before:** Four-step setup with JSON snippet to copy.
**After:** Two commands: `git clone` and `bash install.sh`.

## What Stayed the Same

* buddy.py - no path changes needed (launched by start-daemon.sh)
* notify.sh - already used self-resolving paths
* classify.py - untouched
* Risk classification and UI behavior - untouched

## Known Issues (logged for v17)

* install.sh doesn't verify that the hooks were applied correctly after writing settings.json
* No way to update an existing installation other than re-running the installer (no `--update` flag, though `git pull` in the install dir works)
* If a user has a malformed settings.json (not valid JSON), the installer's Python block will fail silently
