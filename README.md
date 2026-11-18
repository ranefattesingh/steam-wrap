# Steam Wrap APP

A read-only **FastAPI** wrapper around the Steam Web API. Send a user's Steam
access token and get:

* **Their whole library**: every game they own or can download and play,
  listed as plain names by default, or as `{id, name, description}` with
  `?only_names=false`. `GET /games/{id}` gives full
  details (genres, tags, developers, franchise, playtime, images, …)
* **Genre filtering**: `?genre=action`, `?genre=shooting&genre=casual`,
  `?genre=rpg&genre=action&match=all`, with friendly aliases
* **Similar games**: `GET /games/{appid}` returns the game and a ranked
  `similar_to` list of games from the same library, best match first
  (*Assassin's Creed IV Black Flag* → *Assassin's Creed Unity*,
  *Odyssey*, …)
* **Groups**: the library clustered by franchise, genre or developer

All endpoints are `GET`.

## Quickstart

```bash
make install                # creates .venv (uses uv if installed, else pip)
cp .env.example .env        # optional overrides
make run                    # http://localhost:8000/docs
```

Without make:

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/uvicorn app:app --reload
```

Or with the pinned exports: `pip install -r requirements.txt` (runtime only)
or `pip install -r requirements-dev.txt` (adds pytest, respx, ruff, mypy).
`pyproject.toml` stays the source of truth.

### Web UI

A Vue frontend in [`frontend/`](frontend/) works with your whole
library in the browser. Paste a token and click **Find** to get:

* **Search** by name
* **Sort** by name, playtime, last played or release date
* **Filter** by one or more genres or tags, matching *any* or *all*
* **Group** by franchise, genre or developer, with a minimum group size
* **Details** for each game, including similar games from your library

The UI loads every page of `GET /api/v1/games`, so there is no page-size
limit. The token stays in memory only, so reloading the page forgets it. It is
sent as an `Authorization: Bearer` header, never in a URL.

For development, with the API running (`make run`):

```bash
make web-install   # pnpm install
make web           # http://localhost:5173 (proxies /api to :8000)
make web-build     # type-check + production build into frontend/dist
```

To call a different backend, set `VITE_API_BASE_URL` at build time, for
example `VITE_API_BASE_URL=https://api.example.com pnpm build` in `frontend/`.
That origin must be allowed by the API's `app.cors_origins`. To serve a build
locally, run `pnpm preview` in `frontend/`.

