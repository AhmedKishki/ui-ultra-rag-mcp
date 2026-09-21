"""Stable adapter contract between the shared UI and an MCP implementation."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, TypeAlias


@dataclass(frozen=True, slots=True)
class UICapabilities:
    """Optional document-workspace actions supported by one adapter."""

    sources: bool = True
    passage_context: bool = True
    ingestion: bool = True
    metadata: bool = True
    source_inclusion: bool = True
    source_files: bool = True
    metadata_filters: bool = True
    project_metadata: bool = False
    source_selection: bool = False
    category_partitions: bool = False
    reranking: bool = True
    force_recompute: bool = False
    bundle_export: bool = False
    bundle_import: bool = False

    def as_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class UIProfile:
    """Visible labels and capabilities for one MCP adapter."""

    application_name: str
    project_label: str = "Project"
    project_fallback_name: str = "Knowledge base"
    navigation_label: str = "Knowledge base views"
    source_types_label: str = "document sources"
    ingest_intro: str = (
        "Included documents will be extracted and indexed. The current generation "
        "remains active unless the complete build succeeds."
    )
    ingest_busy_message: str = "Building the indexes. This can take several minutes…"
    footer_text: str = "Verify important quotations in the original source."
    result_text_label: str = "Retrieved passage"
    copy_text_label: str = "Copy passage"
    bundle_import_intro: str = (
        "Place the archive in the server's project-local bundle directory, then "
        "enter its filename."
    )
    bundle_export_warning: str = (
        "Export this generation? The archive may contain complete original sources."
    )
    capabilities: UICapabilities = UICapabilities()
    version_label: str = ""

    def __post_init__(self) -> None:
        if not self.application_name.strip():
            raise ValueError("application_name must not be empty")

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["capabilities"] = self.capabilities.as_dict()
        return value


@dataclass(frozen=True, slots=True)
class SourceFile:
    """A source file that an adapter has already authorized for browser access."""

    path: Path
    media_type: str
    filename: str
    content_disposition_type: str = "inline"


class UIRequestError(Exception):
    """A safe adapter error that may be returned to the local browser."""

    def __init__(self, detail: str, *, status_code: int = 400) -> None:
        if not 400 <= status_code <= 599:
            raise ValueError("status_code must be between 400 and 599")
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class UIAdapter(Protocol):
    """Normalize one MCP server to the shared document-workspace operations."""

    async def health(self) -> Mapping[str, Any]: ...

    async def call(
        self,
        operation: str,
        arguments: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...

    async def source_file(self, source_path: str) -> SourceFile: ...


AdapterContext: TypeAlias = AbstractAsyncContextManager[UIAdapter]
AdapterFactory: TypeAlias = Callable[[], AdapterContext]
