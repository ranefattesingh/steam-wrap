"""Shared fixtures: fake tokens, fake Steam responses and a configured test app."""

from __future__ import annotations

import base64
import json
import time
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from steam_wrap.core.config import Settings
from steam_wrap.main import create_app

STEAMID = "76561198000000001"
API = "https://api.steampowered.com"

TAGS = {
    19: "Action",
    21: "Adventure",
    597: "Casual",
    122: "RPG",
    1663: "FPS",
    1774: "Shooter",
    1695: "Open World",
    1681: "Pirates",
    4182: "Singleplayer",
    1702: "Crafting",
    3810: "Sandbox",
    1664: "Puzzle",
    492: "Indie",
}

# appid -> (name, playtime, tagids, franchises, developers, publishers)
LIBRARY: dict[int, tuple[str, int, list[int], list[str], list[str], list[str]]] = {
    242050: (
        "Assassin's Creed® IV Black Flag™",
        1800,
        [1681, 1695, 21, 19, 4182],
        ["Assassin's Creed"],
        ["Ubisoft Montreal"],
        ["Ubisoft"],
    ),
    289650: (
        "Assassin's Creed® Unity",
        600,
        [1695, 19, 21, 4182],
        ["Assassin's Creed"],
        ["Ubisoft"],
        ["Ubisoft"],
    ),
    812140: (
        "Assassin's Creed® Odyssey",
        3000,
        [1695, 122, 19, 21],
        ["Assassin's Creed"],
        ["Ubisoft Quebec"],
        ["Ubisoft"],
    ),
    730: ("Counter-Strike 2", 9000, [1663, 1774, 19], [], ["Valve"], ["Valve"]),
    620: ("Portal 2", 700, [1664, 19, 21], [], ["Valve"], ["Valve"]),
    400: ("Portal", 300, [1664, 19], [], ["Valve"], ["Valve"]),
    413150: (
        "Stardew Valley",
        5000,
        [597, 122, 3810, 1702, 492],
        [],
        ["ConcernedApe"],
        ["ConcernedApe"],
    ),
    999999: ("Delisted Game", 10, [], [], [], []),
}


def make_token(steamid: str = STEAMID, exp_in: int = 3600, **extra: Any) -> str:
    def enc(obj: dict[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    payload = {"iss": "steam", "sub": steamid, "exp": int(time.time()) + exp_in, **extra}
    return f"{enc({'alg': 'EdDSA', 'typ': 'JWT'})}.{enc(payload)}.signature"


def owned_games_payload() -> dict[str, Any]:
    return {
        "response": {
            "game_count": len(LIBRARY),
            "games": [
                {
                    "appid": appid,
                    "name": name,
                    "playtime_forever": playtime,
                    "img_icon_url": "abc123",
                    "rtime_last_played": 1_700_000_000 + appid % 1000,
                }
                for appid, (name, playtime, *_rest) in LIBRARY.items()
            ],
        }
    }


def store_item(appid: int) -> dict[str, Any]:
    name, _pt, tagids, franchises, devs, pubs = LIBRARY[appid]
    if appid == 999999:
        return {"item_type": 0, "id": appid, "success": 9}
    return {
        "item_type": 0,
        "id": appid,
        "appid": appid,
        "success": 1,
        "visible": True,
        "name": name,
        "store_url_path": f"app/{appid}/Slug",
        "is_free": appid == 730,
        "tagids": tagids,
        "tags": [{"tagid": t, "weight": 1000 - i * 10} for i, t in enumerate(tagids)],
        "basic_info": {
            "short_description": f"About {name}",
            "developers": [{"name": d} for d in devs],
            "publishers": [{"name": p} for p in pubs],
            "franchises": [{"name": f} for f in franchises],
        },
        "assets": {
            "asset_url_format": f"steam/apps/{appid}/${{FILENAME}}?t=1",
            "header": "header.jpg",
        },
        "release": {"steam_release_date": 1_380_000_000},
        "platforms": {"windows": True, "steam_deck_compat_category": 3},
    }


def get_items_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.url.params["input_json"])
    ids = [entry["appid"] for entry in body["ids"]]
    return httpx.Response(
        200, json={"response": {"store_items": [store_item(i) for i in ids if i in LIBRARY]}}
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        app={"environment": "test", "log_level": "WARNING"},
        steam={"max_retries": 1, "retry_backoff_seconds": 0, "store_batch_size": 3},
        genres={
            "aliases": {"shooting": ["Shooter", "FPS"], "roleplaying": ["RPG"]},
        },
        similarity={"ignored_tags": ["Singleplayer"], "min_score": 0.1},
    )


@pytest.fixture
def steam_mock() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=API, assert_all_called=False) as router:
        router.get("/IPlayerService/GetOwnedGames/v1/", name="owned").respond(
            200, json=owned_games_payload()
        )
        router.get("/IStoreBrowseService/GetItems/v1/", name="items").mock(
            side_effect=get_items_handler
        )
        router.get("/IStoreService/GetTagList/v1/", name="tags").respond(
            200,
            json={"response": {"tags": [{"tagid": k, "name": v} for k, v in TAGS.items()]}},
        )
        router.get("/ISteamUser/GetPlayerSummaries/v2/", name="profile").respond(
            200,
            json={
                "response": {
                    "players": [
                        {
                            "steamid": STEAMID,
                            "personaname": "tester",
                            "profileurl": "https://steamcommunity.com/id/tester/",
                            "avatarfull": "https://avatars.example/a.jpg",
                        }
                    ]
                }
            },
        )
        yield router


@pytest.fixture
def client(settings: Settings, steam_mock: respx.MockRouter) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token()}"}
