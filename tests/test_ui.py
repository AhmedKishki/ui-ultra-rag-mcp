"""The attached-clients view: opt-in, and held to the write rules.

A host may serve this workspace and still not be a server — a stdio-only process
has no other client to report — so both the capability and the two routes are off
until a host turns them on, and a host that turns them on without the methods is
told so rather than raising.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from starlette.testclient import TestClient

from ui_ultra_rag_mcp import (
    SourceFile,
    UICapabilities,
    UIProfile,
    UIRequestError,
    create_ui_app,
)


class ClientControlAdapter:
    """An adapter that can report and end the clients attached to its host."""

    def __init__(self) -> None:
        self.dropped: list[tuple[str, str | None]] = []

    async def health(self) -> Mapping[str, Any]:
        return {"status": "ok"}

    async def call(
        self, operation: str, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        if operation == "status":
            return {"ready": False, "project_root": "/p", "project_name": "p"}
        if operation == "list_sources":
            return {"ready": False, "source_count": 0, "sources": []}
        raise UIRequestError(f"Research operation {operation!r} is not available", 404)

    async def source_file(self, source_path: str) -> SourceFile:  # pragma: no cover
        raise UIRequestError("not used")

    async def list_clients(self) -> list[Mapping[str, Any]]:
        return [
            {
                "session_id": "s-1",
                "name": "reader-agent",
                "attached": True,
                "requests": 7,
                "streams": 2,
                "idle_seconds": 0.2,
                "detached_reason": None,
            }
        ]

    async def disconnect_client(
        self, session_id: str, reason: str | None = None
    ) -> Mapping[str, Any]:
        self.dropped.append((session_id, reason))
        if session_id == "gone":
            raise UIRequestError("No client is attached with session gone")
        return {"session_id": session_id, "attached": False, "reason": reason}


def _host(adapter: Any, *, enabled: bool = True) -> TestClient:
    return TestClient(
        create_ui_app(
            profile=UIProfile(
                application_name="Client host",
                navigation_label="Views",
                capabilities=UICapabilities(clients=enabled, retrieval_modes=False),
            ),
            adapter=adapter,
        )
    )


def test_a_host_can_report_its_attached_clients() -> None:
    with _host(ClientControlAdapter()) as client:
        response = client.get("/api/clients")
    assert response.status_code == 200
    clients = response.json()["clients"]
    assert [entry["name"] for entry in clients] == ["reader-agent"]
    assert clients[0]["requests"] == 7
    assert clients[0]["streams"] == 2


def test_a_host_can_end_one_session_from_the_workspace() -> None:
    adapter = ClientControlAdapter()
    with _host(adapter) as client:
        response = client.post(
            "/api/clients/s-1/disconnect", json={"reason": "from the workspace"}
        )
        assert response.status_code == 200
        assert response.json()["attached"] is False
    assert adapter.dropped == [("s-1", "from the workspace")]


def test_the_clients_routes_are_absent_when_the_capability_is_off() -> None:
    """A memory-only or stdio-only host has nothing to report, so it says nothing."""

    adapter = ClientControlAdapter()
    with _host(adapter, enabled=False) as client:
        assert client.get("/api/clients").status_code == 404
        assert client.post("/api/clients/s-1/disconnect", json={}).status_code == 404
    assert adapter.dropped == []


def test_a_workspace_disconnect_is_same_origin_and_json_only() -> None:
    """Ending a session is a write, so it is held to the write rules."""

    adapter = ClientControlAdapter()
    with _host(adapter) as client:
        cross_origin = client.post(
            "/api/clients/s-1/disconnect",
            headers={"Origin": "https://example.com"},
            json={"reason": "x"},
        )
        form = client.post(
            "/api/clients/s-1/disconnect",
            content=b"reason=x",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    assert cross_origin.status_code == 403
    assert form.status_code == 415
    assert adapter.dropped == []


def test_a_host_that_advertises_clients_and_cannot_answer_says_501() -> None:
    """A capability without the methods is a host fact, not a traceback."""

    class Partial:
        async def health(self) -> Mapping[str, Any]:
            return {"status": "ok"}

        async def call(
            self, operation: str, arguments: Mapping[str, Any]
        ) -> Mapping[str, Any]:
            if operation == "status":
                return {"ready": False, "project_root": "/p", "project_name": "p"}
            if operation == "list_sources":
                return {"ready": False, "source_count": 0, "sources": []}
            raise UIRequestError("no", 404)

    with _host(Partial()) as client:
        response = client.get("/api/clients")
    assert response.status_code == 501
    assert "cannot report" in response.json()["error"]


def test_a_host_refusal_keeps_its_own_status_and_reason() -> None:
    """A host that refuses a client request has said something a reader can act on.

    Translating it into a generic failure would throw the reason away, so the two
    client routes carry the same translation the operation routes do.
    """

    with _host(ClientControlAdapter()) as client:
        response = client.post("/api/clients/gone/disconnect", json={})
    assert response.status_code == 400
    assert "No client is attached" in response.json()["error"]


def test_the_disconnect_reason_must_be_a_string() -> None:
    adapter = ClientControlAdapter()
    with _host(adapter) as client:
        response = client.post("/api/clients/s-1/disconnect", json={"reason": 7})
    assert response.status_code == 400
    assert adapter.dropped == []


def test_the_status_view_carries_the_clients_panel() -> None:
    """The panel ships hidden and is revealed by the capability, not by a route."""

    with _host(ClientControlAdapter()) as client:
        page = client.get("/")
    assert 'id="client-chips"' in page.text
    assert 'data-capability="clients"' in page.text
