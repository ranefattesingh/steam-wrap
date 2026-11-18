"""Service discovery: tells clients how to use this API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from steam_wrap import __version__
from steam_wrap.api.v1.deps import SettingsDep
from steam_wrap.schemas import ApiIndex, ApiLinks, AuthInfo, EndpointInfo

router = APIRouter(tags=["meta"])

_HTTP_METHODS = {"get", "post", "put", "patch", "delete"}


def _endpoints(schema: dict[str, Any], prefix: str) -> list[EndpointInfo]:
    """Flatten an OpenAPI schema into endpoint entries under ``prefix``."""
    return [
        EndpointInfo(
            method=method.upper(),
            path=path,
            summary=op.get("summary") or op.get("operationId", ""),
            tags=list(op.get("tags", [])),
            requires_token=bool(op.get("security")),
        )
        for path, operations in schema.get("paths", {}).items()
        if path.startswith(prefix)
        for method, op in operations.items()
        if method in _HTTP_METHODS
    ]


@router.get(
    "",
    response_model=ApiIndex,
    summary="API index: endpoints, docs and auth",
)
async def api_index(request: Request, settings: SettingsDep) -> ApiIndex:
    """Machine-readable entry point. Lists every endpoint with its method,
    summary and whether it needs a token, plus links to the interactive
    documentation. Generated from the OpenAPI schema, so it never goes stale."""
    # app.openapi() is cached by FastAPI and works even when /openapi.json is off.
    endpoints = _endpoints(request.app.openapi(), settings.app.api_prefix)
    docs_on = settings.app.docs_enabled
    return ApiIndex(
        name=settings.app.name,
        version=__version__,
        links=ApiLinks(
            swagger_ui="/docs" if docs_on else None,
            redoc="/redoc" if docs_on else None,
            openapi_schema="/openapi.json" if docs_on else None,
        ),
        auth=AuthInfo(
            header="Authorization: Bearer <steam_access_token>",
            query_parameter="access_token" if settings.app.allow_query_token else None,
            how_to_get_token="Log in at https://store.steampowered.com, open "
            "https://store.steampowered.com/pointssummary/ajaxgetasyncconfig "
            "and copy data.webapi_token.",
        ),
        endpoints=endpoints,
    )
