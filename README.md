# ui-ultra-rag-mcp

A reusable, local browser interface for document-oriented MCP servers built around UltraRAG.

The package provides the plain evidence workspace, a loopback-only HTTP host, request validation, and a small adapter contract. An MCP project supplies a thin adapter that maps its own public tools to the UI operations. This keeps UI code in one repository without sharing a server's indexes, source files, or private project state.

This package is UI infrastructure, not an MCP server and not a knowledge base. Installing it alone does not expose MCP tools or ingest documents. Use the UI command documented by the MCP server you installed.

The `mcp` in the name identifies the interface it is designed to consume; it does not mean this package implements an MCP server.

## What it provides

- a basic search-and-sources workspace with no frontend build step;
- a persistent sidebar that carries the project selector above the views, with the project named in its footer;
- a spacing scale and a type scale declared once in CSS, with a max readable width, generous line height, and panels that wrap rather than truncate;
- a cream and burnt-orange light and dark scheme built on the same tokens, after Anthropic's palette, meeting WCAG AA for body text, labels, and the focus ring in both;
- print rules that keep a passage and its citation and drop the chrome;
- status, search, passage context, source listing, and ingestion views;
- optional metadata editing, source exclusion, source-file access, filters, retrieval modes, reranking, chunk settings, and portable-bundle controls;
- optional per-query source selection, category-partition, and project-tag filters for servers that support them;
- an optional settings panel that renders each setting's own description, range, choices, and environment variable where the server declares them, alongside its value, origin, and cost, and an optional chunk-exclusion control beside the existing whole-source one;
- an optional memory view for servers that expose memory scopes, with opt-in writes;
- an optional SQL console for servers that keep their records in a store a reader may need to read or repair;
- capability flags so an adapter can hide unsupported actions;
- an optional header label an adapter fills with its own version and this package's, so the running software is visible in the browser;
- same-origin checks for writes, a strict content security policy, and loopback-only serving; and
- no dependency on FastMCP, UltraRAG internals, or a particular storage layout.

The current normalized document contract uses bibliographic metadata fields (`title`, `authors`, `year`, `doi`, `categories`, and `keywords`). A specialized server remains responsible for validating those values and may disable the metadata controls entirely.

## How the workspace is laid out

Navigation is a vertical sidebar rather than a row of tabs. The same views it held — `Search`, `Sources`, `Config`, `MCP`, and `Memory` — are the sidebar's items, each gated by the same capability the panel is gated by, each carrying an inline SVG icon so the page fetches nothing to draw it. The item in view is marked `aria-current="page"`, the whole column is keyboard operable with a visible focus ring, and the project name sits in a quiet footer beneath the views.

The project selector is the first thing in the sidebar and above the views, because changing the workspace is what a reader reaches for before choosing a view; the header carries the project's identity and the actions, and not the control that changes it. It is given room: a labelled control at pointer height, its note beneath it, and the start command for a project whose app is down on a line of its own instead of crammed beside the selector.

At 992px and wider the column is fixed and always visible. Below it the column becomes a drawer behind a button in the header; Escape and the scrim both close it, and it traps nothing, because a drawer that held the keyboard would be the one place on the page a reader could not leave. The selector rides into that drawer rather than being duplicated for it, so the one control that changes the workspace is the one that is always there.

Everything is built on a spacing scale and a type scale declared as CSS custom properties in one `:root` block. No rule carries a hand-picked small value, nothing is smaller than 13px, body text reads at 1.5 and a long description higher than that, prose and settings text carry a max readable width, cards have real internal padding, and a settings row wraps rather than truncating.

