# Claude Buddy v22 — Smart Focus CTA

## What Changed from v21

The "Go to session" button always showed the same label regardless of what environment Claude Code was running in. For Claude Desktop users it was misleading — clicking it wouldn't navigate to a session, it would just bring the app to the front. v22 captures the shell's `TERM_PROGRAM` env var at hook time, uses it to activate the correct app, and shows a label that accurately describes what the button does.

---

## Changes

### 1. Capture `TERM_PROGRAM` in notify.sh
**Before:** Only `ITERM_SESSION_ID` was passed in the payload. There was no way to know which terminal (or non-terminal) spawned the hook.
**After:** `TERM_PROGRAM` env var is captured as `TERM_PROG` and included in the JSON payload as `term_program`. Payload arg count shifted from 10 to 11 args accordingly.

### 2. Smarter focus logic in `_focus_terminal_with_session`
**Before:** If no `iterm_session` UUID, scanned a hardcoded list of terminal app names and activated the first one running — could activate the wrong app if multiple terminals were open.
**After:** Four-stage fallback:
1. iTerm2 UUID → exact tab targeting via AppleScript (unchanged)
2. `term_program` set → activate the specific app via `TERM_TO_APP` lookup
3. Neither set (Claude Desktop) → activate "Claude" if running
4. Last resort → scan for any running terminal

### 3. Context-aware CTA label
**Before:** Button always read "Go to session" regardless of context.
**After:** Label reflects what the button actually does:
- iTerm2 with session UUID → "Go to session"
- iTerm2 without UUID → "Open iTerm2" (via `term_program`)
- Terminal.app → "Open Terminal"
- Warp → "Open Warp"
- Ghostty / VS Code / Cursor → "Open Ghostty" / "Open VS Code" / "Open Cursor"
- Claude Desktop (no `term_program`) → "Open Claude"

---

## What Stayed the Same

* iTerm2 exact-tab navigation via session UUID — unchanged
* All chip UI, pill layout, approve/deny/always-allow flow — unchanged
* Risk classification, auto-approve logic — unchanged
* `classify.py`, `start-daemon.sh` — unchanged

## Known Issues (logged for v23)

* **"Open Claude" doesn't navigate to the specific conversation** — clicking brings the Claude Desktop window to the front but doesn't jump to the triggering session. The `claude://` URL scheme only handles MCP auth callbacks; no session-routing API is exposed.
* **`TERM_PROGRAM` not set in all terminals** — some environments (e.g. non-standard shells, CI-like launchers) may not set `TERM_PROGRAM`, falling through to "Open Claude" even if a terminal is intended.
* Carried from v21: menu bar icon legibility, no restart feedback, SMAppService in /Applications, `swift build` CLT bug, terminal approval delay.
