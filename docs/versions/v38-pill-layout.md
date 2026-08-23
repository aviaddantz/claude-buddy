# Claude Buddy v38 — Pill Layout

## What Changed from v37

The expanded pill was wasting its real estate on a raw bash command that isn't useful for approval decisions. Replaced it with a cleaner layout: full intent text front and center, command hidden until explicitly requested.

---

## Changes

### 1. Command hidden by default
**Before:** Expanded pill always showed a truncated single-line command plus a "show full ▾" toggle to reveal the complete command.
**After:** Command is hidden entirely by default. A centered "show command ▾" link reveals the full command block on demand. The truncated short command line is gone — the toggle goes directly from hidden to full.

### 2. Intent label expands to full text on open
**Before:** Intent line stayed elided (single line, cut off with "…") even in the expanded state.
**After:** Clicking to expand switches the intent label to word-wrap mode showing the full untruncated text. Collapsing restores the single-line elided version.

### 3. "show command" toggle centered
**Before:** Toggle label was right-aligned.
**After:** Centered, consistent with the rest of the pill layout.

### 4. "Show when idle" renamed to "Always show"
**Before:** Menu bar toggle was labeled "Show when idle."
**After:** "Always show" — reflects that the widget now stays visible during thinking state too, not just idle.

## What Stayed the Same

* Collapsed pill appearance (source label + single elided intent line)
* All button behavior (Yes / Yes always / No / Go to session)
* Risk color theming
* Flag and rope animations

## Known Issues (logged for v39)

* Rope arc clips at widget boundary — doesn't visibly clear below the feet. Pending implementation (option B agreed: medium arc, rope drawn in front).
* Right-pointing flag would look cleaner but requires wider sprite canvas.
* No transition animation between rope and flag states.
