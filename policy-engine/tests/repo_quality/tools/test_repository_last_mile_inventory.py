from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_NAME = "tools.quality.validation.repository_last_mile_inventory"
EXPECTED_FINDING_IDS = {f"LM-{index:03d}" for index in range(1, 27)}
LEGACY_DASHBOARD_PATH = "frontend" + "/runtime-dashboard"
REQUIRED_FINDING_FIELDS = {
    "path",
    "paths",
    "count",
    "kind",
    "owner",
    "package",
    "finding_id",
    "suggested_target",
    "current_status",
}


def _module():
    assert importlib.util.find_spec(MODULE_NAME) is not None, (
        "Phase 0.1 last-mile inventory module is missing"
    )
    return importlib.import_module(MODULE_NAME)


@lru_cache(maxsize=1)
def _inventory() -> dict[str, object]:
    return _module().collect_inventory(REPO_ROOT)


def test_inventory_reports_all_last_mile_findings_with_gate_fields() -> None:
    last_mile = _module()
    payload = _inventory()

    assert last_mile.validate_inventory(payload) == []
    assert payload["schema_version"] == last_mile.SCHEMA_VERSION
    assert payload["phase"] == "0.1"

    findings = payload["findings"]
    assert {finding["finding_id"] for finding in findings} == EXPECTED_FINDING_IDS

    for finding in findings:
        assert set(finding) >= REQUIRED_FINDING_FIELDS, finding["finding_id"]
        assert isinstance(finding["paths"], list), finding["finding_id"]
        assert finding["count"] == len(finding["paths"]), finding["finding_id"]
        assert finding["kind"], finding["finding_id"]
        assert finding["owner"], finding["finding_id"]
        assert finding["current_status"] in {
            "observed",
            "not_observed",
            "needs_review",
        }


def test_inventory_captures_phase_0_1_last_mile_regressions() -> None:
    by_id = {
        finding["finding_id"]: finding
        for finding in _inventory()["findings"]
    }

    scientist_loose = by_id["LM-001"]
    assert scientist_loose["kind"] == "package_root_loose_python"
    assert scientist_loose["package"] == "scientist"
    assert scientist_loose["count"] <= 1
    assert scientist_loose["paths"] in ([], ["src/polisyos/scientist/api.py"])

    single_file_shells = by_id["LM-002"]
    assert single_file_shells["kind"] == "single_file_shell_package"
    assert 0 < single_file_shells["count"] <= 12
    assert any(path.startswith("src/polisyos/fabric/") for path in single_file_shells["paths"])
    assert any(path.startswith("src/polisyos/ir/") for path in single_file_shells["paths"])
    assert "src/polisyos/fabric/extensions" in single_file_shells["paths"]
    assert "src/polisyos/ir/schemas" in single_file_shells["paths"]

    assert by_id["LM-003"]["paths"] == []
    assert by_id["LM-003"]["current_status"] == "not_observed"
    assert by_id["LM-004"]["paths"] == [
        "src/polisyos/scientist/orchestration",
    ]

    semantic_pairs = {
        tuple(pair["paths"])
        for pair in by_id["LM-005"]["metadata"]["semantic_pairs"]
    }
    assert semantic_pairs == set()
    assert by_id["LM-005"]["current_status"] == "not_observed"

    assert by_id["LM-015"]["kind"] == "cross_cutting_concern_duplicate"
    assert by_id["LM-015"]["count"] > 0
    assert by_id["LM-016"]["kind"] == "scientist_parallel_family"
    assert by_id["LM-016"]["count"] == 0
    assert by_id["LM-016"]["current_status"] == "not_observed"
    assert by_id["LM-017"]["kind"] == "repeated_cross_package_name"
    assert by_id["LM-017"]["count"] > 0


def test_inventory_records_sunset_metadata_and_schema_residue() -> None:
    by_id = {
        finding["finding_id"]: finding
        for finding in _inventory()["findings"]
    }

    for finding_id in ("LM-006", "LM-010", "LM-012"):
        finding = by_id[finding_id]
        assert "sunset" in finding
        assert set(finding["sunset"]) >= {
            "metadata_present",
            "sunset_date",
            "source",
        }

    assert by_id["LM-006"]["count"] == 0
    assert by_id["LM-006"]["current_status"] == "not_observed"
    assert by_id["LM-006"]["sunset"]["sunset_date"] is None
    assert by_id["LM-010"]["sunset"]["source"] is None
    assert by_id["LM-012"]["sunset"]["source"] == "frontend/README.md"
    for finding_id in ("LM-010", "LM-012"):
        sunset = by_id[finding_id]["sunset"]
        assert sunset["metadata_present"] == (sunset["sunset_date"] is not None)

    schemas = by_id["LM-022"]
    assert schemas["kind"] == "top_level_schema_python_cache_residue"
    assert all(path.startswith("schemas/") for path in schemas["paths"])


