"""OpenAPI / Swagger UI configuration.

Everything that shapes the interactive docs lives here so ``main.py`` stays
about wiring. FastAPI serves:

* ``/docs``          Swagger UI (try requests in the browser)
* ``/redoc``         ReDoc (read-only reference)
* ``/openapi.json``  the raw OpenAPI 3.1 schema (for client generators, Postman, …)

All three can be disabled with ``app.docs_enabled: false``.
"""

from __future__ import annotations

from typing import Any

DESCRIPTION = """
Read-only wrapper around the **Steam Web API**. Send a user's Steam access token
and get their library, enriched with genres, tags, developers, publishers and
franchise data, plus similar-game discovery.

## Using this page (Swagger UI)

1. **Get a Steam access token.** Log in at
   [store.steampowered.com](https://store.steampowered.com), then open
   [`/pointssummary/ajaxgetasyncconfig`](https://store.steampowered.com/pointssummary/ajaxgetasyncconfig)
   and copy `data.webapi_token`.
2. Click **Authorize** (top right) and paste the token. Don't type `Bearer `;
   Swagger adds it. The token is kept across page reloads until you log out.
3. Open any endpoint and press **Execute**. A good first call is `GET /api/v1/me`.

## What you can do

| Goal | Call |
|---|---|
| Whole library | `GET /api/v1/games` |
| Filter by genre | `GET /api/v1/games?genre=action&genre=shooting` (any of) or add `&match=all` |
| Games like one you own | `GET /api/v1/games/{appid}` → `similar_to` |
| Library grouped into series | `GET /api/v1/groups?by=franchise` |
| Which genres are available | `GET /api/v1/genres` |
| List every endpoint (machine-readable) | `GET /api/v1` |

## Authentication

Send `Authorization: Bearer <steam_access_token>` with every request except
`/api/v1` and `/api/v1/health`. When the server enables it
(`app.allow_query_token`), `?access_token=<token>` also works. That is handy
for quick browser tests but should be disabled in production.

## Errors

Every error uses the same envelope, and `request_id` is also returned in the
`X-Request-ID` header:

```json
{"error": {"code": "invalid_token", "message": "Token expired.", "request_id": "2f6c..."}}
```
"""

TAGS_METADATA: list[dict[str, Any]] = [
    {
        "name": "meta",
        "description": "Service discovery and liveness. **No token required.**",
    },
    {
        "name": "user",
        "description": "Who the access token belongs to.",
    },
    {
        "name": "games",
        "description": "The user's owned and playable games: list, filter by genre, search, "
        "sort, paginate, and get similar games from the same library.",
    },
    {
        "name": "genres",
        "description": "Genres and tags present in the library. `?genre=` accepts genre names, "
        "tag names and friendly aliases such as `shooting`, all case-insensitive.",
    },
    {
        "name": "groups",
        "description": "The library clustered by franchise, genre or developer.",
    },
]

SWAGGER_UI_PARAMETERS: dict[str, Any] = {
    "persistAuthorization": True,  # keep the token after a page refresh
    "tryItOutEnabled": True,  # Execute buttons ready without an extra click
    "displayRequestDuration": True,
    "filter": True,  # search box for operations
    "docExpansion": "list",
    "defaultModelsExpandDepth": 0,  # schemas section collapsed
    "syntaxHighlight": {"theme": "obsidian"},
}

CONTACT: dict[str, str] = {"name": "Steam Wrap API"}
LICENSE_INFO: dict[str, str] = {"name": "MIT", "identifier": "MIT"}
