"""Actual served A→B→B→B→C acquisition and retained-evaluation oracle."""

from __future__ import annotations

import sys
import threading
from collections import Counter
from functools import wraps
from pathlib import Path
from types import CodeType, SimpleNamespace
from typing import Any, Literal

import pytest
from fastapi.testclient import TestClient

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactRef, artifact_ref_for_manifest
from polisyos.runtime.http.services.acquisition_action_service import (
    AcquisitionRouteMutationRequest,
)
from polisyos.runtime.quality import n5_execution_basis as n5_basis
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationBasis,
    AcquisitionEvaluationDecision,
    AcquisitionSelectedEvaluation,
    basis_exact_values_equal,
    read_acquisition_evaluation_artifact,
    resolve_selected_acquisition_evaluation_parts,
)
from polisyos.runtime.quality.acquisition_retained_continuation import (
    read_acquisition_retained_continuation,
)
from polisyos.runtime.quality.acquisition_route_loop import (
    AcquisitionRouteLoopReceiptV2,
    AcquisitionRoutePhaseReceipt,
)
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthReceipt
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.runtime.quality.generation_cycle import (
    AcquisitionOverlayReentryReceipt,
    GenerationCycleController,
    JointSimulationPort,
    N4GenerationPort,
    generation_cycle_run_content_hash,
)
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    reconcile_live_n5_implementation,
)
from tests._helpers import acquisition_chain, acquisition_production
from tests._helpers import acquisition_served_history as fixture
from tests._helpers.acquisition_retention_history_probe import (
    assert_later_reentry_is_visible,
    assert_live_history_owner_was_exercised,
    install_history_owner_probe,
    install_later_reentry_probe,
)
from tests._helpers.control_worker import dispatch_one_control_job

pytest_plugins = ("tests._helpers.acquisition_served_history",)


class _OwnerCallMonitor:
    """Count actual owner entries without changing their loaded callable slots.

    Only PY_START is enabled locally for exact code objects: a coroutine's
    later PY_RESUME is not another call. The separate sys.monitoring tool
    does not occupy sys.setprofile, which the real N5 capture uses.
    """

    def __init__(self) -> None:
        self._tool_id: int | None = None
        self._targets: dict[int, tuple[CodeType, str]] = {}
        self._slots: list[tuple[Any, str, object]] = []
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()
        self._prior_profile: Any = None

    def __enter__(self) -> _OwnerCallMonitor:
        from polisyos.runtime.quality import data_state_substrate, world_model_record
        from polisyos.runtime.quality.cycle_substrate import (
            ConfiguredCandidateSimulationContextAdmissionOwner,
            CycleSubstrateContextArtifactOwner,
        )
        from polisyos.runtime.quality.joint_simulation_horizon import (
            JointSimulationHorizonController,
        )

        # IDs 0, 1, 2 and 5 are reserved for debugger, coverage, profiler,
        # and optimizer users. Never replace another active monitoring tool.
        for tool_id in (3, 4):
            if sys.monitoring.get_tool(tool_id) is not None:
                continue
            try:
                sys.monitoring.use_tool_id(tool_id, "acquisition-sequence-owner-observer")
            except ValueError:  # another user claimed it between the two reads
                continue
            self._tool_id = tool_id
            break
        if self._tool_id is None:
            raise RuntimeError("acquisition_sequence_monitor_tool_unavailable")
        self._prior_profile = sys.getprofile()
        try:
            # Python 3.14 clears any abandoned state for this now-owned free
            # tool ID. Active tools are never selected or modified.
            sys.monitoring.clear_tool_id(self._tool_id)
            if sys.monitoring.get_events(self._tool_id) != 0:
                raise RuntimeError("acquisition_sequence_monitor_global_events_active")
            old_callback = sys.monitoring.register_callback(
                self._tool_id, sys.monitoring.events.PY_START, self._on_start
            )
            if old_callback is not None or sys.getprofile() is not self._prior_profile:
                raise RuntimeError("acquisition_sequence_monitor_not_isolated")
            self.watch("n4", N4GenerationPort.__call__)
            self.watch_slot("n5", JointSimulationPort, "__call__")
            self.watch_slot("n5_controller", JointSimulationHorizonController, "run")
            self.watch_slot(
                "context",
                ConfiguredCandidateSimulationContextAdmissionOwner,
                "admit_context_for_acquired_world",
            )
            self.watch_slot(
                "context_persist", CycleSubstrateContextArtifactOwner, "persist_for_current_job"
            )
            self.watch_slot(
                "world", data_state_substrate, "build_acquired_observation_candidate_world"
            )
            self.watch_slot("world_persist", world_model_record, "persist_world_model_record")
            self.watch_slot("cycle", GenerationCycleController, "run")
            # Acquisition reentry enters the actual cycle directly; seed
            # run and reentry cycle are different observed quantities.
            self.watch_slot("reentry_cycle", GenerationCycleController, "_run_cycle")
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
        if _exc[0] is None and sys.getprofile() is not self._prior_profile:
            raise RuntimeError("acquisition_sequence_profile_state_changed")

    def watch(self, label: str, function: Any) -> None:
        code = getattr(function, "__code__", None)
        if self._tool_id is None or not isinstance(code, CodeType):
            raise RuntimeError("acquisition_sequence_owner_code_not_established")
        with self._lock:
            previous = self._targets.get(id(code))
            if previous is not None and (previous[0] is not code or previous[1] != label):
                raise RuntimeError("acquisition_sequence_owner_code_ambiguous")
            self._targets[id(code)] = (code, label)
        sys.monitoring.set_local_events(self._tool_id, code, sys.monitoring.events.PY_START)

    def watch_slot(self, label: str, owner: Any, name: str) -> None:
        function = getattr(owner, name)
        self._slots.append((owner, name, function))
        self.watch(label, function)

    def _on_start(self, code: CodeType, _instruction_offset: int) -> None:
        with self._lock:
            target = self._targets.get(id(code))
            if target is not None and target[0] is code:
                self._counts[target[1]] += 1

    def snapshot(self) -> Counter[str]:
        with self._lock:
            return self._counts.copy()

    def assert_slots_unchanged(self) -> None:
        assert all(getattr(owner, name) is function for owner, name, function in self._slots), (
            "a monitored owner slot changed while collecting calls"
        )

    def close(self) -> None:
        if self._tool_id is None:
            return
        tool_id = self._tool_id
        for code, _label in self._targets.values():
            sys.monitoring.set_local_events(tool_id, code, 0)
        sys.monitoring.register_callback(tool_id, sys.monitoring.events.PY_START, None)
        sys.monitoring.free_tool_id(tool_id)
        self._tool_id = None


