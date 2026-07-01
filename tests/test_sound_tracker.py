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
