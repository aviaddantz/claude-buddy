# Intent Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the nudge pill show Claude's plain-English `description` field as the collapsed intent, falling back to the existing classify.py extraction logic when no description is present.

**Architecture:** Two targeted changes to `classify.py` only — a description-first early return at the top of the intent logic, and a word-boundary truncate function replacing the current mid-character one. Risk classification is untouched.

**Tech Stack:** Python 3, stdin/stdout JSON, no external dependencies.

---

### Task 1: Replace `truncate()` with word-boundary version

**Files:**
- Modify: `classify.py:25-29`

- [ ] **Step 1: Write a standalone test script to verify current vs new behavior**

Create a temp file `/tmp/test_truncate.py`:

```python
# Current behavior (mid-character cut)
def truncate_old(s, limit=42):
    s = str(s).strip()
    if len(s) <= limit:
        return s
    return s[:limit - 1] + "…"

# New behavior (word boundary)
def truncate(s, limit=42):
    s = str(s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    boundary = cut.rfind(" ")
    if boundary > 0:
        return s[:boundary] + "…"
    return s[:limit - 1] + "…"

cases = [
    ("Delete standalone product wiki files", 42, "Delete standalone product wiki files"),
    ("Delete standalone product wiki files from the vault", 42, "Delete standalone product wiki…"),
    ("Superlongwordwithnospacesatallinthisstring", 42, "Superlongwordwithnospacesatallinthisstr…"),
    ("Short", 42, "Short"),
]

for s, limit, expected in cases:
    old = truncate_old(s, limit)
    new = truncate(s, limit)
    status = "PASS" if new == expected else f"FAIL (got: {new!r})"
    print(f"{status} | input={s!r[:40]} | new={new!r}")
```

- [ ] **Step 2: Run the test to verify expected behavior**

```bash
python3 /tmp/test_truncate.py
```

Expected output — all lines start with `PASS`:
```
PASS | input='Delete standalone product wiki files' | new='Delete standalone product wiki files'
PASS | input='Delete standalone product wiki files from' | new='Delete standalone product wiki…'
PASS | input='Superlongwordwithnospacesatallinthisstring' | new='Superlongwordwithnospacesatallinthisstr…'
PASS | input='Short' | new='Short'
```

- [ ] **Step 3: Replace `truncate()` in classify.py**

In `classify.py`, replace lines 25-29:

```python
def truncate(s, limit=42):
    s = str(s).strip()
    if len(s) <= limit:
        return s
    return s[:limit - 1] + "…"
```

With:

```python
def truncate(s, limit=42):
    s = str(s).strip()
    if len(s) <= limit:
        return s
    cut = s[:limit]
    boundary = cut.rfind(" ")
    if boundary > 0:
        return s[:boundary] + "…"
    return s[:limit - 1] + "…"
```

- [ ] **Step 4: Verify classify.py still produces valid output**

```bash
echo '{"tool": "Bash", "input": {"command": "rm file.txt"}, "file_path": ""}' | python3 /Users/aviadda/Development/nudge/classify.py
```

Expected: valid JSON with `intent`, `risk`, `mode` keys. No crash.

- [ ] **Step 5: Commit**

```bash
cd /Users/aviadda/Development/nudge
git add classify.py
git commit -m "fix: word-boundary truncation in classify.py"
```

---

### Task 2: Add description-first intent check

**Files:**
- Modify: `classify.py` — add early return after risk classification, before tool-specific logic

- [ ] **Step 1: Write a test that exercises description-first path**

Create `/tmp/test_description.py`:

