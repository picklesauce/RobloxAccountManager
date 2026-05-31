# QOL Settings Tab + Non-Exclusive Window Arrangement — Design

**Date:** 2026-05-31
**Area:** `utils/ui.py` (Settings window + window-arrangement helpers)

## Goal

Add organization to the Settings window by introducing a dedicated **QOL**
(quality-of-life) tab. Move the window-arrangement options and several
convenience toggles into it, make auto-tile and auto-minimize independent
(non-exclusive), and add two manual "apply now" buttons.

## Requirements

1. Add a new **QOL** notebook tab to the Settings window.
2. Move **Auto Tile Windows** and **Auto Minimize Windows** into QOL.
3. Make Auto Tile and Auto Minimize **not mutually exclusive** (both can be on;
   they apply on launch).
4. Add a **Tile Windows** button and a **Minimize Windows** button that act on
   currently-open Roblox windows immediately. Place both in QOL.
5. Move additional convenience toggles into QOL: **Enable Topmost**,
   **Confirm Before Launch**, **Multi Select (Ctrl+Click)**,
   **Disable Launch Success Popup**.
6. Ensure the Settings window has enough room for a 7th tab.

## Decisions (from brainstorming)

- **Placement:** new dedicated QOL tab (not a section inside General).
- **Both-on launch behavior:** **tile, then minimize** — so restoring a
  minimized window later reveals it in its tiled slot.
- **Convenience toggles to move:** all four listed in requirement 5.
- **Left in General (not moved):** Add to Start Menu, Max Recent Games (these
  are setup/config rather than comfort settings).

## Layout

QOL tab, top → bottom:

```
── Window arrangement ──────────
[ ] Auto Tile Windows        (on launch)
[ ] Auto Minimize Windows    (on launch)
Apply now:  [ Tile Windows ] [ Minimize Windows ]

── Convenience ─────────────────
[ ] Enable Topmost
[ ] Confirm Before Launch
[ ] Multi Select (Ctrl + Click)
[ ] Disable Launch Success Popup
```

Tab order in the notebook: `General | Themes | Roblox | Tool | Discord |
Developer | QOL`.

## Changes

### Settings window (`open_settings` in `utils/ui.py`)

- Widen the window: `settings_width` **330 → 400** so all 7 tabs fit. Height
  stays **470** (General loses items; QOL content is short).
- Add `qol_tab = ttk.Frame(...)`, `tabs.add(qol_tab, text="QOL")` after the
  Developer tab. Build a `qol_frame` inside it.
- Relocate widget creation for the six toggles from `main_frame` (General) into
  `qol_frame`. Their `tk.*Var` definitions and command callbacks are unchanged —
  only the parent frame and `.pack()` location change. `self.<name>_check`
  attribute assignments are preserved.
  - Topmost still applies `-topmost` to root + settings window via its existing
    `auto_save_setting("enable_topmost", ...)` save hook.
  - Multi Select still flips `self.account_list` `selectmode` via
    `on_multi_select_toggle`.
- Add the two manual buttons in an "Apply now" row inside the window-arrangement
  group.

### Non-exclusive toggles

In `on_auto_tile_toggle` / `on_auto_minimize_toggle`, remove the logic that
clears the *other* setting. Each handler now only saves its own boolean:

```python
def on_auto_tile_toggle():
    self.settings["auto_tile_windows"] = auto_tile_windows_var.get()
    self.save_settings()

def on_auto_minimize_toggle():
    self.settings["auto_minimize_windows"] = auto_minimize_windows_var.get()
    self.save_settings()
```

### Ordered apply helper

Add one helper so every launch path applies the same ordered behavior:

```python
def _apply_window_arrangement(self):
    """Apply enabled window-arrangement preferences in order: tile then
    minimize (so a later restore shows the tiled slot)."""
    if self.settings.get("auto_tile_windows", False):
        self._tile_roblox_windows()
    if self.settings.get("auto_minimize_windows", False):
        self._minimize_roblox_windows()
```

- `_arrange_roblox_windows_after_start_all`: replace its trailing
  `if minimize / elif tile` block with `self._apply_window_arrangement()`.
- New `_arrange_roblox_windows_after_launch`: same "wait until the Roblox
  process count rises, then settle ~6s" loop used by the current
  `*_after_launch` helpers, followed by `self._apply_window_arrangement()`.
- Launch call sites (`launch_home` ~line 4209, `launch_game` ~line 4289):
  replace the two-branch block with a single thread when either toggle is set:

  ```python
  if success_count > 1 and (self.settings.get("auto_tile_windows", False)
                            or self.settings.get("auto_minimize_windows", False)):
      threading.Thread(target=self._arrange_roblox_windows_after_launch,
                       daemon=True).start()
  ```

- Remove the now-unused `_tile_roblox_windows_after_launch` and
  `_minimize_roblox_windows_after_launch` helpers (no remaining references).

**Why one thread, not two:** starting separate tile and minimize threads would
race, so tile-before-minimize ordering couldn't be guaranteed. A single thread
through `_apply_window_arrangement` makes the order deterministic.

### Manual buttons

```python
def _qol_tile_now():
    threading.Thread(target=self._tile_roblox_windows, daemon=True).start()

def _qol_minimize_now():
    threading.Thread(target=self._minimize_roblox_windows, daemon=True).start()
```

Run in daemon threads so the UI never blocks. The underlying helpers already
no-op silently when no Roblox windows are open (consistent with existing
behavior — no error popup).

## Data / settings

No new settings keys. Reuses existing `auto_tile_windows` and
`auto_minimize_windows` booleans (defaults remain `False` at both default-build
sites). Manual buttons persist nothing.

## Out of scope

- Moving Add to Start Menu / Max Recent Games into QOL.
- Any change to the actual tiling grid math or minimize mechanics.
- A "no Roblox windows open" notification for the manual buttons.

## Verification

- `py -m py_compile utils/ui.py` — confirm no syntax breakage.
- Manual smoke (typically via the CI-built EXE per the user's run setup):
  open Settings → confirm a **QOL** tab exists and all 7 tabs are visible;
  both auto checkboxes can be enabled at once; the **Tile Windows** /
  **Minimize Windows** buttons act on open Roblox instances; the four moved
  toggles still behave (topmost, confirm, multi-select, popup suppression).
