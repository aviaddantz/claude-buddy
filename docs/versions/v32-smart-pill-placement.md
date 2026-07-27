# v32 — Smart Pill Placement

## What changed

The approval pill now appears **above** the sprite when the widget is positioned in the lower portion of the screen (below 55% of screen height), and **below** when it's near the top. Previously the pill always rendered below the sprite, pushing it off-screen when the sprite was docked at the bottom.

## How it works

* `_compute_flip()` checks if `_base_y` (the sprite's screen Y anchor) exceeds 55% of screen height.
* `_apply_flip_layout(total_pills_h, rows_h)` repositions the container and badge: in flipped mode, the pill container moves to `y=0` (top of window) and the badge anchors to the top-right corner of the first pill. In normal mode, existing behavior is preserved.
* `_flip_pills_h` tracks the offset so the bob animation, drag, and `_reanchor` all keep the sprite visually anchored in place regardless of flip state.
* Drag release calls `_update_window_size` + `_reanchor` to recompute the flip layout after the sprite crosses the screen midpoint.

## Also in this release

* **Hitbox fix** (v32a): `SpriteWidget.hit_rect()` now uses `self.geometry().adjusted()` instead of the bare `QRect(...)` constructor, which was not imported in the `run_daemon()` scope and caused a `NameError` on every mouse move.
* **Grace period fix** (v32b): `notify.sh` now skips PPID death and reparenting checks for the first 5 seconds of the wait loop. In the desktop app, Claude Code's spawning shell exits immediately after forking `notify.sh`, causing the reparenting check to fire before the user could interact with the widget.
