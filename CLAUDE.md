# CLAUDE.md — Roblox Account Manager

## Project overview

Python/Tkinter desktop application for managing multiple Roblox accounts on Windows.
Handles account storage (encrypted), game launching, multi-instance Roblox, auto-rejoin
monitoring, Discord bot/webhook integration, and anti-AFK.

Run with: `py main.py`
Dependencies: `py -m pip install -r requirements.txt`
Requires: Windows, Google Chrome (or bundled Chromium), Python 3.7+

## Architecture

```
main.py                         — Entry point; encryption setup → builds UI
classes/
  __init__.py                   — Exports RobloxAccountManager
  account_manager.py            — RobloxAccountManager: account CRUD, Selenium browser
                                  automation (login flow + browser-click join)
  roblox_api.py                 — RobloxAPI: all HTTP calls (auth ticket, presence,
                                  game info, launch deep-link building, _execute_launch)
  encryption.py                 — Hardware / Password / No-op encryption for cookie storage
  discord_manager.py            — Discord webhook + bot integration
utils/
  ui.py                         — AccountManagerUI (Tkinter): entire UI + all feature logic
                                  (auto-rejoin threads, multi-Roblox, favorites, settings…)
  encryption_setup.py           — First-run encryption wizard
  theme_manager.py              — Dynamic Tk theme/color application
```

### Key responsibilities by file

| File | Owns |
|---|---|
| `roblox_api.py` | Every outbound Roblox HTTP request; `launch_roblox` builds `roblox-player:` deep-link + calls `_execute_launch`; `get_auth_ticket` POSTs to auth.roblox.com |
| `account_manager.py` | Cookie/account persistence, Selenium Chrome driver (`setup_chrome_driver`), browser-based login flow, **`launch_roblox_browser_click`**, **`launch_roblox_profile_join`** (flagged-account path), `open_authenticated_browser` (detached Chrome to any URL), `_try_click_chrome_protocol_dialog` (UI-Automation helper) |
| `utils/ui.py` | All Tkinter windows; auto-rejoin worker threads (`auto_rejoin_worker_for_account`); `_launch_and_track_pid` dispatches launches and tracks PIDs; `_detect_join_off_cycle` + `_is_account_currently_in_game` gate the profile-join path |

## Game launching — two code paths

### 1. API path (default)
`_launch_and_track_pid` → `manager.launch_roblox` → `RobloxAPI.launch_roblox`
→ `RobloxAPI.get_auth_ticket` (POST `auth.roblox.com/v1/authentication-ticket/`)
→ builds `roblox-player:1+launchmode:play+gameinfo:<ticket>+...` URL
→ `RobloxAPI._execute_launch` (os.startfile / Bloxstrap / Fishstrap / Froststrap / Voidstrap / client)

### 2. Profile-join path (flagged-account anti-captcha)
Roblox flags accounts for botting and requires a captcha on API-initiated joins
(`Roblox/WinInet` User-Agent on the auth-ticket request is detectable). The
original browser-click approach (clicking Play on the game page) still triggers
captchas for flagged accounts. The path that works: clicking **Join** on a
friend's Roblox profile inside a real browser.

`_launch_and_track_pid` (config has `join_off_username`)
→ checks parent is in-game via `_is_account_currently_in_game` (returns `None`
   if not — auto-rejoin treats `None` as "skipped, don't burn a retry")
→ `manager.launch_roblox_profile_join(account, friend_username, …)`
  1. Resolves friend username → user ID via `RobloxAPI.get_user_id_from_username`
  2. Spins up a fresh temp Chrome profile via Selenium
  3. Plants `.ROBLOSECURITY` cookie on roblox.com
  4. Navigates to `https://www.roblox.com/users/{friend_user_id}/profile`
  5. Injects the same JS interceptors as below (capture `roblox-player:` URLs)
  6. Polls up to 20 s for a "Join" button using a multi-strategy selector
     (testid → class → text/aria-label/title)
  7. Clicks via `ActionChains.move_to_element(...).click()` so the click carries
     `event.isTrusted=true` (synthetic JS `.click()` is often ignored by Roblox)
  8. Waits up to 20 s for **either** `window.__rblxLaunchUrl` to be populated
     **or** Chrome's "Open Roblox Game Client?" protocol dialog to appear
  9. URL path → `RobloxAPI._execute_launch` (honors launcher preference).
     Dialog path → `_try_click_chrome_protocol_dialog` dismisses it via
     `pywinauto` UI Automation (Chrome's dialog is canvas-drawn, not real
     Win32 controls); the OS protocol handler launches whatever client is
     registered for `roblox-player:` (launcher preference is ignored on this
     path)
  10. Cleans up driver + temp profile

### Legacy browser-click path
`launch_roblox_browser_click` (same idea, clicking Play on the game page) is
still in `account_manager.py` but no longer wired into the UI — flagged
accounts get captcha'd on this path, so it was replaced by profile-join.

