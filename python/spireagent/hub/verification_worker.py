"""Bounded verifier process: malformed evidence cannot take down the API process."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from spireagent.hub.capacity import IMAGE_RESERVE_INODES, RESERVE_INODES, filesystem_capacity

if TYPE_CHECKING:
    from spireagent.hub.database import Operations

DATASET_TIMEOUT_SECONDS = 900
DATASET_CPU_SECONDS = 600


class VerifierCapacityDeferred(Exception):
    """No upload was claimed or attempted; retry accounting must remain unchanged."""


def constrain_worker(*, dataset: bool = False) -> None:
    if sys.platform == "linux":
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (1536 * 1024**2, 1536 * 1024**2))
        cpu = DATASET_CPU_SECONDS if dataset else 120
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (3 * 1024**3, 3 * 1024**3))


def run_verifier(
    arguments: Sequence[str], *, timeout: float = 150, shutdown: threading.Event | None = None,
    required_inodes: int = RESERVE_INODES,
    on_failure: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> bool:
    # A single production verifier needs its bounded scratch reserve before any claim.
    # Capacity shortages leave the upload pending; they are not verification failures.
    # Other platforms keep the portable engineering path, not Linux host qualification.
    if sys.platform == "linux":
        if filesystem_capacity(
            Path(tempfile.gettempdir()), reserve_inodes=max(RESERVE_INODES, required_inodes),
        )["status"] != "ok":
            raise VerifierCapacityDeferred
    # The parent owns temporary storage so a killed child cannot leak expanded bundles.
    with tempfile.TemporaryDirectory(prefix="stpd-verifier-") as scratch:
        return _run_verifier(arguments, timeout, shutdown, scratch, on_failure, should_stop)


def supervise_pending_upload(
    operations: Operations, upload_id: str, arguments: Sequence[str], shutdown: threading.Event,
) -> str:
    """Parent disposition: resource deferral cannot consume a verification attempt."""
    required_inodes = RESERVE_INODES
    if sys.platform == "linux":
        # Intent was bounded and validated by UploadService before durable admission.
        # Only this selected upload is materialized. Sum path separators rather than
        # constructing an unbounded parent set; shared directories are conservatively
        # counted again. Corrupt metadata still goes to the original verifier owner.
        try:
            intent = json.loads(operations.upload(upload_id)["intent"])
            files = intent["transfer_manifest"]["files"]
            required_inodes = max(
                RESERVE_INODES,
                IMAGE_RESERVE_INODES + sum(1 + item["path"].count("/") for item in files),
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
    try:
        completed = run_verifier(arguments, shutdown=shutdown, required_inodes=required_inodes)
    except VerifierCapacityDeferred:
        return "capacity_deferred"
    if completed:
        return "process_completed"
    if shutdown.is_set():
        return "stopping"
    operations.verification_failure(
        upload_id, "verifier_resource_or_process_limit", now=time.time(),
    )
    return "retry_pending"


def _run_verifier(
    arguments: Sequence[str], timeout: float, shutdown: threading.Event | None, scratch: str,
    on_failure: Callable[[str], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> bool:
    def failed(reason: str) -> bool:
        if on_failure:
            on_failure(reason)
        return False

    try:
        process = subprocess.Popen(
            [sys.executable, "-m", "spireagent.hub", "verify", "--isolated", *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={**os.environ, "TMPDIR": scratch, "TEMP": scratch, "TMP": scratch},
        )
    except OSError:
        return failed("worker_start_failed")
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline and not (shutdown and shutdown.is_set()):
            if should_stop and should_stop():
                return failed("worker_cancelled")
            try:
                code = process.wait(timeout=min(0.2, max(0.01, deadline - time.monotonic())))
                if code == 0:
                    return True
                if code == -getattr(signal, "SIGXCPU", 9999):
                    return failed("worker_cpu_limit")
                if code < 0:
                    return failed("worker_killed")
                return failed("worker_exit_failed")
            except subprocess.TimeoutExpired:
                pass
        return failed("worker_interrupted" if shutdown and shutdown.is_set() else "worker_timeout")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
