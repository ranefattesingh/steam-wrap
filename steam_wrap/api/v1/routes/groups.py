"""Library grouped into clusters of related games."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from steam_wrap.api.v1.deps import AUTH_RESPONSES, LibraryDep, SimilarityDep, TokenDep
from steam_wrap.schemas import GroupsResponse
from steam_wrap.services.similarity_service import GroupBy

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get(
    "",
    response_model=GroupsResponse,
    responses=AUTH_RESPONSES,
    summary="Group similar games together",
)
async def list_groups(
    token: TokenDep,
    library_service: LibraryDep,
    similarity: SimilarityDep,
    by: Annotated[GroupBy, Query(description="How to cluster the library")] = "franchise",
    min_size: Annotated[int, Query(ge=1, le=100, description="Smallest group returned")] = 2,
) -> GroupsResponse:
    """* `franchise`: games in the same series (Steam franchise data, falling back to
      title matching such as *Dark Souls* / *Dark Souls III*).
    * `genre`: one group per top-level genre (a game can be in several).
    * `developer`: games by the same lead developer.
    """
    library = await library_service.get_library(token)
    return GroupsResponse(
        by=by,
        library=library.info(),
        groups=similarity.group(library.games, by, min_size=min_size),
    )
