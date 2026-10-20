from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from polisyos.runtime.quality import confidence_ledger as ledger

_PRODUCT_ROOT = Path(__file__).resolve().parents[5]
_MODULE = "polisyos.foundry.methods.selection"
_REQUIREMENT_EXPORTS = frozenset({"select_method_candidates_for_requirements"})
_RECEIPT_EXPORTS = frozenset({"MethodSelectionAlternative", "MethodSelectionReceipt"})
_EXPECTED_EXPORTS = (
    "COST_PER_MS",
    "ActiveSetSummary",
    "AdvisorOptimizationResult",
    "AdvisorValuePolicy",
    "BudgetCertificate",
    "CalibratedRegretCertificate",
    "CandidateScore",
    "ConfidenceSequence",
    "CrossMethodConsensus",
    "DataCharacteristics",
    "MethodAdvisorQuery",
    "MethodAdvisorResult",
    "MethodLossProfile",
    "MethodScoreTraceEntry",
    "MethodSelectionAlternative",
    "MethodRouteConstraint",
    "InputContractMethodCandidate",
    "InputContractMethodSelection",
    "select_method_for_input_contract",
    "MethodSelectionReceipt",
    "MethodSelectionCriteria",
    "_score_entry",
    "_score_entry_v2",
    "advise_methods",
    "advise_methods_for_analyst",
    "attach_advisor_execution_context",
    "authoring_catalog_payload",
    "build_advisor_execution_context",
    "compute_voi",
    "method_selection_context_hash",
    "method_accepts_input_contract",
    "method_selection_payload",
    "pareto_advise_methods",
    "rank_method_catalog_entries",
    "reachable_value_method_fqns",
    "select_method_candidates_for_requirements",
    "select_value_method_for_problem",
    "suggest_adapter_methods",
    "suggest_alternative_methods",
    "suggest_plan_node_alternatives",
)


def _expected_provider_map() -> dict[str, str]:
    advisor_exports = set(_EXPECTED_EXPORTS) - _REQUIREMENT_EXPORTS - _RECEIPT_EXPORTS
    assert len(_EXPECTED_EXPORTS) == 40
    assert len(advisor_exports) == 37
    expected = dict.fromkeys(
        _REQUIREMENT_EXPORTS,
        "polisyos.foundry.methods.selection.requirements",
    )
    expected.update(dict.fromkeys(_RECEIPT_EXPORTS, "polisyos.foundry.methods.selection.receipt"))
    expected.update(dict.fromkeys(advisor_exports, "polisyos.foundry.methods.selection.advisor"))
    return expected


def _write_source_package(root: Path, initializer: str) -> Path:
    package = root / "src/polisyos/foundry/methods/selection"
    for parent in (
        root / "src/polisyos",
        root / "src/polisyos/foundry",
        root / "src/polisyos/foundry/methods",
        package,
    ):
        parent.mkdir(parents=True, exist_ok=True)
        (parent / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text(initializer, encoding="utf-8")
    return package


def _run_in_source_root(root: Path, probe: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.pathsep.join([str(root / "src"), os.environ.get("PYTHONPATH", "")]),
    }
    # Security rationale: execute a fixed test probe with the current interpreter.
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        cwd=root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )


def test_literal_owner_map_binds_the_complete_public_route_table() -> None:
    import ast

    source_path = _PRODUCT_ROOT / "src/polisyos/foundry/methods/selection/__init__.py"
    source = source_path.read_bytes()
    tree = ledger.ast.parse(source, filename=source_path.as_posix())
    provider_index = ledger._source_module_provider_index(
        _PRODUCT_ROOT,
        _MODULE,
        tree,
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )
    all_exports = next(
        ast.literal_eval(statement.value)
        for statement in tree.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in statement.targets
        )
    )
    owner_map = next(
        ast.literal_eval(statement.value)
        for statement in tree.body
        if isinstance(statement, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "_EXPORT_MODULES"
            for target in statement.targets
        )
    )

    assert type(all_exports) is list
    assert tuple(all_exports) == _EXPECTED_EXPORTS
    assert type(owner_map) is dict
    assert tuple(owner_map) == _EXPECTED_EXPORTS
    assert not provider_index.invalid_exports

    expected = _expected_provider_map()
    assert owner_map == expected
    observed: dict[str, tuple[str, str]] = {}
    for export in _EXPECTED_EXPORTS:
        providers = provider_index.providers_by_export[export]
        symbols = provider_index.provider_symbols_by_export[export]
        assert len(providers) == 1
        assert len(symbols) == 1
        observed[export] = (next(iter(providers)), next(iter(symbols)))
    assert observed == {export: (module_name, export) for export, module_name in expected.items()}
    assert len(observed) == 40

    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})
    for export, module_name in expected.items():
        assert ledger._source_module_import_route(
            _PRODUCT_ROOT,
            _MODULE,
            export,
            directory_entries={},
            source_index=source_index,
        ) == ("symbol", module_name, export)


