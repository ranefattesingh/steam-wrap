"""Thin async client for the Steam Web API.

Endpoints used (all ``GET`` on ``api.steampowered.com``):

=====================================  ===========================================
``IPlayerService/GetOwnedGames/v1``    The user's library. Needs the user's token.
``ISteamUser/GetPlayerSummaries/v2``   Profile name/avatar for ``/me``.
``IStoreBrowseService/GetItems/v1``    Public store metadata (tags, developers,
                                       publishers, franchises, assets) for up to
                                       ``store_batch_size`` apps per call.
``IStoreService/GetTagList/v1``        Tag id -> tag name dictionary.
=====================================  ===========================================

The client only does transport concerns: building requests, retrying
429/5xx/network failures with exponential backoff, and translating failures
into :mod:`steam_wrap.core.exceptions`. It never logs query strings because
they contain the access token.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from typing import Any

import httpx

from steam_wrap.core.config import SteamSettings
from steam_wrap.core.exceptions import (
    SteamAuthError,
    SteamRateLimitedError,
    SteamUnavailableError,
)

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class SteamClient:
    """Async wrapper over the Steam Web API endpoints this service needs."""

    def __init__(self, settings: SteamSettings, http: httpx.AsyncClient) -> None:
        self._settings = settings
        self._http = http

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def get_owned_games(self, access_token: str, steamid: str) -> list[dict[str, Any]]:
        """Return the raw ``games`` array of ``GetOwnedGames``.

        Includes free games the user has played and free-to-play licences, i.e.
        everything the user can download and play. A private profile yields an
        empty list (Steam returns an empty ``response`` object).
        """
        data = await self._get(
            "/IPlayerService/GetOwnedGames/v1/",
            {
                "access_token": access_token,
                "steamid": steamid,
                "include_appinfo": "true",
                "include_played_free_games": "true",
                "include_free_sub": "true",
                "skip_unvetted_apps": "false",
                "language": self._settings.language,
            },
            operation="GetOwnedGames",
        )
        games = data.get("response", {}).get("games", [])
        return [g for g in games if isinstance(g, dict) and "appid" in g]

    async def get_player_summary(self, access_token: str, steamid: str) -> dict[str, Any] | None:
        """Return the player's public profile, or ``None`` if unavailable."""
        params: dict[str, str] = {"steamids": steamid}
        if self._settings.api_key is not None:
            params["key"] = self._settings.api_key.get_secret_value()
        else:
            params["access_token"] = access_token
        data = await self._get(
            "/ISteamUser/GetPlayerSummaries/v2/", params, operation="GetPlayerSummaries"
        )
        players = data.get("response", {}).get("players", [])
        return players[0] if players else None

    async def get_store_items(self, appids: Iterable[int]) -> dict[int, dict[str, Any]]:
        """Fetch store metadata for one batch of appids.

        Returns a mapping ``appid -> store_item``. Apps Steam doesn't know (or
        that were delisted) are present with ``success != 1``.
        """
        ids = list(appids)
        if not ids:
            return {}
        request = {
            "ids": [{"appid": appid} for appid in ids],
            "context": {
                "language": self._settings.language,
                "country_code": self._settings.country_code,
            },
            "data_request": {
                "include_basic_info": True,
                "include_tag_count": self._settings.tags_per_game,
                "include_assets": True,
                "include_release": True,
                "include_platforms": True,
            },
        }
        data = await self._get(
            "/IStoreBrowseService/GetItems/v1/",
            {"input_json": json.dumps(request, separators=(",", ":"))},
            operation="GetItems",
        )
        items = data.get("response", {}).get("store_items", [])
        result: dict[int, dict[str, Any]] = {}
        for item in items:
            appid = item.get("appid") or item.get("id")
            if isinstance(appid, int):
                result[appid] = item
        return result

    async def get_tag_list(self) -> dict[int, str]:
        """Return Steam's tag dictionary (``tagid -> name``) in the configured language."""
        data = await self._get(
            "/IStoreService/GetTagList/v1/",
            {"language": self._settings.language},
            operation="GetTagList",
        )
        tags = data.get("response", {}).get("tags", [])
        return {int(t["tagid"]): str(t["name"]) for t in tags if "tagid" in t and "name" in t}

    # ------------------------------------------------------------------ #
    # Transport
    # ------------------------------------------------------------------ #
    async def _get(self, path: str, params: dict[str, str], *, operation: str) -> dict[str, Any]:
        url = self._settings.api_base_url.rstrip("/") + path
        attempts = self._settings.max_retries + 1
        last_error: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self._http.get(url, params=params)
            except httpx.TransportError as exc:
                last_error = exc
                logger.warning(
                    "Steam %s transport error (attempt %d/%d): %s",
                    operation,
                    attempt,
                    attempts,
                    type(exc).__name__,
                )
            else:
                status = response.status_code
                if status in (401, 403):
                    raise SteamAuthError(
                        "Steam rejected the access token (it may be expired or revoked)."
                    )
                if status not in _RETRYABLE_STATUS:
                    if status >= 400:
                        raise SteamUnavailableError(f"Steam {operation} failed with HTTP {status}.")
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise SteamUnavailableError(
                            f"Steam {operation} returned invalid JSON."
                        ) from exc
                    return payload if isinstance(payload, dict) else {}

                last_error = (
                    SteamRateLimitedError()
                    if status == 429
                    else SteamUnavailableError(f"Steam {operation} failed with HTTP {status}.")
                )
                logger.warning(
                    "Steam %s returned HTTP %d (attempt %d/%d)",
                    operation,
                    status,
                    attempt,
                    attempts,
                )

            if attempt < attempts:
                await asyncio.sleep(self._settings.retry_backoff_seconds * 2 ** (attempt - 1))

        if isinstance(last_error, SteamRateLimitedError | SteamUnavailableError):
            raise last_error
        raise SteamUnavailableError(f"Could not reach Steam ({operation}).") from last_error
