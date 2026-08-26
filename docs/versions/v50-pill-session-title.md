# Claude Buddy v50 — Session Title on Pills

## What Changed from v49

Pending approval pills only showed the folder name (e.g. "nudge"), so when multiple pills were stacked for different sessions in the same project, there was no way to tell them apart without expanding each one. Pills now show the resolved conversation title, the same value already used in the double-click session list.

---

## Changes

### 1. Title line added to each pill
**Before:** `_SessionPill` showed only the cwd/folder label above the intent text.
**After:** A purple title label is inserted between the folder label and the intent text, showing the session's resolved title (via `_resolve_session_title`). Elided to fit the 200px pill width. Hidden entirely if no title has resolved yet (e.g. brand-new session with no ai-title/custom-title in its transcript).

### 2. Fixed session lookup at pill construction time
**Before (this cycle, caught during testing):** the title lookup used `self.window()` inside `_SessionPill.__init__` to reach `ChipWidget._sessions`. At construction time the pill isn't parented into the window yet, so `self.window()` returned the pill itself, and the lookup silently found nothing.
**After:** `ChipWidget._rebuild_sessions` now passes `sessions=self._sessions` directly into the `_SessionPill` constructor, so the lookup works regardless of parenting order.

## What Stayed the Same
- Pill layout, sizing (200px fixed width), risk coloring, and expand/collapse behavior
- `_resolve_session_title` itself — unchanged, reused as-is from the session-list feature
- No changes to notify.sh or the socket payload — `session_id` was already present on every request

## Known Issues (logged for v51+)
- No fallback distinguishes two pills from different sessions if both are brand-new and neither has a resolved title yet (both just show cwd)
