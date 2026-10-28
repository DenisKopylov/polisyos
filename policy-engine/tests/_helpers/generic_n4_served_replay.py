"""Real N4 source/profile preparation and served N5 replay helpers for tests."""

from __future__ import annotations

import copy
import dataclasses
import json
import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest

from polisyos.core.security.tenant_context import tenant_scope
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
from tests._helpers.controlled_candidate_profile import (
    ControlledSKGSourceSelection,
    _configured_procurement_profile,
    _controlled_direct_ncm_outcome_state_paths,
    _controlled_procurement_recording,
    _current_compiler_problem,
    _materialize_controlled_world_model_record,
    _validate_controlled_skg_source,
)
from tests._helpers.controlled_candidate_profile import (
    _seed_controlled_selected_skg_source as _build_candidate_only_skg_source,
)
from tools.quality.validation import (
    check_layer3_gy_design_generation_contract as n4_contract,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _candidate_source_l3_row_counts(path: Path) -> dict[str, int]:
    """Read bounded row counts from the selected controlled L3 fixture."""
    import duckdb

    connection = duckdb.connect(str(path), read_only=True)
    try:
        return {
            "lex_amendments": int(
                connection.execute("SELECT COUNT(*) FROM lex_amendments").fetchone()[0]
            ),
            "lex_normative_ready_facts": int(
                connection.execute("SELECT COUNT(*) FROM lex_normative_ready_facts").fetchone()[0]
            ),
            "lex_reference_edges": int(
                connection.execute("SELECT COUNT(*) FROM lex_reference_edges").fetchone()[0]
            ),
            "lex_rule_thresholds": int(
                connection.execute("SELECT COUNT(*) FROM lex_rule_thresholds").fetchone()[0]
            ),
        }
    finally:
        connection.close()


_RECORDING_ID = "gy_n4_cgf_decisive_capture_1_20260704_092222_049411"
_ORIGINAL_SECOND_CAPTURE_RECORDING_ID = "gy_n4_replay_20260704_095710_425807_7bf5552df372"
_ORIGINAL_SECOND_CAPTURE_CONTENT_HASH = (
    "sha256:107f896fb1fd1c37170b74c88726c07169277d05d3ec5459ceb360919e692cb1"
)
_CANDIDATE_SCM_OVERRIDE_FIELDS = frozenset(
    {
        "target_baseline",
        "outcome_baseline",
        "outcome_per_target_unit",
        "outcome_noise_stddev",
    }
)


def _validated_candidate_scm_overrides(
    overrides: object,
) -> dict[str, float]:
    """Validate finite candidate-model parameters before fixture side effects."""
    if type(overrides) is not dict:
        raise TypeError("controlled_candidate_scm_overrides_untyped")
    unknown = set(overrides) - _CANDIDATE_SCM_OVERRIDE_FIELDS
    if unknown:
        raise ValueError("controlled_candidate_scm_override_field_unsupported")
    if any(type(value) is not float or not math.isfinite(value) for value in overrides.values()):
        raise ValueError("controlled_candidate_scm_override_not_finite_float")
    return dict(overrides)


def _validated_candidate_scm_overrides_by_child(
    overrides: object,
    *,
    child_count: int,
) -> dict[int, dict[str, float]]:
    """Validate the exact N4 child indices and typed candidate-model override rows."""
    if overrides is None:
        return {}
    if type(overrides) is not dict:
        raise TypeError("controlled_candidate_scm_child_overrides_untyped")
    result: dict[int, dict[str, float]] = {}
    for index, fields in overrides.items():
        if type(index) is not int or index < 0 or index >= child_count:
            raise ValueError("controlled_candidate_scm_child_index_out_of_range")
        result[index] = _validated_candidate_scm_overrides(fields)
    return result


def _source_recorded_n4_retry_inputs(recording: dict[str, Any]) -> dict[str, int]:
    """Read the retry settings needed to align the recorded N4 response window."""
    capture_summary = recording.get("capture_summary")
    if not isinstance(capture_summary, dict):
        raise ValueError("controlled_n4_recorded_runtime_config_missing")
    runtime_config = capture_summary.get("effective_runtime_config")
    if not isinstance(runtime_config, dict):
        raise ValueError("controlled_n4_recorded_runtime_config_missing")
    fields = {
        "POLISYOS_DRAFTER_PASS_RETRY_COUNT": "drafter_pass_retry_count",
        "POLISYOS_FORMALIZER_LLM_RETRIES": "formalizer_retry_count",
    }
    values: dict[str, int] = {}
    for environment_name, field_name in fields.items():
        value = runtime_config.get(field_name)
        if type(value) is not int or value < 0:
            raise ValueError("controlled_n4_recorded_runtime_config_invalid:" + field_name)
        values[environment_name] = value
    return values


def _bind_source_recorded_n4_retry_inputs(
    recording: dict[str, Any], monkeypatch: Any
) -> dict[str, int]:
    """Use capture-bound retry counts rather than ambient replay defaults."""
    values = _source_recorded_n4_retry_inputs(recording)
    for environment_name, value in values.items():
        monkeypatch.setenv(environment_name, str(value))
    return values


@dataclass(frozen=True)
class PreparedGenericN4ServedReplay:
    """Controlled source and complete N4-derived profile set for a serving app."""

    tmp_path: Path
    cas_root: Path
    runtime_api_context: Any
    app_kwargs: dict[str, Any]
    request_json: dict[str, Any]
    recording: dict[str, Any]
    source_recording_id: str
    source_recording_content_hash: str
    recorded_problem: Any
    organ_run: Any
    selected_reference: Any
    selected_source_ref: Any
    selected_source_profile: Any
    selected_skg_db_path: Path
    selected_skg_version_id: int
    selected_skg_snapshot_ref: str
    selected_skg_source: ControlledSKGSourceSelection
    selected_skg_source_checkpoints: tuple[str, ...]
    base_profile: Any
    base_declaration: Any
    generic_profiles: tuple[Any, ...]
    generic_child_profiles: tuple[Any, ...]
    children: tuple[Any, ...]
    child_keys: tuple[str, ...]
    root_profile: Any
    model_id: str
    tenant_id: str
    cell_id: str
    source_root: Path | None = None
    source_root_witness: dict[str, Any] = dataclasses.field(default_factory=dict)


@dataclass(frozen=True)
class N4ServedRunReceipt:
    """Observed output from the actual control worker and fresh run-details GET."""

    accepted_payload: dict[str, Any]
    job_id: str
    job_state: str
    run_id: str
    failure_code: str
    failure_message: str
    get_payload: dict[str, Any]
    projection: dict[str, Any]
    successful_observation: dict[str, Any]
    n5_result_ref: Any
    checkpoint: dict[str, Any]
    actual_sibling_failure: dict[str, Any]
    child_attempt_profile_ids: tuple[str, ...]
    successful_child_runs: tuple[Any, ...]
    corrupt_projection: dict[str, Any] | None
    incomplete_profile_projection: dict[str, Any] | None
    missing_result_ref_error_code: str


@dataclass(frozen=True)
class N4BudgetStopRunReceipt:
    """Observed actual N6 budget stop and its HTTP checkpoint projection."""

    accepted_payload: dict[str, Any]
    job_id: str
    job_state: str
    run_id: str
    get_payload: dict[str, Any]
    job_status_payload: dict[str, Any]
    projection: dict[str, Any]
    checkpoint: dict[str, Any]
    child_node_refs: tuple[str, ...]


def _emit_served_phase(
    phase_callback: Any | None,
    stage: str,
    *,
    job_id: str | None = None,
    run_id: str | None = None,
) -> None:
    """Emit one optional test-only lifecycle marker without recording payloads."""
    if phase_callback is not None:
        phase_callback(stage, job_id, run_id)


def _contract_value_matches(observed: Any, expected: Any) -> bool:
    """Compare a decoded fixture value with its typed JSON sequence shape."""
    if isinstance(expected, list):
        return (
            isinstance(observed, (list, tuple))
            and len(observed) == len(expected)
            and all(
                _contract_value_matches(actual, item)
                for actual, item in zip(observed, expected, strict=True)
            )
        )
    if isinstance(expected, dict):
        return (
            isinstance(observed, dict)
            and set(observed) == set(expected)
            and all(_contract_value_matches(observed[key], item) for key, item in expected.items())
        )
    return type(observed) is type(expected) and observed == expected


def _original_second_capture_expected_output(
    *,
    recording_id: str,
    recording_content_hash: str,
) -> dict[str, Any]:
    """Return expectations only for the exact immutable source recording."""
    if (recording_id, recording_content_hash) != (
        _ORIGINAL_SECOND_CAPTURE_RECORDING_ID,
        _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH,
    ):
        raise RuntimeError("original_second_capture_expected_source_mismatch")
    candidate_groups_by_proposal = {
        "gy_n4.industrial_retention_tax_credit": (
            "tax_relief_rate",
            ("global.tax_rate",),
        ),
        "gy_n4.procurement_distress_backstop": (
            "procurement_shock_intensity",
            ("cells.distress_score",),
        ),
    }
    return {
        "candidate_groups_by_proposal": candidate_groups_by_proposal,
        "dispositions": {
            **dict.fromkeys(candidate_groups_by_proposal, "shadow_bound"),
            "gy_n4.msme_working_capital_guarantee": "unknown_blocked",
        },
        "diversity_report": {
            "min_required": 3,
            "candidate_count": 3,
            "unique_diversity_key_count": 3,
            "diverse_enough": True,
        },
        "grounding_disposition_summary": {
            "total_candidates": 3,
            "shadow_bound": 2,
            "abstain_or_blocked": 1,
        },
    }


def _original_second_capture_candidate_semantics(
    result: Any,
) -> dict[str, tuple[str, str, tuple[str, ...]]]:
    """Project typed producer candidates to their complete semantic identity tuple."""
    observed: dict[str, tuple[str, str, tuple[str, ...]]] = {}
    for candidate in result.candidates:
        candidate_id = str(candidate.candidate_id)
        atom = candidate.atom
        operator_kind = atom.operator_kind.trinity_kind
        if hasattr(operator_kind, "value"):
            operator_kind = operator_kind.value
        targets = tuple(str(target) for target in atom.target_world_slots)
        if candidate_id in observed or not targets:
            raise AssertionError("original_second_capture_candidate_identity_not_unique")
        observed[candidate_id] = (str(atom.content_hash), str(operator_kind), targets)
    return observed


def _assert_original_second_capture_generation_result(
    result: Any,
    *,
    design_problem_ref: str,
    recording_id: str,
    recording_content_hash: str,
) -> dict[str, tuple[str, str, tuple[str, ...]]]:
    """Check the current parent binding and complete recorded N4 semantics."""
    expected = _original_second_capture_expected_output(
        recording_id=recording_id,
        recording_content_hash=recording_content_hash,
    )
    if result.design_problem_ref != design_problem_ref:
        raise AssertionError("original_second_capture_result_problem_ref_mismatch")
    if result.status != "generated":
        raise AssertionError("original_second_capture_generation_not_generated")

    report = result.diversity_report
    for field, value in expected["diversity_report"].items():
        if not _contract_value_matches(getattr(report, field), value):
            raise AssertionError("original_second_capture_diversity_contract_mismatch")
    summary = result.grounding_disposition_summary
    for field, value in expected["grounding_disposition_summary"].items():
        if not _contract_value_matches(getattr(summary, field), value):
            raise AssertionError("original_second_capture_summary_contract_mismatch")

    observed_dispositions: dict[str, str] = {}
    disposition_candidate_ids_by_proposal: dict[str, str] = {}
    for row in result.grounding_dispositions:
        proposal_id = str(row.proposal_id)
        if proposal_id in observed_dispositions:
            raise AssertionError("original_second_capture_duplicate_disposition")
        disposition = getattr(row.disposition, "value", row.disposition)
        observed_dispositions[proposal_id] = str(disposition)
        if disposition == "shadow_bound":
            candidate_id = getattr(row, "candidate_id", None)
            if (
                not isinstance(candidate_id, str)
                or candidate_id in disposition_candidate_ids_by_proposal.values()
            ):
                raise AssertionError("original_second_capture_shadow_candidate_binding_invalid")
            disposition_candidate_ids_by_proposal[proposal_id] = candidate_id
    if observed_dispositions != expected["dispositions"]:
        raise AssertionError("original_second_capture_complete_disposition_map_mismatch")

    observed_candidates = _original_second_capture_candidate_semantics(result)
    candidate_groups_by_id = {
        candidate_id: (operator_kind, tuple(sorted(targets)))
        for candidate_id, (
            _atom_ref,
            operator_kind,
            targets,
        ) in observed_candidates.items()
    }
    observed_groups_by_proposal: dict[str, tuple[str, tuple[str, ...]]] = {}
    for proposal_id, candidate_id in disposition_candidate_ids_by_proposal.items():
        group = candidate_groups_by_id.get(candidate_id)
        if group is None:
            raise AssertionError("original_second_capture_disposition_candidate_not_generated")
        observed_groups_by_proposal[proposal_id] = group
    if (
        len(observed_candidates) != 2
        or len(set(candidate_groups_by_id.values())) != len(observed_candidates)
        or observed_groups_by_proposal != expected["candidate_groups_by_proposal"]
    ):
        raise AssertionError("original_second_capture_candidate_semantics_mismatch")
    return observed_candidates


def _original_second_capture_child_group(child: Any) -> tuple[tuple[str, str], ...]:
    """Return the complete operator/target group represented by one typed child."""
    levers = tuple(child.problem.candidate_lever_space.candidate_levers)
    if not levers:
        raise AssertionError("original_second_capture_child_has_no_candidate_levers")
    return tuple(sorted((str(lever.operator_kind), str(lever.target_slot)) for lever in levers))


def _assert_original_second_capture_child_semantic_join(
    children: Any,
    candidate_semantics: dict[str, tuple[str, str, tuple[str, ...]]],
) -> dict[tuple[tuple[str, str], ...], tuple[str, ...]]:
    """Bind every contract candidate atom to exactly its derived typed child group."""
    expected: dict[tuple[tuple[str, str], ...], set[str]] = {}
    for atom_ref, operator_kind, targets in candidate_semantics.values():
        group = tuple(sorted((operator_kind, target) for target in targets))
        expected.setdefault(group, set()).add(atom_ref)
    observed: dict[tuple[tuple[str, str], ...], tuple[str, ...]] = {}
    for child in children:
        group = _original_second_capture_child_group(child)
        refs = tuple(sorted(str(ref) for ref in child.source_atom_refs))
        if not refs or len(refs) != len(set(refs)) or group in observed:
            raise AssertionError("original_second_capture_child_atom_group_not_unique")
        observed[group] = refs
    expected_normalized = {group: tuple(sorted(refs)) for group, refs in expected.items()}
    if observed != expected_normalized:
        raise AssertionError("original_second_capture_candidate_to_child_join_mismatch")
    return observed


def _hashed_model(model_type: type[Any], fields: dict[str, Any], *, hash_fn: Any):
    draft = model_type.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    body = draft.model_dump(mode="json", exclude={"content_hash"})
    return model_type.model_validate({**body, "content_hash": hash_fn(body)})


def _two_child_recording(recording: dict[str, Any], *, outcome_variable: str) -> dict[str, Any]:
    """Derive a two-child controlled recording without claiming historical bytes."""
    from polisyos.pdc import gy_content_hash

    # This composite fixture has one persisted parent: the recorded input. The
    # controlled overlay below is an in-memory transformation step, not a
    # separately recorded artifact.
    source_recording_id = str(recording["recording_id"])
    source_recording_content_hash = str(recording["recording_content_hash"])
    controlled = _controlled_procurement_recording(
        recording,
        outcome_variable=outcome_variable,
    )
    responses = controlled["responses"]
    if not isinstance(responses, list):
        raise AssertionError("controlled_recording_responses_not_list")
    for response_index in (4, 8):
        response = responses[response_index]
        if not isinstance(response, dict):
            raise AssertionError("controlled_recording_response_not_object")
        raw = response.get("raw_response")
        if not isinstance(raw, str):
            raise AssertionError("controlled_recording_response_bytes_missing")
        payload = json.loads(raw)
        interventions = payload["policy_spec"]["interventions"]
        retained = [row for row in interventions if row.get("kind") != "credit_guarantee"]
        if {row.get("kind") for row in retained} != {
            "tax_relief_rate",
            "procurement_shock_intensity",
        }:
            raise AssertionError("controlled_recording_child_interventions_changed")
        removed_ids = {row.get("intervention_id") for row in interventions if row not in retained}
        payload["policy_spec"]["interventions"] = retained
        payload["policy_spec"]["parameters"] = [
            row
            for row in payload["policy_spec"].get("parameters", [])
            if row.get("intervention_id") not in removed_ids
        ]
        rewritten = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)

    fixture_id = (
        "synthetic_two_n4_children_"
        + gy_content_hash(
            {
                "base_recording_id": source_recording_id,
                "base_content_hash": source_recording_content_hash,
                "response_hashes": [
                    row.get("raw_response_hash") for row in responses if isinstance(row, dict)
                ],
            }
        ).removeprefix("sha256:")[:20]
    )
    controlled["recording_id"] = fixture_id
    controlled["fixture_id"] = fixture_id
    controlled["recording_source"] = "synthetic_two_child_overlay_of_recorded_capture"
    controlled["derived_from_recording_id"] = source_recording_id
    controlled["derived_from_content_hash"] = source_recording_content_hash
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)  # type: ignore[arg-type]
    return controlled


