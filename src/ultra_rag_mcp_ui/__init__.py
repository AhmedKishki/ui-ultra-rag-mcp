"""Reusable local browser UI for UltraRAG-derived MCP servers."""

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

__version__ = "0.1.0"
