from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

from ui_ultra_rag_mcp import (
    SourceFile,
    UICapabilities,
    UIProfile,
    UIRequestError,
    create_ui_app,
)


class FakeAdapter:
    def __init__(self, source: Path) -> None:
        self.source = source
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def health(self) -> Mapping[str, Any]:
        return {"project_root": "/project", "source_root": "/project/sources"}

    async def call(
        self,
        operation: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        self.calls.append((operation, dict(arguments)))
        responses: dict[str, dict[str, Any]] = {
            "status": {
                "ready": True,
                "stale": False,
                "project_root": "/project",
                "generation_id": "generation-1",
                "indexed_source_count": 1,
                "searchable_source_count": 1,
                "excluded_source_count": 0,
                "chunk_count": 1,
                "hybrid_ready": True,
                "available_retrieval_methods": ["bm25", "dense", "hybrid"],
                "default_retrieval_method": "hybrid",
            },
            "list_sources": {
                "ready": True,
                "sources": [{"document_id": "doc-1", "title": "Evidence"}],
                "excluded_sources": [],
            },
            "search": {
                "query": arguments.get("query"),
                "result_count": 0,
                "hits": [],
            },
            "get_passage": {
                "requested_chunk_id": arguments.get("chunk_id"),
                "context": [],
            },
            "ingest": {"generation_id": "generation-2", "chunk_count": 2},
            "set_source_metadata": {"requires_ingest": True},
            "set_source_inclusion": {"included": arguments.get("included")},
        }
        return responses[operation]

    async def source_file(self, source_path: str) -> SourceFile:
        if source_path != "evidence.pdf":
            raise UIRequestError("Source was not found", status_code=404)
        return SourceFile(
            path=self.source,
            media_type="application/pdf",
            filename=self.source.name,
        )


def _profile(**capabilities: bool) -> UIProfile:
    return UIProfile(
        application_name="Test UltraRAG",
        capabilities=UICapabilities(**capabilities),
    )


def test_workspace_and_normalized_read_operations(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    adapter = FakeAdapter(source)
    app = create_ui_app(profile=_profile(), adapter=adapter)

    with TestClient(app) as client:
        page = client.get("/")
        stylesheet = client.get("/assets/app.css")
        script = client.get("/assets/app.js")
        profile = client.get("/api/ui")
        health = client.get("/api/health")
        status = client.get("/api/status")
        sources = client.get("/api/sources?categories=theory,history")
        passage = client.get("/api/passages/chunk-1?context_chunks=2")

    assert page.status_code == 200
    assert "UltraRAG MCP" in page.text
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert "applyProfile" in script.text
    assert profile.json()["application_name"] == "Test UltraRAG"
    assert health.json()["project_root"] == "/project"
    assert status.json()["generation_id"] == "generation-1"
    assert sources.json()["sources"][0]["title"] == "Evidence"
    assert passage.json()["requested_chunk_id"] == "chunk-1"
    assert (
        "list_sources",
        {"categories": ["theory", "history"], "keywords": None},
    ) in adapter.calls


def test_writes_and_source_file_are_constrained(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    adapter = FakeAdapter(source)
    app = create_ui_app(profile=_profile(), adapter=adapter)

    with TestClient(app) as client:
        search = client.post("/api/search", json={"query": "evidence", "top_k": 5})
        metadata = client.post(
            "/api/source-metadata",
            json={"source_path": "evidence.pdf", "metadata": {"title": "Evidence"}},
        )
        inclusion = client.post(
            "/api/source-inclusion",
            json={"source_path": "evidence.pdf", "included": False},
        )
        ingestion = client.post(
            "/api/ingest",
            json={"chunk_size": 384, "chunk_overlap": 64},
        )
        served = client.get("/api/source-file?path=evidence.pdf")
        missing = client.get("/api/source-file?path=missing.pdf")
        non_json = client.post("/api/search", content=b"query=test")
        cross_origin = client.post(
            "/api/search",
            headers={"Origin": "https://example.com"},
            json={"query": "test"},
        )
        unknown = client.post(
            "/api/search",
            json={"query": "test", "unsupported": True},
        )

    assert search.status_code == 200
    assert metadata.json()["requires_ingest"] is True
    assert inclusion.json()["included"] is False
    assert ingestion.json()["generation_id"] == "generation-2"
    assert served.headers["content-type"].startswith("application/pdf")
    assert missing.status_code == 404
    assert non_json.status_code == 415
    assert cross_origin.status_code == 403
    assert unknown.status_code == 400


def test_disabled_capabilities_are_reported_and_enforced(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    profile = _profile(
        sources=False,
        passage_context=False,
        ingestion=False,
        metadata=False,
        source_inclusion=False,
        source_files=False,
        metadata_filters=False,
        reranking=False,
    )
    app = create_ui_app(profile=profile, adapter=FakeAdapter(source))

    with TestClient(app) as client:
        ui = client.get("/api/ui")
        sources = client.get("/api/sources")
        ingest = client.post("/api/ingest", json={})
        rerank = client.post(
            "/api/search",
            json={"query": "evidence", "rerank": True},
        )
        source_file = client.get("/api/source-file?path=evidence.pdf")

    assert ui.json()["capabilities"]["sources"] is False
    assert sources.status_code == 404
    assert ingest.status_code == 404
    assert rerank.status_code == 400
    assert source_file.status_code == 404


def test_configuration_rejects_ambiguous_adapter_setup(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    adapter = FakeAdapter(source)

    try:
        create_ui_app(profile=_profile())
    except ValueError as exc:
        assert "exactly one" in str(exc)
    else:
        raise AssertionError("missing adapter was accepted")

    try:
        create_ui_app(
            profile=_profile(),
            adapter=adapter,
            adapter_factory=lambda: None,  # type: ignore[arg-type,return-value]
        )
    except ValueError as exc:
        assert "exactly one" in str(exc)
    else:
        raise AssertionError("ambiguous adapter setup was accepted")
