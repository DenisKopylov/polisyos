from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

from tools.quality.validation import architecture_report_only_contracts as contracts
from tools.quality.validation import check_package_import_gates
from tools.quality.validation import directory_health

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent

PHASE6_1_GATE_IDS = {
    "root-facade-package-layout",
    "package-boundary",
    "public-surface",
    "deep-import",
    "dynamic-import",
    "import-cycle",
    "package-layout",
    "name-collision",
    "shim-expiry",
    "importable-root-contracts",
    "schema-only-root",
    "module-size-ratchet",
    "scientist-first-level-package-count",
    "single-file-shell-package",
    "cross-cutting-concern-home",
}
SCIENTIST_PHASE2_1_ROOT_SHIM_PATHS = {
    "src/polisyos/scientist/decision_validity.py",
    "src/polisyos/scientist/error_semantics.py",
    "src/polisyos/scientist/evidence_sources.py",
    "src/polisyos/scientist/feedback_utils.py",
    "src/polisyos/scientist/frontier_runtime.py",
    "src/polisyos/scientist/latent_separation.py",
    "src/polisyos/scientist/llm_cycle.py",
    "src/polisyos/scientist/publisher.py",
    "src/polisyos/scientist/reliability_scorecard.py",
    "src/polisyos/scientist/remediation_status.py",
    "src/polisyos/scientist/replay_backend.py",
}
PHASE6_7_VALIDATION_BUDGET_PATHS = {
    "tools/quality/validation/check_package_import_gates.py",
    "tools/quality/validation/directory_health.py",
    "tools/quality/validation/check_docs_lifecycle.py",
    "tools/quality/validation/repository_last_mile_inventory.py",
    "tools/quality/validation/check_extension_examples.py",
    "tools/quality/validation/architecture_report_only_contracts.py",
}


def test_phase6_1_import_boundary_report_emits_package_level_deltas() -> None:
    payload = contracts.build_report(REPO_ROOT, report="dependency-graph")
    summary = payload["summary"]["import_boundary"]

    assert payload["contract_error_count"] == 0
    assert summary["rule"].startswith("first-party cross-package imports")
    assert isinstance(summary["package_level_deltas"], list)
    assert summary["package_level_deltas"]
    assert {
        "source_package",
        "target_package",
        "baseline_hidden_edges",
        "current_hidden_edges",
        "delta_hidden_edges",
        "registered_added_hidden_edges",
        "unregistered_added_hidden_edges",
    } <= set(summary["package_level_deltas"][0])
    assert summary["public_surface_import_contract"]["drift_count"] == 0
    assert summary["public_surface_import_contract"]["inventory_drift_count"] == 0


def test_phase6_1_conversion_report_covers_all_package_import_gates() -> None:
    payload = contracts.build_report(REPO_ROOT, report="phase6-1")
    summary = payload["summary"]

    assert payload["contract_error_count"] == 0
    assert {
        "import_boundary",
        "package_boundary",
        "dynamic_imports",
        "import_cycles",
        "package_layout",
        "name_collisions",
        "shim_debt",
        "phase6_1",
    } <= set(summary)
    assert summary["phase6_1"]["status"] == "report_only_conversion"
    assert {
        "package-boundary",
        "public-surface",
        "deep-import",
        "dynamic-import",
        "import-cycle",
        "name-collision",
        "shim-expiry",
    } <= set(summary["phase6_1"]["converted_gates"])
    assert summary["package_boundary"]["package_level_forbidden_edges"]
    assert summary["dynamic_imports"]["missing_target_slots"] == 0
    assert summary["import_cycles"]["new_cycle_count"] == 0
    assert summary["package_layout"]["mode"] == "report_only"
    assert summary["name_collisions"]["mode"] == "report_only"
    assert summary["shim_debt"]["expired_count"] == 0


def test_phase6_1_report_only_gate_registry_lists_converted_gates() -> None:
    payload = tomllib.loads(
        (REPO_ROOT / "architecture" / "gates" / "report_only.toml").read_text()
    )
    gate_ids = {gate["id"] for gate in payload["gate"]}

    assert {
        "import-boundary-report",
        "dynamic-import-registry",
        "phase6-1-package-import-gate-conversion",
        "import-cycle-registry",
        "package-layout-root-facade",
        "name-collision-registry",
        "shim-expiry-registry",
    }.isdisjoint(gate_ids)


