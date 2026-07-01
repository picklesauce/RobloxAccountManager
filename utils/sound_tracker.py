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
