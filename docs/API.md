# API reference (v1)

Base URL: `http://localhost:8000/api/v1`. All endpoints are `GET`.
Interactive docs: `/docs` (Swagger UI, use **Authorize** to set your token) and `/redoc`.
The schema is at `/openapi.json`. All three can be disabled with `app.docs_enabled: false`.

Authenticated endpoints need `Authorization: Bearer <steam_access_token>`
(see [STEAM_TOKEN.md](STEAM_TOKEN.md)).

```bash
export TOKEN="eyJhbGciOi..."
alias api='curl -s -H "Authorization: Bearer $TOKEN"'
```

| Method & path | Auth | Description |
|---|---|---|
| `GET /` | – | Redirect to `/docs` (or to `/api/v1` when docs are off) |
| `GET /api/v1` | – | API index: endpoints, docs links, auth instructions |
| `GET /health` | – | Liveness check |
| `GET /me` | ✔ | SteamID, token expiry, public profile |
| `GET /games` | ✔ | Owned/playable game names (or `{id, name, description}` with `only_names=false`), with filters, search, sorting and paging |
| `GET /games/{appid}` | ✔ | Full details of one game plus `similar_to` |
| `GET /games/{appid}/similar` | ✔ | Ranked similar games only |
| `GET /genres` | ✔ | Genre/tag counts across the library |
| `GET /genres/{genre}/games` | ✔ | Games in one genre |
| `GET /groups` | ✔ | Library clustered by franchise, genre or developer |

---

## `GET /api/v1` (index)

A public entry point for clients and humans. The endpoint list is generated
from the OpenAPI schema, so it always matches what is deployed.

```json
{
  "name": "Steam Wrap API",
  "version": "1.0.0",
  "links": {"swagger_ui": "/docs", "redoc": "/redoc", "openapi_schema": "/openapi.json"},
  "auth": {
    "header": "Authorization: Bearer <steam_access_token>",
    "query_parameter": "access_token",
    "how_to_get_token": "Log in at https://store.steampowered.com, open ... and copy data.webapi_token."
  },
  "endpoints": [
    {"method": "GET", "path": "/api/v1/games", "summary": "List owned / playable games", "tags": ["games"], "requires_token": true}
  ]
}
```

`links.*` are `null` when docs are disabled. `auth.query_parameter` is `null`
when query-string tokens are disabled.

## `GET /health`

```json
{"status": "ok", "version": "1.0.0", "environment": "production"}
```

## `GET /me`

```json
{
  "steamid": "76561198000000000",
  "token_expires_at": "2026-11-19T10:00:00Z",
  "profile": {"persona_name": "gamer", "profile_url": "...", "avatar_url": "...", "country_code": "US"}
}
```

`profile` is `null` if Steam won't return it.

## `GET /games`

Returns every game the user **owns or can play**. That includes free-to-play
games they have added or played (`include_played_free_games` and
`include_free_sub`).

| Query | Default | Notes |
|---|---|---|
| `genre` | – | Repeatable. Matches genres **and** tags, ignoring case and punctuation. Aliases apply (e.g. `shooting` → Shooter, FPS, …). |
| `match` | `any` | `any` = at least one genre, `all` = every genre |
| `search` | – | Substring of the game name |
| `sort` | `name` | `name`, `playtime`, `last_played`, `release_date` |
| `order` | auto | `asc` for name, otherwise `desc`. Missing values always sort last. |
| `page`, `page_size` | 1, 50 | `page_size` is capped by `pagination.max_page_size` |
| `refresh` | `false` | Bypass the library cache |
| `only_names` | `true` | `true`: `items` is a plain array of names. `false`: each item is `{id, name, description}`. |

### Default: `only_names=true`

```bash
api 'localhost:8000/api/v1/games?genre=action&genre=shooting&sort=playtime&page_size=5'
```

```json
{
  "library": {"steamid": "7656...", "total_games": 412, "metadata_missing": 3, "fetched_at": "..."},
  "page": {"page": 1, "page_size": 5, "total": 37, "pages": 8},
  "filters": {"sort": "playtime", "order": "desc", "genre": ["action", "shooting"], "match": "any"},
  "only_names": true,
  "items": ["Counter-Strike 2", "Apex Legends", "Borderlands 2", "DOOM", "Titanfall 2"]
}
```

`page.total` is the number of games matching the filters, and
`library.total_games` is the size of the whole library.

### With ids and descriptions: `only_names=false`

```bash
api 'localhost:8000/api/v1/games?genre=action&genre=shooting&sort=playtime&page_size=5&only_names=false'
```

```json
{
  "library": {"...": "..."},
  "page": {"page": 1, "page_size": 5, "total": 37, "pages": 8},
  "filters": {"...": "..."},
  "only_names": false,
  "items": [
    {"id": 730, "name": "Counter-Strike 2", "description": "For over two decades, Counter-Strike has offered..."},
    {"id": 1172470, "name": "Apex Legends", "description": "Apex Legends is the award-winning, free-to-play Hero Shooter..."}
  ]
}
```

