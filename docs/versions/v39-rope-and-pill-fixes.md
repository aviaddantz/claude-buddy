# Claude Buddy v39 — Rope During Tool Use + Pill Text Fix

## What Changed from v38

Two fixes: rope animation wasn't showing during multi-step agentic sessions, and the expanded pill was still truncating the intent text.

---

## Changes

### 1. Rope now animates throughout the full agentic session
**Before:** `thinking_start` only fired on `UserPromptSubmit` (human message). `Stop` fired after every intermediate response, killing the rope. During long tool-use sessions the rope would disappear after the first tool call and never come back.
**After:** `PreToolUse` hook also fires `thinking_start`. The rope restarts before every tool call, so it stays on continuously as long as Claude is working.

### 2. Expanded pill shows full intent text
**Before:** The expanded intent label was still eliding text — the separate word-wrap label was added to `_expanded_widget` but various attempts to dynamically resize `_intent_label` didn't work due to Qt layout constraint conflicts. Also briefly used 14px bold which didn't match the collapsed style.
**After:** `_intent_full_label` (word-wrap, 12px, same style as collapsed) lives inside `_expanded_widget`. When expanded, the elided `_intent_label` hides and the full label shows. No dynamic resize, no font mismatch.

## What Stayed the Same

* Collapsed pill appearance
* `thinking_stop` on `Stop` hook (rope stops when Claude finishes)
* All button and approval behavior

## Known Issues (logged for v40)

* Rope arc clips at widget boundary — doesn't visibly clear below the feet. Pending implementation.
* Right-pointing flag would look cleaner but requires wider sprite canvas.
* No transition animation between rope and flag states.
