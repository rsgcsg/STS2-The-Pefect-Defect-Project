from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from spireagent.json_boundary import BoundaryError
from tools import install_developer_kit as install


def archive(tmp_path: Path, *, extra: str | None = None) -> tuple[Path, str]:
    files = {name: b"synthetic" for name in install.STAGING}
    for name in ("platform-bom.json", "developer-combination.json", "mod/STS2_PLATFORM.json"):
        files[name] = b"synthetic"
    if extra:
        files[extra] = b"unsafe"
    manifest = {
        "schema": "spireagent/developer-kit-v1",
        "stpd_source_revision": "a" * 40,
        "uv_lock_sha256": "b" * 64,
        "collection_tool_release_id": "c" * 64,
        "mod_sha256": install.sha(files["mod/STS2_PLATFORM.dll"]),
        "mod_manifest_sha256": install.sha(files["mod/STS2_PLATFORM.json"]),
        "platform_bom_sha256": install.sha(files["platform-bom.json"]),
        "developer_combination_sha256": install.sha(files["developer-combination.json"]),
        "files": {name: install.sha(raw) for name, raw in files.items()},
    }
    files["combination.json"] = json.dumps(manifest).encode()
    target = tmp_path / "kit.zip"
    with zipfile.ZipFile(target, "w") as z:
        for name, raw in files.items():
            z.writestr(name, raw)
    return target, install.sha(target.read_bytes())


def test_verified_inventory_needs_independent_archive_hash(tmp_path):
    path, expected = archive(tmp_path)
    manifest, files = install.verified_archive(path, expected)
    assert manifest["stpd_source_revision"] == "a" * 40
    assert set(install.STAGING).issubset(files)
    with pytest.raises(BoundaryError, match="checksum"):
        install.verified_archive(path, "f" * 64)
    with zipfile.ZipFile(path, "a") as z:
        z.writestr("unlisted", b"not in manifest")
    with pytest.raises(BoundaryError, match="inventory"):
        install.verified_archive(path, install.sha(path.read_bytes()))


@pytest.mark.parametrize("extra", ["../outside", "/absolute", "C:/drive", "a\\b", "a/../b"])
def test_unsafe_archive_names_fail_before_any_extraction(tmp_path, extra):
    path, expected = archive(tmp_path, extra=extra)
    with pytest.raises(BoundaryError, match="unsafe"):
        install.verified_archive(path, expected)
    assert set(p.name for p in tmp_path.iterdir()) == {"kit.zip"}


def test_wrong_native_game_and_running_game_never_deploy(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "status", lambda _: {"status": "prepared"})
    data = tmp_path / "game"
    data.mkdir()
    (data / "sts2.dll").write_bytes(b"changed game")
    doctor = {
        "status": "ok",
        "game_running": True,
        "platform": "darwin",
        "architecture": "arm64",
        "installation": {"data_dir": str(data)},
        "build_provenance": {
            "platform": "darwin",
            "architecture": "arm64",
            "game": {
                "sts2": {"sha256": "a" * 64},
                "godotsharp_sha256": "b" * 64,
                "harmony_sha256": "c" * 64,
            },
        },
    }
    calls = []

    def run(args, cwd, **kwargs):
        calls.append(args)
        assert args[-1] == "doctor"
        return json.dumps(doctor)

    monkeypatch.setattr(install, "run", run)
    with pytest.raises(BoundaryError, match="closed"):
        install.deploy(tmp_path, data)
    doctor["game_running"] = False
    with pytest.raises(BoundaryError, match="native_game"):
        install.deploy(tmp_path, data)
    assert len(calls) == 2


def test_registration_uses_selected_owner_and_never_replaces_existing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(install, "status", lambda _: {"tool_release_id": "a" * 64})
    calls = []

    def run(args, cwd):
        calls.append((args, cwd))
        return '{"status":"registered"}'

    monkeypatch.setattr(install, "run", run)
    install.register(tmp_path, tmp_path / "profile.json")
    args, cwd = calls[0]
    assert cwd == tmp_path / "source"
    assert "--replace-tool" not in args and "collection-tool" in args
    assert "--locked" in args and "build" not in args
