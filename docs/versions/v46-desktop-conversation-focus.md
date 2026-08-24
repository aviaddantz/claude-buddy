# v46 — Clicking a desktop row opens the conversation

v44 concluded that clicking a desktop session row could only bring Claude to the front,
because no `claude://` URL opens a specific local conversation. The URL half of that was
right. The conclusion was wrong: the app's own sidebar is reachable through the
accessibility API, so the row can be pressed the way a person would press it.

## Why URLs really are a dead end

Worth recording so nobody retries it. The `claude://` handler is a switch over
`Hotkey | Login | ClaudeAI | Preview | Cowork | Code | DebugHandoff`. Two cases could
plausibly carry a conversation id, and neither does:

* **`Cl.Code`** resolves the first path segment then gates it on
  `function iM(e){ return /^(cse|session)_/.test(e) }`. Local conversations are
  `local_<uuid>`, so they can never match. Anything else falls through to a `/new` check
  and logs `unrecognized code path`.
* **`Cl.Cowork`** — the internally correct name for these conversations — handles only
  `/shared-artifact?uuid=…` and `/new`. There is no case for an existing session.

`claude://resume?session=<uuid>` is separately useless: `importCliSession` throws
`Cannot import CLI session: the id names a live Cowork session`, and on success it would
duplicate rather than focus.

## What works

Claude is an Electron app, and Electron publishes its web content to the accessibility
tree once a client asks. Setting `AXManualAccessibility` on the application element exposes
the whole sidebar:

```
AXWebArea  Claude
  AXGroup                              Sidebar
    AXButton  Idle Monday dashboard access
      AXImage                          Idle
      AXStaticText                     Monday dashboard access
      AXPopUpButton                    More options for Monday dashboard access
    AXButton  Idle Brainstorm skill
    ...
```

Each conversation is an `AXButton` labelled `<status> <conversation name>`, and `AXPress`
on it navigates. Implementation, in `buddy.py`:

1. Activate Claude.
2. Set `AXManualAccessibility` on its application element.
3. Depth-first search for the `AXButton` whose title contains the conversation name,
   skipping any element described `More options for …` so the per-row overflow menu cannot
   win the match.
4. `AXPress` it.

The title comes from the desktop record, which is the same string the sidebar renders, so
matching is reliable.

## Details that mattered

**Verification signal.** Every URL attempt was judged against the record's `lastFocusedAt`,
and none of them moved it. The accessibility press does: `1787567762991 → 1787582115857`.
That is the whole reason to trust this and not the URL theories.

**The window is not in the tree until Claude is frontmost.** With no window open, the tree
is 199 nodes of menu bar and nothing else. This is why the search runs in a retry loop of
up to 12 × 150 ms after activation rather than failing on the first pass. Once the window
is up, finding the row takes ~5 ms and visits ~38 nodes.

**It runs on a background thread.** Activation plus the retry loop can take up to 2
seconds, which would freeze Qt on the main thread — the same constraint that already
applies to the decision-pipe write.

**No compiled helper.** The API is reached with `ctypes` against CoreFoundation and
ApplicationServices, loaded lazily and wrapped so a failure degrades to "just activate
Claude". A Swift helper would have needed a build step, a binary in the repo and
code signing. pyobjc was not an option: `Quartz` and `ApplicationServices` are not
installed, only `AppKit`.

**A borrowed-reference bug worth remembering.** `CFArrayGetValueAtIndex` returns borrowed
references. Releasing the children array before using the pointers silently truncated the
walk to 2 nodes rather than crashing. Each child is now `CFRetain`ed first.

**Accessibility permission.** The press needs the calling process to be trusted. Verified
`AXIsProcessTrusted() == true` for the daemon in its real launch context (setsid'd,
reparented to launchd, per v45). If that ever stops being true, the code logs the exact
System Settings path and falls back to activating Claude.

## Known limitation

Conversations are matched by title, and the sidebar shows nothing else, so two conversations
with the same auto-generated title are indistinguishable. There are currently two called
"Meeting with Zac Peterson" in different folders. The first match wins, and since the
sidebar is ordered by recency that is the more recent one.

## Files

`buddy.py` only.