The visual vocabulary is cream and burnt orange, after Anthropic's own palette: a warm paper ground, warm greys rather than neutral ones, near-black and warm-black text, and one burnt-orange accent — `#b8592f` in light, `#e39070` in dark. UltraRAG's geometry is the vocabulary rather than its palette, because this workspace is not UltraRAG's face: the 6/12/16 radii, the three shadows, `Inter` for the interface and `JetBrains Mono` for code, and the 576 / 768 / 992 breakpoints are its own. Its accent green `#10a37f` and accent blue `#2563eb` are its product colours and are not borrowed. Two values in the light scheme are darker than they read best on cream, for the pairs they serve: the accent carries white text, and at `#c15f3c` that pair reaches 4.23:1; `--text-tertiary` reaches 4.37:1 on the cream surface. Both clear AA as declared, and `tests/test_ui.py` computes every pair rather than trusting it. Everything else about the upstream stack is deliberately left behind: the workspace is three hand-written static files with no bundler, no framework, and no build step, and `Inter` and `JetBrains Mono` are named with system fallbacks rather than downloaded, because a page that must fetch a font to be legible is not a local tool.

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

A server whose project keeps memory — a standing document plus dated rounds, or anything with that shape — can add a **Memory** view instead of a second application. These capability flags are opt-in and default to `False`:

| Capability | What the UI adds | Operations it enables |
|---|---|---|
| `memory` | A **Memory** view showing every scope at once: one block per scope with its standing document and its recorded rounds | `memory_status`, `memory_rounds`, `memory_standing` |
| `memory_writes` | An **Add a round** form inside each scope block and an **Edit standing memory** dialog | `memory_append`, `memory_standing_save` |
| `clients` | An **Attached clients** panel on the status view, listing every MCP client connected to the host with a **Disconnect** action | `list_clients`, `disconnect_client` |
| `generations` | A **Generations** panel on the status view listing every retained build with its size and which one is in use, with a **Remove** action and a dialog that requires the id typed back | `remove_generation` |
| `sql_console` | A **SQL console** panel on the status view: a scope selector, a statement field, **Run query** and **Execute write**, a results grid, and a line naming the records a write changed | `sql_query`, `sql_execute` |
| `settings` | A **Settings** panel on the status view, listing every setting by section with its value, its origin, and what changing it costs | `settings_read`, `settings_write` |
| `chunk_exclusion` | An **Exclude this chunk** action on every search hit and every passage of a context dialog, and a **Chunk exclusions** list on the status view with a restore for each row | `list_chunk_exclusions`, `set_chunk_inclusion` |
| `projects` | A **Projects** selector in the header, beside the project name, listing every project this installation serves and whether an app is up for each | `list_projects` |
| `agent_entry` | A copyable **Client entry** in the **MCP** view, the host's own text, for a client that cannot open a socket | `agent_entry` |

`clients` is about the host rather than the corpus. A host that serves this workspace and is not a server — a stdio-only process, or a library embedded in one — has no other client to report, so the flag defaults to off and the panel and both routes stay absent. A host that turns it on must implement `list_clients()` and `disconnect_client()` on its adapter; a host that advertises the flag without them is refused with a 501 rather than raising inside the route. `disconnect_client` ends one session, and the client owns its process, so the UI says so next to the action. The write is same-origin JSON, like every other write here.

`generations` is about how the corpus is stored rather than what it contains. The listing is free: it comes from the `generations` entries in the status response, so a host that retains immutable builds shows the panel with no read route of its own. The one operation is `remove_generation`, which takes `generation_id` and a `confirm` that repeats it. The dialog keeps the submit button disabled until the typed id matches, and a generation the host reports as current gets no remove action at all rather than one that would be refused. Nothing here decides which generation a reader may delete: the host's own refusal is shown unchanged, and the shared library only insists that a removal carry the id twice.

Both memory flags off means no view, no route, and a 404 for every memory request. A
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

### SQL console

A server whose records a reader may need to inspect, or repair, one statement at a time can add a **SQL console** to the status view. The `sql_console` flag is opt-in and defaults to `False`: this library cannot know which store an adapter keeps, and it must never open one of its own. A host that turns the flag on implements two methods on a `SqlConsole` protocol, separate from `UIAdapter`, because a statement is not a document operation:

| Adapter method | Returns |
|---|---|
| `sql_query(scope, statement)` | `{"columns": [...], "rows": [[...]], "row_count": n, "statement": "...", "scope": "..."}`, plus `truncated` when the adapter cut the result short |
| `sql_execute(scope, statement)` | `{"scope": "...", "rows_affected": n, "statement": "...", "reindexed": true}` |

