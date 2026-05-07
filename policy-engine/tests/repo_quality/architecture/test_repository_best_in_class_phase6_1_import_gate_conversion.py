from __future__ import annotations

import tomllib
import importlib.util
from pathlib import Path

from tools.quality.validation import architecture_report_only_contracts as contracts
from tools.quality.validation import check_package_import_gates

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
        (REPO_ROOT / "architecture" / "package_import_gates.toml").read_text()
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
    assert report["summary"]["module_size_ratchet"]["finding_count"] == 0


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
            "package root Python file is neither an allowed facade, registered shim, nor dated root-file exception",
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
            "Scientist first-level root is not canonical, registered compatibility debt, or explicitly ignored",
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


def test_phase6_1_public_surface_and_package_boundary_dependencies_agree() -> None:
    public_surface = tomllib.loads((REPO_ROOT / "architecture" / "public_surface.toml").read_text())
    packages = {
        package["module"]: set(package.get("supported_entrypoints", [])) | {package["module"]}
        for package in public_surface["package"]
    }
    package_modules = sorted(packages, key=len, reverse=True)
    boundaries = tomllib.loads(
        (REPO_ROOT / "architecture" / "package_boundaries.toml").read_text()
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
    architecture.mkdir()
    rendered = ["[directory_contracts]", 'owner = "team-architecture"', ""]
    for contract in contracts:
        rendered.append("[[contract]]")
        for key, value in contract.items():
            rendered.append(f"{key} = {value!r}")
        rendered.append("")
    (architecture / "directory_contracts.toml").write_text(
        "\n".join(rendered), encoding="utf-8"
    )


def _write_minimal_package_layout(repo_root: Path) -> None:
    architecture = repo_root / "architecture"
    architecture.mkdir(exist_ok=True)
    (architecture / "package_layout.toml").write_text(
        "\n".join(
            (
                "[package_layout]",
                'status = "fail_closed"',
                "",
                "[defaults]",
                'allowed_root_py_files = ["__init__.py", "api.py", "_api.py"]',
            )
        )
        + "\n",
        encoding="utf-8",
    )
