# Claude Buddy v52 — Auto-approve Link Crash Fix

## What Changed from v51

The daemon was crashing silently on every pill render since v51 introduced the auto-approve link label in `_SessionPill.__init__`. The function `_autoapprove_link_text` was called but never defined, causing a `NameError` traceback on every `do_show()` call. The widget would vanish without logging any visible error to the user.

---

## Changes

### 1. Defined missing `_autoapprove_link_text` helper
**Before:** `_autoapprove_link_text(req)` was called at line 995 inside `_SessionPill.__init__` but did not exist anywhere in the file. Every pill render raised `NameError: name '_autoapprove_link_text' is not defined`, crashing the daemon silently.

**After:** Function defined as a module-level helper just above `_SessionPill`. For `Bash` tools it returns `Always allow "<first_word>" commands`; for other tools it returns `Always allow <tool_name>`.

## What Stayed the Same

* Auto-approve rule storage logic (`_add_autoapprove_rule`)
* Risk classification
* Pill layout and expand/collapse behavior
* Session title display (v51)
* New session window reuse fix (v51)

## Known Issues (logged for v53)

* No known issues introduced this cycle.
