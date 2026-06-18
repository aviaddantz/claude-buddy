# Claude Buddy v20 — Auto-approve Toggle

## What Changed from v19

Every tool call — including reads, web fetches, and other low-risk operations — triggered a pill. During web searches this meant a new approval pill for each fetch, generating noise for operations that were never going to be denied. v20 adds silent auto-approval for low-risk tools, with a menu bar toggle to turn it off when you want full visibility.

---

## Changes

### 1. Auto-approve low-risk operations (`notify.sh`)
**Before:** Every PermissionRequest, regardless of risk level, created a named pipe, contacted the daemon, and showed a pill requiring user interaction.
**After:** If risk is `low` and `~/.nudge-autoapprove-disabled` does not exist, `notify.sh` returns `allow` immediately without touching the daemon. No pipe, no pill, no latency. Affects: WebFetch, Read, Glob, Grep, LS, TaskGet, TaskList, bash with cat/echo/pwd/which/date.

### 2. Menu bar toggle for auto-approve (`NudgeApp.swift`, `DaemonController.swift`)
**Before:** No way to configure auto-approve behavior from the UI.
**After:** "Auto-approve safe operations" toggle in the menu bar (above "Launch at Login"). When checked, low-risk tools are silently approved. When unchecked, low-risk tools go through the normal pill flow. State persists via `~/.nudge-autoapprove-disabled` flag file — present means disabled, absent means enabled. Default is enabled (no flag file).

---

## What Stayed the Same

* Medium and high risk operations still show a pill and require user action
* All pill UI, chip widget, sprite, approval flow — unchanged
* `buddy.py`, `classify.py`, `stop-daemon.sh` — unchanged
* Risk classification rules in `classify.py` — unchanged

## Known Issues (logged for v21)

* **Menu bar icon reads poorly at 16px** — the Claude silhouette is hard to distinguish at small sizes; a purpose-designed minimal template icon would help
* **No visual feedback on Resume/Restart** — status label says "Inactive" for ~2s while daemon initializes
* **SMAppService requires /Applications** — Login Item registration silently fails if app is run from dev directory
* **`swift build` / `swift package resolve` broken** — CLT 16.4 bug; Swift changes require `bash bundle.sh` directly
* **Terminal approval delay** — (carried from v17) pill stays until tool completes
