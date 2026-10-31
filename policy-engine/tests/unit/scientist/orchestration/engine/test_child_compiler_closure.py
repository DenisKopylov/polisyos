"""Exercise compiler closure on real selected Foundry output and corrupted lineage."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import validate_core_model_json_artifact
from polisyos.core.artifacts.canonical_profile import CoreJsonReadLimits
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    ProducerInfo,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecuteRequest,
    LoweredIR,
    SimulationResult,
    StateDelta,
    StateSnapshot,
)
from polisyos.core.registry import build_default_registry_bundle
from polisyos.foundry._internal.quickstart import prepare_trivial_input_bindings
from polisyos.foundry.data_plane.bindings import load_input_bindings
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.scientist.adapters.foundry_bridge import DefaultFoundryPort
from polisyos.scientist.orchestration.engine.child_compiler_closure import (
    compiler_artifact_children,
)

if TYPE_CHECKING:
    from pathlib import Path


_LIMITS = CoreJsonReadLimits(
    max_bytes=1_000_000, max_depth=100, max_elements=100_000, max_manifest_bytes=1_000_000
)


def _keys(refs):
    return {artifact_ref_identity_key(ref) for ref in refs}


@pytest.fixture(scope="module")
def actual_compilation(tmp_path_factory):
    """Use the selected tiny real Foundry input, compiler and CAS producer graph."""
    store = FileSystemCAS(tmp_path_factory.mktemp("compiler-closure") / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    input_ref = prepare_trivial_input_bindings(
        store, registry.bundle_ref, n_agents=2, n_firms=1, step=0
    )
    data_ref = load_input_bindings(store, input_ref).data_snapshot_ref
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_one", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_one",
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
            model_id="model_one",
            data_snapshot_ref=str(data_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )

    def compile_bundle(value):
        policy = store.put_json(
            value,
            PutOptions(
                kind=TrinityBundle.ARTIFACT_KIND,
                media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(name=TrinityBundle.ARTIFACT_SCHEMA_NAME, version="1.0"),
            ),
            return_selected_profile=True,
        )
        request = CompileRequest(
            policy_ref=policy,
            registry_bundle_ref=registry.bundle_ref,
            return_selected_profile=True,
        )
        return policy, DefaultFoundryPort().compile(store, request)

    policy, result = compile_bundle(bundle)
    assert result.ok, result.notes
    rejected_bundle = bundle.model_copy(deep=True)
    rejected_bundle.policy_spec.interventions[0].params["rate"] = Decimal("2")
    rejected_policy, rejected = compile_bundle(rejected_bundle)
    assert not rejected.ok and rejected.candidate_rejection is not None
    return store, registry.bundle_ref, policy, result, rejected_policy, rejected


def _artifact(result, kind):
    if kind == "compiler.compile_report":
        return result.compile_report_ref
    return next(item.ref for item in result.derived_refs if item.ref.kind == kind)


def _reissue(store, ref, *, inputs=None, value=None, version="changed"):
    manifest = store.get_manifest(ref)
    options = PutOptions(
        kind=manifest.kind,
        media_type=manifest.media_type,
        schema=manifest.artifact_schema,
        producer=ProducerInfo(component="test.compiler.closure", version=version),
        inputs=manifest.inputs if inputs is None else inputs,
        canon=manifest.canon,
    )
    if value is not None:
        return store.put_json(value, options, return_selected_profile=True)
    return store.put_bytes(store.get_bytes(ref), options, return_selected_profile=True)


def test_real_compiler_family_has_complete_selected_immediate_children(actual_compilation) -> None:
    store, registry, policy, result, _, _ = actual_compilation
    children = compiler_artifact_children(store, result.compile_report_ref, limits=_LIMITS)
    assert children is not None
    assert _keys(children) == _keys([policy, registry, *(item.ref for item in result.derived_refs)])
    pending = [result.compile_report_ref]
    visited = set()
    families = set()
    while pending:
        ref = pending.pop()
        key = artifact_ref_identity_key(ref)
        if key in visited:
            continue
        visited.add(key)
        found = compiler_artifact_children(store, ref, limits=_LIMITS)
        if found is None:
            assert ref.kind in {"core.registry_bundle", "ir.trinity_bundle"}
            continue
        families.add(ref.kind)
        assert all(type(child) is ArtifactRef and child.manifest_profile_sha256 for child in found)
        pending.extend(found)
    assert families == {
        "compiler.compile_report",
        "compiler.link_report",
        "foundry.lowered_ir",
        "foundry.lowered_mechanism_payload",
        "foundry.program_graph",
        "foundry.exec_plan",
        "foundry.slot_layout",
        "foundry.treasury_plan",
    }


def test_actual_negative_compile_report_1_1_and_link_report_retain_exact_sources(
    actual_compilation,
) -> None:
    store, registry, _, _, policy, result = actual_compilation
    report = validate_core_model_json_artifact(CompileReport, store, result.compile_report_ref)
    assert report.schema_version == "1.1" and not report.ok
    children = compiler_artifact_children(store, result.compile_report_ref, limits=_LIMITS)
    assert children is not None and report.link_report_ref is not None
    assert _keys(children) == _keys([policy, registry, report.link_report_ref])
    linked = compiler_artifact_children(store, report.link_report_ref, limits=_LIMITS)
    assert linked is not None and _keys(linked) == _keys([policy, registry])
    assert result.exec_plan_ref is None


@pytest.mark.parametrize(
    ("kind", "role"),
    [
        ("compiler.compile_report", "link_report"),
        ("compiler.link_report", "ir"),
        ("foundry.lowered_ir", "effective_params:tax_cut"),
        ("foundry.program_graph", "registry_bundle"),
        ("foundry.exec_plan", "treasury_plan"),
        ("foundry.slot_layout", "program_graph"),
        ("foundry.treasury_plan", "program_graph"),
    ],
)
def test_removing_an_actual_required_compiler_edge_refuses(actual_compilation, kind, role) -> None:
    store, _, _, result, _, _ = actual_compilation
    ref = _artifact(result, kind)
    manifest = store.get_manifest(ref)
    assert sum(edge.role == role for edge in manifest.inputs) == 1
    changed = _reissue(store, ref, inputs=[edge for edge in manifest.inputs if edge.role != role])
    assert changed.artifact_id == ref.artifact_id
    with pytest.raises(ValueError, match="child_compiler_required_input_missing"):
        compiler_artifact_children(store, changed, limits=_LIMITS)


@pytest.mark.parametrize(
    ("kind", "role"),
    [
        ("compiler.compile_report", "ir"),
        ("foundry.lowered_ir", "effective_params:tax_cut"),
        ("foundry.program_graph", "params:tax_cut"),
        ("foundry.exec_plan", "program_graph"),
    ],
)
def test_same_bytes_wrong_selected_child_profile_refuses(actual_compilation, kind, role) -> None:
    store, _, _, result, _, _ = actual_compilation
    ref = _artifact(result, kind)
    manifest = store.get_manifest(ref)
    edge = next(item for item in manifest.inputs if item.role == role)
    from polisyos.core.artifacts.canonical_profile import read_core_input_manifest_profile_bounded

    child = read_core_input_manifest_profile_bounded(
        store, edge, max_manifest_bytes=_LIMITS.max_manifest_bytes
    ).effective_ref
    other = _reissue(store, child, version="foreign-child")
    assert other.artifact_id == child.artifact_id
    assert other.manifest_profile_sha256 != child.manifest_profile_sha256
    changed = _reissue(
        store,
        ref,
        inputs=[
            input_ref_from_artifact_ref(other, role=role) if item.role == role else item
            for item in manifest.inputs
        ],
    )
    with pytest.raises(ValueError, match="child_compiler_payload_input_mismatch"):
        compiler_artifact_children(store, changed, limits=_LIMITS)


@pytest.mark.parametrize("carrier", ["object", "artifact_id", "text", "nonfinite"])
def test_parameter_payload_does_not_hide_a_reference_under_an_arbitrary_name(
    actual_compilation, carrier
) -> None:
    store, _, _, result, _, _ = actual_compilation
    lowered = validate_core_model_json_artifact(
        LoweredIR, store, _artifact(result, "foundry.lowered_ir")
    )
    ref = lowered.mechanisms[0].effective_params_ref
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, ref)
    payload["params"]["opaque"] = {
        "object": {"location": result.exec_plan_ref.model_dump(mode="json")},
        "artifact_id": str(result.exec_plan_ref.artifact_id),
        "text": "not-a-number",
        "nonfinite": "NaN",
    }[carrier]
    changed = _reissue(store, ref, value=payload)
    with pytest.raises(ValueError, match="child_compiler_opaque_value_unsupported"):
        compiler_artifact_children(store, changed, limits=_LIMITS)


def test_parameter_payload_must_reconcile_the_selected_policy_source(actual_compilation) -> None:
    store, _, _, result, _, _ = actual_compilation
    lowered = validate_core_model_json_artifact(
        LoweredIR, store, _artifact(result, "foundry.lowered_ir")
    )
    ref = lowered.mechanisms[0].effective_params_ref
    from polisyos.core.artifacts import load_core_json_artifact

    payload = load_core_json_artifact(store, ref)
    payload["params"]["rate"] = Decimal("0.2")
    changed = _reissue(store, ref, value=payload)
    with pytest.raises(ValueError, match="child_compiler_parameter_source_mismatch"):
        compiler_artifact_children(store, changed, limits=_LIMITS)


def test_unknown_report_field_cannot_hide_an_unwalked_child(actual_compilation) -> None:
    store, _, _, result, _, _ = actual_compilation
    report = validate_core_model_json_artifact(CompileReport, store, result.compile_report_ref)
    value = report.model_dump(mode="python")
    value["unregistered"] = result.exec_plan_ref.model_dump(mode="python")
    changed = _reissue(store, result.compile_report_ref, value=value)
    with pytest.raises(ValueError, match="child_compiler_payload_invalid"):
        compiler_artifact_children(store, changed, limits=_LIMITS)


def test_historical_lowering_is_still_typed_readable_but_cannot_claim_complete_lineage(
    actual_compilation,
) -> None:
    store, _, _, result, _, _ = actual_compilation
    ref = _artifact(result, "foundry.lowered_ir")
    legacy = _reissue(
        store,
        ref,
        inputs=[
            item
            for item in store.get_manifest(ref).inputs
            if item.role in {"ir", "registry_bundle"}
        ],
    )
    assert validate_core_model_json_artifact(LoweredIR, store, legacy).mechanisms
    with pytest.raises(ValueError, match="child_compiler_required_input_missing"):
        compiler_artifact_children(store, legacy, limits=_LIMITS)


def test_unknown_family_is_not_interpreted_as_compiler_closure(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    ref = store.put_json(
        {"ordinary": 1},
        PutOptions(kind="test.unknown", media_type="application/json"),
        return_selected_profile=True,
    )
    assert compiler_artifact_children(store, ref, limits=_LIMITS) is None


@pytest.fixture(scope="module")
def actual_execution(tmp_path_factory):
    """Run the real tiny selected candidate -> compile -> execute path."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.ir.trinity.loaders import persist_trinity_bundle_artifact
    from polisyos.scientist.nodes.builtins.planning.stage_b_projection import (
        persist_stage_b_candidate,
    )
    from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

    backing = FileSystemCAS(tmp_path_factory.mktemp("execution-closure") / "cas")

    class SelectedWrites:
        """Mirror the private child's selected occurrence write contract."""

        def __getattr__(self, name):
            return getattr(backing, name)

        def put_json(self, obj, opts, canon_spec=None, *, return_selected_profile=False):
            return backing.put_json(obj, opts, canon_spec, return_selected_profile=True)

        def put_bytes(self, data, opts, *, return_selected_profile=False):
            return backing.put_bytes(data, opts, return_selected_profile=True)

    store = SelectedWrites()
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    bindings = prepare_trivial_input_bindings(
        store, registry.bundle_ref, n_agents=2, n_firms=1, step=0, agent_income=10.0
    )
    data = load_input_bindings(store, bindings).data_snapshot_ref
    from polisyos.foundry._internal.quickstart import build_trivial_trinity_bundle

    bundle = build_trivial_trinity_bundle(str(registry.bundle_ref.artifact_id))
    bundle = bundle.model_copy(
        update={
            "model_spec": bundle.model_spec.model_copy(
                update={"data_snapshot_ref": str(data.artifact_id)}
            )
        }
    )
    candidate = persist_stage_b_candidate(
        store,
        PolicyCandidateSchema.from_trinity_bundle(bundle, candidate_id="executed_candidate"),
        {"data_snapshot_ref": data, "registry_bundle_ref": registry.bundle_ref},
    )
    policy = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store),
            bundle,
            inputs=[input_ref_from_artifact_ref(candidate, role="policy_candidate")],
        ).model_dump(mode="python")
    )
    port = DefaultFoundryPort()
    compiled = port.compile(
        store,
        CompileRequest(
            policy_ref=policy,
            registry_bundle_ref=registry.bundle_ref,
            return_selected_profile=True,
        ),
    )
    assert compiled.ok, compiled.notes
    request = ExecuteRequest(
        exec_plan_ref=compiled.exec_plan_ref,
        input_bindings_ref=bindings,
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )
    executed = port.execute(store, request)
    assert executed.ok and executed.simulation_result_ref is not None, executed.notes
    return store, compiled, executed, request