To run the UI and the API together in Docker, see [Deployment](#deployment).

Get a token (see [Getting a Steam access token](#getting-a-steam-access-token)
below) and call the API:

```bash
TOKEN="eyJhbGciOi..."
curl -H "Authorization: Bearer $TOKEN" "localhost:8000/api/v1/games?genre=shooting&sort=playtime"
curl -H "Authorization: Bearer $TOKEN" "localhost:8000/api/v1/games/242050"        # + similar_to
curl -H "Authorization: Bearer $TOKEN" "localhost:8000/api/v1/groups?by=franchise"
```

## Getting a Steam access token

Every endpoint except `/api/v1` and `/api/v1/health` needs the user's Steam
access token. The easiest way to get one is from the Steam store in your
browser:

1. Log in at <https://store.steampowered.com>.
2. In the same browser, open
   <https://store.steampowered.com/pointssummary/ajaxgetasyncconfig>.
3. The page shows JSON like this:
   ```json
   {"success":1,"data":{"webapi_token":"eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJpc3Mi..."}}
   ```
4. Copy the `webapi_token` value. That's your access token.

To use it:

* **Swagger UI:** open <http://localhost:8000/docs>, click **Authorize** and
  paste the token without `Bearer `.
* **curl / HTTP clients:** send `Authorization: Bearer <token>`:
  ```bash
  curl -H "Authorization: Bearer eyJhbGciOi..." localhost:8000/api/v1/me
  ```

Some things to know:

* **It expires after about 24 hours.** When calls start returning
  `401 invalid_token` or `steam_auth_failed`, repeat step 2 to get a new one.
* **It's a credential for your Steam account,** so treat it like a password:
  don't commit it or paste it publicly. The API never logs it.
* **An empty library usually means a privacy setting.** In your Steam
  profile's Privacy Settings, set **Game details** to Public.
* **For other users:** an app serving other people would get each user's token
  from its own Steam sign-in flow instead of copying it by hand.

More detail is in [docs/STEAM_TOKEN.md](docs/STEAM_TOKEN.md).

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/v1` | API index: every endpoint, docs links, how to authenticate (no token) |
| `GET /api/v1/health` | Liveness check |
| `GET /api/v1/me` | SteamID, token expiry and profile |
| `GET /api/v1/games` | Library as names (`only_names=true`, default) or `{id, name, description}`, with `genre`, `match`, `search`, `sort`, `order`, `page`, `page_size`, `refresh`, `only_names` |
| `GET /api/v1/games/{appid}` | Full game details plus `similar_to` |
| `GET /api/v1/games/{appid}/similar` | Similar games only |
| `GET /api/v1/genres` | Genre/tag counts in the library |
| `GET /api/v1/genres/{genre}/games` | Games in a genre |
| `GET /api/v1/groups` | Groups by `franchise`, `genre` or `developer` |

Full reference with examples: [docs/API.md](docs/API.md).

## Interactive documentation (Swagger)

| URL | What |
|---|---|
| `/docs` | **Swagger UI**: try every endpoint from the browser |
| `/redoc` | ReDoc: readable reference |
| `/openapi.json` | OpenAPI 3.1 schema, for Postman, Insomnia or client generators |
| `/` | Redirects to `/docs` |

To use Swagger UI:

1. Open <http://localhost:8000/docs>.
2. Click **Authorize** and paste your Steam access token (without `Bearer `).
   It stays saved across page reloads.
3. Expand an endpoint, fill in the parameters and press **Execute**.

Set `STEAMWRAP_APP__DOCS_ENABLED=false` to turn off all three docs URLs in
production. `GET /api/v1` keeps working either way.

To generate a typed client from the schema, for example in TypeScript:

```bash
npx openapi-typescript http://localhost:8000/openapi.json -o steam-wrap.d.ts
```

## Configuration

Defaults are in [config.yaml](config.yaml), and every value is documented
inline. Override any value with environment variables (or `.env`) using the
`STEAMWRAP_` prefix and `__` for nesting:

```bash
STEAMWRAP_APP__LOG_JSON=true
STEAMWRAP_APP__ALLOW_QUERY_TOKEN=false
STEAMWRAP_CACHE__LIBRARY_TTL_SECONDS=120
STEAMWRAP_SIMILARITY__WEIGHTS__FRANCHISE=0.5
STEAMWRAP_CONFIG_FILE=/etc/steam-wrap/config.yaml
```

Priority: environment > `.env` > `config.yaml` > code defaults.

Settings you will most likely change:

| Setting | Why |
|---|---|
| `genres.aliases` | Map your own query words to Steam tags |
| `similarity.weights`, `min_score`, `ignored_tags` | Tune what counts as similar |
| `cache.*_ttl_seconds` | Trade freshness against Steam calls |
| `app.cors_origins`, `app.allow_query_token`, `app.docs_enabled` | Production hardening |

## Project layout

```
app.py                      ASGI entrypoint (uvicorn app:app)
config.yaml                 default configuration
steam_wrap/
  main.py                   app factory, lifespan, middleware
  core/                     config, logging (with secret redaction), security, errors, middleware
  clients/steam_client.py   Steam Web API client with retries
  cache/memory.py           TTL+LRU cache behind a pluggable protocol
  services/                 library loading, genre filtering, similarity and grouping
  schemas/                  Pydantic response models (the API contract)
  api/openapi.py            Swagger/OpenAPI description, tags and UI settings
  api/v1/                   routers and dependencies
tests/                      offline test suite (Steam mocked with respx)
frontend/                   Vue 3 + Vite + Tailwind + shadcn-vue web UI
  Dockerfile, nginx.conf    production image: static build served by nginx
  src/lib/api.ts            typed API client (+ fetchAllGames page walker)
  src/composables/          useLibrary.ts: token, filters, loading, grouping
  src/components/           TokenForm, LibraryToolbar, GenrePicker, GameList,
                            GameDetailDialog
  src/components/ui/        generated shadcn-vue components
requirements*.txt           pinned pip exports of pyproject.toml
docs/                       API reference, architecture, token guide
```

Design notes, caching and the similarity algorithm are covered in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Development

```bash
make test      # pytest
make lint      # ruff + mypy (strict)
make format    # auto-format
```

## Deployment

```bash
docker compose up --build        # web UI on :3000, API on :8080
```

Then open <http://localhost:3000> for the web UI, or
<http://localhost:8080/docs> for Swagger UI.

Compose runs two services:

| Service | Host port | What it does |
|---|---|---|
| `api` | 8080 | The FastAPI backend (port 8000 inside the container), with JSON logs and query-token auth disabled |
| `web` | 3000 | The Vue app served by nginx, which also proxies `/api`, `/docs`, `/redoc` and `/openapi.json` to `api` |

Because nginx proxies the API, the browser talks to a single origin, so no
CORS or `VITE_API_BASE_URL` setup is needed. `web` starts once the API's
health check passes. If the API should only be reachable through the UI,
remove the `ports:` entry from the `api` service.

The API image runs one uvicorn worker as a non-root user. Both images include
a health check. The cache is per process, so scale the API by adding
replicas. For a shared cache, see the Redis note in ARCHITECTURE.md.

## Limitations

* Similar games come only from the user's own library (by design).
* Steam access tokens expire after about 24h, and clients must refresh them.
* A library whose **Game details** privacy setting is not public may come
  back empty.
* Delisted apps have no store metadata (`description: null` in lists,
  `metadata_available: false` in details), so genre filters skip them.
