# Claude Buddy v43 — Flip and Flag

## What Changed from v42

Two visual bugs fixed: the pill was rendering transparent (background content bleeding through) when the sprite was positioned in the lower screen half, and the flag on the sprite always showed orange regardless of the actual risk level.

---

## Changes

### 1. QRegion mask correct in flip mode

**Before:** `_update_mask` always computed the pill content region at `y = sprite_h` (74px). In flip mode (sprite at bottom, pills above), pills are actually at `y = 0`. The pill area fell entirely outside the mask, making it transparent -- background windows bled through the pill, showing unrelated content where the approval card should be.

**After:** `_update_mask` now handles three cases:
- No content (idle/thinking): sprite-only mask
- Flip mode: pill region from `y=0` to `y=flip_pills_h`, sprite region below that
- Normal mode: sprite at top, pill content below `sprite_h`

### 2. Flag color matches pill risk level

**Before:** `_highest_risk()` initialised `best = "medium"`, so a low-risk request (green pill) never beat the default and always produced an orange flag.

**After:** Initialised `best = "low"` so the flag color correctly reflects the highest risk level among pending requests. Green pill → green flag, orange pill → orange flag, red pill → red flag.

---

## What Stayed the Same

* Flip layout trigger threshold (55% of screen height)
* Flag animation speed and waveform
* All pill layout, expand/collapse, and button behavior
* Mask logic for normal (non-flip) mode

## Known Issues (logged for v44)

* Sleeping sprite for idle state not yet implemented
* Pill font metrics computed at construction time before stylesheet applies — may measure with wrong font in rare edge cases
