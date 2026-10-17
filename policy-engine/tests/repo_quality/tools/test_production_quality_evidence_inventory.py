from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from polisyos.runtime.quality.capability_index_compiler import (
    CapabilityIndexCompilerConfig,
    compile_capability_index,
    create_capability_index_fixture_inputs,
)
from tools.quality.validation import production_quality_evidence_inventory as inventory

REPO_ROOT = inventory.REPO_ROOT


def _inventory() -> dict[str, object]:
    return inventory.build_inventory(REPO_ROOT)


def test_inventory_covers_phase01_acceptance_surfaces() -> None:
    payload = _inventory()

    assert payload["schema_version"] == inventory.SCHEMA_VERSION
    assert payload["phase"] == "0.1"
    assert payload["mode"] == "read_only_inventory"
    assert payload["status_model"]["allowed_statuses"] == list(inventory.STATUS_VALUES)

    reports = {str(row["id"]): row for row in payload["quality_reports"]}
    assert set(reports) >= {
        "lex.normative_evidence",
        "fabric.retrieval_trace",
        "foundry.method_report",
        "scientist.policy_grounding_matrix",
        "runtime.semantic_binding_ledger",
        "lex.policy_conflict_check",
        "runtime.performance_summary",
        "ir.metric_taxonomy",
        "llm.provider_preflight",
        "fabric.production_data_context",
        "core.cas_ownership_evidence",
    }

    for report in reports.values():
        assert report["status"] in inventory.STATUS_VALUES
        assert report["expected_ref"]
        assert report["owner_runtime_layer"]
        assert report["producer"]["name"]
        assert report["artifact_fields"]
        assert report["validators"]


def test_inventory_names_first_missing_producer_for_required_serious_refs() -> None:
    payload = _inventory()

    required_refs = {
        str(row["expected_ref"]): row for row in payload["serious_profile_required_refs"]
    }
    assert set(required_refs) >= {
        "provider_preflight.json",
        "performance.json",
        "production_data_evidence.json",
        "runtime_quality_ref#normative_applicability_report_ref",
        "runtime_quality_ref#fabric_retrieval_trace_ref",
        "runtime_quality_ref#foundry_method_report_ref",
        "runtime_quality_ref#policy_grounding_matrix_ref",
        "runtime_quality_ref#semantic_binding_ledger_ref",
        "runtime_quality_ref#conflict_check_ref",
        "runtime_quality_ref#provider_model_quality_ledger_ref",
        "quality_evidence/normative_evidence.json",
        "quality_evidence/fabric_retrieval_trace.json",
        "quality_evidence/foundry_method_report.json",
        "quality_evidence/policy_grounding_matrix.json",
        "quality_evidence/semantic_binding_ledger.json",
        "quality_evidence/conflict_check.json",
        "quality_evidence/provider_model_quality_ledger.json",
        "artifacts.json#data_snapshot_ref",
        "artifacts.json#input_bindings_ref",
        "artifacts.json#registry_bundle_ref",
        "artifacts.json#quality_report_ref",
        "artifacts.json#production_data_quality_report_ref",
        "bundle.json#metric_taxonomy",
        "cas_manifest#producer",
    }

    assert payload["summary"]["missing_or_input_required_producers"] == []
    for row in required_refs.values():
        assert "first_missing_producer" in row
        assert row["status"] == "runtime_emitted"
        assert row["first_missing_producer"] is None

    runtime_refs = {
        "runtime_quality_ref#normative_applicability_report_ref",
        "runtime_quality_ref#fabric_retrieval_trace_ref",
        "runtime_quality_ref#foundry_method_report_ref",
        "runtime_quality_ref#policy_grounding_matrix_ref",
        "runtime_quality_ref#semantic_binding_ledger_ref",
        "runtime_quality_ref#conflict_check_ref",
        "runtime_quality_ref#provider_model_quality_ledger_ref",
        "cas_manifest#producer",
    }
    for expected_ref in runtime_refs:
        row = required_refs[expected_ref]
        assert row["status"] == "runtime_emitted"
        assert row["producer"]


