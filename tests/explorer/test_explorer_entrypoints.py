import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from semantica.context.context_graph import ContextGraph  # noqa: E402
from semantica.explorer.runtime import install_mutation_bridge  # noqa: E402
from semantica.explorer.session import GraphSession  # noqa: E402


def test_mutation_bridge_supports_multiple_apps_for_one_graph(monkeypatch):
    graph = ContextGraph(advanced_analytics=False)
    first_session = GraphSession(graph)
    second_session = GraphSession(graph)
    received = []
    graph.mutation_callback = lambda *event: received.append(("original", event))

    monkeypatch.setattr(
        first_session,
        "handle_graph_mutation",
        lambda *event: received.append(("first", event)),
    )
    monkeypatch.setattr(
        second_session,
        "handle_graph_mutation",
        lambda *event: received.append(("second", event)),
    )

    first_app = FastAPI()
    first_app.state.event_loop = None
    first_app.state.ws_manager = None
    second_app = FastAPI()
    second_app.state.event_loop = None
    second_app.state.ws_manager = None

    install_mutation_bridge(first_app, first_session)
    install_mutation_bridge(second_app, second_session)
    graph.mutation_callback("UPDATE_NODE", "node-1", {"content": "Updated"})

    assert [receiver for receiver, _ in received] == ["second", "first", "original"]


def test_mutation_bridge_is_idempotent_for_one_app(monkeypatch):
    graph = ContextGraph(advanced_analytics=False)
    session = GraphSession(graph)
    received = []
    monkeypatch.setattr(
        session,
        "handle_graph_mutation",
        lambda *event: received.append(event),
    )
    app = FastAPI()
    app.state.event_loop = None
    app.state.ws_manager = None

    install_mutation_bridge(app, session)
    install_mutation_bridge(app, session)
    graph.mutation_callback("UPDATE_NODE", "node-1", {"content": "Updated"})

    assert len(received) == 1


def test_mutation_bridge_reinstalls_for_new_session_on_same_app(monkeypatch):
    first_session = GraphSession(ContextGraph(advanced_analytics=False))
    second_session = GraphSession(ContextGraph(advanced_analytics=False))
    received = []
    monkeypatch.setattr(
        first_session,
        "handle_graph_mutation",
        lambda *event: received.append(("first", event)),
    )
    monkeypatch.setattr(
        second_session,
        "handle_graph_mutation",
        lambda *event: received.append(("second", event)),
    )
    app = FastAPI()
    app.state.event_loop = None
    app.state.ws_manager = None

    install_mutation_bridge(app, first_session)
    install_mutation_bridge(app, second_session)
    second_session.graph.mutation_callback(
        "UPDATE_NODE",
        "node-2",
        {"content": "Updated"},
    )

    assert [receiver for receiver, _ in received] == ["second"]


def test_legacy_server_mounts_editable_markdown_routes(monkeypatch):
    monkeypatch.setenv("SEMANTICA_ALLOW_ANONYMOUS", "true")

    from semantica import server

    # fastapi>=0.141 nests included routers in app.routes as _IncludedRouter
    # entries whose own routes only appear via original_router — expand them
    # so mounted paths stay visible on every fastapi version.
    def _iter_paths(routes):
        for route in routes:
            nested = getattr(route, "original_router", None)
            if nested is not None:
                yield from _iter_paths(nested.routes)
            elif hasattr(route, "path"):
                yield route.path

    paths = set(_iter_paths(server.app.routes))
    assert "/api/markdown/{kind}/{resource_id:path}" in paths
    assert "/api/memories" in paths
    assert "/ws/graph-updates" in paths

    with TestClient(server.app) as client:
        with client.websocket_connect("/ws/graph-updates") as websocket:
            acknowledgement = websocket.receive_json()
            assert acknowledgement["event"] == "connection_ack"
            assert acknowledgement["data"] == {"connected": True}
            assert acknowledgement["timestamp"]
        info = client.get("/api/info")
        memories = client.get("/api/memories")
        server.app.state.session.graph.add_node(
            "server-node",
            "Note",
            "Original server content",
        )
        current = client.get("/api/markdown/context-node/server-node").json()
        saved = client.put(
            "/api/markdown/context-node/server-node",
            json={
                "markdown": current["source"].replace(
                    "Original server content",
                    "Updated server content",
                ),
                "expected_revision": current["revision"],
            },
        )

    assert info.json()["capabilities"]["agent_memory"] is False
    assert memories.status_code == 503
    assert memories.json()["detail"] == (
        "AgentMemory is not configured for this Explorer instance."
    )
    assert saved.status_code == 200
    assert saved.json()["body"] == "Updated server content"


@pytest.fixture
def reload_legacy_server(monkeypatch):
    """Re-import ``semantica.server`` under the test's environment.

    The legacy server reads ``SEMANTICA_CORS_ORIGINS`` once, at import, so a
    test that changes it has to re-import the module. The fixture re-imports
    it again after the environment is restored, so later tests see the
    module as it is by default.
    """
    import importlib

    from semantica import server

    yield lambda: importlib.reload(server)
    monkeypatch.undo()
    importlib.reload(server)


def _websocket_ack(client, origin):
    with client.websocket_connect(
        "/ws/graph-updates", headers={"Origin": origin}
    ) as websocket:
        return websocket.receive_json()["event"]


def _websocket_close_code(client, origin):
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws/graph-updates", headers={"Origin": origin}):
            pass
    return excinfo.value.code


