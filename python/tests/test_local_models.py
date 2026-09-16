from __future__ import annotations

import copy
import hashlib
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from spireagent.artifact_contracts import Manifest, Producer
from spireagent.json_boundary import BoundaryError, FrozenObject
from spireagent.workbench import local_models
from spireagent.workbench.developer import ProjectConfig, combination
from spireagent.workbench.local_models import LocalModelService, RuntimeClient
from stpd.canonical import canonical_json
from stpd.policy import installation


@pytest.fixture
def service(tmp_path, monkeypatch):
    config = ProjectConfig(tmp_path, "", "", None, combination())
    result = LocalModelService(config)
    # Synthetic native acceptance isolates the Runtime transport tests. The actual
    # bridge and fail-closed handoff have their own wire-level regression suite.
    monkeypatch.setattr(result.native_tasks, "prepare_model", lambda observed: {})
    return result


def finished(service):
    assert service.thread is not None
    service.thread.join(timeout=3)
    assert not service.thread.is_alive()
    return service.status()


def startup():
    return {
        "run_id": "run-00000000-0000-0000-0000-000000000000",
        "manifest_id": "fixture-policy",
        "policy_artifact_sha256": "a" * 64,
        "runtime_version": "0.1.0-rc.1",
        "runtime_code_sha256": "b" * 64,
    }


def status():
    start = startup()
    return {
        "schema": "sts2.policy-runtime/status-1",
        "run_id": start["run_id"],
        "runtime": {
            "version": start["runtime_version"],
            "code_sha256": start["runtime_code_sha256"],
        },
        "policy": {
            "manifest_id": start["manifest_id"],
            "artifact_sha256": start["policy_artifact_sha256"],
        },
        "mode": "human",
        "lifecycle": "running",
        "controller": "released",
        "tainted": False,
        "environment": {"host_kind": "test", "loaded_mod_ids": ["STS2_PLATFORM"]},
    }


@pytest.fixture
def runtime_http(request):
    legacy = getattr(request, "param", "current") == "legacy"
    state = status()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            requests.append((self.path, None))
            self.respond()

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, body))
            prefix = "" if legacy else "/v2"
            if self.path not in {prefix + route for route in ("/mode", "/tick", "/stop")}:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not legacy and self.headers.get("X-STS2-Policy-Run-ID") != state["run_id"]:
                self.send_response(409)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            route = self.path.removeprefix(prefix) if prefix else self.path
            if route == "/mode":
                state["mode"] = body["mode"]
            if route == "/tick":
                state["mode"] = "human"
            if route == "/stop":
                state["lifecycle"] = "stopped"
            self.respond()

        def respond(self):
            value = {
                "schema": "sts2.policy-runtime/http-1" if legacy else "sts2.policy-runtime/http-2",
                "status": state,
            }
            if self.path in {"/tick", "/v2/tick"}:
                value["schema"] += "/tick-1"
                value["results"] = []
            raw = json.dumps(value).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield RuntimeClient(f"http://127.0.0.1:{server.server_port}", startup()), state, requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_registry_is_trusted_code_selection_not_downloaded_command(service, tmp_path):
    report = service.catalog()
    assert report["policies"][0]["selection_id"] == "s1-human-combat-v4"
    with pytest.raises(BoundaryError, match="unregistered_policy"):
        service.start("../../downloaded/evil.json")
    root = tmp_path / "untrusted"
    registry = root / "configs/developer/local-policies-v1.json"
    registry.parent.mkdir(parents=True)
    value = service.registry()
    value["policies"][0]["command"] = "sh -c anything"
    registry.write_text(json.dumps(value))
    service.root = root
    with pytest.raises(BoundaryError):
        service.registry()


def test_readiness_reports_real_missing_prerequisites_without_loading(service, monkeypatch):
    monkeypatch.setattr(
        installation, "_backend_check", lambda: {"status": "blocked", "code": "no_cuda"}
    )
    result = service.readiness("s1-human-combat-v4")
    assert result["status"] == "blocked" and result["loaded"] is False
    assert result["checks"]["policy_identity"]["status"] == "pass"
    assert result["checks"]["backend"]["code"] == "no_cuda"
    assert service.process is None
    service.start("s1-human-combat-v4")
    result = finished(service)
    assert result["error_code"] == "model_readiness_blocked"
    assert service.process is None


