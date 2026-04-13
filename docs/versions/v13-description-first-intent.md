# v13 — Description-First Intent Display

## What Changed

### classify.py: description-first intent
The pill's intent string now uses Claude's own plain-English `description` field from the `tool_input` payload — the same text the terminal shows — instead of mechanically extracting it from the raw command. If `description` is absent or empty, falls back to existing classify.py logic unchanged.

### classify.py: word-boundary truncation
Replaced the `truncate()` function which cut mid-character with a word-boundary version. It walks back to the last space before the 42-char limit before appending the ellipsis.

### buddy.py: word-boundary eliding in the UI
Qt's `elidedText()` also cuts mid-word. Added post-processing to find the last word boundary before Qt's cut point, so the collapsed pill label matches the same behavior.

### buddy.py: project name demoted to metadata
The project/cwd label (e.g. `de-agentic-workflows`) was styled the same as the intent text — same color, heavier weight — causing visual competition. It's now dimmed to `#666`, smaller (10px vs 11px), and regular weight so the intent text reads as the clear headline.

## Why

Previously the collapsed pill showed things like `Bash: rm zero-to-hero.md ai-brains…` — unreadable to a non-developer. Now it shows `Delete standalone product wiki files` — Claude's outcome-oriented label, exactly what a product manager needs to make an approve/deny decision without opening the expanded view.
