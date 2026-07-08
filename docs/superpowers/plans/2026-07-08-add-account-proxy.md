# Add Account Proxy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optionally route "Add Account" (and JavaScript Import) browser logins through a rotating list of user-authenticated proxies, to spread logins across IPs and reduce captcha escalation.

**Architecture:** A new pure module `utils/proxy.py` parses proxy strings and does round-robin selection (unit-tested). The UI (`ui.py`) owns the proxy list + rotation cursor in settings, exposes a "Proxy Settings" window from the Tool tab, and passes chosen proxies down into `RobloxAccountManager.add_account`, which threads them into `setup_chrome_driver`. No-auth proxies use `--proxy-server`; authenticated proxies use a throwaway generated Chrome extension that supplies credentials via `onAuthRequired`.

**Tech Stack:** Python 3.12, Tkinter, Selenium/Chrome, `requests` (already imported), pytest 9.1.1.

## Global Constraints

- **Windows-only**, Python 3.7+ compatible syntax.
- **No new pip dependencies.** Auth uses a generated Chrome extension, not selenium-wire.
- Settings loaded from `ui_settings.json` are **not** default-merged — always read new keys with `self.settings.get(key, default)`.
- Feature **off by default**; when off, behavior is byte-for-byte identical to today (no proxy args, `--disable-extensions` still added).
- Scope: proxy applies **only** to `setup_chrome_driver` (Add Account + JavaScript Import). Not game-launch paths, not `roblox_api.py`.
- New keys: `proxy_enabled` (bool, default False), `proxy_list` (list[str] raw lines, default []), `proxy_rotation_index` (int, default 0).
- Match existing UI idioms: `style="Dark.TFrame/TLabel/TButton/TCheckbutton"`, `tk.Label` for colored status text, `apply_window_icon`, centered Toplevel.

---

### Task 1: `utils/proxy.py` — parser + rotation (pure, unit-tested)

**Files:**
- Create: `utils/proxy.py`
- Test: `tests/test_proxy.py`

**Interfaces:**
- Produces:
  - `parse_proxy(raw: str) -> dict | None` → `{"scheme","host","port","username","password"}` (username/password `None` when absent).
  - `parse_proxy_list(lines: list[str] | str) -> list[dict]` (drops unusable lines).
  - `take_proxies(parsed_list: list[dict], start_index: int, n: int) -> (list[dict], int)` round-robin, returns `(chosen, new_index)`.
  - `to_requests_proxies(proxy: dict | None) -> dict | None` → `{"http": url, "https": url}` for connectivity tests.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_proxy.py`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.proxy import (
    parse_proxy,
    parse_proxy_list,
    take_proxies,
    to_requests_proxies,
)


def test_host_port():
    assert parse_proxy("1.2.3.4:8080") == {
        "scheme": "http", "host": "1.2.3.4", "port": "8080",
        "username": None, "password": None,
    }


def test_host_port_user_pass_positional():
    assert parse_proxy("1.2.3.4:8080:bob:secret") == {
        "scheme": "http", "host": "1.2.3.4", "port": "8080",
        "username": "bob", "password": "secret",
    }


def test_user_pass_at_host_port():
    assert parse_proxy("bob:secret@1.2.3.4:8080") == {
        "scheme": "http", "host": "1.2.3.4", "port": "8080",
        "username": "bob", "password": "secret",
    }


def test_scheme_prefix_with_auth():
    assert parse_proxy("socks5://bob:secret@1.2.3.4:1080") == {
        "scheme": "socks5", "host": "1.2.3.4", "port": "1080",
        "username": "bob", "password": "secret",
    }


def test_scheme_prefix_no_auth():
    assert parse_proxy("http://1.2.3.4:8080") == {
        "scheme": "http", "host": "1.2.3.4", "port": "8080",
        "username": None, "password": None,
    }


def test_blank_and_comment_and_garbage_return_none():
    assert parse_proxy("") is None
    assert parse_proxy("   ") is None
    assert parse_proxy("# a comment") is None
    assert parse_proxy("not-a-proxy") is None
    assert parse_proxy("host:notaport") is None
    assert parse_proxy("host:99999") is None  # port out of range
    assert parse_proxy("a:b:c") is None       # 3 fields, ambiguous


def test_parse_list_drops_bad_lines():
    raw = "1.2.3.4:8080\n\n# note\nbad\n5.6.7.8:9090:u:p"
    result = parse_proxy_list(raw)
    assert [p["host"] for p in result] == ["1.2.3.4", "5.6.7.8"]


def test_take_proxies_wraps_and_advances_index():
    lst = parse_proxy_list("a.com:1\nb.com:2\nc.com:3")
    chosen, idx = take_proxies(lst, 0, 2)
    assert [p["host"] for p in chosen] == ["a.com", "b.com"]
    assert idx == 2
    chosen2, idx2 = take_proxies(lst, idx, 2)
    assert [p["host"] for p in chosen2] == ["c.com", "a.com"]  # wraps
    assert idx2 == 1


def test_take_proxies_empty_list():
    assert take_proxies([], 0, 3) == ([], 0)


def test_take_proxies_n_zero():
    lst = parse_proxy_list("a.com:1")
    assert take_proxies(lst, 0, 0) == ([], 0)


def test_to_requests_proxies_with_auth():
    proxy = parse_proxy("bob:secret@1.2.3.4:8080")
    assert to_requests_proxies(proxy) == {
        "http": "http://bob:secret@1.2.3.4:8080",
        "https": "http://bob:secret@1.2.3.4:8080",
    }


def test_to_requests_proxies_no_auth():
    proxy = parse_proxy("1.2.3.4:8080")
    assert to_requests_proxies(proxy) == {
        "http": "http://1.2.3.4:8080",
        "https": "http://1.2.3.4:8080",
    }


def test_to_requests_proxies_none():
    assert to_requests_proxies(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -m pytest tests/test_proxy.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'utils.proxy'`

