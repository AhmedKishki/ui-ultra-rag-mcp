# ui-ultra-rag-mcp

A reusable, local browser interface for document-oriented MCP servers built around UltraRAG.

The package provides the plain evidence workspace, a loopback-only HTTP host, request validation, and a small adapter contract. An MCP project supplies a thin adapter that maps its own public tools to the UI operations. This keeps UI code in one repository without sharing a server's indexes, source files, or private project state.

This package is UI infrastructure, not an MCP server and not a knowledge base. Installing it alone does not expose MCP tools or ingest documents. Use the UI command documented by the MCP server you installed.

The `mcp` in the name identifies the interface it is designed to consume; it does not mean this package implements an MCP server.

## What it provides

- a basic search-and-sources workspace with no frontend build step;
- status, search, passage context, source listing, and ingestion views;
- optional metadata editing, source exclusion, source-file access, filters, retrieval modes, reranking, chunk settings, and portable-bundle controls;
- optional per-query source selection, category-partition, and project-tag filters for servers that support them;
- an optional memory view for servers that expose memory scopes, with opt-in writes;
- capability flags so an adapter can hide unsupported actions;
- an optional header label an adapter fills with its own version and this package's, so the running software is visible in the browser;
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

### A server that serves no documents

`documents` defaults to `True`. An adapter that serves something other than a corpus — memory, for instance — sets it to `False`, and the shared host then hides the document workspace: the Search view, the knowledge-base status, and the document routes, so `search` answers a 404 instead of forwarding a question the adapter cannot answer. The adapter still answers `status` and `health`, which carry the project identity the header shows, and any view it does enable becomes the visible one.

### Optional memory view

A server whose project keeps memory — a standing document plus dated rounds, or anything with that shape — can add a **Memory** view instead of a second application. Two capability flags are opt-in and default to `False`:

| Capability | What the UI adds | Operations it enables |
|---|---|---|
| `memory` | A **Memory** view showing every scope at once: one block per scope with its standing document and its recorded rounds | `memory_status`, `memory_rounds`, `memory_standing` |
| `memory_writes` | An **Add a round** form inside each scope block and an **Edit standing memory** dialog | `memory_append`, `memory_standing_save` |

Both flags off means no tab, no route, and a 404 for every memory request. A
**scope** is an opaque identifier the adapter supplies — the UI never invents one, never interprets one, and never resolves a memory path itself. The adapter's `memory_status` decides which scopes exist and what they are called:

```json
{
  "scopes": [
    {
      "scope": "local",
      "label": "This project",
      "directory": "/projects/thesis/.memory-rag",
      "standing_present": true,
      "round_count": 3,
      "latest_round_date": "2026-09-22"
    }
  ]
}
```

`memory_rounds` takes `scope` and `limit` (1–200) and answers with the newest rounds first:

```json
{
  "scope": "local",
  "round_count": 3,
  "truncated": false,
  "rounds": [
    {
      "date": "2026-09-22",
      "time": "14:54:02",
      "user": "Where does the draft live?",
      "assistant": "In the project directory.",
      "source_file": "2026-09-22.md"
    }
  ]
}
```

`memory_standing` returns the whole standing document with the digest of the bytes it read:

```json
{ "scope": "local", "content": "# MEMORY\n…", "sha256": "…" }
```

`memory_append` takes `scope`, `user_message`, and `assistant_message`; the adapter writes the round in its own format and returns `{"status": "saved", …}`. `memory_standing_save` takes `scope`, `content`, and the optional `expected_sha256` the page read, and the adapter decides whether to write: the UI only forwards the digest it displayed, so a document changed meanwhile can be refused rather than overwritten. Both writes are same-origin JSON, validated here, and refused with a 404 when `memory_writes` is off.

The adapter owns every memory decision: which scopes exist, what they are called, where they live, what a round is, and whether a standing write is allowed.

Every scope the status reports is shown at once, local and global together, each as a block with its own standing document, rounds, filter, and write form. At most ten are rendered and a note names how many were left out. The view holds no scope of its own: it sends back only the identifiers the status gave it.

Bundle controls are disabled by default. A consuming server enables `bundle_export` and/or `bundle_import` in `UICapabilities` only when its adapter implements those operations. The shared UI never reads an archive itself. Servers that distinguish an ordinary re-ingestion from a forced rebuild can also enable `force_recompute`; the UI then sends that flag only for its **Regenerate** action.

Three capability flags default to `True` and hide a control the server cannot honour, so a profile turns them off when its own tool surface offers no choice there:

| Capability | What the UI adds | Fields it sends |
|---|---|---|
| `retrieval_modes` | The **Retrieval** method radios (hybrid, BM25, dense) | `retrieval_method` |
| `reranking` | The **CPU rerank** checkbox | `rerank` |
| `chunk_settings` | The **Chunk size** and **Overlap** fields in the ingestion dialog | `chunk_size`, `chunk_overlap` |

A field from one of those three travels only when its capability is on, and the matching route rejects it with a 400 when the capability is off.

Three further capability flags are opt-in and cover filters a server may not implement:

| Capability | What the UI adds | Search fields it sends |
|---|---|---|
| `source_selection` | "Limit to named sources" with include and exclude lists, a stable-ID line on every source card, and **Only this source** / **Exclude from search** actions | `source_ids`, `exclude_source_ids` |
| `category_partitions` | "Limit to corpus partitions" any-of filter and a partition list beside the status, with one chip per category and its searchable source count | `categories_any` (and `categories_any` on the source listing) |
| `project_metadata` | A **Projects** field in the metadata editor, "Limit to projects" any-of filter, a project list beside the status, and a project tag on every source card | `projects`, `projects_any` (and both on the source listing) |

All three default to `False`, so an adapter that does not support them sees neither the controls nor the extra request fields, and a request that still carries them is rejected with a 400 rather than forwarded. The partition and project lists are read from the status response's `categories` and `projects` entries; the UI never derives either from source metadata itself.

The adapter owns MCP startup and shutdown, error translation, source-file and memory-scope authorization, and schema normalization. The shared host never reads an index, a memory directory, or any other file of its own accord. See the tests for a minimal in-memory adapter.

Create and serve an app from the consuming project:

```python
from ui_ultra_rag_mcp import UIProfile, create_ui_app, run_ui

app = create_ui_app(
    profile=UIProfile(application_name="My UltraRAG"),
    adapter_factory=my_adapter_factory,
)
run_ui(app, host="127.0.0.1", port=5051)
```

`UIProfile.version_label` is an optional short string shown under the project name in the header. A consuming server normally fills it with its own version and this package's, so an operator can see which software the running browser session is actually using. Leaving it empty hides the element.

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
