# Roblox Sound Emission Tracker — Design

**Date:** 2026-07-01
**Branch:** `sound-tracker` (off `main`)
**Status:** Approved design, pending implementation plan

## Problem

The account manager runs multiple Roblox instances at once, each a separate
`RobloxPlayerBeta.exe` process. The instances are **normally silent** (AFK / idle
/ quiet game). When one starts emitting audio, that is a meaningful event, and the
user wants to know **which instance** produced it.

## Research summary — why this approach

- **No Roblox-side API applies.** Roblox's audio APIs (`VoiceChatService`, the
  `AudioAnalyzer`/`AudioListener` beta) only run *inside* an experience via Luau
  and cannot tell an external program which OS process produced audio. Dead end.
- **The correct layer is Windows Core Audio (WASAPI).** Windows tracks audio
  **per process** via "audio sessions" (what the volume mixer uses). Each session
  exposes its owning **PID** and a **peak meter**
  (`IAudioMeterInformation::GetPeakValue`, range `0.0`–`1.0`).
- **`pycaw`** (Python wrapper over WASAPI) exposes exactly this — audio sessions
  with a `ProcessId` and a peak-meter interface — so no raw COM is required.
- Any audio the process routes to the device registers on its session peak
  (game audio, music, UI, voice) — this is process-level "any sound," which is
  what the user wants.

## Chosen approach: poll the per-session peak meter

A dedicated daemon worker polls pycaw audio sessions on an interval, filters to
Roblox game-client PIDs, reads each session's peak, and **edge-triggers** on the
silent → sound transition. Chosen over event-driven `IAudioSessionEvents`
because:

- It matches the codebase's existing idiom — rename, auto-rejoin, and anti-AFK
  are all daemon poll loops.
- "Any audio = flag" needs no push-latency precision.
- Event-driven COM callbacks arrive on COM threads (awkward to marshal into the
  Tkinter app) and `Active` state is coarser than a real peak reading.

## Reused existing infrastructure

All in `utils/ui.py` unless noted. The sound subsystem mirrors the **rename
monitoring** subsystem (`_rename_monitoring_worker`, ui.py:9538).

| Existing piece | Reused for |
|---|---|
| `psutil` (already a dependency) | Enumerating `RobloxPlayerBeta.exe` PIDs |
| `_is_valid_roblox_game_client(pid, name)` (ui.py:10605) | Filtering to real game clients, not launcher/other |
| `_get_user_id_from_pid(pid)` (ui.py:10690) → `RobloxAPI.get_username_from_user_id` (roblox_api.py:329) | Resolving PID → username label |
| QOL settings-tab toggle pattern (`rename_roblox_windows`, ui.py:6708) | The `sound_tracking_enabled` toggle |
| `root.after(1000, start_..._monitoring)` boot pattern (ui.py:6873) | Auto-starting the worker on launch |
| `renamed_pids.intersection(current_pids)` prune trick (ui.py:9570) | Pruning per-PID state for closed instances |

**Only new dependency:** `pycaw` (pulls in `comtypes`), added to
`requirements.txt`.

**Labeling cost note:** `_get_user_id_from_pid` parses Roblox log files off disk
and `get_username_from_user_id` makes an HTTP call. Both are too expensive to run
per poll tick, so labels are **resolved once per PID and memoized**.

## Components (new, in `utils/ui.py`)

- **`start_sound_monitoring()` / `stop_sound_monitoring()`** — lifecycle, gated on
  the `sound_tracking_enabled` setting; started via the existing
  `root.after(1000, ...)` boot pattern and the QOL toggle.
- **`_sound_monitoring_worker()`** — the daemon poll loop. Initializes COM for the
  thread, loops until a stop event, and uninitializes COM on exit.
- **`_resolve_pid_label(pid)`** — wraps `_get_user_id_from_pid` →
  `get_username_from_user_id`, memoized in `self._sound_pid_labels: dict[int,str]`.
  Falls back to `"PID <n>"` when resolution fails.
- **`_on_sound_event(pid, label, peak)`** — the single internal "sound detected"
  sink. For now it logs; the notification layer plugs in here later (the one
  intended extension seam).
- **State fields** initialized alongside the rename fields (near ui.py:118):
  `self.sound_thread`, `self.sound_stop_event`, `self.sound_pid_state`,
  `self._sound_pid_labels`.

## Data flow (one poll tick, ~250 ms)

```
pycaw AudioUtilities.GetAllSessions()
  → for each session whose ProcessId is a Roblox game client
       (reuse _is_valid_roblox_game_client)
  → peak = session.<IAudioMeterInformation>.GetPeakValue()   # 0.0–1.0
  → feed (pid, peak, now) into the per-PID edge detector
  → on a rising edge:
        label = _resolve_pid_label(pid)
        _on_sound_event(pid, label, peak)
```

A Roblox PID with **no audio session** (or peak `0.0`) is treated as silent, so a
session *appearing* is itself the sound signal and is caught by the same logic.

## Edge-trigger state machine (per PID)

Instances are normally silent, so fire on the **silent → sound** transition, not
continuously.

- Per-PID state: `silent` or `sounding`, plus `last_event_time`.
- `peak > SOUND_THRESHOLD` while `silent` → emit event, transition to `sounding`.
- Transition back to `silent` only after peak stays `≤ SOUND_THRESHOLD` for the
  full `RELEASE_SECONDS` (debounce — brief dips don't re-arm/re-trigger).
- `COOLDOWN_SECONDS` caps re-fires per PID so a noisy instance can't spam events.

### Tunable constants (module-level, defaults)

| Constant | Default | Meaning |
|---|---|---|
| `SOUND_THRESHOLD` | `0.02` | Peak noise floor; above this counts as sound |
| `POLL_INTERVAL` | `0.25` s | Poll cadence |
| `RELEASE_SECONDS` | `1.5` s | Continuous silence required to re-arm a PID |
| `COOLDOWN_SECONDS` | `5` s | Minimum gap between events for one PID |

## Lifecycle & cleanup

- Each tick, prune `self.sound_pid_state` and `self._sound_pid_labels` to the set
  of currently-live Roblox PIDs (same `intersection(current_pids)` approach as the
  rename worker), so closed instances don't leak state.
- COM is initialized at worker start and uninitialized on worker exit, inside the
  worker thread.
- `stop_sound_monitoring()` sets the stop event and drops the thread reference,
  matching `stop_rename_monitoring` (ui.py:9530).

## Error handling

- The whole poll tick is wrapped in try/except (matching the rename worker) so a
  transient COM/session error logs and the loop continues rather than dying.
- Missing `pycaw` degrades gracefully: the import is guarded, the QOL toggle shows
  a "pycaw not installed" note, and the worker no-ops instead of crashing.

## Testing

- **Unit test the edge detector in isolation.** Extract the per-PID transition
  logic so it can be driven by a synthetic sequence of `(pid, peak, timestamp)`
  samples. Assert: exactly one event per silent→sound transition; brief dips
  within `RELEASE_SECONDS` do not re-trigger; `COOLDOWN_SECONDS` is respected. No
  audio hardware required.
- **Manual integration check.** Launch one instance; confirm no events while idle;
  play a sound in it; confirm exactly one flagged event carrying the correct
  username label.

## Out of scope (explicit)

- **Notification delivery** (Discord / toast / in-UI). The design exposes the
  `_on_sound_event` seam for it; delivery is a later, separate piece of work.
- Event-driven (`IAudioSessionEvents`) detection — rejected above.
- Distinguishing *kinds* of sound (voice vs game vs UI). Any audio counts.