def test_runtime_client_accepts_current_environment_and_binds_exact_identity(runtime_http):
    client, state, requests = runtime_http
    assert client.request("/status")["status"]["environment"]["loaded_mod_ids"] == ["STS2_PLATFORM"]
    state["run_id"] = "replacement-runtime"
    with pytest.raises(BoundaryError, match="identity_drift"):
        client.request("/status")
    assert all(body is None for _, body in requests)


@pytest.mark.parametrize(
    "route,body", [("/mode", {"mode": "human"}), ("/tick", {"max_ticks": 1}), ("/stop", {})]
)
def test_runtime_command_fences_replaced_process_before_effect(runtime_http, route, body):
    client, runtime, requests = runtime_http
    assert client.request("/status")["status"]["run_id"] == startup()["run_id"]
    # The same listening address now belongs to another process, after the GET.
    runtime.update(run_id="replacement-runtime", mode="auto")
    before = copy.deepcopy(runtime)
    with pytest.raises(BoundaryError, match="runtime_command_unknown"):
        client.request(route, body)
    assert runtime == before
    assert [request for request in requests if request[1] is not None] == [("/v2" + route, body)]


@pytest.mark.parametrize("runtime_http", ["legacy"], indirect=True)
@pytest.mark.parametrize(
    "route,body", [("/mode", {"mode": "human"}), ("/tick", {"max_ticks": 1}), ("/stop", {})]
)
def test_runtime_command_cannot_mutate_legacy_server_at_reused_address(runtime_http, route, body):
    client, runtime, requests = runtime_http
    runtime["mode"] = "auto"
    before = copy.deepcopy(runtime)
    with pytest.raises(BoundaryError, match="runtime_command_unknown"):
        client.request(route, body)
    assert runtime == before
    assert [request for request in requests if request[1] is not None] == [("/v2" + route, body)]


def test_closing_old_workbench_cannot_stop_replacement_runtime(service, runtime_http, monkeypatch):
    client, runtime, requests = runtime_http
    service.client = client
    service.state.update(status="loaded", loaded=True, startup=startup())
    # This HTTP fixture has no Agent evidence; the real verifier is covered separately.
    monkeypatch.setattr(service, "_evaluation_handoff", lambda: None)
    runtime["run_id"] = "replacement-runtime"
    service.close()
    assert runtime["lifecycle"] == "running"
    assert [request for request in requests if request[1] is not None] == [("/v2/stop", {})]
    restarted = LocalModelService(service.config)
    assert restarted.state["status"] == "recovery_required"
    assert restarted.state["previous_session"]["startup"] == startup()


