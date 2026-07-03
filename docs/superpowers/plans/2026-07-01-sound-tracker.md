# Roblox Sound Emission Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag which Roblox instance (by account/username) starts emitting sound, by polling per-process WASAPI peak meters.

**Architecture:** A pure, unit-tested module (`utils/sound_tracker.py`) holds the per-PID silent→sound edge detector, the pycaw peak-reading adapter, and label formatting. A daemon worker in `utils/ui.py` — mirroring the existing rename-monitoring subsystem — polls the adapter every ~250 ms, runs peaks through the detector, resolves PID→username (memoized), and calls a single `_on_sound_event` sink. Notification delivery is out of scope; `_on_sound_event` is the seam for it.

**Tech Stack:** Python 3.12 (project floor 3.7+), Tkinter app, `pycaw` (+ `comtypes`) for WASAPI, `psutil` (already present), `pytest` (dev-only) for the pure logic.

## Global Constraints

- Windows-only. Python floor 3.7+ (dev machine runs 3.12.10). Run scripts with the `py` launcher.
- App runtime dependencies go in `requirements.txt`. Test-only dependencies go in a new `requirements-dev.txt` — do NOT put `pytest` in `requirements.txt`.
- `utils/sound_tracker.py` MUST contain NO Tkinter and NO direct COM/threading state — pure, importable logic only, so it tests without a UI or audio hardware. The `pycaw` import there is guarded (`PYCAW_AVAILABLE`).
- The monitoring subsystem in `utils/ui.py` MUST follow the existing rename-monitoring patterns: state fields near ui.py:115-117; `start_/stop_` methods near ui.py:9492-9509; boot via `root.after(1000, ...)` near ui.py:6846; close cleanup near ui.py:437; QOL toggle near ui.py:6681.
- New app dependency: `pycaw` (pulls in `comtypes`).
- Reuse existing helpers verbatim — do NOT reimplement: `_is_valid_roblox_game_client(pid, process_name_lower=None)` (ui.py:10530), `_get_user_id_from_pid(pid, used_logs=None)` (ui.py:10615), `RobloxAPI.get_username_from_user_id(user_id)` (classes/roblox_api.py:329, already imported in ui.py).
- Tunable constants (module-level in `sound_tracker.py`): `SOUND_THRESHOLD=0.02`, `POLL_INTERVAL=0.25`, `RELEASE_SECONDS=1.5`, `COOLDOWN_SECONDS=5.0`.
- Run pytest from the repo root so `from utils.sound_tracker import ...` resolves (namespace package; no `utils/__init__.py`).
- **Out of scope:** notification delivery (Discord/toast/UI), event-driven `IAudioSessionEvents`, and distinguishing sound *kinds*.

## File Structure

- **Create `utils/sound_tracker.py`** — pure logic: tunable constants, `format_pid_label`, `SoundEdgeDetector`, `filter_roblox_peaks`, and the guarded pycaw glue (`PYCAW_AVAILABLE`, `_iter_session_peaks`, `get_roblox_session_peaks`).
- **Create `tests/test_sound_tracker.py`** — unit tests for the detector, `format_pid_label`, and `filter_roblox_peaks`.
- **Create `requirements-dev.txt`** — `pytest`.
- **Modify `requirements.txt`** — add `pycaw`.
- **Modify `utils/ui.py`** — state fields, worker, start/stop, `_resolve_pid_label`, `_on_sound_event`, QOL toggle, boot wiring, close cleanup.
- **Modify `CLAUDE.md`** — document the sound-tracking subsystem.

---

### Task 1: Pure edge detector + label formatting

**Files:**
- Create: `utils/sound_tracker.py`
- Create: `tests/test_sound_tracker.py`
- Create: `requirements-dev.txt`

