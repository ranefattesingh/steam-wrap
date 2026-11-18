"""Information about the token's owner."""

from fastapi import APIRouter

from steam_wrap.api.v1.deps import AUTH_RESPONSES, LibraryDep, TokenDep
from steam_wrap.schemas import MeResponse

router = APIRouter(tags=["user"])


@router.get(
    "/me",
    response_model=MeResponse,
    responses=AUTH_RESPONSES,
    summary="Who does this token belong to?",
)
async def me(token: TokenDep, library: LibraryDep) -> MeResponse:
    """SteamID decoded from the token, its expiry and (when available) the public profile."""
    return MeResponse(
        steamid=token.steamid,
        token_expires_at=token.expires_at,
        profile=await library.get_profile(token),
    )