def test_phase6_1_fail_closed_gate_contract_is_active_and_wired() -> None:
    contract = tomllib.loads(
        (REPO_ROOT / "architecture" / "gates" / "package_import.toml").read_text()
    )
    header = contract["package_import_gates"]
    gates = {gate["id"]: gate for gate in contract["gate"]}

    assert header["status"] == "fail_closed"
    assert header["phase"] == "repository-best-in-class-phase-6.1"
    assert (
        header["gate_command"]
        == "uv run polisyos-tools validation check-package-import-gates --fail-closed"
    )
    assert PHASE6_1_GATE_IDS <= set(gates)
    assert header["active_source_move_report_only_blockers"] == []
    for gate_id in PHASE6_1_GATE_IDS:
        gate = gates[gate_id]
        assert gate["mode"] == "fail_closed", gate_id
        assert gate["owner"].startswith("team-"), gate_id
        assert gate["source_contracts"], gate_id
        assert gate["blocks"], gate_id

    workflow = (WORKSPACE_ROOT / ".github/workflows/abi.yml").read_text(encoding="utf-8")
    assert "check-package-import-gates" in workflow
    assert "--fail-closed" in workflow


def test_phase1_1_single_file_shell_policy_is_wired_to_package_import_gates() -> None:
    contract = tomllib.loads(
        (REPO_ROOT / "architecture" / "gates" / "package_import.toml").read_text()
    )
    gates = {gate["id"]: gate for gate in contract["gate"]}
    policy = contract["single_file_shell_package_policy"]
    directory_contracts = tomllib.loads(
        (REPO_ROOT / "architecture" / "policies" / "directory_contracts.toml").read_text()
    )
    local_docs = directory_contracts["single_file_shell_package_local_documentation"]

    assert "single-file-shell-package" in gates
    assert policy["status"] == "fail_closed"
    assert policy["scope_roots"] == ["src/polisyos/fabric", "src/polisyos/ir"]
    assert policy["exception_required_fields"] == [
        "path",
        "owner",
        "rationale",
        "sunset",
        "migration_target",
        "smoke_import_test",
    ]
    assert policy["latest_allowed_sunset"] == "2026-07-31"
    assert local_docs["accepted_local_documents"] == ["README.md"]
    assert {"single module", "intentional"} <= set(local_docs["required_markers"])


def test_phase6_1_fail_closed_cli_report_passes_current_contract() -> None:
    spec = importlib.util.find_spec("tools.quality.validation.check_package_import_gates")
    assert spec is not None

    report = check_package_import_gates.build_report(REPO_ROOT)

    assert report["phase"] == "repository-best-in-class-phase-6.1"
    assert report["mode"] == "fail_closed"
    assert report["status"] == "passed", report["findings"]
    assert report["finding_count"] == 0, report["findings"]
    assert report["summary"]["import_boundary"]["unregistered_added_hidden_edge_count"] == 0
    assert report["summary"]["package_boundary"]["unregistered_forbidden_edge_count"] == 0
    assert report["summary"]["dynamic_imports"]["missing_target_slots"] == 0
    assert report["summary"]["import_cycles"]["new_cycle_count"] == 0
    assert report["summary"]["shim_debt"]["expired_count"] == 0
    assert report["summary"]["importable_roots"]["finding_count"] == 0
    assert report["summary"]["schema_only"]["finding_count"] == 0
    assert report["summary"]["root_file_exceptions"]["finding_count"] == 0
    assert report["summary"]["scientist_layout"]["finding_count"] == 0
    assert report["summary"]["scientist_root_facade"]["finding_count"] == 0
    assert report["summary"]["module_size_ratchet"]["finding_count"] == 0
    assert report["summary"]["single_file_shell_packages"]["finding_count"] == 0
    assert report["summary"]["cross_cutting_concerns"]["finding_count"] == 0


def test_phase2_1_scientist_root_facade_summary_reports_registered_shims() -> None:
    report = check_package_import_gates.build_report(REPO_ROOT)
    summary = report["summary"]["scientist_root_facade"]

    assert summary["root_loose_py_count"] == 11
    assert summary["registered_root_py_shim_count"] == 11
    assert summary["canonical_first_level_root_count"] == 18
    assert summary["compatibility_shim_root_count"] == 21
    assert summary["duplicate_package_file_pair_count"] == 5
    assert summary["wave2_root_file_debt_count"] == 0
    assert summary["unregistered_root_py_count"] == 0
    assert set(summary["registered_root_py_shim_files"]) == SCIENTIST_PHASE2_1_ROOT_SHIM_PATHS


def test_phase2_1_scientist_contract_tracks_resolved_root_shims() -> None:
    package_contract = tomllib.loads(
        (REPO_ROOT / "architecture" / "packages" / "scientist.toml").read_text()
    )
    shim_contract = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text())
    layout = package_contract["layout"]
    registered_root_shims = {
        entry["source_path"]: entry
        for entry in shim_contract["shim"]
        if entry.get("type") == "python_reexport"
        and str(entry.get("source_path", "")).startswith("src/polisyos/scientist/")
        and str(entry.get("source_path", "")).count("/") == 3
        and str(entry.get("source_path", "")).endswith(".py")
    }

    assert layout["status"] == "resolved_root_facade"
    assert layout["legacy_layout_status"] == "resolved_root_facade"
    assert "root_facade_wave2_debt" not in package_contract
    assert SCIENTIST_PHASE2_1_ROOT_SHIM_PATHS <= set(registered_root_shims)
    for path in SCIENTIST_PHASE2_1_ROOT_SHIM_PATHS:
        entry = registered_root_shims[path]
        assert entry["owner"] == "team-scientist"
        assert entry["sunset_date"] <= "2026-12-31"
        assert entry["reason"]
        assert entry["target_path"].startswith("src/polisyos/scientist/")


