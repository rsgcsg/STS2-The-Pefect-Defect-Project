from __future__ import annotations

import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest
from sts2_platform_evidence.collection_tool import CollectionTool, digest

from stpd.json_boundary import BoundaryError
from stpd.workbench import control
from tools.package_developer_kit import PinnedFile, package, sha256


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "uv.lock").write_bytes(b"synthetic locked dependencies\n")
    config = root / "configs/developer/combination-v1.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        json.dumps(
            {
                "schema": "stpd/developer-combination-v1",
                "platform_repository": "https://github.com/rsgcsg/STS2-AI-PLATFORM.git",
                "platform_source_revision": "a" * 40,
                "evidence_source_revision": "b" * 40,
                "policy_mode": "existing-adapter-only",
                "node_packages": [],
            }
        )
    )
    for command in (
        ["init", "-q"],
        ["config", "user.name", "Synthetic Test"],
        ["config", "user.email", "test@example.invalid"],
        ["add", "."],
        ["commit", "-qm", "synthetic packaging source"],
    ):
        subprocess.run(["git", *command], cwd=root, check=True, capture_output=True)
    # Exercise the real clean-source checks with an isolated installed-checkout location.
    monkeypatch.setattr(control, "__file__", str(root / "stpd/workbench/control.py"))
    explicit = {}
    for name in ("mod_dll", "mod_manifest", "platform_bom"):
        path = tmp_path / name
        path.write_bytes(f"synthetic public {name}".encode())
        explicit[name] = PinnedFile(path, sha256(path.read_bytes()))
    tool = tmp_path / "tool"
    tool.mkdir()
    for name in ("sts2-human-annotator.dll", "platform-bom.json"):
        (tool / name).write_bytes(f"synthetic tool {name}".encode())
    setup = "setup/apps/game-mod/collection-setup.mjs"
    provenance = "game-mod/build-provenance.json"
    (tool / setup).parent.mkdir(parents=True)
    (tool / setup).write_text("// synthetic setup fixture; never executed")
    (tool / provenance).parent.mkdir()
    (tool / provenance).write_text(
        json.dumps(
            {
                "schema": "sts2.platform/game-mod-build-provenance-1",
                "artifact": {"sha256": explicit["mod_dll"].sha256},
            }
        )
    )
    identity = {
        "worktree": "clean",
        "source_revision": "c" * 40,
        "workspace_revision": "d" * 40,
        "entrypoint": "sts2-human-annotator.dll",
        "supported_recording_schema": "sts2.human-annotator/recording-manifest-2",
        "collection_setup_entrypoint": setup,
        "collection_setup_provenance": provenance,
        "files": [
            {
                "path": path.relative_to(tool).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path.read_bytes()),
            }
            for path in sorted(tool.rglob("*"))
            if path.is_file()
        ],
    }
    release_id = digest(identity)
    (tool / "collection-tool.json").write_text(
        json.dumps(
            {
                "schema": "sts2.evidence/collection-tool-1",
                "release_id": release_id,
                "identity": identity,
            },
            indent=2,
        )
    )
    return {
        **explicit,
        "root": root,
        "collection_tool": tool,
        "tool_release_id": release_id,
        "output": tmp_path / "first.zip",
    }


def test_deterministic_public_inventory_and_real_owner_verification(inputs, tmp_path):
    # Unrelated local credentials must never be discovered/copied by the packager.
    (tmp_path / "operator.env").write_text("TOKEN=must-not-be-packaged")
    receipt = package(**inputs)
    second = tmp_path / "second.zip"
    for path in inputs["collection_tool"].iterdir():
        os.utime(path, (1_700_000_000, 1_700_000_000))
    assert package(**{**inputs, "output": second}) == receipt
    raw = inputs["output"].read_bytes()
    assert raw == second.read_bytes()
    assert sha256(raw) == receipt["sha256"]
    assert b"must-not-be-packaged" not in raw
    with zipfile.ZipFile(inputs["output"]) as archive:
        expected = {
            "README.md",
            "mod/STS2_PLATFORM.dll",
            "mod/STS2_PLATFORM.json",
            "platform-bom.json",
            "developer-combination.json",
            "combination.json",
            "collection-tool/collection-tool.json",
            "collection-tool/platform-bom.json",
            "collection-tool/sts2-human-annotator.dll",
            "collection-tool/setup/apps/game-mod/collection-setup.mjs",
            "collection-tool/game-mod/build-provenance.json",
        }
        assert set(archive.namelist()) == expected
        manifest = json.loads(archive.read("combination.json"))
        assert set(manifest["files"]) == expected - {"combination.json"}
        for name, expected_hash in manifest["files"].items():
            assert sha256(archive.read(name)) == expected_hash
        assert manifest["collection_tool_source_revision"] == "c" * 40
        assert manifest["collection_tool_workspace_revision"] == "d" * 40
        assert not {"status", "human_approval_source", "hub_image", "stpd_ci_run"} & set(manifest)
        assert (
            archive.read("collection-tool/collection-tool.json")
            == (inputs["collection_tool"] / "collection-tool.json").read_bytes()
        )
        extracted = tmp_path / "extracted"
        # Only our generated archive, after exact path inventory verification.
        archive.extractall(extracted)
    CollectionTool(extracted / "collection-tool", inputs["tool_release_id"])


