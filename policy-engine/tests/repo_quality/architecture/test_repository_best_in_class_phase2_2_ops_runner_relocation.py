from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent

LEGACY_RUNNER_PATH = "tools/" + "ops/"
LEGACY_RUNNER_MODULE = "tools." + "ops."

ARCHIVE_PREFIXES = (
    "docs/archive/",
    "docs/migration/archive/",
    "docs/plans/archive/",
    "docs/plans/accepted/",
)
LIVE_TEXT_ROOTS = (
    WORKSPACE_ROOT / ".github",
    REPO_ROOT / "architecture",
    REPO_ROOT / "apps",
    REPO_ROOT / "docs",
    REPO_ROOT / "frontend",
    REPO_ROOT / "ops",
    REPO_ROOT / "packages",
    REPO_ROOT / "release",
    REPO_ROOT / "release-fragments",
    REPO_ROOT / "schemas",
    REPO_ROOT / "src",
    REPO_ROOT / "tests",
    REPO_ROOT / "tools",
)
LIVE_TEXT_FILES = (
    REPO_ROOT / "basedpyright.toml",
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "ruff.toml",
)
EXCLUDED_DIR_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "_build",
    "_cache",
    "node_modules",
}

OPS_FOLDER_CONTRACTS = {
    "ci": ("team-devx", "ci-template-control-plane"),
    "cloud": ("team-ops", "cloud-infrastructure-contracts"),
    "deploy": ("team-ops", "deployment-contracts"),
    "docker": ("team-ops", "local-runtime-infrastructure"),
    "migrations": ("team-ops", "migration-contracts"),
    "observability": ("team-ops", "observability-contracts"),
    "policy": ("team-security", "policy-as-code"),
    "release": ("team-ops", "release-policy-contracts"),
    "runtime": ("team-runtime", "runtime-operations-contracts"),
    "security": ("team-security", "security-baseline-contracts"),
}


def test_phase2_2_physical_ops_runner_namespace_is_relocated() -> None:
    assert not (REPO_ROOT / "tools" / "ops").exists()
    assert (REPO_ROOT / "tools" / "ops_runners").is_dir()


def test_phase2_2_live_text_does_not_reference_legacy_ops_runner_namespace() -> None:
    violations: list[str] = []
    for path in _iter_live_text_files():
        text = _read_text_or_skip(path)
        if text is None:
            continue
        if LEGACY_RUNNER_PATH in text or LEGACY_RUNNER_MODULE in text:
            violations.append(str(path.relative_to(REPO_ROOT)))

    assert violations == []


def test_phase2_2_top_level_ops_folders_have_declared_contracts() -> None:
    discovered = {
        path.name
        for path in (REPO_ROOT / "ops").iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert set(OPS_FOLDER_CONTRACTS) <= discovered

    for folder, (owner, artifact_type) in OPS_FOLDER_CONTRACTS.items():
        readme = REPO_ROOT / "ops" / folder / "README.md"
        assert readme.exists(), folder
        text = readme.read_text(encoding="utf-8")
        assert f"Owner: `{owner}`" in text, folder
        assert f"Artifact type: `{artifact_type}`" in text, folder
        concrete_files = [
            path
            for path in (REPO_ROOT / "ops" / folder).rglob("*")
            if path.is_file() and path.name != "README.md"
        ]
        if not concrete_files:
            assert "Backlog:" in text or "Current contract source:" in text, folder


def _iter_live_text_files() -> list[Path]:
    candidates: list[Path] = []
    for root in LIVE_TEXT_ROOTS:
        if not root.exists():
            continue
        for current_root, dirnames, filenames in os.walk(root):
            dirnames[:] = [name for name in dirnames if name not in EXCLUDED_DIR_NAMES]
            current = Path(current_root)
            for filename in filenames:
                path = current / filename
                if _is_archived(path):
                    continue
                candidates.append(path)
    candidates.extend(path for path in LIVE_TEXT_FILES if path.exists())
    return candidates


def _is_archived(path: Path) -> bool:
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return False
    return any(rel.startswith(prefix) for prefix in ARCHIVE_PREFIXES)


def _read_text_or_skip(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None
