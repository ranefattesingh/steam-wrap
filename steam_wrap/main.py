"""Application factory.

``create_app()`` wires configuration, logging, middleware, error handlers and
routers. Long-lived resources (HTTP connection pool, cache, services) are
created in the lifespan handler and stored on ``app.state``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import RedirectResponse

from steam_wrap import __version__
from steam_wrap.api.openapi import (
    CONTACT,
    DESCRIPTION,
    LICENSE_INFO,
    SWAGGER_UI_PARAMETERS,
    TAGS_METADATA,
)
from steam_wrap.api.v1 import api_router
from steam_wrap.api.v1.routes import meta
from steam_wrap.cache import MemoryTTLCache
from steam_wrap.clients import SteamClient
from steam_wrap.core.config import Settings, get_settings
from steam_wrap.core.exceptions import register_exception_handlers
from steam_wrap.core.logging import configure_logging
from steam_wrap.core.middleware import RequestContextMiddleware
from steam_wrap.services import GenreMatcher, LibraryService, SimilarityService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.app.log_level, settings.app.log_json)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        steam = settings.steam
        http = httpx.AsyncClient(
            timeout=httpx.Timeout(steam.timeout_seconds),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            headers={"User-Agent": f"steam-wrap/{__version__}", "Accept": "application/json"},
            follow_redirects=True,
        )
        cache = MemoryTTLCache(settings.cache.max_entries)
        client = SteamClient(steam, http)

        app.state.settings = settings
        app.state.cache = cache
        app.state.library_service = LibraryService(client, cache, settings)
        app.state.similarity_service = SimilarityService(settings.similarity)
        app.state.genre_matcher = GenreMatcher(settings.genres)
        try:
            yield
        finally:
            await http.aclose()

    docs_on = settings.app.docs_enabled
    app = FastAPI(
        title=settings.app.name,
        version=__version__,
        summary="Steam library, genre filtering and similar-game discovery.",
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        contact=CONTACT,
        license_info=LICENSE_INFO,
        swagger_ui_parameters=SWAGGER_UI_PARAMETERS,
        debug=settings.app.debug,
        lifespan=lifespan,
        # Setting the schema URL to None disables /docs and /redoc too.
        openapi_url="/openapi.json" if docs_on else None,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = settings

    # Middleware (last added runs first).
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origins,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(meta.router, prefix=settings.app.api_prefix)
    app.include_router(api_router, prefix=settings.app.api_prefix)

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        """Send browsers to Swagger UI, or to the JSON index when docs are off."""
        return RedirectResponse(url="/docs" if docs_on else settings.app.api_prefix)

    return app
