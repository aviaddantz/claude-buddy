# v47 — Widget can no longer strand itself off-screen

Nudge appeared to be dead: no sprite, nothing on screen. It was running the whole time,
answering hooks normally, parked at `x: 1685` on a 1512-wide screen. Entirely past the
right edge.

## Cause

`_load_saved_position` read `~/.nudge-position` and returned it verbatim:

```python
x, y = data.get("x"), data.get("y")
if isinstance(x, int) and isinstance(y, int):
    return x, y
```

The position is an absolute desktop coordinate, saved when the widget is dragged. Drag it
onto an external monitor, unplug the monitor, and the coordinate now names dead space. The
restore path never asked whether a screen still covered that point.

This failure mode is worse than a crash. A crash leaves a log; this leaves a healthy
daemon, a live socket, working hooks, and nothing to look at — indistinguishable from the
app being broken, and it survives every restart because the bad coordinate is on disk.

## Fix

`_clamp_to_screens` sits between the file and the caller. If the saved point puts at least
60 px of the widget on any current screen it is used unchanged, so ordinary multi-monitor
placement still works. Otherwise it is clamped into the primary screen's available
geometry, and the move is logged:

```
[buddy] saved position 1685,248 is off-screen; moved to 1311,248
```

Clamping happens inside `_load_saved_position`, which is the single point all three callers
go through, so no caller can bypass it.

The file on disk is deliberately left alone. It gets rewritten on the next drag, which
keeps the original placement if the monitor comes back before then.

## Note

Two things spotted during diagnosis that were settings, not faults, and are worth checking
before assuming a bug:

* `~/.nudge-sessions-disabled` turns the session row list off
* `~/.nudge-idle-visible` controls whether the sprite shows when idle

Together with `/tmp/claude-buddy-disabled` (v45) these are three separate ways for nudge to
be intentionally quiet while looking broken.

## Files

`buddy.py` only.
