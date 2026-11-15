"""One real candidate treatment through the ordinary runtime CAS guard.

This is a test-owned diagnostic invocation, not an independent production
verifier, a hosted N5 completion, or permission to repeat another run's work.
It retains actual deadline diagnostics without changing the guard's defaults.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.core.artifacts import FileSystemCAS, artifact_ref_identity_key
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.foundry import ExecuteRequest, FoundryExecConfig
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.foundry.execute.actuation import (
    create_program_graph_actuation_selection,
    resolve_program_graph_actuation,
)
from polisyos.foundry.execute.api import admit_execution_source
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot
from polisyos.foundry.methods.catalog.policy.accounting import PeriodFlowToStock
from polisyos.runtime.http.errors import RuntimeDependencyTimeoutError
from polisyos.runtime.http.resilience import guard_runtime_cas
from tests._helpers.derived_selected_method_input import materialize_selected_method_input_case
from tests._helpers.selected_method_input import (
    prepare_selected_method_input_case,
    selected_method_tax_subsidy_policy,
)
from tests.unit.foundry.runtime.test_selected_method_inputs import _fresh_process_read
from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import _diagnostic_owner


def _value_identity(value: np.ndarray) -> dict[str, Any]:
    """Hash the actual argument independently of its selected binding record."""
    raw = value.tobytes(order="C")
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii"))
    digest.update(json.dumps(value.shape, separators=(",", ":")).encode("ascii"))
    digest.update(raw)
    return {
        "dtype": value.dtype.str,
        "shape": list(value.shape),
        "raw_hex": raw.hex(),
        "value_sha256": digest.hexdigest(),
    }


class _ActualCalls:
    def __init__(self) -> None:
        self.methods: list[dict[str, Any]] = []
        self.mechanisms: list[dict[str, Any]] = []
        self.nodes: list[dict[str, Any]] = []
        self.finishes: list[dict[str, Any]] = []
        self.graphs: list[dict[str, Any]] = []

    def graph_started(self, **values: Any) -> None:
        self.graphs.append({"step": values["step"], "seed": values["seed"]})

    def method_started(self, **values: Any) -> None:
        call = values["prepared_call"]
        actual = np.asarray(call.input_values["period_flow"])
        self.methods.append(
            {
                "node_id": values["node_id"],
                "step": values["step"],
                "seed": call.seed,
                "input": _value_identity(actual),
                "value": float(actual),
            }
        )

    def mechanism_started(self, **values: Any) -> None:
        self.mechanisms.append(
            {
                "node_id": values["node_id"],
                "step": values["step"],
                "government_balance_before_call": float(values["state"].government_balance),
            }
        )

    def method_finished(self, **values: Any) -> None:
        self.finishes.append({"family": "method", "status": values["status"]})

    def mechanism_finished(self, **values: Any) -> None:
        self.finishes.append({"family": "mechanism", "status": values["status"]})

    def node_finished(self, **values: Any) -> None:
        self.nodes.append({"node_id": values["node_id"], "status": values["status"]})

    def graph_finished(self, **values: Any) -> None:
        self.finishes.append({"family": "graph", "step": values["step"], "seed": values["seed"]})


def _exception_diagnostics(error: BaseException) -> list[dict[str, Any]]:
    """Retain bounded native wait observations from the actual exception chain."""
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(rows) < 8:
        seen.add(id(current))
        row: dict[str, Any] = {
            "type": f"{type(current).__module__}.{type(current).__qualname__}",
            "code": getattr(current, "code", None),
            "dependency_timeout": isinstance(current, RuntimeDependencyTimeoutError),
            "message": str(current)[:512],
        }
        diagnostic = getattr(current, "diagnostic", None)
        if callable(diagnostic):
            row["diagnostic"] = diagnostic()
        rows.append(row)
        current = current.__cause__ or current.__context__
    return rows


def _materialize_observing_epoch(
    case: Any, metadata: dict[str, Any], report: dict[str, Any]
) -> Any:
    """Observe a caught preparatory error without changing its owner or outcome."""
    from polisyos.runtime.quality.semantic_epoch import SemanticEpochService

    code = SemanticEpochService.finalize_admitted_epoch.__code__
    failures = report.setdefault("preparatory_epoch_exceptions", [])

    def handled(actual: Any, offset: int, error: BaseException) -> None:
        if actual is not code:
            return
        frames = []
        traceback = error.__traceback__
        while traceback is not None and len(frames) < 16:
            frame_code = traceback.tb_frame.f_code
            frames.append(
                {
                    "source": frame_code.co_filename,
                    "qualname": frame_code.co_qualname,
                    "line": traceback.tb_lineno,
                }
            )
            traceback = traceback.tb_next
        failures.append(
            {
                "type": f"{type(error).__module__}.{type(error).__qualname__}",
                "message": str(error)[:512],
                "frames": frames,
            }
        )

    tool_id = 4
    assert sys.monitoring.get_tool(tool_id) is None
    sys.monitoring.use_tool_id(tool_id, "guarded-foundry-preparation-cause")
    sys.monitoring.register_callback(tool_id, sys.monitoring.events.EXCEPTION_HANDLED, handled)
    # Python exposes EXCEPTION_HANDLED globally; retain only this exact code.
    sys.monitoring.set_events(tool_id, sys.monitoring.events.EXCEPTION_HANDLED)
    try:
        return materialize_selected_method_input_case(
            case, metadata, ratio_value=Decimal("-0.03"), denominator_value=Decimal("200000000000")
        )
    finally:
        sys.monitoring.set_events(tool_id, 0)
        sys.monitoring.register_callback(tool_id, sys.monitoring.events.EXCEPTION_HANDLED, None)
        sys.monitoring.free_tool_id(tool_id)


@pytest.mark.integration
def test_real_treatment_uses_default_guarded_foundry_execution(tmp_path: Path) -> None:
    """Observe one actual guarded treatment; preserve a real failure unchanged."""
    assert "POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS" not in os.environ
    report_path = tmp_path / "guarded-execution-diagnostic.json"
    report: dict[str, Any] = {
        "purpose": "candidate_guarded_execution_diagnostic_only",
        "guard_timeout_origin": "unchanged_factory_default_1.5_seconds",
        "foundry_execute_attempt_limit": 1,
        "n5_physical_work_observations": "not_observed",
        "foundry_execute_attempts": 0,
        "stage": "fixture",
        "timings_seconds": {},
    }
    observer = _ActualCalls()
    raw_store = FileSystemCAS(tmp_path / "cas")
    guarded_store = None
    case = None
    middleware = None
    phase_started = time.monotonic()
    try:
        incomes = (2**26, 2**27)
        case, metadata = prepare_selected_method_input_case(
            tmp_path,
            method_class=PeriodFlowToStock,
            store=raw_store,
            policy_spec=selected_method_tax_subsidy_policy(),
            income_values=incomes,
        )
        report["store_root"] = str(case.store_root)
        report["timings_seconds"]["fixture"] = time.monotonic() - phase_started
        report["stage"] = "materialize"
        phase_started = time.monotonic()
        materialized = _materialize_observing_epoch(case, metadata, report)
        bindings = load_input_bindings(case.store, materialized.input_bindings_ref)
        (selected_flow,) = (
            item for item in bindings.selected_method_inputs if item.slot_id == "period_flow"
        )
        selected_value = np.load(
            BytesIO(case.store.get_bytes(selected_flow.npy_value_ref)), allow_pickle=False
        )
        assert selected_value.dtype == np.dtype(np.float64) and selected_value.shape == ()
        assert float(selected_value) == -6_000_000_000.0
        report["selected_input"] = {
            "npy_ref": selected_flow.npy_value_ref.model_dump(mode="json"),
            **_value_identity(selected_value),
        }
        assert report["selected_input"]["value_sha256"] == selected_flow.value_sha256
        report["timings_seconds"]["materialize"] = time.monotonic() - phase_started
        report["stage"] = "select_treatment"
        inventory_ref = create_program_graph_actuation_selection(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            selected_intervention_ids=(),
        )
        inventory = resolve_program_graph_actuation(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            actuation_selection_ref=inventory_ref,
        )
        selected_ids = tuple(
            sorted({item for group in inventory.binding_groups for item in group.intervention_ids})
        )
        assert selected_ids
        selection_ref = create_program_graph_actuation_selection(
            case.store,
            program_ref=case.program_graph_ref,
            exec_plan_ref=case.exec_plan_ref,
            selected_intervention_ids=selected_ids,
        )
        request = ExecuteRequest(
            schema_version="1.1",
            exec_plan_ref=case.exec_plan_ref,
            input_bindings_ref=materialized.input_bindings_ref,
            registry_bundle_ref=case.registry_bundle_ref,
            actuation_selection_ref=selection_ref,
            exec_config=FoundryExecConfig(seed=23),
            return_selected_profile=True,
        )
        report["request"] = request.model_dump(mode="json")
        report["stage"] = "reserve_diagnostic_invocation"
        budget_directory = tmp_path / "separate-diagnostic-budget"
        _ledger, middleware, binding, policy, budget = _diagnostic_owner(
            budget_directory, total=1, protected=1, purpose="diagnostic"
        )
        assert policy.total_units == policy.protected_units == 1
        assert budget.invocation_purpose == "diagnostic"
        report["diagnostic_budget"] = {
            "run_binding": binding.model_dump(mode="json"),
            "policy": policy.model_dump(mode="json"),
            "ledger_directory": str(budget_directory),
        }
        operation_id = hashlib.sha256(str(report_path).encode()).hexdigest()
        request_digest = hashlib.sha256(
            to_canonical_bytes(request.model_dump(mode="json"), CanonSpec(forbid_floats=False))
        ).hexdigest()
        with budget.invocation_purpose_scope_from_selected_owner(policy, purpose="diagnostic"):
            reservation = budget.reserve_invocation(operation_id, request_digest)
            assert reservation is not None and reservation.units == 1
            guarded_store = guard_runtime_cas(case.store)
            report["stage"] = "guarded_execute"
            phase_started = time.monotonic()
            report["foundry_execute_attempts"] += 1
            try:
                executed = execute_foundry(guarded_store, request, observer=observer)
            except BaseException as error:
                report["exception"] = _exception_diagnostics(error)
                uncertain = not isinstance(error, Exception) or any(
                    row["dependency_timeout"] for row in report["exception"]
                )
                budget.finish_invocation(
                    operation_id, request_digest, "unknown" if uncertain else "failed"
                )
                raise
            else:
                budget.finish_invocation(
                    operation_id, request_digest, "completed" if executed.ok else "failed"
                )
            finally:
                report["timings_seconds"]["guarded_execute"] = time.monotonic() - phase_started
        report["execution"] = executed.model_dump(mode="json")
        assert executed.ok and executed.simulation_result_ref is not None
        assert len(observer.methods) == len(observer.mechanisms) == 1
        assert observer.graphs == [{"step": 0, "seed": 23}]
        assert [row["node_id"] for row in observer.nodes] == [
            node for node, _ in inventory.node_execution
        ]
        assert all(row["status"] == "succeeded" for row in observer.nodes)
        assert observer.methods[0]["input"] == _value_identity(selected_value)
        # This compiled profile buffers the method delta until op.merge_state;
        # record the actual mechanism prestate rather than predicting a flush.
        assert observer.mechanisms[0]["government_balance_before_call"] == 10_000_000_000.0
        assert {row["family"] for row in observer.finishes} == {"method", "mechanism", "graph"}
        assert all(
            row["status"] == "returned" for row in observer.finishes if row["family"] != "graph"
        )
        report["stage"] = "fresh_admission"
        phase_started = time.monotonic()
        fresh = FileSystemCAS.open_existing_read_only(case.store_root)
        admitted = admit_execution_source(fresh, executed.simulation_result_ref)
        assert admitted.basis is not None
        assert artifact_ref_identity_key(
            admitted.basis.actuation_selection_ref
        ) == artifact_ref_identity_key(selection_ref)
        assert admitted.simulation_result.state_snapshot_ref is not None
        state = load_state_snapshot(
            fresh, snapshot_ref=admitted.simulation_result.state_snapshot_ref
        )
        expected_income = np.asarray([value + value // 8 for value in incomes], dtype=np.float64)
        expected_balance = 10_000_000_000 - 6_000_000_000 - sum(incomes) // 8
        np.testing.assert_array_equal(np.asarray(state.agents.income), expected_income)
        assert float(state.government_balance) == expected_balance == 3_974_834_176.0
        assert float(np.mean(expected_income)) - sum(incomes) / len(incomes) == 12_582_912.0
        report["outcome"] = {
            "government_balance": float(state.government_balance),
            "income_mean": float(np.mean(np.asarray(state.agents.income, dtype=np.float64))),
            "notes": list(admitted.simulation_result.notes),
        }
        report["fresh_process"] = _fresh_process_read(case, executed.simulation_result_ref)
        assert report["fresh_process"]["stock"] == expected_balance
        assert report["fresh_process"]["occurrences"] == 1
        assert (
            report["fresh_process"]["value_sha256"] == observer.methods[0]["input"]["value_sha256"]
        )
        report["timings_seconds"]["fresh_admission"] = time.monotonic() - phase_started
        report["stage"] = "completed"
    except BaseException as error:
        if "exception" not in report:
            report["exception"] = _exception_diagnostics(error)
        raise
    finally:
        report["actual_methods"] = observer.methods
        report["actual_mechanisms"] = observer.mechanisms
        report["actual_nodes"] = observer.nodes
        report["actual_finishes"] = observer.finishes
        if middleware is not None:
            snapshot = middleware.snapshot_safe()
            report["invocations"] = [
                item.model_dump(mode="json") for item in snapshot.invocation_reservations.values()
            ]
            report["producer_settlement_count"] = len(snapshot.producer_settlements)
            assert len(snapshot.invocation_reservations) <= 1
            assert all(
                item.purpose == "diagnostic" for item in snapshot.invocation_reservations.values()
            )
        report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
        print(
            "guarded_foundry_diagnostic",
            json.dumps(
                {
                    "stage": report["stage"],
                    "foundry_execute_attempts": report["foundry_execute_attempts"],
                    "diagnostic_path": str(report_path),
                    "exception": report.get("exception"),
                }
            ),
        )
        if guarded_store is not None:
            guarded_store.close()
        elif callable(close := getattr(raw_store, "close", None)):
            close()
        if case is not None:
            case.close()