def test_phase7_undocumented_top_level_namespace_root_fails(tmp_path: Path) -> None:
    (tmp_path / "rogue_namespace").mkdir()
    _write_minimal_directory_contracts(
        tmp_path,
        contracts=[
            {
                "path": "architecture",
                "python_import_policy": "namespace_only_non_product_no_python_code",
            }
        ],
    )

    findings = check_package_import_gates._check_importable_root_contracts(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "importable-root-contracts",
            "rogue_namespace",
            "top-level importable or namespace-capable root lacks a directory contract",
        )
    ]


def test_phase7_top_level_schemas_root_rejects_python_code(tmp_path: Path) -> None:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "example.py").write_text("VALUE = 1\n", encoding="utf-8")

    findings = check_package_import_gates._check_schema_only_root(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "schema-only-root",
            "schemas/example.py",
            "top-level schemas/ may contain schemas and generated snapshots, not Python code",
        )
    ]


def test_phase6_4_top_level_schemas_root_rejects_cache_residue(tmp_path: Path) -> None:
    cache_root = tmp_path / "schemas" / "snapshots" / "__pycache__"
    cache_root.mkdir(parents=True)
    (cache_root / "abi_models.cpython-312.pyc").write_bytes(b"cache")

    findings = check_package_import_gates._check_schema_only_root(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "schema-only-root",
            "schemas/snapshots/__pycache__",
            "top-level schemas/ must not contain Python cache residue",
        )
    ]


def test_phase6_4_directory_health_rejects_schema_cache_residue(tmp_path: Path) -> None:
    cache_root = tmp_path / "schemas" / "snapshots" / "__pycache__"
    cache_root.mkdir(parents=True)
    (cache_root / "abi_models.cpython-312.pyc").write_bytes(b"cache")

    findings = directory_health._schema_pure_data_findings(tmp_path)

    assert findings == [
        directory_health.Finding(
            "schema-only-root",
            "blocker",
            "schemas/snapshots/__pycache__",
            "top-level schemas/ must not contain Python code or cache residue",
        )
    ]


def test_phase6_4_top_level_schemas_root_rejects_product_imports(tmp_path: Path) -> None:
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "abi_models.py").write_text(
        "from polisyos.schemas.abi_models import ABI_MODELS\n",
        encoding="utf-8",
    )

    findings = check_package_import_gates._check_schema_only_root(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "schema-only-root",
            "schemas/abi_models.py",
            "top-level schemas/ may contain schemas and generated snapshots, not Python code",
        ),
        check_package_import_gates.Finding(
            "schema-only-root",
            "schemas/abi_models.py",
            "top-level schemas/ Python residue must not import product modules",
            "polisyos.schemas.abi_models",
        ),
    ]


def test_phase6_4_top_level_schemas_contract_is_pure_data() -> None:
    directory_contracts = tomllib.loads(
        (REPO_ROOT / "architecture" / "policies" / "directory_contracts.toml").read_text()
    )
    topology = tomllib.loads((REPO_ROOT / "architecture" / "topology.toml").read_text())
    schemas_contract = next(
        item for item in directory_contracts["contract"] if item["path"] == "schemas"
    )
    schemas_topology = next(item for item in topology["path"] if item["path"] == "schemas")

    assert "schemas" not in {
        item["path"] for item in directory_contracts.get("non_product_python_root", [])
    }
    assert schemas_contract["status"] == "active"
    assert schemas_contract["python_import_policy"] == "not_importable_schema_data_only"
    assert schemas_contract["allowed_file_kinds"] == [
        "schema_snapshot",
        "generated_committed",
        "documentation",
    ]
    assert schemas_topology["content_policy"] == "pure_schema_data_only_no_python"


def test_phase6_4_schema_python_wrapper_lives_under_src_polisyos() -> None:
    assert not (REPO_ROOT / "schemas" / "abi_models.py").exists()
    assert (REPO_ROOT / "src" / "polisyos" / "schemas" / "abi_models.py").is_file()


def test_phase7_unregistered_package_root_python_file_fails(tmp_path: Path) -> None:
    package_root = tmp_path / "src" / "polisyos" / "demo"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "extra.py").write_text("VALUE = 1\n", encoding="utf-8")
    _write_minimal_package_layout(tmp_path)

    findings = check_package_import_gates._check_root_file_exceptions(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "root-file-exception",
            "src/polisyos/demo/extra.py",
            "package root Python file is neither an allowed facade, registered shim, "
            "nor dated root-file exception",
        )
    ]