- [ ] **Step 3: Implement `utils/proxy.py`**

```python
"""Proxy-string parsing + round-robin rotation for the Add Account browser.

Pure functions only (no Tk/Selenium) so they are unit-testable in isolation.
Accepted proxy line formats (IPv4 hosts only in v1):
    host:port
    host:port:user:pass          (positional; common provider export)
    user:pass@host:port
    scheme://user:pass@host:port  (scheme optional; also scheme://host:port)
"""

import json

DEFAULT_SCHEME = "http"


def _is_valid_port(port):
    return port.isdigit() and 1 <= int(port) <= 65535


def parse_proxy(raw):
    """Normalize one proxy line into a dict, or None if unusable."""
    if not raw:
        return None
    line = raw.strip()
    if not line or line.startswith("#"):
        return None

    scheme = DEFAULT_SCHEME
    if "://" in line:
        scheme_part, _, rest = line.partition("://")
        scheme_part = scheme_part.strip().lower()
        if scheme_part:
            scheme = scheme_part
        line = rest

    username = None
    password = None

    if "@" in line:
        cred, _, hostport = line.rpartition("@")
        if ":" in cred:
            username, _, password = cred.partition(":")
        else:
            username = cred
        host, sep, port = hostport.strip().rpartition(":")
        if not sep:
            return None
    else:
        parts = line.split(":")
        if len(parts) == 2:
            host, port = parts[0], parts[1]
        elif len(parts) == 4:
            host, port, username, password = parts[0], parts[1], parts[2], parts[3]
        else:
            return None

    host = (host or "").strip()
    port = (port or "").strip()
    if not host or not _is_valid_port(port):
        return None

    return {
        "scheme": scheme,
        "host": host,
        "port": port,
        "username": username if username else None,
        "password": password if password else None,
    }


def parse_proxy_list(lines):
    """Parse a multiline string or iterable of lines; drop unusable entries."""
    if isinstance(lines, str):
        lines = lines.splitlines()
    result = []
    for line in lines:
        parsed = parse_proxy(line)
        if parsed is not None:
            result.append(parsed)
    return result


def take_proxies(parsed_list, start_index, n):
    """Return (list_of_n_proxies, new_index) via round-robin. Wraps with modulo."""
    if not parsed_list or n <= 0:
        return [], start_index
    size = len(parsed_list)
    start = start_index % size
    chosen = [parsed_list[(start + i) % size] for i in range(n)]
    return chosen, (start + n) % size


def to_requests_proxies(proxy):
    """Build a `requests`-style proxies dict from a parsed proxy (connectivity test)."""
    if not proxy:
        return None
    scheme = proxy.get("scheme") or DEFAULT_SCHEME
    user = proxy.get("username")
    if user:
        auth = "{}:{}@".format(user, proxy.get("password") or "")
    else:
        auth = ""
    url = "{}://{}{}:{}".format(scheme, auth, proxy["host"], proxy["port"])
    return {"http": url, "https": url}


def build_auth_extension_files(scheme, host, port, username, password):
    """Return (manifest_json_str, background_js_str) for a proxy-auth MV2 extension.

    Credentials are JSON-encoded into JS string literals so quotes/backslashes
    in a password can't break the script.
    """
    manifest = json.dumps({
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "RAM Proxy Auth",
        "permissions": [
            "proxy", "tabs", "unlimitedStorage", "storage",
            "<all_urls>", "webRequest", "webRequestBlocking",
        ],
        "background": {"scripts": ["background.js"]},
        "minimum_chrome_version": "22.0.0",
    }, indent=2)

    background = """
var config = {
  mode: "fixed_servers",
  rules: {
    singleProxy: { scheme: %s, host: %s, port: %s },
    bypassList: ["localhost", "127.0.0.1"]
  }
};
chrome.proxy.settings.set({ value: config, scope: "regular" }, function () {});
chrome.webRequest.onAuthRequired.addListener(
  function (details) {
    return { authCredentials: { username: %s, password: %s } };
  },
  { urls: ["<all_urls>"] },
  ["blocking"]
);
""" % (
        json.dumps(scheme),
        json.dumps(host),
        int(port),
        json.dumps(username),
        json.dumps(password),
    )
    return manifest, background
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -m pytest tests/test_proxy.py -v`
Expected: PASS (all 13 tests)

