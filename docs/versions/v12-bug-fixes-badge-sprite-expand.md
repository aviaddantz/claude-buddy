# v12 — Bug Fixes: Badge, Sprite Gap, One-Click Expand

## What changed

Three bugs found during real-world testing of v11 session pill navigation.

### Badge repositioned to window level (notification style)

The count badge was parented to `_SessionPill`, which clipped it to the pill's bounds — it appeared inside the pill border rather than floating at the corner. Moved the badge to `ChipWidget` (the window widget) so it can freely overlap the pill edge. Widened the window from 200px to 209px to give the badge 9px of overhang past the pill's right edge. Badge is now centered on the top-right corner of the first pill like a standard macOS/iOS app notification badge.

### Sprite gap above first pill

`_sprite_h = BOB_AMP + SPRITE_H` (8 + 32 = 40px) left zero clearance between the sprite's resting position bottom and the container top. Added 14px gap (`_sprite_h = BOB_AMP + SPRITE_H + 14`) so the sprite bobs visibly above the pill stack without overlapping it.

### One-click expand for inactive pills

Clicking an inactive pill activated it (switching `_current_index`) and rebuilt the pill stack — but the new active pill was born collapsed, requiring a second click to expand. Fixed `_on_pill_activated` to immediately call `toggle_expand()` on the newly active pill after `_rebuild_sessions()`, so activation and expansion happen in a single click.

## Files changed

* `buddy.py` — `_SessionPill` (removed badge), `ChipWidget.__init__` (badge widget, window width), `ChipWidget._rebuild_sessions` (badge management), `ChipWidget._on_pill_activated` (auto-expand)
