"""Genre matching, filtering, sorting and pagination of library games.

Genre queries are matched against a game's **tags** (which include Steam's
top-level genres), case- and punctuation-insensitively. Friendly words are
expanded through ``genres.aliases`` in ``config.yaml``, so ``?genre=shooting``
matches games tagged ``Shooter``, ``FPS``, ``Third-Person Shooter`` and so on.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from typing import Literal

from steam_wrap.core.config import GenreSettings
from steam_wrap.schemas import Game, GenreCount, Page
from steam_wrap.services.text import normalize_key

SortField = Literal["name", "playtime", "last_played", "release_date"]
SortOrder = Literal["asc", "desc"]
GenreScope = Literal["genres", "tags", "all"]


class GenreMatcher:
    """Resolves user genre queries to sets of tag keys and tests games against them."""

    def __init__(self, settings: GenreSettings) -> None:
        self._primary = {normalize_key(g) for g in settings.primary}
        self._aliases: dict[str, frozenset[str]] = {
            normalize_key(word): frozenset(normalize_key(t) for t in tags) | {normalize_key(word)}
            for word, tags in settings.aliases.items()
        }
        self.aliases = settings.aliases

    def resolve(self, query: str) -> frozenset[str]:
        key = normalize_key(query)
        return self._aliases.get(key, frozenset({key}))

    @staticmethod
    def game_keys(game: Game) -> set[str]:
        return {normalize_key(t) for t in (*game.tags, *game.genres)}

    def matches(self, game: Game, queries: Sequence[str], *, match_all: bool = False) -> bool:
        if not queries:
            return True
        keys = self.game_keys(game)
        hits = (bool(keys & self.resolve(q)) for q in queries)
        return all(hits) if match_all else any(hits)

    def is_primary(self, name: str) -> bool:
        return normalize_key(name) in self._primary

    def count(self, games: Sequence[Game], scope: GenreScope = "genres") -> list[GenreCount]:
        """Count games per genre/tag across a library, most common first."""
        counter: Counter[str] = Counter()
        for game in games:
            names = game.genres if scope == "genres" else game.tags
            if scope == "all":
                names = list(dict.fromkeys([*game.genres, *game.tags]))
            counter.update(set(names))
        return [
            GenreCount(name=name, game_count=n, is_primary=self.is_primary(name))
            for name, n in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0].casefold()))
        ]


def filter_games(
    games: Sequence[Game],
    matcher: GenreMatcher,
    *,
    genres: Sequence[str] = (),
    match_all: bool = False,
    search: str | None = None,
) -> list[Game]:
    """Apply genre and free-text name filters."""
    needle = normalize_key(search) if search else ""
    return [
        g
        for g in games
        if matcher.matches(g, genres, match_all=match_all)
        and (not needle or needle in normalize_key(g.name))
    ]


def sort_games(games: list[Game], field: SortField, order: SortOrder | None) -> list[Game]:
    """Sort games; ``None`` order means ascending for name, descending otherwise.

    Games without a value for the sort field (e.g. never played) always sort last.
    """
    descending = (order or ("asc" if field == "name" else "desc")) == "desc"
    if field == "name":
        return sorted(games, key=lambda g: g.name.casefold(), reverse=descending)

    def value(g: Game) -> float | None:
        if field == "playtime":
            return float(g.playtime_minutes)
        if field == "last_played":
            return g.last_played_at.timestamp() if g.last_played_at else None
        return float(g.release_date.toordinal()) if g.release_date else None

    present = [g for g in games if value(g) is not None]
    absent = [g for g in games if value(g) is None]
    present.sort(key=lambda g: value(g) or 0.0, reverse=descending)
    return present + absent


def paginate(items: list[Game], page: int, page_size: int) -> tuple[list[Game], Page]:
    total = len(items)
    start = (page - 1) * page_size
    meta = Page(page=page, page_size=page_size, total=total, pages=math.ceil(total / page_size))
    return items[start : start + page_size], meta
