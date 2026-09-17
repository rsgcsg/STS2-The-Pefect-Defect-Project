"""Disposable fixed preview selections referencing the private verified source index."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from spireagent.json_boundary import BoundaryError, FrozenObject, json_bytes

from .contracts import ResearchTransitionV2
from .decision_cache import MAX_ENTRY_BYTES, VerifiedSourceCache
from .decision_dataset import DecisionDataset, _identity
from .decision_index import INDEX_SCHEMA
from .decision_spool import DecisionSpool


class PreviewCache:
    """A speed-up only: eviction/corruption requires reproducing the original preview.

    The key binds exact source manifests and rules; owner binds verifier/source/lock.
    Neither a public request nor a completed job summary can populate selected rows.
    """

    def __init__(self, cache: VerifiedSourceCache) -> None:
        self.cache = cache
        with cache._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS decision_preview_cache("
                       "key TEXT PRIMARY KEY,body BLOB NOT NULL,sha256 TEXT NOT NULL)")

    def _key(self, selection: dict[str, Any]) -> str:
        return hashlib.sha256(json_bytes([self.cache.owner, selection])).hexdigest()

    def put(self, selection: dict[str, Any], dataset: DecisionDataset) -> None:
        refs = []
        source_keys: dict[str, str] = {}
        with self.cache._connect() as db:
            for record in dataset.records:
                source = hashlib.sha256(json_bytes([
                    INDEX_SCHEMA, self.cache.owner, record.provenance.bundle_sha256,
                ])).hexdigest()
                if source not in source_keys:
                    header = db.execute("SELECT rows_key FROM decision_source_index WHERE key=?",
                                        (source,)).fetchone()
                    if header is None:
                        return
                    source_keys[source] = header[0]
                source = source_keys[source]
                row = db.execute(
                    "SELECT ordinal,body FROM decision_source_rows "
                    "WHERE source=? AND transition_id=?", (source, record.transition_id),
                ).fetchone()
                if row is None:
                    return  # Bounded source index eviction never removes source eligibility.
                refs.append([source, row[0], hashlib.sha256(row[1]).hexdigest()])
            body = json_bytes({"logical_id": dataset.logical_id,
                               "report": dataset.report.value(), "rows": refs})
            if len(body) > MAX_ENTRY_BYTES:
                return
            db.execute("INSERT OR REPLACE INTO decision_preview_cache VALUES(?,?,?)",
                       (self._key(selection), body, hashlib.sha256(body).hexdigest()))
            # This is disposable acceleration, not the authoritative durable job history.
            db.execute("DELETE FROM decision_preview_cache WHERE rowid NOT IN "
                       "(SELECT rowid FROM decision_preview_cache ORDER BY rowid DESC LIMIT 32)")

    def get(self, selection: dict[str, Any], expected: str) -> DecisionDataset | None:
        with self.cache._connect() as db:
            row = db.execute("SELECT body,sha256 FROM decision_preview_cache WHERE key=?",
                             (self._key(selection),)).fetchone()
            if row is None:
                return None
            try:
                if hashlib.sha256(row[0]).hexdigest() != row[1]:
                    raise ValueError("preview checksum")
                value = json.loads(row[0])
                if value["logical_id"] != expected:
                    raise ValueError("preview identity")
                spool = DecisionSpool()
                for source, ordinal, checksum in value["rows"]:
                    record_row = db.execute(
                        "SELECT body FROM decision_source_rows WHERE source=? AND ordinal=?",
                        (source, ordinal),
                    ).fetchone()
                    if record_row is None or hashlib.sha256(record_row[0]).hexdigest() != checksum:
                        raise ValueError("preview row missing or corrupt")
                    record = ResearchTransitionV2.decode(json.loads(record_row[0]))
                    identity = _identity(record)
                    spool[identity] = record
                    spool.select(identity)
                result = DecisionDataset(spool.selected(), FrozenObject.of(value["report"]))
                if result.logical_id != expected:
                    raise ValueError("preview changed")
                self.cache.preview_hits += 1
                return result
            except (ValueError, KeyError, TypeError, BoundaryError):
                db.execute("DELETE FROM decision_preview_cache WHERE key=?",
                           (self._key(selection),))
                return None
