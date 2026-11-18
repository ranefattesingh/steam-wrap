"""Swagger/OpenAPI documentation and the API index endpoint."""

from __future__ import annotations

import respx
from fastapi.testclient import TestClient

from steam_wrap.core.config import Settings
from steam_wrap.main import create_app


def test_swagger_and_redoc_served(client: TestClient) -> None:
    swagger = client.get("/docs")
    assert swagger.status_code == 200
    assert "swagger-ui" in swagger.text
    assert '"persistAuthorization": true' in swagger.text
    assert client.get("/redoc").status_code == 200
    assert client.get("/", follow_redirects=False).headers["location"] == "/docs"


def test_openapi_schema(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert [t["name"] for t in schema["tags"]] == ["meta", "user", "games", "genres", "groups"]
    assert schema["components"]["securitySchemes"]["SteamAccessToken"]["scheme"] == "bearer"
    assert "Authorize" in schema["info"]["description"]

    games = schema["paths"]["/api/v1/games"]["get"]
    assert games["security"] == [{"SteamAccessToken": []}]
    params = {p["name"] for p in games["parameters"]}
    assert {"genre", "match", "search", "sort", "page", "page_size"} <= params
    assert "access_token" not in params  # Authorize button is the documented path
    assert "401" in games["responses"]

    assert "security" not in schema["paths"]["/api/v1/health"]["get"]


def test_api_index(client: TestClient) -> None:
    r = client.get("/api/v1")  # public, no token
    assert r.status_code == 200
    body = r.json()
    assert body["links"] == {
        "swagger_ui": "/docs",
        "redoc": "/redoc",
        "openapi_schema": "/openapi.json",
    }
    assert body["auth"]["query_parameter"] == "access_token"
    endpoints = {(e["method"], e["path"]): e for e in body["endpoints"]}
    assert endpoints[("GET", "/api/v1/games/{appid}")]["requires_token"] is True
    assert endpoints[("GET", "/api/v1/health")]["requires_token"] is False
    assert endpoints[("GET", "/api/v1")]["requires_token"] is False
    assert len(endpoints) == 9


def test_docs_can_be_disabled(steam_mock: respx.MockRouter) -> None:
    settings = Settings(
        app={"environment": "test", "docs_enabled": False, "allow_query_token": False}
    )
    with TestClient(create_app(settings)) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/openapi.json").status_code == 404
        assert c.get("/", follow_redirects=False).headers["location"] == "/api/v1"
        body = c.get("/api/v1").json()
        assert body["links"]["swagger_ui"] is None
        assert body["auth"]["query_parameter"] is None
