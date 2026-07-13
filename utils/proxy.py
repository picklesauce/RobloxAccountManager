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
