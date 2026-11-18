"""Liveness endpoint (no authentication)."""

from fastapi import APIRouter

from steam_wrap import __version__
from steam_wrap.api.v1.deps import SettingsDep
from steam_wrap.schemas import HealthResponse

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def health(settings: SettingsDep) -> HealthResponse:
    """Returns 200 while the process is up. Does not call Steam."""
    return HealthResponse(status="ok", version=__version__, environment=settings.app.environment)
