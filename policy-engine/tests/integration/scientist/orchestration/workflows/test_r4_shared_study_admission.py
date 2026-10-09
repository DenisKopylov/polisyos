"""Exercise configured process admission on concurrent Runtime MethodJobs.

The parent test runs one native child process per profile because the canonical
shared executor is process-scoped and deliberately refuses a second capacity.
It uses the existing internal control-job enqueue path with a typed Scientist
state payload; the served ``WorkflowRunRequest`` does not expose arbitrary HTE
method inputs. The actual ControlWorker, RunLifecycle, ``run_experiment``,
builder, causal node, ``run_job``, MethodBackend, dispatcher, TMLE folds, and CAS
writes remain production implementations.
"""

from __future__ import annotations

import contextvars
import json
import os
import subprocess
import sys
import threading
import uuid
from collections import Counter
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from polisyos.common import async_tools
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.control import PolicyFlags
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.contracts.foundry import StateSnapshotRef
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.catalog.causal import HTEObservationalData
from polisyos.foundry.methods.catalog.causal.treatment_effects import TMLEEstimator
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.http.execution_policy import RuntimePrincipal
from polisyos.scientist.compute import runner as compute_runner
from polisyos.scientist.nodes.builtins import state_keys

_REPO_ROOT = Path(__file__).resolve().parents[5]
_TENANT_IDS = (
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
)
_CELL_IDS = ("cell-a", "cell-b")
_PRINCIPALS = tuple(
    RuntimePrincipal(
        subject=f"r4-native-workload-fixture-{study_index}",
        authenticated=True,
        tenant_id=tenant_id,
        cell_id=_CELL_IDS[study_index],
        roles=frozenset({"analyst"}),
    )
    for study_index, tenant_id in enumerate(_TENANT_IDS)
)
_METHOD_PARAMS: dict[str, Any] = {
    "propensity_backend": "logistic",
    "outcome_backend": "linear",
    "calibration_mode": "none",
    "outcome_scaling": "raw",
    "crossfit_folds": 3,
    "n_repeats": 2,
    "random_seed": 18,
    "random_seed_manifest": [18, 1015],
    "ci_mode": "wald",
    "coverage_guard": "off",
    "inference_profile": "regular_iid",
    "parallel_folds": False,
    "max_parallel_folds": 1,
}


def _owner_scope_observation(
    store: FileSystemCAS,
    artifact_id: Any,
    *,
    tenant_id: str,
    cell_id: str,
) -> dict[str, Any]:
    """Summarize owner claims without copying tenant or cell identifiers."""
    owner_rows = store._ownership_index.owners_for(artifact_id)
    admitted_owner = any(
        row.get("tenant_id") == tenant_id and row.get("cell_id") == cell_id for row in owner_rows
    )
    return {
        "claim_count": len(owner_rows),
        "matches_admitted_scope": admitted_owner,
        "scope_class": (
            "admitted_scope" if admitted_owner else "other_scope" if owner_rows else "unowned"
        ),
    }