def _execution_ref(store, executed, kind):
    if kind == "foundry.simulation_result":
        return executed.simulation_result_ref
    result = validate_core_model_json_artifact(
        SimulationResult, store, executed.simulation_result_ref
    )
    if kind == "foundry.execution_input_basis":
        return result.execution_input_basis_ref
    if kind == "foundry.state_snapshot":
        return result.state_snapshot_ref
    if kind == "foundry.state_blob":
        return validate_core_model_json_artifact(
            StateSnapshot, store, result.state_snapshot_ref
        ).state_ref
    return next(item.ref for item in executed.derived_refs if item.ref.kind == kind)


def test_real_selected_execution_reaches_numeric_arrays_and_exact_source_basis(
    actual_execution,
) -> None:
    from polisyos.foundry.execute.executor import load_state_snapshot

    store, _, executed, _ = actual_execution
    result = validate_core_model_json_artifact(
        SimulationResult, store, executed.simulation_result_ref
    )
    assert result.schema_version == "1.4" and result.execution_source_status == "single_step_basis"
    state = load_state_snapshot(store, snapshot_ref=result.state_snapshot_ref)
    assert state.agents.income.tolist() == [9.0, 9.0]
    assert float(state.government_balance) == 2.0
    pending = [executed.simulation_result_ref, *(item.ref for item in executed.derived_refs)]
    visited, families = set(), set()
    while pending:
        ref = pending.pop()
        key = artifact_ref_identity_key(ref)
        if key in visited:
            continue
        visited.add(key)
        children = compiler_artifact_children(store, ref, limits=_LIMITS)
        if children is None:
            assert ref.kind in {
                "core.registry_bundle",
                "ir.trinity_bundle",
                "scientist.policy_design.candidate",
                "fabric.data_snapshot",
                "foundry.input_bindings",
                "ir.slot_registry",
                "ir.merge_rule_registry",
                "ir.constraint_registry",
                "ir.selector_field_registry",
                "ir.metric_registry",
                "ir.mechanism_registry",
                "ir.units_registry",
                "ir.trust_registry",
            }
            continue
        families.add(ref.kind)
        assert all(
            type(child) is ArtifactRef and child.manifest_profile_sha256 for child in children
        )
        pending.extend(children)
    assert {
        "foundry.simulation_result",
        "foundry.execution_input_basis",
        "foundry.state_snapshot",
        "foundry.state_blob",
        "foundry.patch_value",
        "foundry.state_delta",
        "foundry.metrics",
        "foundry.constraint_report",
        "foundry.welfare_bound_report",
    } <= families


