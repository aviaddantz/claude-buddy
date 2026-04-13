# Claude Buddy v11 — Session Pill Navigation

## What Changed from v10

v10 had a horizontal pill-tab row below the main chip for multi-session navigation. The row was implemented as `_PillTab` widgets in a `_NavPill` container. The count badge was positioned absolutely relative to the window, causing it to clip at the window edge.

v11 replaces the entire nav system with a vertical stack of self-contained `_SessionPill` widgets — one per queued request. The active session pill is fully opaque and expanded by default. Inactive sessions are dimmed below it and can be clicked to switch focus.

## Changes

### 1. Removed `_PillTab` + `_NavPill` classes
The horizontal tab row and its outer container are gone entirely. Also removed: `_tab_label`, `_rebuild_nav`, `_reposition_nav`, `_update_window_height` methods, and the floating `_badge` QLabel.

### 2. New `_SessionPill` class
Each pending request gets its own pill widget containing: project label, elided intent, and the full expanded approval UI (Yes / Always allow / No / Go to session). The pill expands/collapses on click. Inactive pills dim their text to `#444` and highlight to `#777` on hover.

### 3. Badge moved inside pill boundary
The count badge (N pending) now lives inside the first `_SessionPill`'s `PillWidget` background, inset 4px from the top-right corner. It cannot be clipped by the window edge.

### 4. `ChipWidget` restructured as a vertical container
The single `self._pill` widget is gone. `ChipWidget` now owns a `_container` QWidget with a `_container_layout` QVBoxLayout that holds all `_SessionPill` instances. Window height recalculates after each expand/collapse via `_update_window_size`.

### 5. Bob animation wired to active pill expand state
Bob stops when the active pill is expanded (via `expand_changed` signal), resumes when collapsed.

### 6. `_focus_terminal` refactored
Renamed to `_focus_terminal_with_session(iterm_session: str)` — takes the iTerm2 session ID as a direct parameter instead of reading from `self._requests`.

### 7. `_on_pill_always` correctly writes `"always_allow"`
The always-allow button writes `"always_allow"` to the decision pipe so `notify.sh` triggers the `updatedPermissions` path in Claude Code.

## What Stayed the Same
- Risk classification (`classify.py`) — unchanged
- Risk colors (`RISK_COLORS`)
- `SpriteWidget` / `PillWidget` rendering
- All-spaces pinning
- Staleness timer (1s PID check)
- Per-request terminal routing via `iterm_session`
- `start-daemon.sh` lifecycle script