def _three_child_recording(recording: dict[str, Any], *, outcome_variable: str) -> dict[str, Any]:
    """Derive a three-child controlled recording from its selected recorded source."""
    from polisyos.pdc import gy_content_hash

    source_recording_id = str(recording["recording_id"])
    source_recording_content_hash = str(recording["recording_content_hash"])
    controlled = _controlled_procurement_recording(
        recording,
        outcome_variable=outcome_variable,
    )
    responses = controlled["responses"]
    if not isinstance(responses, list):
        raise AssertionError("controlled_recording_responses_not_list")
    # The source problem declares labor_market on agents_is_employed, but it
    # does not declare credit_guarantee. Adapt the recorded third proposal into
    # a synthetic candidate for the existing lever so this fixture exercises
    # the complete source-bound child path without adding a lever or claiming
    # evidence.
    expected_kinds = {
        "labor_market",
        "tax_relief_rate",
        "procurement_shock_intensity",
    }
    for response_index in (4, 8):
        response = responses[response_index]
        if not isinstance(response, dict):
            raise AssertionError("controlled_recording_response_not_object")
        raw = response.get("raw_response")
        if not isinstance(raw, str):
            raise AssertionError("controlled_recording_response_bytes_missing")
        payload = json.loads(raw)
        interventions = payload["policy_spec"]["interventions"]
        third = [row for row in interventions if row.get("kind") == "credit_guarantee"]
        if len(third) != 1:
            raise AssertionError("controlled_recording_third_candidate_missing")
        source_intervention_id = third[0].get("intervention_id")
        synthetic_intervention_id = f"synthetic_labor_market_retention_{response_index}"
        if not isinstance(source_intervention_id, str) or not source_intervention_id:
            raise AssertionError("controlled_recording_third_candidate_identity_missing")
        third[0].update(
            {
                "description": (
                    "A synthetic labor-market retention candidate adapted to the "
                    "parent's already-declared lever."
                ),
                "intervention_id": synthetic_intervention_id,
                "kind": "labor_market",
                "name": "Synthetic labor-market employment-retention candidate",
                "notes": [
                    "Synthetic candidate adapted to the already-declared labor_market "
                    "lever; no empirical effect or authority is asserted."
                ],
                "params": {
                    "effect_path": ["agents.is_employed", "employment_retention"],
                    "estimand": "average_treatment_effect",
                    "employment_threshold": "0.5",
                    "outcome_slots": ["employment_retention"],
                    "sign": "increase",
                    "target_world_slot": "agents.is_employed",
                },
                "rationale": (
                    "This controlled candidate exercises the declared labor-market "
                    "lever in a synthetic replay. It does not assert an empirical "
                    "effect, source evidence, or authority."
                ),
                "target_population": "Synthetic industrial MSME test population",
            }
        )
        payload["policy_spec"]["description"] = (
            "Synthetic three-intervention candidate combining tax relief, procurement "
            "stabilization, and the already-declared labor-market retention lever."
        )
        parameters = payload["policy_spec"].get("parameters")
        if not isinstance(parameters, list):
            raise AssertionError("controlled_recording_parameters_not_list")
        if not any(
            isinstance(parameter, dict)
            and parameter.get("intervention_id") == source_intervention_id
            for parameter in parameters
        ):
            raise AssertionError("controlled_recording_third_parameter_missing")
        payload["policy_spec"]["parameters"] = [
            parameter
            for parameter in parameters
            if not (
                isinstance(parameter, dict)
                and parameter.get("intervention_id") == source_intervention_id
            )
        ]
        payload["policy_spec"]["parameters"].append(
            {
                "default_value": "0.5",
                "intervention_id": synthetic_intervention_id,
                "max_value": "1.0",
                "min_value": "0.0",
                "param_id": "employment_threshold",
                "param_path": "employment_threshold",
            }
        )
        model_spec = payload.get("model_spec")
        if isinstance(model_spec, dict):
            assumptions = model_spec.get("assumptions")
            if isinstance(assumptions, list):
                for assumption in assumptions:
                    if not isinstance(assumption, dict):
                        continue
                    if "credit_guarantee" in str(assumption.get("assumption_id", "")):
                        assumption.update(
                            {
                                "assumption_id": (
                                    f"synthetic_labor_market_candidate_{response_index}"
                                ),
                                "description": (
                                    "The labor-market candidate is a synthetic test input "
                                    "adapted to an existing declared lever; no empirical "
                                    "effect or authority is asserted."
                                ),
                            }
                        )
        rewritten = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        response["raw_response"] = rewritten
        response["raw_response_hash"] = gy_content_hash(rewritten)
        if {row.get("kind") for row in interventions} != expected_kinds:
            raise AssertionError("controlled_recording_three_child_interventions_changed")

    fixture_id = (
        "synthetic_three_n4_children_"
        + gy_content_hash(
            {
                "base_recording_id": source_recording_id,
                "base_content_hash": source_recording_content_hash,
                "response_hashes": [
                    row.get("raw_response_hash") for row in responses if isinstance(row, dict)
                ],
            }
        ).removeprefix("sha256:")[:20]
    )
    controlled["recording_id"] = fixture_id
    controlled["fixture_id"] = fixture_id
    controlled["recording_source"] = "synthetic_three_child_overlay_of_recorded_capture"
    controlled["derived_from_recording_id"] = source_recording_id
    controlled["derived_from_content_hash"] = source_recording_content_hash
    controlled["recording_content_hash"] = gy_content_hash(
        {key: value for key, value in controlled.items() if key != "recording_content_hash"}
    )
    n4_contract._validate_recording_fixture(controlled)  # type: ignore[arg-type]
    return controlled


