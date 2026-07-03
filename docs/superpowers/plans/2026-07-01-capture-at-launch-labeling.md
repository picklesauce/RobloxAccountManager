# Capture-at-Launch Account Labeling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Label Roblox instances (window titles + sound events) from an authoritative PID→account map captured at launch, eliminating the wrong/duplicate names caused by log-parse + HTTP reverse-lookup.

**Architecture:** A pure `pick_launched_pid` helper identifies the new PID a launch produced. `utils/ui.py` records `pid_account_map[pid] = account` at every launch (normal + auto-rejoin), renames the window off-thread, and the sound tracker's label lookup reads the same map. The old polling rename worker is removed.

**Tech Stack:** Python 3.12, Tkinter, `psutil` (PID enumeration), `pywin32` (`win32gui` window rename), `pytest` (dev-only).

## Global Constraints

- Windows-only. Python floor 3.7+ (dev runs 3.12.10). Run scripts with `py`. Run pytest from repo root.
- **Manager-launched instances only** — no HTTP and no log-parsing in the rename/label path. External/pre-existing instances are not auto-renamed.
- `utils/pid_labels.py` MUST be pure (no Tkinter, no threading, no psutil) so it unit-tests without a UI.
- All access to `self.pid_account_map` MUST go through `self.pid_account_lock`.
- `rename_roblox_windows` setting **defaults to `True`** — every read uses `self.settings.get("rename_roblox_windows", True)`.
- Keep `_get_user_id_from_pid` and `_match_pids_to_accounts` (auto-rejoin "Start All" still uses them). Keep `_rename_roblox_window`. Remove only the polling rename worker + its wiring.
- Reuse existing helpers verbatim: `_get_roblox_pids()` (ui.py:10695), `_get_roblox_hwnds_from_pids(pids)` (used at ui.py:3004), `_rename_roblox_window(pid, name)` (ui.py:9616).

## File Structure

- **Create `utils/pid_labels.py`** — pure `pick_launched_pid(pids_before, pids_after, assigned)`.
- **Create `tests/test_pid_labels.py`** — unit tests for it.
- **Modify `utils/ui.py`** — map state + capture/rename helpers; wire both launch paths; rewrite `_resolve_pid_label`; remove polling rename worker + wiring; default-on toggle; auto-rejoin + match map maintenance.
- **Modify `CLAUDE.md`** — replace the rename description with the capture-at-launch model.

---

### Task 1: Pure `pick_launched_pid` helper

**Files:**
- Create: `utils/pid_labels.py`
- Create: `tests/test_pid_labels.py`

**Interfaces:**
- Produces: `pick_launched_pid(pids_before: set[int], pids_after: set[int], assigned: set[int]) -> int | None` — the single PID in `pids_after - pids_before - assigned`; `None` if that set is empty or has more than one element (ambiguous).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pid_labels.py`:

```python
from utils.pid_labels import pick_launched_pid


def test_single_new_pid_returned():
    assert pick_launched_pid({1, 2}, {1, 2, 3}, assigned=set()) == 3


def test_no_new_pid_returns_none():
    assert pick_launched_pid({1, 2}, {1, 2}, assigned=set()) is None


def test_two_new_pids_is_ambiguous_returns_none():
    assert pick_launched_pid({1}, {1, 2, 3}, assigned=set()) is None


def test_new_pid_already_assigned_is_excluded():
    # 3 appeared but is already owned by another account -> not a candidate
    assert pick_launched_pid({1, 2}, {1, 2, 3}, assigned={3}) is None


def test_assigned_pid_excluded_leaving_one_candidate():
    # 3 already assigned, 4 is the genuinely new one
    assert pick_launched_pid({1, 2}, {1, 2, 3, 4}, assigned={3}) == 4
```

- [ ] **Step 2: Run to verify failure**

Run: `py -m pytest tests/test_pid_labels.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.pid_labels'`.

