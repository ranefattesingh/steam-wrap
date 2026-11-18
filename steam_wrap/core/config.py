"""Application configuration.

Settings are layered (highest priority first):

1. Explicit keyword arguments to :class:`Settings` (used by tests).
2. Environment variables prefixed ``STEAMWRAP_`` with ``__`` as nested
   delimiter, e.g. ``STEAMWRAP_CACHE__LIBRARY_TTL_SECONDS=60``.
3. A ``.env`` file in the working directory.
4. The YAML file named by ``STEAMWRAP_CONFIG_FILE`` (default ``config.yaml``).
5. The defaults declared in this module.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    YamlConfigSettingsSource,
)

CONFIG_FILE_ENV = "STEAMWRAP_CONFIG_FILE"
DEFAULT_CONFIG_FILE = "config.yaml"


class AppSettings(BaseModel):
    """HTTP server / application level settings."""

    name: str = "Steam Wrap API"
    environment: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"
    log_json: bool = False
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    allow_query_token: bool = True
    docs_enabled: bool = True


class SteamSettings(BaseModel):
    """Upstream Steam endpoints and HTTP client behaviour."""

    api_base_url: str = "https://api.steampowered.com"
    store_base_url: str = "https://store.steampowered.com"
    asset_base_url: str = "https://shared.akamai.steamstatic.com/store_item_assets"
    media_base_url: str = "https://media.steampowered.com"
    language: str = "english"
    country_code: str = "US"
    api_key: SecretStr | None = None
    timeout_seconds: float = Field(15.0, gt=0)
    max_retries: int = Field(3, ge=0, le=10)
    retry_backoff_seconds: float = Field(0.5, ge=0)
    store_batch_size: int = Field(50, ge=1, le=100)
    store_max_concurrency: int = Field(4, ge=1, le=32)
    tags_per_game: int = Field(20, ge=1, le=50)


class CacheSettings(BaseModel):
    """In-memory TTL cache sizes and lifetimes (seconds)."""

    max_entries: int = Field(20_000, ge=100)
    library_ttl_seconds: int = Field(600, ge=0)
    store_item_ttl_seconds: int = Field(86_400, ge=0)
    tag_list_ttl_seconds: int = Field(86_400, ge=0)
    profile_ttl_seconds: int = Field(300, ge=0)


class PaginationSettings(BaseModel):
    default_page_size: int = Field(50, ge=1)
    max_page_size: int = Field(200, ge=1)


class GenreSettings(BaseModel):
    """Which tags count as genres and how friendly words map onto tags."""

    primary: list[str] = Field(
        default_factory=lambda: [
            "Action",
            "Adventure",
            "Casual",
            "Indie",
            "Massively Multiplayer",
            "Racing",
            "RPG",
            "Simulation",
            "Sports",
            "Strategy",
            "Free to Play",
            "Early Access",
        ]
    )
    aliases: dict[str, list[str]] = Field(default_factory=dict)


class SimilarityWeights(BaseModel):
    franchise: float = Field(0.40, ge=0)
    tags: float = Field(0.30, ge=0)
    genres: float = Field(0.15, ge=0)
    developer: float = Field(0.10, ge=0)
    publisher: float = Field(0.05, ge=0)


class SimilaritySettings(BaseModel):
    default_limit: int = Field(10, ge=1)
    max_limit: int = Field(50, ge=1)
    min_score: float = Field(0.2, ge=0, le=1)
    top_tags: int = Field(15, ge=1)
    weights: SimilarityWeights = Field(default_factory=SimilarityWeights)
    ignored_tags: list[str] = Field(default_factory=list)


class Settings(BaseSettings):
    """Root settings object. Obtain the process-wide instance via :func:`get_settings`."""

    model_config = SettingsConfigDict(
        env_prefix="STEAMWRAP_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app: AppSettings = Field(default_factory=AppSettings)
    steam: SteamSettings = Field(default_factory=SteamSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    pagination: PaginationSettings = Field(default_factory=PaginationSettings)
    genres: GenreSettings = Field(default_factory=GenreSettings)
    similarity: SimilaritySettings = Field(default_factory=SimilaritySettings)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        yaml_file = os.getenv(CONFIG_FILE_ENV, DEFAULT_CONFIG_FILE)
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file),
        )


@lru_cache
def get_settings() -> Settings:
    """Return the cached, process-wide settings instance."""
    return Settings()