`id` is the Steam app id: pass it to `GET /games/{id}` for everything
else (genres, tags, playtime, images, platforms, similar games).
`description` is `null` when Steam's store has no data for the app (delisted,
or a temporary Steam error). Such games are still listed, but genre filters
skip them because their genres are unknown.

## `GET /games/{appid}`

Full details for one game. The list endpoints return only names (or `{id, name, description}` with `only_names=false`).

| Query | Default | Notes |
|---|---|---|
| `similar_limit` | 10 | `0` omits `similar_to`. Capped by `similarity.max_limit`. |
| `min_score` | 0.2 | 0..1 |

```bash
api localhost:8000/api/v1/games/242050      # Assassin's Creed IV Black Flag
```

```json
{
  "appid": 242050,
  "name": "Assassin's Creed® IV Black Flag™",
  "playtime_minutes": 1830,
  "playtime_2weeks_minutes": 0,
  "last_played_at": "2026-10-02T19:12:45Z",
  "genres": ["Action", "Adventure"],
  "tags": ["Pirates", "Open World", "Naval", "Action", "Adventure", "..."],
  "franchises": ["Assassin's Creed"],
  "developers": ["Ubisoft Montreal"],
  "publishers": ["Ubisoft"],
  "short_description": "Discover Assassin's Creed IV Black Flag, the classic pirate action-adventure game...",
  "is_free": false,
  "release_date": "2013-11-19",
  "platforms": {"windows": true, "mac": false, "linux": false, "steam_deck": "playable"},
  "icon_url": "https://media.steampowered.com/steamcommunity/public/images/apps/242050/....jpg",
  "header_image_url": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/242050/header.jpg?t=...",
  "store_url": "https://store.steampowered.com/app/242050/Assassins_Creed_IV_Black_Flag",
  "metadata_available": true,
  "similar_to": [
    {"id": 289650, "name": "Assassin's Creed® Unity", "description": "Paris, 1789. In this action-adventure game..."},
    {"id": 812140, "name": "Assassin's Creed® Odyssey", "description": "Choose your fate in Assassin's Creed® Odyssey..."}
  ]
}
```

`similar_to` is ordered best match first. Ranking uses franchise, shared
genres and tags, developer and publisher (see
[ARCHITECTURE.md](ARCHITECTURE.md#similarity)). The scores themselves aren't
returned.

Similar games always come from the **user's own library**. The game must be
owned, otherwise you get `404 game_not_found`.

## `GET /games/{appid}/similar`

Same ranking without the game details. Query: `limit`, `min_score`.

```json
{
  "appid": 242050,
  "name": "Assassin's Creed® IV Black Flag™",
  "items": [
    {"id": 289650, "name": "Assassin's Creed® Unity", "description": "..."},
    {"id": 812140, "name": "Assassin's Creed® Odyssey", "description": "..."}
  ]
}
```

## `GET /genres`

| Query | Default | Notes |
|---|---|---|
| `scope` | `genres` | `genres` = Steam top-level genres, `tags` = all community tags, `all` = both |

```json
{
  "scope": "genres",
  "library": {"...": "..."},
  "aliases": {"shooting": ["Shooter", "FPS", "..."], "...": []},
  "items": [
    {"name": "Action", "game_count": 211, "is_primary": true},
    {"name": "Adventure", "game_count": 160, "is_primary": true}
  ]
}
```

## `GET /genres/{genre}/games`

Equivalent to `GET /games?genre={genre}`. Accepts `search`, `sort`, `order`,
`page`, `page_size` and `only_names` (default `true`), with the same response shape as `/games`.

```bash
api localhost:8000/api/v1/genres/casual/games
```

## `GET /groups`

| Query | Default | Notes |
|---|---|---|
| `by` | `franchise` | `franchise`, `genre` (groups overlap), `developer` |
| `min_size` | 2 | Smallest group returned |

```json
{
  "by": "franchise",
  "library": {"...": "..."},
  "groups": [
    {"name": "Assassin's Creed", "size": 3, "games": [{"id": 812140, "name": "Assassin's Creed® Odyssey", "description": "..."}]},
    {"name": "Portal", "size": 2, "games": ["..."]}
  ]
}
```

---

## Errors

Every non-2xx response uses the same envelope. `request_id` also comes back
in the `X-Request-ID` response header.

```json
{"error": {"code": "invalid_token", "message": "Access token has expired.", "request_id": "2f6c..."}}
```

| HTTP | `code` | When |
|---|---|---|
| 401 | `invalid_token` | Token missing, not a JWT, no SteamID, or expired |
| 401 | `steam_auth_failed` | Steam rejected the token (revoked or forged) |
| 404 | `game_not_found` | App not in this user's library |
| 404 | `not_found` | Unknown route |
| 422 | `validation_error` | Bad query/path parameter (`details` lists each problem) |
| 502 | `steam_unavailable` | Steam returned 5xx or garbage, or was unreachable after retries |
| 503 | `steam_rate_limited` | Steam kept returning 429 after retries |
| 500 | `internal_error` | Bug; check logs using the request ID |
