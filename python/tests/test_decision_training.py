from dataclasses import replace
from pathlib import Path

import pytest
from test_dataset_curation import build
from test_decision_store import setup

from spireagent.json_boundary import BoundaryError, FrozenObject
from stpd.fullrun.decision_store import load
from stpd.fullrun.decision_training import (
    AllocationSpec,
    allocate,
    load_allocation,
    publish_allocation,
    publish_decision_view,
)
from stpd.fullrun.features import load_model_view
from stpd.fullrun.representation import FullRunSerializer


def prepared(tmp_path):
    owner, upload, _, jobs = setup(tmp_path)
    dataset = build(jobs, upload)["result"]["artifact_id"]
    return owner, dataset


def test_allocation_fixed_members_and_verified_input_view(tmp_path: Path):
    owner, dataset_id = prepared(tmp_path)
    spec = AllocationSpec(max_train=2, max_dev=1)
    first = publish_allocation(owner.store, dataset_id, spec, owner.producer)
    assert publish_allocation(owner.store, dataset_id, spec, owner.producer) == first
    _, _, allocation = load_allocation(owner.store, first.artifact_id)
    assert allocation["counts"] == {"dev": 1, "train": 2}
    roles = {}
    for member in allocation["members"]:
        assert roles.setdefault(member["run_id"], member["split"]) == member["split"]
    view = publish_decision_view(
        owner.store, first.artifact_id, FullRunSerializer(), owner.producer
    )
    _, samples = load_model_view(owner.store, view.artifact_id)
    assert len(samples) == 3
    assert all(s.action_keys[s.chosen_index] for s in samples)
    # A changed protocol cannot keep the same committed membership.
    forged = replace(
        first,
        parameters=FrozenObject.of(
            {
                **first.parameters.value(),
                "spec": {**first.parameters.value()["spec"], "max_train": 1},
            }
        ),
    )
    owner.store.publish(forged)
    with pytest.raises(BoundaryError, match="membership_or_identity_mismatch"):
        load_allocation(owner.store, forged.artifact_id)
    wrong = replace(view, parameters=FrozenObject.of({**view.parameters.value(), "samples": 99}))
    owner.store.publish(wrong)
    with pytest.raises(BoundaryError, match="decision_projection_mismatch"):
        load_model_view(owner.store, wrong.artifact_id)


def test_decision_isolation_is_explicit_and_does_not_claim_unseen_run(tmp_path: Path):
    owner, dataset_id = prepared(tmp_path)
    _, data = load(owner.store, dataset_id)
    selected_run = data.records[0].run_id
    same_run = replace(data, records=tuple(r for r in data.records if r.run_id == selected_run))
    with pytest.raises(BoundaryError, match="insufficient_independent_components"):
        allocate(same_run, AllocationSpec(isolation="run"))
    allocation = allocate(same_run, AllocationSpec(isolation="decision"))
    assert allocation["interpretation"] == "unseen_decisions_may_share_runs"
    assert set(m["split"] for m in allocation["members"]) == {"train", "dev"}
    assert len({m["occurrence"] for m in allocation["members"]}) == len(allocation["members"])


def test_held_out_dataset_cannot_be_allocated_to_training(tmp_path: Path):
    owner, upload, _, jobs = setup(tmp_path)
    dataset = build(jobs, upload, "test")["result"]["artifact_id"]
    with pytest.raises(BoundaryError, match="held_out_data_cannot_train"):
        publish_allocation(owner.store, dataset, AllocationSpec(), owner.producer)
