# ui-ultra-rag-mcp

A reusable, local browser interface for document-oriented MCP servers built around UltraRAG.

The package provides the plain evidence workspace, a loopback-only HTTP host, request validation, and a small adapter contract. An MCP project supplies a thin adapter that maps its own public tools to the UI operations. This keeps UI code in one repository without sharing a server's indexes, source files, or private project state.

This package is UI infrastructure, not an MCP server and not a knowledge base. Installing it alone does not expose MCP tools or ingest documents. Use the UI command documented by the MCP server you installed.

The `mcp` in the name identifies the interface it is designed to consume; it does not mean this package implements an MCP server.

## What it provides

- a basic search-and-sources workspace with no frontend build step;
- status, search, passage context, source listing, and ingestion views;
- optional metadata editing, source exclusion, source-file access, filters, reranking, and portable-bundle controls;
- optional per-query source selection and category-partition filters for servers that support them;
- capability flags so an adapter can hide unsupported actions;
- same-origin checks for writes, a strict content security policy, and loopback-only serving; and
- no dependency on FastMCP, UltraRAG internals, or a particular storage layout.

The current normalized document contract uses bibliographic metadata fields (`title`, `authors`, `year`, `doi`, `categories`, and `keywords`). A specialized server remains responsible for validating those values and may disable the metadata controls entirely.

## How MCP projects use it

```text
browser
   │ local HTTP
   ▼
ui-ultra-rag-mcp
   │ normalized adapter calls
   ▼
server-owned adapter
   │ normally a private stdio MCP client
   ▼
the server's public MCP tools and project state
```

The dependency should be pinned by commit in the consuming project's `pyproject.toml`:

```toml
dependencies = [
  "ui-ultra-rag-mcp @ git+https://github.com/AhmedKishki/ui-ultra-rag-mcp.git@COMMIT",
]
```

The adapter implements three methods:

```python
class UIAdapter(Protocol):
    async def health(self) -> Mapping[str, Any]: ...
    async def call(
        self, operation: str, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]: ...
    async def source_file(self, source_path: str) -> SourceFile: ...
```

`call` receives one of these normalized operations:

| Operation | Role |
|---|---|
| `status` | Describe the current generation and whether it is stale |
| `list_sources` | Return indexed and excluded sources |
| `search` | Return structured passages with provenance |
| `get_passage` | Return one passage with nearby context |
| `ingest` | Build and select a complete generation |
| `set_source_metadata` | Save reviewed bibliographic metadata |
| `set_source_inclusion` | Exclude or restore a reviewed source |
| `export_bundle` | Export a server-defined portable project bundle |
| `import_bundle` | Validate and import a named project-local bundle |

Bundle controls are disabled by default. A consuming server enables `bundle_export` and/or `bundle_import` in `UICapabilities` only when its adapter implements those operations. The shared UI never reads an archive itself. Servers that distinguish an ordinary re-ingestion from a forced rebuild can also enable `force_recompute`; the UI then sends that flag only for its **Regenerate** action.

Two further capability flags are opt-in and cover filters a server may not implement:

| Capability | What the UI adds | Search fields it sends |
|---|---|---|
| `source_selection` | "Limit to named sources" with include and exclude lists, a stable-ID line on every source card, and **Only this source** / **Exclude from search** actions | `source_ids`, `exclude_source_ids` |
| `category_partitions` | "Limit to corpus partitions" any-of filter and a partition list beside the status, with one chip per category and its searchable source count | `categories_any` (and `categories_any` on the source listing) |

Both default to `False`, so an adapter that does not support them sees neither the controls nor the extra request fields, and a request that still carries them is rejected with a 400 rather than forwarded. The partition list is read from the status response's `categories` entries; the UI never derives partitions from source metadata itself.

The adapter owns MCP startup and shutdown, error translation, source-file authorization, and schema normalization. The shared host never reads an index or discovers files itself. See the tests for a minimal in-memory adapter.

Create and serve an app from the consuming project:

```python
from ui_ultra_rag_mcp import UIProfile, create_ui_app, run_ui

app = create_ui_app(
    profile=UIProfile(application_name="My UltraRAG"),
    adapter_factory=my_adapter_factory,
)
run_ui(app, host="127.0.0.1", port=5051)
```

## Development

```bash
git clone https://github.com/AhmedKishki/ui-ultra-rag-mcp.git
cd ui-ultra-rag-mcp
uv sync --frozen
uv run pytest -q
uv run ruff check .
```

Static HTML, CSS, and JavaScript are packaged inside the Python distribution. There is deliberately no Node.js toolchain.

## Security boundary

The host accepts only `127.0.0.1`, `localhost`, or `::1`. It has no authentication and must not be exposed to a network. Write requests must be same-origin JSON. A source file is served only after the server-owned adapter returns an authorized `SourceFile`; adapters must resolve paths within their own project policy.

## UltraRAG credit

This independent companion project is designed for MCP servers built around [`OpenBMB/UltraRAG`](https://github.com/OpenBMB/UltraRAG). UltraRAG is a joint project of THUNLP, NEUIR, OpenBMB, AI9stars, and its contributors and is licensed under Apache-2.0. This repository is not an official UltraRAG release and does not imply endorsement. See [`NOTICE`](NOTICE).
