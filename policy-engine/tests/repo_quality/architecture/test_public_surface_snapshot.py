from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from tools.quality.validation import decomposition_preflight
from tools.quality.validation.decomposition_preflight import validate_public_surface_snapshot


def test_public_surface_snapshot_gate_matches_phase3a_baseline() -> None:
    findings = validate_public_surface_snapshot()

    assert findings == [], "\n".join(finding.render() for finding in findings)


def test_public_surface_snapshot_resolves_exported_class_alias_from_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = (tmp_path / "src").resolve()
    package = source_root / "polisyos" / "fixture"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(
        "from .owner import SharedReady as PackageReady\n"
        "__all__ = ['PackageReady']\n",
        encoding="utf-8",
    )
    (package / "owner.py").write_text(
        "class SharedReady:\n    pass\n",
        encoding="utf-8",
    )
    compatibility = package / "compat.py"
    compatibility.write_text(
        "from .owner import SharedReady as LegacyReady\n"
        "__all__ = ['LegacyReady']\n",
        encoding="utf-8",
    )
    chained = package / "chain.py"
    chained.write_text(
        "from .compat import LegacyReady as ChainedReady\n"
        "__all__ = ['ChainedReady']\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(decomposition_preflight, "REPO_ROOT", tmp_path.resolve())
    monkeypatch.setattr(decomposition_preflight, "SRC_ROOT", source_root)

    snapshot = decomposition_preflight.collect_public_surface_snapshot()
    fixture = next(
        row for row in snapshot["packages"] if row["package"] == "polisyos.fixture"
    )
    modules = {row["module"]: row for row in fixture["modules"]}
    alias = next(
        row
        for row in modules["polisyos.fixture.compat"]["objects"]
        if row["fqn"] == "polisyos.fixture.compat.LegacyReady"
    )
    owner = next(
        row
        for row in modules["polisyos.fixture.owner"]["objects"]
        if row["fqn"] == "polisyos.fixture.owner.SharedReady"
    )
    assert alias["kind"] == owner["kind"] == "class"
    assert alias["bases"] == owner["bases"]
    package_alias = next(
        row
        for row in modules["polisyos.fixture"]["objects"]
        if row["fqn"] == "polisyos.fixture.PackageReady"
    )
    assert package_alias["kind"] == owner["kind"] == "class"
    assert package_alias["bases"] == owner["bases"]
    chained_alias = next(
        row
        for row in modules["polisyos.fixture.chain"]["objects"]
        if row["fqn"] == "polisyos.fixture.chain.ChainedReady"
    )
    assert chained_alias["kind"] == owner["kind"] == "class"
    assert chained_alias["bases"] == owner["bases"]

    compatibility.write_text("__all__ = ['LegacyReady']\n", encoding="utf-8")
    removed = decomposition_preflight.collect_public_surface_snapshot()
    removed_fixture = next(
        row
        for row in removed["packages"]
        if row["package"] == "polisyos.fixture"
    )
    removed_modules = {row["module"]: row for row in removed_fixture["modules"]}
    assert removed_modules["polisyos.fixture.compat"]["__all__"] == ["LegacyReady"]
    assert all(
        row["fqn"] != "polisyos.fixture.compat.LegacyReady"
        for row in removed_modules["polisyos.fixture.compat"]["objects"]
    )
    assert all(
        row["fqn"] != "polisyos.fixture.chain.ChainedReady"
        for row in removed_modules["polisyos.fixture.chain"]["objects"]
    )



def test_public_surface_snapshot_gate_ignores_only_source_coordinates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = (tmp_path / "src").resolve()
    package = source_root / "polisyos" / "fixture"
    package.mkdir(parents=True)
    source = package / "__init__.py"
    original = (
        "__all__ = ['PublicRecord', 'public_api']\n"
        "class PublicRecord(BaseModel):\n"
        "    pass\n\n"
        "def public_api(value: int) -> str:\n"
        "    return str(value)\n"
    )
    source.write_text(original, encoding="utf-8")
    baseline_path = tmp_path / "public_surface.json"
    monkeypatch.setattr(decomposition_preflight, "REPO_ROOT", tmp_path.resolve())
    monkeypatch.setattr(decomposition_preflight, "SRC_ROOT", source_root)
    monkeypatch.setattr(
        decomposition_preflight, "PUBLIC_SURFACE_BASELINE_PATH", baseline_path
    )
    baseline_path.write_text(
        json.dumps(decomposition_preflight.collect_public_surface_snapshot()),
        encoding="utf-8",
    )
    baseline_snapshot = json.loads(baseline_path.read_text(encoding="utf-8"))
    baseline_module = baseline_snapshot["packages"][0]["modules"][0]
    baseline_line = next(
        row["line"]
        for row in baseline_module["objects"]
        if row["name"] == "public_api"
    )

    source.write_text("\n\n" + original, encoding="utf-8")
    shifted_snapshot = decomposition_preflight.collect_public_surface_snapshot()
    shifted_module = shifted_snapshot["packages"][0]["modules"][0]
    shifted_line = next(
        row["line"]
        for row in shifted_module["objects"]
        if row["name"] == "public_api"
    )
    assert shifted_line == baseline_line + 2
    assert validate_public_surface_snapshot() == []

    source.write_text(original.replace("value: int", "value: bytes"), encoding="utf-8")
    findings = validate_public_surface_snapshot()
    assert [finding.message for finding in findings] == ["snapshot drift detected"]


def test_public_surface_snapshot_normalization_preserves_api_fields() -> None:
    baseline = {
        "version": 1,
        "packages": [
            {
                "package": "polisyos.fixture",
                "modules": [
                    {
                        "module": "polisyos.fixture",
                        "source_file": "src/polisyos/fixture/__init__.py",
                        "__all__": ["PublicRecord", "public_api"],
                        "line": 10,
                        "objects": [
                            {
                                "kind": "class",
                                "name": "PublicRecord",
                                "fqn": "polisyos.fixture.PublicRecord",
                                "bases": ["BaseModel"],
                                "pydantic": True,
                                "line": 2,
                                "metadata": {"line": 1},
                            },
                            {
                                "kind": "function",
                                "name": "public_api",
                                "fqn": "polisyos.fixture.public_api",
                                "signature": "(value: int)",
                                "line": 5,
                            },
                        ],
                    }
                ],
            }
        ],
    }
    shifted = copy.deepcopy(baseline)
    module = shifted["packages"][0]["modules"][0]
    module["objects"][0]["line"] = 22
    module["objects"][1]["line"] = 25
    assert decomposition_preflight._normalize_public_surface_snapshot(
        baseline
    ) == decomposition_preflight._normalize_public_surface_snapshot(shifted)

    changes = []
    changed = copy.deepcopy(baseline)
    changed["packages"][0]["modules"][0]["objects"][0]["kind"] = "function"
    changes.append(changed)
    changed = copy.deepcopy(baseline)
    changed["packages"][0]["modules"][0]["objects"][0]["fqn"] = (
        "polisyos.fixture.RenamedRecord"
    )
    changes.append(changed)
    changed = copy.deepcopy(baseline)
    changed["packages"][0]["modules"][0]["objects"][0]["bases"] = ["Protocol"]
    changes.append(changed)
    changed = copy.deepcopy(baseline)
    changed["packages"][0]["modules"][0]["objects"][0]["pydantic"] = False
    changes.append(changed)
    changed = copy.deepcopy(baseline)
    changed["packages"][0]["modules"][0]["objects"][1]["signature"] = (
        "(value: bytes)"
    )
    changes.append(changed)
    changed = copy.deepcopy(baseline)
    changed["packages"][0]["modules"][0]["__all__"] = ["PublicRecord"]
    changes.append(changed)
    changed = copy.deepcopy(baseline)
    changed_module = changed["packages"][0]["modules"][0]
    marker = changed_module["__all__"]
    changed_module["objects"].pop(0)
    assert changed_module["__all__"] == marker
    changes.append(changed)
    changed = copy.deepcopy(baseline)
    changed["packages"][0]["modules"][0]["line"] = 11
    changes.append(changed)
    changed = copy.deepcopy(baseline)
    changed["packages"][0]["modules"][0]["objects"][0]["metadata"]["line"] = 2
    changes.append(changed)

    normalized_baseline = decomposition_preflight._normalize_public_surface_snapshot(
        baseline
    )
    assert all(
        decomposition_preflight._normalize_public_surface_snapshot(change)
        != normalized_baseline
        for change in changes
    )


@pytest.mark.parametrize(
    ("version", "omit_version"),
    [
        pytest.param(2, False, id="version-2"),
        pytest.param(None, True, id="missing-version"),
        pytest.param(True, False, id="boolean-version"),
        pytest.param("1", False, id="string-version"),
        pytest.param(1.0, False, id="float-version"),
    ],
)
def test_public_surface_snapshot_gate_preserves_coordinates_for_non_v1_versions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    version: object,
    omit_version: bool,
) -> None:
    baseline = {
        "version": version,
        "generated_at": "fixture-time",
        "packages": [
            {
                "package": "polisyos.fixture",
                "modules": [
                    {
                        "module": "polisyos.fixture",
                        "source_file": "src/polisyos/fixture/__init__.py",
                        "__all__": ["public_api"],
                        "objects": [
                            {
                                "kind": "function",
                                "name": "public_api",
                                "fqn": "polisyos.fixture.public_api",
                                "signature": "()",
                                "line": 5,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    if omit_version:
        baseline.pop("version")
    current = copy.deepcopy(baseline)
    current["packages"][0]["modules"][0]["objects"][0]["line"] += 2
    baseline_path = tmp_path / "public_surface.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(decomposition_preflight, "REPO_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        decomposition_preflight, "PUBLIC_SURFACE_BASELINE_PATH", baseline_path
    )
    monkeypatch.setattr(
        decomposition_preflight,
        "collect_public_surface_snapshot",
        lambda: current,
    )

    findings = validate_public_surface_snapshot()

    assert [finding.message for finding in findings] == ["snapshot drift detected"]


@pytest.mark.parametrize("source_line", [0, -1, True, "5", None])
def test_public_surface_snapshot_gate_preserves_invalid_coordinates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source_line: object,
) -> None:
    baseline = {
        "version": 1,
        "generated_at": "fixture-time",
        "packages": [
            {
                "package": "polisyos.fixture",
                "modules": [
                    {
                        "module": "polisyos.fixture",
                        "__all__": ["public_api"],
                        "objects": [
                            {
                                "kind": "function",
                                "name": "public_api",
                                "fqn": "polisyos.fixture.public_api",
                                "signature": "()",
                                "line": source_line,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    current = copy.deepcopy(baseline)
    current["packages"][0]["modules"][0]["objects"][0]["line"] = 9
    baseline_path = tmp_path / "public_surface.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(decomposition_preflight, "REPO_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        decomposition_preflight, "PUBLIC_SURFACE_BASELINE_PATH", baseline_path
    )
    monkeypatch.setattr(
        decomposition_preflight,
        "collect_public_surface_snapshot",
        lambda: current,
    )

    findings = validate_public_surface_snapshot()

    assert [finding.message for finding in findings] == ["snapshot drift detected"]


def test_public_surface_snapshot_gate_preserves_unknown_v1_object_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = {
        "version": 1,
        "generated_at": "fixture-time",
        "packages": [
            {
                "package": "polisyos.fixture",
                "modules": [
                    {
                        "module": "polisyos.fixture",
                        "objects": [
                            {
                                "kind": "function",
                                "name": "public_api",
                                "fqn": "polisyos.fixture.public_api",
                                "line": 5,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    current = copy.deepcopy(baseline)
    current["packages"][0]["modules"][0]["objects"][0]["line"] += 2
    baseline_path = tmp_path / "public_surface.json"
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(decomposition_preflight, "REPO_ROOT", tmp_path.resolve())
    monkeypatch.setattr(
        decomposition_preflight, "PUBLIC_SURFACE_BASELINE_PATH", baseline_path
    )
    monkeypatch.setattr(
        decomposition_preflight,
        "collect_public_surface_snapshot",
        lambda: current,
    )

    findings = validate_public_surface_snapshot()

    assert [finding.message for finding in findings] == ["snapshot drift detected"]