- [ ] **Step 5: Commit**

```bash
git add utils/proxy.py tests/test_proxy.py
git commit -m "feat(proxy): proxy-string parser + round-robin rotation (utils/proxy.py)"
```

---

### Task 2: Manager — thread proxy into `setup_chrome_driver` + auth extension

**Files:**
- Modify: `classes/account_manager.py` — `__init__` (add `self.temp_extension_dirs = []`), `setup_chrome_driver`, `cleanup_temp_profile`, `add_account`; add `_build_proxy_auth_extension`.

**Interfaces:**
- Consumes: `utils.proxy.build_auth_extension_files`.
- Produces:
  - `setup_chrome_driver(self, browser_path=None, proxy=None)` — `proxy` is a parsed-proxy dict or `None`.
  - `add_account(self, amount=1, website=..., javascript="", browser_path=None, proxies=None)` — `proxies` is `None`, a single dict, or a `list[dict]`.

- [ ] **Step 1: Add extension-dir tracking in `__init__`**

In `classes/account_manager.py`, after `self.temp_profile_dir = None` (line ~61):

```python
        self.temp_profile_dir = None
        self.temp_extension_dirs = []
```

- [ ] **Step 2: Add the extension generator + import**

At the top of `account_manager.py`, ensure the proxy helper is importable. Add near the other `from .` / stdlib imports:

```python
from utils.proxy import build_auth_extension_files
```

Add this method to the class (place it right after `cleanup_temp_profile`, ~line 159):

```python
    def _build_proxy_auth_extension(self, scheme, host, port, username, password):
        """Write a throwaway MV2 extension that supplies proxy credentials.

        Returns the extension directory path, or None on failure. The dir is
        tracked in self.temp_extension_dirs and removed by cleanup_temp_profile.
        NOTE: relies on MV2 blocking webRequest auth; verify against the bundled
        Chromium version before shipping (see plan Task 4 live check).
        """
        try:
            manifest, background = build_auth_extension_files(
                scheme, host, port, username, password
            )
            ext_dir = tempfile.mkdtemp(prefix="ram_proxy_ext_")
            with open(os.path.join(ext_dir, "manifest.json"), "w", encoding="utf-8") as f:
                f.write(manifest)
            with open(os.path.join(ext_dir, "background.js"), "w", encoding="utf-8") as f:
                f.write(background)
            return ext_dir
        except Exception as e:
            print(f"[ERROR] Failed to build proxy auth extension: {e}")
            return None
```

- [ ] **Step 3: Wire proxy into `setup_chrome_driver`**

Change the signature (line 161):

```python
    def setup_chrome_driver(self, browser_path=None, proxy=None):
```

Immediately after `if browser_path: chrome_options.binary_location = browser_path` (line ~169), insert:

```python
        # --- Proxy support (Add Account only) -------------------------------
        proxy_ext_dir = None
        if proxy:
            scheme = proxy.get("scheme") or "http"
            host = proxy.get("host")
            port = proxy.get("port")
            username = proxy.get("username")
            password = proxy.get("password")
            if username:
                proxy_ext_dir = self._build_proxy_auth_extension(
                    scheme, host, port, username, password or ""
                )
                if proxy_ext_dir:
                    self.temp_extension_dirs.append(proxy_ext_dir)
            else:
                chrome_options.add_argument(f"--proxy-server={scheme}://{host}:{port}")
            print(f"[INFO] Add Account routing through proxy {host}:{port}")
```

Then replace the single line 189 `chrome_options.add_argument("--disable-extensions")` with:

```python
        if proxy_ext_dir:
            chrome_options.add_argument(f"--load-extension={proxy_ext_dir}")
            chrome_options.add_argument(f"--disable-extensions-except={proxy_ext_dir}")
        else:
            chrome_options.add_argument("--disable-extensions")
```

(Leave `--disable-plugins` and every other flag unchanged.)

- [ ] **Step 4: Clean up extension dirs in `cleanup_temp_profile`**

Replace the body of `cleanup_temp_profile` (lines ~153-159) with:

```python
    def cleanup_temp_profile(self):
        """Clean up temporary profile + proxy-extension directories"""
        if self.temp_profile_dir and os.path.exists(self.temp_profile_dir):
            try:
                shutil.rmtree(self.temp_profile_dir)
            except:
                pass
        for ext_dir in self.temp_extension_dirs:
            if ext_dir and os.path.exists(ext_dir):
                try:
                    shutil.rmtree(ext_dir)
                except:
                    pass
        self.temp_extension_dirs = []
```

- [ ] **Step 5: Thread `proxies` through `add_account`**

Change the signature (line 464):

```python
    def add_account(self, amount=1, website="https://www.roblox.com/login", javascript="", browser_path=None, proxies=None):
```

In the instance loop, replace `driver = self.setup_chrome_driver(browser_path)` (line ~483) with:

```python
                instance_proxy = None
                if isinstance(proxies, list):
                    if i < len(proxies):
                        instance_proxy = proxies[i]
                elif isinstance(proxies, dict):
                    instance_proxy = proxies
                driver = self.setup_chrome_driver(browser_path, proxy=instance_proxy)
```

- [ ] **Step 6: Smoke-test import + no-proxy behavior unchanged**

Run:
```bash
py -c "from classes.account_manager import RobloxAccountManager; from utils.proxy import build_auth_extension_files; m,b=build_auth_extension_files('http','1.2.3.4','8080','u','p\"x'); print('manifest ok' if 'RAM Proxy Auth' in m else 'BAD'); print('bg ok' if '1.2.3.4' in b and 'onAuthRequired' in b else 'BAD')"
```
Expected: prints `manifest ok` then `bg ok` (and no import error). Confirms the extension builder escapes a quote in the password and the module imports cleanly.

- [ ] **Step 7: Commit**

```bash
git add classes/account_manager.py
git commit -m "feat(proxy): route setup_chrome_driver through optional proxy + auth extension"
```

---

### Task 3: UI — rotation helper, Proxy Settings window, wire launch call sites

**Files:**
- Modify: `utils/ui.py` — add `from utils.proxy import ...`; add 3 keys to both default dicts; add `_take_proxies`; add `open_proxy_settings_window`; add Tool-tab button; update the two `manager.add_account(...)` call sites.

**Interfaces:**
- Consumes: `self.manager.add_account(..., proxies=...)`; `parse_proxy_list`, `take_proxies`, `to_requests_proxies`.
- Produces: `_take_proxies(self, n) -> list[dict] | None` (None = direct connection; advances + persists `proxy_rotation_index`).

- [ ] **Step 1: Import the proxy helpers**

Near the other `from utils.` imports (line ~48):

```python
from utils.proxy import parse_proxy_list, take_proxies, to_requests_proxies
```

- [ ] **Step 2: Add default keys to both settings dicts**

In `load_settings`, add these three keys to **both** default dicts (after `"developer_mode": False,` at lines ~915 and ~947):

```python
                    "proxy_enabled": False,
                    "proxy_list": [],
                    "proxy_rotation_index": 0,
```

- [ ] **Step 3: Add `_take_proxies` helper**

Add this method near the other launch helpers (e.g. right before `def add_account(self):` at line ~3260):

```python
    def _take_proxies(self, n):
        """Return n parsed proxies for a launch batch, or None if proxying is off.

        Advances and persists the round-robin cursor. None => direct connection.
        """
        if not self.settings.get("proxy_enabled", False):
            return None
        parsed = parse_proxy_list(self.settings.get("proxy_list", []))
        if not parsed:
            return None
        start = int(self.settings.get("proxy_rotation_index", 0) or 0)
        chosen, new_index = take_proxies(parsed, start, n)
        self.settings["proxy_rotation_index"] = new_index
        self.save_settings()
        return chosen
```