**Interfaces:**
- Produces:
  - `SOUND_THRESHOLD=0.02`, `POLL_INTERVAL=0.25`, `RELEASE_SECONDS=1.5`, `COOLDOWN_SECONDS=5.0` (module-level floats)
  - `format_pid_label(pid: int, username: str | None) -> str`
  - `SoundEdgeDetector(threshold=SOUND_THRESHOLD, release_seconds=RELEASE_SECONDS, cooldown_seconds=COOLDOWN_SECONDS)` with `update(pid: int, peak: float, now: float) -> bool` and `prune(live_pids: set[int]) -> None`

- [ ] **Step 1: Add the dev requirements file and install pytest**

Create `requirements-dev.txt`:

```
pytest>=8.0
```

Run: `py -m pip install -r requirements-dev.txt`
Expected: pytest installs (or "already satisfied").

- [ ] **Step 2: Write the failing tests**

Create `tests/test_sound_tracker.py`:

```python
from utils.sound_tracker import (
    SoundEdgeDetector,
    format_pid_label,
    SOUND_THRESHOLD,
)

LOUD = SOUND_THRESHOLD + 0.5
QUIET = 0.0


def _det():
    # explicit short windows so tests read clearly
    return SoundEdgeDetector(threshold=SOUND_THRESHOLD,
                             release_seconds=1.5,
                             cooldown_seconds=5.0)


def test_format_pid_label_uses_username_when_present():
    assert format_pid_label(123, "coolalt") == "coolalt"


def test_format_pid_label_falls_back_to_pid():
    assert format_pid_label(123, None) == "PID 123"
    assert format_pid_label(123, "") == "PID 123"


def test_first_sound_emits_event():
    d = _det()
    assert d.update(100, LOUD, now=1000.0) is True


def test_below_threshold_never_emits():
    d = _det()
    assert d.update(100, SOUND_THRESHOLD, now=1000.0) is False
    assert d.update(100, QUIET, now=1000.25) is False


def test_continuous_sound_emits_once():
    d = _det()
    assert d.update(100, LOUD, now=1000.0) is True
    assert d.update(100, LOUD, now=1000.25) is False
    assert d.update(100, LOUD, now=1000.5) is False


def test_brief_dip_within_release_does_not_rearm():
    d = _det()
    assert d.update(100, LOUD, now=1000.0) is True
    d.update(100, QUIET, now=1001.0)          # silent_since = 1001.0
    assert d.update(100, LOUD, now=1001.4) is False   # dip < 1.5s release
    assert d.update(100, LOUD, now=1001.65) is False


def test_cooldown_blocks_quick_reevent():
    d = _det()
    assert d.update(100, LOUD, now=1000.0) is True
    # go silent long enough to re-arm (>1.5s) but total < 5s cooldown
    d.update(100, QUIET, now=1001.0)
    d.update(100, QUIET, now=1003.0)          # re-armed (silent >= 1.5s)
    assert d.update(100, LOUD, now=1003.5) is False   # 3.5s < 5s cooldown


def test_rearms_after_release_and_cooldown():
    d = _det()
    assert d.update(100, LOUD, now=1000.0) is True
    d.update(100, QUIET, now=1001.0)
    d.update(100, QUIET, now=1006.0)          # silent, re-armed
    assert d.update(100, LOUD, now=1006.5) is True    # >5s since last event


def test_pids_are_independent():
    d = _det()
    assert d.update(100, LOUD, now=1000.0) is True
    assert d.update(200, LOUD, now=1000.1) is True


def test_prune_resets_dead_pid():
    d = _det()
    assert d.update(100, LOUD, now=1000.0) is True
    d.prune(live_pids=set())                  # 100 no longer present
    assert d.update(100, LOUD, now=1000.5) is True    # treated as brand new
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `py -m pytest tests/test_sound_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.sound_tracker'`.

- [ ] **Step 4: Implement `utils/sound_tracker.py` (pure part)**

Create `utils/sound_tracker.py`:

```python
"""
Sound emission tracking for Roblox instances.

Pure, importable helpers used by the sound-monitoring worker in utils/ui.py.
No Tkinter and no COM/threading state lives here, so the logic tests without a
UI or audio hardware. The pycaw import is guarded (see PYCAW_AVAILABLE below).
"""

# --- Tunable constants -----------------------------------------------------
SOUND_THRESHOLD = 0.02      # peak (0.0-1.0) above this counts as "sound"
POLL_INTERVAL = 0.25        # seconds between polls in the worker loop
RELEASE_SECONDS = 1.5       # continuous silence needed to re-arm a PID
COOLDOWN_SECONDS = 5.0      # minimum gap between events for one PID


def format_pid_label(pid, username):
    """Display label for a sound event: the username if known, else 'PID <n>'."""
    return username if username else f"PID {pid}"


class SoundEdgeDetector:
    """
    Per-PID state machine that fires once on each silent -> sound transition.

    Feed samples with update(pid, peak, now); it returns True exactly on a
    rising edge that should emit an event, subject to:
      - release_seconds: how long peak must stay <= threshold before a PID is
        re-armed (debounces brief dips), and
      - cooldown_seconds: minimum gap between emitted events for one PID.
    """

    def __init__(self, threshold=SOUND_THRESHOLD,
                 release_seconds=RELEASE_SECONDS,
                 cooldown_seconds=COOLDOWN_SECONDS):
        self.threshold = threshold
        self.release_seconds = release_seconds
        self.cooldown_seconds = cooldown_seconds
        # pid -> {'sounding': bool, 'last_event': float, 'silent_since': float|None}
        self._state = {}

    def update(self, pid, peak, now):
        st = self._state.get(pid)
        if st is None:
            st = {'sounding': False, 'last_event': 0.0, 'silent_since': now}
            self._state[pid] = st

        is_loud = peak > self.threshold

        if not st['sounding']:
            if is_loud:
                st['sounding'] = True
                st['silent_since'] = None
                if now - st['last_event'] >= self.cooldown_seconds:
                    st['last_event'] = now
                    return True
                return False
            return False

        # currently sounding
        if is_loud:
            st['silent_since'] = None
        else:
            if st['silent_since'] is None:
                st['silent_since'] = now
            elif now - st['silent_since'] >= self.release_seconds:
                st['sounding'] = False
                st['silent_since'] = now
        return False

    def prune(self, live_pids):
        """Drop state for PIDs no longer present."""
        for pid in list(self._state.keys()):
            if pid not in live_pids:
                del self._state[pid]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `py -m pytest tests/test_sound_tracker.py -v`
Expected: PASS — all tests green.

- [ ] **Step 6: Commit**

```bash
git add utils/sound_tracker.py tests/test_sound_tracker.py requirements-dev.txt
git commit -m "feat: add pure sound edge detector + label formatting"
```

---

### Task 2: pycaw peak-reading adapter

**Files:**
- Modify: `utils/sound_tracker.py`
- Modify: `tests/test_sound_tracker.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `filter_roblox_peaks(session_readings: Iterable[tuple[int|None, str|None, float]], is_roblox_pid: Callable[[int, str|None], bool]) -> dict[int, float]` — returns `{pid: max_peak}` for PIDs the predicate accepts.
  - `PYCAW_AVAILABLE: bool`
  - `get_roblox_session_peaks(is_roblox_pid: Callable[[int, str|None], bool]) -> dict[int, float]` — reads live WASAPI sessions and delegates to `filter_roblox_peaks`; returns `{}` if pycaw is unavailable.

- [ ] **Step 1: Add pycaw to app requirements**

Modify `requirements.txt` — add this line (keep existing lines):

```
pycaw>=20240210
```

Run: `py -m pip install -r requirements.txt`
Expected: `pycaw` and `comtypes` install (or "already satisfied").

- [ ] **Step 2: Write failing tests for `filter_roblox_peaks`**

Append to `tests/test_sound_tracker.py`:

```python
from utils.sound_tracker import filter_roblox_peaks


def _is_roblox(pid, name):
    return name == "robloxplayerbeta.exe"


def test_filter_keeps_only_roblox_pids():
    readings = [
        (100, "robloxplayerbeta.exe", 0.4),
        (200, "chrome.exe", 0.9),
        (300, "robloxplayerbeta.exe", 0.1),
    ]
    result = filter_roblox_peaks(readings, _is_roblox)
    assert result == {100: 0.4, 300: 0.1}


def test_filter_takes_max_peak_per_pid():
    readings = [
        (100, "robloxplayerbeta.exe", 0.2),
        (100, "robloxplayerbeta.exe", 0.7),
        (100, "robloxplayerbeta.exe", 0.3),
    ]
    result = filter_roblox_peaks(readings, _is_roblox)
    assert result == {100: 0.7}


def test_filter_skips_none_pid():
    readings = [(None, "robloxplayerbeta.exe", 0.5)]
    assert filter_roblox_peaks(readings, _is_roblox) == {}
```

- [ ] **Step 3: Run to verify the new tests fail**

Run: `py -m pytest tests/test_sound_tracker.py -v`
Expected: FAIL — `ImportError: cannot import name 'filter_roblox_peaks'`.

- [ ] **Step 4: Implement the adapter**

Append to `utils/sound_tracker.py`:

```python
# --- WASAPI peak reading (pycaw) -------------------------------------------

try:
    from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
    PYCAW_AVAILABLE = True
except Exception:
    PYCAW_AVAILABLE = False


def filter_roblox_peaks(session_readings, is_roblox_pid):
    """
    session_readings: iterable of (pid, process_name, peak).
    is_roblox_pid(pid, process_name) -> bool.
    Returns {pid: max_peak} across a PID's sessions, for accepted PIDs only.
    """
    peaks = {}
    for pid, name, peak in session_readings:
        if pid is None:
            continue
        if not is_roblox_pid(pid, name):
            continue
        if pid not in peaks or peak > peaks[pid]:
            peaks[pid] = peak
    return peaks


def _iter_session_peaks():
    """Yield (pid, process_name_lower_or_None, peak) for every audio session."""
    if not PYCAW_AVAILABLE:
        return
    for session in AudioUtilities.GetAllSessions():
        try:
            pid = session.ProcessId
            if not pid:
                continue
            name = None
            if session.Process is not None:
                try:
                    name = session.Process.name().lower()
                except Exception:
                    name = None
            meter = session._ctl.QueryInterface(IAudioMeterInformation)
            peak = meter.GetPeakValue()
            yield (pid, name, peak)
        except Exception:
            continue


def get_roblox_session_peaks(is_roblox_pid):
    """{pid: peak} for Roblox game-client PIDs currently producing audio."""
    return filter_roblox_peaks(_iter_session_peaks(), is_roblox_pid)
```

- [ ] **Step 5: Run to verify all tests pass**

Run: `py -m pytest tests/test_sound_tracker.py -v`
Expected: PASS — detector + filter tests all green.

- [ ] **Step 6: Smoke-check pycaw reads real sessions (manual, optional)**

Run (play any audio first, e.g. a YouTube tab):

```bash
py -c "from utils.sound_tracker import get_roblox_session_peaks; print(get_roblox_session_peaks(lambda pid, name: True))"
```

Expected: a non-empty dict like `{1234: 0.13, ...}` while audio plays; peaks near `0.0` when silent. (This confirms the pycaw path works on this machine.)

- [ ] **Step 7: Commit**

```bash
git add utils/sound_tracker.py tests/test_sound_tracker.py requirements.txt
git commit -m "feat: add pycaw WASAPI peak-reading adapter"
```

---

### Task 3: Sound-monitoring subsystem in the UI

**Files:**
- Modify: `utils/ui.py` (state fields ~115-117; new methods near the rename methods ~9492-9545)

**Interfaces:**
- Consumes: `utils.sound_tracker` (`SoundEdgeDetector`, `get_roblox_session_peaks`, `format_pid_label`, `PYCAW_AVAILABLE`, `POLL_INTERVAL`); existing `self._is_valid_roblox_game_client`, `self._get_user_id_from_pid`, `RobloxAPI.get_username_from_user_id`.
- Produces (methods on `AccountManagerUI`): `start_sound_monitoring()`, `stop_sound_monitoring()`, `_sound_monitoring_worker()`, `_resolve_pid_label(pid) -> str`, `_on_sound_event(pid, label, peak)`, `_is_sound_pid(pid, name) -> bool`; state fields `self.sound_thread`, `self.sound_stop_event`, `self.sound_detector`, `self._sound_pid_labels`, `self._sound_valid_pids`.

