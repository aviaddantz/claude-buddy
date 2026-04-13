#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-approval}"

if [ "$MODE" != "approval" ]; then
    python3 "$SCRIPT_DIR/buddy.py" hide 2>/dev/null || true
    exit 0
fi

SOCKET_PATH="/tmp/claude-buddy.sock"
PIPE="/tmp/claude-buddy-decision-$$"
echo "[notify.sh $$] started mode=$MODE" >> /tmp/claude-buddy.log
# On exit: always tell daemon to remove this request from queue (idempotent — no-op if already resolved via widget)
trap '
  _PIPE="$PIPE"
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

# Create named pipe for decision response
rm -f "$PIPE"
mkfifo "$PIPE"

# Build and send JSON payload to buddy daemon (includes ITERM_SESSION_ID for correct terminal focus)
ITERM_SESSION="${ITERM_SESSION_ID:-}"
PAYLOAD=$(python3 -c "
import json, sys
tool_input = json.loads(sys.argv[10]) if sys.argv[10] else {}
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
    'tool_input': tool_input,
}))
" "$TOOL_NAME" "$INTENT" "$RISK" "$PIPE" "$CWD" "$SUGGESTIONS" "$MODE" "$ITERM_SESSION" "$$" "$TOOL_INPUT" 2>/dev/null)

python3 -c "
import socket, sys
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect('/tmp/claude-buddy.sock')
    s.sendall(sys.argv[1].encode())
    s.close()
except Exception as e:
    sys.stderr.write(f'[notify] buddy connect failed: {e}\n')
" "$PAYLOAD" 2>/dev/null || true

# Snapshot transcript mtime so we can detect when Claude Code moves on
TRANSCRIPT_MTIME=""
if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ]; then
    TRANSCRIPT_MTIME=$(stat -f "%m" "$TRANSCRIPT" 2>/dev/null || echo "")
fi

# Wait for user decision — poll with 1s timeout so we can detect if Claude Code
# moved on via transcript file changed or parent process gone (ESC)
HOOK_PPID="$PPID"
DECISION=""
while [ -z "$DECISION" ]; do
    DECISION=$(timeout 1 cat "$PIPE" 2>/dev/null || true)
    if [ -z "$DECISION" ]; then
        # ESC / abort: parent shell killed by Claude Code
        if ! kill -0 "$HOOK_PPID" 2>/dev/null; then
            break
        fi
        # Check transcript mtime: Claude Code wrote new content (terminal answered)
        if [ -n "$TRANSCRIPT" ] && [ -f "$TRANSCRIPT" ] && [ -n "$TRANSCRIPT_MTIME" ]; then
            CURRENT_MTIME=$(stat -f "%m" "$TRANSCRIPT" 2>/dev/null || echo "")
            if [ -n "$CURRENT_MTIME" ] && [ "$CURRENT_MTIME" != "$TRANSCRIPT_MTIME" ]; then
                DECISION="approve"
            fi
        fi
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
