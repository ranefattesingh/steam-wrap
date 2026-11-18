"""Game-related response models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from steam_wrap.schemas.common import Page


class Platforms(BaseModel):
    windows: bool = False
    mac: bool = False
    linux: bool = False
    steam_deck: Literal["verified", "playable", "unsupported", "unknown"] = "unknown"


class Game(BaseModel):
    """A game in the user's library, enriched with public store metadata."""

    appid: int = Field(..., examples=[242050])
    name: str = Field(..., examples=["Assassin's Creed® IV Black Flag™"])
    playtime_minutes: int = Field(0, description="Total playtime", examples=[1830])
    playtime_2weeks_minutes: int = Field(0, description="Playtime in the last two weeks")
    last_played_at: datetime | None = None
    genres: list[str] = Field(
        default_factory=list,
        description="Steam's top-level genres for the game",
        examples=[["Action", "Adventure"]],
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Community tags, most relevant first",
        examples=[["Pirates", "Open World", "Action", "Adventure", "Naval"]],
    )
    franchises: list[str] = Field(default_factory=list, examples=[["Assassin's Creed"]])
    developers: list[str] = Field(default_factory=list, examples=[["Ubisoft Montreal"]])
    publishers: list[str] = Field(default_factory=list, examples=[["Ubisoft"]])
    short_description: str | None = None
    is_free: bool = False
    release_date: date | None = None
    platforms: Platforms = Field(default_factory=Platforms)
    icon_url: str | None = None
    header_image_url: str | None = None
    store_url: str = Field(..., examples=["https://store.steampowered.com/app/242050"])
    metadata_available: bool = Field(
        True,
        description="False if store metadata could not be loaded (delisted app or Steam error); "
        "genres/tags will then be empty.",
    )


class GameRef(BaseModel):
    """A game as shown in lists.

    Pass ``id`` to ``GET /games/{id}`` for full details and similar games.
    """

    id: int = Field(..., description="Steam app id", examples=[289650])
    name: str = Field(..., examples=["Assassin's Creed® Unity"])
    description: str | None = Field(
        None,
        description="Short store description; null if Steam has none",
        examples=["Paris, 1789. In this action-adventure game, experience the French Revolution."],
    )


class GameDetail(Game):
    """A single game plus the games in the library most similar to it."""

    similar_to: list[GameRef] = Field(
        default_factory=list, description="Most similar library games, best match first"
    )


class LibraryInfo(BaseModel):
    """Summary of the whole library behind a response."""

    steamid: str = Field(..., examples=["76561198000000000"])
    total_games: int = Field(..., description="All owned/playable games")
    metadata_missing: int = Field(0, description="Games whose store metadata could not be loaded")
    fetched_at: datetime


class GameListResponse(BaseModel):
    library: LibraryInfo
    page: Page = Field(..., description="Paging info; `page.total` is the number of matching games")
    filters: dict[str, object] = Field(default_factory=dict, description="Filters applied")
    only_names: bool = Field(
        ...,
        description="True: `items` is a plain array of names. False: `{id, name, description}`.",
    )
    items: list[str] | list[GameRef] = Field(
        ...,
        examples=[["Assassin's Creed® IV Black Flag™", "Counter-Strike 2", "Portal 2"]],
    )


class SimilarGamesResponse(BaseModel):
    appid: int
    name: str
    items: list[GameRef] = Field(..., description="Best match first")


class GameGroup(BaseModel):
    name: str = Field(..., examples=["Assassin's Creed"])
    size: int
    games: list[GameRef]


class GroupsResponse(BaseModel):
    by: Literal["franchise", "genre", "developer"]
    library: LibraryInfo
    groups: list[GameGroup]