@pytest.mark.parametrize(
    ("kind", "role", "reason"),
    [
        (
            "foundry.simulation_result",
            "execution_input_basis",
            "execution_source_requires_one_execution_input_basis_edge",
        ),
        (
            "foundry.state_snapshot",
            "state_blob",
            "child_compiler_snapshot_reference_contract_unsupported",
        ),
        (
            "foundry.execution_input_basis",
            "basis.source.runtime_registry_bundle",
            "child_compiler_execution_basis_input_mismatch",
        ),
        ("foundry.state_delta", "patch_value", "child_compiler_patch_input_mismatch"),
        ("foundry.metrics", "patch_value", "child_compiler_patch_input_mismatch"),
        (
            "foundry.welfare_bound_report",
            "mechanism_params",
            "child_compiler_required_input_missing",
        ),
    ],
)
def test_removing_one_actual_execution_edge_refuses(actual_execution, kind, role, reason) -> None:
    store, _, executed, _ = actual_execution
    ref = _execution_ref(store, executed, kind)
    inputs = list(store.get_manifest(ref).inputs)
    position = next(index for index, item in enumerate(inputs) if item.role == role)
    del inputs[position]
    changed = _reissue(store, ref, inputs=inputs)
    assert changed.artifact_id == ref.artifact_id
    with pytest.raises(ValueError, match=reason):
        compiler_artifact_children(store, changed, limits=_LIMITS)


