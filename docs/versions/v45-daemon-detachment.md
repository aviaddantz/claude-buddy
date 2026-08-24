# v45 — Daemon survives its launcher

The sprite disappeared and every restart attempt silently did nothing. Two separate
causes, one of them a real fragility that had been there since the beginning.

## The immediate cause: a sticky pause

`/tmp/claude-buddy-disabled` was present. `stop-daemon.sh` creates it and `pkill`s the
daemon, and `start-daemon.sh` exits on line 2 when it sees it. So nudge was paused, not
broken — but a paused nudge is indistinguishable from a dead one, because nothing on the
restart path says why it declined to start.

No code change here. The flag is doing its job (v26 added the check deliberately, so a
`notify.sh` restart could not undo an intentional pause). Worth remembering:
`rm /tmp/claude-buddy-disabled` is the recovery, and `stop-daemon.sh` prints that hint
when you use it.

## The real fix: process group detachment

`start-daemon.sh` launched the daemon like this:

```bash
/usr/local/bin/python3 "$SCRIPT_DIR/buddy.py" daemon > /tmp/claude-buddy.log 2>&1 &
```

Backgrounding leaves the process in the **caller's process group**. The caller is a
`SessionStart` hook, so anything that reaps that hook's group takes the widget down with
it. The failure mode is nasty: the daemon dies with no traceback, no crash report, and
nothing in the log, because it was signalled rather than crashed.

Now:

```bash
nohup perl -e 'use POSIX qw(setsid); setsid(); exec @ARGV or die $!' \
    /usr/local/bin/python3 "$SCRIPT_DIR/buddy.py" daemon \
    > /tmp/claude-buddy.log 2>&1 &
disown 2>/dev/null || true
```

`setsid()` puts the daemon in a new session and a new process group before exec, so group
signals aimed at the launcher never reach it. macOS ships no `setsid` binary, hence perl's
`POSIX::setsid` — perl is at `/usr/bin/perl` on every macOS install.

Verified: the daemon comes up with `PPID 1` (reparented to launchd) and `PGID == PID`.

`pkill -f "buddy.py daemon"` still finds and stops it, so `stop-daemon.sh` and the restart
path are unaffected.

## Files

`start-daemon.sh` only.