- [ ] **Step 3: Implement `utils/pid_labels.py`**

Create `utils/pid_labels.py`:

```python
"""
Pure helper for capture-at-launch account labeling.

No Tkinter, threading, or psutil here so it unit-tests without a UI or a live
process table. See utils/ui.py for the stateful map that consumes this.
"""


def pick_launched_pid(pids_before, pids_after, assigned):
    """
    Identify the single new Roblox PID a launch produced.

    Returns the one PID present in `pids_after` but not in `pids_before` and not
    already in `assigned`. Returns None when there are zero such PIDs (process
    not up yet) or more than one (ambiguous — refuse to guess).
    """
    candidates = (set(pids_after) - set(pids_before)) - set(assigned)
    if len(candidates) == 1:
        return next(iter(candidates))
    return None
```

- [ ] **Step 4: Run to verify pass**

Run: `py -m pytest tests/test_pid_labels.py -v`
Expected: PASS — 5 tests green.

- [ ] **Step 5: Commit**

```bash
git add utils/pid_labels.py tests/test_pid_labels.py
git commit -m "feat: add pure pick_launched_pid helper"
```

---

### Task 2: Authoritative map + capture/rename helpers

**Files:**
- Modify: `utils/ui.py` (import ~line 50; state fields ~line 122; new methods near `_rename_roblox_window` ~line 9616)

**Interfaces:**
- Consumes: `pick_launched_pid` (Task 1); existing `_get_roblox_pids()`, `_get_roblox_hwnds_from_pids()`, `_rename_roblox_window()`.
- Produces: `self.pid_account_map: dict[int, str]`, `self.pid_account_lock`; `_record_launched_account(account, pids_before, timeout=12) -> int | None`; `_rename_window_for_pid_when_ready(pid, name, timeout=45)`.

- [ ] **Step 1: Add the import**

In `utils/ui.py`, find (line ~50):

```python
from utils import sound_tracker
```

Change to:

```python
from utils import sound_tracker
from utils import pid_labels
```

- [ ] **Step 2: Add map state**

In `utils/ui.py`, find the sound-tracking state block (lines ~123-128) and add the map fields immediately after `self._sound_valid_pids = {}`:

```python
        self._sound_valid_pids = {}   # pid -> bool (is a real Roblox game client)

        # Authoritative PID -> account username, captured at launch. Source of
        # truth for window auto-rename and sound-event labels. Written by launch
        # worker threads, read by the sound worker thread -> guard with the lock.
        self.pid_account_map = {}
        self.pid_account_lock = threading.Lock()
```

- [ ] **Step 3: Add the capture + rename helpers**

In `utils/ui.py`, immediately BEFORE `def _rename_roblox_window(self, pid, username):` (line ~9616), insert:

```python
    def _record_launched_account(self, account, pids_before, timeout=12):
        """After launching `account`, find the new Roblox PID it produced and
        record it authoritatively in pid_account_map. Renames its window
        off-thread when enabled. Returns the PID, or None if none could be
        unambiguously identified within `timeout` seconds.

        Call this synchronously from a launch worker (it polls up to `timeout`),
        so each account's PID is claimed before the next launch starts."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            pids_after = self._get_roblox_pids()
            with self.pid_account_lock:
                assigned = set(self.pid_account_map)
            new_pid = pid_labels.pick_launched_pid(pids_before, pids_after, assigned)
            if new_pid is not None:
                with self.pid_account_lock:
                    self.pid_account_map[new_pid] = account
                print(f"[Rename] Tracked {account} -> PID {new_pid}")
                if self.settings.get("rename_roblox_windows", True):
                    threading.Thread(
                        target=self._rename_window_for_pid_when_ready,
                        args=(new_pid, account),
                        daemon=True
                    ).start()
                return new_pid
            time.sleep(0.5)
        print(f"[Rename] Could not identify a new PID for {account} within {timeout}s")
        return None

    def _rename_window_for_pid_when_ready(self, pid, name, timeout=45):
        """Wait for the window owned by `pid` to appear, then set its title to
        `name`. Mirrors _minimize_roblox_window_for_pid's polling. Daemon thread
        only — never call while holding a launch lock."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._get_roblox_hwnds_from_pids({pid}):
                self._rename_roblox_window(pid, name)
                print(f"[Rename] Renamed window for PID {pid} -> '{name}'")
                return
            time.sleep(1)
        print(f"[Rename] Window for PID {pid} never appeared within {timeout}s; not renamed")

```