@pytest.mark.parametrize("lost_stop", [False, True])
def test_recovered_runtime_shutdown_requires_confirmation(
    service, runtime_http, monkeypatch, lost_stop
):
    from urllib.error import URLError

    client, runtime, _ = runtime_http
    manifest = {"manifest_id": "fixture-policy", "artifact": {"sha256": "a" * 64}}
    exact = {
        **startup(),
        "address": "http://127.0.0.1:15527",
        "policy_manifest_sha256": hashlib.sha256(canonical_json(manifest).encode()).hexdigest(),
    }
    service.state["previous_session"] = {"startup": exact, "selection_id": "fixture"}
    with monkeypatch.context() as recovery:
        recovery.setattr(service, "selection", lambda _: {"id": "fixture", "manifest": "fixture"})
        recovery.setattr(local_models, "_object_file", lambda _: manifest)
        recovery.setattr(
            service,
            "_runtime_package",
            lambda: {
                "version": exact["runtime_version"],
                "code_sha256": exact["runtime_code_sha256"],
            },
        )
        recovery.setattr(local_models, "RuntimeClient", lambda *_: client)
        service._recover("human", service.intent_generation)
    assert service.client is client and service.process is None
    if lost_stop:
        # A real recovered HTTP client loses its Stop response; no local Popen
        # exists to supply alternative proof that the process terminated.
        def lost(*args, **kwargs):
            raise URLError("lost response")

        monkeypatch.setattr(client.opener, "open", lost)
    monkeypatch.setattr(service, "_evaluation_handoff", lambda: None)
    service.close()
    assert service.state["status"] == ("command_unknown" if lost_stop else "stopped")
    assert runtime["lifecycle"] == ("running" if lost_stop else "stopped")
    restarted = LocalModelService(service.config)
    assert restarted.state["status"] == ("recovery_required" if lost_stop else "idle")
    if lost_stop:
        assert restarted.state["previous_session"]["startup"] == exact
        restarted.close()
        again = LocalModelService(service.config)
        assert again.state["previous_session"]["startup"] == exact
        with monkeypatch.context() as recovery:
            recovery.setattr(again, "selection", lambda _: {"id": "fixture", "manifest": "fixture"})
            recovery.setattr(local_models, "_object_file", lambda _: manifest)
            recovery.setattr(
                again,
                "_runtime_package",
                lambda: {
                    "version": exact["runtime_version"],
                    "code_sha256": exact["runtime_code_sha256"],
                },
            )
            recovery.setattr(local_models, "RuntimeClient", lambda *_: client)
            again.command("human")
            assert finished(again)["status"] == "recovery_required"
        final = LocalModelService(service.config)
        assert final.state["previous_session"]["startup"] == exact
        with pytest.raises(BoundaryError, match="requires_recovery"):
            final.start("s1-human-combat-v4")


@pytest.mark.parametrize("session_status", ["loaded", "command_unknown"])
def test_recovered_exact_observation_clears_only_observation_error(
    service, runtime_http, session_status
):
    client, runtime, requests = runtime_http
    service.client = client
    service.state.update(status=session_status, loaded=True, error_code="runtime_command_unknown")
    runtime["run_id"] = "replacement-runtime"
    assert service.status()["observation_error"] == "runtime_status_unavailable_or_identity_drift"
    runtime["run_id"] = startup()["run_id"]
    runtime["tainted"] = True
    observed = service.status()
    assert "observation_error" not in observed
    assert observed["status"] == session_status
    assert observed["error_code"] == "runtime_command_unknown"
    assert observed["runtime"]["tainted"] is True
    assert all(body is None for _, body in requests)


@pytest.mark.parametrize(
    "address",
    ["http://public.example:15527", "https://127.0.0.1:15527", "http://127.0.0.1:15527/path"],
)
def test_runtime_requires_loopback_and_no_extra_path(address):
    with pytest.raises(BoundaryError):
        RuntimeClient(address, startup())


def test_one_step_is_exact_owner_mode_and_one_tick(service, runtime_http):
    client, _, requests = runtime_http
    service.client = client
    service.state.update(status="loaded", loaded=True)
    initial = service.command("one_step")
    assert initial["operation"]["action"] == "one_step"
    finished(service)
    assert [r for r in requests if r[1] is not None] == [
        ("/v2/mode", {"mode": "one_step"}),
        ("/v2/tick", {"max_ticks": 1}),
    ]
    assert service.state["runtime"]["mode"] == "human"


def test_lost_tick_response_is_unknown_and_never_retried(service):
    class LostResponse:
        calls = []

        def request(self, route, body=None):
            self.calls.append((route, body))
            if route == "/tick":
                raise BoundaryError("local_model", "runtime_command_unknown")
            return {"status": status()}

    client = LostResponse()
    service.client = client
    service.state.update(status="loaded", loaded=True)
    service.command("one_step")
    assert finished(service)["status"] == "command_unknown"
    with pytest.raises(BoundaryError, match="requires_recovery"):
        service.command("one_step")
    service.command("human")
    finished(service)
    assert sum(route == "/tick" for route, _ in client.calls) == 1


def test_human_handoff_can_be_requested_while_tick_pending(service):
    started, release = threading.Event(), threading.Event()
    calls = []

    class BlockingRuntime:
        def request(self, route, body=None):
            calls.append((route, body))
            if route == "/tick":
                started.set()
                assert release.wait(timeout=3)
            return {"status": status()}

    service.client = BlockingRuntime()
    service.state.update(status="loaded", loaded=True)
    service.command("one_step")
    assert started.wait(timeout=2)
    service.command("human")
    # Recovery invalidates old intent immediately, but its effect follows the
    # already-submitted tick rather than racing it over a second HTTP request.
    assert ("/mode", {"mode": "human"}) not in calls
    release.set()
    finished(service)
    for thread in service.threads:
        thread.join(timeout=2)
    assert [body for route, body in calls if route == "/mode"][-1] == {"mode": "human"}


def test_restarted_service_does_not_guess_pid_or_activate(service):
    service.state.update(status="loaded", loaded=True, startup=startup())
    service._save()
    replacement = LocalModelService(service.config)
    assert replacement.status()["status"] == "recovery_required"
    assert replacement.client is None and replacement.process is None
    with pytest.raises(BoundaryError, match="requires_recovery"):
        replacement.start("s1-human-combat-v4")


def test_shutdown_during_readiness_cannot_launch_a_late_runtime(service, monkeypatch):
    checking, release = threading.Event(), threading.Event()
    calls = []

    def readiness(_):
        checking.set()
        assert release.wait(timeout=3)
        return {"status": "ready_to_load"}

    monkeypatch.setattr(service, "readiness", readiness)
    monkeypatch.setattr(service, "_runtime_package", lambda: {"version": "fixture"})
    monkeypatch.setattr(local_models.subprocess, "Popen", lambda *a, **k: calls.append(a))
    service.start("s1-human-combat-v4")
    assert checking.wait(timeout=2)
    service.close()
    release.set()
    finished(service)
    assert calls == []
    assert service.state["loaded"] is False


def test_start_uses_fixed_command_human_and_rejects_foreign_attestation(service, monkeypatch):
    monkeypatch.setattr(service, "readiness", lambda _: {"status": "ready_to_load"})
    monkeypatch.setattr(
        service, "_runtime_package", lambda: {"version": "0.1.0-rc.1", "code_sha256": "b" * 64}
    )
    calls = []

    class Process:
        stdout = io.BytesIO(json.dumps({"schema": "foreign"}).encode() + b"\n")
        stopped = False

        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))

        def terminate(self):
            self.stopped = True

        def wait(self, timeout):
            return 0

        def poll(self):
            return 0 if self.stopped else None

    monkeypatch.setattr(local_models.subprocess, "Popen", Process)
    monkeypatch.setenv("STPD_HUB_TOKEN", "must-not-reach-inference-child")
    service.start("s1-human-combat-v4")
    result = finished(service)
    assert result["error_code"] == "runtime_load_or_attestation_failed"
    command, options = calls[0]
    assert command[-2:] == ["--mode", "human"]
    assert "--adapter-arg=tools/policy_adapter.py" in command
    assert "STPD_HUB_TOKEN" not in options["env"]
    assert options["env"]["HF_HUB_OFFLINE"] == "1"
    assert options["env"]["TRANSFORMERS_OFFLINE"] == "1"
    assert service.process.stopped


def test_evaluation_catalog_verifies_content_identity(service):
    directory = service.directory / "evaluations"
    directory.mkdir(parents=True)
    report = {"schema": "stpd/local-runtime-evaluation-handoff-v1", "game_outcome": "not_measured"}
    identity = hashlib.sha256(canonical_json(report).encode()).hexdigest()
    good = {**report, "evaluation_id": identity}
    (directory / (identity + ".json")).write_text(json.dumps(good))
    corrupt = copy.deepcopy(good)
    corrupt["game_outcome"] = "invented win"
    (directory / "corrupt.json").write_text(json.dumps(corrupt))
    assert service.evaluations() == [good]