- [ ] **Step 1: Add the module import**

In `utils/ui.py`, near the other `from utils...` / top-level imports, add:

```python
from utils import sound_tracker
```

- [ ] **Step 2: Add state fields**

In `utils/ui.py`, immediately after line 117 (`self.renamed_pids = set()`), add:

```python
        # Sound-emission tracking (mirrors rename monitoring above)
        self.sound_thread = None
        self.sound_stop_event = threading.Event()
        self.sound_detector = sound_tracker.SoundEdgeDetector()
        self._sound_pid_labels = {}   # pid -> resolved username (successes only)
        self._sound_valid_pids = {}   # pid -> bool (is a real Roblox game client)
```

- [ ] **Step 3: Add the subsystem methods**

In `utils/ui.py`, immediately after `_rename_monitoring_worker` ends (the rename block spans ~9492-9545; insert after its final line, before the next `def`), add:

```python
    def start_sound_monitoring(self):
        """Start monitoring which Roblox instance emits sound."""
        if not sound_tracker.PYCAW_AVAILABLE:
            print("[Sound] pycaw not installed; sound tracking disabled")
            return
        if self.sound_thread and self.sound_thread.is_alive():
            return
        self.sound_stop_event.clear()
        self.sound_detector = sound_tracker.SoundEdgeDetector()
        self._sound_pid_labels.clear()
        self._sound_valid_pids.clear()
        self.sound_thread = threading.Thread(
            target=self._sound_monitoring_worker, daemon=True)
        self.sound_thread.start()
        print("[Sound] Sound monitoring started")

    def stop_sound_monitoring(self):
        """Stop sound monitoring."""
        if self.sound_thread:
            self.sound_stop_event.set()
            self.sound_thread = None
            self._sound_pid_labels.clear()
            self._sound_valid_pids.clear()
            print("[Sound] Sound monitoring stopped")

    def _is_sound_pid(self, pid, name):
        """Cached check: is this PID a real Roblox game client?"""
        cached = self._sound_valid_pids.get(pid)
        if cached is not None:
            return cached
        valid = self._is_valid_roblox_game_client(pid, name)
        self._sound_valid_pids[pid] = valid
        return valid

    def _resolve_pid_label(self, pid):
        """PID -> username, memoized. Failed lookups are not cached (retry later)."""
        cached = self._sound_pid_labels.get(pid)
        if cached is not None:
            return cached
        username = None
        try:
            user_id, _ = self._get_user_id_from_pid(pid)
            if user_id:
                username = RobloxAPI.get_username_from_user_id(user_id)
        except Exception:
            username = None
        if username:
            self._sound_pid_labels[pid] = username
            return username
        return sound_tracker.format_pid_label(pid, None)

    def _on_sound_event(self, pid, label, peak):
        """Single sink for detected sound. Notification layer plugs in here later."""
        print(f"[Sound] {label} (PID {pid}) emitted sound (peak={peak:.3f})")

    def _sound_monitoring_worker(self):
        """Poll per-process peaks; flag Roblox instances on silent->sound edges."""
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            comtypes = None
        try:
            while not self.sound_stop_event.is_set():
                try:
                    peaks = sound_tracker.get_roblox_session_peaks(self._is_sound_pid)
                    now = time.time()
                    for pid, peak in peaks.items():
                        if self.sound_detector.update(pid, peak, now):
                            label = self._resolve_pid_label(pid)
                            self._on_sound_event(pid, label, peak)
                    live = set(peaks.keys())
                    self.sound_detector.prune(live)
                    self._sound_pid_labels = {
                        p: l for p, l in self._sound_pid_labels.items() if p in live}
                    self._sound_valid_pids = {
                        p: v for p, v in self._sound_valid_pids.items() if p in live}
                except Exception as e:
                    print(f"[Sound] Error in sound monitoring: {e}")
                self.sound_stop_event.wait(sound_tracker.POLL_INTERVAL)
        finally:
            if comtypes is not None:
                try:
                    comtypes.CoUninitialize()
                except Exception:
                    pass
```