def _persist_compiled_run_with_incomplete_child_set(
    *,
    store: Any,
    compiled_ref: Any,
    tenant_id: str,
    cell_id: str,
):
    """Persist a self-consistent compiled ref to a source-incomplete child-set artifact."""
    from polisyos.core import canon
    from polisyos.core.artifacts import ArtifactWriteOptions
    from polisyos.core.artifacts.manifest import ArtifactTenantContextInfo, SchemaInfo
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveLeafContextOwner,
        RecursiveN4ChildProfileSetV1,
    )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            canon.from_canonical_bytes(store.get_bytes(compiled_ref))
        )
        child_set_ref = compiled.n4_child_profile_set_ref
        assert child_set_ref is not None
        original_set = RecursiveN4ChildProfileSetV1.model_validate(
            canon.from_canonical_bytes(store.get_bytes(child_set_ref))
        )
    assert len(original_set.children) == 2
    incomplete_set = _hashed_model(
        RecursiveN4ChildProfileSetV1,
        {
            **original_set.model_dump(mode="python", exclude={"content_hash"}),
            "children": original_set.children[:-1],
        },
        hash_fn=gy_content_hash,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        incomplete_set_ref = store.put_json(
            incomplete_set.model_dump(mode="json"),
            RecursiveLeafContextOwner._n4_child_profile_set_write_options(incomplete_set),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )

    compiled_fields = compiled.model_dump(mode="python", exclude={"content_hash"})
    compiled_fields["n4_child_profile_set_ref"] = incomplete_set_ref
    draft = compiled.model_copy(
        update={
            "n4_child_profile_set_ref": incomplete_set_ref,
            "content_hash": "sha256:" + "0" * 64,
        },
    )
    identity_payload = gy_artifact_self_identity_projection(draft)
    recursive_payload = dict(identity_payload["recursive_run"])
    recursive_payload.pop("leaf_nodes", None)
    identity_payload["recursive_run"] = recursive_payload
    compiled_fields["content_hash"] = gy_content_hash(identity_payload)
    incomplete_compiled = CompiledRecursiveGenerationCycleRun.model_validate(compiled_fields)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        incomplete_compiled_ref = store.put_json(
            incomplete_compiled.model_dump(mode="json"),
            ArtifactWriteOptions(
                kind="runtime.compiled_recursive_generation_cycle",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.runtime.CompiledRecursiveGenerationCycleRun",
                    version="1.0",
                ),
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id=tenant_id,
                    cell_id=cell_id,
                ),
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )
    return incomplete_compiled_ref, incomplete_set_ref


def _seed_controlled_selected_skg_source(
    tmp_path: Path,
    *,
    recorded_problem: Any,
    source_root: Path | None = None,
) -> ControlledSKGSourceSelection:
    """Use the canonical producer for a candidate-only variable-identity SKG."""
    return _build_candidate_only_skg_source(
        tmp_path,
        recorded_problem=recorded_problem,
        source_root=source_root,
    )


