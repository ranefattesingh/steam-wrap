"""Similar-game scoring and library grouping.

Steam has no "similar games" API, so similarity is computed from store
metadata of the games the user owns. For a target game ``A`` and candidate
``B``::

    score = Σ weight_i · signal_i / Σ weight_i          (0..1)

==========  ======================================================================
signal      value
==========  ======================================================================
franchise   1 if both share an official Steam franchise. If either game lacks
            franchise data, 1 if the titles look like the same series
            ("Dark Souls" / "Dark Souls III").
tags        Jaccard overlap of each game's top-N tags (generic tags ignored).
genres      Jaccard overlap of top-level genres.
developer   1 if any developer is shared.
publisher   1 if any publisher is shared.
==========  ======================================================================

Each result carries human-readable ``reasons`` explaining the score.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from steam_wrap.core.config import SimilaritySettings
from steam_wrap.schemas import Game, GameGroup, GameRef
from steam_wrap.services.text import normalize_key, same_series, series_label, title_tokens

GroupBy = Literal["franchise", "genre", "developer"]


@dataclass(frozen=True, slots=True)
class _Features:
    game: Game
    tokens: list[str]
    franchises: dict[str, str]  # normalised -> display
    tags: dict[str, str]
    genres: dict[str, str]
    developers: dict[str, str]
    publishers: dict[str, str]


def _keyed(values: Iterable[str]) -> dict[str, str]:
    return {normalize_key(v): v for v in values if normalize_key(v)}


def _jaccard(a: dict[str, str], b: dict[str, str]) -> tuple[float, list[str]]:
    if not a or not b:
        return 0.0, []
    shared = [a[k] for k in a if k in b]  # keep A's (relevance) order
    return len(shared) / len(a.keys() | b.keys()), shared


def to_ref(game: Game) -> GameRef:
    return GameRef(id=game.appid, name=game.name, description=game.short_description)


@dataclass(frozen=True, slots=True)
class ScoredGame:
    """A candidate with its similarity score (0..1) and the reasons behind it."""

    game: Game
    score: float
    reasons: list[str]


class SimilarityService:
    """Ranks library games by similarity and clusters a library into groups."""

    def __init__(self, settings: SimilaritySettings) -> None:
        self._settings = settings
        self._ignored = {normalize_key(t) for t in settings.ignored_tags}
        w = settings.weights
        self._weights = {
            "franchise": w.franchise,
            "tags": w.tags,
            "genres": w.genres,
            "developer": w.developer,
            "publisher": w.publisher,
        }
        self._weight_total = sum(self._weights.values()) or 1.0

    # ------------------------------------------------------------------ #
    # Features
    # ------------------------------------------------------------------ #
    def _features(self, game: Game) -> _Features:
        top_tags = [t for t in game.tags if normalize_key(t) not in self._ignored][
            : self._settings.top_tags
        ]
        return _Features(
            game=game,
            tokens=title_tokens(game.name),
            franchises=_keyed(game.franchises),
            tags=_keyed(top_tags),
            genres=_keyed(game.genres),
            developers=_keyed(game.developers),
            publishers=_keyed(game.publishers),
        )

    @staticmethod
    def _franchise_match(a: _Features, b: _Features) -> str | None:
        """Return a reason string if A and B are in the same franchise/series."""
        if a.franchises and b.franchises:
            shared = [a.franchises[k] for k in a.franchises if k in b.franchises]
            return f"same franchise: {shared[0]}" if shared else None
        if same_series(a.tokens, b.tokens):
            return f"same series: {series_label([a.tokens, b.tokens])}"
        return None

    # ------------------------------------------------------------------ #
    # Scoring
    # ------------------------------------------------------------------ #
    def _score(self, a: _Features, b: _Features) -> tuple[float, list[str]]:
        reasons: list[str] = []
        total = 0.0

        franchise = self._franchise_match(a, b)
        if franchise:
            total += self._weights["franchise"]
            reasons.append(franchise)

        genre_score, shared_genres = _jaccard(a.genres, b.genres)
        if shared_genres:
            total += self._weights["genres"] * genre_score
            reasons.append(f"shared genres: {', '.join(shared_genres)}")

        tag_score, shared_tags = _jaccard(a.tags, b.tags)
        if shared_tags:
            total += self._weights["tags"] * tag_score
            # Don't repeat genres in the tag reason.
            extra = [t for t in shared_tags if normalize_key(t) not in a.genres]
            if extra:
                reasons.append(f"shared tags: {', '.join(extra[:5])}")

        dev = next((a.developers[k] for k in a.developers if k in b.developers), None)
        if dev:
            total += self._weights["developer"]
            reasons.append(f"same developer: {dev}")

        pub = next((a.publishers[k] for k in a.publishers if k in b.publishers), None)
        if pub:
            total += self._weights["publisher"]
            reasons.append(f"same publisher: {pub}")

        return round(min(total / self._weight_total, 1.0), 4), reasons

    def score(self, a: Game, b: Game) -> tuple[float, list[str]]:
        """Similarity of two games (0..1) and the reasons behind it."""
        return self._score(self._features(a), self._features(b))

    def rank(
        self,
        target: Game,
        candidates: Sequence[Game],
        *,
        limit: int | None = None,
        min_score: float | None = None,
    ) -> list[ScoredGame]:
        """Rank ``candidates`` by similarity to ``target`` (target itself excluded).

        Ties are broken by playtime (games the user plays more come first), then name.
        """
        limit = limit or self._settings.default_limit
        threshold = self._settings.min_score if min_score is None else min_score
        target_f = self._features(target)

        scored: list[ScoredGame] = []
        for game in candidates:
            if game.appid == target.appid:
                continue
            score, reasons = self._score(target_f, self._features(game))
            if score >= threshold and score > 0:
                scored.append(ScoredGame(game=game, score=score, reasons=reasons))

        scored.sort(key=lambda s: (-s.score, -s.game.playtime_minutes, s.game.name.casefold()))
        return scored[:limit]

    def similar(
        self,
        target: Game,
        candidates: Sequence[Game],
        *,
        limit: int | None = None,
        min_score: float | None = None,
    ) -> list[GameRef]:
        """Names (and app ids) of the most similar games, best match first."""
        return [
            to_ref(s.game) for s in self.rank(target, candidates, limit=limit, min_score=min_score)
        ]

    # ------------------------------------------------------------------ #
    # Grouping
    # ------------------------------------------------------------------ #
    def group(self, games: Sequence[Game], by: GroupBy, *, min_size: int = 2) -> list[GameGroup]:
        """Cluster the library. Genre groups overlap; franchise/developer groups don't."""
        if by == "franchise":
            buckets = self._franchise_buckets(games)
        else:
            named: dict[str, list[Game]] = defaultdict(list)
            for game in games:
                values = game.genres if by == "genre" else game.developers[:1]
                for value in values:
                    named[value].append(game)
            buckets = list(named.items())

        groups = [
            GameGroup(
                name=name,
                size=len(members),
                games=[to_ref(g) for g in sorted(members, key=lambda g: g.name.casefold())],
            )
            for name, members in buckets
            if len(members) >= min_size
        ]
        groups.sort(key=lambda g: (-g.size, g.name.casefold()))
        return groups

    def _franchise_buckets(self, games: Sequence[Game]) -> list[tuple[str, list[Game]]]:
        feats = [self._features(g) for g in games]
        parent = list(range(len(feats)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            parent[find(i)] = find(j)

        # 1. Official franchise names.
        first_with: dict[str, int] = {}
        for i, f in enumerate(feats):
            for key in f.franchises:
                if key in first_with:
                    union(i, first_with[key])
                else:
                    first_with[key] = i

        # 2. Title heuristic - only compare titles sharing a first word.
        by_first_word: dict[str, list[int]] = defaultdict(list)
        for i, f in enumerate(feats):
            if f.tokens:
                by_first_word[f.tokens[0]].append(i)
        for indices in by_first_word.values():
            for x, i in enumerate(indices):
                for j in indices[x + 1 :]:
                    if find(i) != find(j) and self._franchise_match(feats[i], feats[j]):
                        union(i, j)

        components: dict[int, list[int]] = defaultdict(list)
        for i in range(len(feats)):
            components[find(i)].append(i)

        buckets: list[tuple[str, list[Game]]] = []
        for members in components.values():
            official = Counter(name for i in members for name in feats[i].franchises.values())
            if official:
                name = official.most_common(1)[0][0]
            else:
                name = (
                    series_label([feats[i].tokens for i in members]) or feats[members[0]].game.name
                )
            buckets.append((name, [feats[i].game for i in members]))
        return buckets
