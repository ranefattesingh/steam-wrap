"""Aggregates all v1 routers.

The index route (``GET /api/v1``) is mounted separately in ``main.py``
because FastAPI needs a non-empty prefix for an empty path.
"""

from fastapi import APIRouter

from steam_wrap.api.v1.routes import games, genres, groups, health, me

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(me.router)
api_router.include_router(games.router)
api_router.include_router(genres.router)
api_router.include_router(groups.router)