def test_actual_patch_role_multiplicity_is_preserved_and_payload_bound(actual_execution) -> None:
    store, _, executed, _ = actual_execution
    ref = _execution_ref(store, executed, "foundry.state_delta")
    delta = validate_core_model_json_artifact(StateDelta, store, ref)
    assert len(delta.ops) >= 2
    declared = [item for item in store.get_manifest(ref).inputs if item.role == "patch_value"]
    assert len(declared) == len(delta.ops)
    children = compiler_artifact_children(store, ref, limits=_LIMITS)
    assert children is not None
    expected = _keys(op.value_ref for op in delta.ops)
    assert expected <= _keys(children)
    wrong = _reissue(store, delta.ops[0].value_ref, version="other-patch-profile")
    inputs = list(store.get_manifest(ref).inputs)
    first = next(index for index, item in enumerate(inputs) if item.role == "patch_value")
    inputs[first] = input_ref_from_artifact_ref(wrong, role="patch_value")
    changed = _reissue(store, ref, inputs=inputs)
    with pytest.raises(ValueError, match="child_compiler_patch_input_mismatch"):
        compiler_artifact_children(store, changed, limits=_LIMITS)


def test_simulation_basis_same_bytes_other_profile_is_not_selected(actual_execution) -> None:
    store, _, executed, _ = actual_execution
    ref = executed.simulation_result_ref
    basis = _execution_ref(store, executed, "foundry.execution_input_basis")
    wrong = _reissue(store, basis, version="other-basis-profile")
    changed = _reissue(
        store,
        ref,
        inputs=[
            input_ref_from_artifact_ref(wrong, role=item.role)
            if item.role == "execution_input_basis"
            else item
            for item in store.get_manifest(ref).inputs
        ],
    )
    with pytest.raises(
        ValueError, match="execution_source_basis_ref_differs_from_exact_result_edge"
    ):
        compiler_artifact_children(store, changed, limits=_LIMITS)


