"""FastAPI dependencies shared by the v1 routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from steam_wrap.core.config import Settings
from steam_wrap.core.exceptions import InvalidTokenError
from steam_wrap.core.security import TokenInfo, decode_steam_token
from steam_wrap.schemas import ErrorResponse
from steam_wrap.services import GenreMatcher, LibraryService, SimilarityService

_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="SteamAccessToken",
    description="Steam user access token (JWT). See docs/STEAM_TOKEN.md.",
)

AUTH_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "Missing, invalid or expired token"},
    502: {"model": ErrorResponse, "description": "Steam returned an error"},
    503: {"model": ErrorResponse, "description": "Steam is rate limiting"},
}


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_library_service(request: Request) -> LibraryService:
    service: LibraryService = request.app.state.library_service
    return service


def get_similarity_service(request: Request) -> SimilarityService:
    service: SimilarityService = request.app.state.similarity_service
    return service


def get_genre_matcher(request: Request) -> GenreMatcher:
    matcher: GenreMatcher = request.app.state.genre_matcher
    return matcher


async def get_token(
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    access_token: Annotated[
        str | None,
        Query(
            include_in_schema=False,
            description="Alternative to the Authorization header "
            "(only when `app.allow_query_token` is enabled).",
        ),
    ] = None,
) -> TokenInfo:
    """Resolve and decode the caller's Steam access token."""
    token = credentials.credentials if credentials else None
    if token is None and access_token and settings.app.allow_query_token:
        token = access_token
    if not token:
        raise InvalidTokenError(
            "Missing access token. Send 'Authorization: Bearer <steam_access_token>'."
        )
    return decode_steam_token(token)


@dataclass(frozen=True, slots=True)
class Pagination:
    page: int
    page_size: int


def get_pagination(
    settings: Annotated[Settings, Depends(get_settings)],
    page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
    page_size: Annotated[
        int | None,
        Query(ge=1, description="Items per page (default and maximum are configurable)"),
    ] = None,
) -> Pagination:
    size = page_size or settings.pagination.default_page_size
    return Pagination(page=page, page_size=min(size, settings.pagination.max_page_size))


TokenDep = Annotated[TokenInfo, Depends(get_token)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
LibraryDep = Annotated[LibraryService, Depends(get_library_service)]
SimilarityDep = Annotated[SimilarityService, Depends(get_similarity_service)]
MatcherDep = Annotated[GenreMatcher, Depends(get_genre_matcher)]
PaginationDep = Annotated[Pagination, Depends(get_pagination)]