def test_inventory_excludes_generated_and_ignored_paths_from_product_findings() -> None:
    generated_prefixes = (
        ".venv/",
        "_build/",
        "_cache/",
        "apps/runtime-dashboard/node_modules/",
        "apps/runtime-reference-shell/node_modules/",
        "node_modules/",
    )
    allowed_generated_kinds = {
        "local_ignored_residue",
        "top_level_schema_python_cache_residue",
    }

    for finding in _inventory()["findings"]:
        if finding["kind"] in allowed_generated_kinds:
            continue
        assert not any(
            path.startswith(generated_prefixes) for path in finding["paths"]
        ), finding["finding_id"]


def test_inventory_keeps_local_ignored_residue_out_of_committed_baseline(
    monkeypatch,
) -> None:
    last_mile = _module()
    monkeypatch.setattr(
        last_mile,
        "_collect_local_ignored_residue",
        lambda _repo_root: ["_build/phase7-local-junk-synthetic"],
    )

    default = last_mile.collect_inventory(REPO_ROOT)
    with_local = last_mile.collect_inventory(
        REPO_ROOT,
        include_local_ignored_residue=True,
    )

    default_lm009 = next(
        finding for finding in default["findings"] if finding["finding_id"] == "LM-009"
    )
    local_lm009 = next(
        finding for finding in with_local["findings"] if finding["finding_id"] == "LM-009"
    )
    assert default_lm009["paths"] == []
    assert local_lm009["paths"] == ["_build/phase7-local-junk-synthetic"]


def test_json_output_cli_and_committed_baseline_are_machine_readable(tmp_path: Path) -> None:
    output_path = tmp_path / "inventory.json"

    completed = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "tools/quality/validation/repository_last_mile_inventory.py",
            "--json-output",
            str(output_path),
        ],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "last-mile inventory" in completed.stdout.lower()
    generated = json.loads(output_path.read_text(encoding="utf-8"))
    baseline = json.loads(
        (
            REPO_ROOT
            / "architecture/baselines/repository_best_in_class_last_mile/inventory.json"
        ).read_text(encoding="utf-8")
    )
    assert generated == baseline


def test_unreadable_tracked_reference_is_ambiguous_instead_of_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    last_mile = _module()
    path = tmp_path / "docs/live.md"
    path.parent.mkdir()
    path.write_text(f"Use {LEGACY_DASHBOARD_PATH}.\n", encoding="utf-8")
    monkeypatch.setattr(last_mile, "_tracked_paths", lambda _root: {"docs/live.md"})
    original = Path.read_text

    def unreadable(current: Path, *args: object, **kwargs: object) -> str:
        if current == path:
            raise PermissionError(13, "Permission denied", str(current))
        return original(current, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)
    assert last_mile.main(["--repo-root", str(tmp_path)]) == 1
    assert "ambiguous inventory input: PermissionError" in capsys.readouterr().err


@pytest.mark.parametrize("payload", [b"{", b"[]", b"\xff"])
def test_invalid_json_inventory_input_is_not_an_empty_object(
    tmp_path: Path, payload: bytes
) -> None:
    path = tmp_path / "inventory.json"
    path.write_bytes(payload)
    with pytest.raises((ValueError, UnicodeError)):
        _module()._load_json(path)


def test_invalid_utf8_tracked_text_is_not_silently_reduced(tmp_path: Path) -> None:
    path = tmp_path / "live.md"
    path.write_bytes(b"front\xffend/runtime-dashboard")
    with pytest.raises(UnicodeError):
        _module()._read_text(path)


def test_missing_optional_sunset_metadata_remains_absent(tmp_path: Path) -> None:
    assert _module()._extract_sunset(tmp_path / "README.md", tmp_path) == {
        "metadata_present": False,
        "sunset_date": None,
        "source": None,
    }


