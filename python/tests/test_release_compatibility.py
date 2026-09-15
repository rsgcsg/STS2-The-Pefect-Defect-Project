"""Bounded archived-client/current-server contracts; not arbitrary version support."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest
from test_hub_uploads import fixture
from test_project_console import config

from spireagent.hub.application import HubApplication
from spireagent.workbench.console import LocalConsole

RELEASE = "45ef463e3c13cd82db55601c122a292c37aaae2e"


def test_published_client_reads_current_hub_without_source_equality(tmp_path):
    root = Path(__file__).resolve().parents[2]
    raw = subprocess.check_output(
        ["git", "show", RELEASE + ":python/spireagent/workbench/hub_client.py"],
        cwd=root,
    )
    namespace = {"__name__": "published_client"}
    # Executed bytes are the explicitly pinned release module from retained history.
    # Shared Python contract helpers remain current; this is bounded wire compatibility.
    exec(compile(raw, "published-hub-client.py", "exec"), namespace)
    service, _, _ = fixture(tmp_path)
    token = "c" * 32
    app = HubApplication(service, token)

    class Quiet(WSGIRequestHandler):
        def log_message(self, *_args):
            pass

    server = make_server("127.0.0.1", 0, app, handler_class=Quiet)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = namespace["HubClient"](
            f"http://127.0.0.1:{server.server_port}",
            token=lambda: token,
        )
        snapshot = client.snapshot()
        assert all(value["status"] == "available" for value in snapshot.values())
        system = client.get("/v1/console/system")
        assert system["producer"]["source_revision"] != RELEASE
        assert system["schema"] == "stpd/console-v1"
        assert service.operations.jobs() == []
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize(
    ("remote", "expected"),
    [
        ({"schema": "stpd/console-v1", "producer": {"source_revision": RELEASE}}, "available"),
        ({"schema": "future-console-v9"}, "unsupported_console_schema"),
        ({"status": "stale", "schema": "stpd/console-v1"}, "stale"),
        ({"status": "unavailable"}, "unavailable"),
    ],
)
def test_system_reports_interface_failure_not_sha_difference(
    tmp_path, monkeypatch, remote, expected
):
    console = LocalConsole(
        config(tmp_path), None, lambda: {}, lambda: "stopped", {"source_revision": "f" * 40}
    )
    monkeypatch.setattr(console, "remote", lambda _: remote)
    result = console.system()
    assert result["cloud_status"] == expected
    assert result["identity"]["source_revision"] == "f" * 40
    assert result["cloud"] == remote
