#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SOCKET_PATH="/tmp/claude-buddy.sock"
MODE="${1:-approval}"

_send_socket_cmd() {
    python3 -c "
import socket, json, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(sys.argv[1])
    s.sendall(sys.argv[2].encode())
    s.close()
except Exception:
    pass
" "$SOCKET_PATH" "$1" 2>/dev/null || true
}

if [ "$MODE" = "session_start" ]; then
    _send_socket_cmd '{"cmd":"session_start"}'
    exit 0
fi

if [ "$MODE" = "session_end" ] || [ "$MODE" = "done" ]; then
    _send_socket_cmd '{"cmd":"session_end"}'
    exit 0
fi

if [ "$MODE" = "idle_on" ]; then
    touch "$HOME/.nudge-idle-visible"
    _send_socket_cmd '{"cmd":"set_idle_visible","value":true}'
    exit 0
fi

if [ "$MODE" = "idle_off" ]; then
    rm -f "$HOME/.nudge-idle-visible"
    _send_socket_cmd '{"cmd":"set_idle_visible","value":false}'
    exit 0
fi

if [ "$MODE" != "approval" ]; then
    exit 0
fi

PIPE="/tmp/claude-buddy-decision-$$"
echo "[notify.sh $$] started mode=$MODE" >> /tmp/claude-buddy.log
# On exit: always tell daemon to remove this request from queue (idempotent — no-op if already resolved via widget)
trap 'echo "[notify.sh $$] SIGTERM received" >> /tmp/claude-buddy.log' TERM
trap '
  _PIPE="$PIPE"
  echo "[notify.sh $$] EXIT trap fired, removing pipe $_PIPE" >> /tmp/claude-buddy.log
  rm -f "$_PIPE"
  python3 -c "