def test_inventory_maps_validators_to_runtime_layers_and_expected_refs() -> None:
    payload = _inventory()

    validators = {str(row["id"]): row for row in payload["validators"]}
    expected_layers = {
        "polisyos.lex.normpack.applicability_report.normalize_normative_applicability_report": (
            "lex",
            "quality_evidence/normative_evidence.json",
        ),
        "polisyos.fabric.catalog.source_selection_audit.normalize_fabric_retrieval_trace": (
            "fabric_retrieval",
            "quality_evidence/fabric_retrieval_trace.json",
        ),
        "polisyos.foundry.validation.method_quality.normalize_foundry_method_report": (
            "foundry_methods",
            "quality_evidence/foundry_method_report.json",
        ),
        "polisyos.scientist.validation.policy_grounding.normalize_policy_grounding_matrix": (
            "scientist_policy_artifacts",
            "quality_evidence/policy_grounding_matrix.json",
        ),
        "polisyos.runtime.quality.semantic_binding.evaluate_semantic_binding_ledger": (
            "semantic_binding",
            "quality_evidence/semantic_binding_ledger.json",
        ),
        "polisyos.lex.normpack.conflict_check.normalize_policy_conflict_check_report": (
            "normative_conflict",
            "quality_evidence/conflict_check.json",
        ),
        "polisyos.runtime.quality.scorecard.build_quality_scorecard": (
            "runtime_quality_scorecard",
            "quality_evidence/quality_scorecard.json",
        ),
    }

    for validator_id, (owner_layer, expected_ref) in expected_layers.items():
        assert validators[validator_id]["owner_runtime_layer"] == owner_layer
        assert validators[validator_id]["expected_ref"] == expected_ref

    fields = {str(row["field_path"]): row for row in payload["quality_artifact_fields"]}
    for field_path in (
        "QualityRef.status",
        "QualityRef.report_ref",
        "quality_scorecard.evidence_refs",
        "runtime.semantic_binding_ledger.semantic_binding_ref",
        "production_data_evidence.materialization_refs.quality_report_ref",
        "cas_manifest.producer",
    ):
        assert field_path in fields
        assert fields[field_path]["expected_ref"]


def test_dump_json_is_stable_and_checked_in_baseline_is_current() -> None:
    payload = _inventory()
    dumped = inventory.dump_json(payload)

    round_tripped = json.loads(dumped)
    assert round_tripped["schema_version"] == inventory.SCHEMA_VERSION
    assert round_tripped == payload
    assert "generated_at" not in dumped

    baseline = (
        REPO_ROOT / "architecture" / "baselines" / "production_quality" / "evidence_inventory.json"
    )
    assert baseline.read_text(encoding="utf-8") == dumped
    assert inventory.check_artifacts(repo_root=REPO_ROOT) == []


