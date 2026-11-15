"""Actual annual source and tensor replay before temporal method execution."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import numpy as np
import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
)
from polisyos.core.contracts import (
    FoundryInputBindings,
    SemanticHorizonStepContext,
    load_model_input_obligation_set,
    load_native_derivation_source_projection,
    load_registered_derived_input_correspondence,
    load_resolved_input_binding_manifest,
)
from polisyos.foundry.data_plane.bindings import (
    build_input_bindings,
    load_input_bindings,
    prepare_input_bindings,
    reconcile_selected_method_input_bindings,
    reconcile_semantic_input_bindings,
    replay_selected_method_input_step_facts,
)
from polisyos.foundry.execute import put_state_snapshot
from polisyos.foundry.execute._internal.models import put_tensor
from polisyos.runtime.quality.model_input_step_materialization import (
    prepare_registered_derived_model_input_steps,
)
from tests._helpers.temporal_registered_method_inputs import (
    prepare_temporal_registered_method_inputs,
)
from tests.unit.foundry.data_plane.test_selected_method_input_bindings import (
    _ProfileReaderWithoutVerifier,
    _removed_blob,
)


@pytest.fixture(scope="module")
def _temporal_fixture(tmp_path_factory):
    """Reuse the same real native acquisitions for positive and removal controls."""
    fixture = prepare_temporal_registered_method_inputs(tmp_path_factory.mktemp("selected-steps"))
    try:
        yield fixture
    finally:
        fixture.case.close()


def _independent_scalar_sha256(value: Decimal) -> str:
    array = np.asarray(str(value), dtype=np.float64)
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _build(case, stage):
    return build_input_bindings(
        case.store,
        data_snapshot_ref=stage.data_snapshot_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        resolved_binding_manifest_ref=stage.resolved_binding_manifest_ref,
        return_selected_profile=True,
    )


def _rebuilt_step_record(case, original_ref, bindings, replacement):
    rows = (replacement, *bindings.selected_method_input_steps[1:])
    rebuilt = bindings.model_copy(update={"selected_method_input_steps": rows})
    inputs = [
        edge
        for edge in case.store.get_manifest(original_ref).inputs
        if not edge.role.startswith("method_input.")
    ]
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
    return case.store.put_json(
        rebuilt,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME, version="1.5"),
            inputs=inputs,
        ),
        return_selected_profile=True,
    )


def test_scalar_step_bindings_replay_partial_and_complete_actual_native_values(_temporal_fixture):
    fixture = _temporal_fixture
    case = fixture.case
    selected_set, _ = load_model_input_obligation_set(
        case.store, fixture.preflight.obligation_set_ref
    )
    invocation = selected_set.invocation
    horizon = SemanticHorizonStepContext(
        obligation_set_ref=fixture.preflight.obligation_set_ref,
        steps=invocation.steps,
        step_index=0,
        replication_seed=17,
    )
    partial = prepare_registered_derived_model_input_steps(
        case.store,
        base_data_snapshot_ref=case.data_snapshot_ref,
        obligation_set_ref=fixture.preflight.obligation_set_ref,
        inputs=fixture.requests[:1],
    )
    partial_built = _build(case, partial)
    fresh = FileSystemCAS.open_existing_read_only(case.store.root)
    reader_without_verifier = _ProfileReaderWithoutVerifier(fresh)
    with pytest.raises(ValueError, match=r"^foundry_selected_method_input_reader_not_established$"):
        replay_selected_method_input_step_facts(
            reader_without_verifier,
            input_bindings_ref=partial_built.input_bindings_ref,
            expected_invocation=invocation,
        )
    partial_facts = replay_selected_method_input_step_facts(
        fresh,
        input_bindings_ref=partial_built.input_bindings_ref,
        expected_invocation=invocation,
    )
    assert partial_facts.coverage.missing_step_scopes == (fixture.requests[1].step_scope,)
    assert tuple(partial_facts.values) == (("period_flow", 0),)
    with pytest.raises(ValueError, match="model_input_step_coverage_incomplete"):
        reconcile_selected_method_input_bindings(
            fresh,
            input_bindings_ref=partial_built.input_bindings_ref,
            expected_invocation=invocation,
            effective_step=0,
            semantic_horizon_step=horizon,
        )

    full = prepare_registered_derived_model_input_steps(
        case.store,
        base_data_snapshot_ref=case.data_snapshot_ref,
        obligation_set_ref=fixture.preflight.obligation_set_ref,
        inputs=tuple(reversed(fixture.requests)),
    )
    built = _build(case, full)
    facts = replay_selected_method_input_step_facts(
        fresh, input_bindings_ref=built.input_bindings_ref, expected_invocation=invocation
    )
    assert facts.bindings.schema_version == "1.5"
    assert facts.bindings.selected_method_inputs is None
    assert facts.bindings.bound_state_snapshot_ref == case.bound_state_snapshot_ref
    assert facts.coverage.is_complete
    assert facts.coverage == full.coverage
    assert tuple(facts.values) == (("period_flow", 0), ("period_flow", 1))
    assert facts.records[0].step_scope == partial_facts.records[0].step_scope
    assert facts.records[0].input.canonical_value == Decimal("-6000000000")
    assert facts.records[1].input.canonical_value == Decimal("4200000000")
    for row, expected in zip(facts.records, fixture.spec.rows, strict=True):
        value = facts.values[(row.input.slot_id, row.step_scope.step)]
        assert type(value) is np.ndarray and value.shape == () and value.dtype == np.float64
        assert Decimal(str(value.item())) == expected.expected_flow
        assert row.input.value_sha256 == _independent_scalar_sha256(expected.expected_flow)
        with pytest.raises(ValueError):
            value.setflags(write=True)
    resolved = reconcile_selected_method_input_bindings(
        fresh,
        input_bindings_ref=built.input_bindings_ref,
        expected_invocation=invocation,
        effective_step=0,
        semantic_horizon_step=horizon,
    )
    assert tuple(resolved.values) == ("period_flow",)
    assert tuple(row.canonical_value for row in resolved.records) == (Decimal("-6000000000"),)
    for options in (
        {},
        {"effective_step": 1},
        {"effective_step": 1, "semantic_horizon_step": horizon},
    ):
        with pytest.raises(ValueError, match="step|horizon"):
            reconcile_selected_method_input_bindings(
                fresh,
                input_bindings_ref=built.input_bindings_ref,
                expected_invocation=invocation,
                **options,
            )


def test_step_reader_reopens_every_source_recipe_and_tensor_before_coverage_credit(
    _temporal_fixture,
):
    fixture = _temporal_fixture
    case = fixture.case
    stage = prepare_registered_derived_model_input_steps(
        case.store,
        base_data_snapshot_ref=case.data_snapshot_ref,
        obligation_set_ref=fixture.preflight.obligation_set_ref,
        inputs=fixture.requests,
    )
    built = _build(case, stage)
    fresh = FileSystemCAS.open_existing_read_only(case.store.root)
    selected_set, _ = load_model_input_obligation_set(fresh, fixture.preflight.obligation_set_ref)

    def replay(ref=built.input_bindings_ref):
        return replay_selected_method_input_step_facts(
            fresh, input_bindings_ref=ref, expected_invocation=selected_set.invocation
        )

    facts = replay()
    manifest = load_resolved_input_binding_manifest(fresh, stage.resolved_binding_manifest_ref)
    proof = load_registered_derived_input_correspondence(
        fresh, manifest.method_input_steps[1].selection.correspondence_ref
    )
    projection = load_native_derivation_source_projection(
        fresh, proof.roles[0].source_projection_ref
    )
    refs = (
        facts.records[1].input.npy_value_ref,
        manifest.method_input_steps[1].selection.recipe_ref,
        projection.occurrence_ref,
    )
    for ref in refs:
        with _removed_blob(case.store, ref), pytest.raises((ValueError, OSError)):
            replay()
        assert replay().coverage.is_complete

    bindings = load_input_bindings(case.store, built.input_bindings_ref)
    original = facts.records[0]
    wrong_value = np.asarray(0, dtype=np.float64)
    wrong_ref = put_tensor(
        case.store,
        wrong_value,
        return_selected_profile=True,
        kind="foundry.selected_method_input_value",
        inputs=list(case.store.get_manifest(original.input.npy_value_ref).inputs),
    )
    replacement = original.model_copy(
        update={
            "input": original.input.model_copy(
                update={
                    "npy_value_ref": wrong_ref,
                    "value_sha256": _independent_scalar_sha256(Decimal(0)),
                }
            )
        }
    )
    tampered_ref = _rebuilt_step_record(case, built.input_bindings_ref, bindings, replacement)
    assert artifact_ref_identity_key(tampered_ref) != artifact_ref_identity_key(
        built.input_bindings_ref
    )
    with pytest.raises(ValueError, match="record_source_mismatch"):
        replay(tampered_ref)
    assert replay().coverage.is_complete
    for value in (
        np.asarray(0, dtype=np.float64),
        np.asarray(-6_000_000_000, dtype=np.float32),
        np.asarray([-6_000_000_000], dtype=np.float64),
        np.asarray(np.nan, dtype=np.float64),
    ):
        # Preserve the source-derived record's dtype, shape, Decimal and value
        # hash. The selected NPY has valid CAS bytes and the correct parents;
        # the reader must compare its actual physical facts to that record.
        value_ref = put_tensor(
            case.store,
            value,
            return_selected_profile=True,
            kind="foundry.selected_method_input_value",
            inputs=list(case.store.get_manifest(original.input.npy_value_ref).inputs),
        )
        wrong_physical = original.model_copy(
            update={"input": original.input.model_copy(update={"npy_value_ref": value_ref})}
        )
        wrong_ref = _rebuilt_step_record(case, built.input_bindings_ref, bindings, wrong_physical)
        with pytest.raises(ValueError):
            replay(wrong_ref)
        assert replay().coverage.is_complete


def test_state_only_binding_cannot_launder_a_step_manifest_through_an_identical_state(
    _temporal_fixture,
):
    fixture = _temporal_fixture
    case = fixture.case
    stage = prepare_registered_derived_model_input_steps(
        case.store,
        base_data_snapshot_ref=case.data_snapshot_ref,
        obligation_set_ref=fixture.preflight.obligation_set_ref,
        inputs=fixture.requests,
    )
    prepared = prepare_input_bindings(
        case.store,
        data_snapshot_ref=stage.data_snapshot_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        resolved_binding_manifest_ref=stage.resolved_binding_manifest_ref,
    )
    state_ref = put_state_snapshot(
        case.store,
        state=prepared.materialized_state,
        step=0,
        inputs=[
            input_ref_from_artifact_ref(stage.data_snapshot_ref, role="input.data_snapshot_ref"),
            input_ref_from_artifact_ref(case.registry_bundle_ref, role="input.registry_bundle_ref"),
        ],
        return_selected_profile=True,
    )
    # Deliberate adversary: this is a coherent new state artifact with the
    # exact expected numerical bytes and parents, not a stale-hash proxy. It
    # cannot replace the selected exogenous NPY rows or their coverage gate.
    downgraded = FoundryInputBindings(
        schema_version="1.2",
        data_snapshot_ref=stage.data_snapshot_ref,
        registry_bundle_ref=case.registry_bundle_ref,
        rules=list(prepared.effective_rules),
        bound_state_snapshot_ref=state_ref,
        resolved_binding_manifest_ref=stage.resolved_binding_manifest_ref,
    )
    downgraded_ref = case.store.put_json(
        downgraded,
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME, version="1.2"),
            inputs=[
                input_ref_from_artifact_ref(
                    stage.data_snapshot_ref, role="input.data_snapshot_ref"
                ),
                input_ref_from_artifact_ref(
                    case.registry_bundle_ref, role="input.registry_bundle_ref"
                ),
                input_ref_from_artifact_ref(state_ref, role="artifact.bound_state_snapshot_ref"),
                input_ref_from_artifact_ref(
                    stage.resolved_binding_manifest_ref, role="input.resolved_binding_manifest_ref"
                ),
            ],
        ),
        return_selected_profile=True,
    )
    fresh = FileSystemCAS.open_existing_read_only(case.store.root)
    loaded = load_input_bindings(fresh, downgraded_ref)
    with pytest.raises(ValueError, match="foundry_selected_method_input_binding_ref_required"):
        reconcile_semantic_input_bindings(fresh, loaded)
