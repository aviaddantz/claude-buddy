# Claude Buddy v7 — Generic Classifier

## What Changed from v6

v6 had a 375-line `classify.py` full of per-tool regex patterns that would always have gaps — any unrecognized tool fell to "Using ToolName" which conveyed nothing. v7 replaces the entire classifier with a ~120-line generic extractor: tool name + most relevant input field, formatted by field type. No per-tool pattern matching. Also adds a distinct "attention" mode for `AskUserQuestion` — instead of showing Allow/Deny, the widget shows only "Go to session" which approves and focuses the terminal in one click.

---

## Changes

### 1. Generic intent extractor (classify.py full rewrite)

**Before:** 375 lines of regex per tool. Gaps meant any new tool fell to `"Using ToolName"`. Long commands like `pip3 install faker --dry-run` were classified as `"Installing faker"` — specific but brittle.

**After:** Single extraction algorithm:
* Parse tool name — MCP tools (`mcp__server__tool`) are cleaned to `Server action` format
* Extract the most meaningful field from `tool_input` in priority order: `command > question > query > description > url > file_path > path > pattern > text > prompt`
* Format by field type: `file_path` → basename, `url` → domain, `command` → raw with absolute paths collapsed to basename
* Truncate to 42 chars

Result: `Bash: pip3 install faker --dry-run`, `Edit: classify.py`, `Slack search: delete resource toast`, `Ask: Which sprint?`

### 2. MCP tool name cleaning

**Before:** `mcp__plugin_slack_slack__slack_search_public` → `"Reading Slack"` (regex match on "slack" + "search")

**After:** Generic parser strips `plugin_`, `_v2`, `_mcp` suffixes, deduplicates repeated words, titlecases the server name, strips redundant server prefix from action name. Result: `Slack search_public` → `Slack search public`.

### 3. Risk classification simplified

**Before:** Risk was derived from per-tool regex patterns spread across 375 lines.

**After:** Three rules only:
* `high`: Bash commands matching a short list of destructive patterns (rm, --force, --hard, sudo, dd, mkfs, truncate, shred)
* `low`: Fixed set of read-only tool names + MCP tools whose action contains read/search/list/get
* `medium`: everything else

### 4. AskUserQuestion — attention mode

**Before:** `AskUserQuestion` fell to default, showed "Using AskUserQuestion" with Allow/Deny buttons. User had to approve from widget then go to terminal to actually answer the question.

**After:** `classify.py` outputs `mode: "attention"` for `AskUserQuestion`. Widget detects this in `_expand()` and hides Allow/Deny/Always Allow — shows only "Go to session" styled as a solid CTA. Clicking it approves + focuses terminal in one action.

`notify.sh` now extracts and forwards the `mode` field through the payload.

### 5. `_on_go_session` method

**Before:** "Go to session" button called `_focus_terminal()` only — no approval, just navigation.

**After:** `_on_go_session()` calls `_write_decision("approve", ...)` then `_focus_terminal()` then `do_hide()`. In attention mode this is the complete decision flow.

---

## What Stayed the Same

* All widget visual design from v6 (colors, button styles, layout)
* Named pipe decision flow
* `notify.sh` structure — only added `MODE` extraction
* `buddy.py` socket protocol
* All-spaces pinning, bob animation, click-to-expand

---

## Known Issues (logged for v8)

* MCP action name formatting still rough — `search_public_and_private` becomes `search public and private` which is verbose
* Bash command truncation cuts from the right — for long commands the meaningful part (package name, target file) may be lost
* `AskUserQuestion` attention mode pill still shows risk border (yellow/orange) — should be neutral since it's not a risk decision
* No hover feedback on compact pill border
* Bob animation runs continuously — should stop after ~3s
