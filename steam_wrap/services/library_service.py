"""Loads a user's library and enriches it with public store metadata.

Data flow for ``get_library``::

    token ─► GetOwnedGames ─► appids ─┬─► per-app cache hit ─────────────┐
                                      └─► GetItems (batched, parallel) ──┤
                       GetTagList (cached) ──────────────────────────────┤
                                                                         ▼
                                                       list[Game] (cached per token)

* The library is cached under a SHA-256 of the token, never under the SteamID,
  so a forged token claiming someone else's SteamID can't read their cached
  library (Steam is the only party that can validate tokens).
* Store metadata is public and shared across users, so it's cached per app
  for much longer.
* Concurrent requests for the same library share one upstream load.
* A failing metadata batch degrades gracefully: those games come back with
  ``metadata_available = false`` instead of failing the whole request.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from steam_wrap.cache import CacheBackend
from steam_wrap.clients import SteamClient
from steam_wrap.core.config import Settings
from steam_wrap.core.exceptions import AppError, GameNotFoundError
from steam_wrap.core.security import TokenInfo
from steam_wrap.schemas import Game, LibraryInfo, Platforms, PlayerProfile

logger = logging.getLogger(__name__)

_UNAVAILABLE: dict[str, Any] = {"__unavailable__": True}
_DECK_COMPAT = {3: "verified", 2: "playable", 1: "unsupported"}


@dataclass(slots=True)
class Library:
    """A user's enriched library, as cached in memory."""

    steamid: str
    games: list[Game]
    metadata_missing: int
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    by_appid: dict[int, Game] = field(init=False)

    def __post_init__(self) -> None:
        self.by_appid = {g.appid: g for g in self.games}

    def get(self, appid: int) -> Game:
        try:
            return self.by_appid[appid]
        except KeyError:
            raise GameNotFoundError(f"App {appid} is not in this user's library.") from None

    def info(self) -> LibraryInfo:
        return LibraryInfo(
            steamid=self.steamid,
            total_games=len(self.games),
            metadata_missing=self.metadata_missing,
            fetched_at=self.fetched_at,
        )