def test_lazy_owner_routes_execute_requirement_receipt_and_advisor_consumers() -> None:
    probe = r"""
import hashlib
import json
import sys

import polisyos.foundry.methods.selection as selection

owner_modules = (
    "polisyos.foundry.methods.selection.requirements",
    "polisyos.foundry.methods.selection.receipt",
    "polisyos.foundry.methods.selection.advisor",
)
assert type(selection.__all__) is list
assert "select_method_candidates_for_requirements" in selection.__all__
assert set(selection.__all__).issubset(set(dir(selection)))
assert not any(module in sys.modules for module in owner_modules)

from polisyos.method_requirement import MethodValidityRequirementSpec

requirement = MethodValidityRequirementSpec(
    requirement_id="method-req-route-probe",
    run_id="run-route-probe",
    claim_id="claim-route-probe",
    identification_class="point",
    method_expectations=["causal_effect_estimation"],
    required_method_families=["causal_effect_estimation"],
    transportability_requirement="target_population_limits",
    uncertainty_class="interval",
    assumption_validation_needs=[
        {"assumption_id": "parallel_trends"},
        {"assumption_id": "overlap_or_support"},
    ],
    facet_refs=["facet_outcome"],
    obligation_refs=["obligation_method"],
)
select_requirements = selection.select_method_candidates_for_requirements
report = select_requirements(
    candidate_methods=[
        {
            "method_id": "causal.did.runtime",
            "method_family": "causal_effect_estimation",
            "method_expectations": ["causal_effect_estimation"],
            "truthfulness_status": "runtime_consistent",
            "runtime_assumption_gates": [
                {
                    "gate_ref": "gate://parallel-trends",
                    "assumption": "parallel_trends",
                    "status": "pass",
                },
                {
                    "gate_ref": "gate://overlap",
                    "assumption": "overlap_or_support",
                    "status": "pass",
                },
            ],
            "uncertainty_refs": {"uncertainty_envelope_ref": "sha256:" + "6" * 64},
            "limitation_refs": {"method_limitation_ref": "sha256:" + "5" * 64},
            "method_result_refs": {"method_result_ref": "sha256:" + "4" * 64},
        }
    ],
    method_requirements=[requirement],
)
assert report["status"] == "pass"
assert report["selected_methods"][0]["method_id"] == "causal.did.runtime"
assert selection.select_method_candidates_for_requirements is select_requirements
assert owner_modules[0] in sys.modules
assert owner_modules[1] not in sys.modules and owner_modules[2] not in sys.modules

alternative = selection.MethodSelectionAlternative(
    rank=1,
    method_fqn="fixture.method@1.0.0",
    method_family="fixture.family",
    selected=True,
)
payload = {
    "schema_version": "policyos.foundry.method_selection_receipt.v2",
    "selection_authority": "requested_registry_method",
    "selected_method_fqn": "fixture.method@1.0.0",
    "ranked_alternatives": [alternative.model_dump(mode="json")],
    "denominator": ["fixture.method@1.0.0"],
    "selection_context_hash": "sha256:" + "0" * 64,
}
payload["content_hash"] = "sha256:" + hashlib.sha256(
    json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
).hexdigest()
receipt_type = selection.MethodSelectionReceipt
receipt = receipt_type.model_validate(payload)
assert receipt.selected_method_fqn == "fixture.method@1.0.0"
assert owner_modules[1] in sys.modules and owner_modules[2] not in sys.modules
assert selection.MethodSelectionReceipt is receipt_type

from polisyos.core.contracts.execution_plan import MethodCatalogEntry, MethodCatalogSnapshot

catalog = MethodCatalogSnapshot(
    snapshot_id="selection-route-probe",
    entries=[
        MethodCatalogEntry(
            fqn="fixture.family.native@1.0.0",
            namespace="fixture.family",
            name="native",
            version="1.0.0",
            backend="numpy",
            execution_backend="numpy",
            kind="pure",
            family="fixture.family",
            variant="native",
            fidelity_tier="high",
            data_modalities=["cross-section"],
            runtime_stack=["numpy"],
            runnable=True,
            truthfulness_tier="exact",
            implementation_depth_tier="production_method",
        )
    ],
)
query = selection.MethodAdvisorQuery(
    criteria=selection.MethodSelectionCriteria(preferred_family="fixture.family"),
    limit=1,
)
advise_methods = selection.advise_methods
advisor_result = advise_methods(catalog, query)
assert advisor_result.recommended[0].fqn == "fixture.family.native@1.0.0"
assert isinstance(advisor_result, selection.MethodAdvisorResult)
assert owner_modules[2] in sys.modules
assert selection.advise_methods is advise_methods

try:
    selection.not_a_supported_selection_export
except AttributeError:
    pass
else:
    raise AssertionError("unknown selection export must preserve AttributeError")

print("foundry_selection_routes_exercised")
"""
    environment = {
        **os.environ,
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": os.pathsep.join(
            [str(_PRODUCT_ROOT / "src"), os.environ.get("PYTHONPATH", "")]
        ),
    }
    # Security rationale: execute a fixed import-and-consumer probe with the current interpreter.
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", probe],
        cwd=_PRODUCT_ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, f"{result.stderr}\n{result.stdout}"
    assert result.stdout.strip() == "foundry_selection_routes_exercised"