def test_downloaded_fullrun_model_is_not_treated_as_a_loadable_policy(service):
    model = Manifest(
        "model",
        Producer("test/repository", "a" * 40, "b" * 64),
        parameters=FrozenObject.of({"schema": "stpd/scheme1-model-v1", "command": "malicious"}),
    )
    directory = service.config.state_dir / "downloads" / model.artifact_id
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_bytes(model.to_bytes())
    (directory / "download.json").write_text("{}")
    result = service.catalog()["downloaded_models"]
    assert result[0]["artifact_id"] == model.artifact_id
    assert result[0]["support_status"] == "unsupported" and result[0]["loaded"] is False
    with pytest.raises(BoundaryError, match="unregistered_policy"):
        service.start(model.artifact_id)
    assert service.process is None


def test_prepare_preserves_verified_download_receipt_and_never_starts_runtime(service):
    receipt = {
        "schema": "stpd/result-download-v1",
        "artifact_id": "a" * 64,
        "model_load_validated": False,
        "parents_downloaded": False,
    }

    class Downloader:
        def download(self, identity, destination):
            assert identity == receipt["artifact_id"]
            assert destination == service.config.state_dir / "downloads"
            return receipt

    service.hub = Downloader()
    service.prepare("a" * 64)
    result = finished(service)
    assert result["last_download"] == receipt and result["loaded"] is False
    assert service.process is None


def test_identity_replacement_between_ui_poll_and_command_never_gets_post(service, runtime_http):
    client, state, requests = runtime_http
    service.client = client
    service.state.update(status="loaded", loaded=True)
    assert service.status()["runtime"]["run_id"] == startup()["run_id"]
    state["run_id"] = "some-other-runtime"
    service.command("auto")
    finished(service)
    assert all(body is None for _, body in requests)


def test_prepare_and_load_does_not_install_when_backend_or_weights_blocked(service, monkeypatch):
    calls = []
    monkeypatch.setattr(
        service,
        "readiness",
        lambda _: {
            "status": "blocked",
            "checks": {
                "runtime_package": {"status": "blocked"},
                "backend": {"status": "blocked", "code": "no_cuda"},
            },
        },
    )
    monkeypatch.setattr(local_models, "install_runtime", lambda *args: calls.append(args))
    service.prepare_and_load("s1-human-combat-v4")
    assert finished(service)["error_code"] == "model_readiness_blocked"
    assert calls == [] and service.process is None


def test_prepare_and_load_installs_only_pinned_runtime_before_existing_human_start(
    service, monkeypatch
):
    calls = []
    monkeypatch.setattr(
        service,
        "readiness",
        lambda _: {
            "status": "blocked",
            "checks": {
                "runtime_package": {"status": "blocked"},
                "public_contract": {"status": "blocked"},
                "backend": {"status": "pass"},
            },
        },
    )
    monkeypatch.setattr(
        local_models, "install_runtime", lambda *args: calls.append(("install", args))
    )
    monkeypatch.setattr(
        service, "_start", lambda identity, intent: calls.append(("start", identity))
    )
    service.prepare_and_load("s1-human-combat-v4")
    assert finished(service)["operation"]["status"] == "completed"
    assert [kind for kind, _ in calls] == ["install", "start"]
    assert calls[0][1][1] == service.registry()["runtime_package"]


@pytest.mark.parametrize(
    "error", ["recording_close_pending_or_failed", "native_task_command_unknown"]
)
def test_native_close_failure_never_requests_model_mode(service, runtime_http, monkeypatch, error):
    client, _, requests = runtime_http
    service.client = client
    service.state.update(status="loaded", loaded=True)

    def failed(observed):
        raise BoundaryError("local_model", error)

    monkeypatch.setattr(service.native_tasks, "prepare_model", failed)
    service.command("auto")
    result = finished(service)
    assert result["operation"]["status"] == (
        "unknown" if error == "native_task_command_unknown" else "failed"
    )
    assert all(body is None for _, body in requests)
    service.command("human")  # manual recovery is independent of recording bridge
    assert finished(service)["operation"]["status"] == "completed"
    assert [body for _, body in requests if body] == [{"mode": "human"}]


