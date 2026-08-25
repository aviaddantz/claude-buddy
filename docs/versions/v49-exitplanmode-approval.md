# v49 — ExitPlanMode now shows a real approval pill

## Problem

When Claude proposed a plan, the widget stayed stuck showing the "thinking"
rope animation instead of an approval pill — even though Claude Code's own
native UI was sitting there waiting on an Accept/Reject decision.

Root cause: `classify.py` classified `exitplanmode` as a low-risk tool
(`LOW_TOOLS`), so `notify.sh` took its silent auto-approve shortcut and
returned `{"behavior": "allow"}` without ever calling the daemon's `show`
command. Buddy had no idea a decision was pending — it just kept showing
whatever state it was already in from the last `PreToolUse` (`thinking_start`).
Meanwhile Claude Code's plan-mode UI isn't fully bypassed by the hook's allow
decision, so the native Accept/Reject bar stayed up regardless.

This meant the single highest-stakes checkpoint in a session — deciding
whether to let Claude execute a proposed plan — was the one decision Buddy
silently skipped.

## Fix

- Removed `exitplanmode` from `LOW_TOOLS` in `classify.py`. It now falls
  through to the default `medium` risk, so it goes through the full pill
  flow with Approve/Deny like any other approval.
- Added `"plan"` to `extract_value`'s `FIELD_ORDER` and mapped
  `exitplanmode` → `"Plan"` in the intent labels, so the pill shows
  `Plan: <first line of the proposed plan>…` instead of falling back to a
  bare tool name.

## Note

`AskUserQuestion` is also in `LOW_TOOLS` with `mode: "attention"`, and
`notify.sh`'s auto-approve shortcut has no mode exception — so the same
bug class could in principle affect it too. Not confirmed broken (it may
never actually route through `PermissionRequest` in practice), but worth
checking if attention-mode pills for AskUserQuestion stop appearing.