- [ ] **Step 4: Verify parse + import**

Run: `py -c "import ast; ast.parse(open('utils/ui.py',encoding='utf-8').read()); print('parse OK')"`
Run: `py -c "import utils.ui; print('import OK')"`
Expected: `parse OK` then `import OK`.

- [ ] **Step 5: Commit**

```bash
git add utils/ui.py
git commit -m "feat: add pid_account_map and capture/rename helpers"
```

---

### Task 3: Wire capture into all launch paths

**Files:**
- Modify: `utils/ui.py` — `launch_home` worker (~4231-4238), `launch_game` worker (~4307-4316), `_launch_and_track_pid` (~4676-4690 region around `self.auto_rejoin_pids[account] = new_pid`)

**Interfaces:**
- Consumes: `_record_launched_account` (Task 2), `pid_account_map`/`pid_account_lock`, existing `_get_roblox_pids`, `_rename_window_for_pid_when_ready`.

- [ ] **Step 1: Wire `launch_home` worker**

In `utils/ui.py`, find the `launch_home` worker loop:

```python
            for uname in selected_usernames:
                try:
                    if self.manager.launch_roblox(uname, "", "", launcher_pref, "", custom_launcher_path):
                        success_count += 1
                    else:
                        failed_launch = True
                except Exception as e:
                    print(f"[ERROR] Failed to launch Roblox home for {uname}: {e}")
```

Replace with:

```python
            for uname in selected_usernames:
                pids_before = self._get_roblox_pids()
                try:
                    if self.manager.launch_roblox(uname, "", "", launcher_pref, "", custom_launcher_path):
                        success_count += 1
                        self._record_launched_account(uname, pids_before)
                    else:
                        failed_launch = True
                except Exception as e:
                    print(f"[ERROR] Failed to launch Roblox home for {uname}: {e}")
```

- [ ] **Step 2: Wire `launch_game` worker**

In `utils/ui.py`, find the `launch_game` worker loop:

```python
            for i, uname in enumerate(selected_usernames):
                try:
                    if self.manager.launch_roblox(uname, pid, psid, launcher_pref, "", custom_launcher_path):
                        success_count += 1
                    else:
                        failed_launch = True
                except Exception as e:
                    print(f"[ERROR] Failed to launch game for {uname}: {e}")
                if i < len(selected_usernames) - 1:
                    time.sleep(2)
```

Replace with (note: `pid` here is the place-id local — do not shadow it; the blind `sleep(2)` is removed because `_record_launched_account` already waits for the process):

```python
            for i, uname in enumerate(selected_usernames):
                pids_before = self._get_roblox_pids()
                try:
                    if self.manager.launch_roblox(uname, pid, psid, launcher_pref, "", custom_launcher_path):
                        success_count += 1
                        self._record_launched_account(uname, pids_before)
                    else:
                        failed_launch = True
                except Exception as e:
                    print(f"[ERROR] Failed to launch game for {uname}: {e}")
```

- [ ] **Step 3: Wire `_launch_and_track_pid` (auto-rejoin path)**

In `utils/ui.py`, find (in `_launch_and_track_pid`):

```python
            if available_pids:
                new_pid = max(available_pids)
                self.auto_rejoin_pids[account] = new_pid
                print(f"[Auto-Rejoin] [{account}] Successfully tracked PID {new_pid}")
```

Replace with:

```python
            if available_pids:
                new_pid = max(available_pids)
                self.auto_rejoin_pids[account] = new_pid
                with self.pid_account_lock:
                    self.pid_account_map[new_pid] = account
                if self.settings.get("rename_roblox_windows", True):
                    threading.Thread(
                        target=self._rename_window_for_pid_when_ready,
                        args=(new_pid, account),
                        daemon=True
                    ).start()
                print(f"[Auto-Rejoin] [{account}] Successfully tracked PID {new_pid}")
```

- [ ] **Step 4: Verify parse + import**

Run: `py -c "import ast; ast.parse(open('utils/ui.py',encoding='utf-8').read()); print('parse OK')"`
Run: `py -c "import utils.ui; print('import OK')"`
Expected: `parse OK` then `import OK`.

- [ ] **Step 5: Commit**

```bash
git add utils/ui.py
git commit -m "feat: capture PID->account at launch in all launch paths"
```

---

### Task 4: Sound labels read the map (DRY)

**Files:**
- Modify: `utils/ui.py` — `_resolve_pid_label` (~9667), remove `_sound_pid_labels` (init ~127, two `.clear()` calls ~9642/9654, prune ~9706-9707)

**Interfaces:**
- Consumes: `pid_account_map`/`pid_account_lock`, `sound_tracker.format_pid_label`.
- Produces: `_resolve_pid_label(pid) -> str` now reads only the map — no HTTP, no log-parse, no `_sound_pid_labels` cache.

- [ ] **Step 1: Rewrite `_resolve_pid_label`**

In `utils/ui.py`, replace:

```python
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
```

with:

```python
    def _resolve_pid_label(self, pid):
        """PID -> account name from the authoritative launch map; 'PID <n>' on miss.
        No HTTP or log-parsing: labels come only from capture-at-launch."""
        with self.pid_account_lock:
            account = self.pid_account_map.get(pid)
        if account:
            return account
        return sound_tracker.format_pid_label(pid, None)
```

- [ ] **Step 2: Remove the `_sound_pid_labels` field**

In `utils/ui.py`, delete this line (in `__init__`, ~line 127):

```python
        self._sound_pid_labels = {}   # pid -> resolved username (successes only)
```

- [ ] **Step 3: Remove the two `_sound_pid_labels.clear()` calls**

In `start_sound_monitoring`, delete the line:

```python
        self._sound_pid_labels.clear()
```

In `stop_sound_monitoring`, delete the line:

```python
            self._sound_pid_labels.clear()
```

(Two separate lines, different indentation — remove both.)

- [ ] **Step 4: Remove the `_sound_pid_labels` prune in the worker**

In `_sound_monitoring_worker`, delete:

```python
                    self._sound_pid_labels = {
                        p: l for p, l in self._sound_pid_labels.items() if p in live}
```

- [ ] **Step 5: Verify parse, import, and no lingering references**

Run: `py -c "import ast; ast.parse(open('utils/ui.py',encoding='utf-8').read()); print('parse OK')"`
Run: `py -c "import utils.ui; print('import OK')"`
Run: `grep -n "_sound_pid_labels" utils/ui.py || echo "none left"`
Expected: `parse OK`, `import OK`, `none left`.

- [ ] **Step 6: Commit**

```bash
git add utils/ui.py
git commit -m "refactor: sound labels read authoritative pid_account_map"
```

---

### Task 5: Retire polling rename worker, default-on toggle, map maintenance, docs

**Files:**
- Modify: `utils/ui.py` — remove state fields (~119-121), boot (~6909-6910), close cleanup (~448-449), worker methods (~9558-9614); simplify + default-on toggle (~6719-6729); auto-rejoin map cleanup (~10533); `_match_pids_to_accounts` map write (~10805)
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: `pid_account_map`/`pid_account_lock`.
- Produces: capture-at-launch is the only rename mechanism; `rename_roblox_windows` defaults on.

