from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from starlette.testclient import TestClient

import ui_ultra_rag_mcp
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
            "export_bundle": {
                "bundle_name": "project-generation.research-rag.zip",
                "sha256": "abc",
            },
            "import_bundle": {
                "generation_id": "generation-imported",
                "activated": arguments.get("activate", True),
            },
            "memory_status": {
                "scopes": [
                    {
                        "scope": "local",
                        "label": "This project",
                        "directory": "/project/.memory-rag",
                        "standing_present": True,
                        "round_count": 1,
                        "latest_round_date": "2026-09-22",
                    },
                    {
                        "scope": "global:ahmed",
                        "label": "Global · ahmed",
                        "directory": "/shared/memory/ahmed",
                        "standing_present": True,
                        "round_count": 0,
                        "latest_round_date": None,
                    },
                ],
            },
            "memory_rounds": {
                "scope": arguments.get("scope"),
                "round_count": 1,
                "truncated": False,
                "rounds": [
                    {
                        "date": "2026-09-22",
                        "time": "14:54:02",
                        "user": "Where does the draft live?",
                        "assistant": "In the project directory.",
                        "source_file": "2026-09-22.md",
                    }
                ],
            },
            "memory_standing": {
                "scope": arguments.get("scope"),
                "content": "# MEMORY\nRemember the draft.\n",
                "sha256": "d1g3st",
            },
            "memory_append": {
                "status": "saved",
                "scope": arguments.get("scope"),
                "written": "/project/.memory-rag/project/2026-09-22.md",
            },
            "memory_standing_save": {
                "status": "saved",
                "scope": arguments.get("scope"),
                "sha256": "n3w-digest",
            },
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
        {
            "categories": ["theory", "history"],
            "categories_any": None,
            "projects": None,
            "projects_any": None,
            "keywords": None,
        },
    ) in adapter.calls