def _generic_profile_for_selection(
    *,
    tmp_path: Path,
    source_root: Path | None = None,
    base_profile: Any,
    base_declaration: Any,
    profile_id: str,
    profile_selection_ref: str,
    profile_selection_kind: str,
    target_world_slot: str,
    operator_kind: str,
    store: Any,
    substrate_registry_ref: Any,
    selected_skg_source: ControlledSKGSourceSelection,
    tenant_id: str,
    cell_id: str,
    candidate_scm_overrides: dict[str, float] | None = None,
):
    """Build a typed candidate-only profile and persist its exact WMRv2/NCM basis."""
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.ir.analytics.ncm import (
        candidate_ncm_spec_from_declaration,
        persist_ncm_spec,
    )
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateScenarioSetToRule,
        CandidateSimulationScenarioProfile,
        candidate_simulation_profile_ref,
    )
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleN5RequestProfileV1,
        GenericCycleSimulationProfileV1,
    )
    from polisyos.runtime.quality.world_model_record import (
        derive_candidate_scenario_world_model_record,
        load_world_model_record,
        persist_world_model_record,
    )

    overrides = (
        {}
        if candidate_scm_overrides is None
        else _validated_candidate_scm_overrides(candidate_scm_overrides)
    )
    outcome_variable = base_declaration.outcome_variable
    baseline_state = {key: float(value) for key, value in base_profile.n5.baseline_state.items()}
    baseline_state.setdefault(target_world_slot, 0.0)
    baseline_state.setdefault(outcome_variable, 0.0)
    if "target_baseline" in overrides:
        baseline_state[target_world_slot] = overrides["target_baseline"]
    if "outcome_baseline" in overrides:
        baseline_state[outcome_variable] = overrides["outcome_baseline"]
    rule = CandidateScenarioSetToRule(
        operator_kind=operator_kind,
        parameter_id="controlled_value",
        target_world_slot=target_world_slot,
        unit_id=base_profile.rule.unit_id,
        minimum=base_profile.rule.minimum,
        maximum=base_profile.rule.maximum,
    )
    candidate_n5 = base_profile.n5.model_copy(update={"baseline_state": baseline_state})
    candidate_fields = base_profile.model_dump(mode="python", exclude={"content_hash"})
    candidate_fields.update(
        {
            "profile_id": "v6-synthetic-model-" + profile_id,
            "profile_selection_ref": profile_selection_ref,
            "context_inputs": base_profile.context_inputs,
            "rule": rule,
            "n5": candidate_n5,
        }
    )
    synthetic_profile = _hashed_model(
        CandidateSimulationScenarioProfile,
        candidate_fields,
        hash_fn=gy_content_hash,
    )
    declaration_fields = base_declaration.model_dump(mode="python", exclude={"content_hash"})
    declaration_fields.update(
        {
            "profile_config_ref": candidate_simulation_profile_ref(synthetic_profile),
            "profile_content_hash": synthetic_profile.content_hash,
            "profile_selection_ref": profile_selection_ref,
            "target_world_slot": target_world_slot,
            "target_unit_id": synthetic_profile.rule.unit_id,
            "target_baseline": baseline_state[target_world_slot],
            "outcome_baseline": baseline_state[outcome_variable],
        }
    )
    for field_name in ("outcome_per_target_unit", "outcome_noise_stddev"):
        if field_name in overrides:
            declaration_fields[field_name] = overrides[field_name]
    declaration = _hashed_model(
        type(base_declaration),
        declaration_fields,
        hash_fn=gy_content_hash,
    )
    ncm = candidate_ncm_spec_from_declaration(declaration)
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        ncm_ref = persist_ncm_spec(ensure_ir_artifact_store(store), ncm)
        ncm_ref = ArtifactRef.model_validate(ncm_ref.model_dump(mode="python"))

    base_context_inputs = base_profile.context_inputs
    base_world = base_context_inputs.world_model_record
    materialized_base_world = _materialize_controlled_world_model_record(
        source_world_model_record=base_world,
        artifact_store=store,
        tmp_path=tmp_path,
        source_root=source_root,
        substrate_registry=base_context_inputs.substrate_registry,
        selected_registry_entry_hashes=base_context_inputs.selected_registry_entry_hashes,
        substrate_registry_ref=substrate_registry_ref,
        policy_slot_ids=tuple(
            dict.fromkeys(
                [item.slot_id for item in base_world.policy_slot_map]
                + [target_world_slot, outcome_variable]
            )
        ),
        selected_skg_source=selected_skg_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
        ncm_view_refs=(ncm_ref,),
        candidate_baseline_state=candidate_n5.baseline_state,
        candidate_outcome_state_paths=_controlled_direct_ncm_outcome_state_paths(outcome_variable),
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        world = derive_candidate_scenario_world_model_record(
            materialized_base_world,
            ncm_artifact_ref=ncm_ref,
            declaration_content_hash=declaration.content_hash,
            substrate_registry_view_ref=substrate_registry_ref,
        )
        world_ref = persist_world_model_record(store, world)
        world_ref = ArtifactRef.model_validate(world_ref.model_dump(mode="python"))
        if load_world_model_record(store, world_ref) != world:
            raise ValueError("controlled_generic_profile_wmr_readback_mismatch")

    context_inputs = base_context_inputs.model_copy(update={"world_model_record": world})
    generic_n5 = GenericCycleN5RequestProfileV1(
        budget_ref=base_profile.n5.budget_ref,
        horizon=base_profile.n5.horizon,
        baseline_state=baseline_state,
        comparator_refs=base_profile.n5.comparator_refs,
        seed=base_profile.n5.seed,
        replications=base_profile.n5.replications,
    )
    profile_fields = {
        "profile_id": profile_id,
        "profile_selection_ref": profile_selection_ref,
        "profile_selection_kind": profile_selection_kind,
        "world_model_record_ref": world_ref,
        "substrate_registry_ref": substrate_registry_ref,
        "selected_ncm_ref": ncm_ref,
        "context_inputs": context_inputs,
        "n5": generic_n5,
        "limitations": (
            "controlled_inputs_only",
            "currentness_not_established",
            "n5_simulation_not_world_evidence",
            "n9_not_admitted",
            "s8_blocked",
            "source_truth_not_established",
        ),
    }
    return _hashed_model(
        GenericCycleSimulationProfileV1,
        profile_fields,
        hash_fn=gy_content_hash,
    )


async def prepare_generic_n4_served_replay(
    *,
    tmp_path: Path,
    controlled_candidate_gateway: Any,
    monkeypatch: Any,
    tenant_id: str,
    cell_id: str,
    recording_id: str = _RECORDING_ID,
    child_count: int = 2,
    recording_mode: Literal[
        "controlled_overlay", "original_second_capture", "served_wdi_global_scalar"
    ] = "controlled_overlay",
    runtime_api_context: Any | None = None,
    catalog_serving_source: CatalogServingSourcePaths | None = None,
    runtime_hints_overlay: Mapping[str, object] | None = None,
    phase_callback: Any | None = None,
    candidate_scm_overrides_by_child_index: dict[int, dict[str, float]] | None = None,
    source_root: Path | None = None,
) -> PreparedGenericN4ServedReplay:
    """Derive a source-bound N4 child family and all typed profiles for a served app.

    Controlled-overlay mode retains the existing altered-fixture controls. The
    served-WDI mode reuses the existing fiscal candidate-only recording with one
    global ``government.balance`` lever and a global ``global.tax_rate`` outcome.
    The original-second-capture mode leaves its pinned source bytes unchanged and
    preserves all three dispositions under the min-three diversity gate. Historical
    parent scope remains not established; no mode establishes institutional
    authority, authenticity, or currentness.
    """
    from polisyos.runtime.http.container import RuntimeContainerOverrides
    from polisyos.runtime.http.dependencies import build_runtime_api_context
    from polisyos.runtime.quality import credal_reference, design_generation
    from polisyos.runtime.quality.credal_reference import (
        credal_reference_data_forge_catalog_source_profile,
        credal_reference_l2_source_profile,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        build_cycle_substrate_context,
        cycle_job_design_problem_ref,
        cycle_job_profile_selection_ref,
        generic_n4_child_profile_selection_ref,
    )
    from polisyos.runtime.quality.design_generation import (
        derive_n4_candidate_child_problems,
    )
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort
    from polisyos.runtime.quality.generic_simulation_admission import (
        GenericCycleSimulationProfileV1,
    )
    from polisyos.runtime.quality.substrate_registry import (
        DEFAULT_L3_LEX_KG_PATH,
        catalog_serving_source_scope,
        persist_substrate_registry,
        run_catalog_source_awaitable,
    )
    from tests._helpers.candidate_cycle_source_profile import (
        bind_candidate_cycle_kref_builder_root,
        build_candidate_cycle_catalog_serving_source,
        candidate_cycle_catalog_source_readback,
        candidate_cycle_kref_source_witness,
        install_candidate_cycle_l6_source_root_reader,
    )
    from tests._helpers.runtime_http import _valid_intake_for_mode

    selected_source_root = (
        Path(source_root).resolve(strict=True) if source_root is not None else None
    )
    if selected_source_root == REPO_ROOT.resolve():
        raise ValueError("controlled_n4_candidate_source_root_must_be_fixture_owned")
    source_root_witness: dict[str, Any] = {}

    candidate_scm_overrides = _validated_candidate_scm_overrides_by_child(
        candidate_scm_overrides_by_child_index,
        child_count=child_count,
    )

    monkeypatch.setenv("POLISYOS_EXECUTION_PROFILE", "dev")
    monkeypatch.setenv("POLISYOS_CONTROL_WORKER_BACKEND", "external")
    monkeypatch.setenv("POLISYOS_CONTROL_STATE_STORE_BACKEND", "sqlite")
    monkeypatch.setenv("POLISYOS_CONTROL_SQLITE_PATH", (tmp_path / "control.sqlite3").as_posix())
    monkeypatch.setenv("POLISYOS_CACHE_HOME", (tmp_path / "runtime-cache").as_posix())
    monkeypatch.setenv("JAX_PLATFORMS", "cpu")
    monkeypatch.setenv("OMP_NUM_THREADS", "1")

    catalog_selection = None
    effective_catalog_source = catalog_serving_source
    selected_catalog_readback = None
    l6_source_reads = []
    bind_expected_l6_source = None
    assert_l6_adapter_installed = None
    source_root_witness: dict[str, Any] = {}
    if selected_source_root is not None:
        catalog_selection, selected_catalog_source = build_candidate_cycle_catalog_serving_source(
            selected_source_root
        )
        if catalog_serving_source is not None and (
            catalog_serving_source.repo_root.resolve() != selected_catalog_source.repo_root
            or catalog_serving_source.database_path.resolve()
            != selected_catalog_source.database_path.resolve()
            or catalog_serving_source.catalog_run_profile
            != selected_catalog_source.catalog_run_profile
        ):
            raise ValueError("controlled_n4_selected_catalog_source_conflict")
        effective_catalog_source = selected_catalog_source
        selected_catalog_readback = candidate_cycle_catalog_source_readback(
            effective_catalog_source.database_path
        )
        (
            l6_source_reads,
            bind_expected_l6_source,
            assert_l6_adapter_installed,
        ) = install_candidate_cycle_l6_source_root_reader(
            monkeypatch,
            code_root=REPO_ROOT,
            source_owner_root=selected_source_root,
        )
    source_recordings = n4_contract._load_recordings(REPO_ROOT)
    recorded_problem_override = None
    if recording_mode == "original_second_capture":
        if recording_id != _RECORDING_ID or child_count != 2:
            raise ValueError("original_second_capture_selector_or_child_count_mismatch")
        matches = [
            item
            for item in source_recordings
            if item.get("recording_id") == _ORIGINAL_SECOND_CAPTURE_RECORDING_ID
        ]
        if len(matches) != 1:
            raise RuntimeError("original_second_capture_recording_not_unique")
        source_recording = matches[0]
        if (
            source_recording.get("design_problem_id") != recording_id
            or source_recording.get("recording_content_hash")
            != _ORIGINAL_SECOND_CAPTURE_CONTENT_HASH
        ):
            raise RuntimeError("original_second_capture_identity_or_content_hash_mismatch")
        recording = copy.deepcopy(source_recording)
    elif recording_mode == "controlled_overlay":
        source_recording = next(
            item for item in source_recordings if item.get("design_problem_id") == recording_id
        )
        source_problem = _current_compiler_problem(source_recording)
        if child_count == 2:
            recording = _two_child_recording(
                source_recording,
                outcome_variable=source_problem.outcome_of_interest.target_variable,
            )
        elif child_count == 3:
            recording = _three_child_recording(
                source_recording,
                outcome_variable=source_problem.outcome_of_interest.target_variable,
            )
        else:
            raise ValueError("controlled_n4_child_count_unsupported")
    elif recording_mode == "served_wdi_global_scalar":
        if recording_id != _RECORDING_ID or child_count != 1:
            raise ValueError("served_wdi_global_scalar_selector_or_child_count_mismatch")
        from tests._helpers import acquisition_chain

        source_recording = acquisition_chain.load_served_wdi_generation_recording(REPO_ROOT)
        if source_recording.get("design_problem_id") != recording_id:
            raise RuntimeError("served_wdi_global_scalar_recording_identity_mismatch")
        source_problem = _current_compiler_problem(source_recording)
        recorded_problem_override = acquisition_chain.controlled_served_wdi_problem(
            source_problem,
            raw_request=acquisition_chain.SERVED_WDI_FISCAL_REQUEST,
        )
        recording = acquisition_chain.controlled_served_wdi_generation_recording(
            source_recording,
            outcome_variable=recorded_problem_override.outcome_of_interest.target_variable,
        )
    else:
        raise ValueError("controlled_n4_recording_mode_unsupported")
    _bind_source_recorded_n4_retry_inputs(source_recording, monkeypatch)
    source_recording_snapshot = copy.deepcopy(source_recording)
    source_recording_id = str(source_recording["recording_id"])
    source_recording_content_hash = str(source_recording["recording_content_hash"])
    if recording_mode == "controlled_overlay" and (
        recording.get("recording_source")
        != (
            "synthetic_three_child_overlay_of_recorded_capture"
            if child_count == 3
            else "synthetic_two_child_overlay_of_recorded_capture"
        )
        or recording.get("derived_from_recording_id") != source_recording_id
        or recording.get("derived_from_content_hash") != source_recording_content_hash
    ):
        raise AssertionError("controlled_n4_recording_source_lineage_mismatch")
    if recording_mode == "served_wdi_global_scalar" and (
        recording.get("recording_source") != "synthetic_controlled_overlay_of_recorded_capture"
        or recording.get("derived_from_recording_id") != source_recording_id
        or recording.get("derived_from_content_hash") != source_recording_content_hash
    ):
        raise AssertionError("served_wdi_global_scalar_recording_source_lineage_mismatch")
    if recording_mode == "original_second_capture" and recording != source_recording_snapshot:
        raise AssertionError("original_second_capture_recording_was_mutated")
    recorded_problem = recorded_problem_override or _current_compiler_problem(recording)
    if runtime_hints_overlay:
        recorded_problem = recorded_problem.model_copy(
            update={
                "runtime_hints": {
                    **recorded_problem.runtime_hints,
                    **dict(runtime_hints_overlay),
                }
            }
        )
        recorded_problem = type(recorded_problem).model_validate(
            recorded_problem.model_dump(mode="python")
        )
    controlled_candidate_gateway.set_fixture(
        copy.deepcopy(recording) if recording_mode == "original_second_capture" else recording,
        problem=recorded_problem,
    )
    model_id = str(recording["model_id"])
    cas_root = tmp_path / ".polisyos"
    if runtime_api_context is None:
        runtime_api_context = build_runtime_api_context(
            cas_root=cas_root,
            core_runs_root=cas_root / "runs",
        )
    else:
        cas_root = Path(runtime_api_context.cas_root)

    selected_skg_source = _seed_controlled_selected_skg_source(
        selected_source_root or tmp_path,
        recorded_problem=recorded_problem,
        source_root=selected_source_root,
    )
    selected_skg_db_path = selected_skg_source.db_path
    selected_skg_version_id = selected_skg_source.version_id
    selected_skg_snapshot_ref = selected_skg_source.snapshot_ref
    source_identity_checkpoints = [_validate_controlled_skg_source(selected_skg_source).sha256]
    profile_rule = {}
    if recording_mode == "served_wdi_global_scalar":
        from polisyos.ir.kernel import DEFAULT_SLOT_REGISTRY

        balance_slot = DEFAULT_SLOT_REGISTRY.slots.get("government.balance")
        if balance_slot is None or balance_slot.unit is None:
            raise ValueError("served_wdi_global_scalar_balance_slot_unit_not_registered")
        profile_rule = {
            "rule_operator_kind": "budget_allocation_multiplier",
            "rule_parameter_id": "multiplier",
            "rule_target_world_slot": "government.balance",
            "rule_unit_id": balance_slot.unit.unit_id,
            "rule_minimum": 1,
            "rule_maximum": 2,
            "target_baseline": 0.0,
            "outcome_baseline": 0.0,
        }
    with catalog_serving_source_scope(effective_catalog_source):
        base_profile, base_declaration = _configured_procurement_profile(
            recorded_problem=recorded_problem,
            tmp_path=tmp_path,
            selected_skg_source=selected_skg_source,
            source_root=selected_source_root,
            artifact_store=runtime_api_context.store,
            tenant_id=tenant_id,
            cell_id=cell_id,
            repo_root=selected_source_root,
            **profile_rule,
        )
    base_wmr = base_profile.context_inputs.world_model_record
    if (
        base_wmr.skg_causal_prior_ref.skg_snapshot_ref != selected_skg_snapshot_ref
        or base_wmr.skg_causal_prior_ref.skg_version_id != str(selected_skg_version_id)
    ):
        raise AssertionError("controlled_n4_preflight_wmr_source_not_selected")
    base_inputs = base_profile.context_inputs
    if (
        base_inputs.world_model_record.skg_causal_prior_ref.skg_snapshot_ref
        != selected_skg_snapshot_ref
        or base_inputs.world_model_record.skg_causal_prior_ref.skg_version_id
        != str(selected_skg_version_id)
    ):
        raise AssertionError("controlled_n4_preflight_wmr_source_not_selected")
    preflight_context = build_cycle_substrate_context(
        design_problem_ref=cycle_job_design_problem_ref(recorded_problem),
        domain=recorded_problem.domain,
        substrate_registry=base_inputs.substrate_registry,
        selected_registry_entry_hashes=base_inputs.selected_registry_entry_hashes,
        world_model_record=base_inputs.world_model_record,
        intervention_substrate=base_inputs.intervention_substrate,
        candidate_levers=base_inputs.candidate_levers,
        transport_context=base_inputs.transport_context,
        source_pack_content_hash=base_inputs.source_pack_content_hash,
        substrate_input_content_hash=base_inputs.substrate_input_content_hash,
    )
    _emit_served_phase(phase_callback, "fixture.n4_port.start")
    n4_port = N4GenerationPort(
        model_id=model_id,
        llm_client=n4_contract.RecordedGenerationReplayClient(
            copy.deepcopy(recording) if recording_mode == "original_second_capture" else recording
        ),
        repo_root=selected_source_root or REPO_ROOT,
        cycle_substrate_context=preflight_context,
    )
    selected_l6_bundle = base_profile.context_inputs.intervention_substrate
    selected_l6_witness = None
    l6_read_start = len(l6_source_reads)
    if selected_source_root is not None:
        import hashlib

        from polisyos.runtime.quality.intervention_substrate import default_l6_bundle_paths
        from polisyos.runtime.quality.world_model_record import _parse_skg_snapshot_ref

        if (
            effective_catalog_source is None
            or selected_catalog_readback is None
            or selected_l6_bundle is None
            or bind_expected_l6_source is None
            or assert_l6_adapter_installed is None
        ):
            raise AssertionError("controlled_n4_selected_source_owner_missing")
        selected_l1_path = effective_catalog_source.database_path.resolve(strict=True)
        selected_l2_ref = base_wmr.skg_causal_prior_ref
        parsed_skg = _parse_skg_snapshot_ref(selected_l2_ref.skg_snapshot_ref)
        selected_l2_path = parsed_skg.db_path.resolve(strict=True)
        if (
            not selected_l1_path.is_relative_to(selected_source_root)
            or selected_skg_source.db_path.resolve(strict=True) != selected_l2_path
            or parsed_skg.version_id != selected_skg_source.version_id
        ):
            raise AssertionError("controlled_n4_selected_l1_l2_source_root_mismatch")
        selected_l3_path = (selected_source_root / DEFAULT_L3_LEX_KG_PATH).resolve(strict=True)
        if not selected_l3_path.is_relative_to(selected_source_root):
            raise AssertionError("controlled_n4_selected_l3_path_outside_source_root")
        selected_l3_rows = _candidate_source_l3_row_counts(selected_l3_path)
        if max(selected_l3_rows.values(), default=0) >= 1000:
            raise AssertionError("controlled_n4_selected_l3_fixture_not_bounded")
        selected_l6_paths = default_l6_bundle_paths(
            REPO_ROOT, source_owner_root=selected_source_root
        )
        for name in (
            "intervention_knob_dictionary",
            "lex_intervention_map",
            "observation_to_contract_manifest",
        ):
            if not selected_l6_paths[name].is_file() or not selected_l6_paths[
                name
            ].resolve().is_relative_to(selected_source_root):
                raise AssertionError("controlled_n4_selected_l6_path_unbound:" + name)
        selected_l6_witness = bind_expected_l6_source(selected_l6_bundle)
        if n4_port._repo_root != selected_source_root:
            raise AssertionError("controlled_n4_port_source_root_mismatch")
        if (
            selected_catalog_readback["source_database_sha256"]
            != hashlib.sha256(selected_l1_path.read_bytes()).hexdigest()
        ):
            raise AssertionError("controlled_n4_selected_catalog_bytes_changed_before_n4")
        assert_l6_adapter_installed()
        source_root_witness = {
            "source_root": str(selected_source_root),
            "n4_repo_root": str(n4_port._repo_root),
            "selected_l1_dcat_path": str(selected_l1_path),
            "selected_l1_dcat_sha256": selected_catalog_readback["source_database_sha256"],
            "selected_catalog_readback": selected_catalog_readback,
            "catalog_selection": catalog_selection.model_dump(mode="json"),
            "catalog_source": {
                "repo_root": str(effective_catalog_source.repo_root),
                "snapshot_root": str(effective_catalog_source.snapshot_root),
                "database_path": str(effective_catalog_source.database_path),
                "catalog_run_profile": effective_catalog_source.catalog_run_profile,
                "selection_basis": effective_catalog_source.selection_basis,
            },
            "selected_l2_skg_path": str(selected_l2_path),
            "selected_l2_source_sha256": selected_skg_source.sha256,
            "selected_l2_version_id": parsed_skg.version_id,
            "selected_l3_lex_path": str(selected_l3_path),
            "selected_l3_row_counts": selected_l3_rows,
            "selected_l6_bundle_paths": selected_l6_witness["paths"],
            "selected_l6_path_sha256": selected_l6_witness["file_sha256"],
            "selected_l6_bundle_content_hash": selected_l6_bundle.content_hash,
            "selected_l6_source_witness": selected_l6_witness,
        }
    actual_kref_repo_roots: list[str] = []
    if selected_source_root is not None:
        original_kref_builder = credal_reference.build_credal_reference
        selected_root_kref_builder = bind_candidate_cycle_kref_builder_root(
            original_kref_builder,
            expected_repo_root=selected_source_root,
            observed_repo_roots=actual_kref_repo_roots,
            mismatch_code="controlled_n4_actual_kref_repo_root_mismatch",
        )

        monkeypatch.setattr(
            credal_reference,
            "build_credal_reference",
            selected_root_kref_builder,
        )
        monkeypatch.setattr(
            design_generation,
            "build_credal_reference",
            selected_root_kref_builder,
        )

    n4_awaitable = n4_port(recorded_problem, cycle_index=0)
    organ_run = (
        await run_catalog_source_awaitable(effective_catalog_source, n4_awaitable)
        if effective_catalog_source is not None
        else await n4_awaitable
    )
    _emit_served_phase(phase_callback, "fixture.n4_port.complete")
    selected_reference = organ_run.credal_reference
    if selected_reference is None:
        n4_result = getattr(organ_run, "result", None)
        lever_slice = getattr(n4_result, "lever_space_prompt_slice", None)
        failure_reason = getattr(lever_slice, "failure_reason", None)
        failure_exception_class = (
            failure_reason.partition(":")[2]
            if isinstance(failure_reason, str)
            and failure_reason.startswith("credal_reference_unavailable:")
            else None
        )
        degraded_artifacts = tuple(
            {
                "organ": getattr(item, "organ", None),
                "reason": getattr(item, "reason", None),
            }
            for item in (getattr(n4_result, "degraded_artifacts", ()) or ())
        )
        replayed_calls = tuple(
            {
                "call_index": getattr(item, "call_index", None),
                "role_hint": getattr(item, "role_hint", None),
                "status": getattr(item, "status", None),
                "model_id": getattr(item, "model_id", None),
                "error_type": getattr(item, "error_type", None),
                "error_status": getattr(item, "error_status", None),
            }
            for item in (getattr(n4_result, "llm_calls", ()) or ())
        )
        raise AssertionError(
            "controlled_n4_selected_credal_reference_missing:"
            f"result_status={getattr(n4_result, 'status', None)!r}; "
            f"failure_reason={failure_reason!r}; "
            f"failure_exception_class={failure_exception_class!r}; "
            f"degraded_artifacts={degraded_artifacts!r}; "
            f"replayed_calls={replayed_calls!r}"
        )
    if selected_source_root is not None:
        if (
            effective_catalog_source is None
            or selected_catalog_readback is None
            or selected_l6_bundle is None
            or selected_l6_witness is None
        ):
            raise AssertionError("controlled_n4_actual_source_readback_inputs_missing")
        if not actual_kref_repo_roots:
            raise AssertionError("controlled_n4_actual_kref_builder_not_observed")
        source_root_witness["actual_kref_build_repo_roots"] = actual_kref_repo_roots
        source_root_witness["actual_kref"] = candidate_cycle_kref_source_witness(
            selected_reference,
            source_root=selected_source_root,
            expected_skg_ref=base_inputs.world_model_record.skg_causal_prior_ref,
            catalog_source=effective_catalog_source,
            expected_catalog_readback=selected_catalog_readback,
            expected_l6_bundle=selected_l6_bundle,
            expected_l6_witness=selected_l6_witness,
            actual_l6_reads=l6_source_reads[l6_read_start:],
        )

    selected_source_ref = base_inputs.world_model_record.skg_causal_prior_ref
    selected_source_profile = credal_reference_l2_source_profile(selected_reference)
    if selected_source_profile is None:
        raise AssertionError("controlled_n4_selected_skg_profile_missing")
    if (
        selected_source_profile.selection_owner != "world_model_record.skg_causal_prior_ref"
        or selected_source_profile.skg_causal_prior_ref != selected_source_ref
        or selected_source_profile.source_snapshot_authenticity != "not_established"
        or selected_source_profile.currentness_status != "not_established"
    ):
        raise AssertionError("controlled_n4_selected_skg_source_binding_mismatch")
    if effective_catalog_source is not None:
        catalog_source_profile = credal_reference_data_forge_catalog_source_profile(
            selected_reference
        )
        if (
            catalog_source_profile is None
            or catalog_source_profile.selection_owner != "catalog_serving_source_paths"
            or catalog_source_profile.catalog_run_profile
            != effective_catalog_source.catalog_run_profile
            or catalog_source_profile.selection_basis != effective_catalog_source.selection_basis
            or Path(catalog_source_profile.source_database_path).resolve()
            != effective_catalog_source.database_path.resolve()
        ):
            raise AssertionError("controlled_n4_selected_catalog_source_binding_mismatch")

    generation_result = getattr(organ_run, "result", None)
    if generation_result is None:
        raise AssertionError("controlled_n4_generation_result_missing")
    original_candidate_semantics: dict[str, tuple[str, str, tuple[str, ...]]] | None = None
    if recording_mode == "original_second_capture":
        if recording != source_recording_snapshot or source_recording != source_recording_snapshot:
            raise AssertionError("original_second_capture_recording_was_mutated")
        original_candidate_semantics = _assert_original_second_capture_generation_result(
            generation_result,
            design_problem_ref=cycle_job_design_problem_ref(recorded_problem),
            recording_id=source_recording_id,
            recording_content_hash=source_recording_content_hash,
        )
    children = tuple(
        derive_n4_candidate_child_problems(
            recorded_problem,
            generation_result,
            model_id=model_id,
        )
    )
    if (
        len(children) != child_count
        or len({child.semantic_ref for child in children}) != child_count
    ):
        raise AssertionError("controlled_n4_child_family_not_complete_and_distinct")
    if recording_mode == "original_second_capture":
        if original_candidate_semantics is None:
            raise AssertionError("original_second_capture_candidate_contract_not_loaded")
        _assert_original_second_capture_child_semantic_join(
            children,
            original_candidate_semantics,
        )
    parent_problem_ref = cycle_job_design_problem_ref(recorded_problem)
    child_keys = tuple(
        generic_n4_child_profile_selection_ref(
            child.problem,
            parent_problem_ref=parent_problem_ref,
            source_result_ref=child.source_result_ref,
            source_atom_refs=child.source_atom_refs,
            semantic_ref=child.semantic_ref,
        )
        for child in children
    )
    if len(set(child_keys)) != len(children):
        raise AssertionError("controlled_n4_child_profile_selection_not_unique")
    with pytest.raises(
        ValueError,
        match="generic_cycle_child_profile_selection_lineage_mismatch",
    ):
        generic_n4_child_profile_selection_ref(
            children[0].problem,
            parent_problem_ref=parent_problem_ref,
            source_result_ref=children[0].source_result_ref,
            source_atom_refs=("sha256:" + "f" * 64,),
            semantic_ref=children[0].semantic_ref,
        )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        substrate_registry_ref = persist_substrate_registry(
            runtime_api_context.store,
            base_inputs.substrate_registry,
        )
    generic_child_profiles_list = []
    for index, (child, child_key) in enumerate(zip(children, child_keys, strict=True)):
        _validate_controlled_skg_source(selected_skg_source)
        generic_child_profiles_list.append(
            _generic_profile_for_selection(
                tmp_path=tmp_path,
                source_root=selected_source_root,
                base_profile=base_profile,
                base_declaration=base_declaration,
                profile_id=f"v6-n4-child-{index}",
                profile_selection_ref=child_key,
                profile_selection_kind="n4_candidate_child",
                target_world_slot=child.problem.candidate_lever_space.candidate_levers[
                    0
                ].target_slot,
                operator_kind=child.problem.candidate_lever_space.candidate_levers[0].operator_kind,
                store=runtime_api_context.store,
                substrate_registry_ref=substrate_registry_ref,
                selected_skg_source=selected_skg_source,
                tenant_id=tenant_id,
                cell_id=cell_id,
                candidate_scm_overrides=candidate_scm_overrides.get(index),
            )
        )
        source_identity_checkpoints.append(
            _validate_controlled_skg_source(selected_skg_source).sha256
        )
    generic_child_profiles = tuple(generic_child_profiles_list)
    if any(
        profile.context_inputs.world_model_record.skg_causal_prior_ref != selected_source_ref
        for profile in generic_child_profiles
    ):
        raise AssertionError("controlled_n4_child_profiles_lost_selected_source")
    root_fields = generic_child_profiles[0].model_dump(
        mode="python",
        exclude={"content_hash"},
    )
    root_fields.update(
        {
            "profile_id": "v6-generic-root",
            "profile_selection_ref": cycle_job_profile_selection_ref(recorded_problem),
            "profile_selection_kind": "problem",
        }
    )
    root_profile = _hashed_model(
        type(generic_child_profiles[0]),
        root_fields,
        hash_fn=gy_content_hash,
    )
    source_identity_checkpoints.append(_validate_controlled_skg_source(selected_skg_source).sha256)
    generic_profiles = (root_profile, *generic_child_profiles)
    if any(type(profile) is not GenericCycleSimulationProfileV1 for profile in generic_profiles):
        raise AssertionError("controlled_n4_profile_tuple_not_fully_typed")
    if any(
        profile.context_inputs.world_model_record.skg_causal_prior_ref != selected_source_ref
        for profile in generic_profiles
    ):
        raise AssertionError("controlled_n4_complete_profile_set_lost_selected_source")
    request_json = {
        "request": recorded_problem.nl_provenance.raw_request,
        "llm_model": model_id,
        "context": {
            "evaluation_safety_attempt": _valid_intake_for_mode("simulate_only").model_dump(
                mode="json"
            )
        },
    }
    app_kwargs = {
        "cas_root": cas_root,
        "container_overrides": RuntimeContainerOverrides(runtime_api_context=runtime_api_context),
        "allow_fixture_identity": True,
        "generic_cycle_simulation_profiles": generic_profiles,
        "generic_cycle_simulation_root_profile_id": root_profile.profile_id,
        "repo_root": selected_source_root,
        "catalog_source_selection": catalog_selection,
        "catalog_run_profile": (
            catalog_selection.catalog_run_profile if catalog_selection is not None else None
        ),
    }
    return PreparedGenericN4ServedReplay(
        tmp_path=tmp_path,
        cas_root=cas_root,
        runtime_api_context=runtime_api_context,
        app_kwargs=app_kwargs,
        request_json=request_json,
        recording=recording,
        source_recording_id=source_recording_id,
        source_recording_content_hash=source_recording_content_hash,
        recorded_problem=recorded_problem,
        organ_run=organ_run,
        selected_reference=selected_reference,
        selected_source_ref=selected_source_ref,
        selected_source_profile=selected_source_profile,
        selected_skg_db_path=selected_skg_db_path,
        selected_skg_version_id=selected_skg_version_id,
        selected_skg_snapshot_ref=selected_skg_snapshot_ref,
        selected_skg_source=selected_skg_source,
        selected_skg_source_checkpoints=tuple(source_identity_checkpoints),
        base_profile=base_profile,
        base_declaration=base_declaration,
        generic_profiles=generic_profiles,
        generic_child_profiles=generic_child_profiles,
        children=children,
        child_keys=child_keys,
        root_profile=root_profile,
        model_id=model_id,
        tenant_id=tenant_id,
        cell_id=cell_id,
        source_root=selected_source_root,
        source_root_witness=source_root_witness,
    )


async def run_n4_control_worker_and_get(
    *,
    client: Any,
    app: Any,
    prepared: PreparedGenericN4ServedReplay,
    monkeypatch: Any,
    expected_failure_code: str,
    exercise_projection_controls: bool = True,
    remove_n5_writer: bool = False,
    phase_callback: Any | None = None,
) -> N4ServedRunReceipt:
    """POST, execute the actual control worker, and replay persisted history through GET.

    The clean GET is captured first. Negative control bytes and run-index overrides are
    restored before returning so a separate serving app can read the same run. The optional
    writer-removal control deletes N5 payload bytes inside the real writer call while retaining
    the returned reference and enclosing compiled-run markers.
    """
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
        load_joint_simulation_result,
    )
    from tests._helpers.control_worker import dispatch_one_control_job

    controller_run = GenerationCycleController.run
    child_attempts: list[str] = []
    successful_child_runs: list[Any] = []
    writer_removed_refs: list[ArtifactRef] = []
    actual_failure_code = "v6_controlled_second_n4_child_failure"

    async def fail_second_child(self: Any, *args: Any, **kwargs: Any) -> Any:
        handoff = getattr(self, "_generic_cycle_simulation_handoff", None)
        if handoff is None or handoff.profile.profile_selection_kind != "n4_candidate_child":
            return await controller_run(self, *args, **kwargs)
        child_attempts.append(handoff.profile.profile_id)
        if len(child_attempts) == 2:
            raise GenerationCycleError(
                actual_failure_code,
                "controlled later N4 sibling failure",
            )
        run = await controller_run(self, *args, **kwargs)
        successful_child_runs.append(run)
        return run

    with monkeypatch.context() as scoped:
        scoped.setattr(GenerationCycleController, "run", fail_second_child)
        if remove_n5_writer:
            store = app.state._control_service._artifact_store
            store_type = type(store)
            original_put_json = store_type.put_json

            def put_json_without_n5_payload(
                store_self: Any,
                payload: object,
                options: Any,
                *args: Any,
                **kwargs: Any,
            ) -> Any:
                ref = original_put_json(store_self, payload, options, *args, **kwargs)
                if options.kind == "polisyos.runtime.joint_simulation_result":
                    blob_path, _manifest_path = store_self._paths(
                        ArtifactID.model_validate(ref.artifact_id)
                    )
                    if not blob_path.is_file():
                        raise AssertionError("n5_writer_removal_target_not_written")
                    blob_path.unlink()
                    writer_removed_refs.append(ArtifactRef.model_validate(ref))
                return ref

            scoped.setattr(store_type, "put_json", put_json_without_n5_payload)
        _emit_served_phase(phase_callback, "sibling.post.start")
        response = client.post(
            "/api/v1/control/runs/nl",
            headers={"Idempotency-Key": uuid.uuid4().hex},
            json=prepared.request_json,
        )
        if response.status_code != 200:
            raise AssertionError(f"n4_control_post_failed:{response.text}")
        accepted = response.json()
        if accepted.get("status") != "accepted":
            raise AssertionError("n4_control_post_not_accepted")
        job_id = str(accepted["job_id"])
        _emit_served_phase(phase_callback, "sibling.post.accepted", job_id=job_id)
        service = app.state._control_service
        _emit_served_phase(phase_callback, "sibling.dispatch.start", job_id=job_id)
        dispatched = dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=accepted["job_id"],
        )
        _emit_served_phase(phase_callback, "sibling.dispatch.complete", job_id=job_id)
        if dispatched != accepted["job_id"]:
            raise AssertionError("n4_control_job_not_dispatched")
        job = service._control_store.get_job(accepted["job_id"])
        if job is None or job.state != "completed":
            raise AssertionError("n4_control_job_not_completed")
        run_id = str(job.progress["core_run_id"])
        _emit_served_phase(
            phase_callback, "sibling.fresh_run_get.start", job_id=job_id, run_id=run_id
        )
        get_response = client.get(f"/api/v1/runs/{run_id}")
        _emit_served_phase(
            phase_callback,
            "sibling.fresh_run_get.complete",
            job_id=job_id,
            run_id=run_id,
        )
        if get_response.status_code != 200:
            raise AssertionError(f"n4_fresh_run_get_failed:{get_response.text}")
        get_payload = get_response.json()["run"]
        projection = get_payload["generic_cycle_simulation"]
        observations = [
            row for row in projection["n5_observations"] if row["status"] == "joint_simulated"
        ]
        checkpoint = projection["recursive_cycle_checkpoint"]
        if remove_n5_writer:
            if not writer_removed_refs:
                raise AssertionError("n4_actual_n5_writer_was_not_removed")
            if observations or projection.get("n5_limitation_code") != (
                "generic_n5_persisted_lineage_not_established"
            ):
                raise AssertionError("n4_fresh_get_trusted_n5_marker_without_writer_payload")
            if projection.get("child_profile_status") != "resolved":
                raise AssertionError("n4_writer_removal_lost_selected_child_profile_set")
            failed = checkpoint.get("failed_branches", [])
            if len(failed) != 1 or failed[0].get("error_code") != actual_failure_code:
                raise AssertionError("n4_writer_removal_changed_later_sibling_failure")
            if (
                checkpoint.get("status") != "partial"
                or checkpoint.get("publication_authority") is not False
            ):
                raise AssertionError("n4_writer_removal_checkpoint_status_not_preserved")
            indexed_run = prepared.runtime_api_context.run_index.get_run(run_id)
            if indexed_run is None:
                raise AssertionError("n4_writer_removal_run_index_missing")
            compiled_ref = next(
                ref
                for ref in indexed_run.details.root_artifacts
                if ref.kind == "runtime.compiled_recursive_generation_cycle"
            )
            from polisyos.core import canon
            from polisyos.runtime.http.services.control.generation_cycle import (
                CompiledRecursiveGenerationCycleRun,
            )

            with tenant_scope(
                None,
                tenant_id=prepared.tenant_id,
                cell_id=prepared.cell_id,
            ):
                compiled = CompiledRecursiveGenerationCycleRun.model_validate(
                    canon.from_canonical_bytes(
                        prepared.runtime_api_context.store.get_bytes(compiled_ref)
                    )
                )
            retained_refs = {
                str(node.joint_simulation_ref.artifact_id)
                for node in compiled.recursive_run.nodes
                if node.joint_simulation_ref is not None and node.joint_simulation is not None
            }
            removed_ids = {str(ref.artifact_id) for ref in writer_removed_refs}
            if not removed_ids or not removed_ids.issubset(retained_refs):
                raise AssertionError("n4_writer_removal_did_not_retain_reference_markers")
            missing_ref_error = "joint_simulation_result_unavailable"
            for ref in writer_removed_refs:
                try:
                    load_joint_simulation_result(
                        ref,
                        store=prepared.runtime_api_context.store,
                    )
                except GenerationCycleError as exc:
                    if exc.code != missing_ref_error:
                        raise AssertionError("n4_writer_removal_refusal_code_mismatch") from exc
                else:
                    raise AssertionError("n4_writer_removal_payload_still_resolves")
            return N4ServedRunReceipt(
                accepted_payload=accepted,
                job_id=accepted["job_id"],
                job_state=job.state,
                run_id=run_id,
                failure_code=str(failed[0]["error_code"]),
                failure_message=str(failed[0]["error_message"]),
                get_payload=get_payload,
                projection=projection,
                successful_observation={},
                n5_result_ref=writer_removed_refs[0],
                checkpoint=checkpoint,
                actual_sibling_failure=failed[0],
                child_attempt_profile_ids=tuple(child_attempts),
                successful_child_runs=tuple(successful_child_runs),
                corrupt_projection=None,
                incomplete_profile_projection=None,
                missing_result_ref_error_code=missing_ref_error,
            )
        if not observations:
            raise AssertionError("n4_fresh_run_get_lost_successful_n5_observation")
        successful = observations[0]
        failed = checkpoint.get("failed_branches", [])
        if len(failed) != 1:
            raise AssertionError("n4_fresh_run_get_missing_single_sibling_failure")
        actual_failure = failed[0]
        if actual_failure.get("error_code") != actual_failure_code:
            raise AssertionError("n4_sibling_failure_receipt_not_actual_controlled_failure")
        if len(child_attempts) != len(successful_child_runs) + 1:
            raise AssertionError("n4_controlled_child_attempts_incomplete")
        if expected_failure_code != actual_failure.get("error_code"):
            raise AssertionError("n4_failure_oracle_does_not_match_actual_projection")
        result_ref = ArtifactRef.model_validate(successful["simulation_result_ref"])

        absent_id = "sha256:" + "0" * 64
        if absent_id == str(result_ref.artifact_id):
            absent_id = "sha256:" + "1" * 64
        absent_ref_fields = result_ref.model_dump(mode="python")
        absent_ref_fields["artifact_id"] = ArtifactID.model_validate(absent_id)
        absent_ref = type(result_ref).model_validate(absent_ref_fields)
        try:
            load_joint_simulation_result(
                absent_ref,
                store=prepared.runtime_api_context.store,
                expected_world_model_record_content_hash=(
                    successful["world_model_record_content_hash"]
                ),
                expected_atom_ids=tuple(successful["atom_ids"]),
                expected_selected_outcomes=tuple(successful["selected_outcomes"]),
            )
        except GenerationCycleError as exc:
            missing_ref_error = exc.code
        else:
            raise AssertionError("missing_n5_result_ref_was_not_refused")
        if missing_ref_error != "joint_simulation_result_unavailable":
            raise AssertionError("missing_n5_result_ref_refusal_code_mismatch")

        corrupt_projection: dict[str, Any] | None = None
        incomplete_projection: dict[str, Any] | None = None
        if exercise_projection_controls:
            with tenant_scope(
                None,
                tenant_id=prepared.tenant_id,
                cell_id=prepared.cell_id,
            ):
                blob_path, _manifest_path = service._artifact_store._paths(
                    ArtifactID.model_validate(result_ref.artifact_id)
                )
                original_blob = blob_path.read_bytes()
                try:
                    blob_path.write_bytes(b"controlled-corrupt-result")
                    _emit_served_phase(
                        phase_callback,
                        "sibling.corrupt_get.start",
                        job_id=job_id,
                        run_id=run_id,
                    )
                    corrupt_response = client.get(f"/api/v1/runs/{run_id}")
                    _emit_served_phase(
                        phase_callback,
                        "sibling.corrupt_get.complete",
                        job_id=job_id,
                        run_id=run_id,
                    )
                    if corrupt_response.status_code != 200:
                        raise AssertionError("n4_corrupt_result_get_http_failure")
                    corrupt_projection = corrupt_response.json()["run"]["generic_cycle_simulation"]
                    if (
                        corrupt_projection["child_profile_status"] != "resolved"
                        or corrupt_projection["recursive_cycle_checkpoint"] != checkpoint
                        or corrupt_projection["n5_limitation_code"]
                        != "generic_n5_persisted_lineage_not_established"
                        or any(
                            row["simulation_result_ref"] == successful["simulation_result_ref"]
                            for row in corrupt_projection["n5_observations"]
                        )
                    ):
                        raise AssertionError("n4_corrupt_result_control_not_fail_closed")
                finally:
                    blob_path.write_bytes(original_blob)

            _emit_served_phase(
                phase_callback,
                "sibling.restored_get.start",
                job_id=job_id,
                run_id=run_id,
            )
            restored_response = client.get(f"/api/v1/runs/{run_id}")
            _emit_served_phase(
                phase_callback,
                "sibling.restored_get.complete",
                job_id=job_id,
                run_id=run_id,
            )
            if restored_response.status_code != 200:
                raise AssertionError("n4_restored_result_get_http_failure")
            restored_projection = restored_response.json()["run"]["generic_cycle_simulation"]
            if not any(
                row["simulation_result_ref"] == successful["simulation_result_ref"]
                for row in restored_projection["n5_observations"]
            ):
                raise AssertionError("n4_corrupt_control_did_not_restore_selected_bytes")

            # Keep the persisted run/checkpoint and its N5 reference markers, but
            # remove the selected result bytes. The fresh reader must derive the
            # limitation from the missing CAS payload rather than trusting refs.
            blob_path.unlink()
            try:
                _emit_served_phase(
                    phase_callback,
                    "sibling.removed_result_get.start",
                    job_id=job_id,
                    run_id=run_id,
                )
                removed_response = client.get(f"/api/v1/runs/{run_id}")
                _emit_served_phase(
                    phase_callback,
                    "sibling.removed_result_get.complete",
                    job_id=job_id,
                    run_id=run_id,
                )
                if removed_response.status_code != 200:
                    raise AssertionError("n4_removed_result_get_http_failure")
                removed_projection = removed_response.json()["run"]["generic_cycle_simulation"]
                if (
                    removed_projection["recursive_cycle_checkpoint"] != checkpoint
                    or removed_projection["n5_limitation_code"]
                    != "generic_n5_persisted_lineage_not_established"
                    or any(
                        row["simulation_result_ref"] == successful["simulation_result_ref"]
                        for row in removed_projection["n5_observations"]
                    )
                ):
                    raise AssertionError("n4_removed_result_control_not_fail_closed")
            finally:
                blob_path.write_bytes(original_blob)

            _emit_served_phase(
                phase_callback,
                "sibling.removed_result_restored_get.start",
                job_id=job_id,
                run_id=run_id,
            )
            restored_after_removal = client.get(f"/api/v1/runs/{run_id}")
            _emit_served_phase(
                phase_callback,
                "sibling.removed_result_restored_get.complete",
                job_id=job_id,
                run_id=run_id,
            )
            if restored_after_removal.status_code != 200 or not any(
                row["simulation_result_ref"] == successful["simulation_result_ref"]
                for row in restored_after_removal.json()["run"]["generic_cycle_simulation"][
                    "n5_observations"
                ]
            ):
                raise AssertionError("n4_removed_result_control_did_not_restore_selected_bytes")

            indexed_run = prepared.runtime_api_context.run_index.get_run(run_id)
            if indexed_run is None:
                raise AssertionError("n4_run_index_entry_missing_for_child_control")
            compiled_ref = next(
                ref
                for ref in indexed_run.details.root_artifacts
                if ref.kind == "runtime.compiled_recursive_generation_cycle"
            )
            incomplete_compiled_ref, incomplete_set_ref = (
                _persist_compiled_run_with_incomplete_child_set(
                    store=prepared.runtime_api_context.store,
                    compiled_ref=compiled_ref,
                    tenant_id=prepared.tenant_id,
                    cell_id=prepared.cell_id,
                )
            )
            original_get_run = prepared.runtime_api_context.run_index.get_run
            with monkeypatch.context() as index_scope:

                def run_with_incomplete_child_set(run_id_arg: str) -> Any:
                    indexed = original_get_run(run_id_arg)
                    if run_id_arg != run_id or indexed is None:
                        return indexed
                    altered_roots = tuple(
                        incomplete_compiled_ref if ref == compiled_ref else ref
                        for ref in indexed.details.root_artifacts
                    )
                    return dataclasses.replace(
                        indexed,
                        details=indexed.details.model_copy(
                            update={"root_artifacts": altered_roots}
                        ),
                    )

                index_scope.setattr(
                    prepared.runtime_api_context.run_index,
                    "get_run",
                    run_with_incomplete_child_set,
                )
                _emit_served_phase(
                    phase_callback,
                    "sibling.incomplete_profile_get.start",
                    job_id=job_id,
                    run_id=run_id,
                )
                incomplete_response = client.get(f"/api/v1/runs/{run_id}")
                _emit_served_phase(
                    phase_callback,
                    "sibling.incomplete_profile_get.complete",
                    job_id=job_id,
                    run_id=run_id,
                )
            if incomplete_response.status_code != 200:
                raise AssertionError("n4_incomplete_child_profile_get_http_failure")
            incomplete_projection = incomplete_response.json()["run"]["generic_cycle_simulation"]
            if (
                incomplete_projection["child_profile_status"] != "not_established"
                or incomplete_projection["child_profile_limitation_code"]
                != "generic_n4_child_profile_set_reference_not_established"
                or incomplete_projection["child_profile_set_ref"]["artifact_id"]
                != str(incomplete_set_ref.artifact_id)
                or incomplete_projection["n5_observations"]
                or incomplete_projection["recursive_cycle_checkpoint"] != checkpoint
            ):
                raise AssertionError("n4_incomplete_child_profile_control_not_fail_closed")

    return N4ServedRunReceipt(
        accepted_payload=accepted,
        job_id=accepted["job_id"],
        job_state=job.state,
        run_id=run_id,
        failure_code=str(actual_failure["error_code"]),
        failure_message=str(actual_failure["error_message"]),
        get_payload=get_payload,
        projection=projection,
        successful_observation=successful,
        n5_result_ref=result_ref,
        checkpoint=checkpoint,
        actual_sibling_failure=actual_failure,
        child_attempt_profile_ids=tuple(child_attempts),
        successful_child_runs=tuple(successful_child_runs),
        corrupt_projection=corrupt_projection,
        incomplete_profile_projection=incomplete_projection,
        missing_result_ref_error_code=missing_ref_error,
    )