def test_phase7_unregistered_scientist_first_level_root_fails(tmp_path: Path) -> None:
    root = tmp_path / "src" / "polisyos" / "scientist" / "rogue"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    package_contract = tmp_path / "architecture" / "packages"
    package_contract.mkdir(parents=True)
    (package_contract / "scientist.toml").write_text(
        "\n".join(
            (
                "[layout]",
                "implementation_roots = []",
                "compatibility_shim_roots = []",
                "canonical_first_level_root_cap = 0",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_package_import_gates._check_scientist_first_level_roots(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "scientist-layout",
            "src/polisyos/scientist/rogue",
            "Scientist first-level root is not canonical, registered compatibility debt, "
            "or explicitly ignored",
        )
    ]


def test_phase0_2_undocumented_loose_scientist_root_python_file_fails(
    tmp_path: Path,
) -> None:
    scientist_root = tmp_path / "src" / "polisyos" / "scientist"
    scientist_root.mkdir(parents=True)
    (scientist_root / "__init__.py").write_text("", encoding="utf-8")
    (scientist_root / "api.py").write_text("", encoding="utf-8")
    (scientist_root / "rogue.py").write_text("VALUE = 1\n", encoding="utf-8")
    package_contract = tmp_path / "architecture" / "packages"
    package_contract.mkdir(parents=True)
    (package_contract / "scientist.toml").write_text(
        "\n".join(
            (
                "[layout]",
                'source_root = "src/polisyos/scientist"',
                'compatibility_shim_roots = []',
                'ignored_first_level_roots = ["__pycache__"]',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    _write_minimal_package_layout(tmp_path)

    findings = check_package_import_gates._check_scientist_root_python_files(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "scientist-root-file",
            "src/polisyos/scientist/rogue.py",
            "Scientist root Python file is neither an allowed facade nor a registered "
            "compatibility shim",
        )
    ]


def test_phase2_1_scientist_root_file_exception_does_not_bypass_registered_shims(
    tmp_path: Path,
) -> None:
    scientist_root = tmp_path / "src" / "polisyos" / "scientist"
    scientist_root.mkdir(parents=True)
    (scientist_root / "__init__.py").write_text("", encoding="utf-8")
    (scientist_root / "rogue.py").write_text("VALUE = 1\n", encoding="utf-8")
    package_contract = tmp_path / "architecture" / "packages"
    package_contract.mkdir(parents=True)
    (package_contract / "scientist.toml").write_text(
        "\n".join(
            (
                "[layout]",
                'source_root = "src/polisyos/scientist"',
                'status = "resolved_root_facade"',
                'compatibility_shim_roots = []',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    _write_minimal_package_layout(
        tmp_path,
        extra_lines=[
            "",
            "[[root_file_exception]]",
            'path = "src/polisyos/scientist/rogue.py"',
            'owner = "team-scientist"',
            'sunset = "2026-07-31"',
            'reason = "Temporary root helper."',
        ],
    )

    findings = check_package_import_gates._check_scientist_root_python_files(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "scientist-root-file",
            "src/polisyos/scientist/rogue.py",
            "Scientist root Python file is neither an allowed facade nor a registered "
            "compatibility shim",
        )
    ]


def test_phase0_2_single_file_shell_package_without_exception_fails(
    tmp_path: Path,
) -> None:
    shell_package = tmp_path / "src" / "polisyos" / "fabric" / "legacy_helper"
    shell_package.mkdir(parents=True)
    (shell_package / "__init__.py").write_text(
        "from polisyos.fabric.legacy_helper_impl import LegacyHelper\n",
        encoding="utf-8",
    )
    _write_minimal_package_layout(
        tmp_path,
        extra_lines=[
            "",
            "[single_file_shell_package_policy]",
            'status = "fail_closed"',
            'scope_roots = ["src/polisyos/fabric"]',
            "max_python_files = 1",
            'allowed_facade_packages = []',
        ],
    )

    findings = check_package_import_gates._check_single_file_shell_packages(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "single-file-shell-package",
            "src/polisyos/fabric/legacy_helper",
            "single-file shell package is neither an allowed facade nor a dated exception",
        )
    ]


def test_phase1_1_single_file_shell_package_uses_package_import_gate_policy(
    tmp_path: Path,
) -> None:
    shell_package = tmp_path / "src" / "polisyos" / "fabric" / "legacy_helper"
    shell_package.mkdir(parents=True)
    (shell_package / "__init__.py").write_text(
        "from polisyos.fabric._legacy_helper import LegacyHelper\n",
        encoding="utf-8",
    )
    _write_minimal_package_import_gates(tmp_path)

    findings = check_package_import_gates._check_single_file_shell_packages(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "single-file-shell-package",
            "src/polisyos/fabric/legacy_helper",
            "single-file shell package is neither an allowed facade, locally documented, "
            "nor covered by a dated exception",
        )
    ]


def test_phase1_1_single_file_shell_package_local_readme_allows_intentional_module(
    tmp_path: Path,
) -> None:
    shell_package = tmp_path / "src" / "polisyos" / "fabric" / "legacy_helper"
    shell_package.mkdir(parents=True)
    (shell_package / "__init__.py").write_text(
        "from polisyos.fabric._legacy_helper import LegacyHelper\n",
        encoding="utf-8",
    )
    (shell_package / "README.md").write_text(
        "This package is intentionally a single module because it is a stable public "
        "facade over generated extension imports.\n",
        encoding="utf-8",
    )
    _write_minimal_directory_contracts(tmp_path, contracts=[])
    _write_minimal_package_layout(
        tmp_path,
        extra_lines=[
            "",
            "[single_file_shell_package_policy]",
            'status = "fail_closed"',
            'scope_roots = ["src/polisyos/fabric"]',
            "max_python_files = 1",
            'allowed_facade_packages = []',
        ],
    )

    assert check_package_import_gates._check_single_file_shell_packages(tmp_path) == []


def test_phase1_1_single_file_shell_exception_requires_migration_target_and_smoke_test(
    tmp_path: Path,
) -> None:
    shell_package = tmp_path / "src" / "polisyos" / "fabric" / "legacy_helper"
    shell_package.mkdir(parents=True)
    (shell_package / "__init__.py").write_text(
        "from polisyos.fabric._legacy_helper import LegacyHelper\n",
        encoding="utf-8",
    )
    _write_minimal_package_import_gates(
        tmp_path,
        extra_lines=[
            "",
            "[[single_file_shell_package_exception]]",
            'path = "src/polisyos/fabric/legacy_helper"',
            'owner = "team-fabric"',
            'rationale = "Legacy facade is waiting for Wave 3 consolidation."',
            'sunset = "2026-07-31"',
        ],
    )

    findings = check_package_import_gates._check_single_file_shell_packages(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "single-file-shell-package",
            "src/polisyos/fabric/legacy_helper",
            "single-file shell package exception missing `migration_target`",
        ),
        check_package_import_gates.Finding(
            "single-file-shell-package",
            "src/polisyos/fabric/legacy_helper",
            "single-file shell package exception missing `smoke_import_test`",
        ),
    ]


def test_phase1_1_wrapper_only_shell_exception_cannot_outlive_wave3(
    tmp_path: Path,
) -> None:
    shell_package = tmp_path / "src" / "polisyos" / "fabric" / "legacy_helper"
    shell_package.mkdir(parents=True)
    (shell_package / "__init__.py").write_text(
        "from polisyos.fabric._legacy_helper import LegacyHelper\n",
        encoding="utf-8",
    )
    smoke_test = tmp_path / "tests" / "unit" / "fabric" / "test_smoke.py"
    smoke_test.parent.mkdir(parents=True)
    smoke_test.write_text(
        "def test_smoke() -> None:\n"
        "    import polisyos.fabric.legacy_helper\n"
        "    assert polisyos.fabric.legacy_helper\n",
        encoding="utf-8",
    )
    _write_minimal_package_import_gates(
        tmp_path,
        extra_lines=[
            "",
            "[[single_file_shell_package_exception]]",
            'path = "src/polisyos/fabric/legacy_helper"',
            'owner = "team-fabric"',
            'rationale = "Legacy facade is waiting for Wave 3 consolidation."',
            'sunset = "2026-08-01"',
            'migration_target = "polisyos.fabric.evidence.legacy_helper"',
            'smoke_import_test = "tests/unit/fabric/test_smoke.py::test_smoke"',
            "created_to_wrap_formerly_loose_file = true",
        ],
    )

    findings = check_package_import_gates._check_single_file_shell_packages(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "single-file-shell-package",
            "src/polisyos/fabric/legacy_helper",
            "single-file shell package exception sunset must be no later than the Wave 3 cutoff",
            "sunset=2026-08-01 cutoff=2026-07-31",
        )
    ]


def test_phase1_1_shell_exception_smoke_import_test_nodeid_must_exist(
    tmp_path: Path,
) -> None:
    shell_package = tmp_path / "src" / "polisyos" / "fabric" / "legacy_helper"
    shell_package.mkdir(parents=True)
    (shell_package / "__init__.py").write_text(
        "from polisyos.fabric._legacy_helper import LegacyHelper\n",
        encoding="utf-8",
    )
    smoke_test = tmp_path / "tests" / "unit" / "fabric" / "test_smoke.py"
    smoke_test.parent.mkdir(parents=True)
    smoke_test.write_text("def test_unrelated() -> None:\n    pass\n", encoding="utf-8")
    _write_minimal_package_import_gates(
        tmp_path,
        extra_lines=[
            "",
            "[[single_file_shell_package_exception]]",
            'path = "src/polisyos/fabric/legacy_helper"',
            'owner = "team-fabric"',
            'rationale = "Legacy facade is waiting for Wave 3 consolidation."',
            'sunset = "2026-07-31"',
            'migration_target = "polisyos.fabric.grouped.legacy_helper"',
            'smoke_import_test = "tests/unit/fabric/test_smoke.py::test_missing_node"',
        ],
    )

    findings = check_package_import_gates._check_single_file_shell_packages(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "single-file-shell-package",
            "src/polisyos/fabric/legacy_helper",
            "single-file shell package exception smoke_import_test node id is missing",
            "tests/unit/fabric/test_smoke.py::test_missing_node",
        )
    ]


def test_phase1_1_shell_exception_smoke_import_test_must_cover_package(
    tmp_path: Path,
) -> None:
    shell_package = tmp_path / "src" / "polisyos" / "fabric" / "legacy_helper"
    shell_package.mkdir(parents=True)
    (shell_package / "__init__.py").write_text(
        "from polisyos.fabric._legacy_helper import LegacyHelper\n",
        encoding="utf-8",
    )
    smoke_test = tmp_path / "tests" / "unit" / "fabric" / "test_smoke.py"
    smoke_test.parent.mkdir(parents=True)
    smoke_test.write_text("def test_smoke() -> None:\n    pass\n", encoding="utf-8")
    _write_minimal_package_import_gates(
        tmp_path,
        extra_lines=[
            "",
            "[[single_file_shell_package_exception]]",
            'path = "src/polisyos/fabric/legacy_helper"',
            'owner = "team-fabric"',
            'rationale = "Legacy facade is waiting for Wave 3 consolidation."',
            'sunset = "2026-07-31"',
            'migration_target = "polisyos.fabric.grouped.legacy_helper"',
            'smoke_import_test = "tests/unit/fabric/test_smoke.py::test_smoke"',
        ],
    )

    findings = check_package_import_gates._check_single_file_shell_packages(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "single-file-shell-package",
            "src/polisyos/fabric/legacy_helper",
            "single-file shell package exception smoke_import_test must reference "
            "the excepted package",
            "expected=polisyos.fabric.legacy_helper "
            "nodeid=tests/unit/fabric/test_smoke.py::test_smoke",
        )
    ]


