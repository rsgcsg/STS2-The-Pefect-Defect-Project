"""Exact native recording-to-model handoff; no browser or gameplay authority."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener
from uuid import uuid4

from spireagent.json_boundary import BoundaryError
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

    def prepare_model(self, runtime: dict[str, Any]) -> dict[str, Any]:
        expected = (runtime.get("environment") or {}).get("runtime_instance_id")
        if not isinstance(expected, str) or not expected:
            raise BoundaryError("local_model", "runtime_game_identity_required")
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
        return observed
