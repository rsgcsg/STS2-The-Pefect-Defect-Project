"""Exact native recording-to-model handoff; no browser or gameplay authority."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from spireagent.json_boundary import BoundaryError
from spireagent.workbench.developer import endpoint
from spireagent.workbench.hub_client import NoRedirect


class NativeTasks:
    address = "http://127.0.0.1:15528"

    def __init__(self) -> None:
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, body: dict[str, Any] | None = None) -> dict[str, Any]:
        route = "/v1/tasks/status" if body is None else "/v1/tasks/prepare-model"
        request = Request(
            self.address + route,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=15 if body is not None else 2) as response:
                raw = response.read(16385)
            if len(raw) > 16384:
                raise ValueError
            value = json.loads(raw)
            if (
                not isinstance(value, dict)
                or value.get("schema") != "sts2.platform/task-status-1"
                or not isinstance(value.get("runtime_instance_id"), str)
                or type(value.get("ready_for_model")) is not bool
                or "recording_session_id" not in value
                or value.get("recording_lifecycle")
                not in {"ready", "recording", "paused", "closing", "closed"}
                or (
                    value.get("recording_session_id") is not None
                    and not isinstance(value["recording_session_id"], str)
                )
                or (
                    value.get("ready_for_model")
                    and value.get("recording_lifecycle") not in {"ready", "closed"}
                )
            ):
                raise ValueError
            return value
        except (HTTPError, URLError, OSError, ValueError, TypeError):
            raise BoundaryError(
                "local_model", "native_task_command_unknown" if body else "native_task_unavailable"
            ) from None

    @staticmethod
    def bound_connector(value: object) -> str:
        """Only the endpoint persisted when this Runtime was launched is usable."""
        try:
            address = endpoint(value)
            if not address.startswith(
                ("http://127.0.0.1:", "http://localhost:", "http://[::1]:")
            ):
                raise ValueError
            return address
        except (BoundaryError, ValueError, TypeError):
            raise BoundaryError("local_model", "runtime_connector_binding_required") from None

    def connector_instance(self, connector_endpoint: object) -> str:
        address = self.bound_connector(connector_endpoint)
        request = Request(
            address + "/api/player-environment/capabilities",
            headers={"Accept": "application/json"},
        )
        try:
            with self.opener.open(request, timeout=2) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError
            value = json.loads(raw)
            # Consume just the public identity contract. Connector/Runtime still
            # own capability validation, control and gameplay legality.
            required = {
                "protocol_version": "1.0.0",
                "snapshot_schema": "sts2.player-environment/snapshot-1",
                "action_schema": "sts2.player-environment/action-1",
                "receipt_schema": "sts2.player-environment/receipt-1",
                "control_schema": "sts2.player-environment/control-1",
            }
            if not isinstance(value, dict) or any(
                value.get(key) != expected for key, expected in required.items()
            ):
                raise ValueError
            host = value.get("host")
            identity = host.get("runtime_instance_id") if isinstance(host, dict) else None
            if not isinstance(identity, str) or not identity:
                raise ValueError
            return identity
        except (HTTPError, URLError, OSError, ValueError, TypeError):
            raise BoundaryError("local_model", "connector_identity_unavailable") from None

    @staticmethod
    def runtime_instance(runtime: dict[str, Any]) -> str | None:
        if "environment" not in runtime:
            raise BoundaryError("local_model", "runtime_game_identity_required")
        environment = runtime["environment"]
        if environment is None:
            return None
        identity = environment.get("runtime_instance_id") if isinstance(environment, dict) else None
        if not isinstance(identity, str) or not identity:
            raise BoundaryError("local_model", "runtime_game_identity_required")
        return identity

    @staticmethod
    def confirm_runtime(runtime: dict[str, Any], expected: str) -> None:
        instance = NativeTasks.runtime_instance(runtime)
        if instance is not None and instance != expected:
            raise BoundaryError("local_model", "native_task_game_identity_mismatch")

    def prepare_model(
        self, runtime: dict[str, Any], connector_endpoint: object
    ) -> dict[str, Any]:
        instance = self.runtime_instance(runtime)
        expected = self.connector_instance(connector_endpoint)
        # Human Runtime has no environment before its first tick. Do not run a
        # tick to discover identity: read the bound Connector and compare bridge.
        if instance is not None and instance != expected:
            raise BoundaryError("local_model", "native_task_game_identity_mismatch")
        observed = self.request()
        if observed["runtime_instance_id"] != expected:
            raise BoundaryError("local_model", "native_task_game_identity_mismatch")
        if not observed["ready_for_model"]:
            # One bounded request only. Uncertain Close is never automatically retried.
            observed = self.request(
                {
                    "runtime_instance_id": expected,
                    "recording_session_id": observed["recording_session_id"],
                    "command_id": str(uuid4()),
                }
            )
        if observed["runtime_instance_id"] != expected:
            raise BoundaryError("local_model", "native_task_game_identity_mismatch")
        if not observed["ready_for_model"]:
            raise BoundaryError("local_model", "recording_close_pending_or_failed")
        if self.connector_instance(connector_endpoint) != expected:
            raise BoundaryError("local_model", "native_task_game_identity_mismatch")
        return observed
