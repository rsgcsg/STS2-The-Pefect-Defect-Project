"""Only exact-byte, exact-owner private results may avoid a repeated native verifier call."""

import gzip
from pathlib import Path
from unittest.mock import patch

import pytest
from test_decision_store import setup

from spireagent.json_boundary import BoundaryError
from stpd.fullrun.decision_cache import VerifiedSourceCache
from stpd.fullrun.decision_dataset import SelectionRules, select_decisions
from stpd.fullrun.decision_store import preview, publish
from stpd.fullrun.platform_bundle3 import PlatformBundle3SourceAdapter


def test_persistent_cache_reuses_verified_original_and_matches_fresh(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    project = PlatformBundle3SourceAdapter.project
    with patch.object(PlatformBundle3SourceAdapter, "project", autospec=True,
                      side_effect=project) as call:
        first = preview(owner.store, (source,), SelectionRules(),
                        cache=VerifiedSourceCache(owner.operations.path, "owner-a"))
        assert call.call_count == 1
        cache = VerifiedSourceCache(owner.operations.path, "owner-a")
        second = preview(owner.store, (source,), SelectionRules(), cache=cache)
        assert first == second and call.call_count == 1
        assert cache.metrics()["cache_hits"] == 1
        publish(owner.store, (source,), SelectionRules(), owner.producer,
                first.logical_id, cache=cache)
        assert call.call_count == 1
        assert preview(owner.store, (source,), SelectionRules()) == first
        assert call.call_count == 2


def test_cache_reverifies_on_changed_owner_bytes_or_corruption(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    raw = b"".join(owner.store.read_payload(source.payload("archive")))
    project = PlatformBundle3SourceAdapter.project
    with patch.object(PlatformBundle3SourceAdapter, "project", autospec=True,
                      side_effect=project) as call:
        cache = VerifiedSourceCache(owner.operations.path, "owner-a")
        original = select_decisions((raw,), cache=cache)
        second = VerifiedSourceCache(owner.operations.path, "owner-b")
        assert select_decisions((raw,), cache=second) == original
        assert call.call_count == 2
        repacked = gzip.compress(gzip.decompress(raw), mtime=12)
        assert len(select_decisions((repacked,), cache=cache).records) == 6
        assert call.call_count == 3
        with cache._connect() as db:
            db.execute("UPDATE decision_source_cache SET body=?", (b'{"forged":true}',))
        assert select_decisions((raw,), cache=cache) == original
        assert call.call_count == 4 and cache.corrupt == 1
        with pytest.raises((ValueError, BoundaryError)):
            select_decisions((b"invalid archive",), cache=cache)
        assert call.call_count == 5


def test_cache_bounds_do_not_discard_source_or_change_result(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    cache = VerifiedSourceCache(owner.operations.path, "owner")
    with patch("stpd.fullrun.decision_cache.MAX_ENTRY_BYTES", 1):
        first = preview(owner.store, (source,), SelectionRules(), cache=cache)
    assert cache.bypassed == 1 and cache.hits == 0
    assert preview(owner.store, (source,), SelectionRules(), cache=cache) == first
    assert cache.misses == 2
    assert preview(owner.store, (source,), SelectionRules(), cache=cache) == first
    assert cache.hits == 1


def test_installed_owner_code_change_misses_even_with_same_producer(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    first = VerifiedSourceCache(owner.operations.path, "same-producer")
    expected = preview(owner.store, (source,), SelectionRules(), cache=first)
    with patch("stpd.fullrun.decision_cache.implementation_identity", return_value="changed"):
        next_owner = VerifiedSourceCache(owner.operations.path, "same-producer")
        assert next_owner.owner != first.owner
        assert preview(owner.store, (source,), SelectionRules(), cache=next_owner) == expected
        assert next_owner.hits == 0 and next_owner.misses == 1


def test_cache_is_disposable_private_file_not_backed_up_authority(tmp_path):
    import os
    import sqlite3

    owner, _, _, _ = setup(tmp_path)
    cache = VerifiedSourceCache(owner.operations.path, 'owner')
    assert cache.database != owner.operations.path
    if os.name != 'nt':
        assert cache.database.stat().st_mode & 0o077 == 0
    with owner.operations.transaction() as db:
        assert not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='decision_source_cache'"
        ).fetchone()
    cache.database.unlink()
    reopened = VerifiedSourceCache(owner.operations.path, 'owner')
    with sqlite3.connect(reopened.database) as db:
        assert db.execute('SELECT count(*) FROM decision_source_cache').fetchone()[0] == 0
