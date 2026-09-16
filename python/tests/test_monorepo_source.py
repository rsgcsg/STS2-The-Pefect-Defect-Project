"""Source provenance binds the real nested lock; it never relabels historic producers."""

import hashlib
import subprocess
from pathlib import Path

import pytest

from spireagent import source
from spireagent.artifact_contracts import Producer
from spireagent.json_boundary import BoundaryError


def test_nested_checkout_identity_and_lock_tampering(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "python"
    project.mkdir()
    (project / "uv.lock").write_bytes(b"fixture lock\n")
    (project / "spireagent").mkdir()
    module = project / "spireagent/source.py"
    module.write_text("# synthetic installed module\n")
    for args in (
        ["init", "-q"],
        ["config", "user.name", "Fixture"],
        ["config", "user.email", "fixture@example.invalid"],
        ["add", "."],
        ["commit", "-qm", "fixture"],
    ):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)
    monkeypatch.setattr(source, "__file__", str(module))
    identity = source.source_identity(project)
    assert identity.repository == "rsgcsg/STS2-The-Perfect-Defect-Project"
    assert identity.uv_lock_sha256 == hashlib.sha256(b"fixture lock\n").hexdigest()
    with pytest.raises(BoundaryError, match="executing_package_checkout_mismatch"):
        source.source_identity(tmp_path)
    (project / "uv.lock").write_bytes(b"altered lock\n")
    with pytest.raises(BoundaryError, match="clean_checkout_required"):
        source.source_identity(project)
    with pytest.raises(BoundaryError, match="working_lock_mismatch"):
        source.source_identity(project, require_clean=False)


@pytest.mark.parametrize(
    "repository",
    [
        "rsgcsg/STS2-The-Perfect-Defect",
        "rsgcsg/STS2-The-Pefect-Defect-Project",
        "rsgcsg/STS2-The-Perfect-Defect-Project",
    ],
)
def test_historical_producer_identity_is_not_rewritten(repository: str) -> None:
    original = {
        "repository": repository,
        "source_revision": "a" * 40,
        "uv_lock_sha256": "b" * 64,
    }
    assert Producer.decode(original).to_dict() == original