**Limitations of profile-join:** the dependent account ends up in whatever
game the friend is in, not necessarily a configured `place_id`. The auto-rejoin
worker accounts for this by forcing the "in any game" presence branch whenever
`join_off_username` is set.

### Main-window Mode dropdown (Place ID vs Join off Friend)
The right-column **Mode** combobox (`join_mode_combo`, persisted as
`last_join_mode`) switches what the primary Join button does:
- **Place ID** → shows the Place ID field; left-click runs `launch_game()`
  (API path, unchanged).
- **Join off Friend** → shows a **Friend Username** field (persisted as
  `last_join_off_username`) and disables the Private Server field; left-click
  runs `launch_join_off_friend()`.

`_apply_join_mode()` is the single source of truth for the mode's visual state
(swaps the field frame in `join_field_container`, relabels the button, toggles
the Private Server entry). `launch_join_off_friend()` mirrors `launch_game()`
(multi-select aware, PID labeling via `_record_launched_account`, window
arrangement for 2+), but resolves the friend, presence-checks them once using a
selected account's cookie (the friend need not be a managed account), then per
account calls `manager.launch_roblox_follow_user` (when `join_off_use_app`) or
`manager.launch_roblox_profile_join` — the **same follow-user / profile-join
paths auto-rejoin's join-off uses**. This differs from the right-click
dropdown's *Join User* by launch **mechanism**: *Join User* reads the target's
presence and joins their current game/job via the API path (`launch_roblox` →
auth ticket), whereas *Join off Friend* uses the follow-user / profile-join
paths.

### Launch Roblox Home dropdown
The homepage "Launch Roblox Home  ▼" button opens a popup menu:
- **Launch in App** → `launch_home()` (existing — API-path launch with `place_id=""`)
- **Launch in Browser** → `launch_home_in_browser()` → spawns a thread per
  selected account calling `manager.open_authenticated_browser(uname,
  "https://www.roblox.com/home")` (detached Chrome, cookie planted, no driver
  cleanup — Chrome stays open after the function returns)

## Auto-rejoin system

Config stored in `settings['auto_rejoin_configs']` keyed by username:
```python
{
  'place_id': str,             # optional if join_off_username is set
  'private_server': str,       # link code, share URL, or empty
  'job_id': str,
  'check_interval': int,       # seconds between presence checks
  'max_retries': int,
  'check_presence': bool,      # forced False when join_off_username is set
  'check_internet_before_launch': bool,
  'join_off_username': str,    # if set: profile-join off this friend
                               # (mutually exclusive with place_id in the UI)
}
```

`place_id` and `join_off_username` are **mutually exclusive** at the UI layer
(Add/Edit dialogs enforce on save + live-disable the other entry as one is
typed in). Either alone is valid; both empty is rejected.

### Cycle detection + ordering
- `_detect_join_off_cycle(account, new_join_off)` runs on save; rejects configs
  that would form a cycle (A→B→A).
- Worker startup order doesn't matter. The dependent (B) calls
  `_is_account_currently_in_game(parent)` before each launch attempt; if the
  parent isn't in-game, `_launch_and_track_pid` returns `None`. Workers treat
  `None` as "skipped, retry next tick" (no max-retries penalty). When the
  parent enters a game, the next tick of the dependent's worker fires the
  profile-join.

Each active config runs `auto_rejoin_worker_for_account` in a daemon thread.
The worker uses `RobloxAPI.get_player_presence` to detect disconnection, then calls
`_launch_and_track_pid` to relaunch. PID tracking (`auto_rejoin_pids`) is used to
kill the old Roblox instance before relaunching.

## Launcher preferences

Set in settings as `roblox_launcher`. Options: `default`, `bloxstrap`, `fishstrap`,
`froststrap`, `voidstrap`, `client`, `custom`. Handled entirely in
`RobloxAPI._execute_launch` — all launch code paths end here.

## Settings window & window arrangement

`open_settings` (in `utils/ui.py`) builds a 7-tab notebook, in order:
`General | Themes | Roblox | Tool | Discord | Developer | QOL`.

The **QOL** tab holds quality-of-life toggles plus the window-arrangement
controls (relocated out of General):

- `auto_tile_windows` / `auto_minimize_windows` — **independent** booleans (not
  mutually exclusive). On a multi-account launch both may be on; the order is
  always **tile, then minimize** so that restoring a minimized window later
  reveals it in its tiled slot.
- Manual **Tile Windows** / **Minimize Windows** buttons act on currently-open
  Roblox windows immediately — each runs `_tile_roblox_windows` /
  `_minimize_roblox_windows` in a daemon thread, and silently no-ops when no
  Roblox windows are open.
- Convenience toggles: `enable_topmost`, `confirm_before_launch`, multi-select
  (Ctrl+Click), `disable_launch_popup`.

Window-arrangement helpers (all in `utils/ui.py`):

- `_apply_window_arrangement` — single source of truth; applies whichever prefs
  are enabled in tile→minimize order.
- `_arrange_roblox_windows_after_launch` — waits for the new Roblox process(es)
  to appear (~6 s settle), then calls `_apply_window_arrangement`. Spawned as a
  daemon thread from `launch_home` / `launch_game` whenever 2+ accounts launch
  and either toggle is set.