class _SequentialOracle:
    """Configure only real fixture inputs and observe the actual owner methods."""

    attempt_ids = (
        acquisition_production._ATTEMPT_ID,
        "n13b-worldbank-government-balance-002",
        "n13b-worldbank-government-balance-003",
        "n13b-worldbank-government-balance-004",
    )

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        monitor: _OwnerCallMonitor,
        *,
        after_real_b: Any | None = None,
    ) -> None:
        self.monkeypatch = monkeypatch
        self.monitor = monitor
        self.after_real_b = after_real_b
        self.epoch_id = 1
        self.value = -17.1
        real_rows = acquisition_production._normalized_rows

        @wraps(real_rows)
        def selected_rows(*, adjacent: str | None = None) -> list[dict[str, object]]:
            rows = real_rows(adjacent=adjacent)
            return [{**row, "value": self.value} if row["year"] == 2024 else row for row in rows]

        # The normal intercepted HTTP transport, Fabric, PII, passport and
        # native epoch owners consume these actual response bytes unchanged.
        monkeypatch.setattr(acquisition_production, "_normalized_rows", selected_rows)

    def observe_case(self, case: Any, patch: pytest.MonkeyPatch) -> None:
        """Observe the fixture's actual installed N4 code without replacing it."""
        del case, patch
        actual = N4GenerationPort.__call__
        fixture_codes = tuple(
            constant
            for constant in acquisition_chain.make_wdi_port_case.__code__.co_consts
            if isinstance(constant, CodeType) and constant.co_name == "fixture_candidates"
        )
        if not any(getattr(actual, "__code__", None) is code for code in fixture_codes):
            raise RuntimeError("acquisition_sequence_fixture_n4_slot_not_established")
        self.monitor.watch("n4", actual)

    @staticmethod
    def _artifact_sets(store: Any) -> dict[str, frozenset[str]]:
        # Every inventory is an owner snapshot, not a list of expected IDs.
        kinds = (
            "runtime.quality.n4_candidate_proposal",
            "runtime.quality.n4_candidate_scenario_source",
            "runtime.quality.cycle_substrate_context_job",
            "runtime.quality.world_model_record",
            "runtime.quality.candidate_simulation_n5_input",
            "runtime.quality.candidate_simulation_execution",
            "polisyos.runtime.joint_simulation_result",
        )
        result = {}
        for kind in kinds:
            inventory = fixture._within_fixture_owner(store.manifest_inventory_snapshot, kind=kind)
            assert inventory.verdict == "pass", (kind, inventory)
            result[kind] = frozenset(str(entry.manifest.artifact_id) for entry in inventory.entries)
        return result

    @staticmethod
    def _selected(store: Any, ref: str) -> ArtifactRef:
        return fixture._within_fixture_owner(
            lambda: artifact_ref_for_manifest(store.get_manifest(ref))
        )

    @staticmethod
    def _actual_source(
        store: Any, growth: AcquisitionWorldGrowthReceipt
    ) -> tuple[ArtifactRef, bytes]:
        from polisyos.core.contracts import epoch
        from polisyos.runtime.quality.acquisition_executor import AdmissionPassport

        passport = AdmissionPassport.model_validate(
            fixture._within_fixture_owner(
                epoch.load_verified_epoch_statement,
                store=store,
                ref=growth.activation.passport_ref,
                expected_kind="epoch.acquisition_passport_snapshot",
            )
        )
        boundary = epoch.AcquisitionSemanticBoundaryCandidateStatement.model_validate(
            fixture._within_fixture_owner(
                epoch.load_verified_epoch_statement,
                store=store,
                ref=passport.semantic_boundary_candidate_ref,
                expected_kind="epoch.acquisition_semantic_boundary_candidate",
            )
        )
        assert epoch.acquisition_semantic_candidate_content_hash(boundary) == (
            passport.semantic_boundary_candidate_content_hash
        )
        source_ref = boundary.source_record_ref
        assert source_ref.manifest_profile_sha256 is not None
        assert fixture._within_fixture_owner(store.verify, source_ref).ok
        return source_ref, fixture._within_fixture_owner(store.get_bytes, source_ref)

    def _action(
        self,
        ctx: SimpleNamespace,
        *,
        name: str,
        appoint: bool,
        expected_worker_error: Literal[
            "n5_prepared_configuration_not_consumed",
            "acquisition_evaluation_configuration_not_established",
        ]
        | None = None,
    ) -> SimpleNamespace:
        """Run ordinary decision, human approval, protected POST, and worker."""
        from polisyos.runtime.http.services.acquisition_action_service import (
            AcquisitionActionService,
        )

        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            service = client.app.state.runtime_container.acquisition_action_service
            closure = fixture._within_fixture_owner(
                service._resolve,
                tenant_id=fixture.TENANT,
                cell_id=fixture.CELL,
                run_id=ctx.run_id,
            )
            request = AcquisitionRouteMutationRequest(
                route_projection_hash=closure.route_id,
                planner_report_hash=agent_action_content_hash(closure.planner_report),
                replay_pins=AcquisitionActionService._pins(closure),
                idempotency_key=f"retained-sequential-{name}",
            )
            response, digest = ctx.trust.post(
                client,
                ctx.path + "/decision-request",
                request.model_dump(mode="json"),
                route=ctx.route_prefix + "/decision-request",
            )
            assert response.status_code == 200, response.text
            slot, job_id = ctx.appoint_mandate(control, request, digest)
            ctx.trust.raw["acquisition_authority"]["mandates"].append(slot)

        with TestClient(ctx.app()) as client:
            _source, human_ref = ctx.approve_request(client, request, digest)
            slot["human_decision_record_ref"] = human_ref

        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            response, _ = ctx.trust.post(
                client,
                ctx.path + "/execute",
                request.model_dump(mode="json"),
                route=ctx.route_prefix + "/execute",
            )
            assert response.status_code in {200, 202}, response.text
            job = control._control_store.get_job(job_id)
            assert job is not None
            payload = canon.from_canonical_bytes(
                fixture._within_fixture_owner(control._artifact_store.get_bytes, job.payload_ref)
            )
            assert payload["invocation"]["budget_delta"] == {"acquisition_actions": 1}
            assert payload["operation"]["cost_model"]["cost_basis_hash"] == closure.cost_basis_hash
            assert payload["decision_ref"]

        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            case = ctx.cases[-1]
            before_calls = self.monitor.snapshot()
            before_artifacts = self._artifact_sets(control._artifact_store)
            dispatch_one_control_job(
                store=control._control_store,
                handler=control._process_control_job,
                expected_job_id=job_id,
            )
            completed = control._control_store.get_job(job_id)
            assert completed is not None
            if expected_worker_error is not None:
                assert expected_worker_error in {
                    "n5_prepared_configuration_not_consumed",
                    "acquisition_evaluation_configuration_not_established",
                }
                assert not appoint
                assert completed.state == "failed", completed
                assert completed.error_message == expected_worker_error, completed
                if expected_worker_error == "acquisition_evaluation_configuration_not_established":
                    failure = completed.progress.get("failure")
                    assert isinstance(failure, dict)
                    assert failure["code"] == expected_worker_error
                    assert failure["layer"] == "n5_configuration_preparation"
                heads = control._control_store.list_acquisition_action_heads_for_source(
                    tenant_id=fixture.TENANT,
                    cell_id=fixture.CELL,
                    run_id=ctx.run_id,
                    source_job_id=ctx.source_job_id,
                )
                selected = tuple(head for head in heads if head.job_id == job_id)
                assert len(selected) == 1, selected
                selected_head = selected[0]
                expected_phase = (
                    "outcome_selected"
                    if expected_worker_error
                    == "acquisition_evaluation_configuration_not_established"
                    else "world_committed_reentry_pending"
                )
                assert selected_head.receipt_phase == expected_phase
                assert selected_head.recovery_state == (
                    "none" if expected_phase == "outcome_selected" else "reentry_recovery_required"
                )
                selected_phase_ref = self._selected(
                    control._artifact_store, selected_head.receipt_ref
                )
                selected_phase = AcquisitionRoutePhaseReceipt.model_validate(
                    canon.from_canonical_bytes(
                        fixture._within_fixture_owner(
                            control._artifact_store.get_bytes, selected_phase_ref
                        ),
                    )
                )
                assert selected_phase.job_id == job_id
                assert selected_phase.receipt_phase == expected_phase
                assert selected_phase.predecessor_receipt_ref
                return SimpleNamespace(
                    receipt=None,
                    receipt_ref=None,
                    job_id=job_id,
                    payload=payload,
                    worker_error=completed.error_message,
                    job_record=completed,
                    selected_head=selected_head,
                    selected_phase=selected_phase,
                    selected_phase_ref=selected_phase_ref,
                    before_calls=before_calls,
                    after_calls=self.monitor.snapshot(),
                    before_artifacts=before_artifacts,
                    after_artifacts=self._artifact_sets(control._artifact_store),
                    transport_calls=tuple(case.transport_calls),
                )
            assert completed.state == "completed", completed
            assert completed.progress["receipt_phase"] == "terminal", completed.progress
            receipt_ref = completed.progress["terminal_receipt_ref"]
            receipt = fixture._read_owned_terminal(control._artifact_store, receipt_ref)
            assert receipt.job_id == job_id and receipt.source_job_id == ctx.source_job_id
            assert receipt.run_id == ctx.run_id
            selected_terminal = self._selected(control._artifact_store, receipt_ref)
            assert fixture._within_fixture_owner(
                control._artifact_store.get_bytes, selected_terminal
            )
            after_artifacts = self._artifact_sets(control._artifact_store)
            if appoint:
                assert receipt.terminal_outcome == "quarantined_no_growth"
                assert case.transport_calls, "fresh provisioned source was not fetched"
                assert fixture._within_fixture_owner(case.bridge.has_deferred_admission, closure)
                fixture._within_fixture_owner(case.appoint_native_policy)
            return SimpleNamespace(
                receipt=receipt,
                receipt_ref=selected_terminal,
                job_id=job_id,
                payload=payload,
                before_calls=before_calls,
                after_calls=self.monitor.snapshot(),
                before_artifacts=before_artifacts,
                after_artifacts=after_artifacts,
                transport_calls=tuple(case.transport_calls),
            )

    def _fresh_projection(self, ctx: SimpleNamespace) -> dict[str, Any]:
        with TestClient(ctx.app()) as client:
            response = client.get(ctx.history_path, headers=ctx.history_headers)
            assert response.status_code == 200, response.text
            projection = response.json()["run"]["candidate_simulation"]
            assert projection["acquisition_history_limitation_code"] is None, projection
            return projection

    def run(self, **values: Any) -> None:
        ctx = SimpleNamespace(**values)
        assert ctx.reentry.new_cycle == ctx.closure.source_cycle
        assert ctx.growth.selection.epoch_id == 1 and ctx.growth.admitted_observation_delta > 0
        assert (
            ctx.seed_input.n5.baseline_state[ctx.target_world_slot]
            != ctx.evaluated_input.n5.baseline_state[ctx.target_world_slot]
        )
        observed = self.monitor.snapshot()
        assert all(
            observed[name] > 0
            for name in (
                "n4",
                "n5",
                "n5_controller",
                "context",
                "context_persist",
                "world",
                "world_persist",
                "cycle",
            )
        ), (
            "actual owner observer missed the initial producer chain",
            observed,
        )
        self.monitor.assert_slots_unchanged()
        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            actual_b = fixture._within_fixture_owner(
                resolve_selected_acquisition_evaluation_parts,
                artifact_store=control._artifact_store,
                control_store=control._control_store,
                tenant_id=fixture.TENANT,
                cell_id=fixture.CELL,
                run_id=ctx.run_id,
                generation_run=ctx.closure.generation_run,
                source_cycle=ctx.closure.source_cycle,
                design_problem_ref=ctx.closure.design_problem_ref,
            )
            selected_b = actual_b.selected
            witness = fixture._within_fixture_owner(
                reconcile_live_n5_implementation,
                actual_b.result,
                input_ref=selected_b.n5_input_ref,
            )
            assert witness.predicate_provenance == "recomputed" and not witness.reason_codes
            with n5_basis._LOCK:
                issued = n5_basis._ISSUED.get(witness.content_hash)
            assert issued is not None and issued.witness == witness
            capture = issued.capture
            from polisyos.runtime.quality.joint_simulation_horizon import (
                JointSimulationHorizonController,
            )

            source = witness.implementation.get("source")
            assert isinstance(source, dict)
            executed = source.get("executed_code")
            assert isinstance(executed, list) and executed
            assert all(
                isinstance(row, list)
                and len(row) == 3
                and all(isinstance(item, str) for item in row)
                for row in executed
            )
            callback = self.monitor._on_start.__func__
            callback_identity = (callback.__globals__["__name__"], callback.__code__.co_qualname)
            controller = JointSimulationHorizonController.run
            controller_identity = (
                controller.__globals__["__name__"],
                controller.__code__.co_qualname,
            )
            observed_identities = {(row[0], row[1]) for row in executed}
            assert controller_identity in observed_identities
            assert callback_identity not in observed_identities
            assert selected_b.evaluation_job_id != ctx.source_job_id
            retained_refs = (
                selected_b.n4_source_ref,
                selected_b.context_job_ref,
                selected_b.n5_input_ref,
                selected_b.n5_execution_ref,
                selected_b.n5_result_ref,
            )
            retained_bytes = tuple(
                (ref, fixture._within_fixture_owner(control._artifact_store.get_bytes, ref))
                for ref in retained_refs
            )

        # Optional independent oracle branch: no product slot is changed during
        # the first B producer. Its callback may drive a fresh real action.
        def issue_equal_source(
            *,
            expected_worker_error: Literal[
                "n5_prepared_configuration_not_consumed",
                "acquisition_evaluation_configuration_not_established",
            ]
            | None = None,
        ) -> tuple[SimpleNamespace, SimpleNamespace]:
            self.epoch_id = 2
            negative = self._action(ctx, name="epoch-2-prepare", appoint=True)
            positive = self._action(
                ctx,
                name="epoch-2-admit-equal",
                appoint=False,
                expected_worker_error=expected_worker_error,
            )
            return negative, positive

        if self.after_real_b is not None:
            self.after_real_b(
                ctx=ctx,
                oracle=self,
                actual_b=actual_b,
                selected_b=selected_b,
                witness=witness,
                capture=capture,
                issue_equal_source=issue_equal_source,
            )
            return

        history_records = install_history_owner_probe(self.monkeypatch)
        later_records = install_later_reentry_probe(self.monkeypatch)

        # Two distinct epochs each obtain real source bytes and an actual
        # policy-admission refusal before a second action resumes admission.
        retained_terminals: list[AcquisitionRouteLoopReceiptV2] = []
        frontier_refs: list[str] = []
        growth_refs: list[str] = []
        for epoch in (2, 3):
            self.epoch_id = epoch
            negative_b = self._action(ctx, name=f"epoch-{epoch}-prepare", appoint=True)
            equal_b = self._action(ctx, name=f"epoch-{epoch}-admit-equal", appoint=False)
            assert negative_b.job_id != equal_b.job_id
            assert equal_b.receipt.action_generation == negative_b.receipt.action_generation + 1
            assert (
                negative_b.payload["invocation"]["invocation_id"]
                != (equal_b.payload["invocation"]["invocation_id"])
            )
            assert not equal_b.transport_calls  # resumes the independently fetched attempt
            terminal = equal_b.receipt
            assert type(terminal) is AcquisitionRouteLoopReceiptV2
            assert terminal.terminal_outcome == "source_admitted_evaluation_retained"
            assert (
                terminal.reentry_receipt_ref is None
                and terminal.current_continuation_ref is not None
            )
            assert terminal.selected_evaluation is not None
            assert exact_n5_content_bytes(
                terminal.selected_evaluation.model_dump(exclude={"basis_ref"})
            ) == exact_n5_content_bytes(selected_b.model_dump(exclude={"basis_ref"}))
            assert terminal.selected_evaluation.basis_ref == terminal.selected_basis_ref
            assert equal_b.after_calls == equal_b.before_calls
            assert equal_b.after_artifacts == equal_b.before_artifacts
            self.monitor.assert_slots_unchanged()

            with TestClient(ctx.app()) as client:
                control = client.app.state.runtime_container.control_service
                store, events = control._artifact_store, control._diagnostic_event_log
                for ref, raw in retained_bytes:
                    assert fixture._within_fixture_owner(store.get_bytes, ref) == raw
                decision = fixture._within_fixture_owner(
                    read_acquisition_evaluation_artifact,
                    store=store,
                    event_log=events,
                    ref=terminal.evaluation_decision_ref,
                    record_type=AcquisitionEvaluationDecision,
                )
                assert type(decision) is AcquisitionEvaluationDecision
                assert decision.comparison_result == "equivalent"
                prior = fixture._within_fixture_owner(
                    read_acquisition_evaluation_artifact,
                    store=store,
                    event_log=events,
                    ref=decision.prior_basis_ref,
                    record_type=AcquisitionEvaluationBasis,
                )
                current = fixture._within_fixture_owner(
                    read_acquisition_evaluation_artifact,
                    store=store,
                    event_log=events,
                    ref=decision.current_basis_ref,
                    record_type=AcquisitionEvaluationBasis,
                )
                assert type(prior) is type(current) is AcquisitionEvaluationBasis
                assert basis_exact_values_equal(prior, current)
                assert str(decision.growth_receipt_ref.artifact_id) != ctx.growth_ref
                growth = AcquisitionWorldGrowthReceipt.model_validate(
                    canon.from_canonical_bytes(
                        fixture._within_fixture_owner(store.get_bytes, decision.growth_receipt_ref)
                    )
                )
                assert growth.selection.epoch_id == epoch and growth.admitted_observation_delta > 0
                source_b, source_b_bytes = self._actual_source(store, growth)
                assert source_b == decision.admitted_source_ref and source_b_bytes
                continuation = fixture._within_fixture_owner(
                    read_acquisition_retained_continuation,
                    store=store,
                    event_log=events,
                    ref=terminal.current_continuation_ref,
                    decision=decision,
                    terminal=terminal,
                )
                assert continuation.retained_evaluation == terminal.selected_evaluation
                assert continuation.source_job_id == ctx.source_job_id
                assert continuation.action_job_id == equal_b.job_id
                assert continuation.current_projection.current_planner_report_ref is not None
                assert continuation.current_projection.current_planner_inputs is not None
                head = fixture._within_fixture_owner(
                    control._control_store.get_acquisition_action_head,
                    tenant_id=terminal.tenant_id,
                    cell_id=terminal.cell_id,
                    run_id=terminal.run_id,
                    source_job_id=terminal.source_job_id,
                    route_id=terminal.route_id,
                    action_generation=terminal.action_generation,
                )
                assert head is not None
                assert head.evaluation_frontier_before_ref == decision.expected_frontier_ref
                assert head.evaluation_frontier_ref == decision.expected_frontier_ref
                frontier = fixture._within_fixture_owner(
                    control._control_store.get_acquisition_evaluation_frontier_by_ref,
                    decision.expected_frontier_ref,
                )
                assert frontier is not None
                assert frontier.revision == decision.expected_frontier_revision
                assert frontier.selected_evaluation_witness_ref == str(
                    selected_b.n5_execution_ref.artifact_id
                )
                assert frontier.selected_evaluation_content_hash == actual_b.execution.content_hash
                assert frontier.basis_ref == str(decision.prior_basis_ref.artifact_id)
                assert frontier.basis_content_hash == prior.content_hash
                frontier_refs.append(decision.expected_frontier_ref)
                growth_refs.append(str(decision.growth_receipt_ref.artifact_id))

            projection = self._fresh_projection(ctx)
            retained = next(
                row
                for row in projection["acquisition_history"]
                if row["action_generation"] == terminal.action_generation
            )
            assert retained["terminal_outcome"] == "source_admitted_evaluation_retained"
            assert (
                AcquisitionSelectedEvaluation.model_validate(retained["retained_evaluation"])
                == terminal.selected_evaluation
            )
            assert retained[
                "current_continuation_ref"
            ] == terminal.current_continuation_ref.model_dump(mode="json")
            assert_live_history_owner_was_exercised(history_records)
            retained_terminals.append(terminal)
            for retained_terminal in retained_terminals:
                replayed = next(
                    row
                    for row in projection["acquisition_history"]
                    if row["action_generation"] == retained_terminal.action_generation
                )
                assert replayed["current_continuation_ref"] == (
                    retained_terminal.current_continuation_ref.model_dump(mode="json")
                )
                assert (
                    AcquisitionSelectedEvaluation.model_validate(replayed["retained_evaluation"])
                    == retained_terminal.selected_evaluation
                )

        assert len(set(growth_refs)) == 2
        assert len(set(frontier_refs)) == 1
        assert retained_terminals[1].action_generation == (
            retained_terminals[0].action_generation + 2
        )
        assert retained_terminals[0].current_continuation_ref != (
            retained_terminals[1].current_continuation_ref
        )

        # Another distinct actual fetch changes the measured value. The next
        # positive result must start from the still-selected B evaluation.
        self.epoch_id = 4
        self.value = -9.0
        negative_c = self._action(ctx, name="epoch-4-prepare", appoint=True)
        changed_c = self._action(ctx, name="epoch-4-admit-different", appoint=False)
        assert negative_c.job_id != changed_c.job_id
        assert negative_c.receipt.action_generation == terminal.action_generation + 1
        assert changed_c.receipt.action_generation == negative_c.receipt.action_generation + 1
        assert (
            negative_c.payload["invocation"]["invocation_id"]
            != (negative_b.payload["invocation"]["invocation_id"])
        )
        assert type(changed_c.receipt) is AcquisitionRouteLoopReceiptV2
        assert changed_c.receipt.terminal_outcome == "reentry_completed"
        assert changed_c.receipt.reentry_receipt_ref is not None
        assert changed_c.after_calls["n5"] > changed_c.before_calls["n5"]
        assert changed_c.after_calls["n5_controller"] > changed_c.before_calls["n5_controller"]
        assert changed_c.after_calls["reentry_cycle"] > changed_c.before_calls["reentry_cycle"]
        self.monitor.assert_slots_unchanged()
        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            store, events = control._artifact_store, control._diagnostic_event_log
            changed_decision = fixture._within_fixture_owner(
                read_acquisition_evaluation_artifact,
                store=store,
                event_log=events,
                ref=changed_c.receipt.evaluation_decision_ref,
                record_type=AcquisitionEvaluationDecision,
            )
            assert type(changed_decision) is AcquisitionEvaluationDecision
            assert changed_decision.comparison_result == "different"
            assert changed_decision.predicate_provenance == "recomputed"
            changed_prior = fixture._within_fixture_owner(
                read_acquisition_evaluation_artifact,
                store=store,
                event_log=events,
                ref=changed_decision.prior_basis_ref,
                record_type=AcquisitionEvaluationBasis,
            )
            changed_current = fixture._within_fixture_owner(
                read_acquisition_evaluation_artifact,
                store=store,
                event_log=events,
                ref=changed_decision.current_basis_ref,
                record_type=AcquisitionEvaluationBasis,
            )
            assert type(changed_prior) is type(changed_current) is AcquisitionEvaluationBasis
            assert not basis_exact_values_equal(changed_prior, changed_current)
            assert changed_decision.prior_evaluation is not None
            assert exact_n5_content_bytes(
                changed_decision.prior_evaluation.model_dump(exclude={"basis_ref"})
            ) == exact_n5_content_bytes(selected_b.model_dump(exclude={"basis_ref"}))
            c_growth_refs = tuple(
                ref
                for ref in changed_c.receipt.owner_receipt_refs
                if fixture._within_fixture_owner(store.get_manifest, ref).kind
                == "runtime_quality.acquisition_world_growth_receipt"
            )
            assert len(c_growth_refs) == 1
            growth_c = AcquisitionWorldGrowthReceipt.model_validate(
                canon.from_canonical_bytes(
                    fixture._within_fixture_owner(store.get_bytes, c_growth_refs[0])
                )
            )
            assert growth_c.selection.epoch_id == 4 and growth_c.admitted_observation_delta > 0
            source_c, source_c_bytes = self._actual_source(store, growth_c)
            assert source_c_bytes and source_c_bytes != source_b_bytes
            assert source_c.artifact_id != source_b.artifact_id
            reentry = AcquisitionOverlayReentryReceipt.model_validate(
                canon.from_canonical_bytes(
                    fixture._within_fixture_owner(
                        store.get_bytes, changed_c.receipt.reentry_receipt_ref
                    )
                )
            )
            assert reentry.source_cycle_index == selected_b.cycle_index
            assert reentry.source_generation_run_content_hash == generation_cycle_run_content_hash(
                ctx.closure.generation_run
            )
            assert reentry.new_cycle.cycle_index == selected_b.cycle_index + 1
            assert (
                reentry.continued_generation_run.cycles[
                    -2
                ].simulation.candidate_simulation_n5_input_ref
                == selected_b.n5_input_ref
            )
        projection = self._fresh_projection(ctx)
        for retained_terminal in retained_terminals:
            replayed = next(
                row
                for row in projection["acquisition_history"]
                if row["action_generation"] == retained_terminal.action_generation
            )
            assert replayed["current_continuation_ref"] == (
                retained_terminal.current_continuation_ref.model_dump(mode="json")
            )
            assert (
                AcquisitionSelectedEvaluation.model_validate(replayed["retained_evaluation"])
                == retained_terminal.selected_evaluation
            )
        assert_later_reentry_is_visible(projection, later_records)
        later = next(
            row
            for row in projection["acquisition_history"]
            if row["action_generation"] == changed_c.receipt.action_generation
        )
        assert later["terminal_outcome"] == "reentry_completed"
        assert later["expected_origin_source_ref"]["artifact_id"] == str(
            selected_b.n4_source_ref.artifact_id
        )


