"""Compose selected annual method inputs with real horizon-step execution."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from contextlib import ExitStack
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, ClassVar

import numpy as np
import pytest

from polisyos.core.artifacts import input_ref_from_artifact_ref, validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.foundry import (
    ExecuteRequest,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    MethodExecutionBundle,
    SemanticHorizonStepContext,
    SimulationResultRef,
)
from polisyos.core.contracts.model_input_requirements import load_model_input_obligation_set
from polisyos.foundry.data_plane.bindings import (
    build_input_bindings,
    load_input_bindings,
    replay_selected_method_input_step_facts,
)
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.execute.api import execute_semantic_horizon_step
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import MethodSignature
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.quality.model_input_step_materialization import (
    prepare_registered_derived_model_input_steps,
)
from tests._helpers.temporal_registered_method_inputs import (
    TemporalRegisteredMethodInputs,
    prepare_temporal_registered_method_inputs,
)
from tests._helpers.temporal_selected_method_input import (
    TemporalMethodYearInput,
    constant_price_two_year_method_spec,
)


def _persist_step_rows(case, original_ref, bindings, rows):
    manifest = case.store.get_manifest(original_ref)
    payload = bindings.model_copy(update={"selected_method_input_steps": rows})
    inputs = [edge for edge in manifest.inputs if not edge.role.startswith("method_input.")]
    for row in rows:
        record = row.input
        inputs.extend(
            (
                input_ref_from_artifact_ref(
                    record.model_input_obligation_ref,
                    role=f"method_input.{record.binding_id}.obligation",
                ),
                input_ref_from_artifact_ref(
                    record.npy_value_ref, role=f"method_input.{record.binding_id}.value"
                ),
            )
        )
    ref = case.store.put_json(
        payload,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME, version="1.5"),
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    return FoundryInputBindingsRef.model_validate(ref.model_dump(mode="python"))


def _prepare_complete_input_bindings(fixture):
    case = fixture.case
    selected_set, _ = load_model_input_obligation_set(
        case.store, fixture.preflight.obligation_set_ref
    )
    invocation = selected_set.invocation
    stage = prepare_registered_derived_model_input_steps(
        case.store,
        base_data_snapshot_ref=case.data_snapshot_ref,
        obligation_set_ref=fixture.preflight.obligation_set_ref,
        inputs=fixture.requests,
    )
    bindings = build_input_bindings(
        case.store,
        data_snapshot_ref=stage.data_snapshot_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        resolved_binding_manifest_ref=stage.resolved_binding_manifest_ref,
        return_selected_profile=True,
    )
    facts = replay_selected_method_input_step_facts(
        case.store,
        input_bindings_ref=bindings.input_bindings_ref,
        expected_invocation=invocation,
    )
    return invocation, bindings, facts


def _loaded_main_origin_snapshot() -> dict[str, str | None]:
    """Capture the loaded PolicyOS module origins at the preflight boundary."""
    return {
        name: getattr(module, "__file__", None)
        for name, module in sorted(sys.modules.items())
        if name == "polisyos" or name.startswith("polisyos.")
    }


def _fresh_process_read_chain(case, result_refs):
    product_root = Path(__file__).resolve().parents[4]
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(product_root / "src")
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    code = """
import hashlib
import json
import sys
from decimal import Decimal
from io import BytesIO
import numpy as np
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.foundry import MethodExecutionBundle, SimulationResultRef
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute import api as execute_api
from polisyos.foundry.execute.executor import load_state_snapshot