- `_arrange_roblox_windows_after_start_all` — same idea after the auto-rejoin
  "Start All", also ending in `_apply_window_arrangement`.
- `_minimize_roblox_window_for_pid(pid)` — minimizes **only** the window owned by
  `pid`, polling up to 45 s for that window to appear. Used by the auto-rejoin
  worker path (see below) so a freshly (re)launched instance is minimized
  without disturbing other windows. Unlike `_apply_window_arrangement` (which
  acts on *all* Roblox windows), this is per-PID.

The above `_apply_window_arrangement`-based helpers cover **manual** launches and
"Start All". The auto-rejoin **worker** path (initial per-account start *and*
every disconnect-relaunch) goes through `_launch_and_track_pid`, which — when
`auto_minimize_windows` is set — spawns `_minimize_roblox_window_for_pid` for the
newly-tracked PID in a daemon thread (off the `auto_rejoin_launch_lock`). This is
why auto-minimize now applies to auto-rejoin relaunches, not just batch launches.

(Replaces the older `_tile_roblox_windows_after_launch` /
`_minimize_roblox_windows_after_launch` pair and the previous "minimize *or*
tile" mutually-exclusive logic.)

## Anti-AFK

The Anti-AFK window (`open_anti_afk_window` in `utils/ui.py`) keeps Roblox
sessions alive by activating each Roblox window in turn and sending the
configured action key/mouse input (`_anti_afk_run_maintenance_cycle` →
`_anti_afk_perform_action`). Settings live under `anti_afk_*`
(`anti_afk_enabled`, `anti_afk_interval_minutes`, `anti_afk_press_count`,
`anti_afk_key`, `anti_afk_tooltip_enabled`).

Two ways to fire a maintenance pass, both funneling through
**`_anti_afk_trigger_once`**:

- **Timer** — `anti_afk_worker` (daemon thread, started by `start_anti_afk`)
  waits the configured interval, shows a 30 s countdown tooltip, then triggers
  a pass. Enabled via the "Enable Anti-AFK" checkbox.
- **Manual "Trigger Now" button** — runs one pass immediately in a daemon
  thread, independent of the timer (works whether or not the timer is enabled).

`_anti_afk_trigger_once` holds **`self.anti_afk_run_lock`** (non-blocking
acquire) so the timer and the manual button can't run a pass simultaneously and
fight over window focus — if a pass is already running, the second trigger is
skipped. `_anti_afk_run_maintenance_cycle` takes a `should_stop` callable for
mid-pass cancellation: the timer passes `anti_afk_stop_event.is_set` (so
disabling Anti-AFK aborts an in-flight timed pass), while the manual button
passes nothing so a one-shot pass always completes (the manual path must NOT be
gated on `anti_afk_stop_event`, which stays *set* whenever the timer is off).
## Instance labeling (auto-rename)

Roblox instances are labeled from an **authoritative `pid_account_map`
(PID → account username)** captured at launch — no HTTP, no log-parsing. Every
launch path (`launch_game`/`launch_home` workers and the auto-rejoin
`_launch_and_track_pid`) snapshots Roblox PIDs before launch, and
`_record_launched_account` uses `utils/pid_labels.pick_launched_pid` to identify
the one new PID and record it. If `rename_roblox_windows` (default **on**) is set,
`_rename_window_for_pid_when_ready` waits for that PID's window and sets its title
to the account name. `_match_pids_to_accounts` (auto-rejoin "Start All") also
writes the map; dead PIDs are dropped on disconnect. Only manager-launched
instances are labeled. The old polling rename worker (`_rename_monitoring_worker`)
was removed. Tests: `tests/test_pid_labels.py`.

## Encryption

Three modes selected at first run: Hardware (tied to machine), Password (portable),
None. Cookies are stored encrypted in `AccountManagerData/`. Switching modes is
supported via the Tool tab in Settings.

## Data folder

`AccountManagerData/` (next to the executable / working dir):
- `accounts.json` — encrypted account cookies + metadata
- `settings.json` — all UI/feature settings
- `encryption_config.json` — which encryption mode is active
- `icon.ico`, `discordlogo.png` — downloaded on first run if absent
- `Chromium/` — bundled Chromium if user downloads it via Settings → Tools

## Windows-only notes

- Uses `ctypes.windll.user32` for window detection (`FindWindowW`)
- Uses `subprocess` with `CREATE_NO_WINDOW` creationflags throughout
- Uses `tasklist` / `taskkill` for PID management in auto-rejoin
- Multi-Roblox mutex removal uses `handle64.exe` (Windows tool)
- Anti-AFK uses `win32api` / `win32con` for key/mouse injection
- Profile-join uses `pywinauto` (UIA backend) to dismiss Chrome's external-
  protocol confirmation dialog. The dialog's buttons are canvas-drawn, not
  Win32 controls, so `win32gui.EnumChildWindows` can't reach them — UIA can.
