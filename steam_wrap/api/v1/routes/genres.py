"""Genres present in the user's library."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Path, Query

from steam_wrap.api.v1.deps import AUTH_RESPONSES, LibraryDep, MatcherDep, PaginationDep, TokenDep
from steam_wrap.api.v1.routes.games import (
    OnlyNamesQuery,
    OrderQuery,
    SearchQuery,
    SortQuery,
    build_game_list,
)
from steam_wrap.schemas import GameListResponse, GenreListResponse

router = APIRouter(prefix="/genres", tags=["genres"])


@router.get(
    "",
    response_model=GenreListResponse,
    responses=AUTH_RESPONSES,
    summary="Genres in the library with game counts",
)
async def list_genres(
    token: TokenDep,
    library_service: LibraryDep,
    matcher: MatcherDep,
    scope: Annotated[
        Literal["genres", "tags", "all"],
        Query(description="`genres`: Steam top-level genres, `tags`: all community tags"),
    ] = "genres",
) -> GenreListResponse:
    """Counts games per genre (or tag), most common first. Also returns the alias
    table so clients know which friendly words `?genre=` accepts."""
    library = await library_service.get_library(token)
    return GenreListResponse(
        scope=scope,
        library=library.info(),
        aliases=matcher.aliases,
        items=matcher.count(library.games, scope),
    )


@router.get(
    "/{genre}/games",
    response_model=GameListResponse,
    responses=AUTH_RESPONSES,
    summary="Games in one genre",
)
async def games_in_genre(
    genre: Annotated[str, Path(max_length=100, examples=["action"])],
    token: TokenDep,
    library_service: LibraryDep,
    matcher: MatcherDep,
    pagination: PaginationDep,
    search: SearchQuery = None,
    sort: SortQuery = "name",
    order: OrderQuery = None,
    only_names: OnlyNamesQuery = True,
) -> GameListResponse:
    """Shortcut for `GET /games?genre={genre}`."""
    library = await library_service.get_library(token)
    return build_game_list(
        library,
        matcher,
        pagination,
        genres=[genre],
        match="any",
        search=search,
        sort=sort,
        order=order,
        only_names=only_names,
    )
