"""Owned games: listing/filtering, details, and similar games."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from steam_wrap.api.v1.deps import (
    AUTH_RESPONSES,
    LibraryDep,
    MatcherDep,
    Pagination,
    PaginationDep,
    SettingsDep,
    SimilarityDep,
    TokenDep,
)
from steam_wrap.schemas import ErrorResponse, GameDetail, GameListResponse, SimilarGamesResponse
from steam_wrap.services import GenreMatcher, Library
from steam_wrap.services.genre_service import (
    SortField,
    SortOrder,
    filter_games,
    paginate,
    sort_games,
)
from steam_wrap.services.similarity_service import to_ref

router = APIRouter(prefix="/games", tags=["games"])

NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "Game not in the user's library"}
}

GenreQuery = Annotated[
    list[str],
    Query(
        description="Genre or tag to filter by; repeat for several "
        "(e.g. `?genre=action&genre=shooting`). Case-insensitive, aliases supported.",
    ),
]
MatchQuery = Annotated[
    str,
    Query(pattern="^(any|all)$", description="`any`: match at least one genre, `all`: every genre"),
]
SearchQuery = Annotated[
    str | None, Query(max_length=200, description="Case-insensitive substring of the game name")
]
SortQuery = Annotated[SortField, Query(description="Sort field")]
OrderQuery = Annotated[
    SortOrder | None,
    Query(description="Defaults to `asc` for name, `desc` for everything else"),
]
RefreshQuery = Annotated[bool, Query(description="Bypass the library cache")]
OnlyNamesQuery = Annotated[
    bool,
    Query(
        description="`true` (default): `items` is a plain array of game names. "
        "`false`: each item is `{id, name, description}`, where `id` is the Steam app id "
        "used by `GET /games/{appid}`.",
    ),
]
MinScoreQuery = Annotated[
    float | None,
    Query(ge=0, le=1, description="Minimum similarity score (default from config)"),
]
AppIdPath = Annotated[int, Path(ge=1, description="Steam app id", examples=[242050])]


def build_game_list(
    library: Library,
    matcher: GenreMatcher,
    pagination: Pagination,
    *,
    genres: list[str],
    match: str,
    search: str | None,
    sort: SortField,
    order: SortOrder | None,
    only_names: bool = True,
) -> GameListResponse:
    """Shared by ``/games`` and ``/genres/{genre}/games``."""
    games = filter_games(
        library.games, matcher, genres=genres, match_all=match == "all", search=search
    )
    games = sort_games(games, sort, order)
    items, page = paginate(games, pagination.page, pagination.page_size)
    filters: dict[str, object] = {
        "sort": sort,
        "order": order or ("asc" if sort == "name" else "desc"),
    }
    if genres:
        filters["genre"] = genres
        filters["match"] = match
    if search:
        filters["search"] = search
    return GameListResponse(
        library=library.info(),
        page=page,
        filters=filters,
        only_names=only_names,
        items=[g.name for g in items] if only_names else [to_ref(g) for g in items],
    )


@router.get(
    "",
    response_model=GameListResponse,
    responses=AUTH_RESPONSES,
    summary="List owned / playable games",
)
async def list_games(
    token: TokenDep,
    library_service: LibraryDep,
    matcher: MatcherDep,
    pagination: PaginationDep,
    genre: GenreQuery = [],  # noqa: B006 - FastAPI copies defaults per request
    match: MatchQuery = "any",
    search: SearchQuery = None,
    sort: SortQuery = "name",
    order: OrderQuery = None,
    refresh: RefreshQuery = False,
    only_names: OnlyNamesQuery = True,
) -> GameListResponse:
    """Every game the user owns or can play, including free-to-play games they've added.

    By default `items` is just an array of names (`only_names=true`). Pass
    `only_names=false` to get `{id, name, description}` per game, then use the `id`
    with `GET /games/{appid}` for full details and similar games.

    Filter by genre (`?genre=action`), several genres (`?genre=action&genre=shooting`,
    any-of by default, all-of with `match=all`) and/or a name search.
    """
    library = await library_service.get_library(token, refresh=refresh)
    return build_game_list(
        library,
        matcher,
        pagination,
        genres=genre,
        match=match,
        search=search,
        sort=sort,
        order=order,
        only_names=only_names,
    )


@router.get(
    "/{appid}",
    response_model=GameDetail,
    responses={**AUTH_RESPONSES, **NOT_FOUND},
    summary="Game details with similar games",
)
async def get_game(
    appid: AppIdPath,
    token: TokenDep,
    library_service: LibraryDep,
    similarity: SimilarityDep,
    settings: SettingsDep,
    similar_limit: Annotated[
        int | None, Query(ge=0, description="Max similar games (0 to omit)")
    ] = None,
    min_score: MinScoreQuery = None,
) -> GameDetail:
    """Full details of one owned game plus `similar_to`: the names of the other
    games in the user's library most similar to it (same franchise, shared
    genres/tags, developer, publisher), best match first.
    """
    library = await library_service.get_library(token)
    game = library.get(appid)
    limit = settings.similarity.default_limit if similar_limit is None else similar_limit
    limit = min(limit, settings.similarity.max_limit)
    similar = (
        similarity.similar(game, library.games, limit=limit, min_score=min_score) if limit else []
    )
    return GameDetail(**game.model_dump(), similar_to=similar)


@router.get(
    "/{appid}/similar",
    response_model=SimilarGamesResponse,
    responses={**AUTH_RESPONSES, **NOT_FOUND},
    summary="Games similar to an owned game",
)
async def get_similar_games(
    appid: AppIdPath,
    token: TokenDep,
    library_service: LibraryDep,
    similarity: SimilarityDep,
    settings: SettingsDep,
    limit: Annotated[int | None, Query(ge=1, description="Max results")] = None,
    min_score: MinScoreQuery = None,
) -> SimilarGamesResponse:
    """Only the names of the most similar games, best match first."""
    library = await library_service.get_library(token)
    game = library.get(appid)
    limit = min(limit or settings.similarity.default_limit, settings.similarity.max_limit)
    return SimilarGamesResponse(
        appid=game.appid,
        name=game.name,
        items=similarity.similar(game, library.games, limit=limit, min_score=min_score),
    )
