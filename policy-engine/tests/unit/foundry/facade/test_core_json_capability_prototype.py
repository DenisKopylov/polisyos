from __future__ import annotations

from decimal import Decimal

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry._artifact_capabilities import resolve_core_json_profile_store
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.http.resilience import (
    BlockingDependencyGuard,
    CircuitBreaker,
    CircuitBreakerConfig,
    GuardedDependencyProxy,
)


class _BaseStoreWithoutRawManifestReader:
    """Expose the generic owner operations while withholding Core profile bytes."""

    def __init__(self, target: FileSystemCAS) -> None:
        self._target = target

    def __getattr__(self, name: str) -> object:
        if name == "get_raw_manifest_bytes":
            raise AttributeError(name)
        return getattr(self._target, name)


def _compile_request(store: FileSystemCAS) -> CompileRequest:
    registry = build_default_registry_bundle(store)
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="capability_probe", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="capability_probe",
            interventions=[
                InterventionSpec(
                    intervention_id="tax_cut",
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
            model_id="capability_probe",
            data_snapshot_ref="sha256:0000000000000000000000000000000000000000000000000000000000000000",
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    policy_ref = store.put_json(
        bundle,
        PutOptions(
            kind=TrinityBundle.ARTIFACT_KIND,
            media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                version=TrinityBundle.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )
    return CompileRequest(
        input_kind="trinity",
        policy_ref=policy_ref,
        registry_bundle_ref=registry.bundle_ref,
    )


def test_foundry_compile_and_execute_use_guarded_owner_profile_reads(tmp_path, monkeypatch) -> None:
    owner = FileSystemCAS(tmp_path / "guarded-foundry-cas")
    request = _compile_request(owner)
    guard = BlockingDependencyGuard(
        dependency_name="foundry-core-json-prototype",
        timeout_seconds=2.0,
        breaker=CircuitBreaker(
            "foundry-core-json-prototype",
            CircuitBreakerConfig(min_throughput=1),
        ),
    )
    try:
        guarded_store = GuardedDependencyProxy(target=owner, guard=guard)
        adapted_guarded_store = CoreToIRArtifactStoreAdapter(store=guarded_store)
        assert adapted_guarded_store.store is guarded_store
        assert resolve_core_json_profile_store(adapted_guarded_store) is guarded_store
        result = compile_foundry(adapted_guarded_store, request)
        assert result.ok is True
        assert result.exec_plan_ref is not None

        registry_ref = request.registry_bundle_ref
        assert registry_ref is not None
        snapshot_ref = put_state_snapshot(
            owner,
            state=GlobalState.empty(n_agents=2, n_firms=1),
            step=0,
        )
        state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)
        data_snapshot_ref = owner.put_json(
            DataSnapshot(data_ref=state_snapshot_ref),
            PutOptions(
                kind=DataSnapshot.ARTIFACT_KIND,
                media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                    version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
                ),
            ),
        )
        bindings_ref = owner.put_json(
            FoundryInputBindings(
                data_snapshot_ref=data_snapshot_ref,
                registry_bundle_ref=registry_ref,
                rules=[],
                bound_state_snapshot_ref=state_snapshot_ref,
            ),
            PutOptions(
                kind=FoundryInputBindings.ARTIFACT_KIND,
                media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                    version=FoundryInputBindings.ARTIFACT_SCHEMA_VERSION,
                ),
            ),
        )
        execute_request = ExecuteRequest(
            exec_plan_ref=result.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=bindings_ref.artifact_id),
            registry_bundle_ref=registry_ref,
        )
        execution = execute_foundry(adapted_guarded_store, execute_request)
        assert execution.ok is True
        assert execution.simulation_result_ref is not None

        class _CoreToIRArtifactStoreAdapterSubclass(CoreToIRArtifactStoreAdapter):
            pass

        subclass_store = _CoreToIRArtifactStoreAdapterSubclass(store=guarded_store)
        assert resolve_core_json_profile_store(subclass_store) is subclass_store
        subclass_compile = compile_foundry(subclass_store, request)
        assert subclass_compile.ok is True
        assert subclass_compile.exec_plan_ref is not None
        subclass_execute_request = ExecuteRequest(
            exec_plan_ref=subclass_compile.exec_plan_ref,
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=bindings_ref.artifact_id),
            registry_bundle_ref=registry_ref,
        )
        subclass_execution = execute_foundry(subclass_store, subclass_execute_request)
        assert subclass_execution.ok is True
        assert subclass_execution.simulation_result_ref is not None

        base_store = _BaseStoreWithoutRawManifestReader(owner)
        nonconforming_subclass = _CoreToIRArtifactStoreAdapterSubclass(store=base_store)
        assert resolve_core_json_profile_store(nonconforming_subclass) is nonconforming_subclass
        subclass_failure = compile_foundry(nonconforming_subclass, request)
        assert subclass_failure.ok is False
        assert subclass_failure.exec_plan_ref is None
        assert subclass_failure.compile_report_ref is not None
        assert any(
            "canon_profile_raw_manifest_unavailable" in note for note in subclass_failure.notes
        )
        failure_report = validate_core_model_json_artifact(
            CompileReport,
            owner,
            subclass_failure.compile_report_ref,
        )
        assert failure_report.ok is False
        with pytest.raises(
            CanonicalProfileRefusalError,
            match="canon_profile_raw_manifest_unavailable",
        ):
            execute_foundry(nonconforming_subclass, subclass_execute_request)
        assert resolve_core_json_profile_store(base_store) is None
        with pytest.raises(
            CanonicalProfileRefusalError,
            match="canon_profile_raw_manifest_unavailable",
        ):
            execute_foundry(base_store, execute_request)

        owner_raw_reader = owner.get_raw_manifest_bytes
        selected_bindings_id = str(bindings_ref.artifact_id)

        def false_bindings_raw_reader(selector, *, manifest_profile_sha256=None):
            selected_id = str(getattr(selector, "artifact_id", selector))
            if selected_id == selected_bindings_id:
                return b'{"canon":null}'
            return owner_raw_reader(
                selector,
                manifest_profile_sha256=manifest_profile_sha256,
            )

        monkeypatch.setattr(owner, "get_raw_manifest_bytes", false_bindings_raw_reader)
        with pytest.raises(
            CanonicalProfileRefusalError,
            match="canon_profile_invalid",
        ):
            execute_foundry(adapted_guarded_store, execute_request)
    finally:
        guard.close()


