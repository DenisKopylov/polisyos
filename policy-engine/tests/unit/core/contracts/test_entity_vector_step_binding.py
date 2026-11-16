"""Direct vector selections reuse the canonical origin and coverage predicates."""

from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    artifact_ref_identity_key,
    validate_core_model_json_artifact,
)
from polisyos.core.contracts import model_input_requirements
from polisyos.core.contracts.foundry import (
    ExecPlanRef,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    FoundrySelectedMethodInput,
    FoundrySelectedMethodInputAtStep,
    ProgramGraphRef,
    StateSnapshotRef,
)
from polisyos.core.contracts.model_input_period_steps import ModelInputPeriodStepProfile
from polisyos.core.contracts.model_input_requirements import (
    ModelInputContext,
    ModelInputObligation,
    ModelInputObligationSet,
    ProgramGraphInputDependency,
    ProgramGraphInputInvocation,
)
from polisyos.core.contracts.semantic_input_binding import (
    ResolvedInputBindingManifest,
    ResolvedInputBindingManifestRef,
    load_resolved_input_binding_manifest,
    persist_resolved_input_binding_manifest,
)
from polisyos.core.contracts.semantic_step_binding import recompute_resolved_step_input_coverage
from tests.unit.core.contracts.test_entity_vector_binding import (
    _case,
    _ref,
    _scope,
    _vector_row,
)


def _original_subjects(
    store: FileSystemCAS, monkeypatch: pytest.MonkeyPatch, *, selected_context: str | None = None
):
    """Isolate normalization from the separately tested compiled-model loader.

    Fully typed original subjects replace only that loader. The manifest and
    original predecessor are real selected CAS artifacts. This unit fixture
    does not establish compiled-model preflight, source or physical replay.
    """
    case = _case()
    rows = (_vector_row(case), _vector_row(case, step=1))
    registry_ref = case.args["source_registry_bundle_ref"]
    data_ref = _ref(71, "fabric.data_snapshot")
    state_ref = _ref(72, "foundry.state_snapshot", StateSnapshotRef)
    predecessor_fields = {
        "data_snapshot_ref": data_ref,
        "registry_bundle_ref": registry_ref,
        "bound_state_snapshot_ref": state_ref,
    }
    if selected_context is not None:
        scalar = FoundrySelectedMethodInput(
            model_input_obligation_ref=_ref(76, "runtime.quality.model_input_obligation"),
            binding_id="prior_scalar",
            port_id="prior.scalar",
            slot_id="prior.scalar",
            canonical_value=Decimal(1),
            dtype="float64",
            shape=(),
            npy_value_ref=_ref(
                77, "foundry.selected_method_input_value", media="application/x-npy"
            ),
            value_sha256="c" * 64,
        )
        predecessor_fields["resolved_binding_manifest_ref"] = _ref(
            78, "foundry.resolved_input_binding_manifest", ResolvedInputBindingManifestRef
        )
        if selected_context == "scalar":
            predecessor_fields["schema_version"] = "1.4"
            predecessor_fields["selected_method_inputs"] = (scalar,)
        else:
            predecessor_fields["schema_version"] = "1.5"
            predecessor_fields["selected_method_input_steps"] = (
                FoundrySelectedMethodInputAtStep(
                    step_scope=rows[0].step_scope.model_copy(update={"port_id": scalar.port_id}),
                    input_kind="scalar",
                    input=scalar,
                ),
            )
    predecessor = FoundryInputBindings(**predecessor_fields)
    stored_predecessor = store.put_json(
        predecessor,
        PutOptions(
            kind=predecessor.ARTIFACT_KIND,
            media_type=predecessor.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=predecessor.ARTIFACT_SCHEMA_NAME, version=predecessor.schema_version
            ),
        ),
        return_selected_profile=True,
    )
    predecessor_ref = FoundryInputBindingsRef.model_validate(
        stored_predecessor.model_dump(mode="python")
    )
    context = ModelInputContext(
        run_id="candidate-run",
        candidate_id="candidate-vector",
        candidate_content_hash="sha256:" + "a" * 64,
        design_problem_ref="candidate:problem",
    )
    invocation = ProgramGraphInputInvocation(
        context=context,
        interface_ref=case.interface_ref,
        program_graph_ref=_ref(73, "foundry.program_graph", ProgramGraphRef),
        exec_plan_ref=_ref(74, "foundry.exec_plan", ExecPlanRef),
        registry_bundle_ref=registry_ref,
        input_bindings_ref=predecessor_ref,
        steps=(0, 1),
    )
    member = ModelInputObligation(
        schema_version="1.2",
        context=context,
        interface_ref=case.interface_ref,
        program_graph_ref=invocation.program_graph_ref,
        exec_plan_ref=invocation.exec_plan_ref,
        registry_bundle_ref=registry_ref,
        input_bindings_ref=predecessor_ref,
        prestate_ref=state_ref,
        port=case.port.model_copy(update={"period_step_profile": ModelInputPeriodStepProfile()}),
        dependencies=(
            ProgramGraphInputDependency(
                node_id="gini",
                kind="method_read",
                first_required_step=0,
                required_steps=(0, 1),
                method_abi_digest="b" * 64,
            ),
        ),
    )
    selected_set = ModelInputObligationSet(
        schema_version="1.2",
        invocation=invocation,
        prestate_ref=state_ref,
        supplied_initial_slots=(),
        obligation_refs=(rows[0].selection.model_input_obligation_ref,),
        required_step_scopes=tuple(row.step_scope for row in rows),
    )
    monkeypatch.setattr(
        model_input_requirements,
        "load_model_input_obligation_set",
        lambda _store, _selected_ref: (selected_set, (member,)),
    )
    manifest = ResolvedInputBindingManifest(
        schema_version="4.0",
        data_snapshot_ref=data_ref,
        model_input_obligation_set_ref=_ref(75, "runtime.quality.model_input_obligation_set"),
        entity_vector_steps=rows,
    )
    return manifest, selected_set