def test_served_actual_acquisition_retains_equal_b_then_reenters_for_c(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """Fresh owner admissions distinguish exact values without inventing a cycle."""
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )

    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "candidate-source", include_owner_slot_manifest=True
    )
    with _OwnerCallMonitor() as monitor:
        oracle = _SequentialOracle(monkeypatch, monitor)
        result = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            sequential_oracle=oracle,
            provider_mode="synthetic_settled_candidate",
        )
    assert result is not None and result["run_id"] and result["candidate_id"]


def test_owner_monitor_counts_one_async_entry_without_replacing_profile_or_slots() -> None:
    """Yield/resume is not a new call, and another profiler keeps receiving events."""
    import asyncio

    async def yielding_operation() -> None:
        await asyncio.sleep(0)
        await asyncio.sleep(0)

    original_n4 = N4GenerationPort.__call__
    original_n5 = JointSimulationPort.__call__
    original_cycle = GenerationCycleController.run
    prior = sys.getprofile()
    if prior is not None:
        raise RuntimeError("acquisition_sequence_monitor_profile_probe_conflict")
    profile_events = []

    def profile(frame: Any, event: str, _arg: object) -> None:
        if frame.f_code is yielding_operation.__code__ and event == "call":
            profile_events.append(event)

    try:
        sys.setprofile(profile)
        with _OwnerCallMonitor() as monitor:
            monitor.watch("probe", yielding_operation)
            asyncio.run(yielding_operation())
            assert monitor.snapshot()["probe"] == 1
            assert sys.getprofile() is profile
            assert len(profile_events) >= 2
            assert N4GenerationPort.__call__ is original_n4
            assert JointSimulationPort.__call__ is original_n5
            assert GenerationCycleController.run is original_cycle
            monitor.assert_slots_unchanged()
        assert sys.getprofile() is profile
    finally:
        sys.setprofile(prior)


