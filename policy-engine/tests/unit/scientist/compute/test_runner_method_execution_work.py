from __future__ import annotations

import gc
import threading
import weakref
from contextvars import ContextVar
from dataclasses import fields
from typing import Any

import numpy as np
import pytest

from polisyos.common import async_tools
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.runtime import ObservationalInputResourcePolicy
from polisyos.foundry.methods import ComputeBackend, MethodRegistry, MethodSignature
from polisyos.foundry.methods.backends.protocol import (
    MethodResult,
    MethodTiming,
    ReproducibilityInfo,
)
from polisyos.foundry.methods.catalog.causal._common import wrap_causal_output
from polisyos.foundry.methods.catalog.causal.forest_dr import ForestDRLearnerEstimator
from polisyos.foundry.methods.catalog.causal.protocols import HTEObservationalData
from polisyos.ir.analytics.causal import CausalEffectReport, CausalMethod
from polisyos.ir.analytics.hte import HTEResult
from polisyos.ir.observation.bundles import ContractCompatibilityTarget
from polisyos.scientist.compute.runner import (
    MethodBackend,
    MethodExecutionRefOutcome,
    MethodExecutionWork,
    MethodMetricProjectionWork,
)

_OWNER_CONTEXT: ContextVar[str | None] = ContextVar("method_execution_owner", default=None)


@pytest.fixture(autouse=True)
def _reset_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


class _FixedDispatcher:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.seen_state = False

    def dispatch(self, **kwargs: Any) -> MethodResult:
        assert kwargs["method_class"] is ForestDRLearnerEstimator
        state = kwargs["state"]
        assert isinstance(state, HTEObservationalData)
        if self.fail:
            raise ValueError("method dispatch failed", state.covariates)
        self.seen_state = True
        return MethodResult(
            output=wrap_causal_output(
                CausalEffectReport(
                    method=CausalMethod.FOREST_DR,
                    estimand="ATE",
                    point_estimate=1.25,
                    confidence_interval=(0.25, 2.25),
                    confidence_level=0.95,
                    standard_error=0.5,
                    inference_method="controlled_test_dispatch",
                    sample_size=40,
                    n_treated=20,
                    n_control=20,
                    pre_periods=0,
                    post_periods=0,
                ),
                extras={
                    "hte_result": HTEResult.from_estimates(
                        method=CausalMethod.FOREST_DR,
                        ate=1.25,
                        ate_ci_lower=0.25,
                        ate_ci_upper=2.25,
                        n_samples=40,
                        n_treated=20,
                        n_control=20,
                        n_features=2,
                        feature_names=["x0", "x1"],
                        cate_values=[1.25] * 40,
                    ),
                },
            ),
            timing=MethodTiming(wall_time_ms=1.0),
            reproducibility=ReproducibilityInfo(
                backend=ComputeBackend.NUMPY,
                determinism_tier=ForestDRLearnerEstimator.determinism_tier,
                seed=9,
            ),
        )


class _Admission:
    derived_tenant_context = None
    protocol = "method_input_envelope_v1"
    method_fqn = ForestDRLearnerEstimator.signature.fqn
    method_version = ForestDRLearnerEstimator.signature.version
    seed = 9
    limits = object()
    method_abi_digest = ForestDRLearnerEstimator.signature.abi_digest()
    method_build_digest = "a" * 64
    resource_policy_digest = "b" * 64

    def __init__(self, store: FileSystemCAS, resource_policy_ref: ArtifactRef) -> None:
        self.store = store
        self.resource_policy_ref = resource_policy_ref
        self.resource_policy = ObservationalInputResourcePolicy()
        self.effective_params = {"alpha": 0.05}