- [ ] **Step 1: Remove the rename-worker state fields**

In `utils/ui.py` `__init__` (~lines 119-121), delete:

```python
        self.rename_thread = None
        self.rename_stop_event = threading.Event()
        self.renamed_pids = set()
```

- [ ] **Step 2: Remove boot wiring**

In `utils/ui.py` (~6909-6910), delete:

```python
        if self.settings.get("rename_roblox_windows", False):
            self.root.after(1000, self.start_rename_monitoring)
```

- [ ] **Step 3: Remove close cleanup**

In `utils/ui.py` (~448-449), delete:

```python
        if hasattr(self, 'rename_stop_event'):
            self.stop_rename_monitoring()
```

- [ ] **Step 4: Remove the polling worker methods**

In `utils/ui.py`, delete the three methods `start_rename_monitoring`, `stop_rename_monitoring`, and `_rename_monitoring_worker` — i.e. everything from:

```python
    def start_rename_monitoring(self):
        """Start monitoring and renaming Roblox windows"""
```

down to (and including) the end of `_rename_monitoring_worker`:

```python
            time.sleep(2)
```

that immediately precedes `def _rename_roblox_window(self, pid, username):`. **Keep `_rename_roblox_window` intact.**

- [ ] **Step 5: Simplify the toggle and default it on**

In `utils/ui.py` (~6719-6737), replace:

```python
        rename_var = tk.BooleanVar(value=self.settings.get("rename_roblox_windows", False))
        
        def on_rename_toggle():
            enabled = rename_var.get()
            self.settings["rename_roblox_windows"] = enabled
            self.save_settings()
            
            if enabled:
                self.start_rename_monitoring()
            else:
                self.stop_rename_monitoring()
        
        ttk.Checkbutton(
            roblox_frame,
            text="Rename Roblox Windows",
            variable=rename_var,
            style="Dark.TCheckbutton",
            command=on_rename_toggle
        ).pack(anchor="w", pady=(0, 10))
```

with:

```python
        rename_var = tk.BooleanVar(value=self.settings.get("rename_roblox_windows", True))

        def on_rename_toggle():
            # Rename now happens at launch; the toggle is just a stored preference
            # read by the launch paths. Takes effect on the next launch.
            self.settings["rename_roblox_windows"] = rename_var.get()
            self.save_settings()

        ttk.Checkbutton(
            roblox_frame,
            text="Rename Roblox Windows (on launch)",
            variable=rename_var,
            style="Dark.TCheckbutton",
            command=on_rename_toggle
        ).pack(anchor="w", pady=(0, 10))
```

- [ ] **Step 6: Drop dead PIDs from the map in auto-rejoin**

In `utils/ui.py`, find (in the auto-rejoin disconnect handler, ~10533):

```python
                        del self.auto_rejoin_pids[account]
```

Replace with:

```python
                        del self.auto_rejoin_pids[account]
                        with self.pid_account_lock:
                            self.pid_account_map.pop(old_pid, None)
```

- [ ] **Step 7: Have `_match_pids_to_accounts` populate the map**

In `utils/ui.py`, find (in `_match_pids_to_accounts`, ~10805):

```python
                    matches[account] = pid
                    self.auto_rejoin_pids[account] = pid
                    print(f"[Auto-Rejoin] MATCHED: {account} (user {account_user_id}) -> PID {pid}")
```

Replace with:

```python
                    matches[account] = pid
                    self.auto_rejoin_pids[account] = pid
                    with self.pid_account_lock:
                        self.pid_account_map[pid] = account
                    print(f"[Auto-Rejoin] MATCHED: {account} (user {account_user_id}) -> PID {pid}")
```

- [ ] **Step 8: Verify parse, import, no lingering references, tests green**