def test_phase0_2_single_file_shell_package_dated_exception_is_allowed(
    tmp_path: Path,
) -> None:
    shell_package = tmp_path / "src" / "polisyos" / "fabric" / "legacy_helper"
    shell_package.mkdir(parents=True)
    (shell_package / "__init__.py").write_text(
        "from polisyos.fabric.legacy_helper_impl import LegacyHelper\n",
        encoding="utf-8",
    )
    _write_minimal_package_layout(
        tmp_path,
        extra_lines=[
            "",
            "[single_file_shell_package_policy]",
            'status = "fail_closed"',
            'scope_roots = ["src/polisyos/fabric"]',
            "max_python_files = 1",
            'allowed_facade_packages = []',
            "",
            "[[single_file_shell_package_exception]]",
            'path = "src/polisyos/fabric/legacy_helper"',
            'owner = "team-fabric"',
            'sunset = "2026-07-31"',
            'reason = "Legacy facade is waiting for Wave 3 consolidation."',
        ],
    )

    assert check_package_import_gates._check_single_file_shell_packages(tmp_path) == []


def test_phase0_2_ir_refs_and_references_collision_without_resolution_fails(
    tmp_path: Path,
) -> None:
    for name in ("refs", "references"):
        root = tmp_path / "src" / "polisyos" / "ir" / name
        root.mkdir(parents=True)
        (root / "__init__.py").write_text("", encoding="utf-8")
    package_contract = tmp_path / "architecture" / "packages"
    package_contract.mkdir(parents=True)
    (package_contract / "ir.toml").write_text(
        "\n".join(
            (
                "[name_collisions]",
                'status = "declared"',
                'owner = "team-ir"',
                'allowed = []',
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_package_import_gates._check_ir_refs_references_collision(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "name-collision",
            "src/polisyos/ir/{refs,references}",
            "IR contains both refs/ and references/ without a dated collision resolution",
        )
    ]


def test_phase7_module_size_ratchet_rejects_growth(tmp_path: Path) -> None:
    module = tmp_path / "src" / "polisyos" / "demo" / "large.py"
    module.parent.mkdir(parents=True)
    module.write_text("a = 1\nb = 2\n", encoding="utf-8")
    architecture = tmp_path / "architecture"
    architecture.mkdir()
    (architecture / "module_size_budget.toml").write_text(
        "\n".join(
            (
                "[module_size_budget]",
                "default_warning_lines = 1000",
                "",
                "[[budget]]",
                'path = "src/polisyos/demo/large.py"',
                "current_lines = 1",
                "report_only_limit_lines = 3",
            )
        )
        + "\n",
        encoding="utf-8",
    )

    findings = check_package_import_gates._check_module_size_ratchet(tmp_path)

    assert findings == [
        check_package_import_gates.Finding(
            "module-size-ratchet",
            "src/polisyos/demo/large.py",
            "module grew above its ratcheted current_lines budget",
            "current=2 budget=1",
        )
    ]


def test_phase6_7_validation_tooling_budgets_are_declared() -> None:
    contract = tomllib.loads(
        (REPO_ROOT / "architecture" / "module_size_budget.toml").read_text()
    )
    validation_defaults = contract["validation_tooling_size_budget"]
    budgets = {budget["path"]: budget for budget in contract["budget"]}

    assert validation_defaults["scope"] == ["tools/quality/validation/**/*.py"]
    assert validation_defaults["warning_lines"] == 1000
    assert validation_defaults["fail_closed_lines"] == 2000
    assert PHASE6_7_VALIDATION_BUDGET_PATHS <= set(budgets)
    for path in PHASE6_7_VALIDATION_BUDGET_PATHS:
        budget = budgets[path]
        assert budget["warning_lines"] == 1000, path
        assert budget["fail_closed_lines"] == 2000, path
        if budget["baseline_lines"] > validation_defaults["warning_lines"]:
            assert budget["current_lines"] == budget["baseline_lines"], path
            assert budget["report_only_limit_lines"] == budget["baseline_lines"], path
            assert budget["owner"].startswith("team-"), path
            assert budget["target_date"] >= "2026-05-08", path
            assert budget["extraction_sequence"], path


def test_phase6_7_unbudgeted_large_validation_script_is_contract_error(
    tmp_path: Path,
) -> None:
    validator = tmp_path / "tools" / "quality" / "validation" / "rogue_validator.py"
    validator.parent.mkdir(parents=True)
    validator.write_text("VALUE = 1\n" * 1001, encoding="utf-8")
    _write_minimal_module_size_budget(tmp_path)

    findings = contracts._validate_module_size_budget(tmp_path)

    assert (
        contracts.Finding(
            "module-size",
            "error",
            "tools/quality/validation/rogue_validator.py",
            "validation tooling above warning threshold lacks a module-size budget",
            "logical_lines=1001 warning=1000",
        )
        in findings
    )


def test_phase6_7_large_validation_budget_requires_extraction_target_date(
    tmp_path: Path,
) -> None:
    validator = tmp_path / "tools" / "quality" / "validation" / "large_validator.py"
    validator.parent.mkdir(parents=True)
    validator.write_text("VALUE = 1\n" * 1001, encoding="utf-8")
    _write_minimal_module_size_budget(
        tmp_path,
        extra_lines=[
            "",
            "[[budget]]",
            'path = "tools/quality/validation/large_validator.py"',
            'owner = "team-devx"',
            "baseline_lines = 1001",
            "current_lines = 1001",
            "warning_lines = 1000",
            "fail_closed_lines = 2000",
            "report_only_limit_lines = 1001",
            "target_lines = 1000",
            'shrink_plan = "Split this validator before extending it."',
            'extraction_sequence = ["contracts", "reporting"]',
            'risk_notes = "Validation behavior must remain stable."',
        ],
    )

    findings = contracts._validate_module_size_budget(tmp_path)

    assert (
        contracts.Finding(
            "module-size",
            "error",
            "tools/quality/validation/large_validator.py",
            "validation tooling above warning threshold must declare extraction target date",
        )
        in findings
    )


def test_phase6_7_module_size_ratchet_counts_logical_code_lines(tmp_path: Path) -> None:
    module = tmp_path / "src" / "polisyos" / "demo" / "logical.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "\n".join(
            (
                "# generated comment",
                "",
                "a = 1",
                "    # indented comment",
                "b = 2",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    _write_minimal_module_size_budget(
        tmp_path,
        extra_lines=[
            "",
            "[[budget]]",
            'path = "src/polisyos/demo/logical.py"',
            "current_lines = 2",
            "report_only_limit_lines = 2",
        ],
    )

    findings = check_package_import_gates._check_module_size_ratchet(tmp_path)

    assert findings == []


def test_phase6_1_public_surface_and_package_boundary_dependencies_agree() -> None:
    public_surface = tomllib.loads((REPO_ROOT / "architecture" / "public_surface" / "contract.toml").read_text())
    packages = {
        package["module"]: set(package.get("supported_entrypoints", [])) | {package["module"]}
        for package in public_surface["package"]
    }
    package_modules = sorted(packages, key=len, reverse=True)
    boundaries = tomllib.loads(
        (REPO_ROOT / "architecture" / "packages" / "boundaries.toml").read_text()
    )

    for package in boundaries["package"]:
        assert package["public_facade"] in packages[package["module"]], package["module"]
        for field in ("allowed_dependencies", "runtime_allowed_submodules"):
            for dependency in package.get(field, []):
                if dependency == "public_facades_only" or not dependency.startswith("polisyos."):
                    continue
                target_package = _package_for_module(dependency, package_modules)
                assert target_package is not None, dependency
                assert dependency in packages[target_package], (
                    package["module"],
                    field,
                    dependency,
                )


def test_phase6_1_reexport_shims_count_toward_shim_debt() -> None:
    payload = contracts.build_report(REPO_ROOT, report="dependency-graph")
    shim_debt = payload["summary"]["shim_debt"]

    assert shim_debt["shim_count"] >= shim_debt["python_reexport_count"] > 0
    assert shim_debt["by_type"]["python_reexport"] == shim_debt["python_reexport_count"]
    assert "foundry" in shim_debt["by_source_package"]


def test_phase6_1_enforcement_promotes_unregistered_hidden_growth_to_error() -> None:
    summary = {
        "package_level_deltas": [
            {
                "source_package": "polisyos.scientist",
                "target_package": "polisyos.foundry",
                "unregistered_added_hidden_edges": 1,
                "added_edge_keys": [
                    "polisyos.scientist.node->polisyos.foundry.methods._internal"
                ],
            }
        ]
    }

    errors = contracts._import_boundary_delta_errors(summary)

    assert len(errors) == 1
    assert errors[0].check == "import-boundary"
    assert errors[0].severity == "error"


def test_phase6_1_enforcement_promotes_unregistered_forbidden_edges_to_error() -> None:
    summary = {
        "package_level_forbidden_edges": [
            {
                "source_package": "polisyos.foundry",
                "target_package": "polisyos.scientist",
                "unregistered_forbidden_edges": 1,
                "edge_keys": ["polisyos.foundry.node->polisyos.scientist.private"],
            }
        ]
    }

    errors = contracts._package_boundary_forbidden_errors(summary)

    assert len(errors) == 1
    assert errors[0].check == "package-boundary"
    assert errors[0].severity == "error"


def _package_for_module(module: str, package_modules: list[str]) -> str | None:
    for package_module in package_modules:
        if module == package_module or module.startswith(f"{package_module}."):
            return package_module
    return None


def _write_minimal_directory_contracts(
    repo_root: Path, *, contracts: list[dict[str, object]]
) -> None:
    architecture = repo_root / "architecture"
    (architecture / "policies").mkdir(parents=True)
    rendered = ["[directory_contracts]", 'owner = "team-architecture"', ""]
    for contract in contracts:
        rendered.append("[[contract]]")
        for key, value in contract.items():
            rendered.append(f"{key} = {value!r}")
        rendered.append("")
    (architecture / "policies" / "directory_contracts.toml").write_text(
        "\n".join(rendered), encoding="utf-8"
    )


def _write_minimal_package_layout(
    repo_root: Path,
    *,
    extra_lines: list[str] | None = None,
) -> None:
    architecture = repo_root / "architecture"
    architecture.mkdir(exist_ok=True)
    lines = [
        "[package_layout]",
        'status = "fail_closed"',
        "",
        "[defaults]",
        'allowed_root_py_files = ["__init__.py", "api.py", "_api.py"]',
    ]
    if extra_lines:
        lines.extend(extra_lines)
    (architecture / "packages").mkdir(exist_ok=True)
    (architecture / "packages" / "layout.toml").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_minimal_module_size_budget(
    repo_root: Path,
    *,
    extra_lines: list[str] | None = None,
) -> None:
    architecture = repo_root / "architecture"
    architecture.mkdir(exist_ok=True)
    lines = [
        "[module_size_budget]",
        "default_warning_lines = 1000",
        "default_fail_closed_target_lines = 2500",
        "",
        "[validation_tooling_size_budget]",
        'scope = ["tools/quality/validation/**/*.py"]',
        "warning_lines = 1000",
        "fail_closed_lines = 2000",
        "require_budget_above_lines = 1000",
        'owner = "team-devx"',
    ]
    if extra_lines:
        lines.extend(extra_lines)
    (architecture / "module_size_budget.toml").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def _write_minimal_package_import_gates(
    repo_root: Path,
    *,
    extra_lines: list[str] | None = None,
) -> None:
    architecture = repo_root / "architecture"
    architecture.mkdir(exist_ok=True)
    lines = [
        "[package_import_gates]",
        'status = "fail_closed"',
        "",
        "[single_file_shell_package_policy]",
        'status = "fail_closed"',
        'scope_roots = ["src/polisyos/fabric"]',
        "max_python_files = 1",
        'allowed_facade_packages = []',
        'latest_allowed_sunset = "2026-07-31"',
        'exception_required_fields = ["path", "owner", "rationale", "sunset", "migration_target", "smoke_import_test"]',
    ]
    if extra_lines:
        lines.extend(extra_lines)
    (architecture / "gates").mkdir(exist_ok=True)
    (architecture / "gates" / "package_import.toml").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )
