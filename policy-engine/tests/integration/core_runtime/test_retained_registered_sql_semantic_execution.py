"""Execute and cold-read a retained candidate SQL/semantic binding in two processes.

These opt-in targets consume the actual handoff emitted by
``test_registered_sql_semantic_bindings``. They never query SQL, renew source
permission, or create an epoch. Source meaning/release/scope remain asserted;
historical transport does not establish current C105 permission or publication.
Run the execution target once, then the reader target in a fresh process.
"""

from __future__ import annotations

import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    artifact_ref_identity_key,
    load_core_json_artifact,
)
from polisyos.core.contracts import (
    REGISTERED_SQL_MEASUREMENT_LIMITATIONS,
    ExecuteRequest,
    FoundryExecConfig,
    FoundryInputBindingsRef,
    SimulationResultRef,
    load_model_input_obligation_set,
    load_resolved_input_binding_manifest,
)
from polisyos.core.security import tenant_scope
from polisyos.foundry.data_plane.bindings import (
    load_input_bindings,
    reconcile_semantic_input_bindings,
)
from polisyos.foundry.execute import load_state_snapshot
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.runtime.http.resilience import guard_runtime_cas

_INPUT_ENV = "POLISYOS_TEST_RETAINED_SQL_BINDING"
_OUTPUT_ENV = "POLISYOS_TEST_RETAINED_SQL_EXECUTION"
_TENANT_ENV = "POLISYOS_TEST_RETAINED_SQL_TENANT"
_CELL_ENV = "POLISYOS_TEST_RETAINED_SQL_CELL"


def _selection() -> tuple[Path, FoundryInputBindingsRef, Path, str, str]:
    """Read caller-selected locators; the canonical owners verify their artifacts."""
    source = os.environ.get(_INPUT_ENV)
    output = os.environ.get(_OUTPUT_ENV)
    if source is None or output is None:
        pytest.skip("requires an explicit test-owned retained SQL binding and output path")
    tenant = os.environ[_TENANT_ENV]
    cell = os.environ[_CELL_ENV]
    handoff = json.loads(Path(source).read_text())
    assert set(handoff) == {"cas_root", "input_bindings_ref"}
    cas_root = Path(handoff["cas_root"]).resolve(strict=True)
    ref = FoundryInputBindingsRef.model_validate(handoff["input_bindings_ref"])
    assert ref.manifest_profile_sha256 is not None
    return cas_root, ref, Path(output), tenant, cell