class LibraryService:
    """Facade over :class:`SteamClient` that adds enrichment and caching."""

    def __init__(self, client: SteamClient, cache: CacheBackend, settings: Settings) -> None:
        self._client = client
        self._cache = cache
        self._settings = settings
        self._primary_genres = {g.casefold(): g for g in settings.genres.primary}
        self._inflight: dict[str, asyncio.Task[Library]] = {}

    # ------------------------------------------------------------------ #
    # Library
    # ------------------------------------------------------------------ #
    async def get_library(self, token: TokenInfo, *, refresh: bool = False) -> Library:
        """Return the user's enriched library (cached for ``library_ttl_seconds``)."""
        key = f"library:{token.fingerprint}"
        if not refresh:
            cached = self._cache.get(key)
            if cached is not None:
                return cached  # type: ignore[no-any-return]

        task = self._inflight.get(key)
        if task is None:
            task = asyncio.create_task(self._load_library(token))
            self._inflight[key] = task
            task.add_done_callback(lambda _t: self._inflight.pop(key, None))
        library = await asyncio.shield(task)
        self._cache.set(key, library, self._settings.cache.library_ttl_seconds)
        return library

    async def _load_library(self, token: TokenInfo) -> Library:
        owned = await self._client.get_owned_games(token.token, token.steamid)
        appids = [int(g["appid"]) for g in owned]
        items, tag_names = await asyncio.gather(
            self._get_store_items(appids), self._get_tag_names()
        )
        games = [self._build_game(g, items.get(int(g["appid"])), tag_names) for g in owned]
        games.sort(key=lambda g: g.name.casefold())
        missing = sum(1 for g in games if not g.metadata_available)
        logger.info("Loaded library: %d games (%d without store metadata)", len(games), missing)
        return Library(steamid=token.steamid, games=games, metadata_missing=missing)

    # ------------------------------------------------------------------ #
    # Profile
    # ------------------------------------------------------------------ #
    async def get_profile(self, token: TokenInfo) -> PlayerProfile | None:
        key = f"profile:{token.fingerprint}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        try:
            raw = await self._client.get_player_summary(token.token, token.steamid)
        except AppError as exc:
            logger.info("Profile lookup failed: %s", exc.code)
            return None
        if raw is None:
            return None
        profile = PlayerProfile(
            persona_name=raw.get("personaname"),
            profile_url=raw.get("profileurl"),
            avatar_url=raw.get("avatarfull") or raw.get("avatar"),
            country_code=raw.get("loccountrycode"),
        )
        self._cache.set(key, profile, self._settings.cache.profile_ttl_seconds)
        return profile

    # ------------------------------------------------------------------ #
    # Store metadata
    # ------------------------------------------------------------------ #
    async def _get_store_items(self, appids: list[int]) -> dict[int, dict[str, Any] | None]:
        """Per-app store items; ``None`` where metadata is unavailable."""
        result: dict[int, dict[str, Any] | None] = {}
        missing: list[int] = []
        for appid in appids:
            cached = self._cache.get(f"store:{appid}")
            if cached is None:
                missing.append(appid)
            else:
                result[appid] = None if cached.get("__unavailable__") else cached

        if not missing:
            return result

        size = self._settings.steam.store_batch_size
        batches = [missing[i : i + size] for i in range(0, len(missing), size)]
        semaphore = asyncio.Semaphore(self._settings.steam.store_max_concurrency)
        ttl = self._settings.cache.store_item_ttl_seconds

        async def fetch(batch: list[int]) -> None:
            async with semaphore:
                try:
                    items = await self._client.get_store_items(batch)
                except AppError as exc:
                    logger.warning("Store metadata batch of %d failed: %s", len(batch), exc.code)
                    for appid in batch:
                        result[appid] = None  # not cached: retry on next load
                    return
            for appid in batch:
                item = items.get(appid)
                if item is None or item.get("success") != 1:
                    self._cache.set(f"store:{appid}", _UNAVAILABLE, ttl)
                    result[appid] = None
                else:
                    self._cache.set(f"store:{appid}", item, ttl)
                    result[appid] = item

        await asyncio.gather(*(fetch(b) for b in batches))
        return result

    async def _get_tag_names(self) -> dict[int, str]:
        cached = self._cache.get("tags:list")
        if cached is not None:
            return cached  # type: ignore[no-any-return]
        try:
            tags = await self._client.get_tag_list()
        except AppError as exc:
            logger.warning("Tag list unavailable: %s", exc.code)
            return {}
        self._cache.set("tags:list", tags, self._settings.cache.tag_list_ttl_seconds)
        return tags

    # ------------------------------------------------------------------ #
    # Mapping
    # ------------------------------------------------------------------ #
    def _build_game(
        self, owned: dict[str, Any], item: dict[str, Any] | None, tag_names: dict[int, str]
    ) -> Game:
        steam = self._settings.steam
        appid = int(owned["appid"])
        icon_hash = owned.get("img_icon_url")
        last_played = owned.get("rtime_last_played") or 0

        game: dict[str, Any] = {
            "appid": appid,
            "name": owned.get("name") or (item or {}).get("name") or f"App {appid}",
            "playtime_minutes": int(owned.get("playtime_forever", 0)),
            "playtime_2weeks_minutes": int(owned.get("playtime_2weeks", 0)),
            "last_played_at": datetime.fromtimestamp(last_played, UTC) if last_played else None,
            "icon_url": (
                f"{steam.media_base_url}/steamcommunity/public/images/apps/{appid}/{icon_hash}.jpg"
                if icon_hash
                else None
            ),
            "header_image_url": f"{steam.asset_base_url}/steam/apps/{appid}/header.jpg",
            "store_url": f"{steam.store_base_url}/app/{appid}",
            "metadata_available": item is not None,
        }
        if item is None:
            return Game(**game)

        tag_entries = sorted(item.get("tags") or [], key=lambda t: t.get("weight", 0), reverse=True)
        tag_ids = [int(t["tagid"]) for t in tag_entries if "tagid" in t] or [
            int(t) for t in item.get("tagids") or []
        ]
        tags = [tag_names[t] for t in tag_ids if t in tag_names]
        genres = [
            self._primary_genres[t.casefold()] for t in tags if t.casefold() in self._primary_genres
        ]

        basic = item.get("basic_info") or {}
        assets = item.get("assets") or {}
        release = item.get("release") or {}
        platforms = item.get("platforms") or {}

        if assets.get("asset_url_format") and assets.get("header"):
            path = str(assets["asset_url_format"]).replace("${FILENAME}", str(assets["header"]))
            game["header_image_url"] = f"{steam.asset_base_url}/{path}"
        if item.get("store_url_path"):
            game["store_url"] = f"{steam.store_base_url}/{item['store_url_path']}"

        release_ts = release.get("original_release_date") or release.get("steam_release_date")

        game.update(
            tags=tags,
            genres=genres,
            franchises=_names(basic.get("franchises")),
            developers=_names(basic.get("developers")),
            publishers=_names(basic.get("publishers")),
            short_description=basic.get("short_description"),
            is_free=bool(item.get("is_free", False)),
            release_date=_to_date(release_ts),
            platforms=Platforms(
                windows=bool(platforms.get("windows")),
                mac=bool(platforms.get("mac")),
                linux=bool(platforms.get("steamos_linux") or platforms.get("linux")),
                steam_deck=_DECK_COMPAT.get(
                    platforms.get("steam_deck_compat_category", 0), "unknown"
                ),
            ),
        )
        return Game(**game)


def _names(entries: Any) -> list[str]:
    if not isinstance(entries, list):
        return []
    return [str(e["name"]) for e in entries if isinstance(e, dict) and e.get("name")]


def _to_date(timestamp: Any) -> date | None:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, UTC).date() if ts > 0 else None
