# Claude Code Hook Setup

## Overview

Claude Buddy integrates with Claude Code via hook commands wired into `~/.claude/settings.json`. These hooks enable the buddy daemon to track session lifecycle and respond to permission requests.

## Configuration

### SessionStart Hook

When a Claude Code session starts, the following command is executed:

```bash
bash ~/Development/nudge/notify.sh session_start
```

This signals the daemon to display the idle sprite widget.

### SessionEnd Hook

When a Claude Code session ends, the following command is executed:

```bash
bash ~/Development/nudge/notify.sh session_end
```

This signals the daemon to hide the idle sprite widget.

### PermissionRequest Hook (existing)

When Claude Code requests a tool permission, the following command is executed:

```bash
bash ~/Development/nudge/notify.sh approval
```

This signals the daemon to show the approval pill widget with risk classification and intent information.

## Installation

Edit `~/.claude/settings.json` and add the following entries to the hooks object:

**SessionStart:**
```json
"SessionStart": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "/Users/aviadda/.local/bin/axcli _session-start"
      }
    ]
  },
  {
    "hooks": [
      {
        "type": "command",
        "command": "bash ~/Development/nudge/notify.sh session_start"
      }
    ]
  }
]
```

**SessionEnd:**
```json
"SessionEnd": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "/Users/aviadda/.local/bin/axcli _session-end"
      }
    ]
  },
  {
    "hooks": [
      {
        "type": "command",
        "command": "bash ~/Development/nudge/notify.sh session_end"
      }
    ]
  }
]
```

Note: The existing axcli hooks are preserved. New hook entries are added as array elements.

## Testing

1. Ensure the daemon is running:
   ```bash
   bash ~/Development/nudge/start-daemon.sh
   ```

2. Start a new Claude Code session in any directory:
   ```bash
   claude
   ```

3. Verify the idle sprite appears within 1-2 seconds

4. End the session (`/exit` or Ctrl+C) and verify the sprite disappears

## Architecture

The notify.sh script communicates with the daemon process via Unix socket at `/tmp/claude-buddy.sock`, sending session lifecycle events that update the widget display state.
