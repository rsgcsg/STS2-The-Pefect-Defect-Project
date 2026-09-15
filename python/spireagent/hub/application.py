"""Authenticated WSGI boundary; independent worker verifies pending uploads."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from spireagent.console.page import CSP
from spireagent.hub.access import require_artifact_access
from spireagent.hub.console_auth import AccessVerifier, ConsolePrincipal
from spireagent.hub.database import token_hash
from spireagent.hub.identity import PERSONAL_PREFIX, IdentityService, text
from spireagent.hub.identity import fields as identity_fields
from spireagent.hub.uploads import LocalStaging, UploadService
from spireagent.json_boundary import BoundaryError, decode_json, json_bytes


@dataclass(frozen=True)
class DownloadBody:
    size: int
    filename: str
    chunks: Iterable[bytes]

    def __iter__(self):
        return iter(self.chunks)


class HubApplication:
    def __init__(
        self,
        service: UploadService,
        admin_token: str,
        *,
        budget_limit: int = 0,
        browser_access: AccessVerifier | None = None,
        backup_status: Path | None = None,
        public_origin: str = "",
    ) -> None:
        if len(admin_token) < 32:
            raise BoundaryError("hub", "admin_token_too_short")
        self.service = service
        self.admin_hash = token_hash(admin_token)
        self.capability_key = hashlib.sha256(("upload-capability:" + admin_token).encode()).digest()
        self.budget_limit = budget_limit
        self.browser_access = browser_access
        self.identity = IdentityService(
            service.operations,
            browser_access,
            hashlib.sha256(("personal-identity:" + admin_token).encode()).digest(),
            public_origin,
        )
        from spireagent.hub.member_routes import MemberAdministration

        self.members = MemberAdministration(self.identity)
        from spireagent.hub.member_api import MemberApi

        self.member_api = MemberApi(service, self.identity)
        from spireagent.hub.console_routes import ConsoleRoutes

        self.console = ConsoleRoutes(
            service,
            budget_limit,
            backup_status=backup_status,
            browser_enabled=browser_access is not None,
        )

    def capability(self, upload_id: str, deadline: int) -> str:
        signature = hmac.new(
            self.capability_key, f"{upload_id}:{deadline}".encode(), hashlib.sha256
        ).hexdigest()
        return f"{deadline}.{signature}"

    def validate_capability(self, upload_id: str, value: str) -> None:
        try:
            deadline = int(value.split(".")[0])
        except ValueError:
            raise BoundaryError("hub", "unauthorized") from None
        if deadline < time.time() or not secrets.compare_digest(
            value, self.capability(upload_id, deadline)
        ):
            raise BoundaryError("hub", "unauthorized")

    def __call__(
        self, environ: dict[str, Any], start_response: Callable[..., Any]
    ) -> Iterable[bytes]:
        try:
            status, kind, body = self.route(environ)
        except BoundaryError as error:
            status = {
                "unauthorized": "401 Unauthorized",
                "browser_access_not_configured": "503 Service Unavailable",
                "collection_not_found": "404 Not Found",
                "resource_not_found": "404 Not Found",
                "invalid_pagination": "400 Bad Request",
                "unexpected_query": "400 Bad Request",
                "status_filter_requires_collections": "400 Bad Request",
                "identity_rate_limited": "429 Too Many Requests",
                "identity_flow_capacity": "429 Too Many Requests",
                "identity_flow_not_found": "404 Not Found",
                "identity_origin_rejected": "403 Forbidden",
                "identity_csrf_rejected": "403 Forbidden",
                "identity_code_rejected": "403 Forbidden",
                "identity_device_not_authorized": "403 Forbidden",
                "invalid_identity_request": "400 Bad Request",
                "membership_not_initialized": "503 Service Unavailable",
                "membership_not_authorized": "403 Forbidden",
                "admin_browser_required": "403 Forbidden",
                "admin_required": "403 Forbidden",
                "browser_identity_required": "403 Forbidden",
                "member_not_found": "404 Not Found",
                "invalid_member_email": "400 Bad Request",
                "invalid_member_request": "400 Bad Request",
                "invalid_member_pagination": "400 Bad Request",
                "invalid_admin_query": "400 Bad Request",
                "member_capacity": "429 Too Many Requests",
            }.get(error.code, "409 Conflict")
            kind, body = "application/json", json_bytes({"error": error.code})
        except (ValueError, KeyError, TypeError):
            status, kind, body = (
                "400 Bad Request",
                "application/json",
                b'{"error":"invalid_request"}',
            )
        except Exception:
            status, kind, body = (
                "503 Service Unavailable",
                "application/json",
                b'{"error":"service_operation_failed"}',
            )
        headers = [
            ("Content-Type", kind),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            ("Content-Security-Policy", CSP),
            ("Referrer-Policy", "no-referrer"),
        ]
        if isinstance(body, DownloadBody):
            headers.extend(
                [
                    ("Content-Length", str(body.size)),
                    ("Content-Disposition", 'attachment; filename="' + body.filename + '"'),
                ]
            )
        if isinstance(body, bytes):
            headers.append(("Content-Length", str(len(body))))
            start_response(status, headers)
            return [body]
        start_response(status, headers)
        return body

    @staticmethod
    def body(environ: dict[str, Any], *, maximum: int = 32 * 1024 * 1024) -> Any:
        length = int(environ.get("CONTENT_LENGTH") or "0")
        if not 0 < length <= maximum:
            raise BoundaryError("hub", "request_size_limit")
        raw = environ["wsgi.input"].read(length)
        if len(raw) != length:
            raise BoundaryError("hub", "truncated_request")
        return decode_json(raw)

    @staticmethod
    def response(value: Any, status: str = "200 OK") -> tuple[str, str, bytes]:
        return status, "application/json", json_bytes(value)

    @staticmethod
    def bearer(env: dict[str, Any]) -> str:
        value = env.get("HTTP_AUTHORIZATION", "")
        if not value.startswith("Bearer ") or not 1 <= len(value[7:]) <= 4096:
            raise BoundaryError("identity", "unauthorized")
        return text(value[7:], 4096)

    def member_route(
        self, env: dict[str, Any], principal: ConsolePrincipal, path: str, *, browser: bool
    ) -> tuple[str, str, bytes | Iterable[bytes]]:
        method = env["REQUEST_METHOD"]
        query = env.get("QUERY_STRING", "")
        if method == "GET":
            payload = re.fullmatch(r"exports/([a-f0-9]{64})/files/([a-f0-9]{64})", path)
            if payload:
                if query:
                    raise BoundaryError("member", "unexpected_query")
                metadata, chunks = self.member_api.payload(payload[1], payload[2], principal)
                return (
                    "200 OK",
                    "application/octet-stream",
                    DownloadBody(metadata["size"], metadata["filename"], chunks),
                )
            return self.response(self.member_api.read(path, query, principal))
        if method == "POST" and not query:
            value = self.body(env, maximum=65536)
            if not isinstance(value, dict):
                raise BoundaryError("member", "invalid_member_request")
            if browser:
                self.identity.check_browser_write(
                    principal, env.get("HTTP_ORIGIN", ""), value.pop("csrf_token", None)
                )
            return self.response(self.member_api.write(path, value, principal))
        return self.response({"error": "method_not_allowed"}, "405 Method Not Allowed")

    def personal_route(self, env: dict[str, Any]) -> tuple[str, str, bytes | Iterable[bytes]]:
        method, path = env["REQUEST_METHOD"], env["PATH_INFO"]
        source = str(env.get("REMOTE_ADDR", "unknown"))[:128]
        identity = self.identity
        if path == "/v1/identity/flows" and method == "POST":
            identity.rate(source, "create", 20)
            return self.response(identity.create(self.body(env, maximum=8192)), "201 Created")
        match = re.fullmatch(r"/v1/identity/flows/([a-f0-9]{32})/(poll|ack)", path)
        if match and method == "POST":
            identity.rate(source, "poll", 300)
            return self.response(
                identity.poll(match[1], self.body(env, maximum=1024), acknowledge=match[2] == "ack")
            )
        token = self.bearer(env)
        if path == "/v1/identity/device" and method == "GET":
            return self.response(identity.device(token))
        if path == "/v1/identity/device/heartbeat" and method == "POST":
            value = identity_fields(self.body(env, maximum=1024), set(), {"version"})
            if "version" in value:
                text(value["version"], 128)
            return self.response(identity.device(token, heartbeat=True))
        if path == "/v1/identity/logout" and method == "POST":
            return self.response(identity.logout(token))
        principal = identity.personal(token)
        if path.startswith("/v1/identity/member/"):
            return self.member_route(
                env, principal, path.removeprefix("/v1/identity/member/"), browser=False
            )
        if path == "/v1/identity/me" and method == "GET":
            return self.response(identity.me(principal))
        if path.startswith("/v1/identity/console/") and method == "GET":
            principal, query = identity.scoped_query(principal, env.get("QUERY_STRING", ""))
            return self.response(
                self.console.read(path.removeprefix("/v1/identity/console/"), query, principal)
            )
        return self.response({"error": "identity_route_not_allowed"}, "405 Method Not Allowed")

    @staticmethod
    def upload_status(row: dict[str, Any]) -> dict[str, Any]:
        # Persisted owner error codes are useful; raw exception text/URLs are not public status.
        error = row.get("last_error")
        if error is not None and (
            not isinstance(error, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,95}", error) is None
        ):
            error = "operational_error_redacted"
        return {
            "upload_id": row["id"],
            "content_id": row["content_id"],
            "status": row["status"],
            "receipt": json.loads(row["receipt"]) if row["receipt"] else None,
            "verify_attempts": row["verify_attempts"],
            "retry_at": row["retry_at"] if row["status"] == "verification_pending" else None,
            "last_error": error,
        }

    def route(self, env: dict[str, Any]) -> tuple[str, str, bytes | Iterable[bytes]]:
        method, path = env["REQUEST_METHOD"], env.get("PATH_INFO", "")
        ops = self.service.operations
        if method == "GET" and path == "/":
            from spireagent.console.page import render_landing

            return (
                "200 OK",
                "text/html; charset=utf-8",
                render_landing(self.service.producer.source_revision).encode(),
            )
        if method == "GET" and path == "/assets/console.css":
            from spireagent.console.page import asset

            found = asset("console.css")
            assert found is not None
            return "200 OK", found[0], found[1]
        if method == "GET" and path == "/health":
            return self.response(
                {
                    "service": "stpd-hub",
                    "schema": "stpd/hub-health-v1",
                    "producer": self.service.producer.to_dict(),
                }
            )
        if path == "/app" or path.startswith("/app/"):
            if self.browser_access is None:
                raise BoundaryError("console", "browser_access_not_configured")
            principal = self.identity.principal(
                self.browser_access.authenticate(env.get("HTTP_CF_ACCESS_JWT_ASSERTION", ""))
            )
            if path == "/app/api/identity" and method == "GET":
                return self.response(self.identity.me(principal, browser=True))
            if path.startswith("/app/api/member/"):
                return self.member_route(
                    env, principal, path.removeprefix("/app/api/member/"), browser=True
                )
            device_revoke = re.fullmatch(
                r"/app/api/identity/devices/([A-Za-z0-9_.-]{1,128})/revoke", path
            )
            if device_revoke and method == "POST" and not env.get("QUERY_STRING"):
                value = identity_fields(self.body(env, maximum=1024), {"csrf_token"})
                self.identity.check_browser_write(
                    principal, env.get("HTTP_ORIGIN", ""), value["csrf_token"]
                )
                return self.response(
                    self.identity.membership.revoke_device(principal, device_revoke[1])
                )
            if path.startswith("/app/api/admin/"):
                resource = path.removeprefix("/app/api/admin/")
                if method == "GET":
                    return self.response(
                        self.members.read(resource, env.get("QUERY_STRING", ""), principal)
                    )
                if method == "POST":
                    if env.get("QUERY_STRING"):
                        raise BoundaryError("membership", "invalid_admin_query")
                    value = self.body(env, maximum=8192)
                    if not isinstance(value, dict) or "csrf_token" not in value:
                        raise BoundaryError("membership", "invalid_member_request")
                    self.identity.check_browser_write(
                        principal, env.get("HTTP_ORIGIN", ""), value.pop("csrf_token")
                    )
                    if resource == "campaigns":
                        return self.response(
                            self.member_api.admin_create_campaign(value, principal)
                        )
                    if resource == "collection-settings":
                        return self.response(
                            self.member_api.admin_collection_settings(value, principal)
                        )
                    if resource == "statistics/refresh":
                        from spireagent.hub.statistics import refresh_decision_statistics

                        with ops.transaction() as db:
                            self.identity.membership.admin(db, principal)
                        if set(value) - {"upload_ids", "dataset_ids"}:
                            raise BoundaryError("statistics", "invalid_refresh_request")
                        return self.response(
                            refresh_decision_statistics(
                                self.service,
                                upload_ids=value.get("upload_ids", []),
                                dataset_ids=value.get("dataset_ids", []),
                            )
                        )
                    return self.response(self.members.write(resource, value, principal))
                return self.response({"error": "method_not_allowed"}, "405 Method Not Allowed")
            flow = re.fullmatch(r"/app/api/identity/flows/([a-f0-9]{32})(?:/(approve|deny))?", path)
            if flow:
                if method == "GET" and flow[2] is None:
                    return self.response(self.identity.flow_view(flow[1], principal))
                if method == "POST" and flow[2] is not None:
                    value = self.body(env, maximum=1024)
                    identity_fields(value, {"csrf_token", "user_code"})
                    self.identity.check_browser_write(
                        principal, env.get("HTTP_ORIGIN", ""), value["csrf_token"]
                    )
                    return self.response(
                        self.identity.decide(flow[1], value, principal, deny=flow[2] == "deny")
                    )
            if method != "GET":
                return self.response({"error": "console_read_only"}, "405 Method Not Allowed")
            if path.startswith("/app/api/"):
                principal, console_query = self.identity.scoped_query(
                    principal, env.get("QUERY_STRING", "")
                )
                return self.response(
                    self.console.read(path[len("/app/api/") :], console_query, principal)
                )
            from spireagent.console.page import asset, render_shell

            if path in {"/app", "/app/"}:
                return (
                    "200 OK",
                    "text/html; charset=utf-8",
                    render_shell(mode="cloud", api_base="/app/api").encode(),
                )
            if path.startswith("/app/assets/"):
                found = asset(path.removeprefix("/app/assets/"))
                if found is not None:
                    return "200 OK", found[0], found[1]
            return self.response({"error": "not_found"}, "404 Not Found")
        if path.startswith("/v1/identity/"):
            return self.personal_route(env)
        upload = re.fullmatch(r"/v1/uploads/([a-f0-9]{32})(?:/(body|complete))?", path)
        if method == "PUT" and upload and upload[2] == "body":
            self.validate_capability(upload[1], env.get("HTTP_X_UPLOAD_CAPABILITY", ""))
            row = ops.upload(upload[1])
            with ops.transaction() as db:
                if not ops.device_authorized(db, row["device"]):
                    raise BoundaryError("hub", "unauthorized")
            if not isinstance(self.service.staging, LocalStaging):
                raise BoundaryError("hub", "direct_store_upload_required")
            if row["status"] != "awaiting_upload":
                raise BoundaryError("hub", "upload_already_sealed")
            size = json.loads(row["intent"])["archive_bytes"]
            if int(env.get("CONTENT_LENGTH") or "0") != size:
                raise BoundaryError("hub", "archive_size_mismatch")
            self.service.staging.write(upload[1], env["wsgi.input"], size)
            return self.response({"uploaded": True})
        authorization = env.get("HTTP_AUTHORIZATION", "")
        if not authorization.startswith("Bearer "):
            raise BoundaryError("hub", "unauthorized")
        token = authorization[7:]
        if token.startswith(PERSONAL_PREFIX):
            raise BoundaryError("identity", "unauthorized")
        admin = secrets.compare_digest(self.admin_hash, token_hash(token))
        device = None if admin else ops.authenticate(token)
        if path.startswith("/v1/console/"):
            if method != "GET":
                return self.response({"error": "console_read_only"}, "405 Method Not Allowed")
            if admin:
                with ops.transaction() as db:
                    devices = tuple(
                        row[0] for row in db.execute("SELECT id FROM devices ORDER BY id")
                    )
                principal = ConsolePrincipal("operator", devices)
            else:
                assert device is not None
                principal = ConsolePrincipal("collector", (device,))
            return self.response(
                self.console.read(
                    path.removeprefix("/v1/console/"), env.get("QUERY_STRING", ""), principal
                )
            )
        if method == "GET" and path == "/v1/status":
            counts = ops.upload_counts(device)
            return self.response(
                {
                    "schema": "stpd/hub-status-v1",
                    "version": 1,
                    "counts": counts,
                    "paused": ops.paused(),
                }
            )
        if method == "GET" and path in {"/v1/uploads", "/v1/incidents"}:
            query = parse_qs(env.get("QUERY_STRING", ""), strict_parsing=True)
            if set(query) - {"limit", "offset"} or any(len(value) != 1 for value in query.values()):
                raise BoundaryError("hub", "invalid_pagination")
            limit, offset = int(query.get("limit", ["100"])[0]), int(query.get("offset", ["0"])[0])
            if not 1 <= limit <= 100 or offset < 0:
                raise BoundaryError("hub", "invalid_pagination")
            statuses = ("quarantined", "transfer_failed") if path.endswith("incidents") else None
            items = [
                self.upload_status(row)
                for row in ops.uploads(device, limit=limit, offset=offset, statuses=statuses)
            ]
            return self.response(
                {
                    "items": items,
                    "limit": limit,
                    "offset": offset,
                    "next_offset": offset + limit if len(items) == limit else None,
                }
            )
        if method == "POST" and path == "/v1/uploads":
            if device is None:
                raise BoundaryError("hub", "collector_identity_required")
            result = self.service.intent(device, self.body(env))
            if isinstance(self.service.staging, LocalStaging):
                result["upload_headers"]["X-Upload-Capability"] = self.capability(
                    result["upload_id"], int(time.time()) + 900
                )
            return self.response(result, "201 Created")
        if upload:
            row = ops.upload(upload[1], device)
            if method == "POST" and upload[2] == "complete":
                ops.request_verification(row["id"])
                row = ops.upload(row["id"], device)
            elif method != "GET" or upload[2] is not None:
                return self.response({"error": "not_found"}, "404 Not Found")
            return self.response(self.upload_status(row))
        artifact = re.fullmatch(r"/v1/artifacts/([a-f0-9]{64})(?:/payloads/([a-z0-9_]+))?", path)
        if artifact and method == "GET":
            manifest = self.service.store.get_manifest(artifact[1])
            require_artifact_access(
                manifest, project_member=admin, payload_role=artifact[2], store=self.service.store
            )
            if artifact[2] is None:
                return self.response(decode_json(manifest.to_bytes()))
            return (
                "200 OK",
                "application/octet-stream",
                self.service.store.read_payload(manifest.payload(artifact[2])),
            )
        if method == "GET" and path == "/v1/jobs":
            fields = {
                "id",
                "kind",
                "input_id",
                "status",
                "max_seconds",
                "reserved_units",
                "attempt_id",
                "provider_ref",
                "result",
            }
            return self.response(
                {
                    "items": [
                        {key: value for key, value in row.items() if key in fields}
                        for row in ops.jobs()
                    ]
                }
            )
        if not admin:
            raise BoundaryError("hub", "unauthorized")
        if method == "POST" and path == "/v1/jobs":
            body = self.body(env)
            job_id = ops.enqueue(
                body["kind"],
                body["input_id"],
                body["request_key"],
                max_seconds=body["max_seconds"],
                reserved_units=body["reserved_units"],
                budget_limit=self.budget_limit,
                options=body.get("options"),
            )
            return self.response({"job_id": job_id}, "201 Created")
        if method == "POST" and path == "/v1/pause":
            value = self.body(env)["paused"]
            if type(value) is not bool:
                raise BoundaryError("hub", "invalid_pause")
            ops.pause(value)
            return self.response({"paused": value})
        match = re.fullmatch(r"/v1/jobs/([a-f0-9]{32})/cancel", path)
        if match and method == "POST":
            ops.cancel(match[1])
            return self.response({"cancel_requested": True})
        match = re.fullmatch(r"/v1/uploads/([a-f0-9]{32})/retry", path)
        if match and method == "POST":
            ops.retry_upload(match[1])
            return self.response({"retry_authorized": True})
        return self.response({"error": "not_found"}, "404 Not Found")