- [ ] **Step 4: Wire the Add Account call site**

Replace line ~3288 `success = self.manager.add_account(1, "https://www.roblox.com/login", "", browser_path)` with:

```python
                proxies = self._take_proxies(1)
                proxy = proxies[0] if proxies else None
                success = self.manager.add_account(1, "https://www.roblox.com/login", "", browser_path, proxies=proxy)
```

- [ ] **Step 5: Wire the JavaScript Import call site**

Replace line ~3672 `success = self.manager.add_account(amount, website, javascript, browser_path)` with:

```python
                proxies = self._take_proxies(amount)
                success = self.manager.add_account(amount, website, javascript, browser_path, proxies=proxies)
```

- [ ] **Step 6: Add the "Proxy Settings" button to the Tool tab**

After the "Browser Engine" button block (line ~7809, the `.pack(fill="x", pady=(0, 5))` for Browser Engine), insert:

```python
        ttk.Button(
            tool_frame,
            text="Proxy Settings",
            style="Dark.TButton",
            command=self.open_proxy_settings_window
        ).pack(fill="x", pady=(0, 5))
```

- [ ] **Step 7: Add `open_proxy_settings_window`**

Add this method right after `open_browser_engine_window` (i.e. before its `def` at line ~8305, or immediately after that method ends — place it before `def open_browser_engine_window`):

```python
    def open_proxy_settings_window(self):
        """Configure a rotating proxy list for Add Account logins."""
        win = tk.Toplevel(self.root)
        self.apply_window_icon(win)
        win.title("Proxy Settings")
        win.geometry("500x470")
        win.configure(bg=self.BG_DARK)
        win.resizable(False, False)
        win.transient(self.root)
        if self.settings.get("enable_topmost", False):
            win.attributes("-topmost", True)
        win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (win.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (win.winfo_height() // 2)
        win.geometry(f"+{x}+{y}")

        container = ttk.Frame(win, style="Dark.TFrame")
        container.pack(fill="both", expand=True, padx=20, pady=20)

        ttk.Label(
            container, text="Add Account Proxy",
            style="Dark.TLabel", font=(self.FONT_FAMILY, 11, "bold")
        ).pack(anchor="w")
        ttk.Label(
            container,
            text=("Route Add Account logins through a rotating proxy list to spread\n"
                  "logins across IPs. This changes the IP, not the browser fingerprint\n"
                  "— it helps captchas but is not a guaranteed fix."),
            style="Dark.TLabel", font=(self.FONT_FAMILY, 8)
        ).pack(anchor="w", pady=(2, 10))

        sep = ttk.Frame(container, style="Dark.TFrame", height=1)
        sep.pack(fill="x", pady=(0, 12))
        sep.configure(relief="solid", borderwidth=1)

        enabled_var = tk.BooleanVar(value=self.settings.get("proxy_enabled", False))
        ttk.Checkbutton(
            container, text="Route Add Account logins through a proxy",
            style="Dark.TCheckbutton", variable=enabled_var
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            container, text="Proxies (one per line):",
            style="Dark.TLabel", font=(self.FONT_FAMILY, 9)
        ).pack(anchor="w")
        ttk.Label(
            container,
            text="host:port   host:port:user:pass   user:pass@host:port   scheme://user:pass@host:port",
            style="Dark.TLabel", font=(self.FONT_FAMILY, 7)
        ).pack(anchor="w", pady=(0, 4))

        text_frame = tk.Frame(container, bg=self.BG_MID, highlightthickness=1, highlightbackground="#555555")
        text_frame.pack(fill="both", expand=True)
        proxy_text = tk.Text(
            text_frame, height=8, bg=self.BG_MID, fg=self.FG_TEXT,
            insertbackground=self.FG_TEXT, relief="flat", font=("Consolas", 9), wrap="none"
        )
        proxy_text.pack(fill="both", expand=True, padx=4, pady=4)
        existing = self.settings.get("proxy_list", [])
        if isinstance(existing, list):
            proxy_text.insert("1.0", "\n".join(existing))

        status_label = tk.Label(
            container, text="", bg=self.BG_DARK, fg=self.FG_TEXT,
            font=(self.FONT_FAMILY, 8), anchor="w", justify="left"
        )
        status_label.pack(anchor="w", fill="x", pady=(8, 4))

        def _current_list():
            raw = proxy_text.get("1.0", "end-1c")
            return [ln.strip() for ln in raw.splitlines() if ln.strip()]

        def _save():
            self.settings["proxy_enabled"] = enabled_var.get()
            self.settings["proxy_list"] = _current_list()
            self.save_settings()
            status_label.config(text="Saved.", fg="#00CC66")

        def _test():
            parsed = parse_proxy_list(_current_list())
            if not parsed:
                status_label.config(text="No valid proxy to test.", fg="#FF6666")
                return
            proxy = parsed[0]
            status_label.config(text="Testing first proxy…", fg=self.FG_TEXT)

            def _run():
                try:
                    resp = requests.get(
                        "https://api.ipify.org?format=json",
                        proxies=to_requests_proxies(proxy), timeout=12
                    )
                    ip = resp.json().get("ip", "?")
                    self.root.after(0, lambda: status_label.config(
                        text=f"OK — exit IP {ip}  (via {proxy['host']}:{proxy['port']})",
                        fg="#00CC66"))
                except Exception as exc:
                    msg = str(exc)
                    self.root.after(0, lambda: status_label.config(
                        text=f"Failed: {msg[:70]}", fg="#FF6666"))

            threading.Thread(target=_run, daemon=True).start()

        btn_frame = ttk.Frame(container, style="Dark.TFrame")
        btn_frame.pack(fill="x", pady=(4, 0))
        ttk.Button(
            btn_frame, text="Test First Proxy", style="Dark.TButton", command=_test
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        ttk.Button(
            btn_frame, text="Save", style="Dark.TButton", command=_save
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))
```

