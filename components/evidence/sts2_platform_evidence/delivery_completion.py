"""Stopped-worker proof that an immutable delivery generation is complete.

This is a local integrity/transfer check, not renewed Human qualification or a
cloud request. The caller owns stopping the game and publishing its active
configuration only when this context exits successfully.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import stat
import tarfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .collection_tool import CollectionTool, canonical, digest, read_json
from .delivery import _session_identity
from .delivery_config import DeliveryConfig
from .delivery_lock import process_lock
from .human_session_bundle import verify_human_session_bundle
from .transfer import DirectoryTransferManifest, _inventory, _sha256_file


@dataclass(frozen=True)
class DeliveryCompletion:
    """Immutable canonical proof; returned dictionaries are independent copies."""

    _payload: bytes

    @property
    def completion_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self._payload) | {"completion_sha256": self.completion_sha256}


def _safe_path(path: Path, *, directory: bool) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("completion_absolute_paths_required")
    for parent in (*reversed(path.parents), path):
        mode = parent.lstat().st_mode
        if stat.S_ISLNK(mode) or (parent != path and not stat.S_ISDIR(mode)):
            raise ValueError("completion_unsafe_path")
    mode = path.lstat().st_mode
    if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
        raise ValueError("completion_unsafe_path")


def _tree(root: Path) -> tuple[tuple[str, int, int, int], ...]:
    """Reject special files and guard replacement separately from public hashes."""
    _safe_path(root, directory=True)
    result = []
    for path in [root, *sorted(root.rglob("*"))]:
        coordination = path.parent == root and path.name in {"outbox.sqlite3-wal", "outbox.sqlite3-shm"}
        try:
            info = path.lstat()
        except FileNotFoundError:
            if coordination:
                continue
            raise
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError("completion_unsafe_path")
        # SQLite reader coordination is neither evidence nor durable identity.
        if coordination:
            continue
        result.append((str(path), info.st_dev, info.st_ino, stat.S_IFMT(info.st_mode)))
    return tuple(result)


def _config_value(config: DeliveryConfig) -> dict[str, Any]:
    value = asdict(config)
    for name in ("recordings_root", "outbox_root", "tool_directory"):
        _safe_path(getattr(config, name), directory=True)
        value[name] = str(getattr(config, name))
    roots = [config.recordings_root, config.outbox_root, config.tool_directory]
    if any(a == b or a in b.parents or b in a.parents for i, a in enumerate(roots) for b in roots[i + 1:]):
        raise ValueError("completion_roots_must_be_separate")
    if config.human_origin_attested is not True:
        raise ValueError("completion_attestation_required")
    return value


def _rows(config: DeliveryConfig) -> list[dict[str, Any]]:
    database = config.outbox_root / "outbox.sqlite3"
    _safe_path(database, directory=False)
    # Do not construct DeliveryOutbox: its initializer creates/migrates tables.
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=1)
    db.row_factory = sqlite3.Row
    try:
        db.execute("BEGIN")
        identity = db.execute("SELECT value FROM config WHERE id=1").fetchone()
        if identity is None or identity[0] != canonical(config.identity).decode():
            raise ValueError("completion_outbox_identity_mismatch")
        return [dict(row) for row in db.execute("SELECT * FROM sessions ORDER BY id")]
    finally:
        db.close()


def _archive_matches(path: Path, transfer: DirectoryTransferManifest) -> None:
    # Read members without extraction. Hashes alone in an editable upload sidecar
    # cannot establish that an archive actually contains the verified bundle.
    expected = {item.path: item for item in transfer.files}
    seen = set()
    try:
        with tarfile.open(path, "r:gz") as archive:
            for member in archive:
                item = expected.get(member.name)
                if not member.isfile() or item is None or member.name in seen or member.size != item.bytes:
                    raise ValueError("completion_archive_membership_mismatch")
                stream = archive.extractfile(member)
                if stream is None:
                    raise ValueError("completion_archive_membership_mismatch")
                with stream:
                    observed = hashlib.file_digest(stream, "sha256").hexdigest()
                if observed != item.sha256:
                    raise ValueError("completion_archive_bytes_mismatch")
                seen.add(member.name)
    except (tarfile.TarError, EOFError) as error:
        raise ValueError("completion_invalid_archive") from error
    if seen != set(expected):
        raise ValueError("completion_archive_membership_mismatch")


def _session(config: DeliveryConfig, tool: CollectionTool, row: dict[str, Any]) -> dict[str, Any]:
    key, source = row["id"], Path(row["source"])
    if (not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{64}", key)
            or source.parent not in {config.recordings_root, config.outbox_root / "recovered-recordings"}
            or row["source"] != str(source)
            or key != digest({"source": str(source)})):
        raise ValueError("completion_enrolled_source_mismatch")
    if row["status"] != "verified":
        raise ValueError("completion_non_verified_session")
    expected = _session_identity(source)
    if canonical(expected).decode() != row["identity"]:
        raise ValueError("completion_sealed_source_changed")
    bundle = config.outbox_root / "bundles" / key
    verified = verify_human_session_bundle(bundle).require_value()
    transfer = DirectoryTransferManifest.from_directory(
        bundle, content_id=verified.bundle_content_id, artifact_type="human-session-bundle")
    if (verified.session_id != expected["session_id"]
            or verified.timeline_id != expected["timeline_id"]
            or verified.worker_id != config.worker_id or verified.campaign_id != config.campaign_id
            or transfer.content_id != row["content_id"]
            or canonical(_inventory(bundle / "raw")) != canonical(expected["raw_files"])
            or DirectoryTransferManifest.read(config.outbox_root / "transfers" / f"{key}.json") != transfer):
        raise ValueError("completion_bundle_identity_mismatch")
    metadata_path = config.outbox_root / "metadata" / f"{key}.json"
    metadata = read_json(metadata_path)
    if canonical(metadata) != canonical({"schema": "sts2.evidence/delivery-metadata-1", **config.identity,
                                        "source_identity": expected, "collection_tool": tool.manifest}):
        raise ValueError("completion_metadata_identity_mismatch")
    archive = config.outbox_root / "archives" / f"{transfer.manifest_sha256}.tar.gz"
    attempt = read_json(archive.with_name(f"{transfer.manifest_sha256}.upload.json"))
    archive_sha, archive_bytes = _sha256_file(archive), archive.stat().st_size
    upload_id = attempt.get("upload_id")
    # Before dafe61f, HubTransport persisted only upload ID and archive hash.
    # Recognize that exact historical shape without modifying its sidecar. The
    # actual archive is still hashed and checked against every transfer member;
    # only this newly derived completion receipt records its observed byte size.
    legacy_attempt = set(attempt) == {"upload_id", "archive_sha256"}
    declared_bytes = attempt.get("archive_bytes")
    if (not isinstance(upload_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", upload_id)
            or attempt.get("archive_sha256") != archive_sha
            or (not legacy_attempt and (type(declared_bytes) is not int or declared_bytes != archive_bytes))):
        raise ValueError("completion_upload_identity_mismatch")
    _archive_matches(archive, transfer)
    receipt_path = config.outbox_root / "receipts" / f"{key}.json"
    receipt = read_json(receipt_path)
    if (canonical(receipt).decode() != row["receipt"]
            or receipt.get("schema") != "stpd/receive-receipt-v1" or receipt.get("status") != "verified"
            or receipt.get("content_id") != transfer.content_id
            or receipt.get("manifest_sha256") != transfer.manifest_sha256
            or not isinstance(receipt.get("receipt_id"), str) or not receipt["receipt_id"]):
        raise ValueError("completion_receipt_mismatch")
    return {"delivery_id": key, "source": str(source), "session_id": verified.session_id,
            "timeline_id": verified.timeline_id, "source_identity_sha256": digest(expected),
            "content_id": transfer.content_id, "transfer_manifest_sha256": transfer.manifest_sha256,
            "metadata_sha256": _sha256_file(metadata_path), "archive_sha256": archive_sha,
            "archive_bytes": archive_bytes, "upload_id": upload_id,
            "receipt_id": receipt["receipt_id"], "receipt_sha256": _sha256_file(receipt_path)}


def _snapshot(config: DeliveryConfig) -> tuple[DeliveryCompletion, object]:
    value = _config_value(config)
    guards = tuple(_tree(root) for root in (config.recordings_root, config.outbox_root, config.tool_directory))
    tool = CollectionTool(config.tool_directory, config.tool_release_id, dotnet=config.dotnet)
    rows = _rows(config)
    originals = {str(path): path for path in config.recordings_root.iterdir()}
    remaining = set(originals)
    recovered_files: set[str] = set()
    for row in rows:
        source = Path(row["source"])
        if str(source) in remaining:
            remaining.remove(str(source))
            continue
        if source.parent != config.outbox_root / "recovered-recordings":
            raise ValueError("completion_recording_inventory_mismatch")
        recovery = read_json(source / "recording-recovery.json")
        manifest = read_json(source / "recording-manifest.json")
        original = config.recordings_root / manifest["session_id"]
        if str(original) not in remaining or (original / "session-close-receipt.json").exists():
            raise ValueError("completion_recovery_origin_mismatch")
        inventory = {name: {"bytes": size, "sha256": sha} for name, size, sha in _inventory(original)
                     if name != "recording-owner.lock"}
        if (inventory != recovery.get("original_files")
                or digest(inventory) != recovery.get("original_inventory_sha256")):
            raise ValueError("completion_recovery_origin_changed")
        remaining.remove(str(original))
        recovered_files.update(path.relative_to(config.outbox_root).as_posix()
                               for path in source.rglob("*") if path.is_file())
    if remaining:
        raise ValueError("completion_recording_inventory_mismatch")
    sessions = [_session(config, tool, row) for row in rows]
    expected_files = {"outbox.sqlite3", "outbox.sqlite3-wal", "outbox.sqlite3-shm", "worker.lock"}
    expected_files.update(recovered_files)
    for session in sessions:
        key, transfer_id = session["delivery_id"], session["transfer_manifest_sha256"]
        expected_files.update(f"{area}/{key}.json" for area in ("transfers", "metadata", "receipts", "projections"))
        expected_files.update(f"archives/{transfer_id}.{suffix}" for suffix in ("tar.gz", "upload.json"))
        expected_files.update(f"bundles/{key}/{p}" for p, _, _ in _inventory(config.outbox_root / "bundles" / key))
    # Extra empty directories count too; no untracked prepared/partial queue is silently retired.
    expected_directories = {"."}
    for name in expected_files:
        expected_directories.update(parent.as_posix() for parent in Path(name).parents)
    files = []
    for path in sorted(config.outbox_root.rglob("*")):
        relative = path.relative_to(config.outbox_root).as_posix()
        if path.is_dir():
            if relative not in expected_directories:
                raise ValueError("completion_extra_outbox_entry")
        elif relative not in expected_files:
            raise ValueError("completion_extra_outbox_entry")
        elif relative not in {"outbox.sqlite3", "outbox.sqlite3-wal", "outbox.sqlite3-shm", "worker.lock"}:
            files.append((relative, path.stat().st_size, _sha256_file(path)))
    # The public proof excludes local telemetry and SQLite physical representation.
    # Full logical rows and all persistent auxiliary bytes still guard this context.
    durable_files = [row for row in files if not row[0].startswith("projections/")
                     and not row[0].endswith(".upload.json")]
    raw_inventory = {"files": _inventory(config.recordings_root),
                     "directories": sorted(path.relative_to(config.recordings_root).as_posix()
                                           for path in config.recordings_root.rglob("*") if path.is_dir())}
    receipt = DeliveryCompletion(canonical({
        "schema": "sts2.evidence/delivery-completion-1", "config_sha256": digest(value),
        **{name: value[name] for name in ("recordings_root", "outbox_root", "tool_directory",
                                         "tool_release_id", "worker_id", "campaign_id")},
        "session_count": len(sessions), "raw_inventory_sha256": digest(raw_inventory),
        "outbox_sha256": digest(durable_files), "sessions": sessions,
    }))
    return receipt, (guards, digest(rows), digest(files))


@contextmanager
def completed_delivery(config: DeliveryConfig) -> Iterator[DeliveryCompletion]:
    """Hold worker ownership while checking a complete, unchanged generation.

    Requires existing distinct absolute non-symlink roots and an existing outbox.
    Every recording must be sealed, enrolled and transferred with a verified
    receipt. Failed Human decisions remain failed; their verified bundles qualify
    for transfer completion. This never runs packing, a native audit or network I/O.

    The receipt is provisional until normal context exit rechecks the entire
    snapshot. A caller that publishes inside the context must roll back if exit
    raises. Game/process lifecycle and same-consent enrollment remain caller-owned.
    """
    _config_value(config)
    _safe_path(config.outbox_root / "outbox.sqlite3", directory=False)
    _tree(config.outbox_root)  # Reject a symlink lock/SQLite sidecar before opening either.
    with process_lock(config.outbox_root):
        try:
            before = _snapshot(config)
            yield before[0]
            if _snapshot(config) != before:
                raise ValueError("completion_generation_changed")
        except (sqlite3.Error, KeyError, TypeError) as error:
            raise ValueError("completion_invalid_evidence") from error
