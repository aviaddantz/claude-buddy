# Claude Buddy v24 — Test Nudge Bypass

## What Changed from v23

The "Test Nudge" menu bar button stopped working after v21 introduced auto-approve for low-risk operations. `curl` is now classified as LOW risk and silently approved, so clicking "Test Nudge" produced no visible chip. v24 adds a `_test: true` flag to the test payload that bypasses auto-approve unconditionally, so the chip always appears when triggered from the menu bar regardless of the auto-approve setting.

---

## Changes

### 1. `_test: true` flag in test payload (`DaemonController.swift`)
**Before:** Test payload was `{"tool_name":"Bash","tool_input":{"command":"curl ..."},...}` — identical to a real hook payload. With auto-approve enabled, the curl command was silently approved and no chip appeared.
**After:** `"_test":true` added to the payload. This field is not part of the Claude Code hook spec; it's a Buddy-internal signal.

### 2. `IS_TEST` check in auto-approve gate (`notify.sh`)
**Before:** Auto-approve fired whenever `RISK=low` and the disabled flag file was absent.
**After:** `IS_TEST` extracted from the hook JSON. Auto-approve is skipped when `_test` is `true`, so the chip always shows for test triggers. Real hooks never include `_test`, so normal behavior is unchanged.

### 3. "Test Nudge" menu bar button (`NudgeApp.swift`)
Wired up in this cycle alongside the Swift changes — button calls `DaemonController.testNudge()` and is disabled when the daemon is not running.

---

## What Stayed the Same

* Auto-approve logic for real hooks — unchanged, `_test` field is never present in real Claude Code payloads
* Risk classification, chip UI, approve/deny flow — unchanged
* `classify.py`, `buddy.py`, `start-daemon.sh` — unchanged

## Known Issues (logged for v25)

* **Swift changes require `bundle.sh` rebuild** — `DaemonController.swift` and `NudgeApp.swift` changes don't take effect until the app is rebuilt via `bash bundle.sh`. The `notify.sh` change is live immediately.
* Carried from v23: space observer never removed on daemon restart (benign); "Open Claude" doesn't navigate to specific conversation; `TERM_PROGRAM` not set in all terminals; menu bar icon legibility; SMAppService in /Applications; `swift build` CLT bug.