Run: `py -c "import ast; ast.parse(open('utils/ui.py',encoding='utf-8').read()); print('parse OK')"`
Run: `py -c "import utils.ui; print('import OK')"`
Run: `grep -nE "rename_monitoring|rename_stop_event|rename_thread|renamed_pids" utils/ui.py || echo "none left"`
Run: `py -m pytest tests/ -q`
Expected: `parse OK`, `import OK`, `none left`, and all tests pass.

- [ ] **Step 9: Update CLAUDE.md**

In `CLAUDE.md`, replace any description of window renaming as a polling/monitoring worker with the capture-at-launch model. Add or adjust a section to read:

```markdown
## Instance labeling (auto-rename + sound labels)

Roblox instances are labeled from an **authoritative `pid_account_map`
(PID → account username)** captured at launch — no HTTP, no log-parsing. Every
launch path (`launch_game`/`launch_home` workers and the auto-rejoin
`_launch_and_track_pid`) snapshots Roblox PIDs before launch, and
`_record_launched_account` uses `utils/pid_labels.pick_launched_pid` to identify
the one new PID and record it. If `rename_roblox_windows` (default **on**) is set,
`_rename_window_for_pid_when_ready` waits for that PID's window and sets its title
to the account name. The sound tracker's `_resolve_pid_label` reads the same map,
so sound events carry the correct account too. `_match_pids_to_accounts`
(auto-rejoin "Start All") also writes the map; dead PIDs are dropped on
disconnect. Only manager-launched instances are labeled. The old polling rename
worker was removed. Tests: `tests/test_pid_labels.py`.
```

- [ ] **Step 10: Commit**

```bash
git add utils/ui.py CLAUDE.md
git commit -m "refactor: retire polling rename worker; default-on capture-at-launch rename"
```

---

## Self-Review

**Spec coverage:**
- Authoritative `pid_account_map` + lock → Task 2. ✓
- Pure `pick_launched_pid` → Task 1 (+ tests). ✓
- Capture at launch, normal paths → Task 3 (Steps 1-2). ✓
- Capture at launch, auto-rejoin path → Task 3 (Step 3). ✓
- Renaming via wait-for-window helper, off-thread → Task 2 + used in Tasks 2/3. ✓
- Sound labels read the map, remove HTTP/log-parse → Task 4. ✓
- Default-on `rename_roblox_windows` → Task 3/2 reads use `True`; toggle default `True` in Task 5 Step 5. ✓
- Remove polling worker + boot/close/toggle-start wiring, remove state fields → Task 5 (Steps 1-5). ✓
- Keep `_get_user_id_from_pid`, `_match_pids_to_accounts`, `_rename_roblox_window` → not deleted; Task 5 Step 4 explicitly keeps `_rename_roblox_window`. ✓
- Pruning: overwrite-on-capture (Task 2/3), auto-rejoin dead-PID pop (Task 5 Step 6), sound reads only live PIDs (Task 4). ✓
- `_match_pids_to_accounts` writes map → Task 5 Step 7. ✓
- Manual verification (3+ alts, distinct names, sound labels correct) → below. ✓

**Placeholder scan:** No TBD/TODO; every code step shows full code. ✓

**Type consistency:** `pick_launched_pid(pids_before, pids_after, assigned) -> int|None`, `_record_launched_account(account, pids_before, timeout=12) -> int|None`, `_rename_window_for_pid_when_ready(pid, name, timeout=45)`, `_resolve_pid_label(pid) -> str`, `pid_account_map: dict[int,str]` — consistent across tasks. ✓

## Manual Verification (after Task 5)

1. Fresh settings (or `rename_roblox_windows` unset): toggle shows checked (default on).
2. Select 3+ accounts, launch to a game at once. Each Roblox window title becomes its **own distinct account name** — no duplicates, no wrong names.
3. Enable sound tracking; trigger audio in two different instances → `[Sound] <accountA>` and `[Sound] <accountB>` with correct names.
4. Auto-rejoin an account; on relaunch the new window is titled correctly and the old PID is gone from the map.
5. Untick the toggle, launch again → windows keep the default "Roblox" title.