```python
import subprocess, json

def classify(payload):
    result = subprocess.run(
        ["python3", "/Users/aviadda/Development/nudge/classify.py"],
        input=json.dumps(payload),
        capture_output=True, text=True
    )
    return json.loads(result.stdout)

# Case 1: Bash with description present — should use description
r = classify({"tool": "Bash", "input": {"command": "rm file.txt", "description": "Delete wiki files"}, "file_path": ""})
assert r["intent"] == "Delete wiki files", f"FAIL case 1: {r['intent']!r}"
assert r["risk"] == "high", f"FAIL case 1 risk: {r['risk']!r}"
print("PASS case 1: description present, used as intent, risk still high")

# Case 2: Bash without description — falls back to command extraction
r = classify({"tool": "Bash", "input": {"command": "npm install axios"}, "file_path": ""})
assert "axios" in r["intent"], f"FAIL case 2: {r['intent']!r}"
print(f"PASS case 2: no description, fallback intent: {r['intent']!r}")

# Case 3: description present but empty string — should fall back
r = classify({"tool": "Bash", "input": {"command": "cat file.txt", "description": ""}, "file_path": ""})
assert "cat" in r["intent"] or "file" in r["intent"].lower(), f"FAIL case 3: {r['intent']!r}"
print(f"PASS case 3: empty description, fallback intent: {r['intent']!r}")

# Case 4: description longer than 42 chars — truncated at word boundary
long_desc = "Delete standalone product wiki files from the Obsidian vault"
r = classify({"tool": "Bash", "input": {"command": "rm file.txt", "description": long_desc}, "file_path": ""})
assert r["intent"].endswith("…"), f"FAIL case 4: not truncated: {r['intent']!r}"
assert not r["intent"].endswith(" …"), f"FAIL case 4: trailing space before ellipsis: {r['intent']!r}"
print(f"PASS case 4: long description truncated at word boundary: {r['intent']!r}")

# Case 5: Non-Bash tool with description — should also use description
r = classify({"tool": "Write", "input": {"file_path": "/some/path/file.py", "description": "Write the config file"}, "file_path": ""})
assert r["intent"] == "Write the config file", f"FAIL case 5: {r['intent']!r}"
print(f"PASS case 5: non-Bash tool uses description: {r['intent']!r}")
```

- [ ] **Step 2: Run the test to confirm it currently fails on cases 1, 4, 5**

```bash
python3 /tmp/test_description.py
```

Expected: cases 1, 4, and 5 fail (description not yet used). Cases 2 and 3 pass.

- [ ] **Step 3: Add description-first check to classify.py**

In `classify.py`, find the line that begins the intent/output section — right after risk is computed (currently around line 143: `risk = get_risk(tool_lower, inp)`).

Add the following block immediately after `risk = get_risk(tool_lower, inp)`:

```python
# Description-first: use Claude's own plain-English label if present
_description = inp.get("description", "").strip()
if _description:
    out(_description, risk)
```

The `out()` function calls `truncate()` (now word-boundary aware) and exits, so all existing tool-specific logic below is untouched.

- [ ] **Step 4: Run the test — all cases should pass**

```bash
python3 /tmp/test_description.py
```

Expected:
```
PASS case 1: description present, used as intent, risk still high
PASS case 2: no description, fallback intent: 'Bash: npm install axios'
PASS case 3: empty description, fallback intent: ...
PASS case 4: long description truncated at word boundary: 'Delete standalone product wiki…'
PASS case 5: non-Bash tool uses description: 'Write the config file'
```

- [ ] **Step 5: Smoke test with a real rm payload matching the original problem**

```bash
echo '{"tool": "Bash", "input": {"command": "rm \"/Users/aviadda/Obsidian/My Notes/wiki/zero-to-hero.md\" \"/Users/aviadda/Obsidian/My Notes/wiki/ai-brains.md\"", "description": "Delete standalone product wiki files"}, "file_path": ""}' | python3 /Users/aviadda/Development/nudge/classify.py
```

Expected:
```json
{"intent": "Delete standalone product wiki files", "risk": "high", "mode": "approval"}
```

- [ ] **Step 6: Commit**

```bash
cd /Users/aviadda/Development/nudge
git add classify.py
git commit -m "feat: prefer description field as intent in classify.py"
```
