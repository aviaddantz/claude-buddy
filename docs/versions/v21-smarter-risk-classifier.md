# Claude Buddy v21 — Smarter Risk Classifier

## What Changed from v20

The risk classifier in `classify.py` was too blunt: read-only bash commands like `curl -s url | grep`, `ls`, `cat`, and `head` were all falling through to MEDIUM and showing a chip. Two patterns in HIGH_BASH_PATTERNS (`-f\b` and `--force\b`) were also causing false positives, flagging `curl -f`, `grep -f`, `tail -f`, and `npm install --force-reinstall` as HIGH. v21 fixes the false positives and adds explicit LOW detection for common read-only bash commands.

---

## Changes

### 1. Removed `-f\b` from HIGH_BASH_PATTERNS
**Before:** Any bash command containing `-f` as a flag was classified HIGH. This incorrectly flagged `curl -f` (fail-fast), `grep -f patterns.txt` (pattern file), `tail -f` (follow mode), `head -f`, `ls -f`.
**After:** `-f\b` removed. The dangerous cases it was meant to catch (`rm -f`, `git push -f`) are already covered by `\brm\b` and `git push.*-f\b` respectively.

### 2. Fixed `--force` to not match `--force-reinstall` / `--force-with-lease`
**Before:** `--force\b` matched any `--force` prefix including `--force-reinstall` (npm) and `--force-with-lease` (git safe force), classifying them HIGH.
**After:** Changed to `--force(?![a-z-])` — only matches bare `--force`, not compound flags.

### 3. Added `find -delete` to HIGH_BASH_PATTERNS
**Before:** `find . -name "*.tmp" -delete` classified as MEDIUM. `-delete` removes every matched file.
**After:** `\bfind\b.*\s-delete\b` added to HIGH patterns.

### 4. Added read-only curl detection (`_is_readonly_curl`)
**Before:** All `curl` commands classified MEDIUM.
**After:** `curl` without data/upload/method-override flags (`-d`, `--data`, `--data-binary`, `--data-raw`, `--data-urlencode`, `--upload-file`, `-X POST/PUT/DELETE/PATCH`, pipe to shell) → LOW. Write-capable curl → MEDIUM.

### 5. Added safe bash command whitelist (`_is_safe_bash`)
**Before:** Common read-only bash commands (`ls`, `cat`, `head`, `tail`, `echo`, `pwd`, `which`, `date`, `grep`, `find`, `diff`, `wc`, `sort`, `uniq`, `jq`, etc.) all fell through to MEDIUM.
**After:** If all segments of a command (split on `|`, `||`, `&&`, `;`) start with a command from `_SAFE_BASH_CMDS`, and the command has no output redirection, no `tee`, no pipe to a shell/interpreter, no `sed -i`, no `find -exec`, no `xargs` → LOW.

### 6. Fixed `&&` not being split in safe bash check
**Before:** `ls && npm install` was classified LOW because `&&` wasn't in the segment splitter — the whole string was treated as one segment starting with `ls`.
**After:** Splitter changed to `\s*(?:\|\|?|&&|;)\s*` to cover all four join operators.

---

## What Stayed the Same

* `find -exec` and `xargs` remain MEDIUM (not LOW) — both can run arbitrary subcommands, so safe-looking uses still get a chip
* All HIGH patterns for `rm`, `rmdir`, `sudo`, `dd`, `mkfs`, `shred`, `truncate`, `chmod NNN7`, `git push -f`, `git reset --hard` — unchanged
* MCP read/search/list/get → LOW rule — unchanged
* All LOW_TOOLS (non-bash tools: Read, Glob, Grep, WebFetch, etc.) — unchanged
* Fallback for anything unclassified → MEDIUM — unchanged
* Chip UI, daemon, notify.sh, auto-approve toggle — unchanged

## Known Issues (logged for v22)

* **`find -exec safeCmd`** — `find . -exec cat {} \;` is MEDIUM, not LOW. The exec check blocks all `-exec` uses regardless of subcommand.
* **`xargs safeCmd`** — same: `ls | xargs grep pattern` is MEDIUM. Xargs is blocked at the whitelist level unconditionally.
* **No subcommand introspection** — the classifier doesn't parse what `-exec` or `xargs` actually runs; it just treats both as "could be anything → not LOW".
* Carried from v20: menu bar icon legibility, no restart feedback, SMAppService in /Applications, `swift build` CLT bug, terminal approval delay.