import socket, sys, json
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(sys.argv[2])
    s.sendall(json.dumps({\"cmd\": \"cancel\", \"pipe\": sys.argv[1]}).encode())
    s.close()
except Exception:
    pass
" "$_PIPE" "$SOCKET_PATH" 2>/dev/null || true
' EXIT

# Clean up orphaned decision pipes from dead processes
for _p in /tmp/claude-buddy-decision-*; do
    [ -e "$_p" ] || continue
    _pipe_pid="${_p##*-}"
    if ! kill -0 "$_pipe_pid" 2>/dev/null; then
        rm -f "$_p"
    fi
done

# Read PermissionRequest JSON from stdin
HOOK_JSON=$(cat)
echo "[notify.sh $$] got HOOK_JSON len=${#HOOK_JSON} tool=$(echo "$HOOK_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','?'))" 2>/dev/null)" >> /tmp/claude-buddy.log
echo "$HOOK_JSON" >> /tmp/claude-buddy.log

TRANSCRIPT=$(echo "$HOOK_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('transcript_path', ''))
except Exception:
    print('')
" 2>/dev/null || echo "")

TOOL_NAME=$(echo "$HOOK_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('tool_name', 'Tool'))
except Exception:
    print('Tool')
" 2>/dev/null || echo "Tool")

TOOL_INPUT=$(echo "$HOOK_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(json.dumps(d.get('tool_input', '')))
except Exception:
    print('\"\"')
" 2>/dev/null || echo '""')

CWD=$(echo "$HOOK_JSON" | python3 -c "
import sys, json, os
try:
    d = json.load(sys.stdin)
    cwd = d.get('cwd', '')
    print(os.path.basename(cwd) if cwd else '')
except Exception:
    print('')
" 2>/dev/null || echo "")

# Extract permission_suggestions (for "always allow" support)
SUGGESTIONS=$(echo "$HOOK_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    s = d.get('permission_suggestions', [])
    print(json.dumps(s))
except Exception:
    print('[]')
" 2>/dev/null || echo "[]")

# Classify risk + intent locally (no API needed)
CLASSIFY_SCRIPT="$SCRIPT_DIR/classify.py"
CLASSIFICATION=$(echo "$HOOK_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(json.dumps({'tool': d.get('tool_name','Tool'), 'input': d.get('tool_input',''), 'file_path': ''}))
" | python3 "$CLASSIFY_SCRIPT" 2>/dev/null || echo "{}")

INTENT=$(echo "$CLASSIFICATION" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('intent', 'Running a command'))
except Exception:
    print('Running a command')
" 2>/dev/null || echo "Running a command")

RISK=$(echo "$CLASSIFICATION" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    r = d.get('risk', 'medium')
    print(r if r in ('low', 'medium', 'high') else 'medium')
except Exception:
    print('medium')
" 2>/dev/null || echo "medium")

MODE=$(echo "$CLASSIFICATION" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('mode', 'approval'))
except Exception:
    print('approval')
" 2>/dev/null || echo "approval")

IS_TEST=$(echo "$HOOK_JSON" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print('true' if d.get('_test') else 'false')
except Exception:
    print('false')
" 2>/dev/null || echo "false")

echo "[notify.sh $$] classified: risk=$RISK intent=$INTENT mode=$MODE is_test=$IS_TEST" >> /tmp/claude-buddy.log

# Auto-approve low-risk operations without showing any pill (unless disabled via menu bar or this is a test)
if [ "$RISK" = "low" ] && [ ! -f "$HOME/.nudge-autoapprove-disabled" ] && [ "$IS_TEST" != "true" ]; then
    echo "[notify.sh $$] auto-approving low-risk tool=$TOOL_NAME" >> /tmp/claude-buddy.log
    rm -f "$PIPE"
    echo '{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}'
    exit 0
fi

# Create named pipe for decision response
rm -f "$PIPE"
mkfifo "$PIPE"

# Build and send JSON payload to buddy daemon (includes ITERM_SESSION_ID for correct terminal focus)
ITERM_SESSION="${ITERM_SESSION_ID:-}"
TERM_PROG="${TERM_PROGRAM:-}"
PAYLOAD=$(python3 -c "
import json, sys
tool_input = json.loads(sys.argv[11]) if sys.argv[11] else {}
# Strip large fields (e.g. Write tool 'content') — only need command/path for display
if isinstance(tool_input, dict):
    tool_input = {k: v for k, v in tool_input.items() if k != 'content'}
print(json.dumps({
    'cmd': 'show',
    'tool': sys.argv[1],
    'intent': sys.argv[2],
    'risk': sys.argv[3],
    'pipe': sys.argv[4],
    'cwd': sys.argv[5],
    'suggestions': json.loads(sys.argv[6]),
    'mode': sys.argv[7],
    'iterm_session': sys.argv[8],
    'notify_pid': int(sys.argv[9]),
    'term_program': sys.argv[10],
    'tool_input': tool_input,
}))
" "$TOOL_NAME" "$INTENT" "$RISK" "$PIPE" "$CWD" "$SUGGESTIONS" "$MODE" "$ITERM_SESSION" "$$" "$TERM_PROG" "$TOOL_INPUT" 2>/dev/null)

echo "[notify.sh $$] sending to daemon buddy_connected=?" >> /tmp/claude-buddy.log
BUDDY_CONNECTED=false
python3 -c "
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2)
s.connect('/tmp/claude-buddy.sock')
s.sendall(sys.argv[1].encode())
s.close()
" "$PAYLOAD" 2>/dev/null && BUDDY_CONNECTED=true
echo "[notify.sh $$] buddy_connected=$BUDDY_CONNECTED" >> /tmp/claude-buddy.log

if [ "$BUDDY_CONNECTED" = false ] && [ ! -f /tmp/claude-buddy-disabled ]; then
    echo "[notify.sh $$] daemon not reachable, auto-starting..." >> /tmp/claude-buddy.log
    bash "$SCRIPT_DIR/start-daemon.sh" 2>/dev/null
    sleep 1.5
    python3 -c "
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2)
s.connect('/tmp/claude-buddy.sock')
s.sendall(sys.argv[1].encode())
s.close()
" "$PAYLOAD" 2>/dev/null && BUDDY_CONNECTED=true
fi

if [ "$BUDDY_CONNECTED" = false ]; then
    echo "[notify.sh $$] daemon unreachable after auto-start attempt, falling through to allow" >> /tmp/claude-buddy.log
    rm -f "$PIPE"
    echo '{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}'
    exit 0
fi

# Wait for user decision — poll with short timeout so we can detect if
# parent was killed or reparented
echo "[notify.sh $$] entering wait loop ppid=$PPID" >> /tmp/claude-buddy.log
HOOK_PPID="$PPID"
DECISION=""
while [ -z "$DECISION" ]; do
    DECISION=$(timeout 0.3 cat "$PIPE" 2>/dev/null || true)
    if [ -z "$DECISION" ]; then
        # ESC / abort: parent shell killed by Claude Code
        if ! kill -0 "$HOOK_PPID" 2>/dev/null; then
            echo "[notify.sh $$] breaking: ppid=$HOOK_PPID dead" >> /tmp/claude-buddy.log
            break
        fi
        # Reparented: parent was killed, we got adopted by launchd/init
        CURRENT_PPID=$(ps -p $$ -o ppid= 2>/dev/null | tr -d ' ')
        if [ -n "$CURRENT_PPID" ] && [ "$CURRENT_PPID" != "$HOOK_PPID" ]; then
            echo "[notify.sh $$] breaking: reparented from $HOOK_PPID to $CURRENT_PPID" >> /tmp/claude-buddy.log
            break
        fi
        # Note: transcript mtime check removed -- it false-triggered constantly because
        # Claude Code writes to the transcript during normal execution, causing
        # immediate auto-approve before the user could interact with the widget.
    fi
done
rm -f "$PIPE"

if [ "$DECISION" = "deny" ]; then
    echo '{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "Denied via Claude Buddy"}}}'
elif [ "$DECISION" = "always_allow" ]; then
    python3 -c "
import json, sys
suggestions = json.loads(sys.argv[1])
updated = suggestions if suggestions else []
print(json.dumps({'hookSpecificOutput': {'hookEventName': 'PermissionRequest', 'decision': {'behavior': 'allow', 'updatedPermissions': updated}}}))
" "$SUGGESTIONS"
else
    echo '{"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}}'
fi
