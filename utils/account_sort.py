"""Account-name sorting.

The account list sorts alphabetically, with one refinement: names shaped as an
all-letters part *followed by* an all-digits part (e.g. ``CoolGuy123``, the
pure-letters ``abc``, or the pure-digits ``001``) compare by their letters
alphabetically first and then by their trailing digits **numerically** — so
``001`` sorts before ``0010`` (1 < 10) and ``user2`` before ``user10``.

Names that don't fit that shape (interleaved letters/digits like ``a1b``, or
anything with other characters like ``ab-cd``) fall back to plain
case-insensitive alphabetical ordering.

Both behaviours are folded into a single ``account_sort_key`` so the whole list
is one consistent total order (see the module tests for the guarantees).
"""

import re

# Whole string = optional letters, then optional digits. ``a1b`` / ``ab-cd`` do
# not match, so they take the plain-alphabetical branch below.
_LETTERS_THEN_DIGITS = re.compile(r"^([A-Za-z]*)([0-9]*)$")


def account_sort_key(name):
    """Sort key implementing the letters-then-digits natural ordering.

    Returns ``(primary, original)`` where ``primary`` is a list compared
    element-wise:

    - Qualifying names → ``[letters_lowercased]`` plus ``[int(digits)]`` when a
      digit part is present. Equal letters therefore compare digits as numbers.
    - Other names → ``[full_name_lowercased]`` (plain alphabetical).

    The primary never mixes ``str`` and ``int`` at the same position across two
    keys (a numeric position only exists when both names qualify with digits and
    share the same letters), so comparisons never raise. ``original`` is the
    final, case-sensitive tie-break for determinism.
    """
    text = name if isinstance(name, str) else str(name)
    m = _LETTERS_THEN_DIGITS.match(text)
    if m is not None:
        letters, digits = m.group(1), m.group(2)
        primary = [letters.lower()]
        if digits != "":
            primary.append(int(digits))
        return (primary, text)
    return ([text.lower()], text)


def sort_account_names(names):
    """Return ``names`` sorted by :func:`account_sort_key`."""
    return sorted(names, key=account_sort_key)