@pytest.mark.parametrize("codec", ["npy", "npz"])
def test_array_codec_cannot_hide_an_artifact_selector_in_a_string_array(
    actual_execution, codec
) -> None:
    from io import BytesIO

    import numpy as np

    store, _, executed, _ = actual_execution
    output = BytesIO()
    value = np.asarray([str(executed.simulation_result_ref.artifact_id)])
    if codec == "npy":
        np.save(output, value, allow_pickle=False)
        kind, media_type = "foundry.patch_value", "application/x-npy"
    else:
        np.savez(output, income=value)
        kind, media_type = "foundry.state_blob", "application/x-npz"
    ref = store.put_bytes(
        output.getvalue(),
        PutOptions(kind=kind, media_type=media_type),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="child_compiler_array_reference_contract_unsupported"):
        compiler_artifact_children(store, ref, limits=_LIMITS)


def test_binary_leaf_uses_bounded_owner_stream_without_json_or_legacy_bytes(
    actual_execution, monkeypatch
) -> None:
    from polisyos.scientist.orchestration.engine import child_compiler_closure as owner

    store, _, executed, _ = actual_execution
    delta = validate_core_model_json_artifact(
        StateDelta, store, _execution_ref(store, executed, "foundry.state_delta")
    )

    def refuse_json(*args, **kwargs):
        raise AssertionError("binary output attempted JSON decoding")

    class BoundedOnly:
        def __getattr__(self, name):
            if name == "get_bytes":
                raise AssertionError("binary output attempted an unbounded legacy read")
            return getattr(store, name)

    monkeypatch.setattr(owner, "read_core_json_artifact_bounded", refuse_json)
    assert compiler_artifact_children(BoundedOnly(), delta.ops[0].value_ref, limits=_LIMITS) == ()


