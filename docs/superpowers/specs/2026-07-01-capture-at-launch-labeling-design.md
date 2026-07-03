# Capture-at-Launch Account Labeling — Design

**Date:** 2026-07-01
**Branch:** `sound-tracker` (builds on the sound-emission tracker work)
**Status:** Approved design, pending implementation plan

## Problem

Two related defects in how Roblox instances are labeled:

1. **Auto-rename gives wrong / duplicate names.** The rename monitoring worker
   (`_rename_monitoring_worker` in `utils/ui.py`) reverse-engineers each PID's
   identity: `_get_user_id_from_pid(pid)` matches the PID to a Roblox **log file
   by process start-time within a ±10s window**, then an **HTTP call**
   (`RobloxAPI.get_username_from_user_id`) turns the user-id into a name.
   - Launching several alts close together makes the start-time windows overlap,
     so the wrong log is matched → **wrong names**.
   - The worker calls `_get_user_id_from_pid(pid)` with a **fresh empty `used_logs`
     set every call**, so two different PIDs can match the **same** log → **the
     same name on multiple instances**.
2. **Sound-event labels share the same bug.** The sound tracker's
   `_resolve_pid_label` does the identical log-parse + HTTP reverse-lookup, so
   sound events inherit the same wrong/duplicate labeling.

Root cause: the normal launch path (`launch_game` / `launch_home`) fires
`launch_roblox(uname, …)` in a loop and never records which PID belongs to which
account, forcing a fragile reverse-lookup after the fact.

## Key insight

The manager **already knows the account** when it launches it. The auto-rejoin
path (`_launch_and_track_pid`) already proves the pattern: snapshot Roblox PIDs
before launch, launch, snapshot after, and the new PID is that account's. Doing
the same in the normal launch loop gives an **authoritative PID → account
mapping with zero HTTP and zero log-parsing**, making wrong/duplicate names
impossible by construction.

## Scope decision

- **Manager-launched instances only** (user-chosen Option A). Instances launched
  outside the manager, or pre-existing before the manager started, are simply not
  auto-renamed. This removes all HTTP/log-parsing from the rename/label path.
- **Fold in the sound tracker** (user-chosen Option A): its labels read from the
  same authoritative map, fixing the same class of bug and removing duplicate
  logic.

## Chosen approach: capture-at-launch

Populate an authoritative `PID → account` map at launch time; both window
auto-rename and sound-event labels read from it. Reframes labeling from
"poll-and-guess" to "capture-at-launch."

## Components

All in `utils/ui.py` unless noted.

### 1. The map (source of truth)
`self.pid_account_map: dict[int, str]` (PID → account username), guarded by
`self.pid_account_lock` (written by launch worker threads, read by the sound
worker thread). Replaces the reverse-lookup entirely.

### 2. Pure PID selection helper (new module)
`utils/pid_labels.py`:
`pick_launched_pid(pids_before: set[int], pids_after: set[int], assigned: set[int]) -> int | None`
— returns the single new PID present in `pids_after` but not in `pids_before` and
not in `assigned`; returns `None` if there are zero such PIDs or more than one
(ambiguous). Pure and unit-testable.

### 3. Capture at launch — normal path (`launch_game` / `launch_home` worker)
The worker loop launches accounts sequentially. Each iteration becomes:
1. `pids_before = self._get_roblox_pids()`
2. `self.manager.launch_roblox(uname, …)`
3. Poll up to `LAUNCH_PID_TIMEOUT` (~12s), re-snapshotting `_get_roblox_pids()`,
   calling `pick_launched_pid(pids_before, pids_after, assigned)` where `assigned`
   is `set(pid_account_map)`; stop as soon as it returns a PID.
4. On a PID: `pid_account_map[pid] = uname`; if rename enabled, rename its window
   (off-thread). On timeout/ambiguity: skip labeling this account (leave it
   unnamed) and continue.

Waiting for the PID replaces the current blind `time.sleep(2)`; it both spaces
launches and makes attribution exact.

