from __future__ import annotations

import dataclasses
import json
import os
import shutil
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path

from sts2_platform_evidence.collection_tool import CollectionTool, canonical, digest
from sts2_platform_evidence.delivery import DeliveryOutbox, _atomic_json
from sts2_platform_evidence.delivery_completion import completed_delivery
from sts2_platform_evidence.delivery_config import DeliveryConfig
from sts2_platform_evidence.delivery_http import HubTransport
from sts2_platform_evidence.delivery_lock import process_lock
from sts2_platform_evidence.transfer import _inventory, _sha256_file
from tests import test_delivery as delivery_tests


class DeliveryCompletionTests(unittest.TestCase):
    setUp = delivery_tests.DeliveryTests.setUp
    tearDown = delivery_tests.DeliveryTests.tearDown
    _write = delivery_tests.DeliveryTests._write
    _stream = delivery_tests.DeliveryTests._stream
    _rows = delivery_tests.DeliveryTests._rows
    _bundle = delivery_tests.DeliveryTests._bundle
    _object = delivery_tests.DeliveryTests._object
    _reseal = delivery_tests.DeliveryTests._reseal

    def _ready(self, *, failed_only=False):
        self.root = self.root.resolve()
        bundle = self._bundle(failed_only=failed_only)
        manifest = json.loads((bundle / "raw/recording-manifest.json").read_text())
        manifest["close_schema_version"] = 1
        self._write(bundle / "raw/recording-manifest.json", manifest)
        self._write(bundle / "raw/session-close-receipt.json", {
            "schema": "sts2.human-annotator/session-close-1", "status": "closed",
            "session_id": manifest["session_id"], "timeline_id": manifest["timeline_id"],
            "closed_at": "2026-09-15T00:00:00Z"})
        self._reseal(bundle)
        self.source = self.root / "recordings/session"
        shutil.copytree(bundle / "raw", self.source)
        tool = self.root / "tool"
        tool.mkdir()
        (tool / "platform-bom.json").write_text("{}")
        (tool / "sts2-human-annotator.dll").write_bytes(b"fixture")
        identity = {"worktree": "clean", "source_revision": "c" * 40,
                    "entrypoint": "sts2-human-annotator.dll",
                    "supported_recording_schema": "sts2.human-annotator/recording-manifest-2",
                    "files": [{"path": p, "bytes": n, "sha256": h} for p, n, h in _inventory(tool)]}
        release_id = digest(identity)
        _atomic_json(tool / "collection-tool.json", {
            "schema": "sts2.evidence/collection-tool-1", "identity": identity, "release_id": release_id})
        owner = CollectionTool(tool, release_id)
        bm = json.loads((bundle / "session-bundle-manifest.json").read_text())
        self.config = DeliveryConfig(self.source.parent, self.root / "outbox", tool, release_id,
                                     bm["worker_id"], bm["campaign_id"], True,
                                     "https://hub.example", ["storage.example"])
        self.outbox = DeliveryOutbox(self.config.outbox_root, **self.config.identity)
        self.assertEqual(self.outbox.reconcile(self.config.recordings_root)["enqueued"], 1)
        packer = delivery_tests.FixturePacker(bundle)
        packer.release_id, packer.manifest = owner.release_id, owner.manifest
        transport = HubTransport("https://hub.example", "fixture-token", self.outbox.root / "archives",
                                 allowed_upload_hosts=["storage.example"])

        def receive(directory, transfer, metadata):
            archive = transport._archive(directory, transfer)
            _atomic_json(archive.with_name(f"{transfer.manifest_sha256}.upload.json"), {
                "upload_id": "fixture-upload", "archive_sha256": _sha256_file(archive),
                "archive_bytes": archive.stat().st_size, "status": "verified", "observed_at": "old-time"})
            return delivery_tests.DeliveryTests.receive(directory, transfer, metadata)

        self.assertEqual(self.outbox.drain_one(packer, receive)["status"], "verified")
        self.key = digest({"source": str(self.source)})
        self.database = self.outbox.root / "outbox.sqlite3"

    def _proof(self):
        with completed_delivery(self.config) as receipt:
            result = receipt.to_dict()
        return result

    def _require_symlink_support(self):
        """Probe symlink support before mutating any durable test fixture."""
        target = self.root / "symlink-probe-target"
        link = self.root / "symlink-probe-link"
        target.write_bytes(b"probe")
        try:
            link.symlink_to(target)
        except (NotImplementedError, OSError) as error:
            # Windows developer environments commonly deny symbolic-link
            # creation without SeCreateSymbolicLinkPrivilege.  Skip only the
            # symlink assertions; callers must clean up before doing so.
            link.unlink(missing_ok=True)
            target.unlink(missing_ok=True)
            if os.name == "nt" and (
                isinstance(error, NotImplementedError)
                or getattr(error, "winerror", None) == 1314
            ):
                self.skipTest("symbolic-link creation privilege is unavailable")
            raise
        else:
            link.unlink()
            target.unlink()

    def _sql(self, query, parameters=()):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute(query, parameters)

    def test_complete_receipt_is_immutable_stable_and_holds_worker_lock(self):
        self._ready()
        original = _inventory(self.source)
        db_bytes = self.database.read_bytes()
        with completed_delivery(self.config) as receipt:
            with self.assertRaises(dataclasses.FrozenInstanceError):
                receipt._payload = b"{}"
            first = receipt.to_dict()
            mutated = receipt.to_dict()
            mutated["sessions"].clear()
            self.assertEqual(receipt.to_dict(), first)
            with self.assertRaisesRegex(ValueError, "already owns"):
                with process_lock(self.outbox.root):
                    self.fail("worker acquired completion lock")
        self.assertEqual(first, self._proof())
        self.assertEqual(first["completion_sha256"], digest({k: v for k, v in first.items() if k != "completion_sha256"}))
        self.assertEqual(first["session_count"], 1)
        self.assertEqual(_inventory(self.source), original)
        self.assertEqual(self.database.read_bytes(), db_bytes)
        with process_lock(self.outbox.root):
            pass

    def test_telemetry_and_file_times_do_not_change_public_completion(self):
        self._ready()
        before = self._proof()
        attempt = next((self.outbox.root / "archives").glob("*.upload.json"))
        value = json.loads(attempt.read_text()) | {"observed_at": "new-time"}
        _atomic_json(attempt, value)
        projection = self.outbox.root / "projections" / f"{self.key}.json"
        _atomic_json(projection, json.loads(projection.read_text()) | {"observed_at": "new-time"})
        os.utime(self.source, None)
        self.assertEqual(self._proof(), before)

    def test_historical_upload_identity_is_verified_without_rewriting_it(self):
        self._ready()
        expected = self._proof()
        attempt = next((self.outbox.root / "archives").glob("*.upload.json"))
        current = json.loads(attempt.read_bytes())
        # HubTransport before dafe61f persisted exactly these two fields.
        _atomic_json(attempt, {key: current[key] for key in ("upload_id", "archive_sha256")})
        before = attempt.read_bytes()
        raw_before = _inventory(self.config.recordings_root)
        outbox_before = _inventory(self.config.outbox_root)
        self.assertEqual(self._proof(), expected)
        self.assertEqual(attempt.read_bytes(), before)
        self.assertEqual(_inventory(self.config.recordings_root), raw_before)
        self.assertEqual(_inventory(self.config.outbox_root), outbox_before)

    def test_upload_size_is_strict_and_only_exact_historical_shape_may_omit_it(self):
        self._ready()
        attempt = next((self.outbox.root / "archives").glob("*.upload.json"))
        current = json.loads(attempt.read_bytes())
        legacy = {key: current[key] for key in ("upload_id", "archive_sha256")}
        invalid = [
            current | {"archive_bytes": size}
            for size in (None, True, False, str(current["archive_bytes"]),
                         float(current["archive_bytes"]), 0, current["archive_bytes"] + 1)
        ]
        invalid.extend((
            legacy | {"status": "verified"},
            legacy | {"observed_at": "unknown"},
            legacy | {"unexpected": "field"},
            legacy | {"archive_sha256": "f" * 64},
            {"upload_id": current["upload_id"]},
        ))
        for value in invalid:
            with self.subTest(value=value):
                _atomic_json(attempt, value)
                before = attempt.read_bytes()
                with self.assertRaisesRegex(ValueError, "completion_upload_identity_mismatch"):
                    self._proof()
                self.assertEqual(attempt.read_bytes(), before)

    def test_historical_attempt_cannot_hide_archive_tampering_or_change_during_completion(self):
        self._ready()
        attempt = next((self.outbox.root / "archives").glob("*.upload.json"))
        current = json.loads(attempt.read_bytes())
        legacy = {key: current[key] for key in ("upload_id", "archive_sha256")}
        _atomic_json(attempt, legacy)
        with self.assertRaisesRegex(ValueError, "generation_changed"):
            with completed_delivery(self.config):
                # Both snapshots are valid, but an observation change inside the
                # stopped generation guard must still invalidate the operation.
                _atomic_json(attempt, current)
        _atomic_json(attempt, legacy)
        archive = next((self.outbox.root / "archives").glob("*.tar.gz"))
        with archive.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "completion_upload_identity_mismatch"):
            self._proof()

    def test_verified_failed_only_evidence_is_complete_without_reclassification(self):
        self._ready(failed_only=True)
        self.assertEqual(self._proof()["session_count"], 1)
        self.assertEqual((self.source / "canonical-transitions.jsonl").read_text(), "")
        self.assertIn("transition_unknown", (self.source / "semantic-boundary-trace.jsonl").read_text())

    def test_live_worker_and_all_nonverified_states_block(self):
        self._ready()
        with process_lock(self.outbox.root):
            with self.assertRaisesRegex(ValueError, "already owns"):
                self._proof()
        for status in ("pending", "auth_blocked", "incident", "quarantined", "unknown"):
            with self.subTest(status=status):
                self._sql("UPDATE sessions SET status=?", (status,))
                with self.assertRaisesRegex(ValueError, "non_verified"):
                    self._proof()

    def test_committed_wal_is_read_and_empty_existing_generation_is_complete(self):
        self._ready()
        # Keep the writer connection open: its committed status is still in WAL.
        with closing(sqlite3.connect(self.database)) as connection:
            connection.execute("UPDATE sessions SET status='pending'")
            connection.commit()
            self.assertTrue(self.database.with_name("outbox.sqlite3-wal").exists())
            with self.assertRaisesRegex(ValueError, "non_verified"):
                self._proof()
        empty_recordings, empty_outbox = self.root / "empty-recordings", self.root / "empty-outbox"
        empty_recordings.mkdir()
        config = dataclasses.replace(self.config, recordings_root=empty_recordings, outbox_root=empty_outbox)
        DeliveryOutbox(empty_outbox, **config.identity)
        with completed_delivery(config) as receipt:
            self.assertEqual(receipt.to_dict()["sessions"], [])

    def test_absent_database_is_not_initialized_and_old_schema_is_not_migrated(self):
        self._ready()
        for column in ("auth_context", "summary", "summary_canonical", "summary_real_failures"):
            self._sql(f"ALTER TABLE sessions DROP COLUMN {column}")
        old = self.database.read_bytes()
        self._proof()
        self.assertEqual(self.database.read_bytes(), old)
        self.database.unlink()
        with self.assertRaises(OSError):
            self._proof()
        self.assertFalse(self.database.exists())

    def test_extra_missing_and_unsealed_recordings_block(self):
        self._ready()
        for kind in ("empty_directory", "unsealed", "extra_file", "missing"):
            with self.subTest(kind=kind):
                extra = self.source.parent / "extra"
                if kind == "empty_directory":
                    extra.mkdir()
                elif kind == "unsealed":
                    shutil.copytree(self.source, extra)
                    (extra / "session-close-receipt.json").unlink()
                elif kind == "extra_file":
                    extra.write_text("unknown")
                else:
                    self.source.rename(self.root / "retained-session")
                with self.assertRaises(ValueError):
                    self._proof()
                if extra.is_dir():
                    shutil.rmtree(extra)
                elif extra.exists():
                    extra.unlink()
                if kind == "missing":
                    (self.root / "retained-session").rename(self.source)
        seal = self.source / "session-close-receipt.json"
        seal.unlink()
        with self.assertRaises((ValueError, OSError)):
            self._proof()

    def test_tamper_at_every_durable_boundary_blocks(self):
        self._ready()
        paths = [self.source / "recording-manifest.json",
                 self.outbox.root / "bundles" / self.key / "raw/recording-manifest.json",
                 *(self.outbox.root / area / f"{self.key}.json" for area in ("transfers", "metadata", "receipts")),
                 *sorted((self.outbox.root / "archives").iterdir()),
                 self.config.tool_directory / "sts2-human-annotator.dll"]
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaises((ValueError, OSError)):
                    self._proof()
                path.write_bytes(original)
        for field, value in (("source", str(self.root / "outside")), ("id", "../escape"),
                             ("identity", "{}"), ("content_id", "f" * 64), ("receipt", "{}")):
            with self.subTest(field=field):
                with closing(sqlite3.connect(self.database)) as connection:
                    before = connection.execute(f"SELECT {field} FROM sessions").fetchone()[0]
                self._sql(f"UPDATE sessions SET {field}=?", (value,))
                with self.assertRaises(ValueError):
                    self._proof()
                self._sql(f"UPDATE sessions SET {field}=?", (before,))
        self._sql("UPDATE config SET value='{}'")
        with self.assertRaisesRegex(ValueError, "outbox_identity"):
            self._proof()

    def test_archive_rehash_cannot_hide_wrong_bundle_members(self):
        self._ready()
        archive = next((self.outbox.root / "archives").glob("*.tar.gz"))
        other = self.root / "other"
        other.mkdir()
        (other / "wrong").write_bytes(b"different payload")
        import tarfile
        with tarfile.open(archive, "w:gz") as stream:
            stream.add(other / "wrong", arcname="wrong")
        sidecar = archive.with_name(archive.name.removesuffix(".tar.gz") + ".upload.json")
        _atomic_json(sidecar, json.loads(sidecar.read_text()) | {
            "archive_sha256": _sha256_file(archive), "archive_bytes": archive.stat().st_size})
        with self.assertRaisesRegex(ValueError, "archive_membership"):
            self._proof()
        current = json.loads(sidecar.read_bytes())
        _atomic_json(sidecar, {key: current[key] for key in ("upload_id", "archive_sha256")})
        with self.assertRaisesRegex(ValueError, "archive_membership"):
            self._proof()

    def test_symlinks_block_before_following(self):
        self._ready()
        self._require_symlink_support()
        for path in (self.outbox.root / "worker.lock", self.database,
                     self.source / "recording-manifest.json", self.config.tool_directory,
                     self.source.parent):
            with self.subTest(path=path):
                # Ensure the persistent worker lock exists before replacing it.
                self._proof()
                saved = path.with_name(path.name + "-saved")
                path.rename(saved)
                path.symlink_to(saved, target_is_directory=saved.is_dir())
                with self.assertRaisesRegex(ValueError, "unsafe_path"):
                    self._proof()
                path.unlink()
                saved.rename(path)

    def test_unknown_outbox_entries_block(self):
        self._ready()
        for name in ("partial", "bundles/unknown"):
            path = self.outbox.root / name
            path.mkdir()
            with self.assertRaisesRegex(ValueError, "extra_outbox"):
                self._proof()
            path.rmdir()

    def test_exit_rechecks_content_config_logical_rows_and_directory_replacement(self):
        self._ready()
        with self.assertRaises(ValueError):
            with completed_delivery(self.config):
                (self.source / "late.json").write_text("{}")
        (self.source / "late.json").unlink()
        with self.assertRaisesRegex(ValueError, "generation_changed"):
            with completed_delivery(self.config):
                self.config.allowed_upload_hosts.append("other.example")
        self.config.allowed_upload_hosts.pop()
        with self.assertRaisesRegex(ValueError, "generation_changed"):
            with completed_delivery(self.config):
                self._sql("UPDATE sessions SET attempts=attempts+1")
        with self.assertRaisesRegex(ValueError, "generation_changed"):
            with completed_delivery(self.config):
                saved = self.root / "old-directory"
                self.source.rename(saved)
                shutil.copytree(saved, self.source)
        with self.assertRaisesRegex(RuntimeError, "caller failed"):
            with completed_delivery(self.config):
                raise RuntimeError("caller failed")
        with process_lock(self.outbox.root):
            pass


if __name__ == "__main__":
    unittest.main()