The scope selector is free: the scopes arrive in the status response's `sql_scopes` entries, each an object with a `scope` identifier and an optional `label`, and a bare scope string is accepted as well. A host that declares the flag and reports no scope gets the panel with both controls disabled and a line saying there is nothing to run against.

The adapter owns the decision. It decides which scope a statement may reach, which statements it will run at all, and whether the rows are safe to send to a browser; a refusal is raised as `UIRequestError` and keeps its own status code and reason, so a read-only store says so instead of failing generically. The statement is forwarded exactly as typed, so its whitespace and its semicolon are part of what the adapter runs, while a scope is trimmed because an identifier with stray whitespace is not one the adapter recognises. A scope or statement that is missing or empty is a 400 before the adapter is called, and so is a statement longer than 20000 characters: a paste of a script stops here rather than travelling to the store. Both routes are same-origin JSON, loopback-only, like every other write here.

**Execute write** changes stored records, and the panel says so beside its own control rather than in a dialog: the server reindexes the change, the affected-row count is reported afterwards, and this workspace cannot undo it.

### Settings panel

A server that has settings a reader may want to see can add a **Settings** panel to the status view. The `settings` flag is opt-in and defaults to `False`: which settings exist, what a value is, where it came from, and what changing it costs are the server's facts, and this library knows none of them. A host that turns the flag on implements two operations on `UIAdapter`:

| Adapter operation | Returns |
|---|---|
| `settings_read()` | `{"revision": "…", "sections": [{"key": "retrieval", "title": "Retrieval", "settings": [{"key": "retrieval.rrf_k", "label": "…", "value": 60, "kind": "int", "layer": "…", "origin": "project", "writable": true, "doc": "…", "minimum": 1, "maximum": 200, "choices": ["hybrid", "bm25"], "env": "ULTRARAG_RRF_K", "cost": {"level": "regeneration", "message": "…"}}]}], "message": "…"}` |
| `settings_write(values, expected_revision, confirm)` | `{"revision": "…", "changed": ["retrieval.rrf_k"], "requires_ingest": true, "message": "…"}`, or a 400 whose `error` names an unknown setting, a bad value, or a wrong revision |

`settings_read` is reached at `GET /api/settings` and `settings_write` at `POST /api/settings`; both answer 404 while the flag is off, and the write is same-origin JSON like every other write here. The request body and the response are forwarded verbatim, so a key the workspace does not know reaches the server and a refusal reaches the browser unchanged.

A row shows six things and gives each of them room: the key's label, the `doc` the server wrote for it, the value the page loaded, the `origin` that value came from, the `cost.message` for changing it, and the control. Where the server declares them, `minimum` and `maximum` become the bounds on a number field, `choices` becomes a select over exactly the values the server offered, and `env` is named as the variable that would override the value in the environment. Every one of those keys is optional. A host that sends none of them draws the same row it drew before, with no blank description line and no control missing its input; a host that sends all of them gets all of them.

The panel draws a field from each setting's `kind`: a boolean is a checkbox, `int` and `float` are number inputs, and anything else is a single-line text input. A range and a list of choices narrow the field where the server declares them and change nothing where it does not; the value is still parsed only as the kind it declares, and the server decides what it will accept. A setting the server reports with `writable: false` — a value that came from the environment or the command line, for instance — is shown disabled with its origin named. A setting the server reports with no value loads an empty control, and leaving that control empty is not sent as a change.

A save sends only the keys whose value differs from what the page loaded, and only a key the page loaded. When any changed key carries a `cost.level` of `regeneration` or `model`, the panel asks first: it names those keys, quotes each one's `cost.message` as the server worded it, and requires the reader to type `ingest`, or `model` when a model change is among them. After a successful write the panel reads the settings again from the returned `revision`, shows the `message`, and — when the reply sets `requires_ingest` — says that an ingestion is needed and names `ingest`. It does not start one: a rebuild is the reader's decision, and the generation in use stays searchable meanwhile.

### Chunk exclusion

A server that can drop one passage from retrieval without removing its source can add an **Exclude this chunk** action to every search hit and to every passage of the context dialog, and a **Chunk exclusions** list beside the status. The `chunk_exclusion` flag is opt-in and defaults to `False`: the whole-source exclusion already exists, and a chunk-level control beside it is only meaningful where the server can honour it.