def _run_child(
    capacity: int,
    *,
    temp_root: Path,
    bypass: bool = False,
) -> dict[str, Any]:
    """Run the two-study native witness in one isolated Runtime process."""
    import importlib

    from tests._helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    revision = f"r4-native-method-cap-{capacity}-v1"
    expected_profile = async_tools.SharedExecutorProfile(
        capacity=capacity,
        revision=revision,
    )
    envs = [
        build_runtime_api_env(
            temp_root / f"runtime-{study_index}",
            include_test_client=True,
            app_kwargs={
                "process_worker_capacity": capacity,
                "process_worker_profile_revision": revision,
            },
        )
        for study_index in range(2)
    ]
    try:
        apps = [env["app"] for env in envs]
        clients = [env["client"] for env in envs]
        assert all(client is not None for client in clients)
        with ExitStack() as runtime_context:
            for client in clients:
                runtime_context.enter_context(client)
            services = [app.state._control_service for app in apps]
            containers = [app.state.runtime_container for app in apps]
            assert all(
                container.config.shared_executor_profile() == expected_profile
                for container in containers
            )
            assert async_tools.get_shared_executor_profile() == expected_profile
            workers = [service._worker for service in services]
            assert all(worker is not None for worker in workers)
            for worker in workers:
                worker.stop()

            physical_executor = async_tools.get_shared_executor()
            assert physical_executor._max_workers == capacity
            worker_ids: set[int] = set()
            worker_ids_lock = threading.Lock()
            ready = threading.Barrier(capacity)

            def identify_shared_worker() -> int:
                thread_id = threading.get_ident()
                with worker_ids_lock:
                    worker_ids.add(thread_id)
                ready.wait(timeout=10)
                return thread_id

            calibration = [
                physical_executor.submit(identify_shared_worker) for _ in range(capacity)
            ]
            [future.result(timeout=10) for future in calibration]
            assert len(worker_ids) == capacity

            runtime_inputs: dict[int, dict[str, Any]] = {}
            for study_index, service in enumerate(services):
                with tenant_scope(
                    None,
                    tenant_id=_TENANT_IDS[study_index],
                    cell_id=_CELL_IDS[study_index],
                ):
                    registry_bundle = build_default_registry_bundle(service._artifact_store)
                    state_snapshot = put_state_snapshot(
                        service._artifact_store,
                        state=GlobalState.empty(n_agents=5, n_firms=2),
                        step=0,
                    )
                    snapshot_ref = service._artifact_store.put_json(
                        DataSnapshot(
                            data_ref=StateSnapshotRef(artifact_id=state_snapshot.artifact_id)
                        ),
                        PutOptions(
                            kind="fabric.data_snapshot",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.core.DataSnapshot",
                                version="0.1.0",
                            ),
                        ),
                    )
                    data_snapshot_ref = DataSnapshotRef(artifact_id=snapshot_ref.artifact_id)
                    trinity_bundle = TrinityBundle(
                        problem_frame=ProblemFrame(
                            problem_id="r4_native_workload",
                            domain=ProblemDomain.FISCAL,
                        ),
                        policy_spec=PolicySpec(
                            policy_id="r4_native_workload",
                            interventions=[
                                InterventionSpec(
                                    intervention_id="r4_tax_change",
                                    kind="income_tax",
                                    target={
                                        "kind": "predicate",
                                        "field": "id",
                                        "operator": SelectorOperator.EQUALS,
                                        "value": "all",
                                    },
                                    schedule={"start_step": 0, "duration_steps": 1},
                                    params={"rate": Decimal("0.1")},
                                )
                            ],
                        ),
                        model_spec=ModelSpec(
                            model_id="r4_native_workload",
                            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
                            registry_bundle_ref=str(registry_bundle.bundle_ref.artifact_id),
                        ),
                    )
                    trinity_ref = service._artifact_store.put_json(
                        trinity_bundle,
                        PutOptions(
                            kind="ir.trinity_bundle",
                            media_type="application/json",
                            schema=SchemaInfo(
                                name="polisyos.ir.TrinityBundle",
                                version=trinity_bundle.schema_version,
                            ),
                        ),
                    )
                    rng = np.random.default_rng(811 + study_index)
                    n_obs = 240
                    covariates = rng.normal(size=(n_obs, 2))
                    treatment = rng.binomial(1, 0.5, size=n_obs).astype(float)
                    outcome = (
                        0.45 * treatment
                        + 0.25 * covariates[:, 0]
                        - 0.15 * covariates[:, 1]
                        + rng.normal(0.0, 0.7, size=n_obs)
                    )
                    observations = HTEObservationalData(
                        outcome=outcome,
                        treatment=treatment,
                        covariates=covariates,
                        feature_names=["x0", "x1"],
                        sample_ids=np.arange(n_obs),
                    )
                    data_ref = service._artifact_store.put_json(
                        observations.model_dump(mode="json"),
                        ArtifactWriteOptions(
                            kind="ir.observational_data",
                            media_type="application/json",
                        ),
                        canon_spec=CanonSpec(forbid_floats=False),
                    )
                    runtime_inputs[study_index] = {
                        "registry_bundle": registry_bundle,
                        "snapshot_ref": snapshot_ref,
                        "trinity_ref": trinity_ref,
                        "data_ref": data_ref,
                    }

            from polisyos.foundry.methods.catalog.causal import tmle_core
            from polisyos.scientist import api as scientist_api

            causal_node = importlib.import_module(
                "polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation"
            )
            # The Runtime endpoint in this slice accepts generic workflow data
            # bindings, while evaluation admission is an independently owned
            # gate. Bypass only that gate so this integration test isolates
            # aggregate MethodJob admission; the result stays legacy-shadow and
            # candidate-only. No safety or promotion claim is tested here.
            causal_gate = causal_node._causal_evaluation_safety_blockers
            causal_node._causal_evaluation_safety_blockers = lambda *_a, **_k: ()

            original_run_experiment = scientist_api.run_experiment
            from polisyos.scientist.orchestration.engine.state import ExperimentState

            active_study: contextvars.ContextVar[int | None] = contextvars.ContextVar(
                "r4_active_native_study",
                default=None,
            )
            final_states: dict[int, dict[str, Any]] = {}
            causal_node_outcomes: dict[int, Any] = {}
            method_results: dict[int, dict[str, Any]] = {}
            producer_lock = threading.Lock()
            producer_entries = 0
            producer_active = 0
            producer_peak = 0
            method_backend_entries = 0
            original_method_backend_run = compute_runner.MethodBackend.run

            def target_method(kwargs: Mapping[str, Any]) -> bool:
                method_class = kwargs.get("method_class")
                signature = getattr(method_class, "signature", None)
                fqn = str(getattr(signature, "fqn", "")).split("@", 1)[0]
                return fqn == TMLEEstimator.signature.fqn.split("@", 1)[0]

            original_causal_execute = causal_node.RunCausalEvaluationNode.execute

            def observed_causal_execute(node: Any, ctx: Any, state: Any) -> Any:
                outcome = original_causal_execute(node, ctx, state)
                study_index = int(state.params["r4_study_index"])
                causal_node_outcomes[study_index] = outcome
                return outcome

            causal_node.RunCausalEvaluationNode.execute = observed_causal_execute

            def observed_method_backend_run(
                backend: compute_runner.MethodBackend,
                **kwargs: Any,
            ) -> Any:
                nonlocal method_backend_entries
                if (kwargs.get("method_fqn") or "").split("@", 1)[0] == (
                    TMLEEstimator.signature.fqn.split("@", 1)[0]
                ):
                    with producer_lock:
                        method_backend_entries += 1
                result = original_method_backend_run(backend, **kwargs)
                if (kwargs.get("method_fqn") or "").split("@", 1)[0] == (
                    TMLEEstimator.signature.fqn.split("@", 1)[0]
                ):
                    study_index = active_study.get()
                    assert study_index is not None
                    artifacts = result.exec_artifacts
                    method_results[study_index] = {
                        "result_ref": artifacts.result_ref,
                        "evidence_ref": artifacts.evidence_ref,
                        "result": result.final_state,
                    }
                return result

            compute_runner.MethodBackend.run = observed_method_backend_run

            def observed_run_experiment(
                state: Mapping[str, Any] | ExperimentState,
                **kwargs: Any,
            ) -> dict[str, Any]:
                nonlocal producer_entries, producer_active, producer_peak
                payload = (
                    state.model_dump(mode="json")
                    if isinstance(state, ExperimentState)
                    else dict(state)
                )
                typed_state = ExperimentState.model_validate(payload)
                study_index = int(typed_state.params["r4_study_index"])
                with producer_lock:
                    producer_entries += 1
                    producer_active += 1
                    producer_peak = max(producer_peak, producer_active)
                token = active_study.set(study_index)
                try:
                    result = original_run_experiment(state, **kwargs)
                finally:
                    active_study.reset(token)
                    with producer_lock:
                        producer_active -= 1
                final_states[study_index] = result
                return result

            scientist_api.run_experiment = observed_run_experiment

            dispatcher = MethodDispatcher.get_instance()
            original_dispatch = dispatcher.dispatch
            submission_lock = threading.Lock()
            submit_count = 0
            both_submitted = threading.Event()
            both_dispatches_waiting = threading.Event()
            release_dispatches = threading.Event()
            active_lock = threading.Lock()
            dispatch_active = 0
            dispatch_peak = 0
            dispatch_rows: list[dict[str, int]] = []
            fold_rows: list[tuple[int, int, int]] = []
            submit_active = 0
            submit_peak = 0

            def observed_dispatch(**kwargs: Any) -> Any:
                nonlocal dispatch_active, dispatch_peak
                if not target_method(kwargs):
                    return original_dispatch(**kwargs)
                study_index = active_study.get()
                assert study_index is not None, "TMLE dispatch lost its submitted context"
                with active_lock:
                    dispatch_active += 1
                    dispatch_peak = max(dispatch_peak, dispatch_active)
                    dispatch_rows.append({"study": study_index, "thread_id": threading.get_ident()})
                    if dispatch_active == 2:
                        both_dispatches_waiting.set()
                try:
                    if capacity == 1 and not bypass:
                        # Do not make the only worker wait for a second call.
                        # The call-level counter below records whether another
                        # producer reached the shared executor while this one ran.
                        pass
                    else:
                        assert release_dispatches.wait(timeout=60), (
                            "dispatch release was not signaled after observing both producers"
                        )
                    return original_dispatch(**kwargs)
                finally:
                    with active_lock:
                        dispatch_active -= 1

            dispatcher.dispatch = observed_dispatch

            original_submit = compute_runner.run_shared_executor_sync

            def observed_submit(func: Any, /, *args: Any, **kwargs: Any) -> Any:
                nonlocal submit_count, submit_active, submit_peak
                is_tmle = target_method(kwargs)
                if is_tmle:
                    assert active_study.get() is not None
                    with submission_lock:
                        submit_count += 1
                        submit_active += 1
                        submit_peak = max(submit_peak, submit_active)
                        if submit_count == 2:
                            both_submitted.set()
                    if bypass:
                        try:
                            return func(*args, **kwargs)
                        finally:
                            with submission_lock:
                                submit_active -= 1
                try:
                    return original_submit(func, *args, **kwargs)
                finally:
                    if is_tmle:
                        with submission_lock:
                            submit_active -= 1

            compute_runner.run_shared_executor_sync = observed_submit
            original_fold = tmle_core._fit_crossfit_fold

            def observed_fold(**kwargs: Any) -> dict[str, Any]:
                study_index = active_study.get()
                assert study_index is not None, "TMLE fold lost its submitted context"
                fold_rows.append(
                    (
                        study_index,
                        int(kwargs["rep_seed"]),
                        int(kwargs["fold_id"]),
                    )
                )
                return original_fold(**kwargs)

            tmle_core._fit_crossfit_fold = observed_fold

            try:
                launches: dict[int, Any] = {}
                study_profiles: dict[int, dict[str, Any]] = {}
                from polisyos.core.run.context import new_run_id

                for study_index in range(2):
                    with tenant_scope(
                        None,
                        tenant_id=_TENANT_IDS[study_index],
                        cell_id=_CELL_IDS[study_index],
                    ):
                        service = services[study_index]
                        inputs = runtime_inputs[study_index]
                        seed = 18 + study_index
                        method_params = dict(_METHOD_PARAMS)
                        method_params["random_seed"] = seed
                        method_params["random_seed_manifest"] = [seed, seed + 997]
                        study_profiles[study_index] = method_params
                        run_id = new_run_id()
                        job_id = uuid.uuid4().hex
                        policy = service._resolve_execution_policy(
                            requested_profile="dev",
                            policy_flags=PolicyFlags(),
                            principal=_PRINCIPALS[study_index],
                        )
                        state_payload = {
                            "run_id": run_id,
                            "inputs": {
                                "data_snapshot_ref": inputs["snapshot_ref"].model_dump(mode="json"),
                                "registry_bundle_ref": inputs[
                                    "registry_bundle"
                                ].bundle_ref.model_dump(mode="json"),
                                "trinity_bundle_ref": inputs["trinity_ref"].model_dump(mode="json"),
                            },
                            "params": {
                                "control_plane_transition": "legacy_shadow",
                                "workflow_id": "scientist_default",
                                "r4_study_index": study_index,
                                "random_seed": seed,
                                "causal_method_params": method_params,
                            },
                            "observational_data_ref": inputs["data_ref"].model_dump(mode="json"),
                            "causal_method_fqn": TMLEEstimator.signature.fqn,
                            "causal_method_params": method_params,
                        }
                        launches[study_index] = service._enqueue_job(
                            job_id=job_id,
                            job_kind="workflow_run",
                            run_id=run_id,
                            pipeline_id=None,
                            payload={
                                "run_id": run_id,
                                "state_payload": state_payload,
                                "checkpoint_policy": "strict",
                            },
                            policy=policy,
                        )
                futures_by_study: dict[int, Any] = {}
                with ThreadPoolExecutor(max_workers=2) as control_threads:
                    futures_by_study = {
                        study_index: control_threads.submit(workers[study_index].dispatch_once)
                        for study_index in range(2)
                    }
                    pre_dispatch_release: dict[str, Any] | None = None
                    if capacity > 1 or bypass:
                        assert both_submitted.wait(timeout=60), (
                            f"both competing studies did not submit to MethodBackend; "
                            f"producer_entries={producer_entries}, "
                            f"method_backend_entries={method_backend_entries}, "
                            f"submissions={submit_count}, dispatches={dispatch_rows}"
                        )
                        with producer_lock:
                            observed_producers = producer_entries
                            observed_methods = method_backend_entries
                        with submission_lock:
                            observed_submissions = submit_count
                        assert observed_producers == observed_methods == observed_submissions == 2
                        assert both_dispatches_waiting.wait(timeout=60), (
                            "both real MethodDispatcher calls did not reach the shared admission point"
                        )
                        with active_lock:
                            observed_dispatches = len(dispatch_rows)
                            observed_dispatch_active = dispatch_active
                        pre_dispatch_release = {
                            "run_experiment_entries": observed_producers,
                            "method_backend_entries": observed_methods,
                            "submit_count": observed_submissions,
                            "dispatch_entries": observed_dispatches,
                            "dispatch_active": observed_dispatch_active,
                            "control_futures_done": [
                                futures_by_study[study_index].done() for study_index in range(2)
                            ],
                        }
                        assert observed_dispatches == observed_dispatch_active == 2
                        assert pre_dispatch_release["control_futures_done"] == [False, False]
                        release_dispatches.set()
                    dispatched = [
                        futures_by_study[study_index].result(timeout=120)
                        for study_index in range(2)
                    ]
                assert dispatched == [True, True]

                terminal_jobs = []
                for study_index, launch in launches.items():
                    with tenant_scope(
                        None,
                        tenant_id=_TENANT_IDS[study_index],
                        cell_id=_CELL_IDS[study_index],
                    ):
                        terminal_jobs.append(
                            services[study_index]._control_store.get_job(launch.job_id)
                        )
                assert all(job is not None and job.state == "completed" for job in terminal_jobs), (
                    "control jobs failed before complete result readback; "
                    f"jobs={[None if job is None else (job.job_id, job.state, job.error_message) for job in terminal_jobs]}, "
                    f"producer_entries={producer_entries}, "
                    f"method_backend_entries={method_backend_entries}, "
                    f"submissions={submit_count}, causal_nodes="
                    f"{[(study, outcome.status, getattr(outcome.error, 'message', None)) for study, outcome in causal_node_outcomes.items()]}"
                )

                study_outputs: dict[str, Any] = {}
                for study_index, state in final_states.items():
                    with tenant_scope(
                        None,
                        tenant_id=_TENANT_IDS[study_index],
                        cell_id=_CELL_IDS[study_index],
                    ):
                        fresh_store = FileSystemCAS(
                            Path(envs[study_index]["cas_root"])
                        ).with_ambient_ownership_enforcement()
                        node_outcome = causal_node_outcomes[study_index]
                        artifacts_index = state["artifacts_index"]
                        ref_payload = artifacts_index.get(
                            state_keys.ARTIFACT_CAUSAL_METHOD_RESULT_REF
                        )
                        state_linked = ref_payload is not None
                        if ref_payload is None:
                            assert study_index in method_results, (
                                f"causal result missing from final state and MethodBackend "
                                f"receipt; artifacts={sorted(artifacts_index)}, "
                                f"params={sorted(state.get('params', {}))}"
                            )
                            ref_payload = method_results[study_index]["result_ref"]
                        ref = ArtifactRef.model_validate(ref_payload)
                        saved = from_canonical_bytes(fresh_store.get_bytes(ref))
                        assert isinstance(saved, dict)
                        result_manifest = fresh_store.get_manifest(ref)
                        input_data_ref = runtime_inputs[study_index]["data_ref"]
                        assert any(
                            str(source.artifact_id) == str(input_data_ref.artifact_id)
                            and source.role == "input:causal_observational_data"
                            for source in result_manifest.inputs
                        )
                        evidence_ref = method_results[study_index]["evidence_ref"]
                        evidence = from_canonical_bytes(fresh_store.get_bytes(evidence_ref))
                        assert isinstance(evidence, dict)
                        assert (
                            evidence.get("method_fqn", "").split("@", 1)[0]
                            == (TMLEEstimator.signature.fqn.split("@", 1)[0])
                        )
                        evidence_manifest = fresh_store.get_manifest(evidence_ref)
                        assert any(
                            str(source.artifact_id) == str(ref.artifact_id)
                            and source.role == "method_result"
                            for source in evidence_manifest.inputs
                        )

                        input_owner_scope = _owner_scope_observation(
                            fresh_store,
                            input_data_ref.artifact_id,
                            tenant_id=_TENANT_IDS[study_index],
                            cell_id=_CELL_IDS[study_index],
                        )
                        result_owner_scope = _owner_scope_observation(
                            fresh_store,
                            ref.artifact_id,
                            tenant_id=_TENANT_IDS[study_index],
                            cell_id=_CELL_IDS[study_index],
                        )
                        evidence_owner_scope = _owner_scope_observation(
                            fresh_store,
                            evidence_ref.artifact_id,
                            tenant_id=_TENANT_IDS[study_index],
                            cell_id=_CELL_IDS[study_index],
                        )
                        result = saved["result"]
                        declared_profile = study_profiles[study_index]
                        repeat_seeds = declared_profile["random_seed_manifest"]
                        fold_count = declared_profile["crossfit_folds"]
                        repeat_count = declared_profile["n_repeats"]
                        expected_study_folds = {
                            (int(repeat_seeds[repeat]), fold)
                            for repeat in range(repeat_count)
                            for fold in range(fold_count)
                        }
                        observed_study_folds = [
                            (fold_seed, fold)
                            for study, fold_seed, fold in fold_rows
                            if study == study_index
                        ]
                        assert set(observed_study_folds) == expected_study_folds
                        assert len(observed_study_folds) == len(expected_study_folds)
                        numerical = {
                            "result": result,
                            "report": saved["report"],
                            "envelope": saved["envelope"],
                            "executed_folds": [
                                {"seed": fold_seed, "fold": fold}
                                for fold_seed, fold in sorted(observed_study_folds)
                            ],
                        }
                        evidence_state_payload = artifacts_index.get(
                            state_keys.ARTIFACT_CAUSAL_METHOD_EVIDENCE_REF
                        )
                        study_outputs[str(study_index)] = {
                            "result_ref": str(ref.artifact_id),
                            "evidence_ref": str(evidence_ref.artifact_id),
                            "input_owner_scope": input_owner_scope,
                            "result_owner_scope": result_owner_scope,
                            "evidence_owner_scope": evidence_owner_scope,
                            "state_linked": state_linked,
                            "evidence_state_linked": (
                                evidence_state_payload is not None
                                and ArtifactRef.model_validate(evidence_state_payload)
                                == evidence_ref
                            ),
                            "causal_node_status": node_outcome.status,
                            "causal_node_error": (
                                node_outcome.error.message
                                if node_outcome.error is not None
                                else None
                            ),
                            "numerical": numerical,
                        }

                expected_folds = {
                    (
                        study_index,
                        int(study_profiles[study_index]["random_seed_manifest"][repeat]),
                        fold,
                    )
                    for study_index in range(2)
                    for repeat in range(study_profiles[study_index]["n_repeats"])
                    for fold in range(study_profiles[study_index]["crossfit_folds"])
                }
                observed_counts = Counter(fold_rows)
                assert set(observed_counts) == expected_folds
                assert set(observed_counts.values()) == {1}
                assert len(dispatch_rows) == 2
                owner_dispatch_count = sum(row["thread_id"] in worker_ids for row in dispatch_rows)
                if bypass:
                    assert dispatch_peak == 2
                    assert owner_dispatch_count == 0
                else:
                    assert dispatch_peak == capacity
                    assert owner_dispatch_count == 2

                results = {
                    "capacity": capacity,
                    "profile_revision": revision,
                    "source": "candidate_configured_runtime_profile",
                    "dispatch_peak": dispatch_peak,
                    "dispatches_on_shared_workers": owner_dispatch_count,
                    "dispatch_count": len(dispatch_rows),
                    "run_experiment_entries": producer_entries,
                    "run_experiment_peak_active": producer_peak,
                    "method_backend_entries": method_backend_entries,
                    "submit_count": submit_count,
                    "submit_peak_active": submit_peak,
                    "expected_fold_count": len(expected_folds),
                    "observed_fold_count": len(fold_rows),
                    "completed_jobs": len(terminal_jobs),
                    "control_worker_results": dispatched,
                    "pre_dispatch_release": pre_dispatch_release,
                    "study_outputs": study_outputs,
                    "bypass": bypass,
                }
            finally:
                compute_runner.run_shared_executor_sync = original_submit
                compute_runner.MethodBackend.run = original_method_backend_run
                dispatcher.dispatch = original_dispatch
                tmle_core._fit_crossfit_fold = original_fold
                scientist_api.run_experiment = original_run_experiment
                causal_node.RunCausalEvaluationNode.execute = original_causal_execute
                causal_node._causal_evaluation_safety_blockers = causal_gate

        return results
    finally:
        for env in reversed(envs):
            close_runtime_api_env(env)


