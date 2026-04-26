# Claude Buddy v15 — Skip Rope Animation

## What Changed from v14

The sprite bobbed up and down with a plain sine wave. Now a green rope arc swings over and under the body in sync with the bob, so it looks like the sprite is skipping rope.

---

## Changes

### 1. Rope drawing in SpriteWidget
**Before:** `paintEvent` drew the body, border, shadow, and eyes. No rope.
**After:** A new `_draw_rope` method draws a quadratic bezier arc anchored near each arm. The arc's control point swings vertically based on `_rope_angle`, driven by `sin()`. A `set_rope_angle(float)` method triggers repaints when the angle updates. Rope color is `#66BB6A` (green), line width is `unit * 0.5` with round caps. The rope always draws on top of the body (no z-order switching).

### 2. Bob timer drives rope angle
**Before:** `_bob_step` only moved the sprite widget vertically.
**After:** `_bob_step` also calls `self.sprite.set_rope_angle(self._bob_tick * 0.12)`, syncing the rope rotation with the existing bob cycle. No new timer.

### 3. Taller sprite widget for rope headroom
**Before:** `SPRITE_H = 32`, sprite centered vertically in widget. The rope arc clipped at the top.
**After:** `SPRITE_H = 52`. The `unit` calculation uses width only (`w / 15.5`) instead of `min(w/15.5, h/12.0)` so the body stays the same size. The body is positioned at the bottom of the widget (`oy = h - char_h - unit`), leaving headroom above for the rope arc.

### 4. QPointF import added
`QPointF` added to the `PyQt6.QtCore` import line for the bezier control points.

## What Stayed the Same

* Bob timer interval (30ms) and amplitude (8px) unchanged
* Sprite body shape, colors, and sticker effect unchanged
* `classify.py` and `notify.sh` unchanged
* Pill UI, risk classification, and button layout unchanged
* Rope plays continuously whenever the bob timer is running (idle and pending)

## Known Issues (logged for v16)

* Rope anchor points are at arm height but float outside the body rather than visually connecting. Could look more natural with slight arm extension during the animation.
* No `prefers-reduced-motion` support. Should fall back to static or gentle bob when the OS accessibility setting is enabled.
* The rope arc radius (`12.0 * unit`) was tuned by eye. On different screen resolutions/DPI it may look too large or too small.