store = FileSystemCAS(sys.argv[1])
refs = tuple(SimulationResultRef.model_validate(item) for item in json.loads(sys.argv[2]))
admissions = execute_api.admit_semantic_horizon_step_chain(store, refs)
expected_flows = (Decimal("-6000000000"), Decimal("4200000000"))
expected_stocks = (Decimal("4000000000"), Decimal("8200000000"))
assert len(admissions) == len(refs) == 2
rows = []
for index, (ref, admission) in enumerate(zip(refs, admissions, strict=True)):
    basis = admission.basis
    assert basis is not None and basis.semantic_horizon_step is not None
    step = basis.semantic_horizon_step
    assert step.steps == (0, 1) and step.step_index == index
    if index == 0:
        assert step.previous_result_ref is None
    else:
        assert step.previous_result_ref == refs[index - 1]
        assert basis.base_state_snapshot_ref == admissions[index - 1].simulation_result.state_snapshot_ref

    bindings = load_input_bindings(store, basis.input_bindings_ref)
    selected_rows = [item for item in bindings.selected_method_input_steps if item.step_scope.step == index]
    assert len(selected_rows) == 1
    selected = selected_rows[0].input
    assert Decimal(selected.canonical_value) == expected_flows[index]
    value = np.load(BytesIO(store.get_bytes(selected.npy_value_ref)), allow_pickle=False)
    assert value.shape == () and value.dtype == np.dtype(np.float64)
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii"))
    digest.update(value.tobytes(order="C"))
    value_sha256 = digest.hexdigest()
    assert value_sha256 == selected.value_sha256
    assert Decimal(str(value.item())) == expected_flows[index]

    edge = next(item for item in store.get_manifest(ref).inputs if item.role == "method_execution")
    bundle_ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        manifest_profile_sha256=edge.manifest_profile_sha256,
        kind=MethodExecutionBundle.ARTIFACT_KIND,
        media_type=MethodExecutionBundle.ARTIFACT_MEDIA_TYPE,
    )
    bundle = validate_core_model_json_artifact(MethodExecutionBundle, store, bundle_ref)
    occurrences = [item for item in bundle.occurrences if item.node_kind == "method"]
    assert len(occurrences) == 1
    occurrence = occurrences[0]
    assert occurrence.status == "succeeded" and occurrence.dispatch is not None
    arguments = [item for item in occurrence.dispatch.input_slot_values if item.slot_id == "period_flow"]
    assert len(arguments) == 1
    argument = arguments[0]
    assert argument.value_sha256 == selected.value_sha256 == value_sha256
    assert argument.runtime_shape == () and argument.runtime_dtype == np.dtype(np.float64).str

    state = load_state_snapshot(store, snapshot_ref=admission.simulation_result.state_snapshot_ref)
    stock = Decimal(str(float(state.government_balance)))
    assert stock == expected_stocks[index]
    rows.append({"step": index, "stock": str(stock), "value_sha256": value_sha256})

print(json.dumps(rows, sort_keys=True))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            code,
            str(case.store_root),
            json.dumps([ref.model_dump(mode="json") for ref in result_refs]),
        ],
        cwd=product_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


