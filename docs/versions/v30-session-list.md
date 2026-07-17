# v30 — Session List

## What Changed

Double-click the idle sprite to see all active Claude Code sessions. Click a row to jump directly to that session.

### Session List UI
- Double-clicking the sprite opens a stacked list of session rows beneath the chip
- Each row shows the project folder name and the session intent (tab title or first user message)
- Clicking a row focuses the right window — iTerm2 tab by UUID, CWD-match for transcript-scanned sessions, Claude desktop for desktop sessions
- Clicking anywhere else (including other apps) dismisses the list via NSEvent global monitor

### Persistent Sessions
- Sessions are stored in `~/.nudge-sessions.json` on `SessionStart`; removed on `session_end`
- Daemon restart no longer wipes session state — existing sessions reappear immediately
- On startup, daemon also scans `~/.claude/projects/` transcript files (mtime < 4h) for sessions not in the JSON file — works even if Nudge was off when sessions started
- Intent extracted from first real user message in the JSONL transcript (skips system/tool lines)

### Menu Bar Toggle
- New "Show sessions on double-click" toggle in Nudge menu bar app
- Backed by `~/.nudge-sessions-disabled` flag file, wired through `notify.sh sessions_on/off` to the daemon live

### Bug Fixes
- `WA_TransparentForMouseEvents` on SpriteWidget — double-click events were being absorbed by the sprite and never reached ChipWidget
- NSEvent global monitor replaces Qt's `installEventFilter` for blur detection — Qt only sees clicks inside the Qt app; NSEvent catches clicks in all other apps
- iTerm2 tab title cleaning — strips braille spinner prefix and ` (claude)` suffix before storing as intent

### Build Fix
- `swift build` is broken with CLT-only toolchain (two CLT files redefine `SwiftBridging`). Build now uses `swiftc` directly with a VFS overlay that hides the conflicting `module.modulemap`. Full recipe in memory.
