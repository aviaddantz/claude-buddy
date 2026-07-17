# v31 — Session List Fixes

## What Changed

Follow-up fixes to the v30 session list feature.

### Swift menu bar toggle rebuild
- `swift build` was broken with CLT-only toolchain due to duplicate `SwiftBridging` module definition in two CLT files
- Workaround: compile with `swiftc` directly + VFS overlay that hides the conflicting `module.modulemap`
- Deploy: `rm -rf /Applications/Nudge.app` first (cp -R into existing dir doesn't replace binary), then copy + ad-hoc codesign

### Intent enrichment
- When double-clicking to open the session list, intents are now re-read from transcripts before building rows (catches sessions that started with an empty intent)
- Desktop sessions now schedule a 15s deferred re-read after `session_start` — picks up the first user message once they type it
- Session rows auto-rebuild when a new session starts while the list is visible

### Desktop session redirection (partial)
- Changed from `open -a "Claude" <cwd>` (landed on Cowork tab) to `claude://code/<session_id>` deep link
- `claude://` scheme is registered; `claude://code/<id>` is handled by the Electron main process
- **Known issue**: deep link opens the Code section but doesn't reliably navigate to the specific conversation. Needs further investigation — pinning for now.
