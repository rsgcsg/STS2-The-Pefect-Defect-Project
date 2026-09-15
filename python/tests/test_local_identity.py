from __future__ import annotations

import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

import pytest

from spireagent.json_boundary import BoundaryError
from spireagent.workbench.developer import ProjectConfig, atomic_json, combination
from spireagent.workbench.developer_server import Application, create_server
from spireagent.workbench.identity import LocalIdentity, private_read


def config(path):
    return ProjectConfig(path, "https://hub.example", "", None, combination())


def test_grant_publication_ack_loss_retry_and_logout_keep_device(tmp_path, monkeypatch):
    account = LocalIdentity(config(tmp_path))
    flow = "a" * 32
    seen, ack = [], [False]

    def request(route, *, body=None, token=None):
        seen.append((route, body, token))
        if route == "/v1/identity/flows":
            assert "device_token" not in body
            return {
                "flow_id": flow,
                "approval_path": "/app/?view=connect&flow=" + flow,
                "user_code": "ABCD-1234",
                "expires_at": datetime.fromtimestamp(time.time() + 600, UTC).isoformat(),
            }
        if route.endswith("/poll"):
            return {
                "status": "approved",
                "session_token": "personal-secret",
                "expires_at": datetime.fromtimestamp(time.time() + 3600, UTC).isoformat(),
                "device": {"device_id": "my-pc", "token": "device-secret"},
            }
        if route.endswith("/ack"):
            assert private_read(account.path)["session_token"] == "personal-secret"
            assert private_read(account.device_path)["device_id"] == "my-pc"
            if not ack[0]:
                ack[0] = True
                raise BoundaryError("hub", "unavailable")
            return {"status": "acknowledged"}
        if route == "/v1/identity/me":
            assert token == "personal-secret"
            return {"principal": {"email": "one@example.test", "role": "reviewer"}}
        if route == "/v1/identity/logout":
            raise BoundaryError("hub", "unavailable")
        raise AssertionError(route)

    monkeypatch.setattr(account, "request", request)
    public = account.begin("Laptop")
    assert "secret" not in json.dumps(public)
    assert account.begin("other name") == public
    with pytest.raises(BoundaryError):
        account.poll()
    assert account.poll() == {"status": "approved"}
    assert not account.flow_path.exists()
    public = account.status()
    assert public["status"] == "signed_in" and "personal-secret" not in json.dumps(public)
    assert "device-secret" not in json.dumps(public)
    before = account.device_path.read_bytes()
    assert account.logout()["remote_revoked"] is False
    assert not account.path.exists() and account.device_path.read_bytes() == before
    assert account.device_token() == "device-secret"


def test_legacy_device_proof_and_changed_grant_fail_closed(tmp_path, monkeypatch):
    account = LocalIdentity(config(tmp_path))
    monkeypatch.setenv("STPD_HUB_TOKEN", "legacy-secret")
    seen = []

    def request(route, *, body=None, token=None):
        seen.append((route, body, token))
        if route == "/v1/identity/device":
            return {"device_id": "old-device"}
        if route == "/v1/identity/flows":
            assert body["device_id"] == "old-device" and body["device_token"] == "legacy-secret"
            return {
                "flow_id": "a" * 32,
                "approval_path": "/app/?view=connect&flow=" + "a" * 32,
                "user_code": "CODE",
                "expires_at": datetime.fromtimestamp(time.time() + 600, UTC).isoformat(),
            }
        return {"status": "approved", "device": {"device_id": "wrong"}}

    monkeypatch.setattr(account, "request", request)
    account.begin("Mac")
    with pytest.raises(BoundaryError, match="device_identity_changed"):
        account.poll()
    assert not account.path.exists() and not account.device_path.exists()


def test_private_files_and_endpoint_changes_fail_closed(tmp_path):
    path = tmp_path / "account.json"
    path.write_text("{}")
    if os.name != "nt":
        path.chmod(0o644)
        with pytest.raises(BoundaryError, match="private_credential_file_required"):
            private_read(path)
    atomic_json(path, {"hub_url": "https://other.example", "expires_at": time.time() + 60})
    with pytest.raises(BoundaryError, match="account_hub_mismatch"):
        LocalIdentity(config(tmp_path)).session()