async def run_n4_budget_stop_worker_and_get(
    *,
    client: Any,
    app: Any,
    prepared: PreparedGenericN4ServedReplay,
    run_budget_usd: float = 0.0,
    phase_callback: Any | None = None,
) -> N4BudgetStopRunReceipt:
    """POST a run-budget request and read the worker result through GET.

    The default zero budget preserves the existing control. A finite budget can
    exercise persisted producer spend in the same served run. The canonical N6
    scheduler and recursive controller produce the terminal; this helper does
    not patch the controller or fabricate checkpoint fields.
    """
    from tests._helpers.control_worker import dispatch_one_control_job

    request_json = {**prepared.request_json, "run_budget_usd": run_budget_usd}
    _emit_served_phase(phase_callback, "budget.post.start")
    response = client.post(
        "/api/v1/control/runs/nl",
        headers={"Idempotency-Key": uuid.uuid4().hex},
        json=request_json,
    )
    if response.status_code != 200:
        raise AssertionError(f"n4_budget_post_failed:{response.text}")
    accepted = response.json()
    if accepted.get("status") != "accepted":
        raise AssertionError("n4_budget_post_not_accepted")
    job_id = str(accepted["job_id"])
    _emit_served_phase(phase_callback, "budget.post.accepted", job_id=job_id)
    service = app.state._control_service
    _emit_served_phase(phase_callback, "budget.dispatch.start", job_id=job_id)
    dispatched = dispatch_one_control_job(
        store=service._control_store,
        handler=service._process_control_job,
        expected_job_id=accepted["job_id"],
    )
    _emit_served_phase(phase_callback, "budget.dispatch.complete", job_id=job_id)
    if dispatched != accepted["job_id"]:
        raise AssertionError("n4_budget_control_job_not_dispatched")
    job = service._control_store.get_job(accepted["job_id"])
    if job is None or job.state != "completed":
        raise AssertionError("n4_budget_control_job_not_completed")
    _emit_served_phase(phase_callback, "budget.job_status_get.start", job_id=job_id)
    job_status_response = client.get(f"/api/v1/control/jobs/{accepted['job_id']}")
    _emit_served_phase(phase_callback, "budget.job_status_get.complete", job_id=job_id)
    if job_status_response.status_code != 200:
        raise AssertionError(f"n4_budget_control_job_get_failed:{job_status_response.text}")
    job_status_payload = job_status_response.json()
    job_progress = job_status_payload.get("progress")
    if (
        job_status_payload.get("job_id") != accepted["job_id"]
        or job_status_payload.get("state") != "completed"
        or not isinstance(job_progress, dict)
        or job_progress.get("recursive_budget_resolution")
        != job.progress.get("recursive_budget_resolution")
    ):
        raise AssertionError("n4_budget_control_job_get_not_bound_to_persisted_resolution")
    run_id = str(job.progress["core_run_id"])
    _emit_served_phase(phase_callback, "budget.fresh_run_get.start", job_id=job_id, run_id=run_id)
    get_response = client.get(f"/api/v1/runs/{run_id}")
    _emit_served_phase(
        phase_callback, "budget.fresh_run_get.complete", job_id=job_id, run_id=run_id
    )
    if get_response.status_code != 200:
        raise AssertionError(f"n4_budget_fresh_get_failed:{get_response.text}")
    get_payload = get_response.json()
    run_payload = get_payload.get("run")
    if not isinstance(run_payload, dict):
        raise AssertionError("n4_budget_fresh_get_run_missing")
    projection = run_payload.get("generic_cycle_simulation")
    if not isinstance(projection, dict):
        raise AssertionError("n4_budget_fresh_get_projection_missing")
    checkpoint = projection.get("recursive_cycle_checkpoint")
    if not isinstance(checkpoint, dict):
        raise AssertionError("n4_budget_fresh_get_checkpoint_missing")
    bindings = projection.get("child_profile_bindings")
    if not isinstance(bindings, list):
        raise AssertionError("n4_budget_child_profile_bindings_missing")
    child_node_refs = tuple(
        sorted(
            str(binding["node_ref"])
            for binding in bindings
            if isinstance(binding, dict) and isinstance(binding.get("node_ref"), str)
        )
    )
    expected_child_count = len(prepared.children)
    if (
        expected_child_count < 1
        or len(child_node_refs) != expected_child_count
        or len(set(child_node_refs)) != expected_child_count
    ):
        raise AssertionError("n4_budget_child_profile_denominator_mismatch")
    return N4BudgetStopRunReceipt(
        accepted_payload=accepted,
        job_id=str(accepted["job_id"]),
        job_state=str(job.state),
        run_id=run_id,
        get_payload=get_payload,
        job_status_payload=job_status_payload,
        projection=projection,
        checkpoint=checkpoint,
        child_node_refs=child_node_refs,
    )
