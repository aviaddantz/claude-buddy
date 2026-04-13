# Expanded Pill Content Design

**Date:** 2026-04-13
**Status:** Approved

## Problem

The expanded pill currently repeats the intent text (already visible in the collapsed state) and shows Yes/No buttons. This is redundant and adds no decision-making value. When a user expands the pill they need to verify *exactly what* Claude is about to do — particularly for high-risk Bash commands where the specific files/arguments matter.

## Goal

The expanded view should give the user enough information to make a confident approve/deny decision, without repeating what's already visible in the collapsed pill.

## Design

### Expanded view — Bash tool

Show a truncated raw command line + "show full" toggle:

```
─────────────────────────────────────
rm "zero-to-hero.md" "ai-brains…"      ← one dim monospace line, truncated
                          show full ▾   ← right-aligned toggle
[ full command block, hidden by default ]

[ Yes                              ]
[ Yes, always allow for session    ]
[ No                               ]
[ Go to session                    ]
```

* Truncated line: single line, monospace, dim color (`#666`), truncated with ellipsis at pill width
* Toggle: right-aligned, small (`10px`), dim (`#444`), clicking reveals/hides the full command
* Full command block: shown below the truncated line when toggled open, `word-break: break-all`, slightly less dim (`#888`), dark background (`#0a0a0a`), 4px border radius
* Toggle label switches: `show full ▾` ↔ `hide full ▴`

### Expanded view — all other tools (Write, Edit, Read, Glob, etc.)

Just the buttons. No command/path shown — the intent headline in the collapsed pill already identifies the target file. Expanding is purely to approve/deny.

```
─────────────────────────────────────
[ Yes                              ]
[ Yes, always allow for session    ]
[ No                               ]
[ Go to session                    ]
```

### Removed

The current `full_intent_label` (repeating the intent text in bold white) is removed entirely from the expanded section.

## Data flow

`notify.sh` currently extracts intent/risk/cwd from `tool_input` but does not pass the raw input through. We need to add `tool_input` (as a JSON string) to the payload sent to the buddy daemon, so `buddy.py` can extract and display the command.

Field extraction priority (same logic as `classify.py`'s `extract_value()`):
1. `command` — for Bash
2. `file_path` — for Write, Edit, Read
3. `url` — for WebFetch
4. First non-empty string field — fallback

Only Bash (`tool_name == "Bash"`) gets the truncated command + toggle UI. All other tools get buttons only. If `tool_input.command` is empty for a Bash call, fall back to buttons-only (same as non-Bash).

## What changes

* **`notify.sh`** — add `tool_input` (raw JSON string) to the payload
* **`buddy.py` `_SessionPill.__init__()`** — remove `full_intent_label`; add truncated command line + toggle for Bash; buttons-only for everything else

## What doesn't change

* `classify.py` — untouched
* Risk classification — untouched
* Button layout and styling — untouched
* Collapsed pill — untouched
