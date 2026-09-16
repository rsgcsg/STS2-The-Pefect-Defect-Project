"""Exact source provenance shared by applications and disposable workers."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from .artifact_contracts import Producer
from .json_boundary import BoundaryError

REPOSITORY = "rsgcsg/STS2-The-Perfect-Defect-Project"
# Exact rename alias, not a wildcard or a rewrite of historical producer facts.
REPOSITORY_ALIASES = (REPOSITORY, "rsgcsg/STS2-The-Pefect-Defect-Project")
REPOSITORY_URLS = tuple(f"https://github.com/{name}.git" for name in REPOSITORY_ALIASES)


def source_identity(root: Path, *, require_clean: bool = True) -> Producer:
    if root.resolve() != Path(__file__).resolve().parents[1]:
        raise BoundaryError("source", "executing_package_checkout_mismatch")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
    if require_clean and dirty:
        raise BoundaryError("source", "clean_checkout_required")
    lock = (root / "uv.lock").read_bytes()
    prefix = subprocess.check_output(
        ["git", "rev-parse", "--show-prefix"], cwd=root, text=True
    ).strip()
    committed = subprocess.check_output(["git", "show", f"HEAD:{prefix}uv.lock"], cwd=root)
    if lock != committed:
        raise BoundaryError("source", "working_lock_mismatch")
    return Producer(REPOSITORY, head, hashlib.sha256(lock).hexdigest())