class _MeasuredOwnerReads:
    """Count actual sealed owner transfers, including bounded refusal attempts."""

    def __init__(self, store):
        self.store = store
        self.observed = 0

    def __getattr__(self, name):
        return getattr(self.store, name)

    def _record(self, usage):
        from polisyos.core.artifacts._integrity_ops import _is_artifact_store_read_usage

        assert _is_artifact_store_read_usage(usage)
        assert type(usage.observed_source_bytes) is int
        self.observed += usage.observed_source_bytes

    def _manifest(self, name, *args, **kwargs):
        try:
            result = getattr(self.store, name)(*args, **kwargs)
        except Exception as exc:
            self._record(exc.usage)
            raise
        self._record(result.usage)
        return result

    def read_raw_manifest_bytes_bounded(self, *args, **kwargs):
        return self._manifest("read_raw_manifest_bytes_bounded", *args, **kwargs)

    def read_raw_input_manifest_bytes_bounded(self, *args, **kwargs):
        return self._manifest("read_raw_input_manifest_bytes_bounded", *args, **kwargs)

    def open_member_bounded(self, *args, **kwargs):
        attempt = self.store.open_member_bounded(*args, **kwargs)
        measured = self

        class MeasuredAttempt:
            recorded = False

            @property
            def usage(self):
                return attempt.usage

            def _record_once(self):
                if not self.recorded:
                    measured._record(attempt.usage)
                    self.recorded = True

            def __enter__(self):
                try:
                    return attempt.__enter__()
                except BaseException:
                    self._record_once()
                    raise

            def __exit__(self, *args):
                try:
                    return attempt.__exit__(*args)
                finally:
                    self._record_once()

        return MeasuredAttempt()


@pytest.mark.parametrize("binary", [False, True])
@pytest.mark.parametrize("reopen_reserved", [False, True])
def test_aggregate_budget_bounds_actual_transfers_before_reopen(
    actual_execution, binary, reopen_reserved
) -> None:
    from polisyos.core.artifacts.registry import RegistryBundlePayload
    from polisyos.scientist.orchestration.engine.child_compiler_closure import _ExecutionReader

    store, _, executed, request = actual_execution
    registry = validate_core_model_json_artifact(
        RegistryBundlePayload, store, request.registry_bundle_ref
    )
    ref = (
        _execution_ref(store, executed, "foundry.state_blob") if binary else registry.slot_registry
    )
    manifest_bytes = len(store.get_raw_manifest_bytes(ref))
    payload_bytes = len(store.get_bytes(ref))
    cap = manifest_bytes * (2 if reopen_reserved else 1) + payload_bytes
    measured = _MeasuredOwnerReads(store)
    reader = _ExecutionReader(
        measured,
        CoreJsonReadLimits(
            max_bytes=cap, max_depth=100, max_elements=100_000, max_manifest_bytes=1_000_000
        ),
    )
    if reopen_reserved:
        reader.blob(ref) if binary else reader.view(ref)
        assert measured.observed == cap
    else:
        with pytest.raises(ValueError, match="child_compiler_execution_read_budget_exhausted"):
            reader.blob(ref) if binary else reader.view(ref)
        assert measured.observed == manifest_bytes
    assert measured.observed <= cap
    assert reader.manifest_bytes + reader.payload_bytes == measured.observed


def test_aggregate_budget_remainder_applies_to_next_actual_model(actual_execution) -> None:
    from polisyos.core.artifacts.registry import RegistryBundlePayload
    from polisyos.scientist.orchestration.engine.child_compiler_closure import _ExecutionReader

    store, _, _, request = actual_execution
    registry = validate_core_model_json_artifact(
        RegistryBundlePayload, store, request.registry_bundle_ref
    )
    first, second = registry.slot_registry, registry.mechanism_registry
    first_cost = 2 * len(store.get_raw_manifest_bytes(first)) + len(store.get_bytes(first))
    second_manifest = len(store.get_raw_manifest_bytes(second))
    cap = first_cost + second_manifest + len(store.get_bytes(second))
    measured = _MeasuredOwnerReads(store)
    reader = _ExecutionReader(
        measured,
        CoreJsonReadLimits(
            max_bytes=cap, max_depth=100, max_elements=100_000, max_manifest_bytes=1_000_000
        ),
    )
    reader.view(first)
    with pytest.raises(ValueError, match="child_compiler_execution_read_budget_exhausted"):
        reader.view(second)
    assert measured.observed == first_cost + second_manifest
    assert measured.observed <= cap
    assert reader.manifest_bytes + reader.payload_bytes == measured.observed


def test_constraint_report_payload_version_cannot_drift_under_current_manifest(
    actual_execution,
) -> None:
    from polisyos.core.contracts.foundry import ConstraintReport

    store, _, executed, _ = actual_execution
    ref = _execution_ref(store, executed, "foundry.constraint_report")
    report = validate_core_model_json_artifact(ConstraintReport, store, ref)
    changed = _reissue(store, ref, value=report.model_copy(update={"schema_version": "9.9"}))
    with pytest.raises(ValueError, match="child_compiler_payload_version_mismatch"):
        compiler_artifact_children(store, changed, limits=_LIMITS)