class _AdmissionService:
    def __init__(self, admission: _Admission) -> None:
        self.admission = admission
        self.resolved_refs: tuple[ArtifactRef, ArtifactRef] | None = None
        self.resolved_owner_context: str | None = None
        self.persisted_fields: frozenset[str] = frozenset()

    def resolve_method_execution_admission(self, *, work: MethodExecutionWork) -> _Admission:
        self.resolved_owner_context = _OWNER_CONTEXT.get()
        self.resolved_refs = (
            work.requested_source_ref,
            work.observational_run_intent_ref,
        )
        return self.admission

    def verify_method_registration(
        self,
        admission: _Admission,
        signature: MethodSignature,
        method_class: type,
    ) -> None:
        assert admission is self.admission
        assert signature is ForestDRLearnerEstimator.signature
        assert method_class is ForestDRLearnerEstimator

    def persist_content_admitted_intent(self, **kwargs: Any) -> ArtifactRef:
        self.persisted_fields = frozenset(kwargs)
        assert "prepared_input" not in kwargs
        assert "data" not in kwargs
        assert kwargs["work"].job_id == "job-1"
        return self.admission.store.put_json(
            {"admitted": True},
            ArtifactWriteOptions(
                kind="tests.content_admitted_intent",
                media_type="application/json",
                schema=SchemaInfo(name="tests.ContentAdmittedIntent", version="1"),
            ),
            return_selected_profile=True,
        )


def _put_ref(store: FileSystemCAS, *, kind: str, schema_name: str) -> ArtifactRef:
    return store.put_json(
        {"kind": kind},
        ArtifactWriteOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version="1"),
        ),
        return_selected_profile=True,
    )


def _hte_data(covariates: np.ndarray) -> HTEObservationalData:
    return HTEObservationalData(
        outcome=np.arange(40, dtype=float),
        treatment=np.tile(np.asarray([0, 1], dtype=int), 20),
        covariates=covariates,
    )


def _install_prepared_input(
    monkeypatch: pytest.MonkeyPatch,
    *,
    data: HTEObservationalData,
    input_ref: ArtifactRef,
    payload_integrity_verified: bool = True,
) -> dict[str, object]:
    from polisyos.foundry.data_plane import bindings

    prepared = type(
        "PreparedFixture",
        (),
        {
            "data": data,
            "submitted_ref": input_ref,
            "effective_ref": input_ref,
            "effective_artifact_schema": SchemaInfo(
                name="polisyos.ir.ObservationMethodInputEnvelope",
                version="1.0",
            ),
            "contract_target": ContractCompatibilityTarget(
                contract_id="foundry.causal.hte_observational_data.v1",
                contract_fqn="polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData",
            ),
            "method_fqn": ForestDRLearnerEstimator.signature.fqn,
            "source_protocol": "method_input_envelope_v1",
            "normalization": "canonical_passthrough",
            "limitations": (),
            "source_governance": None,
            "source_tenant_context": None,
            "observed_manifest_bytes": 192,
            "observed_manifest_selection_bytes": 192,
            "observed_manifest_verification_bytes": 64,
            "observed_payload_bytes": 512,
            "observed_source_bytes": 768,
            "payload_integrity_verified": payload_integrity_verified,
            "observed_bytes": 512,
            "observed_depth": 4,
            "observed_elements": 120,
        },
    )()
    holder: dict[str, object] = {"prepared": prepared}

    def prepare(**kwargs: Any) -> object:
        assert kwargs["method_fqn"] == ForestDRLearnerEstimator.signature.fqn
        return holder["prepared"]

    monkeypatch.setattr(bindings, "prepare_hte_observational_input", prepare, raising=False)
    return holder


def _build_backend(
    tmp_path,
    *,
    fail: bool = False,
) -> tuple[MethodBackend, _AdmissionService, _FixedDispatcher, FileSystemCAS, ArtifactRef]:
    registry = MethodRegistry.get_instance()
    registry.register(ForestDRLearnerEstimator, override=True)
    store = FileSystemCAS(tmp_path)
    resource_policy_ref = _put_ref(
        store,
        kind="runtime.observational_input_resource_policy",
        schema_name="polisyos.runtime.ObservationalInputResourcePolicy",
    )
    admission = _Admission(store, resource_policy_ref)
    service = _AdmissionService(admission)
    dispatcher = _FixedDispatcher(fail=fail)
    backend = MethodBackend(
        registry_provider=lambda: registry,
        dispatcher_provider=lambda: dispatcher,
        admission_service=service,
    )
    return backend, service, dispatcher, store, resource_policy_ref


def test_qualified_method_backend_requires_pinned_runtime_registry_provider(
    tmp_path,
) -> None:
    store = FileSystemCAS(tmp_path)
    resource_policy_ref = _put_ref(
        store,
        kind="runtime.observational_input_resource_policy",
        schema_name="polisyos.runtime.ObservationalInputResourcePolicy",
    )
    service = _AdmissionService(_Admission(store, resource_policy_ref))

    with pytest.raises(
        ValueError,
        match="qualified_method_execution_requires_runtime_registry_provider",
    ):
        MethodBackend(admission_service=service)


