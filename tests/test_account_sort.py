"""Tests for utils.account_sort — the account-list ordering."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.account_sort import account_sort_key, sort_account_names


def _sorted(names):
    return sort_account_names(names)


def test_digits_compared_numerically_not_lexically():
    # The headline example from the spec: 001 < 0010 because 1 < 10.
    assert _sorted(["0010", "001"]) == ["001", "0010"]
    assert _sorted(["user10", "user2", "user100", "user1"]) == [
        "user1", "user2", "user10", "user100",
    ]


def test_letters_compared_before_digits():
    assert _sorted(["b1", "a2", "a10"]) == ["a2", "a10", "b1"]


def test_pure_letters_alphabetical():
    assert _sorted(["cherry", "apple", "banana"]) == ["apple", "banana", "cherry"]


def test_case_insensitive_alphabetical():
    # zebra before Zed (case-insensitive), regardless of input order.
    assert _sorted(["Zed", "zebra"]) == ["zebra", "Zed"]
    assert _sorted(["zebra", "Zed"]) == ["zebra", "Zed"]


def test_pure_letters_sort_before_same_prefix_with_digits():
    assert _sorted(["abc5", "abc", "abc0"]) == ["abc", "abc0", "abc5"]


def test_non_qualifying_names_use_plain_alphabetical():
    # Interleaved digits (a1b2) and names with other characters (ab-cd) do NOT
    # get numeric treatment — they sort lexically by their lowercased form.
    assert account_sort_key("a1b2")[0] == ["a1b2"]
    assert account_sort_key("ab-cd")[0] == ["ab-cd"]
    # "a10b" (interleaved) must NOT sort after "a9b" numerically.
    assert _sorted(["a9b", "a10b"]) == ["a10b", "a9b"]


def test_qualifying_shapes_detected():
    # Qualifying: letters-then-digits, pure letters, pure digits.
    assert len(account_sort_key("CoolGuy123")[0]) == 2
    assert account_sort_key("CoolGuy123")[0] == ["coolguy", 123]
    assert account_sort_key("abc")[0] == ["abc"]
    assert account_sort_key("001")[0] == ["", 1]
    # Non-qualifying: digits-then-letters, interleaved.
    assert account_sort_key("123abc")[0] == ["123abc"]


def test_digits_sort_before_letters():
    # A leading-digit name sorts before a letters name (matches plain ASCII too).
    assert _sorted(["abc", "5"]) == ["5", "abc"]


def test_stable_deterministic_tiebreak_for_case_variants():
    # Same lowercased key -> deterministic order by original (uppercase first).
    result = _sorted(["abc", "ABC", "Abc"])
    assert result == sorted(result, key=account_sort_key)  # idempotent
    assert set(result) == {"abc", "ABC", "Abc"}


def test_mixed_realistic_list():
    names = ["Zeta", "alpha10", "alpha2", "alpha1", "beta", "007", "42"]
    assert _sorted(names) == [
        "007", "42", "alpha1", "alpha2", "alpha10", "beta", "Zeta",
    ]
