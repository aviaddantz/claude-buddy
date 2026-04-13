# Claude Buddy v4 — Specific Intent Copy & Stale Lock Fix

## What Changed from v3

v3 had the approval flow working correctly but the pre-hover chip text was too generic:
- "Reading files" for any read tool
- "Running a command" for most bash commands
- "Git operation" for all git subcommands
- "Installing packages" with no package name
- No distinction between editing and creating a file

v4 makes the chip copy specific enough to decide whether to hover without needing to expand.

## New: Specific Intent Strings

The classification logic moved from an inline bash heredoc in `notify.sh` into a dedicated `classify.py` file. This fixed a shell parsing bug (single quotes inside `$()` heredocs were being misinterpreted by bash).

**Pattern:** verb + specific target, always plain English. File paths show last two segments for context (e.g. `nudge/buddy.py` not just `buddy.py`).

| Case | Before | After |
|---|---|---|
| Read tool | "Reading files" | "Reading nudge/buddy.py" |
| Edit tool | "Editing buddy.py" | "Editing nudge/buddy.py" |
| Write tool | "Editing {file}" | "Creating config.json" |
| git status/log/diff | "Git operation" | "Checking git status" |
| git commit | "Git operation" | "Committing: Fix chip layout..." |
| git push | "Git operation" | "Pushing to remote" |
| git add | "Git operation" | "Staging files" |
| npm/pip install | "Installing packages" | "Installing express" |
| curl/wget | "Fetching from network" | "Fetching httpbin.org" |
| rm | "Deleting files" | "Deleting test-a.txt" |
| mkdir | "File system change" | "Creating test-dir" |
| cp | "File system change" | "Copying to backup.sh" |
| mv | "File system change" | "Moving to archive/" |
| python3 script.py | "Running a command" | "Running buddy.py" |
| python3 -c "..." | "Running a command" | "Running Python script" |
| npm run X | "Running a command" | "Running npm build" |
| ls /path | "Reading system info" | "Listing tmp/nudge" |
| cat /path | "Reading system info" | "Reading nudge/buddy.py" |
| pwd, which, date | "Reading system info" | "Reading system info" |
| Agent | "Spawning subagent" | "Spinning up a subagent" |
| Generic bash | "Running a command" | "Running: binary-name" |

**Commit message truncation:** truncated at last full word before 25 chars with "..."

## Bug Fix: /dev/null False Positive

`2>/dev/null` (redirecting stderr to /dev/null) was matching the high-risk pattern `> /dev/` and showing "Irreversible system change" for safe commands like `python3 buddy.py --help 2>/dev/null`. Fixed with a negative lookahead: `> /dev/(?!null)`.

## New: Internal Tool Suppression

Claude Code's internal tools (ExitPlanMode, TaskCreate, TaskUpdate, ToolSearch, etc.) were showing the widget unnecessarily. These are now in the auto-approve list — they get low risk classification and the widget doesn't appear.

## Stale Lock Fix

The macOS spinlock on `/tmp/claude-buddy.lock` was getting stuck when:
- The user approved from the terminal instead of the widget (EXIT trap in notify.sh didn't fire)
- A session crashed mid-approval

Two fixes:
1. **Dead PID detection** — if the lock-holding PID no longer exists, clear the lock immediately
2. **10-second timeout** — if the lock can't be acquired after 10s regardless, force-clear and proceed
3. **Orphaned pipe cleanup** — on each notify.sh invocation, any `/tmp/claude-buddy-decision-*` pipes from dead PIDs are removed

## UI Changes

**Chip layout: horizontal → vertical**
Sprite moved from left of text to centered above it. Intent and project label are stacked below with tight spacing (1px gap, fixed heights to eliminate Qt default padding).

**Project label**
CWD now shown as "project: nudge" instead of just "nudge".

**"Go to session" → "Open Claude Code"**
Button renamed. Behavior changed: clicking it now only focuses the terminal, it no longer auto-approves the request. Approve/Deny remain as separate buttons.

## Files Changed

| File | Change |
|---|---|
| `notify.sh` | Replaced inline Python heredoc with call to `classify.py`; added lock timeout + pipe cleanup |
| `classify.py` | New file — all classification logic |
| `buddy.py` | Vertical chip layout; project label prefix; "Open Claude Code" button focus-only |

## Architecture (unchanged from v3)

```
notify.sh  →  classify.py  →  [Unix socket /tmp/claude-buddy.sock]  →  buddy.py daemon
buddy.py   →  [named pipe /tmp/claude-buddy-decision-$$]  →  notify.sh
```