def _new_work(store: FileSystemCAS) -> tuple[MethodExecutionWork, ArtifactRef, ArtifactRef]:
    source_ref = _put_ref(
        store,
        kind="tests.requested_observation",
        schema_name="tests.RequestedObservation",
    )
    intent_ref = _put_ref(
        store,
        kind="tests.observational_run_intent",
        schema_name="tests.ObservationalRunIntent",
    )
    return (
        MethodExecutionWork(
            job_id="job-1",
            run_id="run-1",
            attempt=1,
            requested_source_ref=source_ref,
            observational_run_intent_ref=intent_ref,
        ),
        source_ref,
        intent_ref,
    )


@pytest.mark.parametrize("field", ["artifact_id", "kind", "media_type", "manifest_profile_sha256"])
def test_method_work_ref_snapshot_rejects_mutable_or_oversized_ref_members(
    tmp_path,
    field: str,
) -> None:
    store = FileSystemCAS(tmp_path)
    source_ref = _put_ref(
        store,
        kind="tests.requested_observation",
        schema_name="tests.RequestedObservation",
    )
    intent_ref = _put_ref(
        store,
        kind="tests.observational_run_intent",
        schema_name="tests.ObservationalRunIntent",
    )
    setattr(source_ref, field, np.ones(100_000, dtype=np.float64))

    with pytest.raises(ValueError, match="full_profile_artifact_refs"):
        MethodExecutionWork(
            job_id="job-1",
            run_id="run-1",
            attempt=1,
            requested_source_ref=source_ref,
            observational_run_intent_ref=intent_ref,
        )


