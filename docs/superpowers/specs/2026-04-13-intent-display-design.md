# Intent Display in Collapsed Pill

**Date:** 2026-04-13
**Status:** Approved

## Problem

The nudge pill currently shows a mechanically-extracted intent string (e.g. `Bash: rm zero-to-hero.md ai-brains…`). This is hard for a non-developer to parse at a glance. The `PermissionRequest` payload already includes `tool_input.description` — Claude's own plain-English, outcome-oriented label (the same text the terminal shows). We're ignoring it.

## Goal

The collapsed pill should answer: "what is Claude about to do?" in plain English — readable by a product manager with no terminal context.

## Design

### Intent priority

`classify.py` gets a description-first check at the top, before any tool-specific logic:

1. If `tool_input.description` is present and non-empty → use it as the intent
2. Otherwise → fall through to existing classify.py logic (extract from command/path/url/etc.)

Risk classification is unchanged — it still runs on `tool_name` + `command` regardless of which intent source wins.

### Word-boundary truncation

Replace the current `truncate()` function (which cuts mid-character) with a word-boundary version:
- Walk back from the character limit to the last space
- Append `…`
- Limit stays at 42 chars

### What doesn't change

- `notify.sh` — no changes
- `buddy.py` — no changes
- Expanded view — no changes
- Risk classification — no changes
- Payload structure — no changes

## Before / After

| Tool | Before | After |
|------|--------|-------|
| Bash `rm` on wiki files | `Bash: rm zero-to-hero.md ai-brains…` | `Delete standalone product wiki…` |
| Bash `git commit` | `Bash: git commit -m feat: add user…` | `Commit user auth feature` |
| Bash `npm install` | `Bash: npm install axios` | `Install axios package` |
| Bash `cat` log | `Bash: cat claude-buddy.log` | `Read buddy daemon log` |
| Write file | `Write: buddy.py` | `Write: buddy.py` (fallback, unchanged) |
| Edit file | `Edit: classify.py` | `Edit: classify.py` (fallback, unchanged) |

## Scope

One file: `classify.py`. Two changes:
1. Description-first check (early return if description present)
2. Word-boundary truncate function