@pytest.mark.asyncio
async def test_legacy_route_attempt_remains_recoverable_and_new_epoch_is_distinct(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> None:
    """A real old producer's pointer stays authoritative only for its own epoch."""
    import hashlib

    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
        AcquisitionWorldGrowthConfig,
    )
    from tests.integration.core_runtime.test_acquisition_world_growth_chain import (
        _run_actual_wdi_admits_delta_and_reenters_same_case,
    )

    def old_route_pointer(
        bridge: AcquisitionWorldGrowthBridge, selected: Any, *, create: bool = True
    ) -> Path:
        overlay, _ = bridge._paths(selected, create=create)
        identity = hashlib.sha256(canon.to_canonical_bytes(list(selected.key))).hexdigest()
        return overlay.parent / (identity + ".growth.json")

    # Produce an authentic old-layout attempt, deferral, admission, and
    # same-epoch zero-delta outcome; do not manufacture their bytes or labels.
    with monkeypatch.context() as old_runtime:
        old_runtime.setattr(AcquisitionWorldGrowthBridge, "_growth_pointer", old_route_pointer)
        served = await _run_actual_wdi_admits_delta_and_reenters_same_case(
            tmp_path, monkeypatch, request, guarded_cas=False
        )
    case, closure = served.case, served.closure
    bridge = case.bridge
    legacy = old_route_pointer(bridge, case.selected, create=False)
    old_bytes = legacy.read_bytes()
    assert bridge._growth_pointer(case.selected, create=False) == legacy
    fetched = tuple(case.transport_calls)
    repeated = case.port.execute(closure)
    assert repeated.disposition == "quarantined_no_growth"
    assert repeated.admitted_observation_delta == 0
    assert tuple(case.transport_calls) == fetched
    assert legacy.read_bytes() == old_bytes

    later = case.selected.model_copy(update={"epoch_id": case.selected.epoch_id + 1})
    later_bridge = AcquisitionWorldGrowthBridge(
        config=AcquisitionWorldGrowthConfig(routes=(later,)),
        repo_root=bridge.repo_root,
        runtime_root=bridge.runtime_root,
        authority=bridge.authority,
        artifact_store=bridge.artifact_store,
        event_log=bridge.event_log,
        epoch_deployment=bridge.epoch_deployment,
        promotion_runtime=bridge.promotion_runtime,
        cycle_substrate_context_admission_owner=bridge.cycle_substrate_context_admission_owner,
        control_store=bridge.control_store,
        action_head_sink=bridge.action_head_sink,
        source_control_service=bridge._source_control_service,
    )
    current = later_bridge._growth_pointer(later, create=False)
    assert current != legacy
    assert not later_bridge.has_admission_attempt(closure)
    assert legacy.read_bytes() == old_bytes

    attempt_path = legacy.with_suffix(".attempt.json")
    attempt_bytes = attempt_path.read_bytes()
    try:
        # A route-only pathname is not proof of an epoch. Corrupt the old
        # owner selector while retaining the old and new route/epoch labels.
        attempt_path.write_bytes(b"{}")
        with pytest.raises(ValueError, match="acquisition_legacy_growth_pointer_unverified"):
            later_bridge._growth_pointer(later, create=False)
    finally:
        attempt_path.write_bytes(attempt_bytes)
    assert later_bridge._growth_pointer(later, create=False) == current