def test_failed_git_census_cannot_fall_back_to_station_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _module().main(["--repo-root", str(tmp_path)]) == 1
    assert "ambiguous inventory input: CalledProcessError" in capsys.readouterr().err


def test_selected_repository_owns_default_baseline_and_genuine_drift_stays_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    last_mile = _module()
    selected = tmp_path / "selected"
    baseline = selected / "architecture/baselines/repository_best_in_class_last_mile/inventory.json"
    baseline.parent.mkdir(parents=True)
    current = {"fixture": "selected repository"}
    baseline.write_text(last_mile.dump_json(current), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(selected)], check=True)
    subprocess.run(["git", "add", "."], cwd=selected, check=True)
    monkeypatch.setattr(last_mile, "collect_inventory", lambda _root: current)
    assert last_mile.check_artifacts(selected) == []
    baseline.write_text(last_mile.dump_json({"fixture": "different commit"}), encoding="utf-8")
    assert last_mile.check_artifacts(selected) == [
        "baseline drift: architecture/baselines/repository_best_in_class_last_mile/inventory.json"
    ]


def test_untracked_baseline_cannot_authorize_a_clean_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    last_mile = _module()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    baseline = tmp_path / "architecture/baselines/repository_best_in_class_last_mile/inventory.json"
    baseline.parent.mkdir(parents=True)
    current = {"fixture": "untracked baseline"}
    baseline.write_text(last_mile.dump_json(current), encoding="utf-8")
    monkeypatch.setattr(last_mile, "collect_inventory", lambda _root: current)
    assert last_mile.check_artifacts(tmp_path) == [
        "missing baseline: architecture/baselines/repository_best_in_class_last_mile/inventory.json"
    ]


def test_selected_repository_owns_phase0_4_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    last_mile = _module()
    sections = (
        "name_collisions", "cross_cutting_concerns", "scientist_parallel_implementations"
    )
    current = {section: {"fixture": section} for section in sections}
    monkeypatch.setattr(last_mile, "collect_inventory", lambda *args, **kwargs: current)
    monkeypatch.setattr(last_mile, "validate_inventory", lambda _inventory: [])
    assert last_mile.main([
        "--repo-root", str(tmp_path), "--write-phase0-4-baselines"
    ]) == 0
    baseline_dir = tmp_path / "architecture/baselines/repository_best_in_class_last_mile"
    for section in sections:
        assert json.loads((baseline_dir / f"{section}.json").read_text()) == current[section]
    assert "Wrote Phase 0.4" in capsys.readouterr().out


def test_new_journal_evidence_does_not_become_a_live_frontend_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    last_mile = _module()
    documents = {
        "docs/live.md": f"Use {LEGACY_DASHBOARD_PATH}.\n",
        "docs/superpowers/journals/new-independent-observation.md": (
            f"Observed {LEGACY_DASHBOARD_PATH} at the recorded commit.\n"
        ),
        "docs/superpowers/journals/new-independent-observation.json": json.dumps({
            "observed_reference": LEGACY_DASHBOARD_PATH
        }),
    }
    for relative, text in documents.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(last_mile, "_tracked_paths", lambda _root: set(documents))
    assert last_mile._collect_frontend_mentions(tmp_path) == ["docs/live.md"]


def _inventory_station(tmp_path: Path) -> Path:
    root = tmp_path / "station"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    product = root / "policy-engine"
    tracked = {
        "pyproject.toml": '[project]\nname="probe"\nversion="0"\n',
        "src/polisyos/fabric/__init__.py": "",
        "src/polisyos/fabric/anchor/__init__.py": "",
        "src/polisyos/scientist/__init__.py": "",
        "src/polisyos/scientist/evidence/__init__.py": "",
        "src/polisyos/ir/__init__.py": "",
        "src/polisyos/ir/references/__init__.py": "",
        "ops/components/probe/slo.yaml": "{}",
        "architecture/base-gate.toml": "",
        "architecture/gates/base.toml": "",
        "schemas/README.md": "",
        "frontend/placeholder.txt": "",
    }
    for relative, text in tracked.items():
        path = product / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=Inventory probe",
         "-c", "user.email=probe@example.invalid", "commit", "-qm", "inventory fixture"],
        cwd=root, check=True,
    )
    return product


