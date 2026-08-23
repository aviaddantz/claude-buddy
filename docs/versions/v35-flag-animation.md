# Claude Buddy v35 — Flag Animation

## What Changed from v34

Previously, both thinking (Claude processing) and approval-pending states used the same rope animation. There was no visual distinction between "Claude is thinking" and "Claude is waiting for your decision." This version adds a flag-waving animation that replaces the rope when an approval pill is on screen, giving the two states distinct looks. Multi-session priority is also clarified: flag wins over rope when any session has a pending approval.

---

## Changes

### 1. Flag animation on approval

**Before:** When an approval pill appeared, the sprite continued the same rope-swinging animation used during thinking.

**After:** When an approval pill arrives, the sprite drops the rope and raises a triangular pennant on a pole from the right arm. The flag waves with a sinusoidal motion. Flag color matches the risk level of the pending request: green (low), yellow (medium), red (high). High-risk requests wave the flag faster (rate 0.20 vs 0.13).

When multiple approval requests are queued, the flag color reflects the highest risk level among all pending requests and updates as requests are resolved.

### 2. State machine: flag wins

**Before:** No explicit priority rule. Both thinking and approval ran the bob timer with rope.

**After:** Clear priority:
* Any approval pending → flag animation, rope hidden
* Thinking only (no approval) → rope animation (unchanged)
* Last approval resolved, still thinking → flag stops, rope resumes
* Neither → idle or hide

`on_thinking_start` returns early without touching the rope if approvals are pending. All four approval-resolution callsites (`_remove_by_pipe`, `_on_cancel`, `_cleanup_stale_requests`, `on_session_end`) now call `_transition_to_rope()` when requests empty and thinking continues, instead of leaving state ambiguous.

### 3. New animation helpers

Four new methods on `ChipWidget`:
* `_highest_risk()` — returns highest risk level across all pending requests
* `_start_flag_animation()` — stops bob timer, sets flag color/rate, starts flag timer
* `_stop_flag_animation()` — stops flag timer, clears show_flag
* `_transition_to_rope()` — calls `_stop_flag_animation`, starts bob timer, calls `_update_window_size` and `_reanchor`

Separate `_flag_timer` (QTimer, 30ms) and `_flag_tick`/`_flag_rate` state added alongside the existing `_bob_timer`.

### 4. Flag geometry

Pole: 9 units tall, from right arm tip upward. Pennant: 8 units wide × 4 units tall, attaches at pole top and extends left toward body center (keeps within the 40px sprite canvas). Wave amplitude: 2.0 units. Pole color: light gray (#CCCCCC). Flag fill: risk-level border color at 92% opacity with a subtle white edge stroke.

### 5. Pill expand/collapse uses flag timer

**Before:** Expanding a pill stopped the bob timer; collapsing restarted it.

**After:** Expanding stops the flag timer; collapsing restarts it. Bob timer is no longer involved in pill expand/collapse since pills only exist during approval (flag) mode.

---

## What Stayed the Same

* Thinking animation (rope swinging) — unchanged
* Pill appearance, approval/deny flow — unchanged
* Risk classification — unchanged
* Session list, idle sprite, drag behavior — unchanged
* All-spaces pinning — unchanged

## Known Issues (logged for v36)

* Flag extends left over the body area when the pennant is large — visually acceptable but a right-pointing flag would look cleaner (requires wider sprite canvas)
* No transition animation between rope and flag states — they switch instantly
* Flag size is fixed regardless of display resolution / screen scale factor