def test_retained_join_reopens_persisted_current_source_and_compiler(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """A synthetic candidate gap exercises the actual retained producer and reader.

    The fixture declares a grounding limitation; it does not measure L1 absence
    or grant a live acquisition right. N4, N5, source admission, retention, CAS,
    and the current continuation reader are the existing served test owners.
    """
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.runtime.quality import acquisition_planner, generation_cycle
    from polisyos.runtime.quality import acquisition_retained_continuation as retained_owner
    from polisyos.runtime.quality.acquisition_evaluation import (
        persist_acquisition_evaluation_artifact,
    )
    from polisyos.runtime.quality.acquisition_planner import (
        AcquisitionStrategy,
        bind_acquisition_planner_report,
        persist_and_verify_acquisition_planner_report,
    )
    from polisyos.runtime.quality.acquisition_retained_continuation import (
        AcquisitionRetainedContinuation,
    )
    from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_hash
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
    )

    monkeypatch.setattr(generation_cycle, "_N7_SOURCE_SEMANTIC_EMISSION_ENABLED", True)
    monkeypatch.setitem(
        acquisition_planner._ACQUISITION_GAP_BASIS,
        "fixture.retained_family",
        {
            "basis_ref": "fixture-only:retained-source-join-cost:v1",
            "collection_mode": "Fixture-only retained acquisition costing input",
            "expert_hours": 1,
            "calendar_days": 1,
        },
    )
    original_retention = GenerationCycleController._retained_configured_cheap_continuation
    original_ground = generation_cycle.PolicyGroundingPort.__call__

    def fixture_grounding(self: Any, *, candidate: Any, problem: Any, **kwargs: Any) -> Any:
        original_ground(self, candidate=candidate, problem=problem, **kwargs)
        return generation_cycle._grounding_unavailable(
            candidate.candidate_id,
            issue_codes=("acquire_data:fixture.retained_family",),
            candidate_content_hash=candidate.atom.content_hash,
            design_problem_ref=generation_cycle._problem_ref(problem),
            authority_level=problem.authority_profile.requested_authority_level,
        )

    def scoped_fixture_retention(self: Any, *args: Any, **kwargs: Any) -> Any:
        with monkeypatch.context() as local:
            local.setattr(generation_cycle.PolicyGroundingPort, "__call__", fixture_grounding)
            return original_retention(self, *args, **kwargs)

    monkeypatch.setattr(
        GenerationCycleController,
        "_retained_configured_cheap_continuation",
        scoped_fixture_retention,
    )
    checked: list[str] = []

    def verify_retained(**inputs: Any) -> None:
        ctx = inputs["ctx"]
        _negative, positive = inputs["issue_equal_source"]()
        terminal = positive.receipt
        assert terminal.terminal_outcome == "source_admitted_evaluation_retained"
        assert terminal.current_continuation_ref is not None
        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            store, events = control._artifact_store, control._diagnostic_event_log
            fresh = FileSystemCAS(store.root, ownership_enforced=True)
            decision = fixture._within_fixture_owner(
                read_acquisition_evaluation_artifact,
                store=fresh,
                event_log=events,
                ref=terminal.evaluation_decision_ref,
                record_type=AcquisitionEvaluationDecision,
            )

            def reopen(ref: ArtifactRef, selected_terminal: Any = terminal) -> Any:
                return fixture._within_fixture_owner(
                    read_acquisition_retained_continuation,
                    store=fresh,
                    event_log=events,
                    ref=ref,
                    decision=decision,
                    terminal=selected_terminal,
                )

            continuation = reopen(terminal.current_continuation_ref)
            projection = continuation.current_projection
            gap = projection.grounding.acquisition_requirement
            report = projection.current_planner_report
            planner_inputs = projection.current_planner_inputs
            assert gap is not None and report is not None and planner_inputs is not None
            assert gap.metadata["issue_codes"] == ["acquire_data:fixture.retained_family"]
            request = projection.revision_request.strategy_payload["acquisition_request"]
            assert request["driver"] == "acquire_data:fixture.retained_family"
            assert request["n7_source_driver_rule"] == "policyos.runtime.n7_source_driver.v1"
            source_rows = tuple(
                row
                for row in report.acquisition_records
                if row.requirement_gap_ref == gap.requirement_gap_id
            )
            assert len(source_rows) == 1
            source_row = source_rows[0]
            assert source_row.compiled_requirement_ref != gap.compiled_requirement_ref
            assert report.requirement_basis_binding is not None
            assert planner_inputs.acquisition_request["n7_source_join_rule"] == (
                "policyos.runtime.n7_source_compiler_join.v1"
            )
            compiler_ref = report.requirement_basis_binding.compiler_report_ref

            # Keep the same selected source and compiler IDs while corrupting
            # the real compiler blob. A fresh reader must reject and recover.
            blob, _ = store._paths(compiler_ref.artifact_id)
            original_bytes = blob.read_bytes()
            try:
                blob.write_bytes(b"{}")
                with pytest.raises((OSError, RuntimeError, ValueError)):
                    reopen(terminal.current_continuation_ref)
            finally:
                blob.write_bytes(original_bytes)
            assert reopen(terminal.current_continuation_ref) == continuation

            # A separate owner-written control keeps source/compiler refs and
            # current planner inputs but changes the actual routed strategy.
            # Rebind and persist the report and continuation through their
            # owners, so the semantic check, not marker presence, is decisive.
            wrong_strategy = (
                AcquisitionStrategy.AGENCY_REQUEST
                if source_row.recommended_strategy is not AcquisitionStrategy.AGENCY_REQUEST
                else AcquisitionStrategy.PUBLIC_REGISTRY
            )
            altered_rows = tuple(
                row.model_copy(
                    update={
                        "requirement_schema_version": "policyos.data_requirement_spec.v1",
                        "recommended_strategy": wrong_strategy,
                    }
                )
                if row is source_row
                else row
                for row in report.acquisition_records
            )
            assert report.planning_context_hash is not None
            altered_report = bind_acquisition_planner_report(
                report.model_copy(update={"acquisition_records": altered_rows}),
                planning_context_hash=report.planning_context_hash,
            )
            altered_report_ref = fixture._within_fixture_owner(
                persist_and_verify_acquisition_planner_report,
                store,
                altered_report,
            )
            altered_projection = projection.model_copy(
                update={
                    "current_planner_report": altered_report,
                    "current_planner_report_ref": altered_report_ref,
                }
            )
            altered_payload = continuation.model_dump(mode="json", exclude={"content_hash"})
            altered_payload["current_projection"] = altered_projection.model_dump(mode="json")
            altered_continuation = AcquisitionRetainedContinuation.model_validate(
                {**altered_payload, "content_hash": exact_n5_content_hash(altered_payload)}
            )
            altered_ref = fixture._within_fixture_owner(
                persist_acquisition_evaluation_artifact,
                store=store,
                event_log=events,
                record=altered_continuation,
            )
            altered_terminal = terminal.model_copy(update={"current_continuation_ref": altered_ref})
            with pytest.raises(ValueError, match="acquisition_retained_source_projection_mismatch"):
                reopen(altered_ref, altered_terminal)
            real_join = retained_owner._n7_joined_planner_records_match
            with monkeypatch.context() as local:
                local.setattr(retained_owner, "_n7_joined_planner_records_match", lambda **_: True)
                assert reopen(altered_ref, altered_terminal) == altered_continuation
            assert retained_owner._n7_joined_planner_records_match is real_join
            with pytest.raises(ValueError, match="acquisition_retained_source_projection_mismatch"):
                reopen(altered_ref, altered_terminal)
            assert reopen(terminal.current_continuation_ref) == continuation

            # Removing the planner-input version and recomputing its real
            # binding must not relabel the independently replayed new revision
            # as an old compiler-family projection.
            downgraded_request = dict(planner_inputs.acquisition_request)
            downgraded_request.pop("n7_source_join_rule")
            downgraded_inputs = planner_inputs.model_copy(
                update={"acquisition_request": downgraded_request}
            )
            downgraded_report = bind_acquisition_planner_report(
                report, planning_context_hash=downgraded_inputs.planner_content_hash()
            )
            downgraded_report_ref = fixture._within_fixture_owner(
                persist_and_verify_acquisition_planner_report, store, downgraded_report
            )
            downgraded_projection = projection.model_copy(
                update={
                    "current_planner_report": downgraded_report,
                    "current_planner_report_ref": downgraded_report_ref,
                    "current_planner_inputs": downgraded_inputs,
                }
            )
            downgraded_payload = continuation.model_dump(mode="json", exclude={"content_hash"})
            downgraded_payload["current_projection"] = downgraded_projection.model_dump(mode="json")
            downgraded = AcquisitionRetainedContinuation.model_validate(
                {**downgraded_payload, "content_hash": exact_n5_content_hash(downgraded_payload)}
            )
            downgraded_ref = fixture._within_fixture_owner(
                persist_acquisition_evaluation_artifact,
                store=store,
                event_log=events,
                record=downgraded,
            )
            downgraded_terminal = terminal.model_copy(
                update={"current_continuation_ref": downgraded_ref}
            )
            with pytest.raises(ValueError, match="acquisition_retained_source_join_rule_mismatch"):
                reopen(downgraded_ref, downgraded_terminal)
            assert reopen(terminal.current_continuation_ref) == continuation
            checked.append("persisted_join_and_removal")

    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "candidate-source", include_owner_slot_manifest=True
    )
    with _OwnerCallMonitor() as monitor:
        oracle = _SequentialOracle(monkeypatch, monitor, after_real_b=verify_retained)
        result = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            sequential_oracle=oracle,
            provider_mode="synthetic_settled_candidate",
        )
    assert result is not None and checked == ["persisted_join_and_removal"]
