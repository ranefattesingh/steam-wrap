# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A read-only (all `GET`) FastAPI wrapper around the Steam Web API. A client sends a user's Steam access token (a JWT from `store.steampowered.com/pointssummary/ajaxgetasyncconfig`) and gets their library, genre filtering, similar-game ranking and franchise/genre/developer grouping. Python ≥3.11.

## Commands

All Make targets use `.venv/bin/python`.

```bash
make install     # create .venv, install -e ".[dev]" (uv if available, else pip)
make run         # uvicorn app:app --reload on :8000 (Swagger at /docs)
make test        # pytest
make lint        # ruff check + ruff format --check + mypy --strict (steam_wrap, app.py)
make format      # ruff format + ruff check --fix
make web         # frontend dev server on :5173 (Vite proxies /api → :8000)
make web-build   # vue-tsc type-check + vite build
```

`requirements.txt` / `requirements-dev.txt` are pinned exports of `pyproject.toml`; regenerate them when dependencies change.

## Frontend (`frontend/`)

Vue 3 + Vite + TypeScript, Tailwind v4, shadcn-vue (reka-ui) components in `src/components/ui` (generated; add more with `pnpm dlx shadcn-vue@latest add <name>`). Use pnpm. `src/lib/api.ts` is the typed API client; `src/composables/useLibrary.ts` holds state. `fetchAllGames` walks every `/games` page at the server's max page size (no client-side limit). Sort/order/genre/match are applied server-side (changing them refetches); name search, grouping (`/groups?min_size=1` intersected with the filtered list) and min group size are client-side. The token is kept in memory only and sent as a Bearer header, never in the URL.

Single test: `.venv/bin/python -m pytest tests/test_api.py::test_name` (or `-k pattern`).

Tests run fully offline: `tests/conftest.py` mocks every Steam endpoint with `respx` against a fixed fake `LIBRARY`, mints unsigned fake JWTs via `make_token()`, and builds the app with `create_app(settings)`. Use the `client`, `auth` and `steam_mock` fixtures; add new fake games to `LIBRARY`/`TAGS` in conftest rather than ad-hoc mocks. `asyncio_mode = "auto"`. mypy is strict but excludes `tests/`.

## Architecture

Full design notes live in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md); API reference in [docs/API.md](docs/API.md). Key points:

- **Layering:** `api/v1/routes/*` are thin handlers → `services/*` (pure Python, **no FastAPI imports**) → `clients/steam_client.py` (httpx, retries, error mapping) + `cache/memory.py`. `schemas/` Pydantic models are the public contract and drive the OpenAPI docs.
- **App wiring:** `steam_wrap/main.py:create_app(settings)` builds long-lived objects (httpx pool, cache, services) in the lifespan handler and stores them on `app.state`; routes get them through `Annotated` dependency aliases in `api/v1/deps.py` (`TokenDep`, `LibraryDep`, `SimilarityDep`, `PaginationDep`, …). `app.py` only exposes `app = create_app()`.
- **Auth:** `core/security.py` decodes the JWT payload locally for SteamID/expiry **without verifying the signature** (Steam's keys aren't public; Steam validates upstream). Consequently, per-user cache keys are `library:<sha256(token)>` / `profile:<sha256(token)>` — never key user data by SteamID. Store/tag data (`store:<appid>`, `tags:list`) is public and shared.
- **Library loading:** `GetOwnedGames`, then store metadata via `IStoreBrowseService/GetItems` in batches (not the legacy `appdetails` endpoint — rate limits). Concurrent loads for the same token are de-duplicated. Failed metadata batches degrade (`metadata_available=false`) and are not cached.
- **Similarity:** weighted score over franchise / tags (Jaccard) / genres / developer / publisher; title-series heuristic in `services/text.py` is the fallback when franchise data is missing. Candidates come only from the user's own library. Weights/thresholds are in `config.yaml` under `similarity`.
- **Cache:** per-process TTL+LRU behind a `CacheBackend` protocol (`get`/`set`/`delete`/`clear`); a shared backend (e.g. Redis) would plug in at `main.py`.
- **OpenAPI:** `api/openapi.py` holds the long description, tag docs and Swagger UI settings. `GET /api/v1` builds its endpoint index from `app.openapi()`. `tests/test_docs.py` asserts on tag order, the `SteamAccessToken` bearer scheme and route parameters — update it when adding tags/params. The `?access_token=` fallback is intentionally excluded from the schema.

## Configuration

Defaults in `config.yaml` (documented inline). Overrides via env/`.env` with `STEAMWRAP_` prefix and `__` nesting (e.g. `STEAMWRAP_SIMILARITY__WEIGHTS__FRANCHISE=0.5`). Priority: env > `.env` > `config.yaml` > code defaults (`core/config.py`). `STEAMWRAP_CONFIG_FILE` points at an alternate YAML.

## Security conventions

- Never log tokens. `core/logging.py`'s `RedactingFilter` masks `access_token=`, `key=` and `Bearer` values; the access-log middleware logs path only (no query string); httpx is held at WARNING because it logs full URLs at INFO. Preserve these when touching logging.
- CORS allows only `GET`/`OPTIONS`.
