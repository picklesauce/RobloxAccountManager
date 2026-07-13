"""Pure decision logic for whether a console line is forwarded to the Discord
webhook.

Kept dependency-free and side-effect-free so it can be unit-tested without a
running Tk UI. The caller is ``AccountManagerUI._maybe_log_message`` in
``utils/ui.py`` — every ``print()`` in the app is redirected through the console
and offered here.

Design: forwarding is **opt-in**. A line is sent only when its category's Log
Filter toggle is on (or "Log Everything" is on). Unrecognized lines are sent
only under Log Everything.
"""


def should_forward_log(message, cfg, console_filters=None):
    """Return True if ``message`` should be forwarded to the Discord webhook.

    Args:
        message: raw console line, e.g. ``"[05:37:20] [Auto-Rejoin] [acct] ..."``.
            The leading ``[HH:MM:SS]`` stamp does not affect classification since
            matching is by substring.
        cfg: the ``discord_webhook`` settings dict. Reads ``log_everything``,
            ``log_errors``, ``log_success``, ``log_warnings``, ``log_info``,
            ``log_auto_rejoin`` and ``log_auto_rejoin_console``.
        console_filters: iterable of substrings that suppress a line. Never
            applied to ``[ERROR]`` lines (matching the Webhook Filters window's
            "[ERROR] messages are never filtered" note).
    """
    msg = message or ""
    cfg = cfg or {}
    is_error = "[ERROR]" in msg

    # Substring blocklist (Webhook Filters window). [ERROR] is never blocked.
    if not is_error:
        for sub in (console_filters or []):
            if sub and sub in msg:
                return False

    if cfg.get("log_everything"):
        return True

    if is_error:
        return bool(cfg.get("log_errors", True))
    if "[SUCCESS]" in msg:
        return bool(cfg.get("log_success", True))
    if "[WARNING]" in msg:
        return bool(cfg.get("log_warnings", True))
    if "[INFO]" in msg:
        return bool(cfg.get("log_info", False))
    if "[Auto-Rejoin]" in msg:
        # The per-tick presence poll is the high-frequency console spam; every
        # other auto-rejoin line is a state-change "event".
        if "Presence check" in msg:
            return bool(cfg.get("log_auto_rejoin_console", False))
        return bool(cfg.get("log_auto_rejoin", True))

    # Uncategorized lines ([Rename], bare prints) forward only under Log
    # Everything (handled above) — otherwise they stay opt-out.
    return False
