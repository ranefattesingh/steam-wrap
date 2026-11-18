"""Text normalisation helpers for genre matching and series detection."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_TRADEMARKS = re.compile(r"[™®©]")
_APOSTROPHES = re.compile("['\u2019`\u00b4]")
_ROMAN = re.compile(r"^(?=[ivxl]+$)l?x{0,3}(ix|iv|v?i{0,3})$")

# Words ignored when comparing titles.
_STOPWORDS = frozenset({"the", "a", "an", "of", "and", "in", "on"})


def normalize_key(text: str) -> str:
    """Case/punctuation-insensitive key: ``"Shoot 'Em Up"`` -> ``"shootemup"``."""
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _NON_ALNUM.sub("", folded.lower())


def title_tokens(name: str) -> list[str]:
    """Tokenise a game title for series comparison.

    ``"Assassin's Creed® IV Black Flag™"`` -> ``["assassins", "creed", "iv", "black", "flag"]``
    """
    text = _TRADEMARKS.sub("", name)
    text = _APOSTROPHES.sub("", text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return [tok for tok in _NON_ALNUM.split(text) if tok and tok not in _STOPWORDS]


def is_numeral(token: str) -> bool:
    """True for sequel markers: ``2``, ``2033``, ``iv``, ``xii``."""
    return token.isdigit() or bool(_ROMAN.match(token))


def common_prefix_length(a: list[str], b: list[str]) -> int:
    n = 0
    for x, y in zip(a, b, strict=False):
        if x != y:
            break
        n += 1
    return n


def same_series(a: list[str], b: list[str]) -> bool:
    """Heuristic: do two tokenised titles belong to the same series?

    * Two or more leading words in common -> same series
      (``Dark Souls`` / ``Dark Souls III``, ``Half-Life`` / ``Half-Life: Alyx``).
    * One leading word in common counts only when it is a whole title apart
      from sequel numbers (``Portal`` / ``Portal 2``,
      ``The Witcher 2`` / ``The Witcher 3: Wild Hunt``).
    """
    if not a or not b or a == b:
        return False
    cp = common_prefix_length(a, b)
    if cp >= 2:
        return True
    if cp == 1:
        base_a = [t for t in a if not is_numeral(t)]
        base_b = [t for t in b if not is_numeral(t)]
        return len(base_a) == 1 or len(base_b) == 1
    return False


def series_label(token_lists: list[list[str]]) -> str:
    """Human-readable name of the longest leading word run shared by every title."""
    if not token_lists:
        return ""
    prefix = token_lists[0]
    for tokens in token_lists[1:]:
        prefix = prefix[: common_prefix_length(prefix, tokens)]
    prefix = [t for t in prefix if not is_numeral(t)] or prefix
    return " ".join(t.upper() if is_numeral(t) else t.capitalize() for t in prefix)