def test_qualified_method_route_keeps_full_worker_lease_and_ref_only_outcome(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend, service, dispatcher, store, _policy_ref = _build_backend(tmp_path)
    work, source_ref, intent_ref = _new_work(store)
    input_ref = _put_ref(
        store,
        kind="tests.effective_method_input",
        schema_name="tests.EffectiveMethodInput",
    )
    _install_prepared_input(
        monkeypatch,
        data=_hte_data(np.ones((40, 2), dtype=float)),
        input_ref=input_ref,
    )

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=1)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    blocker_started = threading.Event()
    release_blocker = threading.Event()
    blocker = executor.submit_cancellable(
        lambda: (blocker_started.set(), release_blocker.wait(timeout=3), "released")[2]
    )
    assert blocker_started.wait(timeout=2)
    try:
        owner_token = _OWNER_CONTEXT.set("tenant-cell-17")
        try:
            handle = backend.submit_method_execution_work(work)
        finally:
            _OWNER_CONTEXT.reset(owner_token)
        # The queued descriptor owns immutable scalar snapshots, not these models.
        source_ref.kind = "tests.mutated_after_enqueue"
        intent_ref.kind = "tests.mutated_after_enqueue"
        release_blocker.set()
        assert blocker.result(timeout=2).value == "released"

        completion = handle.result(timeout=3)
        assert completion.status == "completed"
        outcome = completion.value
        assert type(outcome) is MethodExecutionRefOutcome
        assert outcome is not None
        assert outcome.requested_source_ref.kind == "tests.requested_observation"
        assert outcome.observational_run_intent_ref.kind == "tests.observational_run_intent"
        assert outcome.method_result_ref.manifest_profile_sha256 is not None
        assert outcome.method_evidence_ref.manifest_profile_sha256 is not None
        assert outcome.content_admitted_intent_ref.manifest_profile_sha256 is not None
        assert outcome.method_dispatch_binding_status == "recomputed"
        assert outcome.candidate_outcome is not None
        assert outcome.candidate_outcome.status == "success"
        assert outcome.candidate_outcome.point_estimate == 1.25
        assert service.resolved_refs is not None
        assert service.resolved_refs[0].kind == "tests.requested_observation"
        assert service.resolved_refs[1].kind == "tests.observational_run_intent"
        assert service.resolved_owner_context == "tenant-cell-17"
        assert "observed_bytes" in service.persisted_fields
        assert "observed_manifest_bytes" in service.persisted_fields
        assert "observed_manifest_selection_bytes" in service.persisted_fields
        assert "observed_manifest_verification_bytes" in service.persisted_fields
        assert "observed_payload_bytes" in service.persisted_fields
        assert "observed_source_bytes" in service.persisted_fields
        assert "payload_integrity_verified" in service.persisted_fields
        assert outcome.resource_policy_ref == _policy_ref
        assert dispatcher.seen_state is True

        mutable_view = outcome.method_result_ref
        mutable_view.kind = "tests.local_mutation"
        assert outcome.method_result_ref.kind == "scientist.method_result.causal.hte"
        assert not any(
            isinstance(getattr(outcome, item.name), (np.ndarray, MethodResult))
            for item in fields(outcome)
        )
        persisted_result = from_canonical_bytes(store.get_bytes(outcome.method_result_ref))
        assert persisted_result["report"]["method"] == "forest_dr"
        assert persisted_result["hte_result"]["ate"] == 1.25
        evidence = from_canonical_bytes(store.get_bytes(outcome.method_evidence_ref))
        assert evidence["authority_purpose"] == "method_execution"
        assert evidence["method_abi_digest"] == ForestDRLearnerEstimator.signature.abi_digest()
        assert evidence["method_build_digest_scope"] == "class_source_only"
        assert evidence["resource_policy_digest"] == "b" * 64
        assert evidence["method_dispatch_binding_status"] == "recomputed"
        assert evidence["method_dispatch_binding"]["method_fqn"] == (
            ForestDRLearnerEstimator.signature.fqn
        )
        assert (
            evidence["method_dispatch_binding"]["input_refs"]["hte_data"]["manifest_profile_sha256"]
            == input_ref.manifest_profile_sha256
        )
    finally:
        release_blocker.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_worker_refuses_unverified_payload_before_content_admission(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend, service, dispatcher, store, _policy_ref = _build_backend(tmp_path)
    work, _source_ref, _intent_ref = _new_work(store)
    input_ref = _put_ref(
        store,
        kind="tests.effective_method_input",
        schema_name="tests.EffectiveMethodInput",
    )
    _install_prepared_input(
        monkeypatch,
        data=_hte_data(np.ones((40, 2), dtype=float)),
        input_ref=input_ref,
        payload_integrity_verified=False,
    )

    with pytest.raises(ValueError, match="prepared_hte_payload_integrity_not_verified"):
        backend._execute_method_execution_work(work)

    assert service.persisted_fields == frozenset()
    assert dispatcher.seen_state is False


def test_metric_projection_work_snapshots_all_full_refs_and_supports_graph_none(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    refs = (
        _put_ref(store, kind="tests.method_result", schema_name="tests.MethodResult"),
        _put_ref(store, kind="tests.simulation_result", schema_name="tests.SimulationResult"),
        _put_ref(
            store,
            kind="tests.method_execution_bundle",
            schema_name="tests.MethodExecutionBundle",
        ),
        _put_ref(
            store,
            kind="tests.method_metric_binding_set",
            schema_name="tests.MethodMetricBindingSet",
        ),
    )
    expected = tuple(
        (ref.artifact_id, ref.kind, ref.media_type, ref.manifest_profile_sha256) for ref in refs
    )
    work = MethodMetricProjectionWork(
        job_id="job-1",
        run_id="run-1",
        attempt=1,
        method_result_ref=refs[0],
        simulation_result_ref=refs[1],
        method_execution_bundle_ref=refs[2],
        method_metric_binding_set_ref=refs[3],
    )
    graph_work = MethodMetricProjectionWork(
        job_id="job-2",
        run_id="run-2",
        attempt=1,
        simulation_result_ref=refs[1],
        method_execution_bundle_ref=refs[2],
        method_metric_binding_set_ref=refs[3],
    )
    queued_views = (
        work.method_result_ref,
        work.simulation_result_ref,
        work.method_execution_bundle_ref,
        work.method_metric_binding_set_ref,
    )
    for ref in (*refs, *(view for view in queued_views if view is not None)):
        ref.kind = "tests.mutated_after_enqueue"
        ref.manifest_profile_sha256 = "0" * 64

    actual = (
        work.method_result_ref,
        work.simulation_result_ref,
        work.method_execution_bundle_ref,
        work.method_metric_binding_set_ref,
    )
    assert (
        tuple(
            (ref.artifact_id, ref.kind, ref.media_type, ref.manifest_profile_sha256)
            for ref in actual
            if ref is not None
        )
        == expected
    )
    assert graph_work.method_result_ref is None
    assert graph_work.simulation_result_ref.kind == "tests.simulation_result"
    assert graph_work.simulation_result_ref.manifest_profile_sha256 == expected[1][3]


def test_metric_projection_route_uses_shared_slot_and_preserves_owner_context(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import sys
    from types import ModuleType

    store = FileSystemCAS(tmp_path)
    refs = (
        _put_ref(store, kind="tests.simulation_result", schema_name="tests.SimulationResult"),
        _put_ref(
            store,
            kind="tests.method_execution_bundle",
            schema_name="tests.MethodExecutionBundle",
        ),
        _put_ref(
            store,
            kind="tests.method_metric_binding_set",
            schema_name="tests.MethodMetricBindingSet",
        ),
    )
    work = MethodMetricProjectionWork(
        job_id="job-1",
        run_id="run-1",
        attempt=1,
        simulation_result_ref=refs[0],
        method_execution_bundle_ref=refs[1],
        method_metric_binding_set_ref=refs[2],
    )
    outcome_type = type(
        "MethodMetricProjectionRefOutcomeFixture",
        (),
        {"status": "verification_missing", "admission": None, "limitations": ()},
    )
    outcome = outcome_type()
    helper_started = threading.Event()
    release_helper = threading.Event()
    observed_owner: list[str | None] = []
    observed_resolver: list[object] = []

    def prepare(*, work: MethodMetricProjectionWork, resolver: object) -> object:
        assert type(work) is MethodMetricProjectionWork
        assert work.method_result_ref is None
        assert work.simulation_result_ref.manifest_profile_sha256 is not None
        assert work.method_execution_bundle_ref.manifest_profile_sha256 is not None
        assert work.method_metric_binding_set_ref.manifest_profile_sha256 is not None
        observed_resolver.append(resolver)
        assert resolver.resolve_method_metric_projection_store(work=work) is store
        helper_started.set()
        release_helper.wait(timeout=3)
        return outcome

    module = ModuleType("polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics")
    module.MethodMetricProjectionRefOutcome = outcome_type
    module.prepare_method_metric_projection_work = prepare
    monkeypatch.setitem(
        sys.modules,
        "polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics",
        module,
    )

    class _Resolver:
        def resolve_method_metric_projection_store(
            self,
            *,
            work: MethodMetricProjectionWork,
        ) -> FileSystemCAS:
            assert type(work) is MethodMetricProjectionWork
            observed_owner.append(_OWNER_CONTEXT.get())
            return store

    resolver = _Resolver()
    backend = MethodBackend(metric_projection_service=resolver)
    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    try:
        owner_token = _OWNER_CONTEXT.set("tenant-cell-17")
        try:
            handle = backend.submit_method_metric_projection_work(work)
        finally:
            _OWNER_CONTEXT.reset(owner_token)
        refs[0].kind = "tests.mutated_after_enqueue"
        assert helper_started.wait(timeout=2)
        with pytest.raises(async_tools.SharedExecutorWaitTimeoutError) as raised:
            handle.result(timeout=0.01)
        assert raised.value.running_slot_retained is True
        assert raised.value.retryable is False
        with pytest.raises(async_tools.SharedExecutorBackpressureError):
            backend.submit_method_metric_projection_work(work)
        release_helper.set()
        completion = handle.result(timeout=2)
        assert completion.status == "completed"
        assert completion.value is outcome
        assert observed_owner == ["tenant-cell-17"]
        assert observed_resolver == [resolver]
        assert work.simulation_result_ref.kind == "tests.simulation_result"
    finally:
        release_helper.set()
        executor.shutdown(wait=True, cancel_futures=True)


def test_qualified_dispatch_fingerprint_tracks_consumed_values_not_only_selected_ref(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend, _service, _dispatcher, store, _policy_ref = _build_backend(tmp_path)
    input_ref = _put_ref(
        store,
        kind="tests.effective_method_input",
        schema_name="tests.EffectiveMethodInput",
    )
    work_one, _source_one, _intent_one = _new_work(store)
    work_two, _source_two, _intent_two = _new_work(store)
    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    try:
        _install_prepared_input(
            monkeypatch,
            data=_hte_data(np.ones((40, 2), dtype=float)),
            input_ref=input_ref,
        )
        first = backend.submit_method_execution_work(work_one).result(timeout=3)
        assert first.status == "completed"
        assert first.value is not None

        _install_prepared_input(
            monkeypatch,
            data=_hte_data(np.zeros((40, 2), dtype=float)),
            input_ref=input_ref,
        )
        second = backend.submit_method_execution_work(work_two).result(timeout=3)
        assert second.status == "completed"
        assert second.value is not None

        first_evidence = from_canonical_bytes(store.get_bytes(first.value.method_evidence_ref))
        second_evidence = from_canonical_bytes(store.get_bytes(second.value.method_evidence_ref))
        first_binding = first_evidence["method_dispatch_binding"]
        second_binding = second_evidence["method_dispatch_binding"]
        assert (
            first_binding["input_refs"]["hte_data"]["manifest_profile_sha256"]
            == (second_binding["input_refs"]["hte_data"]["manifest_profile_sha256"])
        )
        assert (
            first_binding["input_state_fingerprints"]["hte_data"]
            != (second_binding["input_state_fingerprints"]["hte_data"])
        )
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_qualified_method_failure_drops_input_arrays_and_exception_frames(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend, _service, _dispatcher, store, _policy_ref = _build_backend(tmp_path, fail=True)
    work, _source_ref, _intent_ref = _new_work(store)
    input_ref = _put_ref(
        store,
        kind="tests.effective_method_input",
        schema_name="tests.EffectiveMethodInput",
    )
    covariates = np.ones((40, 20_000), dtype=float)
    covariates_ref = weakref.ref(covariates)
    prepared_holder = _install_prepared_input(
        monkeypatch,
        data=_hte_data(covariates),
        input_ref=input_ref,
    )

    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    try:
        handle = backend.submit_method_execution_work(work)
        del covariates
        completion = handle.result(timeout=3)
        assert completion.status == "failed"
        assert completion.failure is not None
        assert completion.failure.exception_type.endswith("ValueError")
        assert completion.failure.message_excerpt == "method dispatch failed"
        prepared_holder.clear()
        gc.collect()
        assert covariates_ref() is None
    finally:
        executor.shutdown(wait=True, cancel_futures=True)


def test_running_qualified_wait_timeout_keeps_slot_through_output_persistence(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend, _service, _dispatcher, store, _policy_ref = _build_backend(tmp_path)
    work, _source_ref, _intent_ref = _new_work(store)
    input_ref = _put_ref(
        store,
        kind="tests.effective_method_input",
        schema_name="tests.EffectiveMethodInput",
    )
    _install_prepared_input(
        monkeypatch,
        data=_hte_data(np.ones((40, 2), dtype=float)),
        input_ref=input_ref,
    )
    entered_result_write = threading.Event()
    resume_result_write = threading.Event()
    original_put_json = store.put_json

    def block_result_persistence(
        payload: object,
        options: ArtifactWriteOptions,
        **kwargs: Any,
    ) -> ArtifactRef:
        if options.kind.startswith("scientist.method_result."):
            entered_result_write.set()
            resume_result_write.wait(timeout=3)
        return original_put_json(payload, options, **kwargs)

    monkeypatch.setattr(store, "put_json", block_result_persistence)
    executor = async_tools._SharedExecutor(max_workers=1, max_queued=0)
    monkeypatch.setattr(async_tools, "_get_shared_executor", lambda: executor)
    handle = backend.submit_method_execution_work(work)
    assert entered_result_write.wait(timeout=2)
    try:
        with pytest.raises(async_tools.SharedExecutorWaitTimeoutError) as raised:
            handle.result(timeout=0.01)
        assert raised.value.running_slot_retained is True
        assert raised.value.retryable is False
        with pytest.raises(async_tools.SharedExecutorBackpressureError) as saturated:
            backend.submit_method_execution_work(work)
        assert saturated.value.retryable is True
    finally:
        resume_result_write.set()
        executor.shutdown(wait=True, cancel_futures=True)