def test_cli_writes_json_output(tmp_path: Path) -> None:
    output = tmp_path / "evidence_inventory.json"

    assert inventory.main(["--json-output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == _inventory()


def test_cli_writes_capability_white_space_report_from_capability_index(
    tmp_path: Path,
) -> None:
    input_root = create_capability_index_fixture_inputs(tmp_path / "production_data")
    result = compile_capability_index(
        CapabilityIndexCompilerConfig(
            production_data_root=input_root,
            output_dir=tmp_path / "capability-index",
            mode="fixture",
            generated_at="2026-05-25T00:00:00Z",
        )
    )
    output = tmp_path / "capability-white-space-after-phase6.json"

    assert (
        inventory.main(
            [
                "--capability-index",
                str(result.primary_duckdb_path),
                "--output",
                str(output),
            ]
        )
        == 0
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "policyos.capability_white_space_report.v1"
    assert payload["validation"]["status"] == "pass"
    assert payload["groupings"]["by_construct"]["credit_program_enrollment"]["count"] >= 1


def _literal_requests_from_tool_source() -> set[str]:
    tree = ast.parse(Path(inventory.__file__).read_text(encoding="utf-8"))
    return {
        node.args[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_literal_assignment"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and isinstance(node.args[1].value, str)
    }


def test_inventory_constants_follow_the_complete_scorecard_source_bindings() -> None:
    requested = _literal_requests_from_tool_source()
    assert requested == {
        "QUALITY_REPORT_FILES",
        "QUALITY_REPORT_RUNTIME_REFS",
        "REQUIRED_MATERIALIZATION_REFS",
    }

    scorecard_path = inventory._SCORECARD_PATH
    resolved = {name: inventory._literal_assignment(scorecard_path, name) for name in requested}
    assert resolved["QUALITY_REPORT_FILES"] == inventory.QUALITY_REPORT_FILES
    assert resolved["QUALITY_REPORT_RUNTIME_REFS"] == inventory.QUALITY_REPORT_RUNTIME_REFS
    assert tuple(resolved["REQUIRED_MATERIALIZATION_REFS"]) == (
        inventory.REQUIRED_MATERIALIZATION_REFS
    )

    scorecard = ast.parse(scorecard_path.read_text(encoding="utf-8"))
    imports = {
        alias.asname or alias.name: node.module
        for node in scorecard.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert {name: imports[name] for name in requested if name in imports} == {
        "QUALITY_REPORT_FILES": "polisyos.runtime.quality.report_registry",
        "QUALITY_REPORT_RUNTIME_REFS": "polisyos.runtime.quality.report_registry",
    }


def _write_literal_fixture(root: Path, relative: str, text: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_literal_assignment_tracks_changed_import_owner_and_local_aliases(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    owner = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/report_registry.py",
        'REPORT_FILENAME = "canonical.json"\nREPORTS = {"quality": REPORT_FILENAME}\n',
    )
    alternate = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/alternate_registry.py",
        'REPORTS = {"quality": "alternate.json"}\n',
    )
    facade = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/scorecard.py",
        "from polisyos.runtime.quality.report_registry import REPORTS as QUALITY_REPORT_FILES\n",
    )

    assert inventory._literal_assignment(
        facade, "QUALITY_REPORT_FILES", source_root=source_root
    ) == {"quality": "canonical.json"}
    facade.write_text(
        "from polisyos.runtime.quality.alternate_registry import REPORTS as QUALITY_REPORT_FILES\n",
        encoding="utf-8",
    )
    assert inventory._literal_assignment(
        facade, "QUALITY_REPORT_FILES", source_root=source_root
    ) == {"quality": "alternate.json"}
    assert owner.is_file() and alternate.is_file()


def test_literal_assignment_rejects_dynamic_or_duplicate_owner_bindings(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    facade = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/scorecard.py",
        "from polisyos.runtime.quality.report_registry import REPORTS as QUALITY_REPORT_FILES\n",
    )
    owner = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/report_registry.py",
        "REPORTS = build_reports()\n",
    )
    with pytest.raises(ValueError, match=r"literal|malformed|unsupported"):
        inventory._literal_assignment(facade, "QUALITY_REPORT_FILES", source_root=source_root)

    owner.write_text(
        'REPORTS = {"quality": "first.json"}\nREPORTS = {"quality": "second.json"}\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="multiple top-level bindings"):
        inventory._literal_assignment(facade, "QUALITY_REPORT_FILES", source_root=source_root)


def test_literal_assignment_rejects_cycles_and_imports_outside_source_namespace(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    facade = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/scorecard.py",
        "from polisyos.runtime.quality.report_registry import REPORTS as QUALITY_REPORT_FILES\n",
    )
    _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/report_registry.py",
        "from polisyos.runtime.quality.scorecard import QUALITY_REPORT_FILES as REPORTS\n",
    )
    with pytest.raises(ValueError, match="cyclic literal binding"):
        inventory._literal_assignment(facade, "QUALITY_REPORT_FILES", source_root=source_root)

    facade.write_text(
        "from external.owner import REPORTS as QUALITY_REPORT_FILES\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="supported absolute polisyos import"):
        inventory._literal_assignment(facade, "QUALITY_REPORT_FILES", source_root=source_root)


def test_literal_assignment_fails_when_import_is_removed_but_markers_remain(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src"
    facade = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/scorecard.py",
        (
            "# from polisyos.runtime.quality.report_registry import REPORTS "
            "as QUALITY_REPORT_FILES\n"
            'MARKER = "QUALITY_REPORT_FILES"\n'
        ),
    )
    with pytest.raises(ValueError, match="no top-level binding"):
        inventory._literal_assignment(facade, "QUALITY_REPORT_FILES", source_root=source_root)


@pytest.mark.parametrize(
    "module_rebinding",
    [
        "def QUALITY_REPORT_FILES():\n    return {}\n",
        "class QUALITY_REPORT_FILES:\n    pass\n",
        'QUALITY_REPORT_FILES += {"changed": "later.json"}\n',
        'if enabled:\n    QUALITY_REPORT_FILES = {"changed": "conditional.json"}\n',
        "for QUALITY_REPORT_FILES in ():\n    pass\n",
        "with manager as QUALITY_REPORT_FILES:\n    pass\n",
        "try:\n    raise ValueError()\nexcept ValueError as QUALITY_REPORT_FILES:\n    pass\n",
        "match 1:\n    case QUALITY_REPORT_FILES:\n        pass\n",
        "del QUALITY_REPORT_FILES\n",
        'if (QUALITY_REPORT_FILES := {"changed": "walrus.json"}):\n    pass\n',
        (
            "if enabled:\n"
            "    from polisyos.runtime.quality.other_registry import REPORTS "
            "as QUALITY_REPORT_FILES\n"
        ),
        "from polisyos.runtime.quality.other_registry import *\n",
    ],
)
def test_literal_assignment_rejects_module_scope_rebindings(
    tmp_path: Path, module_rebinding: str
) -> None:
    source_root = tmp_path / "src"
    _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/report_registry.py",
        'REPORTS = {"quality": "canonical.json"}\n',
    )
    facade = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/scorecard.py",
        "from polisyos.runtime.quality.report_registry import REPORTS "
        "as QUALITY_REPORT_FILES\n" + module_rebinding,
    )

    with pytest.raises(ValueError, match=r"binding|star import"):
        inventory._literal_assignment(facade, "QUALITY_REPORT_FILES", source_root=source_root)


def test_literal_assignment_ignores_function_and_class_local_bindings(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    owner = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/report_registry.py",
        (
            'REPORTS = {"quality": "canonical.json"}\n'
            "def local_reports():\n"
            "    REPORTS = make_reports()\n"
            "    return REPORTS\n"
            "class LocalReports:\n"
            "    REPORTS = make_reports()\n"
        ),
    )

    assert inventory._literal_assignment(owner, "REPORTS", source_root=source_root) == {
        "quality": "canonical.json"
    }


def test_literal_assignment_rejects_a_conditional_only_module_binding(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    owner = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/report_registry.py",
        'if enabled:\n    REPORTS = {"quality": "conditional.json"}\n',
    )

    with pytest.raises(ValueError, match="direct module literal"):
        inventory._literal_assignment(owner, "REPORTS", source_root=source_root)


def test_literal_assignment_rejects_class_suite_global_rebinding(tmp_path: Path) -> None:
    source_root = tmp_path / "src"
    owner = _write_literal_fixture(
        source_root,
        "polisyos/runtime/quality/report_registry.py",
        (
            'REPORTS = {"quality": "canonical.json"}\n'
            "class GlobalReports:\n"
            "    global REPORTS\n"
            "    REPORTS = make_reports()\n"
        ),
    )

    with pytest.raises(ValueError, match="multiple top-level bindings"):
        inventory._literal_assignment(owner, "REPORTS", source_root=source_root)
