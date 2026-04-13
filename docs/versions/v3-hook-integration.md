# Claude Buddy v3 — Hook Integration & Mirror Buttons

## What Changed from v2

v2 had the chip UI working visually but the approval flow was broken:
- `notify.sh` crashed immediately on macOS because `flock` (Linux-only) was used
- Even when the widget showed, clicking Approve did nothing because the hook output format was wrong
- Claude Code was ignoring the hook response and falling back to its own built-in prompt

v3 fixes all of that and adds proper mirroring of the built-in prompt options.

## Fixes

**`flock` → macOS spinlock**
`flock` doesn't exist on macOS. Replaced with a `set -C` noclobber spinlock that serializes concurrent `notify.sh` processes so they queue instead of racing.

**Wrong hook output format**
Claude Code's `PermissionRequest` hook requires:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": { "behavior": "allow" }
  }
}
```
v2 was returning `{"decision": "allow"}` which Claude Code silently ignored, causing it to show its own built-in prompt every time.

## New: Mirror Buttons

The widget now mirrors the exact options Claude Code's built-in prompt offers:

| Button | Behavior |
|--------|----------|
| ✓ Allow | One-time approval |
| ★ Always Allow | Approves + writes a permanent rule via `updatedPermissions` |
| ✓ Go to session | Approves + focuses the terminal |
| ✕ Deny | Blocks the command, returns reason to Claude |

**Always Allow** is only shown when Claude Code sends `permission_suggestions` in the hook payload -- meaning it's only offered when the built-in prompt would have offered it too.

## How Always Allow Works

`notify.sh` extracts `permission_suggestions` from the hook JSON and passes it to the daemon. When the user clicks "★ Always Allow", the widget writes `always_allow` to the decision pipe. `notify.sh` then echoes back the suggestions as `updatedPermissions` in the hook response, which Claude Code writes as a permanent rule to `localSettings`.

## Architecture (unchanged from v2)

```
notify.sh  →  [Unix socket /tmp/claude-buddy.sock]  →  buddy.py daemon
buddy.py   →  [named pipe /tmp/claude-buddy-decision-$$]  →  notify.sh
```

Locking: `/tmp/claude-buddy.lock` (macOS spinlock via `set -C`)
