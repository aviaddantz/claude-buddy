#!/usr/bin/env python3
"""
Generic intent extractor for Claude Buddy.
Reads JSON from stdin: {"tool": "Bash", "input": {...}, "file_path": ""}
Prints JSON to stdout: {"intent": "...", "risk": "low|medium|high"}

No per-tool regex pattern matching — just tool name + most relevant input field.
"""
import json, os, re, sys

data = json.load(sys.stdin)
tool = data.get("tool", "Tool")
raw_input = data.get("input", "")

try:
    inp = json.loads(raw_input) if isinstance(raw_input, str) else raw_input
    if not isinstance(inp, dict):
        inp = {}
except Exception:
    inp = {}

tool_lower = tool.lower()


def truncate(s, limit=42):
    s = str(s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    boundary = cut.rfind(" ")
    if boundary > 0:
        return s[:boundary] + "…"
    return s[:limit - 1] + "…"


def basename(path):
    return os.path.basename(str(path).rstrip("/\\")) or str(path)


def domain(url):
    url = str(url).strip().strip("\"'")
    url = re.sub(r"^https?://", "", url)
    return url.split("/")[0].split("?")[0].rstrip("\"'") or url


def clean_mcp(tool_name):
    """Parse mcp__server__tool_name → (server_display, action_display)"""
    parts = tool_name.split("__")
    # parts: ["mcp", "server_name", "tool_name"]
    if len(parts) >= 3:
        server = parts[1]
        action = parts[2]
    elif len(parts) == 2:
        server = parts[1]
        action = ""
    else:
        return tool_name, ""

    # Clean server name: strip common prefixes/suffixes
    server = re.sub(r"^plugin_", "", server)
    server = re.sub(r"_v\d+$", "", server)
    server = re.sub(r"_mcp$", "", server)
    # Collapse repeated words: "plugin_slack_slack" → "slack"
    words = server.split("_")
    seen = []
    for w in words:
        if not seen or w != seen[-1]:
            seen.append(w)
    server = " ".join(seen).title()

    # Clean action: strip server name prefix from action if repeated
    action = action.replace("_", " ")
    server_lower = server.lower().replace(" ", "_")
    action = re.sub(rf"^{re.escape(server_lower.split('_')[0])}\s+", "", action, flags=re.I)

    return server.strip(), action.strip()


def extract_value(inp_dict):
    """Pick the most meaningful field from tool_input, in priority order."""
    FIELD_ORDER = ["command", "question", "query", "description",
                   "url", "file_path", "path", "pattern", "text", "prompt", "plan"]
    for key in FIELD_ORDER:
        val = inp_dict.get(key)
        if val and str(val).strip():
            return key, str(val).strip()
    # Fallback: first non-empty string value in the dict
    for key, val in inp_dict.items():
        if val and isinstance(val, str) and str(val).strip():
            return key, str(val).strip()
    return None, ""


def format_value(key, val):
    """Format the extracted value based on its field type."""
    if key in ("file_path", "path"):
        return basename(val)
    if key == "url":
        return domain(val)
    if key == "command":
        # Collapse absolute paths inside commands to basename
        val = re.sub(r"/(?:[^\s/]+/)+([^\s/]+)", lambda m: m.group(1), val)
        return val
    return val


def out(intent, risk, mode="approval"):
    print(json.dumps({"intent": truncate(intent), "risk": risk, "mode": mode}))
    sys.exit(0)


# ── Risk classification ──────────────────────────────────────────────────────

LOW_TOOLS = {
    "read", "glob", "grep", "webfetch", "websearch",
    "askuserquestion", "taskget", "tasklist", "taskoutput",
    "enterplanmode", "toolsearch",
    "listmcpresourcestool", "readmcpresourcetool",
    "exitworktree", "enterworktree",
}
# ExitPlanMode is the single highest-stakes approval point in a session --
# accepting a plan hands Claude free rein to execute it. It must go through
# the real pill flow, not the low-risk silent auto-approve path.

HIGH_BASH_PATTERNS = [
    r"\brm\b", r"\brmdir\b",
    r"--force(?![a-z-])",              # --force but NOT --force-reinstall / --force-with-lease
    r"--hard\b",
    r"\bdd\b", r"\bmkfs\b",
    r"git push.*-f\b", r"git reset.*--hard",
    r"chmod\s+[0-7]*7", r"sudo\b", r">\s*/dev/(?!null)",
    r"\btruncate\b", r"\bshred\b",
    r"\bfind\b.*\s-delete\b",
]

# curl flags that indicate data is being sent or a method override is in play
CURL_WRITE_PATTERNS = [
    r"\s-d\b", r"\s--data\b", r"\s--data-binary\b", r"\s--data-raw\b",
    r"\s--data-urlencode\b", r"\s--upload-file\b",
    r"-x\s+(post|put|delete|patch)",   # -X lowercased; --proxy would never match these words
    r"--request\s+(post|put|delete|patch)",
    r"\|\s*(bash|sh|zsh)\b",           # piped to a shell = executing downloaded content
]


def _is_readonly_curl(cmd):
    """True if the command uses curl purely as a read (GET, no data/upload/method flags)."""
    return bool(re.search(r"\bcurl\b", cmd)) and not any(
        re.search(p, cmd) for p in CURL_WRITE_PATTERNS
    )


# Commands that are read-only when not combined with output redirection
_SAFE_BASH_CMDS = frozenset([
    "ls", "ll", "la", "cat", "head", "tail", "wc", "stat", "file",
    "which", "whereis", "echo", "printf", "pwd", "date", "uname",
    "id", "whoami", "env", "printenv", "hostname",
    "grep", "egrep", "fgrep", "rg",
    "find", "diff", "sort", "uniq", "tr", "cut", "column",
    "jq", "yq", "open",
])

# Patterns that make an otherwise-safe bash command risky
_SAFE_BASH_DANGEROUS = [
    r"(?<![<2])>{1,2}\s*\S",           # output redirection (but not 2>&1)
    r"\btee\b",                         # tee writes to files
    r"\|\s*(bash|sh|zsh|python\d*|node|ruby|perl)\b",  # pipe to interpreter
    r"\bfind\b.*-(exec|delete)\b",      # find with exec or delete
    r"\bsed\b.*\s-[^\s]*i\b",          # sed -i (in-place edit)
    r"\bxargs\b",                       # xargs could run anything
]


def _is_safe_bash(cmd):
    """True if bash command is clearly read-only (no curl — handled separately)."""
    if re.search(r"\bcurl\b", cmd):
        return False
    if any(re.search(p, cmd) for p in _SAFE_BASH_DANGEROUS):
        return False
    for seg in re.split(r"\s*(?:\|\|?|&&|;)\s*", cmd):
        words = seg.strip().split()
        if not words:
            continue
        first = words[0].lstrip("\\")
        # Skip leading env-var assignments like FOO=bar cmd
        while first and re.match(r"^[a-z_][a-z0-9_]*=", first):
            words = words[1:]
            first = words[0].lstrip("\\") if words else ""
        if first and first not in _SAFE_BASH_CMDS:
            return False
    return True


def get_risk(tool_lower, inp_dict):
    if tool_lower in LOW_TOOLS:
        return "low"
    if tool_lower == "bash":
        cmd = str(inp_dict.get("command", "")).lower()
        if any(re.search(p, cmd) for p in HIGH_BASH_PATTERNS):
            return "high"
        if _is_readonly_curl(cmd) or _is_safe_bash(cmd):
            return "low"
    if tool_lower.startswith("mcp__"):
        # MCP reads are low risk
        action = tool_lower.split("__")[-1]
        if any(x in action for x in ("read", "search", "list", "get")):
            return "low"
    return "medium"


# ── Intent formatting ────────────────────────────────────────────────────────

risk = get_risk(tool_lower, inp)

# Description-first: use Claude's own plain-English label if present
_description = inp.get("description", "").strip()
if _description:
    out(_description, risk)

if tool_lower == "askuserquestion":
    out("Needs your attention", "low", mode="attention")

if tool_lower.startswith("mcp__"):
    server, action = clean_mcp(tool_lower)
    key, val = extract_value(inp)
    if val:
        display = format_value(key, val)
        out(f"{server} {action}: {display}", risk)
    elif action:
        out(f"{server} {action}", risk)
    else:
        out(server, risk)

else:
    key, val = extract_value(inp)
    label = tool  # preserve original casing: "Bash", "Write", "AskUserQuestion"

    # Friendlier label for a few verbose tool names
    LABELS = {
        "askuserquestion": "Ask",
        "notebookedit": "Notebook",
        "websearch": "Search",
        "webfetch": "Fetch",
        "listmcpresourcestool": "List MCP",
        "readmcpresourcetool": "Read MCP",
        "exitplanmode": "Plan",
    }
    label = LABELS.get(tool_lower, tool)

    if val:
        display = format_value(key, val)
        out(f"{label}: {display}", risk)
    else:
        out(label, risk)