- [ ] **Step 4: Verify the module imports without error**

Run: `py -c "import ast; ast.parse(open('utils/ui.py', encoding='utf-8').read()); print('ui.py parses OK')"`
Expected: `ui.py parses OK` (syntax check without launching the GUI).

- [ ] **Step 5: Manual smoke test of the subsystem**

Launch the app (`py main.py`), launch ONE Roblox instance, then from a separate `py` shell in the repo root run the detector against live sessions to confirm labeling — OR simply enable the toggle in Task 4 and watch the console. Confirm: no `[Sound]` lines while the instance is silent; exactly one `[Sound] <username> (PID …) emitted sound` line shortly after audio starts. (Toggle wiring lands in Task 4; this step just confirms the methods run without exceptions.)

- [ ] **Step 6: Commit**

```bash
git add utils/ui.py
git commit -m "feat: add sound-monitoring worker subsystem"
```

---

### Task 4: QOL toggle, boot wiring, close cleanup, docs

**Files:**
- Modify: `utils/ui.py` (QOL toggle ~6681-6699; boot ~6846-6847; close cleanup ~437-438)
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `start_sound_monitoring` / `stop_sound_monitoring` (Task 3); setting key `sound_tracking_enabled`.
- Produces: user-facing toggle + auto-start on launch + clean shutdown.

- [ ] **Step 1: Add the QOL checkbox**

In `utils/ui.py`, immediately AFTER the rename-toggle Checkbutton block (the `def on_rename_toggle` + its `ttk.Checkbutton(...)` that starts at line 6681), add — using the same parent frame `roblox_frame` the rename checkbutton uses:

```python
        sound_var = tk.BooleanVar(value=self.settings.get("sound_tracking_enabled", False))

        def on_sound_toggle():
            enabled = sound_var.get()
            self.settings["sound_tracking_enabled"] = enabled
            self.save_settings()
            if enabled:
                self.start_sound_monitoring()
            else:
                self.stop_sound_monitoring()

        sound_check_text = "Track Roblox Sound Emission"
        if not sound_tracker.PYCAW_AVAILABLE:
            sound_check_text += "  (pycaw not installed)"
        sound_check = ttk.Checkbutton(
            roblox_frame,
            text=sound_check_text,
            variable=sound_var,
            style="Dark.TCheckbutton",
            command=on_sound_toggle
        )
        if not sound_tracker.PYCAW_AVAILABLE:
            sound_check.configure(state="disabled")
        sound_check.pack(anchor="w", pady=(0, 10))
```

> Note: match the exact parent container and pack/grid style used by the neighboring rename checkbutton — read lines 6693-6699 first and mirror them. If the rename checkbutton uses `.grid(...)` rather than `.pack(...)`, use the same geometry manager here.

- [ ] **Step 2: Add boot wiring**

In `utils/ui.py`, immediately after the rename boot lines (6846-6847):

```python
        if self.settings.get("rename_roblox_windows", False):
            self.root.after(1000, self.start_rename_monitoring)
```

add:

```python
        if self.settings.get("sound_tracking_enabled", False):
            self.root.after(1000, self.start_sound_monitoring)
```

- [ ] **Step 3: Add close cleanup**

In `utils/ui.py`, immediately after the rename close-cleanup (lines 437-438):

```python
        if hasattr(self, 'rename_stop_event'):
            self.stop_rename_monitoring()
```

add:

```python
        if hasattr(self, 'sound_stop_event'):
            self.stop_sound_monitoring()
```

- [ ] **Step 4: Verify the module still parses**

Run: `py -c "import ast; ast.parse(open('utils/ui.py', encoding='utf-8').read()); print('ui.py parses OK')"`
Expected: `ui.py parses OK`.

