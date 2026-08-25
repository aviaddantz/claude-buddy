# v48 — Stop dragging the sprite from stealing app focus

## Problem

Clicking the sprite to drag the widget made macOS activate Claude Buddy as the
frontmost app, since any click on a window belonging to an app activates that
app regardless of window flags. This pulled keyboard focus away from whatever
app (terminal, Claude Desktop, etc.) the user was actually working in, so after
repositioning the widget they had to click back into their previous app before
they could keep typing.

Setting `Qt.WindowType.WindowDoesNotAcceptFocus` did not fix this — that flag
only affects key-window status, not the separate app-activation step Cocoa
performs before delivering the mouse event at all.

## Fix

`ChipWidget` now registers an `NSWorkspaceDidActivateApplicationNotification`
observer (`_watch_foreground_app`) that records whichever app was frontmost
immediately before Buddy itself became active. When a sprite drag ends
(`mouseReleaseEvent`), `_restore_previous_app` reactivates that recorded app via
`activateWithOptions_(NSApplicationActivateIgnoringOtherApps)`, handing focus
back once the reposition is done.

## Why this approach

Preventing the activation outright would require swapping the underlying
`NSWindow` for an `NSPanel` with the `nonactivatingPanel` style mask, which Qt
doesn't expose and PyQt can't easily retrofit onto an existing `QWidget`.
Letting the activation happen and then handing focus back afterward reuses the
same AppKit-notification pattern already used elsewhere in the file (the
space-change observer in `_pin_to_all_spaces`), and fixes the actual symptom
without touching window class internals.
