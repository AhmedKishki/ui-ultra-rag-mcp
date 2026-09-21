"""Reusable local browser UI for UltraRAG-derived MCP servers."""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _distribution_version

from .app import create_ui_app, run_ui
from .contracts import (
    AdapterFactory,
    SourceFile,
    UIAdapter,
    UICapabilities,
    UIProfile,
    UIRequestError,
)

__all__ = [
    "AdapterFactory",
    "SourceFile",
    "UIAdapter",
    "UICapabilities",
    "UIProfile",
    "UIRequestError",
    "create_ui_app",
    "run_ui",
]

try:
    # Kept equal to the installed distribution so the number a consumer displays
    # comes from one source of truth, the version in pyproject.toml.
    __version__ = _distribution_version("ui-ultra-rag-mcp")
except PackageNotFoundError:  # a source tree that was never installed
    __version__ = "0.0.0+source"
