"""Loopback task bridge must close the exact recording before model control."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from spireagent.json_boundary import BoundaryError
from spireagent.workbench.native_tasks import NativeTasks


@pytest.fixture
def bridge():
    observed = {
        "schema": "sts2.platform/task-status-1",
        "runtime_instance_id": "game-1",
        "recording_session_id": "recording-1",
        "recording_lifecycle": "recording",
        "closeout_status": "recording",
        "ready_for_model": False,
    }
    calls, behavior = [], {"close": "success"}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            calls.append((self.path, None))
            self.respond()

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, body))
            assert body["runtime_instance_id"] == "game-1"
            assert body["recording_session_id"] == "recording-1"
            if behavior["close"] == "lost":
                self.close_connection = True
                return
            if behavior["close"] == "success":
                observed.update(recording_lifecycle="closed", ready_for_model=True)
            else:
                observed.update(recording_lifecycle="closing")
            self.respond()

        def respond(self):
            raw = json.dumps(observed).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = NativeTasks()
    client.address = f"http://127.0.0.1:{server.server_port}"
    try:
        yield client, observed, calls, behavior
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_fresh_instance_and_recording_binding_one_close_only(bridge):
    client, _, calls, _ = bridge
    assert client.prepare_model({"environment": {"runtime_instance_id": "game-1"}})[
        "ready_for_model"
    ]
    assert len(calls) == 2
    assert len(calls[1][1]["command_id"]) == 36
    client.prepare_model({"environment": {"runtime_instance_id": "game-1"}})
    assert len(calls) == 3 and calls[-1][1] is None


@pytest.mark.parametrize(
    "outcome,error",
    [("pending", "recording_close_pending_or_failed"), ("lost", "native_task_command_unknown")],
)
def test_close_pending_or_lost_response_is_not_model_permission(bridge, outcome, error):
    client, _, calls, behavior = bridge
    behavior["close"] = outcome
    with pytest.raises(BoundaryError, match=error):
        client.prepare_model({"environment": {"runtime_instance_id": "game-1"}})
    assert len(calls) == 2  # no automatic POST retry


def test_wrong_game_missing_identity_and_inconsistent_ready_never_send_close(bridge):
    client, observed, calls, _ = bridge
    with pytest.raises(BoundaryError, match="runtime_game_identity_required"):
        client.prepare_model({"environment": {}})
    assert calls == []
    with pytest.raises(BoundaryError, match="native_task_game_identity_mismatch"):
        client.prepare_model({"environment": {"runtime_instance_id": "different-game"}})
    observed["ready_for_model"] = True
    with pytest.raises(BoundaryError, match="native_task_unavailable"):
        client.prepare_model({"environment": {"runtime_instance_id": "game-1"}})
    assert all(body is None for _, body in calls)