def test_legacy_server_accepts_websocket_from_its_own_port(
    reload_legacy_server, monkeypatch
):
    """The legacy server listens on 8000, so a browser opened there must be able
    to open the WebSocket, while other origins are still refused."""
    monkeypatch.setenv("SEMANTICA_ALLOW_ANONYMOUS", "true")
    monkeypatch.delenv("SEMANTICA_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTICA_CORS_ORIGINS", raising=False)
    server = reload_legacy_server()

    with TestClient(server.app) as client:
        for origin in ("http://localhost:8000", "http://127.0.0.1:8000"):
            assert _websocket_ack(client, origin) == "connection_ack"
        for origin in ("https://evil.example", "http://localhost:8001"):
            assert _websocket_close_code(client, origin) == 4403


def test_legacy_server_explicit_cors_origins_replace_the_default(
    reload_legacy_server, monkeypatch
):
    """An explicit SEMANTICA_CORS_ORIGINS is the whole allowlist: the default
    localhost:8000 origin is not added to it."""
    monkeypatch.setenv("SEMANTICA_ALLOW_ANONYMOUS", "true")
    monkeypatch.delenv("SEMANTICA_API_KEY", raising=False)
    monkeypatch.setenv("SEMANTICA_CORS_ORIGINS", "https://custom.example.com")
    server = reload_legacy_server()

    with TestClient(server.app) as client:
        assert _websocket_ack(client, "https://custom.example.com") == "connection_ack"
        assert _websocket_close_code(client, "http://localhost:8000") == 4403


def test_cli_main_configures_allowed_origins_for_custom_port(tmp_path, monkeypatch):
    """Regression test for #1257: semantica-explorer --port 8020 includes the port in
    allowed_origins."""
    monkeypatch.setenv("SEMANTICA_ALLOW_ANONYMOUS", "true")
    monkeypatch.delenv("SEMANTICA_API_KEY", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("EXPLORER_CORS_ORIGINS", raising=False)

    graph_file = tmp_path / "test_graph.json"
    graph_file.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    import uvicorn

    from semantica.explorer import main

    captured_app = None
    captured_kwargs = {}

    def mock_run(app, **kwargs):
        nonlocal captured_app, captured_kwargs
        captured_app = app
        captured_kwargs = kwargs

    monkeypatch.setattr(uvicorn, "run", mock_run)

    main(["--graph", str(graph_file), "--port", "8020", "--no-browser"])

    assert captured_kwargs["port"] == 8020
    assert (
        "http://127.0.0.1:8020"
        in captured_app.state.explorer_settings["allowed_origins"]
    )
    assert (
        "http://localhost:8020"
        in captured_app.state.explorer_settings["allowed_origins"]
    )

    with TestClient(captured_app) as client:
        with client.websocket_connect(
            "/ws/graph-updates", headers={"Origin": "http://127.0.0.1:8020"}
        ) as ws:
            ack = ws.receive_json()
        assert ack["event"] == "connection_ack"

        # Hostile origin still rejected
        with pytest.raises(WebSocketDisconnect) as excinfo:
            with client.websocket_connect(
                "/ws/graph-updates", headers={"Origin": "https://evil.example"}
            ):
                pass
        assert excinfo.value.code == 4403


def test_cli_main_preserves_explicit_allowed_origins(tmp_path, monkeypatch):
    """Ensure explicit ALLOWED_ORIGINS is not overridden when --port is specified."""
    monkeypatch.setenv("SEMANTICA_ALLOW_ANONYMOUS", "true")
    monkeypatch.delenv("SEMANTICA_API_KEY", raising=False)
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://custom.example.com")
    monkeypatch.delenv("EXPLORER_CORS_ORIGINS", raising=False)

    graph_file = tmp_path / "test_graph.json"
    graph_file.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    import uvicorn

    from semantica.explorer import main

    captured_app = None

    def mock_run(app, **kwargs):
        nonlocal captured_app
        captured_app = app

    monkeypatch.setattr(uvicorn, "run", mock_run)

    main(["--graph", str(graph_file), "--port", "8020", "--no-browser"])

    assert captured_app.state.explorer_settings["allowed_origins"] == [
        "https://custom.example.com"
    ]


def _cli_allowed_origins(tmp_path, monkeypatch, *args):
    """Run ``semantica-explorer`` with ``args`` and return the app's origins."""
    monkeypatch.setenv("SEMANTICA_ALLOW_ANONYMOUS", "true")
    monkeypatch.delenv("SEMANTICA_API_KEY", raising=False)
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("EXPLORER_CORS_ORIGINS", raising=False)
    graph_file = tmp_path / "test_graph.json"
    graph_file.write_text('{"nodes": [], "edges": []}', encoding="utf-8")

    import uvicorn

    from semantica.explorer import main

    captured = {}
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: captured.update(app=app))
    main(["--graph", str(graph_file), "--no-browser", *args])
    return captured["app"].state.explorer_settings["allowed_origins"]


def test_cli_main_brackets_an_ipv6_host_origin(tmp_path, monkeypatch):
    """A browser sends an IPv6 origin in brackets, so --host fe80::1 must give
    http://[fe80::1]:<port>, not an origin that can never match."""
    origins = _cli_allowed_origins(
        tmp_path, monkeypatch, "--host", "fe80::1", "--port", "8020"
    )

    assert "http://[fe80::1]:8020" in origins
    assert "http://fe80::1:8020" not in origins


def test_cli_main_skips_the_port_origins_for_port_zero(tmp_path, monkeypatch):
    """With --port 0 the OS picks the port later, so no :0 origin is added and
    the Vite defaults are kept."""
    origins = _cli_allowed_origins(tmp_path, monkeypatch, "--port", "0")

    assert origins == ["http://localhost:5173", "http://127.0.0.1:5173"]
