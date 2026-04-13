# v14 — Expanded Pill Command Display

## What Changed

### notify.sh: pass tool_input through payload
`tool_input` (the raw JSON input Claude sent to the tool) was already extracted in `notify.sh` but never forwarded to the daemon. Now included in the payload so `buddy.py` can access the raw command.

### buddy.py: remove redundant intent label in expanded view
Removed the `full_intent_label` that repeated the intent text in the expanded section — it was already visible in the collapsed pill header.

### buddy.py: truncated command + show/hide toggle for Bash
For Bash tool calls, the expanded view now shows:
- A single dim monospace line with the command, truncated with ellipsis
- A "show full ▾" toggle below it (always anchored below)
- Clicking reveals the full raw command in a dark code block
- Clicking again collapses it back

Non-Bash tools (Write, Edit, Read, etc.) show buttons only — no command line.

### buddy.py: targeted pill resize on toggle
Toggle uses `_update_window_size_for_pill()` — a new targeted method that only calls `adjustSize()` on the toggled pill, reads other pills' current sizes without touching them. Fixes a bug where toggling the command in one pill caused other pills in the queue to shift/resize.

## Why

The expanded view was redundant — it just repeated the intent and showed buttons. Now expanding gives you the actual command to verify before approving, without switching to the terminal. The "show full" toggle keeps it compact for short commands, and available for long multi-file commands where the detail matters most.