def test_r4_native_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run one profile child and emit its complete machine-readable receipt."""
    if os.environ.get("POLISYOS_R4_CHILD") != "1":
        pytest.skip("invoked only by the R4 profile parent")
    capacity = int(os.environ["POLISYOS_R4_CAPACITY"])
    bypass = os.environ.get("POLISYOS_R4_BYPASS") == "1"
    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    result = _run_child(capacity, temp_root=tmp_path, bypass=bypass)
    print("R4_NATIVE_RESULT=" + json.dumps(result, sort_keys=True, allow_nan=False), flush=True)


def _invoke_child(*, capacity: int, bypass: bool = False) -> dict[str, Any]:
    child_env = dict(os.environ)
    child_env.update(
        {
            "POLISYOS_R4_CHILD": "1",
            "POLISYOS_R4_CAPACITY": str(capacity),
            "POLISYOS_R4_BYPASS": "1" if bypass else "0",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "POLISYOS_EXECUTION_PROFILE": "dev",
            "POLISYOS_RUNNER_BACKEND": "local",
            "LOG_LEVEL": "WARNING",
        }
    )
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-s",
                "tests/integration/scientist/orchestration/workflows/"
                "test_r4_shared_study_admission.py::test_r4_native_child",
            ],
            cwd=_REPO_ROOT,
            env=child_env,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        _retain_child_output(
            capacity=capacity,
            bypass=bypass,
            stdout=exc.stdout,
            stderr=exc.stderr,
        )
        raise
    _retain_child_output(
        capacity=capacity,
        bypass=bypass,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    marker = "R4_NATIVE_RESULT="
    payloads = [
        line[len(marker) :] for line in completed.stdout.splitlines() if line.startswith(marker)
    ]
    assert completed.returncode == 0 and len(payloads) == 1, (
        f"R4 child cap={capacity} bypass={bypass} failed ({completed.returncode})\n"
        f"stdout tail:\n{_diagnostic_tail(completed.stdout)}\n"
        f"stderr tail:\n{_diagnostic_tail(completed.stderr)}"
    )
    result = json.loads(payloads[0])
    assert isinstance(result, dict)
    return result


def _retain_child_output(
    *,
    capacity: int,
    bypass: bool,
    stdout: str | bytes | None,
    stderr: str | bytes | None,
) -> None:
    """Persist complete native child output before any parent assertion."""
    receipt_directory = os.environ.get("POLISYOS_R4_RECEIPT_DIR")
    if not receipt_directory:
        return
    directory = Path(receipt_directory)
    directory.mkdir(parents=True, exist_ok=True)
    profile = "removal" if bypass else "configured"
    stem = f"cap-{capacity}-{profile}"
    for stream_name, output in (("stdout", stdout), ("stderr", stderr)):
        content = (
            output.decode("utf-8", errors="replace") if isinstance(output, bytes) else output or ""
        )
        (directory / f"{stem}.{stream_name}.txt").write_text(content, encoding="utf-8")


def _diagnostic_tail(output: str, *, limit: int = 80) -> str:
    """Keep failure reports readable while preserving route diagnostics."""
    lines = output.splitlines()
    relevant = [
        line
        for line in lines
        if any(
            marker in line
            for marker in (
                "R4_NATIVE_RESULT=",
                "Traceback",
                "AssertionError",
                "Error:",
                "error:",
                "FAILED",
                "Control worker",
                "control job",
                "legacy_workflow",
            )
        )
    ]
    return "\n".join(relevant[-limit:] if relevant else lines[-limit:])


def test_r4_child_output_retention_writes_full_timeout_streams(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    receipt_directory = tmp_path / "receipts"
    monkeypatch.setenv("POLISYOS_R4_RECEIPT_DIR", str(receipt_directory))

    _retain_child_output(
        capacity=2,
        bypass=True,
        stdout=b"full partial child stdout\n",
        stderr=b"full partial child stderr\n",
    )

    assert (receipt_directory / "cap-2-removal.stdout.txt").read_text() == (
        "full partial child stdout\n"
    )
    assert (receipt_directory / "cap-2-removal.stderr.txt").read_text() == (
        "full partial child stderr\n"
    )


def test_runtime_control_worker_shared_method_admission_and_removal_probe() -> None:
    """Measure cap 1/2, preserve results, and prove bridge removal escapes the cap."""
    cap_one = _invoke_child(capacity=1)
    if os.environ.get("POLISYOS_R4_CAP1_DIAGNOSTIC_ONLY") == "1":
        print("R4_NATIVE_CAP1_DIAGNOSTIC=" + json.dumps(cap_one, sort_keys=True), flush=True)
        assert cap_one["capacity"] == 1
        assert cap_one["source"] == "candidate_configured_runtime_profile"
        assert cap_one["profile_revision"] == "r4-native-method-cap-1-v1"
        assert cap_one["completed_jobs"] == 2
        assert cap_one["control_worker_results"] == [True, True]
        assert cap_one["run_experiment_entries"] == 2
        assert cap_one["run_experiment_peak_active"] == 2
        assert cap_one["method_backend_entries"] == cap_one["submit_count"] == 2
        assert cap_one["submit_peak_active"] == 2
        assert cap_one["dispatch_count"] == 2
        assert cap_one["dispatch_peak"] == 1
        assert cap_one["dispatches_on_shared_workers"] == 2
        assert cap_one["expected_fold_count"] == cap_one["observed_fold_count"] == 12
        assert set(cap_one["study_outputs"]) == {"0", "1"}
        for study_index, output in cap_one["study_outputs"].items():
            assert output["causal_node_status"] == "ok", (
                f"study {study_index} causal node failed: {output['causal_node_error']}"
            )
            assert output["causal_node_error"] is None
            assert output["input_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["result_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["evidence_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["state_linked"]
            assert output["evidence_state_linked"]
        return
    cap_two = _invoke_child(capacity=2)
    no_bridge = _invoke_child(capacity=1, bypass=True)
    print(
        "R4_NATIVE_PROFILES="
        + json.dumps(
            {"cap_one": cap_one, "cap_two": cap_two, "no_bridge": no_bridge},
            sort_keys=True,
            allow_nan=False,
        ),
        flush=True,
    )

    assert cap_one["dispatch_peak"] == 1
    assert cap_two["dispatch_peak"] == 2
    assert cap_one["expected_fold_count"] == cap_one["observed_fold_count"] == 12
    assert cap_two["expected_fold_count"] == cap_two["observed_fold_count"] == 12
    assert cap_one["completed_jobs"] == cap_two["completed_jobs"] == 2
    for profile in (cap_one, cap_two):
        for study_index, output in profile["study_outputs"].items():
            assert output["causal_node_status"] == "ok", (
                f"study {study_index} causal node failed: {output['causal_node_error']}"
            )
            assert output["causal_node_error"] is None
            assert output["input_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["result_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["evidence_owner_scope"]["scope_class"] == "admitted_scope"
            assert output["state_linked"]
            assert output["evidence_state_linked"]
    assert all(output["state_linked"] for output in cap_one["study_outputs"].values()), (
        "cap-1 MethodBackend CAS results were not projected into final Scientist state: "
        + json.dumps(cap_one["study_outputs"], sort_keys=True)
    )
    assert all(output["state_linked"] for output in cap_two["study_outputs"].values()), (
        "cap-2 MethodBackend CAS results were not projected into final Scientist state: "
        + json.dumps(cap_two["study_outputs"], sort_keys=True)
    )
    assert cap_one["study_outputs"] == cap_two["study_outputs"]

    assert no_bridge["capacity"] == 1
    assert no_bridge["dispatch_peak"] == 2
    assert no_bridge["dispatches_on_shared_workers"] == 0
    assert no_bridge["expected_fold_count"] == no_bridge["observed_fold_count"] == 12
    assert no_bridge["completed_jobs"] == 2
