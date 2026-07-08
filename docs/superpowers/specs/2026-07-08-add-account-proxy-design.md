# Rotating Proxy Support for Add Account — Design

**Date:** 2026-07-08
**Status:** Approved (brainstorm), pending implementation plan
**Scope:** Route the "Add Account" cookie-scraper browser through a rotating list of user-authenticated proxies.

## Problem

"Add Account" is a manual-login cookie scraper. The UI (`ui.py::add_account`)
resolves a browser via `get_browser_path()` and calls
`manager.add_account(...)`, which spins up real Chrome/Chromium windows through
`setup_chrome_driver()` (`account_manager.py:161`), navigates each to
`roblox.com/login`, waits for the user to finish logging in
(`wait_for_login`), and reads back the `.ROBLOSECURITY` cookie
(`extract_user_info`).

All of that login traffic — including Roblox's Arkose/FunCaptcha challenge,
which is solved *inside* that Chrome window — exits the user's home IP. Adding
many accounts from one IP escalates captcha difficulty; the user reports
"impossible" captchas as account count grows.

**No proxy is configured anywhere in `setup_chrome_driver` today.**

### Honest limitation (carried into the design as a UI note)

A proxy changes the **IP** the login originates from — a major captcha input —
but Arkose *also* fingerprints the **browser/device** (canvas, fonts, timing).
A proxy does not change that. So a proxy will likely help but is not a
guaranteed captcha-killer, and a *single* proxy merely relocates the
"too many from one IP" signal. Rotating IPs is what actually spreads the load,
which is why this design rotates a list.

## Goals

- Optionally route each Add Account login through a proxy from a user-supplied
  list, **rotating** so consecutive logins use different IPs.
- Support **user:pass authenticated** HTTP proxies (the common cheap
  static-proxy plan), plus no-auth / IP-whitelisted proxies.
- Rotation cursor persists across app restarts (no reset to proxy #1 each
  launch).
- A "Test Proxy" affordance so the user can confirm a proxy is live before
  burning a login.
- Leave today's behavior completely unchanged when the feature is off.

## Non-goals (explicit scope limits)

- **Not** applied to game-launch browser paths (`launch_roblox_profile_join`,
  `launch_roblox_follow_user`, `open_authenticated_browser`) or the
  `roblox_api.py` HTTP calls. Routing gameplay / auth-ticket traffic through a
  proxy risks latency and login/play IP-mismatch flags, and is not the source
  of the Add Account captchas. Easy to extend later.
- No proxy *health-checking / auto-removal* of dead proxies beyond the manual
  Test button. (YAGNI for v1.)
- No SOCKS-specific handling beyond passing a `socks5://` scheme through to
  `--proxy-server` for no-auth SOCKS; authenticated SOCKS is out of scope for
  v1 (the auth-extension path targets HTTP/HTTPS).

## Design

### 1. Settings (`ui_settings.json`)

| Key | Type | Default | Meaning |
|---|---|---|---|
| `proxy_enabled` | bool | `False` | Master toggle for the Add Account proxy path. |
| `proxy_list` | list[str] | `[]` | One proxy per pasted line (raw strings, stored verbatim). |
| `proxy_rotation_index` | int | `0` | Persisted round-robin cursor into the *parsed* proxy list. |

### 2. Proxy-string parser

A pure function `parse_proxy(raw: str) -> dict | None` normalizes the four
accepted formats. Returns `None` for blank/garbage lines (which callers skip).

Accepted input forms:
- `host:port`
- `host:port:user:pass`  (common provider export; **positional**, so parsed
  before the `@` forms)
- `user:pass@host:port`
- `scheme://user:pass@host:port` (scheme optional; defaults to `http`)

Normalized output:
```python
{"scheme": "http", "host": "1.2.3.4", "port": "8080",
 "username": "u" or None, "password": "p" or None}
```

Parsing rules / edge cases to cover in tests:
- Explicit `scheme://` prefix wins; otherwise default `http`.
- Distinguish `host:port:user:pass` (4 colon-separated fields, no `@`) from
  `host:port` (2 fields). >4 fields or non-numeric port → `None`.
- IPv6 hosts are **not** supported in v1 (documented; providers hand out IPv4).
- Whitespace trimmed; empty lines and lines starting with `#` ignored.

This function lives in a new small module `utils/proxy.py` so it is unit-
testable without Tk/Selenium.

### 3. Rotation helper (in `utils/proxy.py`, state owned by `ui.py`)

`utils/proxy.py` exposes a pure helper:

```python
def take_proxies(parsed_list, start_index, n) -> (list_of_n, new_index)
```

- Returns `n` parsed proxies starting at `start_index`, wrapping with modulo.
- Returns the advanced index (`(start_index + n) % len`) for persistence.
- `parsed_list` empty → returns `([], start_index)`.

