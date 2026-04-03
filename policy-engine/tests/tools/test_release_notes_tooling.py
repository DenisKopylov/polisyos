from __future__ import annotations

from pathlib import Path

import pytest

from tools.release.build_release_notes import validate_required_curated_sections
from tools.release.check_release_version import resolve_release_fragments_dir


def test_validate_required_curated_sections_accepts_complete_snapshot() -> None:
    fragments = [
        {
            "type": "changed",
            "summary": "Release pipeline update.",
            "compatibility": "Require the new required checks.",
            "migration": "Move legacy workflow usage to the canonical set.",
            "api": "No public API changes.",
            "limitations": "Protected environments must exist.",
        }
    ]

    counts = validate_required_curated_sections(
        fragments,
        ["compatibility", "migration", "api", "limitations"],
    )

    assert counts["compatibility"] == 1
    assert counts["migration"] == 1
    assert counts["api"] == 1
    assert counts["limitations"] == 1


def test_validate_required_curated_sections_rejects_missing_required_content() -> None:
    fragments = [
        {
            "type": "changed",
            "summary": "Release pipeline update.",
            "compatibility": "Require the new required checks.",
            "migration": "",
            "api": "No public API changes.",
            "limitations": "Protected environments must exist.",
        }
    ]

    with pytest.raises(ValueError, match="Migration Notes"):
        validate_required_curated_sections(
            fragments,
            ["compatibility", "migration", "api", "limitations"],
        )


def test_resolve_release_fragments_dir_uses_immutable_version_snapshot(tmp_path: Path) -> None:
    release_root = tmp_path / "releases"
    version_dir = release_root / "1.2.3"
    version_dir.mkdir(parents=True)

    assert resolve_release_fragments_dir("1.2.3", release_root) == version_dir

    with pytest.raises(SystemExit, match="Stage a versioned snapshot"):
        resolve_release_fragments_dir("9.9.9", release_root)
