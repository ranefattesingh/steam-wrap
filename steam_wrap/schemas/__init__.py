"""Pydantic models that define the public API contract."""

from steam_wrap.schemas.common import ErrorResponse, HealthResponse, Page
from steam_wrap.schemas.game import (
    Game,
    GameDetail,
    GameGroup,
    GameListResponse,
    GameRef,
    GroupsResponse,
    LibraryInfo,
    Platforms,
    SimilarGamesResponse,
)
from steam_wrap.schemas.genre import GenreCount, GenreListResponse
from steam_wrap.schemas.meta import ApiIndex, ApiLinks, AuthInfo, EndpointInfo
from steam_wrap.schemas.user import MeResponse, PlayerProfile

__all__ = [
    "ApiIndex",
    "ApiLinks",
    "AuthInfo",
    "EndpointInfo",
    "ErrorResponse",
    "Game",
    "GameDetail",
    "GameGroup",
    "GameListResponse",
    "GameRef",
    "GenreCount",
    "GenreListResponse",
    "GroupsResponse",
    "HealthResponse",
    "LibraryInfo",
    "MeResponse",
    "Page",
    "Platforms",
    "PlayerProfile",
    "SimilarGamesResponse",
]
