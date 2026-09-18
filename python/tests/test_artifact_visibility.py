from dataclasses import replace
from pathlib import Path

import pytest
from test_decision_training import prepared
from test_hub_member_data import MEMBER

from spireagent.hub.artifact_visibility import ArtifactVisibility
from spireagent.json_boundary import BoundaryError
from stpd.fullrun.decision_training import AllocationSpec, publish_allocation


def test_archive_preserves_identity_lineage_and_other_members(tmp_path: Path):
    owner, dataset = prepared(tmp_path)
    allocation = publish_allocation(owner.store, dataset, AllocationSpec(), owner.producer)
    owner.console_index.artifact(allocation)
    visibility = ArtifactVisibility(owner)

    def query(principal, archived=False):
        return owner.console_index.artifacts(
            principal, "training", limit=25, offset=0, archived=archived
        )

    assert query(MEMBER)["total"] == 1
    before = owner.store.get_manifest(allocation.artifact_id).to_bytes()
    visibility.write(MEMBER, {"ids": [allocation.artifact_id], "archived": True})
    assert query(MEMBER)["total"] == 0
    assert query(MEMBER, True)["total"] == 1
    assert query(replace(MEMBER, subject="other"))["total"] == 1
    assert owner.store.get_manifest(allocation.artifact_id).to_bytes() == before
    # Re-indexing must not reset the personal overlay.
    owner.console_index.artifact(allocation)
    assert query(MEMBER)["total"] == 0
    visibility.write(MEMBER, {"ids": [allocation.artifact_id], "archived": False})
    assert query(MEMBER)["total"] == 1
    with pytest.raises(BoundaryError):
        visibility.write(MEMBER, {"ids": ["invalid"], "archived": True})