def test_finalization_is_background_and_verifies_exact_bytes_not_page_read(service, monkeypatch):
    from agent_evaluation_fixture import evidence

    directory, expected = evidence(service.directory / "agent-runs")
    service.state.update(
        startup=expected, selection_id="s1-human-combat-v4", loaded=True, status="loaded"
    )
    calls = []

    class Finalized:
        def request(self, route, body=None):
            calls.append((route, body))
            return {"status": {**status(), "lifecycle": "stopped"}}

    service.client = Finalized()
    service.status()
    assert service.evaluations() == []
    service.observe_once()
    (report,) = service.evaluations()
    assert report["evidence_verification"] == "pass"
    assert report["run_id"] == directory.name and report["game_outcome"] == "not_measured"
    assert service.client is None and service.state["status"] == "stopped"
    service.observe_once()
    assert len(service.evaluations()) == 1
    assert all(route == "/status" and body is None for route, body in calls)


def test_owned_process_exit_can_finalize_without_http_but_unowned_disconnect_cannot(service):
    from agent_evaluation_fixture import evidence

    _, expected = evidence(service.directory / "agent-runs")
    service.state.update(
        startup=expected, selection_id="s1-human-combat-v4", loaded=True, status="loaded"
    )

    class Unavailable:
        def request(self, *args):
            raise BoundaryError("local_model", "runtime_unavailable")

    class Exited:
        def poll(self):
            return 0

    service.client = Unavailable()
    service.observe_once()
    assert service.evaluations() == [] and service.client is not None
    service.process = Exited()
    service.observe_once()
    assert service.state["status"] == "stopped"
    assert service.evaluations()[0]["evidence_verification"] == "pass"


@pytest.mark.parametrize("action", ["auto", "one_step", "shadow"])
def test_human_cancels_old_intent_while_native_close_is_pending(service, monkeypatch, action):
    entered, release = threading.Event(), threading.Event()
    calls = []

    class Runtime:
        def request(self, route, body=None):
            calls.append((route, body))
            return {"status": status()}

    def native_close(_):
        entered.set()
        assert release.wait(timeout=3)
        return {"ready_for_model": True}

    monkeypatch.setattr(service.native_tasks, "prepare_model", native_close)
    service.client = Runtime()
    service.state.update(status="loaded", loaded=True)
    service.command(action)
    assert entered.wait(timeout=2)
    service.command("human")
    assert finished(service)["operation"]["status"] == "completed"
    release.set()
    for thread in service.threads:
        thread.join(timeout=2)
    assert [(route, body) for route, body in calls if body is not None] == [
        ("/mode", {"mode": "human"})]
    assert service.state["runtime"]["mode"] == "human"


def test_human_during_step_mode_response_prevents_late_tick(service):
    entered, release = threading.Event(), threading.Event()
    calls = []

    class Runtime:
        def request(self, route, body=None):
            calls.append((route, body))
            if body == {"mode": "one_step"}:
                entered.set()
                assert release.wait(timeout=3)
            return {"status": status()}

    service.client = Runtime()
    service.state.update(status="loaded", loaded=True)
    service.command("one_step")
    assert entered.wait(timeout=2)
    service.command("human")
    release.set()
    assert finished(service)["operation"]["status"] == "completed"
    for thread in service.threads:
        thread.join(timeout=2)
    assert not any(route == "/tick" for route, _ in calls)
    assert [body for route, body in calls if route == "/mode"] == [
        {"mode": "one_step"}, {"mode": "human"}]


def test_stop_while_loading_cancels_late_start_without_waiting_for_readiness(service, monkeypatch):
    entered, release = threading.Event(), threading.Event()
    calls = []

    def readiness(_):
        entered.set()
        assert release.wait(timeout=3)
        return {"status": "ready_to_load"}

    monkeypatch.setattr(service, "readiness", readiness)
    monkeypatch.setattr(local_models.subprocess, "Popen", lambda *a, **k: calls.append(a))
    service.start("s1-human-combat-v4")
    assert entered.wait(timeout=2)
    service.command("stop")
    assert finished(service)["status"] == "stopped"
    release.set()
    for thread in service.threads:
        thread.join(timeout=2)
    assert calls == [] and service.state["status"] == "stopped"