def test_drifted_route_target_is_rejected_even_with_a_sibling_export_module(
    tmp_path: Path,
) -> None:
    source_path = _PRODUCT_ROOT / "src/polisyos/foundry/methods/selection/__init__.py"
    source_text = source_path.read_text(encoding="utf-8")
    old_target = '"polisyos.foundry.methods.selection.requirements"'
    assert source_text.count(old_target) == 1
    drifted = source_text.replace(old_target, '"polisyos.missing.selection_requirements"', 1)
    fixture_root = tmp_path / "drifted-route"
    package = _write_source_package(fixture_root, drifted)
    (package / "select_method_candidates_for_requirements.py").write_text(
        "def select_method_candidates_for_requirements():\n    return {}\n",
        encoding="utf-8",
    )
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_module_import_route(
            fixture_root,
            _MODULE,
            "select_method_candidates_for_requirements",
            directory_entries={},
            source_index=source_index,
        )


def test_missing_owner_row_refuses_with_attribute_error_not_key_error(tmp_path: Path) -> None:
    source_path = _PRODUCT_ROOT / "src/polisyos/foundry/methods/selection/__init__.py"
    source_text = source_path.read_text(encoding="utf-8")
    missing_row = (
        '    "select_method_candidates_for_requirements": '
        '"polisyos.foundry.methods.selection.requirements",\n'
    )
    assert source_text.count(missing_row) == 1
    missing_route_source = source_text.replace(missing_row, "", 1)
    fixture_root = tmp_path / "missing-route"
    _write_source_package(fixture_root, missing_route_source)
    probe = r"""
import polisyos.foundry.methods.selection as selection
assert "select_method_candidates_for_requirements" in selection.__all__
try:
    selection.select_method_candidates_for_requirements
except AttributeError:
    print("missing_route_refused")
else:
    raise AssertionError("missing owner row must not fall back or raise KeyError")
"""
    result = _run_in_source_root(fixture_root, probe)

    assert result.returncode == 0, f"{result.stderr}\n{result.stdout}"
    assert result.stdout.strip() == "missing_route_refused"
