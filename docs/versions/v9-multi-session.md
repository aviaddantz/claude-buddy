# Claude Buddy v9 — Multi-Session

## What Changed from v8

v8 handled one permission request at a time. When multiple Claude Code sessions ran concurrently, each new request replaced the previous one, "Go to session" targeted the wrong terminal, and ESC/terminal-acceptance left the widget orphaned. v9 adds a request queue with visual session navigation, per-request terminal routing, and a PID-based staleness mechanism that clears resolved requests regardless of how they were resolved.

---

## Changes

### 1. Request queue (`notify.sh`, `buddy.py`)

**Before:** One request at a time. New request replaced the current one.

**After:** `ChipWidget` maintains `self._requests` (list of payload dicts) and `self._current_index`. `do_show()` appends to the queue rather than replacing. The widget stays visible until the queue is empty.

### 2. Lock mechanism removed (`notify.sh`)

**Before:** `notify.sh` used a lock file and a `PENDING` sentinel so back-to-back requests would serialize and the first would auto-approve when a second arrived.

**After:** Lock removed entirely. Each `notify.sh` invocation runs independently in parallel. Requests accumulate in the daemon queue.

### 3. Counter badge (`buddy.py`)

**Before:** No indication of how many requests were pending.

**After:** A red circular `QLabel` badge (20×20px, #f44336) appears at the top-right of the pill showing the total count. Hidden when only 1 request is pending.

### 4. Project tab navigation (`buddy.py`)

**Before:** No way to switch between pending requests.

**After:** When 2–3 requests are queued, small pill-shaped tab buttons appear below the main chip — one per request, labeled with the project name (cwd basename). Active tab has the risk-colored border and text of its request. Inactive tabs are dark (#0a0a0a background, #333 border, #666 text). When 4+ requests are queued, tabs switch to risk-colored dots (10px circles). Clicking a tab/dot calls `_switch_to(index)` which swaps chip content without collapsing the expanded state.

Tabs are rendered as custom `_PillTab(QWidget)` with `paintEvent` using `QPainterPath.addRoundedRect`. `QPushButton` was tried first but macOS native style overrides `border-radius` in stylesheets.

### 5. Same-project deduplication in tab labels (`buddy.py`)

**Before:** N/A.

**After:** `_tab_label(index)` counts how many prior requests share the same cwd basename. If duplicates exist, appends a number: "nudge", "nudge 2", etc.

### 6. Per-request session routing (`notify.sh`, `buddy.py`)

**Before:** `_focus_terminal()` read `ITERM_SESSION_ID` from the daemon's own environment (wrong for multi-session — the daemon always sees the session that started it).

**After:** `notify.sh` passes `ITERM_SESSION_ID` in the show payload as `iterm_session`. `_focus_terminal()` reads `req.get("iterm_session", "")` from the current request in the queue.

### 7. Approve/deny removes from queue, not full hide (`buddy.py`)

**Before:** Approve/deny called `do_hide()` which cleared everything.

**After:** `_resolve_current(decision)` writes the decision to the current request's pipe, pops that request from the queue, and either shows the next request or calls `do_hide()` if the queue is now empty.

### 8. Cancel signal for interrupt/ESC (`notify.sh`, `buddy.py`)

**Before:** EXIT trap called `buddy.py hide` (full hide).

**After:** EXIT trap sends `{"cmd": "cancel", "pipe": "<path>"}` to the daemon. `_on_cancel(pipe_path)` removes the matching request from the queue by pipe path. Works for ESC and SIGTERM. Also added PPID check in the wait loop to break out if the parent shell is killed.

### 9. PID-based staleness timer (`notify.sh`, `buddy.py`)

**Before:** No fallback if the EXIT trap failed to fire (e.g. SIGKILL, or transcript-mtime auto-approve where the cancel and the pipe-write race).

**After:** `notify.sh` passes `$$` (bash PID) in the payload as `notify_pid`. A 1-second `QTimer` in `ChipWidget` calls `_cleanup_stale_requests()`, which does `os.kill(pid, 0)` on each request's `notify_pid`. If the process no longer exists, the request is removed from the queue. This is the primary mechanism that restores v8 bidirectionality for the terminal-acceptance case.

### 10. Tab click doesn't expand chip (`buddy.py`)

**Before:** Clicking a tab also triggered `ChipWidget.mousePressEvent`, expanding the chip.

**After:** `_PillTab.mousePressEvent` calls `event.accept()` for left-click instead of `super()`, stopping propagation. `ChipWidget.mousePressEvent` also checks `self._nav_pill.geometry().contains(event.pos())` and returns early if the click landed in the nav row.

### 11. Nav row is fully transparent (`buddy.py`)

**Before:** `_NavPill` had a `paintEvent` drawing a risk-colored rounded rect, creating a "pill inside a pill" appearance.

**After:** `_NavPill` has no `paintEvent`. The container is transparent. Each `_PillTab` draws its own background and border independently.

---

## What Stayed the Same

* Risk classification logic (`classify.py`) — unchanged
* Risk color constants (`RISK_COLORS`)
* Expanded view buttons (Yes, Always allow, No, Go to session)
* Attention mode for `AskUserQuestion`
* `SpriteWidget` / `PillWidget` rendering
* Bob animation
* All-spaces pinning (`_pin_to_all_spaces`)
* `start-daemon.sh` lifecycle script

---

## Known Issues (logged for v10)

* Terminal-acceptance detection relies on the 1s staleness timer polling `notify_pid`. There is a ~1 second delay before the widget clears after terminal acceptance.
* If a request has no `notify_pid` (e.g. sent manually or by an older notify.sh), the staleness timer skips it and it must be cleared via the cancel signal or widget button.
* ESC detection via PPID check only works if Claude Code kills the intermediate shell process. If Claude Code uses SIGKILL directly on notify.sh, the EXIT trap doesn't fire and we rely on the staleness timer instead.
* "Go to session" focuses the terminal but doesn't scroll or highlight the pending approval line.
* Bob animation runs indefinitely — should stop after a few seconds when idle.
* Attention mode (AskUserQuestion) still shows a risk-colored border; should be neutral.