@pytest.mark.parametrize("change", ["old_tool", "mismatched_mod"])
def test_new_workflow_kit_requires_native_setup_and_same_mod(inputs, change):
    tool = inputs["collection_tool"]
    manifest_path = tool / "collection-tool.json"
    value = json.loads(manifest_path.read_bytes())
    if change == "old_tool":
        del value["identity"]["collection_setup_entrypoint"]
    else:
        path = inputs["mod_dll"].path
        path.write_bytes(b"another independently valid native candidate")
        inputs["mod_dll"] = PinnedFile(path, sha256(path.read_bytes()))
    value["release_id"] = digest(value["identity"])
    manifest_path.write_text(json.dumps(value))
    inputs["tool_release_id"] = value["release_id"]
    with pytest.raises(BoundaryError, match="collection_setup_"):
        package(**inputs)
    assert not inputs["output"].exists()


@pytest.mark.parametrize("field", ["mod_dll", "mod_manifest", "platform_bom"])
def test_explicit_public_file_tamper_never_publishes(inputs, field):
    inputs[field].path.write_bytes(b"changed")
    with pytest.raises(BoundaryError, match="pinned_file_changed"):
        package(**inputs)
    assert not inputs["output"].exists()


@pytest.mark.parametrize("change", ["tamper", "extra", "untrusted_manifest", "wrong_pin"])
def test_tool_owner_rejection_and_uninventoried_manifest_fields(inputs, change):
    tool = inputs["collection_tool"]
    if change == "tamper":
        (tool / "sts2-human-annotator.dll").write_bytes(b"changed")
    elif change == "extra":
        (tool / "credentials.env").write_text("TOKEN=private")
    elif change == "untrusted_manifest":
        path = tool / "collection-tool.json"
        value = json.loads(path.read_bytes())
        value["ignored_private_field"] = "must-not-be-packaged"
        path.write_text(json.dumps(value))
    else:
        inputs["tool_release_id"] = "0" * 64
    with pytest.raises(ValueError):
        package(**inputs)
    assert not inputs["output"].exists()


@pytest.mark.parametrize("kind", ["mod", "tool_file", "tool_directory"])
def test_symlinks_are_not_followed(inputs, tmp_path, kind):
    if kind == "mod":
        path = tmp_path / "mod-link"
        target = inputs["mod_dll"].path
    elif kind == "tool_file":
        path = inputs["collection_tool"] / "extra-link"
        target = inputs["mod_dll"].path
    else:
        path = tmp_path / "tool-link"
        target = inputs["collection_tool"]
    try:
        path.symlink_to(target, target_is_directory=kind == "tool_directory")
    except OSError:
        pytest.skip("OS does not permit symlink creation")
    if kind == "mod":
        inputs["mod_dll"] = PinnedFile(path, inputs["mod_dll"].sha256)
    elif kind == "tool_directory":
        inputs["collection_tool"] = path
    with pytest.raises(ValueError):
        package(**inputs)
    assert not inputs["output"].exists()


def test_existing_output_is_immutable_even_at_publication_race(inputs, monkeypatch):
    inputs["output"].write_bytes(b"original release")
    with pytest.raises(BoundaryError, match="output_already_exists"):
        package(**inputs)
    assert inputs["output"].read_bytes() == b"original release"
    inputs["output"].unlink()
    real_link = os.link

    def raced_link(source, destination):
        Path(destination).write_bytes(b"concurrently published release")
        real_link(source, destination)

    monkeypatch.setattr(os, "link", raced_link)
    with pytest.raises(FileExistsError):
        package(**inputs)
    assert inputs["output"].read_bytes() == b"concurrently published release"


def test_dirty_source_and_mid_packaging_changes_never_publish(inputs, monkeypatch):
    lock = inputs["root"] / "uv.lock"
    original = lock.read_bytes()
    lock.write_bytes(b"changed lock")
    with pytest.raises(BoundaryError, match="clean_checkout_required"):
        package(**inputs)
    assert not inputs["output"].exists()
    lock.write_bytes(original)
    real_write = zipfile.ZipFile.writestr

    def changing_write(self, *args, **kwargs):
        result = real_write(self, *args, **kwargs)
        lock.write_bytes(b"source changed during packaging")
        return result

    monkeypatch.setattr(zipfile.ZipFile, "writestr", changing_write)
    with pytest.raises(BoundaryError, match="clean_checkout_required"):
        package(**inputs)
    assert not inputs["output"].exists()