def test_vector_normalizer_retains_full_denominator_and_original_predecessor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    manifest, original = _original_subjects(store, monkeypatch)
    selected = persist_resolved_input_binding_manifest(store, manifest)
    fresh = FileSystemCAS.open_existing_read_only(store.root)
    loaded = load_resolved_input_binding_manifest(fresh, selected)
    coverage = recompute_resolved_step_input_coverage(fresh, loaded)
    assert coverage.required_step_scopes == original.required_step_scopes
    assert coverage.is_complete
    partial = ResolvedInputBindingManifest.model_validate(
        loaded.model_dump(mode="python") | {"entity_vector_steps": loaded.entity_vector_steps[:1]}
    )
    missing = recompute_resolved_step_input_coverage(fresh, partial)
    assert missing.missing_step_scopes == original.required_step_scopes[1:]
    with pytest.raises(ValueError, match="model_input_step_coverage_incomplete"):
        missing.require_complete()


@pytest.mark.parametrize("mutation", ["origin", "axis", "scope", "predecessor"])
def test_vector_normalizer_refuses_subject_grafts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    manifest, _ = _original_subjects(store, monkeypatch)
    row = manifest.entity_vector_steps[0]
    expected = {
        "origin": "model_input_step_selection_origin_not_member",
        "axis": "model_input_step_selection_entity_axis_mismatch",
        "scope": "model_input_step_selection_scope_mismatch",
        "predecessor": "resolved_entity_vector_original_predecessor_mismatch",
    }[mutation]
    if mutation in {"origin", "axis"}:
        field = "model_input_obligation_ref" if mutation == "origin" else "entity_axis_ref"
        kind = (
            "runtime.quality.model_input_obligation"
            if mutation == "origin"
            else "foundry.selected_entity_axis"
        )
        row = row.model_copy(
            update={"selection": row.selection.model_copy(update={field: _ref(90, kind)})}
        )
        manifest = manifest.model_copy(update={"entity_vector_steps": (row,)})
    elif mutation == "scope":
        row = row.model_copy(
            update={"step_scope": row.step_scope.model_copy(update={"scope": _scope(2021)})}
        )
        manifest = manifest.model_copy(update={"entity_vector_steps": (row,)})
    else:
        manifest = manifest.model_copy(
            update={"data_snapshot_ref": _ref(91, "fabric.data_snapshot")}
        )
    selected = persist_resolved_input_binding_manifest(store, manifest)
    with pytest.raises(ValueError, match=f"^{expected}$"):
        load_resolved_input_binding_manifest(
            FileSystemCAS.open_existing_read_only(store.root), selected
        )


@pytest.mark.parametrize("selected_context", ["scalar", "step"])
def test_vector_readback_refuses_a_valid_prior_selected_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selected_context: str
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    manifest, original = _original_subjects(store, monkeypatch, selected_context=selected_context)
    fresh = FileSystemCAS.open_existing_read_only(store.root)
    # Prove the precise prerequisite is reached: this is an owner-readable
    # valid prior binding, and both original snapshot identities still match.
    predecessor = validate_core_model_json_artifact(
        FoundryInputBindings, fresh, original.invocation.input_bindings_ref
    )
    assert artifact_ref_identity_key(predecessor.data_snapshot_ref) == artifact_ref_identity_key(
        manifest.data_snapshot_ref
    )
    assert artifact_ref_identity_key(predecessor.bound_state_snapshot_ref) == (
        artifact_ref_identity_key(original.prestate_ref)
    )
    if selected_context == "scalar":
        assert predecessor.schema_version == "1.4"
        assert predecessor.selected_method_inputs is not None
        assert predecessor.selected_method_input_steps is None
    else:
        assert predecessor.schema_version == "1.5"
        assert predecessor.selected_method_inputs is None
        assert predecessor.selected_method_input_steps is not None
    selected = persist_resolved_input_binding_manifest(store, manifest)
    with pytest.raises(ValueError, match=r"^resolved_entity_vector_original_prestate_required$"):
        load_resolved_input_binding_manifest(
            FileSystemCAS.open_existing_read_only(store.root), selected
        )
