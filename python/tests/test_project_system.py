"""Mutation tests for the required cross-platform repository contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.project import RepositoryGateError, portable_commands

ROOT = Path(__file__).resolve().parents[1]


def test_portable_gate_includes_all_existing_checks_and_package() -> None:
    commands = portable_commands("python")
    assert ("python", "tools/doctor.py") in commands
    assert ("python", "-m", "ruff", "check", ".") in commands
    assert ("python", "-m", "mypy", "stpd", "spireagent", "tools") in commands
    assert ("npm", "run", "check:connector-sdk") in commands
    pytest_commands = [command for command in commands if command[:3] == ("python", "-m", "pytest")]
    assert len(pytest_commands) == 1
    assert "--durations=30" in pytest_commands[0]
    assert "--junitxml=.local/pytest.xml" in pytest_commands[0]
    assert (
        "python",
        "-m",
        "compileall",
        "-q",
        "stpd",
        "spireagent",
        "tests",
        "tools",
        "deploy",
    ) in commands
    assert (
        "python",
        "-m",
        "spireagent.workbench",
        "e2e",
        "--output",
        ".local/cpu-e2e.json",
    ) in commands
    assert ("uv", "build") in commands
    assert ("git", "diff", "--check") in commands


@pytest.mark.parametrize("mutation", ["python", "current", "bootstrap", "route", "eol"])
def test_repository_drift_is_rejected(tmp_path: Path, mutation: str) -> None:
    from tools.project import ROUTES, validate_repository

    for route in ROUTES:
        path = tmp_path / route
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Fixture\n")
    for path in ("AGENTS.md", "CONTRIBUTING.md"):
        (tmp_path / path).write_text("uv sync --locked --all-extras\ntools/project.py check\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nrequires-python = ">=3.11,<3.12"\n')
    (tmp_path / ".python-version").write_text("3.11\n")
    (tmp_path / "uv.lock").write_text("fixture\n")
    (tmp_path / ".gitattributes").write_text("* text=auto eol=lf\n")
    validate_repository(tmp_path)
    if mutation == "python":
        (tmp_path / ".python-version").write_text("3.13\n")
    elif mutation == "current":
        (tmp_path / "docs/memory/CURRENT.md").write_text("x" * 3073)
    elif mutation == "bootstrap":
        (tmp_path / "AGENTS.md").write_text("python3 -m unittest\n")
    elif mutation == "route":
        (tmp_path / "README.md").write_text("[missing](absent.md)\n")
    else:
        (tmp_path / ".gitattributes").write_text("* text=auto\n")
    with pytest.raises(RepositoryGateError):
        validate_repository(tmp_path)
