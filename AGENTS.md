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

- `UIProfile` supplies labels and supported capabilities, including the optional `version_label` the header shows under the project name.
- `UIAdapter` normalizes one server to the document-workspace operations.
- Portable bundle buttons only forward `export_bundle` and `import_bundle`; archive placement, validation, and storage remain adapter/server concerns.
- `source_selection`, `category_partitions`, `project_metadata`, and `bibliographic_filters` are opt-in and default to `False`: they only forward `source_ids`, `exclude_source_ids`, `categories_any`, `projects`, `projects_any`, `authors_any`, `titles_any`, and `languages_any`, and the partition, project, and language lists are read from the status response's `categories`, `projects`, and `languages` entries. Never derive partitions, project tags, or languages from source metadata in this repository, and keep a request carrying a disabled filter field a 400 rather than a forwarded call. `languages_any` rides on `bibliographic_filters` because a source's language is recorded beside its authors and its title, so one flag governs all three and an adapter that declares the flag has declared the layer. A field this repository sends as an empty list when a reader typed nothing is absent from a request body, so adding a gated field does not change what a pinned adapter receives until a reader uses the control.
- `memory` and `memory_writes` are opt-in and default to `False`: the Memory view, its routes, and the write controls appear only for an adapter that reports both. Never invent a memory scope, interpret one, or resolve a memory path here; a scope is an opaque adapter-supplied identifier whose label and directory arrive in the `memory_status` response. The view renders every scope the status reports, local and global together, and sends a write back only to the scope whose block it came from. The `memory_standing_save` request forwards only the digest the page read, and the adapter owns the comparison and the refusal.
- `documents` defaults to `True` and is turned off by an adapter that serves no corpus: the document workspace, the `search` route, and the status summary are then hidden, while `status` and `health` stay available because the header shows the identity they carry.
- `create_ui_app` builds the Starlette application.
- `clients` is opt-in and defaults to `False`: a host that is not a server has no client to report, so the panel, the panel's two routes, and the 501 for a host that advertises the flag without the methods are all decided here rather than in each consumer. The two adapter methods live on a `ClientControl` protocol separate from `UIAdapter`, because a host that serves a workspace is not thereby a server. Never let this library name, interpret, or end a client: the adapter supplies the list and performs the disconnect, and the reason it passes along is a sentence the UI shows unchanged.
- `generations` is opt-in and defaults to `False`. The listing arrives in the status response's `generations` entries, so the panel needs no read route; the only operation is `remove_generation`, which takes `generation_id` and a `confirm` that repeats it. A missing or mismatched `confirm` is a 400 before the adapter is called, because a workspace that supplied its own confirmation would be a workspace where one click removed a generation nobody chose. Render the generation the host reports as current with no remove action, rather than with one that would be refused, and keep the typed id a gate on the submit button rather than a message beside it.
- `run_ui` starts Uvicorn on a loopback address.

Changing operation names, payloads, capability names, or public routes is an API change. Preserve compatibility or release a new major version. A flag that hides an existing control defaults to `True`, so it stays inert for a pinned adapter; a flag that adds a control the adapter has to honour, as the filter flags do, defaults to `False` and stays invisible until an adapter asks for it. `footer_text` defaults to empty: the UI states no policy of its own, and the quotation rule belongs in the server's documentation and its tool descriptions.

## Validation

Before committing:

```bash
uv lock --check
uv run ruff format --check .
uv run ruff check .
uv run pytest -q
uv run python -m compileall -q src tests
```

Tests must cover packaged static assets, the normalized routes, capability enforcement, same-origin write protection, the memory view and its writes, and source-file delegation.