- [ ] **Step 5: Full manual verification**

1. `py main.py` → Settings → the Roblox section shows "Track Roblox Sound Emission".
2. Enable it. Launch one Roblox instance; leave it idle → console shows NO `[Sound]` lines.
3. Trigger audio in that instance → exactly one `[Sound] <username> (PID …) emitted sound (peak=…)` line appears within ~1s.
4. Keep audio playing continuously → no repeat spam (cooldown holds).
5. Toggle off → `[Sound] Sound monitoring stopped`. Close app → no hang/error.

- [ ] **Step 6: Document the subsystem in CLAUDE.md**

In `CLAUDE.md`, add a section (mirroring the style/placement of the existing rename / anti-AFK sections):

```markdown
## Sound-emission tracking

Flags which Roblox instance emits sound. Pure logic lives in
`utils/sound_tracker.py` (constants, `SoundEdgeDetector`, `filter_roblox_peaks`,
and the guarded pycaw peak-reader `get_roblox_session_peaks`). A daemon worker in
`utils/ui.py` (`_sound_monitoring_worker`, started/stopped by
`start_/stop_sound_monitoring`, gated on the `sound_tracking_enabled` setting and
on `pycaw` being installed) polls per-process WASAPI peak meters every
`POLL_INTERVAL` (0.25 s), filters to Roblox game-client PIDs via the cached
`_is_sound_pid`, and runs peaks through `SoundEdgeDetector` (fires once per
silent→sound edge; `RELEASE_SECONDS` debounce + `COOLDOWN_SECONDS` rate limit).
On an edge it resolves PID→username (memoized `_resolve_pid_label`, reusing
`_get_user_id_from_pid` + `RobloxAPI.get_username_from_user_id`) and calls
`_on_sound_event` — the single seam where notification delivery will later plug
in. Tests: `tests/test_sound_tracker.py` (run `py -m pytest tests/ -v`).
New dependency: `pycaw`.
```

- [ ] **Step 7: Commit**

```bash
git add utils/ui.py CLAUDE.md
git commit -m "feat: wire sound tracking into QOL toggle, boot, and shutdown"
```

---

## Self-Review

**Spec coverage:**
- WASAPI peak-meter polling → Task 2 (`get_roblox_session_peaks`) + Task 3 (worker). ✓
- Filter to Roblox PIDs (reuse `_is_valid_roblox_game_client`) → Task 3 (`_is_sound_pid`). ✓
- Edge trigger (silent→sound, release, cooldown, thresholds) → Task 1 (`SoundEdgeDetector` + tests). ✓
- PID→username memoized labeling (log parse + HTTP too costly per tick) → Task 3 (`_resolve_pid_label`, successes cached; failures retry). ✓
- `_on_sound_event` seam; notification out of scope → Task 3. ✓
- Per-tick pruning of state for dead PIDs → Task 3 worker + `SoundEdgeDetector.prune` (Task 1). ✓
- COM init/uninit in worker thread → Task 3. ✓
- Graceful degradation without pycaw → Task 2 (`PYCAW_AVAILABLE`), Task 3 (start guard), Task 4 (disabled toggle note). ✓
- Settings toggle in Roblox/QOL area + boot + close cleanup → Task 4. ✓
- Unit test the detector on synthetic samples; manual integration check → Task 1 tests, Task 3/4 manual steps. ✓
- New dependency pycaw in requirements; pytest dev-only → Task 2 / Task 1. ✓

**Placeholder scan:** No TBD/TODO; every code step shows complete code. The one judgement call (matching the rename checkbutton's geometry manager) is called out explicitly with the exact lines to read. ✓

**Type consistency:** `update(pid, peak, now) -> bool`, `prune(live_pids)`, `filter_roblox_peaks(readings, is_roblox_pid) -> dict`, `get_roblox_session_peaks(is_roblox_pid)`, `format_pid_label(pid, username)`, `_resolve_pid_label(pid) -> str`, `_is_sound_pid(pid, name) -> bool` — names/signatures match across Tasks 1-4. ✓