`list_chunk_exclusions` is reached at `GET /api/chunk-exclusions` and answers with `{"exclusions": [{"chunk_id", "source_relative_path", "locator", "reason", "excluded_at", "in_current_generation"}], "message": "…"}`. `set_chunk_inclusion` is reached at `POST /api/chunk-inclusion` and takes `{"chunk_id": "…", "included": false, "reason": "…"}` to exclude and `{"chunk_id": "…", "included": true}` with no reason to restore; both bodies are forwarded verbatim, both answer 404 while the flag is off, and the write is same-origin JSON.

The dialog shows the chunk's `source_relative_path` and locator, requires a reason, and stays open showing the server's own `error` after a refusal. A chunk the server marks as absent from the current generation is labelled with the wording the row supplies, or with a fixed sentence saying so, because restoring it changes the next generation rather than the passages already on screen. The whole-source exclusion and its dialog are unchanged by this flag.

Bundle controls are disabled by default. A consuming server enables `bundle_export` and/or `bundle_import` in `UICapabilities` only when its adapter implements those operations. The shared UI never reads an archive itself. Servers that distinguish an ordinary re-ingestion from a forced rebuild can also enable `force_recompute`; the UI then sends that flag only for its **Regenerate** action.

Three capability flags default to `True` and hide a control the server cannot honour, so a profile turns them off when its own tool surface offers no choice there:

| Capability | What the UI adds | Fields it sends |
|---|---|---|
| `retrieval_modes` | The **Retrieval** method radios (hybrid, BM25, dense) | `retrieval_method` |
| `reranking` | The **CPU rerank** checkbox | `rerank` |
| `chunk_settings` | The **Chunk size** and **Overlap** fields in the ingestion dialog | `chunk_size`, `chunk_overlap` |

A field from one of those three travels only when its capability is on, and the matching route rejects it with a 400 when the capability is off.

Four further capability flags are opt-in and cover filters a server may not implement:

| Capability | What the UI adds | Search fields it sends |
|---|---|---|
| `bibliographic_filters` | "Limit by author, work, or language" with an any-of author list, an any-of title list, and an any-of language list, plus a language list beside the status | `authors_any`, `titles_any`, `languages_any` |
| `source_selection` | "Limit to named sources" with include and exclude lists, a stable-ID line on every source card, and **Only this source** / **Exclude from search** actions | `source_ids`, `exclude_source_ids` |
| `category_partitions` | "Limit to corpus partitions" any-of filter and a partition list beside the status, with one chip per category and its searchable source count | `categories_any` (and `categories_any` on the source listing) |
| `project_metadata` | A **Projects** field in the metadata editor, "Limit to projects" any-of filter, a project list beside the status, and a project tag on every source card | `projects`, `projects_any` (and both on the source listing) |

All four default to `False`, so an adapter that does not support them sees neither the controls nor the extra request fields, and a request that still carries them is rejected with a 400 rather than forwarded. The partition, project, and language lists are read from the status response's `categories`, `projects`, and `languages` entries; the UI never derives any of them from source metadata itself.

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

Static HTML, CSS, and JavaScript are packaged inside the Python distribution. There is deliberately no Node.js toolchain, and none is needed to read or change the styles: `src/ui_ultra_rag_mcp/static/app.css` opens with a comment naming every token it adopts and the two it departs from, and the spacing and type scales are the first thing in the `:root` block.

## Security boundary

The host accepts only `127.0.0.1`, `localhost`, or `::1`. It has no authentication and must not be exposed to a network. Write requests must be same-origin JSON. A source file is served only after the server-owned adapter returns an authorized `SourceFile`; adapters must resolve paths within their own project policy.

## UltraRAG credit

This independent companion project is designed for MCP servers built around [`OpenBMB/UltraRAG`](https://github.com/OpenBMB/UltraRAG). UltraRAG is a joint project of THUNLP, NEUIR, OpenBMB, AI9stars, and its contributors and is licensed under Apache-2.0. This repository is not an official UltraRAG release and does not imply endorsement. See [`NOTICE`](NOTICE).