### 4. Capture at launch — auto-rejoin path (`_launch_and_track_pid`)
Already captures the new PID into `auto_rejoin_pids`. Add: also write
`pid_account_map[new_pid] = account` (under the lock) and trigger the rename when
enabled. Unifies both launch paths through one mechanism.

### 5. Renaming
- Keep `_rename_roblox_window(pid, name)` (the `SetWindowText` helper).
- Add `_rename_window_for_pid_when_ready(pid, name)`: polls up to
  `RENAME_WINDOW_TIMEOUT` (~45s, mirroring `_minimize_roblox_window_for_pid`) for
  the PID's window to appear, then calls `_rename_roblox_window`. Always run in a
  daemon thread so it never blocks a launch.

### 6. Sound labels (DRY)
`_resolve_pid_label(pid)` becomes: read `pid_account_map` under the lock → return
the account name; on miss, return `sound_tracker.format_pid_label(pid, None)`
("PID n"). **All log-parsing and HTTP are removed from this method.** No other
sound-tracker code changes; `format_pid_label` stays.

### 7. Enabled by default + retire the polling worker
- `rename_roblox_windows` setting **defaults to `True`** (via
  `self.settings.get("rename_roblox_windows", True)` everywhere it is read).
  Users who previously set it to `False` keep `False`; unset users get `True`.
- **Remove** `_rename_monitoring_worker`, `start_rename_monitoring`,
  `stop_rename_monitoring`, and their boot (`root.after`), close-cleanup, and
  toggle start/stop wiring. Also remove the now-unused state fields
  `self.rename_thread`, `self.rename_stop_event`, `self.renamed_pids`.
- The QOL toggle's `on_rename_toggle` becomes a simple
  "store setting + save" (no thread start/stop). Toggling on takes effect on the
  next launch.
- **Keep** `_get_user_id_from_pid` and `_match_pids_to_accounts` — auto-rejoin's
  "Start All" still uses them to re-associate PIDs (untouched behavior). Bonus:
  when `_match_pids_to_accounts` produces a match, also write it into
  `pid_account_map` so re-matched instances get labeled at no new cost.

### 8. Pruning / correctness
- Capture-at-launch **overwrites** any stale entry for a reused PID, so a
  mislabel cannot survive a relaunch.
- Auto-rejoin already deletes dead PIDs from `auto_rejoin_pids` on
  disconnect/relaunch — mirror that to also `pop` them from `pid_account_map`.
- Sound-label reads happen only for currently-sounding (alive) PIDs, so a stale
  dead-PID entry never affects a label. Dead entries are otherwise benign memory.

## Data flow summary

```
launch (normal or auto-rejoin)
  → pids_before snapshot
  → launch_roblox(account)
  → poll: pick_launched_pid(before, after, assigned) → pid
  → pid_account_map[pid] = account            (authoritative)
  → if rename enabled: rename window (off-thread, waits for window)

sound event for pid
  → _resolve_pid_label(pid) = pid_account_map.get(pid) or "PID <n>"
```

## Error handling

- PID capture timeout or ambiguity (2+ new PIDs): log and skip labeling that
  account; the launch itself still succeeds.
- Window never appears within `RENAME_WINDOW_TIMEOUT`: the off-thread renamer logs
  and exits; no crash, instance just stays unnamed.
- All map access goes through `self.pid_account_lock`.

## Testing

- **Unit-test `pick_launched_pid`** (`tests/test_pid_labels.py`): one new PID →
  returns it; no new PID → `None`; two+ new PIDs → `None` (ambiguous); a new PID
  already in `assigned` is excluded.
- **Manual integration:** launch 3+ alts at once → each window titled with its
  correct, distinct account name; sound events show the correct account; no
  duplicate or wrong names. Toggle default confirmed on for a fresh settings file.

## Out of scope

- External / manually-launched or pre-existing instances (Option A) — not
  auto-renamed.
- The event-driven vs polling debate for sound detection (already settled).
- Any change to auto-rejoin's launch/kill/matching logic beyond writing the
  shared map.
