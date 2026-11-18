"""Genre response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from steam_wrap.schemas.game import LibraryInfo


class GenreCount(BaseModel):
    name: str = Field(..., examples=["Action"])
    game_count: int = Field(..., examples=[42])
    is_primary: bool = Field(..., description="True for Steam's top-level genres")


class GenreListResponse(BaseModel):
    scope: Literal["genres", "tags", "all"]
    library: LibraryInfo
    aliases: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Friendly query words accepted by ?genre= and the tags they expand to",
    )
    items: list[GenreCount]
