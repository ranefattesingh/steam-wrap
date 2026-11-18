"""Shared response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Page(BaseModel):
    """Pagination metadata for list responses."""

    page: int = Field(..., ge=1, examples=[1])
    page_size: int = Field(..., ge=1, examples=[50])
    total: int = Field(..., ge=0, description="Items matching the filters", examples=[137])
    pages: int = Field(..., ge=0, examples=[3])


class HealthResponse(BaseModel):
    status: str = Field("ok", examples=["ok"])
    version: str = Field(..., examples=["1.0.0"])
    environment: str = Field(..., examples=["production"])


class ErrorBody(BaseModel):
    code: str = Field(..., examples=["invalid_token"])
    message: str = Field(..., examples=["Access token has expired."])
    request_id: str | None = Field(None, examples=["2f6c1c7d9b3e4a0f8d7e1b2c3a4d5e6f"])
    details: Any | None = None


class ErrorResponse(BaseModel):
    """Envelope used for every non-2xx response."""

    error: ErrorBody
