"""User/profile response models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PlayerProfile(BaseModel):
    persona_name: str | None = Field(None, examples=["gaben"])
    profile_url: str | None = None
    avatar_url: str | None = None
    country_code: str | None = None


class MeResponse(BaseModel):
    steamid: str = Field(..., examples=["76561198000000000"])
    token_expires_at: datetime | None = None
    profile: PlayerProfile | None = Field(
        None, description="Null if Steam would not return the profile"
    )