def test_inventory_all_scans_ignore_station_debris_and_keep_tracked_additions(
    tmp_path: Path,
) -> None:
    last_mile = _module()
    product = _inventory_station(tmp_path)
    clean = tmp_path / "clean"
    subprocess.run(
        ["git", "worktree", "add", "--detach", str(clean), "HEAD"],
        cwd=product, check=True, capture_output=True,
    )
    before = last_mile.collect_inventory(clean / "policy-engine")
    debris = {
        "architecture/local-station-gate.toml": "",
        "architecture/gates/local.toml": "",
        "architecture/local-concern.toml": "",
        "architecture/packages/layout.toml": '[single_file_shell_package_policy]\nmax_python_files=8\n',
        "architecture/name_registry.toml": '[[shared_name]]\nname="evidence"\n',
        "architecture/policies/cross_cutting_concerns.toml": '[[concern]]\nname="security"\n',
        "architecture/module_size_budget.toml": '[[budget]]\npath="local.py"\ncurrent_lines=9\ntarget_lines=1\n',
        "architecture/baselines/repository_best_in_class_phase0_4/verification_inventory.json": (
            '{"ratchet_starting_points":[{"package":"scientist","mirror_floor":99}]}'
        ),
        "src/polisyos/fabric/anchor/local.py": "",
        "src/polisyos/fabric/security/__init__.py": "",
        "src/polisyos/scientist/security.py": "",
        "src/polisyos/scientist/evidence_sources.py": "",
        "src/polisyos/ir/refs/__init__.py": "",
        "schemas/local.py": "",
        "schemas/__pycache__/local.pyc": "",
        "ops/components/local/slo.yaml": "{}",
        "ops/components/probe/alerts.yml": "",
        "ops/components/probe/dashboard.json": "{}",
        "ops/components/probe/retention-policy.toml": "",
        "ops/components/probe/runtime-contract.toml": "",
        "frontend/README.md": "Sunset 2099-01-01\n",
        "docs/adr/index.md": "",
    }
    for relative, text in debris.items():
        path = product / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert last_mile.collect_inventory(product) == before
    observed = "architecture/local-station-gate.toml"
    subprocess.run(["git", "add", observed], cwd=product, check=True)
    after = last_mile.collect_inventory(product)
    assert after != before
    assert observed in next(
        row["paths"] for row in after["findings"] if row["finding_id"] == "LM-013"
    )


@pytest.mark.parametrize("dangling", [False, True])
def test_inventory_missing_tracked_path_is_ambiguous(
    tmp_path: Path, dangling: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    product = _inventory_station(tmp_path)
    path = product / "architecture/base-gate.toml"
    path.unlink()
    if dangling:
        path.symlink_to("missing-target")
    assert _module().main(["--repo-root", str(product)]) == 1
    assert "ambiguous inventory input" in capsys.readouterr().err


def test_tracked_optional_input_disappearing_during_read_stays_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    product = _inventory_station(tmp_path)
    original = Path.read_text

    def disappear(path: Path, *args: object, **kwargs: object) -> str:
        if path == product / "pyproject.toml":
            raise FileNotFoundError(2, "Disappeared", str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", disappear)
    assert _module().main(["--repo-root", str(product)]) == 1
    assert "ambiguous inventory input: FileNotFoundError" in capsys.readouterr().err


def test_inventory_git_census_preserves_complete_filename_boundaries(tmp_path: Path) -> None:
    product = _inventory_station(tmp_path)
    names = ("docs/with space.md", "docs/with\nnewline.md", "docs/with-é.md")
    for name in names:
        path = product / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Use {LEGACY_DASHBOARD_PATH}.\n", encoding="utf-8")
    subprocess.run(["git", "add", "docs"], cwd=product, check=True)
    payload = _module().collect_inventory(product)
    assert next(row["paths"] for row in payload["findings"] if row["finding_id"] == "LM-025") == (
        sorted(names)
    )


def test_inventory_keeps_tracked_symlink_identity_lexical(tmp_path: Path) -> None:
    product = _inventory_station(tmp_path)
    target = product / "src/polisyos/scientist/api.py"
    target.write_text("", encoding="utf-8")
    alias = target.with_name("alias.py")
    alias.symlink_to(target.name)
    subprocess.run(["git", "add", "src"], cwd=product, check=True)
    payload = _module().collect_inventory(product)
    assert next(row["paths"] for row in payload["findings"] if row["finding_id"] == "LM-001") == [
        "src/polisyos/scientist/alias.py", "src/polisyos/scientist/api.py"
    ]
