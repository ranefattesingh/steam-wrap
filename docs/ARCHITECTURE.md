# Architecture

## Layers

```
HTTP request
   │
   ▼
steam_wrap/core/middleware.py   request ID, access log (path only, no query string)
   │
   ▼
steam_wrap/api/openapi.py       Swagger/ReDoc description, tag docs, UI settings
steam_wrap/api/v1/routes/*      thin handlers: parse params → call services → return schemas
   │  deps.py                   token extraction/decoding, pagination, service lookup
   ▼
steam_wrap/services/*           business logic (pure Python, no FastAPI imports)
   │  library_service.py        load + enrich + cache the library
   │  genre_service.py          genre matching, filtering, sorting, paging
   │  similarity_service.py     similarity scoring and grouping
   │  text.py                   title tokenisation / series heuristic
   ▼
steam_wrap/clients/steam_client.py   HTTP transport to Steam, retries, error mapping
steam_wrap/cache/memory.py           TTL + LRU cache behind a CacheBackend protocol
```

`core/` holds the config, logging, security (token decoding) and exception
handlers. `schemas/` holds the Pydantic models that define the public
contract and the OpenAPI docs.

Long-lived objects (the httpx connection pool, cache and services) are built
once in the lifespan handler in `main.py` and stored on `app.state`. Routes
get them through dependencies in `deps.py`.

## Upstream Steam endpoints

| Endpoint | Used for | Auth |
|---|---|---|
| `IPlayerService/GetOwnedGames/v1` | The library (owned games plus playable free games) | user token |
| `ISteamUser/GetPlayerSummaries/v2` | `/me` profile | user token, or `steam.api_key` if set |
| `IStoreBrowseService/GetItems/v1` | Tags, developers, publishers, **franchises**, assets, release date, platforms. Takes up to 50 apps per call. | public |
| `IStoreService/GetTagList/v1` | Tag ID → name | public |

`GetItems` is used instead of the older `store.steampowered.com/api/appdetails`.
`appdetails` only takes one app per call and is limited to roughly 200 calls
per 5 minutes, which is unusable for large libraries. `GetItems` also returns
Steam's own franchise data, which drives the similarity ranking.

## Request flow: `GET /games?genre=shooting`

1. `deps.get_token` reads the bearer token and decodes the JWT payload
   locally to get the SteamID (`sub`) and expiry. The **signature is not
   verified**, because Steam's keys aren't public. Steam validates the token
   when it is used upstream.
2. `LibraryService.get_library` checks the cache key `library:<sha256(token)>`.
   * On a cache miss it calls `GetOwnedGames`, then loads per-app store
     metadata and the tag list concurrently.
   * Store metadata is looked up per app (`store:<appid>`). Missing apps are
     fetched in batches of `store_batch_size`, with up to
     `store_max_concurrency` batches in flight.
   * Concurrent requests for the same token share one in-flight load.
3. `genre_service.filter_games` expands `shooting` through the alias table
   and matches it against each game's normalised tags and genres.
4. The results are sorted, paginated and serialised.

## Caching

| Key | Value | TTL (default) | Shared across users? |
|---|---|---|---|
| `library:<sha256(token)>` | Enriched library | 10 min | No |
| `profile:<sha256(token)>` | Profile | 5 min | No |
| `store:<appid>` | Store item, or an "unavailable" marker | 24 h | Yes (public data) |
| `tags:list` | Tag dictionary | 24 h | Yes |

* User data is keyed by the **token hash**, not the SteamID. Tokens aren't
  verified locally, so keying by SteamID would let a forged token that claims
  someone else's SteamID read that user's cached library.
* Store batch failures are **not** cached. Those games come back with
  `metadata_available=false` and are retried on the next library load.
* The cache is per process. To run several workers or replicas with a shared
  cache, implement the `CacheBackend` protocol (`get`/`set`/`delete`/`clear`)
  on Redis and pass it in `main.py`. Values would then need to be serialised
  (e.g. `model_dump_json`).

## Similarity

Steam has no "similar games" API. `SimilarityService` scores each candidate
in the user's library against the target game:

```
score = Σ wᵢ·signalᵢ / Σ wᵢ
```

| Signal | Value | Default weight |
|---|---|---|
| franchise | 1 if the games share an official Steam franchise. If either game has no franchise data, 1 if the titles look like the same series. | 0.40 |
| tags | Jaccard overlap of the top `top_tags` tags, ignoring `ignored_tags` | 0.30 |
| genres | Jaccard overlap of the top-level genres | 0.15 |
| developer | 1 if any developer is shared | 0.10 |
| publisher | 1 if any publisher is shared | 0.05 |

The **title-series heuristic** (`services/text.py`) normalises titles by
stripping ™/®, apostrophes and stopwords, then treats two titles as the same
series when:

* they share at least 2 leading words (*Dark Souls* / *Dark Souls III*), or
* they share 1 leading word and one title is only that word plus sequel
  numbers (*Portal* / *Portal 2*, *The Witcher 2* / *The Witcher 3*).

All weights and thresholds are in `config.yaml` under `similarity`.

**Grouping** (`/groups?by=franchise`) runs union-find over games linked by
official franchise names or the title heuristic. Title comparisons only
happen between games that share a first word, so the cost stays close to
linear.

## Resilience

* httpx uses a shared pool and per-request timeouts (`steam.timeout_seconds`).
* Responses with status 429, 500, 502, 503 or 504, and transport errors, are
  retried with exponential backoff (`max_retries`, `retry_backoff_seconds`).
* 401/403 from Steam map to `401 steam_auth_failed`. Other failures map to
  `502`/`503` with the common error envelope.
* A failing metadata batch or tag list degrades the response instead of
  failing it.

## API documentation

* FastAPI generates the OpenAPI 3.1 schema from the route signatures and the
  Pydantic models in `schemas/`, so the docs can't drift from the code.
  Field `examples` and descriptions appear in Swagger.
* `api/openapi.py` holds the long description (with the Swagger how-to), the
  tag descriptions and the Swagger UI settings: `persistAuthorization`,
  `tryItOutEnabled`, the operation filter and request durations.
* The Bearer security scheme (`SteamAccessToken`, defined in `deps.py`)
  produces the **Authorize** button, and authenticated operations show a lock
  icon. The `?access_token=` fallback is left out of the schema on purpose,
  so Swagger has only one way to send credentials.
* `GET /api/v1` builds its endpoint list from `app.openapi()`. That call is
  cached and works even when `/openapi.json` is disabled.

## Security

* Tokens are never logged. `RedactingFilter` masks `access_token=`, `key=`
  and `Bearer` values in every log record, including uvicorn's. httpx is
  kept at WARNING because it logs full URLs at INFO.
* The `?access_token=` fallback can be turned off
  (`STEAMWRAP_APP__ALLOW_QUERY_TOKEN=false`), and should be in production.
* CORS only allows `GET`/`OPTIONS`. Set `app.cors_origins` to your frontend.
* The container runs as a non-root user.

## Testing

`tests/` mocks every Steam endpoint with `respx`, so the suite runs offline
with fake JWTs:

* `test_api.py`: end-to-end route behaviour, caching, degraded mode and error envelopes
* `test_text_and_similarity.py`: series heuristic, genre matching, ranking and grouping
* `test_security.py`: token decoding and log redaction
* `test_cache.py`: TTL and LRU behaviour
