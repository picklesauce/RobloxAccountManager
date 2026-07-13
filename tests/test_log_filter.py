"""Tests for utils.log_filter.should_forward_log.

Run: py -m pytest tests/test_log_filter.py -v
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.log_filter import should_forward_log

# Mirrors the app defaults in _default_discord_integration_settings.
DEFAULT_CFG = {
    "log_everything": False,
    "log_errors": True,
    "log_success": True,
    "log_warnings": True,
    "log_info": False,
    "log_auto_rejoin": True,
    "log_auto_rejoin_console": False,
}

# Everything unchecked — the state in the user's screenshot.
ALL_OFF_CFG = {k: False for k in DEFAULT_CFG}

# The exact lines the user reported receiving despite unchecking everything.
INFO_LINE = "[05:37:15] [INFO] Auto-minimized Roblox window for PID 28256.\n"
RENAME_LINE = "[05:37:15] [Rename] Renamed window for PID 28256 -> 'hands0071'\n"
TRACK_LINE = "[05:37:12] [Auto-Rejoin] [hands0071] Successfully tracked PID 28256\n"
PRESENCE_LINE = (
    "[05:37:20] [Auto-Rejoin] [hands0061] Presence check (any game mode) - "
    "in_game: True, place_id: 9404223526\n"
)
ERROR_LINE = "[05:40:00] [ERROR] Something broke\n"
SUCCESS_LINE = "[05:40:00] [SUCCESS] Logged in\n"
WARNING_LINE = "[05:40:00] [WARNING] Slow response\n"
DISCONNECT_LINE = "[05:41:00] [Auto-Rejoin] [hands0061] Disconnection detected! Rejoining...\n"


def test_everything_off_suppresses_all_reported_lines():
    """The core bug: with all filters off, none of these forward."""
    for line in (INFO_LINE, RENAME_LINE, TRACK_LINE, PRESENCE_LINE,
                 ERROR_LINE, SUCCESS_LINE, WARNING_LINE, DISCONNECT_LINE):
        assert should_forward_log(line, ALL_OFF_CFG) is False, line


def test_log_everything_overrides_categories():
    cfg = dict(ALL_OFF_CFG, log_everything=True)
    for line in (INFO_LINE, RENAME_LINE, TRACK_LINE, PRESENCE_LINE, ERROR_LINE):
        assert should_forward_log(line, cfg) is True, line


def test_error_forwarded_when_enabled():
    assert should_forward_log(ERROR_LINE, DEFAULT_CFG) is True


def test_error_not_forwarded_when_disabled():
    assert should_forward_log(ERROR_LINE, dict(DEFAULT_CFG, log_errors=False)) is False


def test_success_and_warning_follow_their_toggles():
    assert should_forward_log(SUCCESS_LINE, DEFAULT_CFG) is True
    assert should_forward_log(WARNING_LINE, DEFAULT_CFG) is True
    off = dict(DEFAULT_CFG, log_success=False, log_warnings=False)
    assert should_forward_log(SUCCESS_LINE, off) is False
    assert should_forward_log(WARNING_LINE, off) is False


def test_info_opt_in_by_default_off():
    assert should_forward_log(INFO_LINE, DEFAULT_CFG) is False
    assert should_forward_log(INFO_LINE, dict(DEFAULT_CFG, log_info=True)) is True


def test_presence_check_is_console_spam():
    # Governed by log_auto_rejoin_console (default off), NOT log_auto_rejoin.
    assert should_forward_log(PRESENCE_LINE, DEFAULT_CFG) is False
    assert should_forward_log(PRESENCE_LINE, dict(DEFAULT_CFG, log_auto_rejoin_console=True)) is True
    # The events toggle alone must not release presence spam.
    assert should_forward_log(PRESENCE_LINE, dict(DEFAULT_CFG, log_auto_rejoin=True, log_auto_rejoin_console=False)) is False


def test_auto_rejoin_events_follow_events_toggle():
    # A non-presence auto-rejoin line is an "event".
    assert should_forward_log(DISCONNECT_LINE, DEFAULT_CFG) is True
    assert should_forward_log(TRACK_LINE, DEFAULT_CFG) is True
    off = dict(DEFAULT_CFG, log_auto_rejoin=False)
    assert should_forward_log(DISCONNECT_LINE, off) is False
    assert should_forward_log(TRACK_LINE, off) is False


def test_uncategorized_only_under_log_everything():
    assert should_forward_log(RENAME_LINE, DEFAULT_CFG) is False
    assert should_forward_log(RENAME_LINE, dict(DEFAULT_CFG, log_everything=True)) is True


def test_substring_blocklist_suppresses_non_error():
    filters = ["You are on the latest version"]
    line = "[05:43:00] [INFO] You are on the latest version\n"
    assert should_forward_log(line, dict(DEFAULT_CFG, log_info=True), filters) is False
    # Even Log Everything respects the blocklist for non-error lines.
    assert should_forward_log(line, dict(DEFAULT_CFG, log_everything=True), filters) is False


def test_substring_blocklist_never_blocks_errors():
    filters = ["boom"]
    line = "[05:44:00] [ERROR] boom happened\n"
    assert should_forward_log(line, DEFAULT_CFG, filters) is True


def test_empty_and_none_inputs_are_safe():
    assert should_forward_log("", DEFAULT_CFG) is False
    assert should_forward_log(None, DEFAULT_CFG) is False
    assert should_forward_log(INFO_LINE, None) is False