def test_compile_persists_failure_report_for_basic_store(tmp_path) -> None:
    owner = FileSystemCAS(tmp_path / "basic-foundry-cas")
    request = _compile_request(owner)

    result = compile_foundry(_BaseStoreWithoutRawManifestReader(owner), request)

    assert result.ok is False
    assert result.exec_plan_ref is None
    assert result.compile_report_ref is not None
    assert any("canon_profile_raw_manifest_unavailable" in note for note in result.notes)
    report = validate_core_model_json_artifact(CompileReport, owner, result.compile_report_ref)
    assert report.ok is False


def test_compile_does_not_treat_present_but_invalid_raw_profile_as_authority(
    tmp_path, monkeypatch
) -> None:
    owner = FileSystemCAS(tmp_path / "false-profile-foundry-cas")
    request = _compile_request(owner)
    selected_policy_id = str(request.policy_ref.artifact_id)
    owner_raw_reader = owner.get_raw_manifest_bytes

    def false_raw_reader(selector, *, manifest_profile_sha256=None):
        selected_id = str(getattr(selector, "artifact_id", selector))
        if selected_id == selected_policy_id:
            return b'{"canon":null}'
        return owner_raw_reader(
            selector,
            manifest_profile_sha256=manifest_profile_sha256,
        )

    monkeypatch.setattr(owner, "get_raw_manifest_bytes", false_raw_reader)

    result = compile_foundry(owner, request)

    assert result.ok is False
    assert result.exec_plan_ref is None
    assert result.compile_report_ref is not None
    assert any("canon_profile_invalid" in note for note in result.notes)
    report = validate_core_model_json_artifact(CompileReport, owner, result.compile_report_ref)
    assert report.ok is False
