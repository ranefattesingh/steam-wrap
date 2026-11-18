"""Models for the API index (discovery) endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ApiLinks(BaseModel):
    swagger_ui: str | None = Field(None, examples=["/docs"], description="Null when docs are off")
    redoc: str | None = Field(None, examples=["/redoc"])
    openapi_schema: str | None = Field(None, examples=["/openapi.json"])


class AuthInfo(BaseModel):
    header: str = Field(..., examples=["Authorization: Bearer <steam_access_token>"])
    query_parameter: str | None = Field(
        None, examples=["access_token"], description="Null when query-string tokens are disabled"
    )
    how_to_get_token: str


class EndpointInfo(BaseModel):
    method: str = Field(..., examples=["GET"])
    path: str = Field(..., examples=["/api/v1/games/{appid}"])
    summary: str = Field(..., examples=["Game details with similar games"])
    tags: list[str] = Field(default_factory=list, examples=[["games"]])
    requires_token: bool = Field(..., examples=[True])


class ApiIndex(BaseModel):
    name: str = Field(..., examples=["Steam Wrap API"])
    version: str = Field(..., examples=["1.0.0"])
    links: ApiLinks
    auth: AuthInfo
    endpoints: list[EndpointInfo]