def _immutable_source_hashes(cas_root: Path) -> dict[str, str]:
    """Pin every original blob and selected manifest/signature, not mutable views."""
    selected = {}
    for path in (cas_root / "artifacts" / "sha256").rglob("*"):
        if path.is_file() and (
            path.name.endswith(".blob")
            or (".view." in path.name and path.name.endswith((".manifest.json", ".sig")))
        ):
            selected[str(path.relative_to(cas_root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    assert selected
    return selected


def _assert_original_sources(cas_root: Path, original: dict[str, str]) -> None:
    for name, digest in original.items():
        assert hashlib.sha256((cas_root / name).read_bytes()).hexdigest() == digest, name


def _save(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


@pytest.mark.integration
def test_retained_registered_sql_semantic_input_executes_once() -> None:
    """Run one real subsidy from existing captured inputs with the default CAS guard."""
    cas_root, input_ref, output, tenant, cell = _selection()
    assert not output.exists(), "execution already recorded; run the read-only target instead"
    assert "POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS" not in os.environ
    original = _immutable_source_hashes(cas_root)
    source_sql = cas_root.parent / "policy.sqlite"
    sql_hash = hashlib.sha256(source_sql.read_bytes()).hexdigest()
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        store = guard_runtime_cas(FileSystemCAS(cas_root, tenant_id=tenant, cell_id=cell))
        try:
            bindings = load_input_bindings(store, input_ref)
            assert bindings.schema_version == "1.3"
            assert bindings.registered_sql_admission_ref is not None
            assert bindings.resolved_binding_manifest_ref is not None
            limits = reconcile_semantic_input_bindings(store, bindings)
            assert {
                "semantic_input_limitation:" + code
                for code in REGISTERED_SQL_MEASUREMENT_LIMITATIONS
            }.issubset(limits)
            manifest = load_resolved_input_binding_manifest(
                store, bindings.resolved_binding_manifest_ref
            )
            obligation_set, _ = load_model_input_obligation_set(
                store, manifest.model_input_obligation_set_ref
            )
            invocation = obligation_set.invocation
            assert invocation.steps == (0,)
            graph = load_core_json_artifact(store, invocation.program_graph_ref)
            applies = [
                node
                for node in graph["nodes"]
                if node.get("op", {}).get("op_kind") == "apply_mechanism"
            ]
            assert len(applies) == 1
            (apply,) = applies
            assert apply["mechanism_type"] == "tax_subsidy"
            payload = load_core_json_artifact(
                store, ArtifactRef.model_validate(apply["params_ref"])
            )
            assert Fraction(payload["params"]["rate"]) == Fraction(1, 8)
            assert payload["schedule"] == {"start_step": 0, "duration_steps": 1, "end_step": None}
            assert payload["selector"] == {
                "kind": "predicate",
                "field": "id",
                "operator": "==",
                "value": "all",
            }
            opening = load_state_snapshot(store, snapshot_ref=bindings.bound_state_snapshot_ref)
            np.testing.assert_array_equal(np.asarray(opening.agents.income), [11, 20])
            np.testing.assert_array_equal(np.asarray(opening.agents.active), [True, True])
            assert float(opening.government_balance) == 11
            request = ExecuteRequest(
                exec_plan_ref=invocation.exec_plan_ref,
                input_bindings_ref=input_ref,
                registry_bundle_ref=bindings.registry_bundle_ref,
                exec_config=FoundryExecConfig(seed=41, mode="dev", capture_env=True),
                return_selected_profile=True,
            )
            report: dict[str, object] = {
                "cas_root": str(cas_root),
                "input_bindings_ref": input_ref.model_dump(mode="json"),
                "request": request.model_dump(mode="json"),
                "scope": "candidate_only_current_C105_permission_not_established",
                "stage": "one_public_execute_attempt",
            }
            _save(output, report)
            response = execute_foundry(store, request)
            report["response"] = response.model_dump(mode="json")
            report["stage"] = "public_execute_returned"
            _save(output, report)
            assert response.ok, response.notes
            assert response.simulation_result_ref is not None
        finally:
            store.close()
    _assert_original_sources(cas_root, original)
    assert hashlib.sha256(source_sql.read_bytes()).hexdigest() == sql_hash


@pytest.mark.integration
def test_retained_registered_sql_semantic_result_reopens_read_only() -> None:
    """Use a fresh process and canonical admission to read the real candidate result."""
    cas_root, input_ref, output, tenant, cell = _selection()
    report = json.loads(output.read_text())
    assert report["stage"] == "public_execute_returned"
    assert report["response"]["ok"] is True
    result_ref = SimulationResultRef.model_validate(report["response"]["simulation_result_ref"])
    original = _immutable_source_hashes(cas_root)
    with tenant_scope(None, tenant_id=tenant, cell_id=cell):
        reader = FileSystemCAS.open_existing_read_only(cas_root)
        assert not hasattr(reader, "put_json")
        admitted = admit_execution_source(reader, result_ref)
        assert admitted.mode == "single_step_basis"
        assert admitted.basis is not None
        assert artifact_ref_identity_key(admitted.basis.input_bindings_ref) == (
            artifact_ref_identity_key(input_ref)
        )
        bindings = load_input_bindings(reader, input_ref)
        assert bindings.schema_version == "1.3"
        assert bindings.registered_sql_admission_ref is not None
        assert admitted.basis.registered_sql_admission_ref is not None
        assert artifact_ref_identity_key(admitted.basis.registered_sql_admission_ref) == (
            artifact_ref_identity_key(bindings.registered_sql_admission_ref)
        )
        assert admitted.basis.request.exec_config.seed == 41
        assert set(REGISTERED_SQL_MEASUREMENT_LIMITATIONS).issubset(
            admitted.semantic_input_limitation_codes or ()
        )
        snapshot_ref = admitted.simulation_result.state_snapshot_ref
        assert snapshot_ref is not None
        state = load_state_snapshot(reader, snapshot_ref=snapshot_ref)
        rate = Fraction(1, 8)
        incomes = (Fraction(11), Fraction(20))
        expected_income = tuple(float(value * (1 + rate)) for value in incomes)
        expected_balance = Fraction(11) - sum(incomes) * rate
        np.testing.assert_array_equal(np.asarray(state.agents.income), expected_income)
        assert float(state.government_balance) == float(expected_balance) == 7.125
    _assert_original_sources(cas_root, original)
