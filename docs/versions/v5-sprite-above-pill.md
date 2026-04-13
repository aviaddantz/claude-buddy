# Claude Buddy v5 — Sprite Above Pill Layout

## What Changed from v4

v4 had everything inside a single rounded rect — sprite and text shared one bordered background. v5 separates them: the sprite floats freely above the pill with a gap, and the pill is its own independently drawn component.

## New Layout

```
  8px headroom (bob up clearance)
  [sprite]        ← transparent, no background, bobs independently
     ↕ 14px gap   (clearance for bob-down so legs don't clip pill)
 ┌──────────┐
 │  intent  │     ← pill: bordered rounded rect, text only
 │ project  │
 └──────────┘
```

**Before (v4):** sprite + text inside one chip background, whole window bobs  
**After (v5):** sprite above pill, only sprite bobs, pill stays fixed

## Key Design Decisions

**Fixed window width (200px)**  
Both the outer window and the pill are fixed at 200px. This is what makes the sprite stay centered above the pill on both compact and expanded states — if the window width changes on expand, the sprite appears to shift. Fixed width prevents any positional movement.

**PillWidget as a separate class**  
The pill background is drawn by a new `PillWidget` class with its own `paintEvent`. This means the rounded rect border only covers the pill area, not the sprite.

**Compact height is explicit**  
Compact pill height is calculated as: `8 (top padding) + 18 (intent) + 1 (gap) + 14 (project) + 8 (bottom padding) = 49px`. Set via `setFixedHeight()` on show and on collapse. Released on expand so buttons can grow in.

**Bob animation on sprite only**  
Replaced `QPropertyAnimation` on window `pos` with a `QTimer` (30ms interval) that drives a sine wave on the sprite's absolute y position only. The pill doesn't move at all. The sprite bobs between `rest_y - 8px` (peak) and `rest_y + 8px` (trough).

**Absolute positioning for sprite and pill**  
Both are placed with `move()` directly on the window rather than inside a layout. This is what allows the sprite to animate independently — layout children can't be animated without moving their parent.

**Spacing constants:**
* `BOB_AMP = 8` — amplitude in pixels
* `SPRITE_GAP = 14` — gap between sprite bottom (at rest) and pill top; needs to be ≥ BOB_AMP to avoid legs clipping the pill at the lowest point
* `BOB_AMP` is also used as top padding so the sprite has headroom when jumping up

## Bug Fixed: Stray Quote in Domain Names

`"https://api.ipify.org"` — when the URL is shell-quoted, the regex match included the trailing `"` in the domain, showing `Fetching api.ipify.org"`. Fixed in `classify.py` by stripping quotes from the URL before and after domain extraction.

## Files Changed

| File | Change |
|---|---|
| `buddy.py` | New `PillWidget` class; `ChipWidget` split into sprite row + pill; fixed 200px window width; explicit compact height on show/collapse |
| `classify.py` | Strip quotes from matched URLs in `extract_domain()` |
