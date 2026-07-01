"""
Pure helper for capture-at-launch account labeling.

No Tkinter, threading, or psutil here so it unit-tests without a UI or a live
process table. See utils/ui.py for the stateful map that consumes this.
"""


def pick_launched_pid(pids_before, pids_after, assigned):
    """
    Identify the single new Roblox PID a launch produced.

    Returns the one PID present in `pids_after` but not in `pids_before` and not
    already in `assigned`. Returns None when there are zero such PIDs (process
    not up yet) or more than one (ambiguous — refuse to guess).
    """
    candidates = (set(pids_after) - set(pids_before)) - set(assigned)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None
