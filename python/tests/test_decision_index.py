"""Receipt-index reuse is private, checksum-bound, and preserves source admission."""

from pathlib import Path
from unittest.mock import patch

from test_decision_store import setup

from stpd.fullrun.decision_cache import VerifiedSourceCache
from stpd.fullrun.decision_dataset import SelectionRules
from stpd.fullrun.decision_store import preview
from stpd.fullrun.platform_bundle3 import PlatformBundle3SourceAdapter


def test_warm_source_index_skips_archive_download_but_rechecks_rows(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    cache = VerifiedSourceCache(owner.operations.path, "owner")
    original = preview(owner.store, (source,), SelectionRules(), cache=cache)
    with patch.object(owner.store, "read_payload", side_effect=AssertionError("downloaded again")):
        assert preview(owner.store, (source,), SelectionRules(), cache=cache) == original
    assert cache.hits == 1
    with owner.operations.transaction() as db:
        db.execute("DELETE FROM decision_source_rows WHERE ordinal=1")
    project = PlatformBundle3SourceAdapter.project
    with patch.object(PlatformBundle3SourceAdapter, "project", autospec=True,
                      side_effect=project) as verify:
        assert preview(owner.store, (source,), SelectionRules(), cache=cache) == original
    assert verify.call_count == 1 and cache.corrupt == 1


def test_failed_index_transaction_never_reuses_partial_rows(tmp_path: Path) -> None:
    owner, _, source, _ = setup(tmp_path)
    cache = VerifiedSourceCache(owner.operations.path, "owner")
    original = preview(owner.store, (source,), SelectionRules(), cache=cache)
    with owner.operations.transaction() as db:
        db.execute("DELETE FROM decision_source_index")
    project = PlatformBundle3SourceAdapter.project
    with patch.object(PlatformBundle3SourceAdapter, "project", autospec=True,
                      side_effect=project) as verify:
        assert preview(owner.store, (source,), SelectionRules(), cache=cache) == original
    assert verify.call_count == 1 and cache.hits == 0
    with owner.operations.transaction() as db:
        assert db.execute("SELECT count(*) FROM decision_source_rows").fetchone()[0] == 6


def test_confirmation_reuses_fixed_selection_without_reprojecting_or_selecting(
    tmp_path: Path,
) -> None:
    from stpd.fullrun.decision_store import load, publish

    owner, _, source, _ = setup(tmp_path)
    cache = VerifiedSourceCache(owner.operations.path, "owner")
    rules = SelectionRules()
    selected = preview(owner.store, (source,), rules, cache=cache)
    with patch("stpd.fullrun.decision_store.preview", side_effect=AssertionError("reselected")):
        manifest = publish(owner.store, (source,), rules, owner.producer,
                           selected.logical_id, cache=cache)
    assert cache.preview_hits == 1
    assert load(owner.store, manifest.artifact_id)[1] == selected
    # Deletion of disposable acceleration is a fallback, not a new selection identity.
    with owner.operations.transaction() as db:
        db.execute("DELETE FROM decision_source_rows")
    manifest2 = publish(owner.store, (source,), rules, owner.producer,
                        selected.logical_id, cache=cache)
    assert load(owner.store, manifest2.artifact_id)[1] == selected
    assert cache.corrupt == 1
