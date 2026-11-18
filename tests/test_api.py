"""End-to-end route tests against a mocked Steam."""

from __future__ import annotations

import httpx
import respx
from fastapi.testclient import TestClient

from tests.conftest import LIBRARY, STEAMID, make_token

P = "/api/v1"


def test_health(client: TestClient) -> None:
    r = client.get(f"{P}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.headers["x-request-id"]


def test_missing_token(client: TestClient) -> None:
    r = client.get(f"{P}/games")
    assert r.status_code == 401
    body = r.json()["error"]
    assert body["code"] == "invalid_token"
    assert body["request_id"]


def test_expired_token(client: TestClient) -> None:
    r = client.get(f"{P}/games", headers={"Authorization": f"Bearer {make_token(exp_in=-5)}"})
    assert r.status_code == 401


def test_steam_rejects_token(
    client: TestClient, steam_mock: respx.MockRouter, auth: dict[str, str]
) -> None:
    steam_mock["owned"].respond(401)
    r = client.get(f"{P}/games", headers=auth)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "steam_auth_failed"


def test_steam_down(client: TestClient, steam_mock: respx.MockRouter, auth: dict[str, str]) -> None:
    steam_mock["owned"].respond(500)
    r = client.get(f"{P}/games", headers=auth)
    assert r.status_code == 502


def test_me(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(f"{P}/me", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["steamid"] == STEAMID
    assert body["profile"]["persona_name"] == "tester"


def test_list_games_enriched_and_cached(
    client: TestClient, steam_mock: respx.MockRouter, auth: dict[str, str]
) -> None:
    r = client.get(f"{P}/games?only_names=false", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["only_names"] is False
    assert body["library"]["total_games"] == len(LIBRARY)
    assert body["library"]["metadata_missing"] == 1
    names = [g["name"] for g in body["items"]]
    assert names == sorted(names, key=str.casefold)

    # List items are compact: only id, name and description.
    black_flag = next(g for g in body["items"] if g["id"] == 242050)
    assert black_flag == {
        "id": 242050,
        "name": "Assassin's Creed® IV Black Flag™",
        "description": "About Assassin's Creed® IV Black Flag™",
    }
    delisted = next(g for g in body["items"] if g["id"] == 999999)
    assert delisted["description"] is None

    # Full data is on the detail endpoint.
    detail = client.get(f"{P}/games/242050", headers=auth).json()
    assert detail["genres"] == ["Adventure", "Action"]
    assert detail["franchises"] == ["Assassin's Creed"]
    assert detail["header_image_url"].endswith("/steam/apps/242050/header.jpg?t=1")
    assert detail["platforms"]["steam_deck"] == "verified"
    assert client.get(f"{P}/games/999999", headers=auth).json()["metadata_available"] is False

    # Store batches of 3 -> 3 GetItems calls; second request is fully cached.
    assert steam_mock["items"].call_count == 3
    client.get(f"{P}/games", headers=auth)
    assert steam_mock["owned"].call_count == 1

    client.get(f"{P}/games?refresh=true", headers=auth)
    assert steam_mock["owned"].call_count == 2
    assert steam_mock["items"].call_count == 3  # store metadata still cached


def test_only_names_is_the_default(client: TestClient, auth: dict[str, str]) -> None:
    body = client.get(f"{P}/games?genre=assassin&search=creed", headers=auth).json()
    assert body["only_names"] is True
    assert body["page"]["total"] == 0  # "assassin" is neither a genre nor a tag

    body = client.get(f"{P}/games?search=assassin&sort=playtime", headers=auth).json()
    assert body["only_names"] is True
    assert body["page"]["total"] == 3
    assert body["items"] == [
        "Assassin's Creed® Odyssey",
        "Assassin's Creed® IV Black Flag™",
        "Assassin's Creed® Unity",
    ]

    body = client.get(f"{P}/genres/fps/games", headers=auth).json()
    assert body["items"] == ["Counter-Strike 2"]


def test_query_token(client: TestClient) -> None:
    r = client.get(f"{P}/games", params={"access_token": make_token()})
    assert r.status_code == 200


def test_filter_by_genre_alias(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(f"{P}/games?genre=shooting&only_names=false", headers=auth)
    assert [g["id"] for g in r.json()["items"]] == [730]

    r = client.get(f"{P}/games?genre=casual&genre=shooting&only_names=false", headers=auth)
    assert {g["id"] for g in r.json()["items"]} == {730, 413150}

    r = client.get(f"{P}/games?genre=action&genre=rpg&match=all&only_names=false", headers=auth)
    assert [g["id"] for g in r.json()["items"]] == [812140]


def test_search_sort_paginate(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(
        f"{P}/games?search=assassin&sort=playtime&page_size=2&only_names=false", headers=auth
    )
    body = r.json()
    assert body["page"] == {"page": 1, "page_size": 2, "total": 3, "pages": 2}
    assert [g["id"] for g in body["items"]] == [812140, 242050]


def test_game_detail_with_similar(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(f"{P}/games/242050", headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["name"].startswith("Assassin's Creed")
    similar_ids = [s["id"] for s in body["similar_to"]]
    assert similar_ids[:2] == [289650, 812140]
    assert set(body["similar_to"][0]) == {"id", "name", "description"}
    assert 242050 not in similar_ids


def test_similar_endpoint_and_limit(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(f"{P}/games/620/similar?limit=1", headers=auth)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == 400
    assert items[0]["name"] == "Portal"


def test_game_not_owned(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(f"{P}/games/1", headers=auth)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "game_not_found"


def test_genres(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(f"{P}/genres", headers=auth)
    items = {g["name"]: g["game_count"] for g in r.json()["items"]}
    assert items["Action"] == 6
    assert items["Casual"] == 1

    r = client.get(f"{P}/genres/fps/games?only_names=false", headers=auth)
    assert [g["id"] for g in r.json()["items"]] == [730]


def test_groups(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(f"{P}/groups", headers=auth)
    groups = {g["name"]: g["size"] for g in r.json()["groups"]}
    assert groups == {"Assassin's Creed": 3, "Portal": 2}

    r = client.get(f"{P}/groups?by=developer", headers=auth)
    assert {g["name"] for g in r.json()["groups"]} == {"Valve"}


def test_store_failure_degrades_gracefully(
    client: TestClient, steam_mock: respx.MockRouter, auth: dict[str, str]
) -> None:
    steam_mock["items"].mock(return_value=httpx.Response(503))
    r = client.get(f"{P}/games", headers=auth)
    assert r.status_code == 200
    assert r.json()["library"]["metadata_missing"] == len(LIBRARY)


def test_validation_error_shape(client: TestClient, auth: dict[str, str]) -> None:
    r = client.get(f"{P}/games?page=0", headers=auth)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"