def test_personal_reads_cannot_become_device_or_arbitrary_requests(tmp_path, monkeypatch):
    account = LocalIdentity(config(tmp_path))
    monkeypatch.setattr(account, "request", lambda *a, **k: pytest.fail("request must be denied"))
    for route in ("../../uploads", "identity/me", "jobs?token=secret", "jobs?device=a&device=b"):
        with pytest.raises((BoundaryError, ValueError)):
            account.read(route)
    with pytest.raises(BoundaryError, match="sign_in_required"):
        account.read("datasets?limit=25")


def test_http_local_csrf_and_personal_boundary(tmp_path, monkeypatch):
    app = Application(config(tmp_path))
    server = create_server(app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = f"http://127.0.0.1:{server.server_port}"
    client = build_opener(HTTPCookieProcessor(CookieJar()))
    monkeypatch.setattr(app.account, "begin", lambda name: {"name": name})
    try:
        with pytest.raises(HTTPError) as denied:
            client.open(root + "/api/identity")
        assert denied.value.code == 401
        with client.open(root + "/") as response:
            assert "HttpOnly; SameSite=Strict" in response.headers["Set-Cookie"]
            assert app.account.cookie not in response.read().decode()
        with client.open(root + "/api/identity") as response:
            identity = json.load(response)
        headers = {
            "Content-Type": "application/json",
            "Origin": root,
            "X-CSRF-Token": identity["csrf_token"],
        }
        for update in (
            {"Origin": "https://evil.example"},
            {"X-CSRF-Token": "wrong"},
            {"Host": "evil.example"},
        ):
            with pytest.raises(HTTPError) as denied:
                client.open(
                    Request(
                        root + "/api/identity/login",
                        data=b'{"device_name":"PC"}',
                        headers={**headers, **update},
                    )
                )
            assert denied.value.code == 403
        with client.open(
            Request(root + "/api/identity/login", data=b'{"device_name":"PC"}', headers=headers)
        ) as response:
            assert json.load(response) == {"name": "PC"}
        with pytest.raises(HTTPError) as denied:
            client.open(root + "/api/project/datasets")
        assert denied.value.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        app.close()


def test_two_local_profiles_share_browser_without_replacing_each_others_cookie(
    tmp_path, monkeypatch
):
    @contextmanager
    def profile(name):
        app = Application(config(tmp_path / name))
        monkeypatch.setattr(app.account, "begin", lambda device: {"profile": name})
        server = create_server(app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield app, f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
            app.close()

    client = build_opener(HTTPCookieProcessor(CookieJar()))
    with profile("second") as (second, second_url):
        with profile("first") as (first, first_url):
            with client.open(first_url + "/") as response:
                first_cookie = response.headers["Set-Cookie"].split(";", 1)[0]
            client.open(second_url + "/").close()
            # A real browser cookie jar shares cookies across localhost ports.
            for app, root, name in ((first, first_url, "first"), (second, second_url, "second")):
                with client.open(root + "/api/identity") as response:
                    assert json.load(response)["csrf_token"] == app.account.csrf
                headers = {
                    "Content-Type": "application/json",
                    "Origin": root,
                    "X-CSRF-Token": app.account.csrf,
                }
                with client.open(
                    Request(
                        root + "/api/identity/login", data=b'{"device_name":"PC"}', headers=headers
                    )
                ) as response:
                    assert json.load(response) == {"profile": name}
            for changed in (
                {"Origin": second_url},
                {"X-CSRF-Token": second.account.csrf},
            ):
                with pytest.raises(HTTPError) as denied:
                    client.open(
                        Request(
                            first_url + "/api/identity/login",
                            data=b'{"device_name":"PC"}',
                            headers={
                                "Content-Type": "application/json",
                                "Origin": first_url,
                                "X-CSRF-Token": first.account.csrf,
                                **changed,
                            },
                        )
                    )
                assert denied.value.code == 403
            # Retired unscoped cookies must not become an authentication fallback.
            with pytest.raises(HTTPError) as denied:
                build_opener().open(
                    Request(
                        first_url + "/api/identity",
                        headers={"Cookie": "spireagent_local=" + first.account.cookie},
                    )
                )
            assert denied.value.code == 401
        with profile("first") as (restarted, restarted_url):
            with pytest.raises(HTTPError) as denied:
                build_opener().open(
                    Request(restarted_url + "/api/identity", headers={"Cookie": first_cookie})
                )
            assert denied.value.code == 401
            with client.open(restarted_url + "/") as response:
                refreshed = response.headers["Set-Cookie"].split(";", 1)[0]
            assert refreshed.split("=", 1)[0] == first_cookie.split("=", 1)[0]
            assert refreshed != first_cookie
            for app, root in ((restarted, restarted_url), (second, second_url)):
                with client.open(root + "/api/identity") as response:
                    assert json.load(response)["csrf_token"] == app.account.csrf


def test_credential_replacement_preserves_device_and_local_identity(tmp_path, monkeypatch):
    account = LocalIdentity(config(tmp_path))
    old = {"device_id": "same", "hub_url": "https://hub.example", "token": "old", "name": "PC"}
    atomic_json(account.device_path, old)
    path = tmp_path / "replacement.json"
    atomic_json(path, {**old, "device_id": "different", "token": "new"})
    with pytest.raises(BoundaryError, match="same_device_replacement_required"):
        account.replace_credential(path)
    atomic_json(path, {**old, "token": "new"})
    monkeypatch.setattr(account, "request", lambda *a, **k: {"device_id": "wrong"})
    with pytest.raises(BoundaryError, match="device_identity_changed"):
        account.replace_credential(path)
    assert private_read(account.device_path) == old
    monkeypatch.setattr(account, "request", lambda *a, **k: {"device_id": "same"})
    assert account.replace_credential(path)["outbox_changed"] is False
    assert private_read(account.device_path) == {**old, "token": "new"}


def test_pending_flow_never_sends_proof_to_changed_hub(tmp_path, monkeypatch):
    account = LocalIdentity(config(tmp_path))
    atomic_json(
        account.flow_path,
        {
            "hub_url": "https://old.example",
            "expires_at": time.time() + 600,
            "client_secret": "do-not-send",
        },
    )
    monkeypatch.setattr(account, "request", lambda *a, **k: pytest.fail("must not send proof"))
    for operation in (account.status, account.poll, lambda: account.begin("PC")):
        with pytest.raises(BoundaryError, match="flow_hub_mismatch"):
            operation()


def test_hub_enrichment_uses_current_private_device_grant(tmp_path, monkeypatch):
    from io import BytesIO

    app = Application(config(tmp_path))
    monkeypatch.setenv("STPD_HUB_TOKEN", "obsolete-env")
    atomic_json(
        app.account.device_path,
        {"hub_url": "https://hub.example", "device_id": "PC", "token": "current-private"},
    )

    class Opener:
        def open(self, request, timeout):
            assert request.headers["Authorization"] == "Bearer current-private"
            return BytesIO(b'{"items":[]}')

    app.hub.opener = Opener()
    assert app.console.remote("collections")["items"] == []


def test_browser_identity_response_races_use_real_presentation_module():
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        ["node", "--test", "tests/console_identity.test.mjs"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_local_bff_uses_actual_hub_dtos_and_preserves_legacy_upload_identity(tmp_path, monkeypatch):
    from dataclasses import replace
    from io import BytesIO
    from urllib.parse import urlsplit

    from test_hub_console import service
    from test_hub_identity import decision
    from test_hub_identity import request as hub_request

    from spireagent.hub.application import HubApplication
    from spireagent.hub.console_auth import AccessVerifier, verified_identity

    access = AccessVerifier(
        "https://team.cloudflareaccess.com",
        "a" * 64,
    )
    principal = replace(
        verified_identity(access.issuer, "native-sub", "owner@example.test"),
        expires_at=time.time() + 3600,
        session_binding="session",
    )
    monkeypatch.setattr(access, "authenticate", lambda token: principal)
    owner = service(tmp_path / "hub")
    with owner.operations.transaction() as db:
        db.execute("DELETE FROM identity_claim_scopes")
        db.execute("DELETE FROM identity_members")
        db.execute("DELETE FROM identity_users")
        db.execute("DELETE FROM settings WHERE key LIKE 'membership_%'")
    app = HubApplication(
        owner,
        "admin" * 16,
        browser_access=access,
        public_origin="https://hub.example",
    )
    app.identity.membership.bootstrap(
        issuer=access.issuer,
        admin_email="owner@example.test",
        legacy_principals=[
            {
                "email": "owner@example.test",
                "role": "reviewer",
                "devices": ["one"],
                "enroll_devices": True,
            }
        ],
    )
    account = LocalIdentity(config(tmp_path / "local"))
    monkeypatch.setenv("STPD_HUB_TOKEN", "one" * 16)

    class Opener:
        def open(self, request, timeout):
            url = urlsplit(request.full_url)
            status, value = hub_request(
                app,
                url.path,
                method=request.get_method(),
                query=url.query,
                bearer=request.headers.get("Authorization", "").removeprefix("Bearer "),
                body=json.loads(request.data) if request.data else None,
            )
            if status >= 400:
                raise HTTPError(request.full_url, status, "redacted", {}, BytesIO())
            return BytesIO(json.dumps(value).encode())

    account.opener = Opener()
    flow = account.begin("Mac")
    assert account.poll()["status"] == "pending"
    assert decision(app, "signed-fixture", flow)[0] == 200
    assert account.poll()["status"] == "approved"
    assert account.status()["principal"]["email"] == "owner@example.test"
    assert account.device()["device_id"] == "one"
    assert account.device_token() == "one" * 16
    cloud = hub_request(app, "/app/api/collections", jwt="signed-fixture", query="limit=25")[1]
    local = account.read("collections?limit=25")
    assert {k: v for k, v in local.items() if k != "observed_at"} == {
        k: v for k, v in cloud.items() if k != "observed_at"
    }
    assert account.logout()["remote_revoked"] is True
    assert account.device_token() == "one" * 16


def test_denied_flow_can_immediately_restart(tmp_path, monkeypatch):
    account = LocalIdentity(config(tmp_path))
    atomic_json(
        account.flow_path,
        {
            "hub_url": "https://hub.example",
            "flow_id": "a" * 32,
            "client_secret": "s" * 32,
            "expires_at": time.time() + 600,
        },
    )
    monkeypatch.setattr(account, "request", lambda *a, **k: {"status": "denied"})
    assert account.poll() == {"status": "denied"}
    assert not account.flow_path.exists()


def test_atomic_private_publication_flushes_directory_before_return(tmp_path, monkeypatch):
    if os.name == "nt":
        pytest.skip("directory fsync is POSIX-specific")
    events = []
    original_fsync, original_replace = os.fsync, os.replace

    def sync(descriptor):
        events.append("directory" if os.path.isdir(f"/dev/fd/{descriptor}") else "file")
        original_fsync(descriptor)

    def replace(source, target):
        events.append("replace")
        original_replace(source, target)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)
    atomic_json(tmp_path / "credential.json", {"test": True})
    assert events == ["file", "replace", "directory"]


@pytest.mark.parametrize(
    "member,body,expected",
    [
        (False, None, 4),
        (False, {}, 4),
        (True, None, 10),
        (True, {}, 20),
    ],
)
def test_member_transport_deadline_and_unknown_submission(tmp_path, member, body, expected):
    account = LocalIdentity(config(tmp_path))
    calls = []

    class TimeoutOpener:
        def open(self, request, timeout):
            calls.append(timeout)
            raise TimeoutError()

    account.opener = TimeoutOpener()
    route = "/v1/identity/member/exports" if member else "/v1/identity/flows"
    with pytest.raises(BoundaryError) as caught:
        account.request(route, body=body)
    assert calls == [expected]  # A lost acknowledgement must never auto-resubmit.
    assert caught.value.code == ("request_unknown" if body is not None else "hub_unavailable")
