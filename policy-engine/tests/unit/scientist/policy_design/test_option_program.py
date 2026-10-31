"""Content-level option/program checks through selected CAS producer and readers."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    PutOptions,
    SchemaInfo,
    ensure_ir_artifact_store,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle, persist_trinity_bundle_artifact
from polisyos.scientist.policy_design.option_program import (
    ExplicitPolicyProgramIntent,
    OptionProgramSelection,
    load_option_program_relation,
    produce_option_program_relation,
    reconcile_option_program,
)
from polisyos.scientist.policy_design.schema import (
    PolicyCandidateSchema,
    load_policy_candidate_schema,
    persist_policy_candidate_schema,
)
from polisyos.scientist.validation.policy_verified.models import (
    PolicyOption,
    PolicyOptionSet,
    PolicyRequestFrame,
    persist_policy_option_set,
    persist_policy_request_frame,
)


def _bundle() -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(problem_id="synthetic_options", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="synthetic_program",
            interventions=[
                InterventionSpec(
                    intervention_id="action",
                    kind="subsidy",
                    target={
                        "kind": "predicate",
                        "field": "region_id",
                        "operator": "==",
                        "value": "synthetic_region",
                    },
                    schedule={"start_step": 0, "duration_steps": 4},
                    params={"amount": {"amount": "25", "currency": "EUR"}},
                )
            ],
        ),
        model_spec=ModelSpec(
            model_id="synthetic_world",
            data_snapshot_ref="sha256:" + "0" * 64,
        ),
    )


def _sources(
    root: Path,
    *,
    final: TrinityBundle | None = None,
    outline: dict | None = None,
    frame_update: dict | None = None,
    option_update: dict | None = None,
) -> tuple[FileSystemCAS, OptionProgramSelection]:
    store = FileSystemCAS(root)
    original = _bundle()
    candidate = PolicyCandidateSchema.from_trinity_bundle(final or original)
    frame = PolicyRequestFrame.model_validate(
        {
            "schema_version": "1.1",
            "request_id": "synthetic_request",
            "policy_question": "Explicit synthetic policy program?",
            "jurisdiction": "synthetic",
            "jurisdiction_source": "policy_request_jurisdiction",
            "as_of": "2026-10-31",
            **(frame_update or {}),
        }
    )
    request_ref = persist_policy_request_frame(store, frame)
    original_candidate = PolicyCandidateSchema.from_trinity_bundle(original)
    intent = ExplicitPolicyProgramIntent(
        schema_version="polisyos.explicit_policy_program_intent.v1",
        jurisdiction="synthetic",
        as_of="2026-10-31",
        policy_spec=original.policy_spec,
        target_population=original_candidate.target_population,
    )
    option = PolicyOption.model_validate(
        {
            "option_id": "synthetic_option",
            "title": "Synthetic action",
            "summary": "Description is not an interpreted program contract.",
            "intervention_outline": intent.model_dump(mode="json") if outline is None else outline,
            **(option_update or {}),
        }
    )
    option_ref = persist_policy_option_set(
        store,
        PolicyOptionSet(request_id=frame.request_id, hypothesis_options=[option]),
        inputs=[input_ref_from_artifact_ref(request_ref, role="policy_request_frame")],
    )
    candidate_ref = persist_policy_candidate_schema(store, candidate, return_selected_profile=True)
    trinity_ref = ArtifactRef.model_validate(
        persist_trinity_bundle_artifact(
            ensure_ir_artifact_store(store), candidate.trinity_bundle
        ).model_dump(mode="json")
    )
    return store, OptionProgramSelection(
        request_ref=request_ref,
        option_set_ref=option_ref,
        candidate_ref=candidate_ref,
        trinity_ref=trinity_ref,
        selected_option_ids=(option.option_id,),
    )


def test_explicit_intent_producer_and_fresh_consumer_reconcile_actual_program(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas")
    relation_ref = produce_option_program_relation(store, selection)
    fresh = FileSystemCAS(tmp_path / "cas")
    relation = load_option_program_relation(fresh, relation_ref, selection=selection)
    assert relation.status == "declared_program_match"
    assert [(item.intervention_id, item.program_path) for item in relation.action_bindings] == [
        ("action", "policy_spec.interventions[0]")
    ]
    assert relation.execution_correspondence == "not_established"
    assert relation.authority_boundary == "candidate_declared_program_only"
    assert relation.intent_provenance == "consumer_asserted"


def test_correctly_rebound_ban_intent_cannot_match_subsidy_program(tmp_path) -> None:
    """All references and their lineage are current; actual action content still differs."""
    original = _bundle()
    intent = ExplicitPolicyProgramIntent(
        schema_version="polisyos.explicit_policy_program_intent.v1",
        jurisdiction="synthetic",
        as_of="2026-10-31",
        policy_spec=original.policy_spec,
        target_population=PolicyCandidateSchema.from_trinity_bundle(original).target_population,
    ).model_dump(mode="json")
    intent["policy_spec"]["interventions"][0]["kind"] = "ban"
    store, selection = _sources(tmp_path / "cas", outline=intent)
    relation_ref = produce_option_program_relation(store, selection)
    relation = load_option_program_relation(
        FileSystemCAS(tmp_path / "cas"), relation_ref, selection=selection
    )
    assert relation.status == "mismatch"
    assert relation.reason_codes == ("option_program_declared_actions_mismatch",)
    assert relation.action_bindings == ()


@pytest.mark.parametrize("change", ["amount", "currency", "target", "schedule", "extra_action"])
def test_actual_final_program_content_controls_correspondence(tmp_path, change) -> None:
    payload = _bundle().model_dump(mode="json")
    action = payload["policy_spec"]["interventions"][0]
    if change == "amount":
        action["params"]["amount"]["amount"] = "50"
    elif change == "currency":
        action["params"]["amount"]["currency"] = "USD"
    elif change == "target":
        action["target"]["value"] = "another_region"
    elif change == "schedule":
        action["schedule"] = {"start_step": 5, "duration_steps": 4}
    else:
        extra = deepcopy(action)
        extra["intervention_id"] = "undeclared_action"
        payload["policy_spec"]["interventions"].append(extra)
    store, selection = _sources(tmp_path / "cas", final=TrinityBundle.model_validate(payload))
    assert reconcile_option_program(store, selection).status == "mismatch"


def test_equivalent_schedule_notation_is_the_same_declared_time_range(tmp_path) -> None:
    payload = _bundle().model_dump(mode="json")
    payload["policy_spec"]["interventions"][0]["schedule"] = {"start_step": 0, "end_step": 3}
    store, selection = _sources(tmp_path / "cas", final=TrinityBundle.model_validate(payload))
    assert reconcile_option_program(store, selection).status == "declared_program_match"


@pytest.mark.parametrize(
    ("frame_update", "expected"),
    [
        ({"jurisdiction": "other"}, "option_program_scope_or_time_mismatch"),
        ({"as_of": "2027-01-01"}, "option_program_scope_or_time_mismatch"),
        (
            {"schema_version": "1.0", "jurisdiction_source": None},
            "option_program_request_scope_not_established",
        ),
    ],
)
def test_request_scope_and_time_are_reconciled_not_inferred(
    tmp_path, frame_update, expected
) -> None:
    store, selection = _sources(tmp_path / "cas", frame_update=frame_update)
    assert reconcile_option_program(store, selection).reason_codes == (expected,)


def test_prose_and_unsupported_composition_remain_uninterpreted(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas", outline={"action": "subsidize businesses"})
    assert reconcile_option_program(store, selection).reason_codes == (
        "option_program_typed_intent_not_established",
    )
    store, selection = _sources(tmp_path / "other", option_update={"constraints": ["No harm"]})
    assert reconcile_option_program(store, selection).reason_codes == (
        "option_program_prose_obligations_not_interpreted",
    )
    joint = selection.model_copy(update={"selection_mode": "joint"})
    assert reconcile_option_program(store, joint).reason_codes == (
        "option_program_composition_semantics_not_established",
    )


def test_stale_relation_cannot_follow_a_new_final_champion(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas")
    relation_ref = produce_option_program_relation(store, selection)
    payload = _bundle().model_dump(mode="json")
    payload["policy_spec"]["interventions"][0]["params"]["amount"]["amount"] = "99"
    _, newer = _sources(tmp_path / "cas", final=TrinityBundle.model_validate(payload))
    with pytest.raises(ValueError, match="option_program_relation_selection_mismatch"):
        load_option_program_relation(store, relation_ref, selection=newer)
    assert reconcile_option_program(store, newer).status == "mismatch"


def test_forged_match_and_mapping_are_recomputed_from_actual_sources(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas")
    relation_ref = produce_option_program_relation(store, selection)
    relation = load_option_program_relation(store, relation_ref, selection=selection)
    forged = relation.model_copy(update={"action_bindings": ()})
    manifest = store.get_manifest(relation_ref)
    counterfeit = store.put_json(
        forged,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError, match="option_program_relation_result_not_recomputed"):
        load_option_program_relation(store, counterfeit, selection=selection)


def test_same_relation_bytes_under_foreign_owner_profile_are_refused(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas")
    relation_ref = produce_option_program_relation(store, selection)
    manifest = store.get_manifest(relation_ref)
    foreign = store.put_bytes(
        store.get_bytes(relation_ref),
        PutOptions(
            kind="synthetic.foreign_relation",
            media_type=manifest.media_type,
            schema=SchemaInfo(name="synthetic.ForeignRelation", version="1.0"),
            canon=manifest.canon,
            inputs=manifest.inputs,
        ),
        return_selected_profile=True,
    )
    assert foreign.artifact_id == relation_ref.artifact_id
    with pytest.raises(ValueError):
        load_option_program_relation(store, foreign, selection=selection)


def test_swapped_candidate_and_trinity_are_not_admitted(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas")
    swapped = selection.model_copy(
        update={"candidate_ref": selection.trinity_ref, "trinity_ref": selection.candidate_ref}
    )
    with pytest.raises(ValueError):
        reconcile_option_program(store, swapped)


def test_missing_relation_is_a_refusal_not_an_implicit_match(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas")
    with pytest.raises(ValueError, match="option_program_relation_missing"):
        load_option_program_relation(store, None, selection=selection)


@pytest.mark.parametrize("declared_value", [10, 20])
def test_constraints_are_reconciled_by_content_across_core_and_ir_readers(
    tmp_path, declared_value
) -> None:
    payload = _bundle().model_dump(mode="json")
    payload["problem_frame"]["hard_constraints"] = [
        {
            "constraint_id": "spending_cap",
            "constraint_type": "hard",
            "value": 10,
            "slot_id": "government.spending",
            "operator": "<=",
        }
    ]
    expected = deepcopy(payload)
    expected["problem_frame"]["hard_constraints"][0]["value"] = declared_value
    expected_bundle = TrinityBundle.model_validate(expected)
    outline = ExplicitPolicyProgramIntent(
        schema_version="polisyos.explicit_policy_program_intent.v1",
        jurisdiction="synthetic",
        as_of="2026-10-31",
        policy_spec=expected_bundle.policy_spec,
        target_population=PolicyCandidateSchema.from_trinity_bundle(
            expected_bundle
        ).target_population,
        hard_constraints=expected_bundle.problem_frame.hard_constraints,
    ).model_dump(mode="json")
    store, selection = _sources(
        tmp_path / "cas", outline=outline, final=TrinityBundle.model_validate(payload)
    )
    result = reconcile_option_program(store, selection)
    if declared_value == 10:
        assert result.status == "declared_program_match"
        assert result.reason_codes == ()
    else:
        assert result.status == "mismatch"
        assert result.reason_codes == ("option_program_constraints_mismatch",)


def test_relation_manifest_cannot_swap_selected_source_roles(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas")
    relation_ref = produce_option_program_relation(store, selection)
    manifest = store.get_manifest(relation_ref)
    inputs = list(manifest.inputs)
    inputs[0], inputs[1] = (
        input_ref_from_artifact_ref(selection.option_set_ref, role="policy_request_frame"),
        input_ref_from_artifact_ref(selection.request_ref, role="policy_option_set"),
    )
    counterfeit = store.put_bytes(
        store.get_bytes(relation_ref),
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            canon=manifest.canon,
            inputs=inputs,
        ),
        return_selected_profile=True,
    )
    assert counterfeit.artifact_id == relation_ref.artifact_id
    with pytest.raises(ValueError, match="option_program_relation_source_edges_mismatch"):
        load_option_program_relation(store, counterfeit, selection=selection)


def test_boolean_parameter_cannot_equal_numeric_parameter_by_python_aliasing(tmp_path) -> None:
    original = _bundle()
    candidate = PolicyCandidateSchema.from_trinity_bundle(original)
    outline = ExplicitPolicyProgramIntent(
        schema_version="polisyos.explicit_policy_program_intent.v1",
        jurisdiction="synthetic",
        as_of="2026-10-31",
        policy_spec=original.policy_spec,
        target_population=candidate.target_population,
    ).model_dump(mode="json")
    outline["policy_spec"]["interventions"][0]["params"]["amount"] = True
    payload = original.model_dump(mode="json")
    payload["policy_spec"]["interventions"][0]["params"]["amount"] = 1
    store, selection = _sources(
        tmp_path / "cas", outline=outline, final=TrinityBundle.model_validate(payload)
    )
    assert reconcile_option_program(store, selection).status == "mismatch"


def test_candidate_trinity_join_also_preserves_boolean_numeric_distinction(tmp_path) -> None:
    payload = _bundle().model_dump(mode="json")
    payload["policy_spec"]["interventions"][0]["params"]["amount"] = 1
    store, selection = _sources(tmp_path / "cas", final=TrinityBundle.model_validate(payload))
    candidate = load_policy_candidate_schema(store, selection.candidate_ref).model_dump(mode="json")
    candidate["trinity_bundle"]["policy_spec"]["interventions"][0]["params"]["amount"] = True
    changed = persist_policy_candidate_schema(
        store, PolicyCandidateSchema.model_validate(candidate), return_selected_profile=True
    )
    swapped = selection.model_copy(update={"candidate_ref": changed})
    with pytest.raises(ValueError, match="option_program_candidate_trinity_mismatch"):
        reconcile_option_program(store, swapped)


def test_unvalidated_dto_copy_cannot_drop_required_selected_profile(tmp_path) -> None:
    store, selection = _sources(tmp_path / "cas")
    changed = selection.model_copy(
        update={
            "candidate_ref": selection.candidate_ref.model_copy(
                update={"manifest_profile_sha256": None}
            )
        }
    )
    with pytest.raises(ValueError, match="option_program_selected_profile_required"):
        reconcile_option_program(store, changed)


def test_shape_without_explicit_interpretation_version_does_not_acquire_meaning(tmp_path) -> None:
    store, selected = _sources(tmp_path / "source")
    payload = load_core_json_artifact(store, selected.option_set_ref)
    outline = payload["hypothesis_options"][0]["intervention_outline"]
    outline.pop("schema_version")
    other, selection = _sources(tmp_path / "untagged", outline=outline)
    assert reconcile_option_program(other, selection).reason_codes == (
        "option_program_typed_intent_not_established",
    )


def test_real_tagged_float_content_survives_owner_reads_and_common_trinity_join(tmp_path) -> None:
    payload = _bundle().model_dump(mode="json")
    payload["policy_spec"]["interventions"][0]["measurement_expectations"] = {
        "diagnostic_threshold": 0.1
    }
    payload["model_spec"]["agent_config"]["agent_types"] = [
        {
            "agent_type_id": "workers",
            "entity_type": "agent",
            "population_count": 2,
            "attribute_distributions": {"income": {"mean": 1.25, "sd": 0.5}},
        }
    ]
    bundle = TrinityBundle.model_validate(payload)
    outline = ExplicitPolicyProgramIntent(
        schema_version="polisyos.explicit_policy_program_intent.v1",
        jurisdiction="synthetic",
        as_of="2026-10-31",
        policy_spec=bundle.policy_spec,
        target_population=PolicyCandidateSchema.from_trinity_bundle(bundle).target_population,
    ).model_dump(mode="json")
    store, selection = _sources(tmp_path / "cas", outline=outline, final=bundle)
    ref = produce_option_program_relation(store, selection)
    fresh = FileSystemCAS(tmp_path / "cas")
    assert load_option_program_relation(fresh, ref, selection=selection).status == (
        "declared_program_match"
    )