def test_selected_method_input_step_preconditions_refuse_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject swapped or incomplete rows before any physical graph dispatch."""
    fixture = prepare_temporal_registered_method_inputs(tmp_path)
    case = fixture.case
    try:
        invocation, full, facts = _prepare_complete_input_bindings(fixture)
        assert invocation.steps == (0, 1)
        assert facts.bindings.schema_version == "1.5"
        assert facts.coverage.is_complete
        assert "semantic_input_use:candidate_simulation_input_only" in facts.notes
        origins = _loaded_main_origin_snapshot()
        origins_path = tmp_path / "loaded-main-origin-snapshot.json"
        origins_path.write_text(json.dumps(origins, sort_keys=True) + "\n")
        print(f"LOADED_MAIN_ORIGIN_SNAPSHOT={origins_path} modules={len(origins)}")
        product_src = Path(__file__).resolve().parents[4] / "src"
        required_origins = (
            "polisyos.core.contracts.foundry",
            "polisyos.core.contracts.model_input_requirements",
            "polisyos.foundry.data_plane.bindings",
            "polisyos.foundry.execute.api",
            "polisyos.foundry.execute._internal.graph",
            "polisyos.runtime.quality.model_input_step_materialization",
        )
        assert all(name in origins for name in required_origins), origins
        assert all(
            origins[name] is not None and Path(origins[name]).resolve().is_relative_to(product_src)
            for name in required_origins
        ), origins

        original_rows = facts.records
        first, second = original_rows
        swapped_ref = _persist_step_rows(
            case,
            full.input_bindings_ref,
            facts.bindings,
            (
                first.model_copy(update={"input": second.input}),
                second.model_copy(update={"input": first.input}),
            ),
        )
        partial_stage = prepare_registered_derived_model_input_steps(
            case.store,
            base_data_snapshot_ref=case.data_snapshot_ref,
            obligation_set_ref=fixture.preflight.obligation_set_ref,
            inputs=fixture.requests[:1],
        )
        partial = build_input_bindings(
            case.store,
            data_snapshot_ref=partial_stage.data_snapshot_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            resolved_binding_manifest_ref=partial_stage.resolved_binding_manifest_ref,
            return_selected_profile=True,
        )

        def refuse_physical_dispatch(*_args, **_kwargs):
            raise AssertionError("invalid temporal bindings reached physical execution")

        def refuse_method_kernel(*_args, **_kwargs):
            raise AssertionError("preflight-only witness reached a method kernel")

        first_step = SemanticHorizonStepContext(
            obligation_set_ref=fixture.preflight.obligation_set_ref,
            steps=invocation.steps,
            step_index=0,
            replication_seed=17,
        )
        with monkeypatch.context() as guard:
            guard.setattr(execute_api, "execute_program_graph", refuse_physical_dispatch)
            guard.setattr(MethodDispatcher, "dispatch", refuse_method_kernel)
            guard.setattr(PeriodFlowToStock, "pure_step", staticmethod(refuse_method_kernel))
            with pytest.raises(
                ValueError, match="foundry_selected_method_input_record_source_mismatch"
            ):
                execute_semantic_horizon_step(
                    case.store,
                    ExecuteRequest(
                        exec_plan_ref=case.exec_plan_ref,
                        registry_bundle_ref=case.registry_bundle_ref,
                        input_bindings_ref=swapped_ref,
                        return_selected_profile=True,
                    ),
                    expected_invocation=invocation,
                    step=first_step,
                )
            with pytest.raises(ValueError, match="model_input_step_coverage_incomplete"):
                execute_semantic_horizon_step(
                    case.store,
                    ExecuteRequest(
                        exec_plan_ref=case.exec_plan_ref,
                        registry_bundle_ref=case.registry_bundle_ref,
                        input_bindings_ref=partial.input_bindings_ref,
                        return_selected_profile=True,
                    ),
                    expected_invocation=invocation,
                    step=first_step,
                )

    finally:
        close = getattr(case.store, "close", None)
        if callable(close):
            close()


def test_selected_method_inputs_execute_and_reopen_exact_two_step_chain(
    tmp_path: Path,
) -> None:
    """Execute and reopen declared synthetic 2020/2021 inputs through Foundry."""
    fixture = prepare_temporal_registered_method_inputs(tmp_path)
    case = fixture.case
    try:
        expected_flows = (Decimal("-6000000000"), Decimal("4200000000"))
        expected_stocks = (Decimal("4000000000"), Decimal("8200000000"))
        assert fixture.spec.opening_stock == Decimal("10000000000")
        assert tuple(row.expected_flow for row in fixture.spec.rows) == expected_flows
        assert fixture.spec.expected_closing_stock == expected_stocks[-1]

        invocation, full, facts = _prepare_complete_input_bindings(fixture)
        assert invocation.steps == (0, 1)
        assert facts.bindings.schema_version == "1.5"
        assert facts.coverage.is_complete
        assert "semantic_input_use:candidate_simulation_input_only" in facts.notes
        assert (
            tuple(
                Decimal(str(facts.values[("period_flow", row.step)].item()))
                for row in fixture.spec.rows
            )
            == expected_flows
        )

        opening = load_state_snapshot(
            case.store, snapshot_ref=facts.bindings.bound_state_snapshot_ref
        )
        assert Decimal(str(float(opening.government_balance))) == Decimal("10000000000")
        request = ExecuteRequest(
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=full.input_bindings_ref,
            return_selected_profile=True,
        )
        handoff_path = tmp_path / "temporal-step-cold-reader-handoff.json"
        result_refs = []
        step_records = []
        handoff = {
            "cas_root": str(case.store_root.resolve()),
            "expected_flows": [str(value) for value in expected_flows],
            "expected_stocks": [str(value) for value in expected_stocks],
            "input_bindings_ref": request.input_bindings_ref.model_dump(mode="json"),
            "obligation_set_ref": fixture.preflight.obligation_set_ref.model_dump(mode="json"),
            "request": request.model_dump(mode="json"),
            "schedule": list(invocation.steps),
            "steps": step_records,
        }

        def persist_handoff() -> None:
            handoff_path.write_text(json.dumps(handoff, sort_keys=True, indent=2) + "\n")

        persist_handoff()
        for index in range(2):
            result = execute_semantic_horizon_step(
                case.store,
                request,
                expected_invocation=invocation,
                step=SemanticHorizonStepContext(
                    obligation_set_ref=fixture.preflight.obligation_set_ref,
                    steps=invocation.steps,
                    step_index=index,
                    replication_seed=17,
                    previous_result_ref=None if index == 0 else result_refs[-1],
                ),
            )
            step_record = {
                "index": index,
                "method_execution_bundle_ref": (
                    None
                    if result.method_execution_bundle_ref is None
                    else result.method_execution_bundle_ref.model_dump(mode="json")
                ),
                "notes": list(result.notes),
                "ok": result.ok,
                "simulation_result_ref": (
                    None
                    if result.simulation_result_ref is None
                    else result.simulation_result_ref.model_dump(mode="json")
                ),
            }
            step_records.append(step_record)
            persist_handoff()
            assert result.ok and result.simulation_result_ref is not None
            assert result.method_execution_bundle_ref is not None
            result_refs.append(result.simulation_result_ref)

        print(f"TEMPORAL_COLD_READ_HANDOFF={handoff_path}")
        cold_rows = _fresh_process_read_chain(case, tuple(result_refs))
        assert tuple(Decimal(row["stock"]) for row in cold_rows) == expected_stocks
        assert len({row["value_sha256"] for row in cold_rows}) == 2
    finally:
        close = getattr(case.store, "close", None)
        if callable(close):
            close()


_LATE_HIDDEN_LOOKUP_FLOW = Decimal("-3000000000")


class _LateUndeclaredGDPReader(PeriodFlowToStock):
    signature: ClassVar[MethodSignature] = replace(
        PeriodFlowToStock.signature,
        namespace="tests.selected_input",
        name="late_undeclared_gdp_reader",
    )

    @staticmethod
    def pure_step(state: Mapping[str, Any], params: Mapping[str, Any]) -> dict[str, Any]:
        flow = state["period_flow"]
        if float(flow) == float(_LATE_HIDDEN_LOOKUP_FLOW) and float(state["gdp"]) < 0:
            raise ValueError("fixture_ambient_gdp_must_be_nonnegative")
        # Keep the stock delta valid even if a widened adapter exposes ambient GDP.
        return PeriodFlowToStock.pure_step({"period_flow": flow}, params)


def test_late_undeclared_method_port_blocks_complete_semantic_horizon(tmp_path: Path) -> None:
    """Reject a hidden port first read at effective step 3 despite complete declared inputs."""
    base = constant_price_two_year_method_spec()
    final_row = TemporalMethodYearInput(
        step=3,
        year=2023,
        ratio=Decimal("0.02"),
        denominator=Decimal("100000000000"),
        expected_flow=Decimal("2000000000"),
    )
    positive_spec = replace(
        base,
        time_semantics=base.time_semantics.model_copy(update={"step_count": 4}),
        scope=base.scope.model_copy(update={"period_end": date(2023, 12, 31)}),
        rows=(
            *base.rows,
            TemporalMethodYearInput(
                step=2,
                year=2022,
                ratio=Decimal("0.01"),
                denominator=Decimal("180000000000"),
                expected_flow=Decimal("1800000000"),
            ),
            final_row,
        ),
        # The positive control ends on an exactly representable float32 stock.
        expected_closing_stock=Decimal("12000000000"),
    )
    refusal_spec = replace(
        positive_spec,
        rows=(
            *positive_spec.rows[:-1],
            replace(final_row, ratio=Decimal("-0.03"), expected_flow=_LATE_HIDDEN_LOOKUP_FLOW),
        ),
        expected_closing_stock=Decimal("7000000000"),
    )

    def run_horizon(
        fixture: TemporalRegisteredMethodInputs,
        *,
        verified_prefix: tuple[SimulationResultRef, ...] = (),
        expect_refusal: bool = False,
    ) -> tuple[SimulationResultRef, ...]:
        case = fixture.case
        invocation, full, facts = _prepare_complete_input_bindings(fixture)
        assert invocation.steps == (0, 1, 2, 3)
        assert facts.bindings.schema_version == "1.5"
        assert facts.coverage.is_complete
        assert set(facts.values) == {("period_flow", step) for step in invocation.steps}
        request = ExecuteRequest(
            exec_plan_ref=case.exec_plan_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            input_bindings_ref=full.input_bindings_ref,
            return_selected_profile=True,
        )
        selected_rows = {
            item.step_scope.step: item.input for item in facts.bindings.selected_method_input_steps
        }
        result_refs = list(verified_prefix)
        for index, row in enumerate(
            fixture.spec.rows[len(verified_prefix) :], start=len(verified_prefix)
        ):
            assert Decimal(str(facts.values[("period_flow", row.step)].item())) == row.expected_flow
            executed = execute_semantic_horizon_step(
                case.store,
                request,
                expected_invocation=invocation,
                step=SemanticHorizonStepContext(
                    obligation_set_ref=fixture.preflight.obligation_set_ref,
                    steps=invocation.steps,
                    step_index=index,
                    replication_seed=17,
                    previous_result_ref=result_refs[-1] if result_refs else None,
                ),
            )
            assert executed.method_execution_bundle_ref is not None
            bundle = validate_core_model_json_artifact(
                MethodExecutionBundle, case.store, executed.method_execution_bundle_ref
            )
            (occurrence,) = (item for item in bundle.occurrences if item.node_kind == "method")
            assert occurrence.method_fqn == _LateUndeclaredGDPReader.signature.fqn
            assert occurrence.dispatch is not None
            assert occurrence.dispatch.step == row.step
            (argument,) = occurrence.dispatch.input_slot_values
            assert argument.slot_id == "period_flow"
            assert argument.value_sha256 == selected_rows[row.step].value_sha256
            if expect_refusal and row.step == 3:
                assert occurrence.status == "failed"
                assert (
                    occurrence.dispatch.failure_message_sha256
                    == hashlib.sha256(
                        b"Declared method invocation attempted an unavailable lookup"
                    ).hexdigest()
                )
                assert "method_execution_aborted" in executed.notes
                assert not executed.ok and executed.simulation_result_ref is None
            else:
                assert occurrence.status == "succeeded"
                assert executed.ok and executed.simulation_result_ref is not None
                result_refs.append(executed.simulation_result_ref)

        fresh = FileSystemCAS(case.store_root)
        try:
            if expect_refusal:
                assert len(result_refs) == 3
                with pytest.raises(ValueError, match="^semantic_horizon_result_schedule_mismatch$"):
                    execute_api.admit_semantic_horizon_step_chain(fresh, tuple(result_refs))
            else:
                admitted = execute_api.admit_semantic_horizon_step_chain(fresh, tuple(result_refs))
                assert len(admitted) == 4
                expected_stocks = (4000000000, 8200000000, 10000000000, 12000000000)
                for index, (item, stock) in enumerate(zip(admitted, expected_stocks, strict=True)):
                    assert item.basis is not None and item.basis.effective_step == index
                    snapshot_ref = item.simulation_result.state_snapshot_ref
                    assert snapshot_ref is not None
                    state = load_state_snapshot(fresh, snapshot_ref=snapshot_ref)
                    assert Decimal(str(float(state.government_balance))) == stock
        finally:
            close = getattr(fresh, "close", None)
            if callable(close):
                close()
        return tuple(result_refs)

    with ExitStack() as cases:
        positive = prepare_temporal_registered_method_inputs(
            tmp_path / "positive", spec=positive_spec, method_class=_LateUndeclaredGDPReader
        )
        cases.callback(positive.case.close)
        positive_results = run_horizon(positive)

        refusal = prepare_temporal_registered_method_inputs(
            tmp_path / "refusal", spec=refusal_spec, method_class=_LateUndeclaredGDPReader
        )
        cases.callback(refusal.case.close)
        run_horizon(refusal, expect_refusal=True)
        # Repeat the deciding step through the same dispatcher on the exact admitted prefix.
        run_horizon(positive, verified_prefix=positive_results[:-1])