`ui.py` owns the stateful wrapper `_take_proxies(n)`:
1. Parse `self.settings['proxy_list']` → drop `None`s.
2. If `not proxy_enabled` or parsed list empty → return `None` (signals "direct
   connection", preserving current behavior).
3. Else call `take_proxies(...)`, write the new index back into
   `self.settings['proxy_rotation_index']`, `save_settings()`, and return the
   list.

### 4. UI — new "Proxy" section, Settings → **Tool** tab

Placed near the Browser Engine controls (both are browser concerns). Contents:

- Checkbox **"Route Add Account logins through a proxy"** → `proxy_enabled`.
- Multiline `Text` widget for the proxy list, one per line; seeded from and
  saved to `proxy_list`. A hint label shows the accepted formats.
- **Test Proxy** button → takes the *next* proxy via `_take_proxies(1)` (or the
  first parsed proxy if the toggle is off) and, on a daemon thread, issues a
  `requests.get("https://api.ipify.org?format=json", proxies=..., timeout=10)`
  through it. Reports the returned exit IP, or the error, in an adjacent status
  label. (Uses `requests`' own proxy support — no Chrome needed for the test,
  so it validates connectivity + credentials directly.)
- A muted one-line note restating the IP-vs-fingerprint caveat.

Saving the settings window persists `proxy_enabled` + `proxy_list` like the
other Tool-tab fields.

### 5. Plumbing into the manager

- `RobloxAccountManager.add_account(self, amount=1, website=..., javascript="",
  browser_path=None, proxies=None)`:
  - `proxies` is `None` (direct), a single normalized-proxy `dict`, or a
    `list[dict]` of length `amount`.
  - Inside the existing per-instance loop, select `proxies[i]`
    (list) / `proxies` (single) / `None`, and pass it to
    `setup_chrome_driver(browser_path, proxy=selected)`.
- Callers in `ui.py`:
  - Add Account button (`amount=1`) → `proxies = self._take_proxies(1)` then
    pass `proxies[0] if proxies else None`.
  - JavaScript Import path (`amount=N`, `ui.py:~4077`) → `proxies =
    self._take_proxies(N)`; pass the list (or `None`).

### 6. `setup_chrome_driver(self, browser_path=None, proxy=None)`

`proxy` is a normalized dict or `None`.

- `proxy is None` → unchanged from today.
- **No-auth** (`username`/`password` both falsy):
  `chrome_options.add_argument(f"--proxy-server={scheme}://{host}:{port}")`.
- **Authenticated** (username present):
  1. Generate a throwaway unpacked Chrome extension into a temp dir
     (see §7).
  2. `chrome_options.add_argument(f"--load-extension={ext_dir}")`.
  3. **Remove the existing `--disable-extensions` argument** for this driver
     and instead add `--disable-extensions-except={ext_dir}` so only our proxy
     extension loads (nothing else). `--disable-extensions` currently lives at
     `account_manager.py:189` and would otherwise block the extension —
     refactor so it is conditional.
  4. Track `ext_dir` for cleanup alongside the temp profile (deleted in the
     same teardown that removes the temp profile).

The proxy host:port for the auth case is still supplied to Chrome by the
extension's `chrome.proxy` config (not `--proxy-server`), so credentials never
touch the command line.

### 7. The runtime auth extension

Generated fresh per authenticated driver, deleted on teardown. Two files:

- `manifest.json` declaring `proxy`, `webRequest`, `webRequestAuthProvider` (or
  `<all_urls>` host permission) and a background script.
- Background script that (a) sets a fixed proxy via `chrome.proxy.settings.set`
  for `{host, port, scheme}`, and (b) registers a **blocking**
  `chrome.webRequest.onAuthRequired` listener returning
  `{authCredentials: {username, password}}`.

**Version risk (the one empirical unknown):** MV2's blocking `webRequest`
auth handling is being deprecated in favor of MV3. The exact manifest
(MV2 vs MV3 + `webRequestAuthProvider`) depends on the bundled Chromium's
version. The implementation plan MUST include a live verification step against
the user's bundled Chromium before this is considered done — pick the manifest
form that actually authenticates against a real proxy on that build. This is
the item flagged for empirical check rather than assumption.

### 8. Cleanup

The temp extension dir(s) are tracked on the manager (mirroring
`temp_profile_dir` handling) and removed in `cleanup_temp_profile` /
per-instance teardown so no extension dirs leak in `%TEMP%`.

## Files touched

| File | Change |
|---|---|
| `utils/proxy.py` (new) | `parse_proxy`, `take_proxies` — pure, unit-tested. |
| `utils/ui.py` | Proxy section in Tool tab; `_take_proxies`; Test-Proxy handler; pass `proxies` into both `add_account` calls; settings load/save + defaults for the 3 keys. |
| `classes/account_manager.py` | `add_account(..., proxies=None)`; `setup_chrome_driver(..., proxy=None)`; conditional `--disable-extensions`; auth-extension generator + cleanup. |
| `tests/test_proxy.py` (new) | Parser (4 formats + garbage + edge cases) and `take_proxies` (wrap-around, empty list, index advance). |

## Testing

- **Unit:** `tests/test_proxy.py` — `parse_proxy` across all four formats,
  scheme defaulting, `host:port:user:pass` vs `host:port` disambiguation,
  garbage → `None`; `take_proxies` wrap-around + returned index.
- **Live (in the plan):**
  1. Test-Proxy button returns a proxy IP different from the home IP.
  2. One real Add Account through an authenticated proxy still captures the
     cookie (extension auth works on the bundled Chromium — the §7 check).
  3. Feature off → behavior byte-for-byte identical to today (no proxy args,
     `--disable-extensions` still present).

## Open questions

None blocking. The only empirical unknown is the exact auth-extension manifest
form for the bundled Chromium version (§7), resolved during implementation.
