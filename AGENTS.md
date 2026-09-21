# AGENTS.md

This repository owns reusable local UI infrastructure for UltraRAG-derived MCP servers. It is not an MCP server and must not acquire retrieval, ingestion, or storage behavior of its own.

## Boundaries

- Keep the package independent of FastMCP and UltraRAG internals.
- Keep server-specific MCP transport, command-line arguments, paths, validation, and lifecycle in a consuming repository's adapter.
- Never inspect or mutate a server's corpus, chunks, indexes, or metadata directly.
- Serve only on loopback addresses unless a complete authenticated remote security design is explicitly requested.
- Keep writes same-origin and JSON-only.
- Treat `SourceFile` as an adapter authorization decision; do not add generic filesystem path resolution here.
- Do not add answer generation or chatbot behavior. The workspace displays evidence returned by the adapter.
- Keep the interface basic, readable, keyboard accessible, and dependency-free in the browser.
- Retain the UltraRAG credit and independent-project disclaimer in `README.md` and `NOTICE`.

## Public package contract

- `UIProfile` supplies labels and supported capabilities.
- `UIAdapter` normalizes one server to the document-workspace operations.
- Portable bundle buttons only forward `export_bundle` and `import_bundle`; archive placement, validation, and storage remain adapter/server concerns.
- `source_selection`, `category_partitions`, and `project_metadata` are opt-in and default to `False`: they only forward `source_ids`, `exclude_source_ids`, `categories_any`, `projects`, and `projects_any`, and the partition and project lists are read from the status response's `categories` and `projects` entries. Never derive partitions or project tags from source metadata in this repository, and keep a request carrying a disabled filter field a 400 rather than a forwarded call.
- `create_ui_app` builds the Starlette application.
- `run_ui` starts Uvicorn on a loopback address.

Changing operation names, payloads, capability names, or public routes is an API change. Preserve compatibility or release a new major version.

## Validation

Before committing:

```bash
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv run python -m compileall -q src tests
```

Tests must cover packaged static assets, the normalized routes, capability enforcement, same-origin write protection, and source-file delegation.
