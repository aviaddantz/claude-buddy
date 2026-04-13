# Claude Buddy v6 — Design Overhaul

## What Changed from v5

v5 had the correct layout (sprite above pill, v-split) but the visual design was AI-slop dark mode: tinted risk-colored backgrounds on the pill, tinted fills on every button, emoji glyphs in labels, and hover-to-expand with a leaky collapse timer. v6 fixes all of it.

---

## Design Changes

### 1. Uniform pill background

**Before:** Pill background was tinted per risk level — `#0d1f0d` (low), `#1f1a00` (medium), `#1f0a0a` (high). Risk color applied to both border and background, creating muddy competing surfaces.

**After:** Single neutral background `#0a0a0a` across all risk levels. The border alone carries the status signal. This mirrors how macOS system notifications handle urgency — the chrome stays neutral, the accent carries the meaning.

```python
RISK_COLORS = {
    "low":    {"border": "#4CAF50", "bg": "#0a0a0a", "text": "#a5d6a7"},
    "medium": {"border": "#ffaa00", "bg": "#0a0a0a", "text": "#ffe082"},
    "high":   {"border": "#f44336", "bg": "#0a0a0a", "text": "#ef9a9a"},
}
```

### 2. Intent text color — consistent across all risk levels

**Before:** Medium risk intent text fell through to neutral `#e8e8e8` while low got green and high got red. Inconsistent.

**After:** All three risk levels use their risk color for intent text. The pill background stays neutral, so text + border together reinforce the signal without muddiness.

### 3. Button hierarchy — one CTA, everything else secondary

**Before:** All four buttons had dark tinted fills with equal visual weight. No clear primary action. Deny was buried last after "Open Claude Code."

**After:**
| Button | Style | Reasoning |
|--------|-------|-----------|
| Yes | Solid green fill `#4CAF50`, black text, bold | Only filled button — unambiguous primary CTA |
| Yes, allow all edits this session | Ghost: `#555` border, `#aaa` text | Secondary, shown only when suggestions present |
| No | Ghost: `#f44336` border + text | Destructive but not dominant |
| Go to session | Text-only, `#555`, 10px | Utility action, not a decision |

### 4. Button labels — drop glyphs

**Before:** `✓ Allow`, `✕ Deny`, `★ Always Allow`, `↗ Open Claude Code` — mixed glyph sources, assembled feel.

**After:** Plain text. `Yes`, `No`, `Yes, allow all edits this session`, `Go to session`. The sprite is the personality — buttons don't need to perform.

### 5. Button order

**Before:** Allow → Always Allow → Open Claude Code → Deny. Deny buried after a utility action.

**After:** Yes → Always Allow → No → Go to session. Decisions first, navigation last.

### 6. Interaction model — click to expand, not hover

**Before:** `enterEvent` triggered expand, `leaveEvent` started a 300ms collapse timer. Caused accidental expands when cursor passed over the widget. Timer was constant micro-friction.

**After:** `mousePressEvent` toggles expand/collapse. Click compact pill → expand. Click anywhere inside expanded panel (not a button) → collapse. No timer involved. `_collapse_timer` removed entirely.

Rationale: hover is clever but accidental. Click is intentional. For an approval widget that requires a conscious decision, click-to-expand matches the mental model better.

### 7. Cursor affordance

`ChipWidget` sets `PointingHandCursor` on the whole widget. All action buttons also set `PointingHandCursor` individually. Before: default arrow cursor — no signal that the widget was interactive.

### 8. Minor polish

| Item | Before | After |
|------|--------|-------|
| CWD label color | `#555` (near-invisible on `#0a0a0a`) | `#666` |
| Divider color | `#333` | `#222` |
| Expanded section spacing | 6px between buttons | 8px |
| Risk badge bg | Tinted risk bg | Transparent |

---

## What Stayed the Same

* Sprite above pill layout (v5)
* Sprite-only bob animation via QTimer sine wave
* Fixed 200px window width
* Named pipe decision flow
* All-spaces pinning via AppKit

---

## Known Issues (logged for v7)

* Clicking inside expanded panel (not on a button) collapses — click target ambiguity between "dismiss" and "interact"
* Bob animation runs continuously — should stop after ~3s and resume only on re-alert
* No easing on expand/collapse (instant visibility toggle)
* No hover feedback on compact pill border (cursor changes but pill is visually static)
* Auto-approve countdown for low-risk ops not yet implemented
