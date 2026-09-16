"""Explicit sharing of one finalized local Agent evaluation, never Human consent."""

from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from spireagent.encoding import canonical_json
from spireagent.json_boundary import BoundaryError, digest
from spireagent.live_evaluation import EXPECTED, SHARE_SCHEMA, encoded_evidence
from spireagent.policy_files import _object_file
from spireagent.workbench.developer import atomic_json
from spireagent.workbench.member_client import MemberClient

if TYPE_CHECKING:
    from spireagent.workbench.local_models import LocalModelService


class EvaluationSharing:
    def __init__(self, models: LocalModelService, members: MemberClient) -> None:
        self.models, self.members = models, members
        self.lock = threading.RLock()
        self.thread: threading.Thread | None = None
        self.cancel = threading.Event()
        self.owner = ""
        self.operation: dict[str, Any] = {"status": "idle"}

    def status(self) -> dict[str, Any]:
        owner = hashlib.sha256(self.members.token().encode()).hexdigest()
        with self.lock:
            if self.owner and owner != self.owner:
                return {"status": "idle"}
            return dict(self.operation)

    def share(self, evaluation_id: str, authorized: object) -> dict[str, Any]:
        identity = digest(evaluation_id, "evaluation.id")
        if authorized is not True:
            raise BoundaryError("evaluation", "explicit_evaluation_sharing_required")
        token = self.members.token()
        with self.lock:
            if self.thread is not None and self.thread.is_alive():
                raise BoundaryError("evaluation", "evaluation_share_in_progress")
            self.owner = hashlib.sha256(token.encode()).hexdigest()
            self.operation = {"status": "preparing", "evaluation_id": identity}
            self.cancel.clear()
            self.thread = threading.Thread(target=self._share, args=(identity, token), daemon=True)
            self.thread.start()
            return dict(self.operation)

    def _update(self, **values: Any) -> None:
        with self.lock:
            self.operation.update(values)

    def _share(self, identity: str, token: str) -> None:
        try:
            report = next(
                (item for item in self.models.evaluations() if item["evaluation_id"] == identity),
                None,
            )
            if report is None or report.get("evidence_verification") != "pass":
                raise BoundaryError("evaluation", "verified_local_evaluation_required")
            run_id = report.get("run_id")
            if not isinstance(run_id, str) or re.fullmatch(r"run-[a-f0-9-]{36}", run_id) is None:
                raise BoundaryError("evaluation", "invalid_local_run_id")
            directory = self.models.directory / "agent-runs" / run_id
            if directory.is_symlink():
                raise BoundaryError("evaluation", "agent_evidence_directory_required")
            manifest = _object_file(directory / "manifest.json")
            expected = {key: manifest.get(key) for key in EXPECTED}
            if any(
                expected.get(key) != report.get(report_key)
                for key, report_key in (
                    ("run_id", "run_id"),
                    ("policy_artifact_sha256", "model_sha256"),
                    ("policy_manifest_sha256", "policy_manifest_sha256"),
                    ("runtime_code_sha256", "runtime_code_sha256"),
                )
            ):
                raise BoundaryError("evaluation", "local_evaluation_identity_drift")
            files = encoded_evidence(directory, expected, report["evidence_content_id"])
            account = self.members.account
            device = account.device().get("device_id")
            if not device:
                raise BoundaryError("evaluation", "connected_device_required")
            if self.cancel.is_set() or self.members.token() != token:
                raise BoundaryError("evaluation", "evaluation_share_session_changed")
            self._update(status="uploading")
            receipt = account.request(
                "/v1/identity/member/live-evaluations",
                body={
                    "schema": SHARE_SCHEMA,
                    "device_id": device,
                    "share_authorized": True,
                    "expected": expected,
                    "files": files,
                },
                token=token,
            )
            if (
                receipt.get("schema") != "stpd/shared-evaluation-receipt-v1"
                or receipt.get("status") != "verified"
                or receipt.get("evidence_content_id") != report.get("evidence_content_id")
            ):
                raise BoundaryError("evaluation", "evaluation_share_receipt_mismatch")
            digest(receipt.get("artifact_id"), "evaluation.artifact_id")
            # Keep the exact receipt even if the browser logged out during the POST;
            # logout cannot undo bytes already submitted with explicit authorization.
            target = (
                self.models.directory
                / "evaluation-shares"
                / identity
                / (receipt["artifact_id"] + ".json")
            )
            self._save_receipt(target, receipt)
            self._update(status="shared", receipt=receipt)
        except (OSError, ValueError, KeyError, BoundaryError) as error:
            code = error.code if isinstance(error, BoundaryError) else "evaluation_share_failed"
            self._update(status="unknown" if code == "request_unknown" else "failed", error=code)

    @staticmethod
    def _save_receipt(target: Path, receipt: dict[str, Any]) -> None:
        if target.exists() or target.is_symlink():
            previous = _object_file(target)
            if canonical_json(previous) != canonical_json(receipt):
                raise BoundaryError("evaluation", "evaluation_share_receipt_changed")
        else:
            atomic_json(target, receipt)

    def close(self) -> None:
        self.cancel.set()
