import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.proxy import (
    parse_proxy,
    parse_proxy_list,
    take_proxies,
    to_requests_proxies,
    build_auth_extension_files,
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


def test_build_auth_extension_escapes_credentials():
    manifest, background = build_auth_extension_files(
        "http", "1.2.3.4", "8080", "bob", 'pa"ss\\word'
    )
    assert "RAM Proxy Auth" in manifest
    assert '"manifest_version": 2' in manifest
    assert "1.2.3.4" in background
    assert "onAuthRequired" in background
    # password with a quote+backslash must be JSON-escaped, not raw
    assert 'pa\\"ss\\\\word' in background
