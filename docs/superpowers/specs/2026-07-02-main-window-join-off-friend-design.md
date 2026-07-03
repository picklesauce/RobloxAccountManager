# Main-window "Join off Friend" mode — Design

**Date:** 2026-07-02
**Status:** Approved (pending spec review)

## Problem

The main window can only join by **Place ID** (plus the right-click extras: *Join
User*, *Job-ID*, *Small Server*). All of those go through the **API launch path**,
which triggers a captcha for accounts Roblox has flagged for botting.

Auto-rejoin already solved this with its **"join off a friend"** feature, which
uses the **anti-captcha** path — either app-follow
(`launch_roblox_follow_user`, the default when `join_off_use_app=True`) or browser
profile-join (`launch_roblox_profile_join`). The user wants that same capability
available directly on the main window as a first-class option.

This is a genuinely new capability on the main window, **not** a rename of the
existing *Join User* (which is the captcha-prone API path that joins a user's
*current game* via presence).

## Goal

Add a **Mode dropdown** next to the Place ID field on the main window that
switches between:

- **Place ID** — current behavior, unchanged.
- **Join off Friend** — launch the selected account(s) off a friend using the
  same anti-captcha path auto-rejoin uses.

## Non-goals (YAGNI)

- No cycle detection (that's an auto-rejoin-only concern — it runs continuous
  workers; this is a one-shot manual launch).
- No changes to auto-rejoin.
- No new backend launch functions — reuse existing
  `manager.launch_roblox_follow_user` / `manager.launch_roblox_profile_join`.
- No new "app vs browser" setting — reuse the existing `join_off_use_app`.

## Locked-in decisions

1. **Backend path:** reuse `join_off_use_app` (app-follow default; browser
   profile-join when the user turned it off). Consistent with auto-rejoin.
2. **Multi-account:** honors multi-select exactly like the current Join button —
   launches every selected account off the one friend, sequentially.
3. **Not-in-game handling:** presence-check the friend once before launching
   (like *Join User*). If the friend is not in a joinable game, show a message
   and launch nothing.
4. **Private Server field:** disabled/greyed in Join-off-Friend mode (irrelevant
   when following a friend).

## UI changes (`utils/ui.py`, `right_frame`, ~lines 296–320)

- Add a read-only `ttk.Combobox` **"Mode"** above the Place ID label. Values:
  `Place ID`, `Join off Friend`. Selected value persists in a new setting
  `last_join_mode` (default `Place ID`).
- Keep `self.place_entry`. Add a sibling `self.friend_entry` that occupies the
  same slot. Its label reads **"Friend Username"**. Its last value persists as a
  new setting `last_join_off_username`.
- A helper `_apply_join_mode()` is the single source of truth for the mode's
  visual state. It:
  - shows the active entry and its label, hides the other (pack/pack_forget, or
    keep both packed and toggle which is visible — implementation detail);
  - swaps the primary button text between **"Join Place ID"** and
    **"Join off Friend"**;
  - enables/disables `self.private_server_entry` (disabled in friend mode);
  - runs on startup (after widgets built) and whenever the combobox changes
    (`<<ComboboxSelected>>`), and writes `last_join_mode`.
- The right-click dropdown (*Join User / Job-ID / Small Server*) is unchanged.

### Window sizing

The main window is `450x520` and non-resizable (`utils/ui.py:96` and `:98`,
`resizable(False, False)` at `:100`). The new combobox row adds ~30px to the
right column. Bump the height in **both** geometry branches (the saved-position
branch at line 96 and the default at line 98) from `520` to a value that fits the
extra row (target ~`555`; verify empirically that nothing is clipped). Keep the
window non-resizable.

## Launch flow

- `on_join_place_split_click` (left-click handler, `utils/ui.py:1406`) branches
  on `last_join_mode`:
  - `Place ID` → existing `self.launch_game()` (unchanged).
  - `Join off Friend` → new `self.launch_join_off_friend()`.
- **`launch_join_off_friend()`** mirrors the structure of `launch_game()`
  (`utils/ui.py:4265`):
  1. Resolve selected account(s) via the same multi-select logic
     (`get_selected_usernames` / `get_selected_username`).
  2. Read `self.friend_entry`; if empty, warn and return. Persist
     `last_join_off_username`.
  3. Optional `confirm_before_launch` prompt (reuse the existing setting; phrase
     for "join off `<friend>`").
  4. Daemon worker thread:
     - Resolve friend username → user ID via
       `RobloxAPI.get_user_id_from_username` (use the cached variant with
       `self.settings['user_id_cache']`, matching `_is_account_currently_in_game`).
       If not found → error dialog, return.
     - Presence-check the friend once (reuse `_is_account_currently_in_game`
       or a direct `get_player_presence`). If not in game → info dialog
       ("'<friend>' is not currently in a game"), return.
     - For each selected account, snapshot `pids_before = self._get_roblox_pids()`,
       then call `manager.launch_roblox_follow_user(...)` if
       `join_off_use_app` else `manager.launch_roblox_profile_join(...)`, using
       `self._get_roblox_launcher_config()` for launcher pref + custom path.
       On success, `self._record_launched_account(uname, pids_before)` for
       PID→account labeling (same as `launch_game`).
     - If 2+ accounts launched and `auto_tile_windows` or
       `auto_minimize_windows` is set, spawn
       `self._arrange_roblox_windows_after_launch` (same as `launch_game`).
     - `on_done` (via `self.root.after(0, ...)`): update `last_joined_user`,
       `save_settings()`, and show the standard success/failure messagebox
       (respect `disable_launch_popup`). Recent-games list is **not** updated
       (we don't know the friend's place ahead of time; keep it simple).

## Settings added

| Key | Default | Meaning |
|---|---|---|
| `last_join_mode` | `"Place ID"` | Remembers the mode dropdown selection. |
| `last_join_off_username` | `""` | Remembers the friend-username entry. |

Both added to the settings defaults blocks (near `last_place_id`, ~lines 900 &
932) so `load_settings` seeds them.

## Error handling

- Empty friend username → warning messagebox, no launch.
- Friend user not found → error messagebox.
- Friend not in a joinable game → info messagebox, no launch.
- Per-account launch exceptions are caught and logged (as in `launch_game`);
  partial success still reports the success count.
- Backend anti-captcha paths already handle their own driver/temp-profile
  cleanup and dialog dismissal; no new cleanup logic here.

## Testing

- No pure-logic module is added, so no new unit-test file is strictly required.
  The change is UI wiring + reuse of existing, already-tested launch paths.
- Manual verification checklist:
  - Toggling the mode swaps label/entry/button text and enables/disables the
    Private Server field.
  - `last_join_mode` / `last_join_off_username` persist across restart.
  - Place-ID mode behaves exactly as before.
  - Join-off-Friend mode launches a single account off an in-game friend
    (app path and, with `join_off_use_app` off, browser path).
  - Multi-select launches all selected accounts off the friend.
  - Friend offline / not-in-game / unknown username each show the right message
    and launch nothing.
  - Window shows no clipped controls at the new height.
