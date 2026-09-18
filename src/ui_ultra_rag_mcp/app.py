"""Secure loopback web host for the shared document workspace."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import uvicorn
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from .contracts import (
    AdapterFactory,
    SourceFile,
    UIAdapter,
    UIProfile,
    UIRequestError,
)

LOGGER = logging.getLogger(__name__)
STATIC_ROOT = Path(__file__).with_name("static")
MAX_ERROR_LENGTH = 1200
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})

_OPERATION_CAPABILITY = {
    "list_sources": "sources",
    "get_passage": "passage_context",
    "ingest": "ingestion",
    "set_source_metadata": "metadata",
    "set_source_inclusion": "source_inclusion",
    "export_bundle": "bundle_export",
    "import_bundle": "bundle_import",
}


def _has_capability(profile: UIProfile, capability: str) -> bool:
    return bool(getattr(profile.capabilities, capability))


def _require_capability(request: Request, capability: str) -> None:
    profile: UIProfile = request.app.state.profile
    if not _has_capability(profile, capability):
        raise HTTPException(status_code=404, detail="This UI action is not available")


async def _adapter_call(
    request: Request,
    operation: str,
    arguments: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    capability = _OPERATION_CAPABILITY.get(operation)
    if capability is not None:
        _require_capability(request, capability)
    adapter: UIAdapter = request.app.state.adapter
    try:
        value = await adapter.call(operation, arguments or {})
    except UIRequestError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=exc.detail[:MAX_ERROR_LENGTH],
        ) from exc
    if not isinstance(value, Mapping):
        raise HTTPException(
            status_code=502,
            detail=f"Adapter operation {operation!r} returned a non-object response",
        )
    return dict(value)


def _same_origin(request: Request) -> bool:
    if request.headers.get("sec-fetch-site", "").casefold() == "cross-site":
        return False
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme in {"http", "https"} and parsed.netloc == request.headers.get(
        "host", ""
    )


async def _json_body(request: Request) -> dict[str, Any]:
    if not _same_origin(request):
        raise HTTPException(status_code=403, detail="Cross-origin writes are blocked")
    content_type = request.headers.get("content-type", "").split(";", 1)[0]
    if content_type.casefold() != "application/json":
        raise HTTPException(
            status_code=415,
            detail="Write requests require application/json",
        )
    try:
        value = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON request") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=400, detail="JSON body must be an object")
    return value


async def _index(request: Request) -> Response:
    return FileResponse(
        request.app.state.static_root / "index.html", media_type="text/html"
    )


async def _asset(request: Request) -> Response:
    filename = request.path_params["filename"]
    allowed = {"app.css": "text/css", "app.js": "text/javascript"}
    media_type = allowed.get(filename)
    if media_type is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(request.app.state.static_root / filename, media_type=media_type)


async def _ui_profile(request: Request) -> Response:
    profile: UIProfile = request.app.state.profile
    return JSONResponse(profile.as_dict())


async def _health(request: Request) -> Response:
    adapter: UIAdapter = request.app.state.adapter
    try:
        adapter_health = await adapter.health()
    except UIRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if not isinstance(adapter_health, Mapping):
        raise HTTPException(
            status_code=502, detail="Adapter health returned a non-object"
        )
    return JSONResponse({"status": "ok", **dict(adapter_health)})


async def _status(request: Request) -> Response:
    return JSONResponse(await _adapter_call(request, "status"))


def _query_list(request: Request, name: str) -> list[str] | None:
    values: list[str] = []
    for raw in request.query_params.getlist(name):
        values.extend(item.strip() for item in raw.split(",") if item.strip())
    return values or None


async def _sources(request: Request) -> Response:
    return JSONResponse(
        await _adapter_call(
            request,
            "list_sources",
            {
                "categories": _query_list(request, "categories"),
                "keywords": _query_list(request, "keywords"),
            },
        )
    )


async def _search(request: Request) -> Response:
    body = await _json_body(request)
    allowed = {
        "query",
        "top_k",
        "categories",
        "keywords",
        "document_ids",
        "retrieval_method",
        "rerank",
    }
    unknown = set(body) - allowed
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported search fields: {', '.join(sorted(unknown))}",
        )
    if not isinstance(body.get("query"), str) or not body["query"].strip():
        raise HTTPException(status_code=400, detail="Search requires a non-empty query")
    if body.get("rerank") and not request.app.state.profile.capabilities.reranking:
        raise HTTPException(status_code=400, detail="Reranking is not available")
    return JSONResponse(await _adapter_call(request, "search", body))


async def _passage(request: Request) -> Response:
    try:
        context_chunks = int(request.query_params.get("context_chunks", "1"))
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="context_chunks must be an integer",
        ) from exc
    return JSONResponse(
        await _adapter_call(
            request,
            "get_passage",
            {
                "chunk_id": request.path_params["chunk_id"],
                "context_chunks": context_chunks,
            },
        )
    )


async def _ingest(request: Request) -> Response:
    body = await _json_body(request)
    allowed = {"chunk_size", "chunk_overlap"}
    unknown = set(body) - allowed
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported ingestion fields: {', '.join(sorted(unknown))}",
        )
    return JSONResponse(await _adapter_call(request, "ingest", body))


async def _set_metadata(request: Request) -> Response:
    body = await _json_body(request)
    if set(body) != {"source_path", "metadata"}:
        raise HTTPException(
            status_code=400,
            detail="Metadata requests require source_path and metadata",
        )
    return JSONResponse(await _adapter_call(request, "set_source_metadata", body))


async def _set_inclusion(request: Request) -> Response:
    body = await _json_body(request)
    allowed = {"source_path", "included", "reason"}
    unknown = set(body) - allowed
    if unknown or not {"source_path", "included"}.issubset(body):
        raise HTTPException(
            status_code=400,
            detail="Inclusion requests require source_path and included",
        )
    return JSONResponse(await _adapter_call(request, "set_source_inclusion", body))


async def _export_bundle(request: Request) -> Response:
    body = await _json_body(request)
    if body:
        raise HTTPException(status_code=400, detail="Bundle export takes no fields")
    return JSONResponse(await _adapter_call(request, "export_bundle"))


async def _import_bundle(request: Request) -> Response:
    body = await _json_body(request)
    if set(body) - {"bundle_name", "activate"} or "bundle_name" not in body:
        raise HTTPException(
            status_code=400,
            detail="Bundle import requires bundle_name and optional activate",
        )
    if not isinstance(body["bundle_name"], str) or not body["bundle_name"].strip():
        raise HTTPException(status_code=400, detail="bundle_name must not be empty")
    if "activate" in body and not isinstance(body["activate"], bool):
        raise HTTPException(status_code=400, detail="activate must be true or false")
    return JSONResponse(await _adapter_call(request, "import_bundle", body))


async def _source_file(request: Request) -> Response:
    _require_capability(request, "source_files")
    raw_path = request.query_params.get("path", "").strip()
    if not raw_path:
        raise HTTPException(status_code=400, detail="Source path is required")
    adapter: UIAdapter = request.app.state.adapter
    try:
        source: SourceFile = await adapter.source_file(raw_path)
    except UIRequestError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    if not isinstance(source, SourceFile):
        raise HTTPException(
            status_code=502, detail="Adapter returned an invalid source file"
        )
    return FileResponse(
        source.path,
        media_type=source.media_type,
        filename=source.filename,
        content_disposition_type=source.content_disposition_type,
    )


async def _security_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'none'; form-action 'self'; "
        "frame-ancestors 'none'; object-src 'self'; script-src 'self'; "
        "style-src 'self'; connect-src 'self'; img-src 'self' data:"
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


async def _http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, HTTPException)
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


async def _unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    LOGGER.exception("UltraRAG MCP UI request failed", exc_info=exc)
    return JSONResponse(
        {"error": "Unexpected UI failure; inspect the UI host log."},
        status_code=500,
    )


def create_ui_app(
    *,
    profile: UIProfile,
    adapter_factory: AdapterFactory | None = None,
    adapter: UIAdapter | None = None,
    static_root: Path | None = None,
) -> Starlette:
    """Create the local UI app around one server-specific adapter."""
    if (adapter_factory is None) == (adapter is None):
        raise ValueError("Provide exactly one of adapter_factory or adapter")

    if adapter is not None:

        @asynccontextmanager
        async def fixed_adapter() -> Any:
            yield adapter

        resolved_factory: AdapterFactory = fixed_adapter
    else:
        assert adapter_factory is not None
        resolved_factory = adapter_factory

    @asynccontextmanager
    async def lifespan(app: Starlette) -> Any:
        async with resolved_factory() as active_adapter:
            app.state.adapter = active_adapter
            yield

    routes = [
        Route("/", _index),
        Route("/assets/{filename:str}", _asset),
        Route("/api/ui", _ui_profile),
        Route("/api/health", _health),
        Route("/api/status", _status),
        Route("/api/sources", _sources),
        Route("/api/search", _search, methods=["POST"]),
        Route("/api/passages/{chunk_id:str}", _passage),
        Route("/api/ingest", _ingest, methods=["POST"]),
        Route("/api/source-metadata", _set_metadata, methods=["POST"]),
        Route("/api/source-inclusion", _set_inclusion, methods=["POST"]),
        Route("/api/bundles/export", _export_bundle, methods=["POST"]),
        Route("/api/bundles/import", _import_bundle, methods=["POST"]),
        Route("/api/source-file", _source_file),
    ]
    app = Starlette(
        routes=routes,
        lifespan=lifespan,
        middleware=[Middleware(BaseHTTPMiddleware, dispatch=_security_headers)],
        exception_handlers={HTTPException: _http_error, Exception: _unexpected_error},
    )
    app.state.profile = profile
    app.state.static_root = (static_root or STATIC_ROOT).resolve()
    return app


def run_ui(
    app: Starlette,
    *,
    host: str = "127.0.0.1",
    port: int = 5051,
    log_level: str = "warning",
) -> None:
    """Run a UI on a loopback address only."""
    if host not in LOOPBACK_HOSTS:
        raise ValueError("The UI host must be a loopback address")
    if not 1 <= port <= 65535:
        raise ValueError("The UI port must be between 1 and 65535")
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=False,
    )