- [ ] **Step 8: Byte-compile check + rerun unit tests**

Run:
```bash
py -m py_compile utils/ui.py classes/account_manager.py utils/proxy.py
py -m pytest tests/test_proxy.py -v
```
Expected: no compile output (success), pytest all PASS.

- [ ] **Step 9: Commit**

```bash
git add utils/ui.py
git commit -m "feat(proxy): Proxy Settings window, rotation helper, wire Add Account launches"
```

---

### Task 4: Live verification (needs the user's machine + a real proxy)

**Not automatable here** — no proxy credentials and no GUI session. When the user has a proxy:

- [ ] Settings → Tool → **Proxy Settings**: paste a proxy, **Test First Proxy** shows an exit IP different from the home IP.
- [ ] Enable the toggle, **Save**, then **Add Account**: the login Chrome window's traffic exits the proxy IP, the auth dialog is satisfied silently (auth proxies), and the `.ROBLOSECURITY` cookie is still captured.
- [ ] **MV2 check:** if the login page fails to load through an *authenticated* proxy (blank page / `ERR_...`), the bundled Chromium has disabled MV2 blocking `webRequest`. Fix: convert `build_auth_extension_files` to an MV3 service-worker manifest using `webRequestAuthProvider`. (Flagged in spec §7.)
- [ ] Toggle **off**, Add Account once → confirms unchanged direct-connection behavior.

---

## Self-Review

**Spec coverage:**
- Storage keys (§1) → Task 3 Step 2 + `_take_proxies`. ✓
- Parser 4 formats (§2) → Task 1 tests + impl. ✓
- Rotation persisted cursor (§3) → `take_proxies` + `_take_proxies`. ✓
- UI in Tool tab + Test button + caveat note (§4) → Task 3 Steps 6-7. ✓
- Manager plumbing + conditional `--disable-extensions` + auth extension (§5-7) → Task 2. ✓
- Cleanup (§8) → Task 2 Step 4. ✓
- Scope limit (§Non-goals) → only `setup_chrome_driver` touched; game-launch/API paths untouched. ✓
- Testing (§Testing) → Task 1 unit tests + Task 4 live checks. ✓

**Placeholder scan:** No TBD/TODO; every code step is complete. The MV2→MV3 fallback is a real conditional verification step, not a placeholder.

**Type consistency:** `proxy` dict keys `scheme/host/port/username/password` are identical across `parse_proxy`, `to_requests_proxies`, `build_auth_extension_files`, `setup_chrome_driver`, `_build_proxy_auth_extension`. `_take_proxies` returns `list|None`; Add Account passes `proxies[0]|None` (dict|None), JS import passes the list — both handled by `add_account`'s `isinstance` checks. ✓