def test_source_selection_and_partitions_are_forwarded(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    adapter = FakeAdapter(source)
    app = create_ui_app(
        profile=_profile(
            source_selection=True,
            category_partitions=True,
            project_metadata=True,
        ),
        adapter=adapter,
    )

    with TestClient(app) as client:
        partitions = client.get("/api/sources?categories_any=theory,history")
        projects = client.get("/api/sources?projects_any=ai-and-fetishism")
        search = client.post(
            "/api/search",
            json={
                "query": "evidence",
                "top_k": 4,
                "categories_any": ["theory"],
                "projects_any": ["ai-and-fetishism"],
                "source_ids": ["src_1"],
                "exclude_source_ids": ["src_2"],
            },
        )
        metadata = client.post(
            "/api/source-metadata",
            json={
                "source_path": "evidence.pdf",
                "metadata": {
                    "categories": ["marxism"],
                    "keywords": ["fetishism"],
                    "project": ["ai-and-fetishism"],
                },
            },
        )

    assert partitions.status_code == 200
    assert projects.status_code == 200
    assert (
        "list_sources",
        {
            "categories": None,
            "categories_any": ["theory", "history"],
            "projects": None,
            "projects_any": None,
            "keywords": None,
        },
    ) in adapter.calls
    assert (
        "list_sources",
        {
            "categories": None,
            "categories_any": None,
            "projects": None,
            "projects_any": ["ai-and-fetishism"],
            "keywords": None,
        },
    ) in adapter.calls
    assert search.status_code == 200
    forwarded = next(
        arguments for operation, arguments in adapter.calls if operation == "search"
    )
    assert forwarded["categories_any"] == ["theory"]
    assert forwarded["projects_any"] == ["ai-and-fetishism"]
    assert forwarded["source_ids"] == ["src_1"]
    assert forwarded["exclude_source_ids"] == ["src_2"]
    assert metadata.status_code == 200
    assert (
        "set_source_metadata",
        {
            "source_path": "evidence.pdf",
            "metadata": {
                "categories": ["marxism"],
                "keywords": ["fetishism"],
                "project": ["ai-and-fetishism"],
            },
        },
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
        unsupported_force = client.post(
            "/api/ingest",
            json={"force_recompute": True},
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
    assert unsupported_force.status_code == 400


def test_force_recompute_is_capability_gated_and_forwarded(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    adapter = FakeAdapter(source)
    app = create_ui_app(
        profile=_profile(force_recompute=True),
        adapter=adapter,
    )

    with TestClient(app) as client:
        ingestion = client.post(
            "/api/ingest",
            json={
                "chunk_size": 384,
                "chunk_overlap": 64,
                "force_recompute": True,
            },
        )
        invalid = client.post(
            "/api/ingest",
            json={"force_recompute": "yes"},
        )

    assert ingestion.status_code == 200
    assert invalid.status_code == 400
    assert (
        "ingest",
        {
            "chunk_size": 384,
            "chunk_overlap": 64,
            "force_recompute": True,
        },
    ) in adapter.calls


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
        source_selection=False,
        category_partitions=False,
        project_metadata=False,
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
        partitions = client.post(
            "/api/search",
            json={"query": "evidence", "categories_any": ["theory"]},
        )
        selection = client.post(
            "/api/search",
            json={"query": "evidence", "source_ids": ["src_1"]},
        )
        project_filter = client.post(
            "/api/search",
            json={"query": "evidence", "projects_any": ["ai-and-fetishism"]},
        )
        source_file = client.get("/api/source-file?path=evidence.pdf")
        export = client.post("/api/bundles/export", json={})
        bundle_import = client.post(
            "/api/bundles/import",
            json={"bundle_name": "project.research-rag.zip"},
        )

    assert ui.json()["capabilities"]["sources"] is False
    assert sources.status_code == 404
    assert ingest.status_code == 404
    assert rerank.status_code == 400
    assert partitions.status_code == 400
    assert selection.status_code == 400
    assert project_filter.status_code == 400
    assert source_file.status_code == 404
    assert export.status_code == 404
    assert bundle_import.status_code == 404


def test_bundle_actions_are_capability_gated_and_forwarded(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    adapter = FakeAdapter(source)
    app = create_ui_app(
        profile=_profile(bundle_export=True, bundle_import=True),
        adapter=adapter,
    )

    with TestClient(app) as client:
        exported = client.post("/api/bundles/export", json={})
        imported = client.post(
            "/api/bundles/import",
            json={
                "bundle_name": "project-generation.research-rag.zip",
                "activate": False,
            },
        )
        unsafe = client.post(
            "/api/bundles/import",
            json={"bundle_name": "bundle.zip", "path": "../bundle.zip"},
        )

    assert exported.json()["bundle_name"].endswith(".research-rag.zip")
    assert imported.json()["activated"] is False
    assert unsafe.status_code == 400
    assert ("export_bundle", {}) in adapter.calls
    assert (
        "import_bundle",
        {
            "bundle_name": "project-generation.research-rag.zip",
            "activate": False,
        },
    ) in adapter.calls


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


def test_version_label_defaults_to_empty(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    app = create_ui_app(profile=_profile(), adapter=FakeAdapter(source))

    with TestClient(app) as client:
        payload = client.get("/api/ui").json()

    assert payload["version_label"] == ""


def test_version_label_is_served_and_rendered(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    profile = UIProfile(
        application_name="Test UltraRAG",
        version_label="server 1.2.3 · ui 0.5.0",
    )
    app = create_ui_app(profile=profile, adapter=FakeAdapter(source))

    with TestClient(app) as client:
        payload = client.get("/api/ui").json()
        page = client.get("/")
        script = client.get("/assets/app.js")

    assert payload["version_label"] == "server 1.2.3 · ui 0.5.0"
    assert 'id="version-label"' in page.text
    assert "version_label" in script.text


def test_a_memory_only_adapter_hides_the_document_workspace(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    adapter = FakeAdapter(source)
    app = create_ui_app(
        profile=_profile(
            documents=False,
            sources=False,
            ingestion=False,
            metadata=False,
            source_inclusion=False,
            source_files=False,
            metadata_filters=False,
            reranking=False,
            memory=True,
        ),
        adapter=adapter,
    )

    with TestClient(app) as client:
        payload = client.get("/api/ui").json()
        page = client.get("/")
        search = client.post("/api/search", json={"query": "evidence"})
        sources = client.get("/api/sources")
        memory = client.get("/api/memory")

    assert payload["capabilities"]["documents"] is False
    assert 'data-panel="search" data-capability="documents"' in page.text
    assert 'data-view="memory" data-capability="memory"' in page.text
    assert search.status_code == 404
    assert sources.status_code == 404
    assert memory.status_code == 200


def test_memory_view_is_capability_gated_and_forwarded(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    adapter = FakeAdapter(source)
    app = create_ui_app(
        profile=_profile(memory=True, memory_writes=True),
        adapter=adapter,
    )

    with TestClient(app) as client:
        status = client.get("/api/memory")
        rounds = client.get("/api/memory/rounds?scope=local&limit=5")
        standing = client.get("/api/memory/standing?scope=global:ahmed")
        appended = client.post(
            "/api/memory/append",
            json={
                "scope": "local",
                "user_message": "Remember this.",
                "assistant_message": "Remembered.",
            },
        )
        saved = client.post(
            "/api/memory/standing",
            json={
                "scope": "local",
                "content": "# MEMORY\nRemember the draft.\n",
                "expected_sha256": "d1g3st",
            },
        )

    assert status.json()["scopes"][0]["scope"] == "local"
    assert rounds.json()["rounds"][0]["assistant"] == "In the project directory."
    assert standing.json()["scope"] == "global:ahmed"
    assert appended.json()["status"] == "saved"
    assert saved.json()["sha256"] == "n3w-digest"
    assert ("memory_rounds", {"scope": "local", "limit": 5}) in adapter.calls
    assert ("memory_standing", {"scope": "global:ahmed"}) in adapter.calls
    assert (
        "memory_append",
        {
            "scope": "local",
            "user_message": "Remember this.",
            "assistant_message": "Remembered.",
        },
    ) in adapter.calls
    assert (
        "memory_standing_save",
        {
            "scope": "local",
            "content": "# MEMORY\nRemember the draft.\n",
            "expected_sha256": "d1g3st",
        },
    ) in adapter.calls


def test_memory_operations_are_capability_gated(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    adapter = FakeAdapter(source)
    append = {
        "scope": "local",
        "user_message": "Remember this.",
        "assistant_message": "Remembered.",
    }

    with TestClient(create_ui_app(profile=_profile(), adapter=adapter)) as client:
        hidden = [
            client.get("/api/memory"),
            client.get("/api/memory/rounds?scope=local"),
            client.get("/api/memory/standing?scope=local"),
            client.post("/api/memory/append", json=append),
            client.post(
                "/api/memory/standing",
                json={"scope": "local", "content": "# MEMORY\n"},
            ),
        ]

    with TestClient(
        create_ui_app(profile=_profile(memory=True), adapter=adapter)
    ) as client:
        readable = client.get("/api/memory")
        refused = client.post("/api/memory/append", json=append)

    assert [response.status_code for response in hidden] == [404] * 5
    assert readable.status_code == 200
    assert refused.status_code == 404
    assert all(operation != "memory_append" for operation, _ in adapter.calls)


def test_memory_writes_are_validated(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    adapter = FakeAdapter(source)
    app = create_ui_app(
        profile=_profile(memory=True, memory_writes=True),
        adapter=adapter,
    )

    with TestClient(app) as client:
        no_scope = client.post(
            "/api/memory/append",
            json={"user_message": "a", "assistant_message": "b"},
        )
        empty_message = client.post(
            "/api/memory/append",
            json={"scope": "local", "user_message": "   ", "assistant_message": "b"},
        )
        unknown_field = client.post(
            "/api/memory/append",
            json={
                "scope": "local",
                "user_message": "a",
                "assistant_message": "b",
                "path": "../outside",
            },
        )
        empty_content = client.post(
            "/api/memory/standing",
            json={"scope": "local", "content": "  "},
        )
        bad_digest = client.post(
            "/api/memory/standing",
            json={"scope": "local", "content": "# MEMORY\n", "expected_sha256": 7},
        )
        bad_limit = client.get("/api/memory/rounds?scope=local&limit=many")
        wide_limit = client.get("/api/memory/rounds?scope=local&limit=900")
        no_scope_read = client.get("/api/memory/standing")

    assert no_scope.status_code == 400
    assert empty_message.status_code == 400
    assert unknown_field.status_code == 400
    assert empty_content.status_code == 400
    assert bad_digest.status_code == 400
    assert bad_limit.status_code == 400
    assert wide_limit.status_code == 400
    assert no_scope_read.status_code == 400
    assert not [
        operation
        for operation, _ in adapter.calls
        if operation in {"memory_append", "memory_standing_save"}
    ]


def test_memory_labels_are_served_and_rendered(tmp_path: Path) -> None:
    source = tmp_path / "evidence.pdf"
    source.write_bytes(b"%PDF-1.4\n% test\n")
    profile = UIProfile(
        application_name="Test memory",
        memory_label="Agent memory",
        memory_standing_label="What is always remembered",
        memory_rounds_label="Dialogue rounds",
        memory_note="Memory stays on this machine.",
        capabilities=UICapabilities(memory=True, memory_writes=True),
    )
    app = create_ui_app(profile=profile, adapter=FakeAdapter(source))

    with TestClient(app) as client:
        payload = client.get("/api/ui").json()
        script = client.get("/assets/app.js")
        page = client.get("/")

    assert payload["memory_label"] == "Agent memory"
    assert payload["memory_standing_label"] == "What is always remembered"
    assert payload["memory_note"] == "Memory stays on this machine."
    assert payload["capabilities"]["memory"] is True
    assert payload["capabilities"]["memory_writes"] is True
    assert 'id="memory-scope"' in page.text
    assert "memory_standing_label" in script.text


def test_package_version_matches_pyproject() -> None:
    if ui_ultra_rag_mcp.__version__ == "0.0.0+source":
        pytest.skip("ui-ultra-rag-mcp is not installed in this environment")
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        expected = tomllib.load(handle)["project"]["version"]
    assert ui_ultra_rag_mcp.__version__ == expected
