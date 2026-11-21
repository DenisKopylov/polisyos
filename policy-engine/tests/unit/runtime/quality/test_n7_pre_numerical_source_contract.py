"""Contract controls for the candidate-only pre-numerical N7 source shapes.

The selected refs in these component DTO fixtures are typed identity markers.
They do not claim runtime provenance or stand in for a served Generic N4/N5
producer; that producer replay is covered by the integration boundary.
"""

from __future__ import annotations

import json

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality import acquisition_planner as owner
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    ValuePortObservation,
    _CandidateN5L1RoutingObservation,
)

_V1_SOURCE = "policyos.runtime.n7_configured_candidate_port_source.v1"
_V2_SOURCE = "policyos.runtime.n7_configured_candidate_port_source.v2"
_V3_SOURCE = "policyos.runtime.n7_configured_candidate_port_source.v3"
_MODEL_INPUT_GAP = "policyos.runtime.model_input_obligation_gap.v1"
_V1_LINEAGE = "policyos.runtime.n7_candidate_report_lineage.v1"
_V2_LINEAGE = "policyos.runtime.n7_candidate_report_lineage.v2"

_CANDIDATE_ID = "candidate-pre-numerical-contract"
_CANDIDATE_HASH = "sha256:" + "a" * 64
_PROBLEM_REF = "sha256:" + "b" * 64
_TENANT_ID = "tenant-component-fixture"
_CELL_ID = "cell-component-fixture"


def _selected_ref(kind: str, artifact_digit: str, profile_digit: str) -> ArtifactRef:
    """Return a selected component ref; it is not evidence that an artifact exists."""
    return ArtifactRef(
        artifact_id="sha256:" + artifact_digit * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + profile_digit * 64,
    )


def _pre_numerical_gap(
    *,
    candidate_id: str,
    candidate_content_hash: str,
    design_problem_ref: str,
    obligation_set_ref: ArtifactRef,
    obligation_ref: ArtifactRef,
    report_ref: ArtifactRef,
) -> owner.AcquisitionRequirementGap:
    """Build the exact candidate-bound model-input gap DTO for shape tests."""
    port_id = "opening-cash"
    requirement_ref = "model-input-requirement:opening-cash"
    binding = {
        "candidate_id": candidate_id,
        "candidate_content_hash": candidate_content_hash,
        "design_problem_ref": design_problem_ref,
    }
    metadata = {
        "source": "model_input_obligation",
        "schema_version": _MODEL_INPUT_GAP,
        "authority_purpose": "candidate_acquisition_routing_only",
        "candidate_binding": binding,
        "model_input_obligation_set_ref": obligation_set_ref.model_dump(mode="json"),
        "model_input_obligation_ref": obligation_ref.model_dump(mode="json"),
        "model_input_port_id": port_id,
        "model_input_routing_report_ref": report_ref.model_dump(mode="json"),
        "historical_catalog_absence": "not_established",
        "source_currentness": "not_established",
        "satisfaction_status": "unsatisfied",
    }
    return owner.AcquisitionRequirementGap(
        requirement_gap_id="requirement-gap:model-input:component-fixture",
        requirement_family=owner.RequirementGapFamily.DATA,
        compiled_requirement_ref=requirement_ref,
        requirement_schema_version=_MODEL_INPUT_GAP,
        gap_type=owner.AcquisitionGapType.DATA_SNAPSHOT_RELEASE,
        claim_ref=f"model-input:{candidate_id}:{port_id}",
        scenario_requirement_refs=(design_problem_ref, str(obligation_set_ref.artifact_id)),
        missing_requirement_fields=(f"bound_model_input:{port_id}",),
        authority_level=owner.AuthorityLevel.RESEARCH,
        mandatory_gate_state=owner.MandatoryGateState.NONE,
        mandatory_gate_refs=(requirement_ref,),
        limitation_permitted=False,
        decision_owner_ref="polisyos.runtime.quality.acquisition_planner",
        producer_output_ref=str(obligation_ref.artifact_id),
        metadata=metadata,
    )


def _pre_numerical_payload(
    *,
    candidate_id: str = _CANDIDATE_ID,
    candidate_content_hash: str = _CANDIDATE_HASH,
    design_problem_ref: str = _PROBLEM_REF,
) -> dict[str, object]:
    n4_ref = _selected_ref("runtime.generation_source_handoff", "1", "a")
    context_ref = _selected_ref("runtime.quality.cycle_substrate_context_job", "2", "b")
    input_ref = _selected_ref("runtime.quality.generic_cycle_simulation_n5_input", "3", "c")
    execution_ref = _selected_ref("runtime.quality.generic_cycle_simulation_n5_execution", "4", "d")
    obligation_set_ref = _selected_ref("runtime.quality.model_input_obligation_set", "5", "e")
    obligation_ref = _selected_ref("runtime.quality.model_input_obligation", "6", "f")
    report_ref = _selected_ref("runtime.quality.model_input_routing_report", "7", "1")
    grounding_digest = {
        "candidate_id": candidate_id,
        "issue_codes": ["cgf_disposition_missing"],
        "source": "grounding_unavailable",
    }
    grounding = CandidateGroundingObservation(
        candidate_id=candidate_id,
        status="grounding_unavailable",
        grounding_score=0.0,
        issue_codes=("cgf_disposition_missing",),
        report_ref=gy_content_hash(grounding_digest),
    )
    value = ValuePortObservation(
        candidate_id=candidate_id,
        status="value_pending_n8",
        candidate_n5_l1_routing=None,
        value_ref=None,
    )
    gap = _pre_numerical_gap(
        candidate_id=candidate_id,
        candidate_content_hash=candidate_content_hash,
        design_problem_ref=design_problem_ref,
        obligation_set_ref=obligation_set_ref,
        obligation_ref=obligation_ref,
        report_ref=report_ref,
    )
    return {
        "schema_version": _V3_SOURCE,
        "tenant_id": _TENANT_ID,
        "cell_id": _CELL_ID,
        "run_id": "run-component-fixture",
        "source_job_id": "job-component-fixture",
        "source_generation_run_id": "generation-component-fixture",
        "cycle_index": 0,
        "candidate_id": candidate_id,
        "candidate_content_hash": candidate_content_hash,
        "design_problem_basis_ref": design_problem_ref,
        "n4_source_ref": n4_ref,
        "context_job_ref": context_ref,
        "n5_input_ref": input_ref,
        "n5_execution_ref": execution_ref,
        # V3 names the state of the numerical boundary explicitly. It does not
        # point at an invented joint-simulation result.
        "numerical_execution_status": "unrun",
        "model_input_obligation_set_ref": obligation_set_ref,
        "model_input_obligation_ref": obligation_ref,
        "model_input_routing_report_ref": report_ref,
        "grounding_observation": grounding.model_dump(mode="json"),
        "value_observation": value.model_dump(mode="json"),
        "grounding_digest_payload": grounding_digest,
        "source_gap": gap,
        "accompanying_requirement_gaps": (),
        "observed_admission": False,
        "publication_authority": False,
    }


def _pre_numerical_source(**updates: object) -> owner._N7ConfiguredCandidatePortSource:
    payload = {**_pre_numerical_payload(), **updates}
    return owner._N7ConfiguredCandidatePortSource.model_validate(payload)


def _legacy_source(schema_version: str) -> owner._N7ConfiguredCandidatePortSource:
    """Build the old result-bearing DTO using component refs only."""
    n4_ref = _selected_ref("runtime.quality.n4_candidate_scenario_source", "1", "a")
    context_ref = _selected_ref("runtime.quality.cycle_substrate_context_job", "2", "b")
    input_ref = _selected_ref("runtime.quality.candidate_simulation_n5_input", "3", "c")
    execution_ref = _selected_ref("runtime.quality.candidate_simulation_execution", "4", "d")
    result_ref = _selected_ref("polisyos.runtime.joint_simulation_result", "5", "e")
    candidate_id = "candidate-legacy-component-fixture"
    candidate_hash = "sha256:" + "c" * 64
    problem_ref = "sha256:" + "d" * 64
    source_gap = owner.l1_variable_availability_requirement_gap(
        candidate_id=candidate_id,
        candidate_content_hash=candidate_hash,
        design_problem_ref=problem_ref,
        authority_level=owner.AuthorityLevel.RESEARCH,
        availability=L1VariableAvailability(
            variable_id="global.unemployment_rate",
            status="unavailable",
            dataset_count=0,
            metric_binding_count=0,
            observation_count=0,
            coverage_ref="fixture://legacy-v2-component-coverage",
        ),
    )
    routing = _CandidateN5L1RoutingObservation(
        source_ref=n4_ref,
        context_job_ref=context_ref,
        n5_input_ref=input_ref,
        n5_execution_ref=execution_ref,
        n5_result_ref=result_ref,
        requirement_gap=source_gap,
    )
    grounding = CandidateGroundingObservation(
        candidate_id=candidate_id,
        status="grounding_unavailable",
        grounding_score=0.0,
    )
    value = ValuePortObservation(
        candidate_id=candidate_id,
        authority_blockers=("candidate_scenario_n5_only",),
        candidate_n5_l1_routing=routing,
    )
    payload: dict[str, object] = {
        "schema_version": schema_version,
        "tenant_id": "tenant-legacy-component-fixture",
        "cell_id": "cell-legacy-component-fixture",
        "run_id": "run-legacy-component-fixture",
        "source_job_id": "job-legacy-component-fixture",
        "source_generation_run_id": "generation-legacy-component-fixture",
        "cycle_index": 0,
        "candidate_id": candidate_id,
        "candidate_content_hash": candidate_hash,
        "design_problem_basis_ref": problem_ref,
        "n4_source_ref": n4_ref,
        "context_job_ref": context_ref,
        "n5_input_ref": input_ref,
        "n5_execution_ref": execution_ref,
        "n5_result_ref": result_ref,
        "grounding_observation": grounding.model_dump(mode="json"),
        "value_observation": value.model_dump(mode="json"),
        "grounding_digest_payload": None,
        "source_gap": source_gap,
        "accompanying_requirement_gaps": (),
        "observed_admission": False,
        "publication_authority": False,
    }
    if schema_version == _V2_SOURCE:
        payload["derivation_bundle_ref"] = _selected_ref(
            "runtime.quality.n7_derivation_bundle", "6", "f"
        )
    return owner._N7ConfiguredCandidatePortSource.model_validate(payload)


def test_v3_accepts_selected_generic_pre_numerical_shape_and_exact_digest() -> None:
    source = _pre_numerical_source()
    wire = source.model_dump(mode="json")

    assert source.schema_version == _V3_SOURCE
    assert source.numerical_execution_status == "unrun"
    assert source.n5_result_ref is None
    assert "n5_result_ref" not in wire
    assert source.n4_source_ref.kind == "runtime.generation_source_handoff"
    assert source.n5_input_ref.kind == "runtime.quality.generic_cycle_simulation_n5_input"
    assert source.n5_execution_ref.kind == "runtime.quality.generic_cycle_simulation_n5_execution"
    assert source.source_gap.requirement_schema_version == _MODEL_INPUT_GAP
    assert source.source_gap.metadata["source"] == "model_input_obligation"
    assert source.source_gap.metadata["candidate_binding"] == {
        "candidate_id": source.candidate_id,
        "candidate_content_hash": source.candidate_content_hash,
        "design_problem_ref": source.design_problem_basis_ref,
    }
    assert source.source_gap.metadata["historical_catalog_absence"] == "not_established"
    assert source.source_gap.metadata["source_currentness"] == "not_established"
    assert (
        source.model_input_obligation_set_ref.kind == "runtime.quality.model_input_obligation_set"
    )
    assert source.model_input_obligation_ref.kind == "runtime.quality.model_input_obligation"
    assert (
        source.model_input_routing_report_ref.kind == "runtime.quality.model_input_routing_report"
    )
    assert source.grounding_digest_payload == {
        "candidate_id": source.candidate_id,
        "issue_codes": ["cgf_disposition_missing"],
        "source": "grounding_unavailable",
    }
    assert (
        gy_content_hash(source.grounding_digest_payload)
        == source.grounding_observation["report_ref"]
    )
    assert source.value_observation["status"] == "value_pending_n8"
    assert source.value_observation.get("candidate_n5_l1_routing") is None
    assert source.observed_admission is False
    assert source.publication_authority is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "n5_result_ref",
            _selected_ref("polisyos.runtime.joint_simulation_result", "8", "9"),
        ),
        (
            "n5_input_ref",
            _selected_ref("runtime.quality.candidate_simulation_n5_input", "8", "9"),
        ),
        (
            "n5_execution_ref",
            _selected_ref("runtime.quality.candidate_simulation_execution", "8", "9"),
        ),
        (
            "model_input_obligation_set_ref",
            _selected_ref("runtime.quality.model_input_obligation", "8", "9"),
        ),
        (
            "model_input_routing_report_ref",
            ArtifactRef(
                artifact_id="sha256:" + "8" * 64,
                kind="runtime.quality.model_input_routing_report",
                media_type="application/json",
            ),
        ),
    ],
)
def test_v3_refuses_invented_result_wrong_generic_kind_and_unselected_refs(
    field: str, value: object
) -> None:
    with pytest.raises(ValueError, match="n7_pre_numerical_source_selected_inputs_invalid"):
        _pre_numerical_source(**{field: value})


def test_v3_refuses_foreign_candidate_binding_and_legacy_result_routing() -> None:
    source = _pre_numerical_source()
    gap_payload = source.source_gap.model_dump(mode="json")
    gap_payload["metadata"]["candidate_binding"] = {
        "candidate_id": "candidate-foreign",
        "candidate_content_hash": source.candidate_content_hash,
        "design_problem_ref": source.design_problem_basis_ref,
    }
    foreign_gap = owner.AcquisitionRequirementGap.model_validate(gap_payload)
    payload = source.model_dump(mode="python")
    payload["source_gap"] = foreign_gap

    with pytest.raises(ValueError, match="n7_pre_numerical_source_subject_mismatch"):
        owner._N7ConfiguredCandidatePortSource.model_validate(payload)

    payload = source.model_dump(mode="python")
    payload["candidate_id"] = "candidate-foreign"
    with pytest.raises(ValueError, match="n7_pre_numerical_source_subject_mismatch"):
        owner._N7ConfiguredCandidatePortSource.model_validate(payload)


@pytest.mark.parametrize("schema_version", [_V1_SOURCE, _V2_SOURCE])
def test_legacy_sources_remain_result_bearing_and_do_not_emit_v3_fields(
    schema_version: str,
) -> None:
    source = _legacy_source(schema_version)
    wire = source.model_dump(mode="json")
    new_fields = {
        "numerical_execution_status",
        "model_input_obligation_set_ref",
        "model_input_obligation_ref",
        "model_input_routing_report_ref",
    }

    assert source.n5_result_ref is not None
    assert source.n4_source_ref.kind == "runtime.quality.n4_candidate_scenario_source"
    assert source.n5_input_ref.kind == "runtime.quality.candidate_simulation_n5_input"
    assert source.n5_execution_ref.kind == "runtime.quality.candidate_simulation_execution"
    assert source.n5_result_ref.kind == "polisyos.runtime.joint_simulation_result"
    assert not new_fields.intersection(wire)


def test_legacy_v2_literal_wire_projection_stays_result_bearing() -> None:
    """Pin old v2 discriminants/kinds; refs below are component markers only."""
    # This literal is the old v2 wire projection, not a served artifact or
    # provenance claim. The complete typed payload is checked separately above.
    golden = json.loads(
        """{
          "authority_purpose": "recorded_candidate_routing_only",
          "derivation_bundle_ref": {
            "artifact_id": "sha256:6666666666666666666666666666666666666666666666666666666666666666",
            "kind": "runtime.quality.n7_derivation_bundle",
            "manifest_profile_sha256": "sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "media_type": "application/json"
          },
          "execution_scope": "configured_candidate",
          "n4_source_ref": {
            "artifact_id": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
            "kind": "runtime.quality.n4_candidate_scenario_source",
            "manifest_profile_sha256": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "media_type": "application/json"
          },
          "n5_execution_ref": {
            "artifact_id": "sha256:4444444444444444444444444444444444444444444444444444444444444444",
            "kind": "runtime.quality.candidate_simulation_execution",
            "manifest_profile_sha256": "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "media_type": "application/json"
          },
          "n5_input_ref": {
            "artifact_id": "sha256:3333333333333333333333333333333333333333333333333333333333333333",
            "kind": "runtime.quality.candidate_simulation_n5_input",
            "manifest_profile_sha256": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "media_type": "application/json"
          },
          "n5_result_ref": {
            "artifact_id": "sha256:5555555555555555555555555555555555555555555555555555555555555555",
            "kind": "polisyos.runtime.joint_simulation_result",
            "manifest_profile_sha256": "sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            "media_type": "application/json"
          },
          "schema_version": "policyos.runtime.n7_configured_candidate_port_source.v2"
        }"""
    )
    source = _legacy_source(_V2_SOURCE)
    wire = source.model_dump(mode="json")
    projection = {
        "authority_purpose": wire["authority_purpose"],
        "derivation_bundle_ref": wire["derivation_bundle_ref"],
        "execution_scope": wire["execution_scope"],
        "n4_source_ref": wire["n4_source_ref"],
        "n5_execution_ref": wire["n5_execution_ref"],
        "n5_input_ref": wire["n5_input_ref"],
        "n5_result_ref": wire["n5_result_ref"],
        "schema_version": wire["schema_version"],
    }

    canonical_projection = json.dumps(projection, sort_keys=True, separators=(",", ":"))
    canonical_golden = json.dumps(golden, sort_keys=True, separators=(",", ":"))
    assert canonical_projection == canonical_golden
    assert "numerical_execution_status" not in wire
    assert "model_input_obligation_set_ref" not in wire


def test_legacy_sources_reject_explicit_pre_numerical_fields() -> None:
    legacy = _legacy_source(_V2_SOURCE)
    payload = legacy.model_dump(mode="python")
    payload["numerical_execution_status"] = "unrun"
    payload["model_input_obligation_set_ref"] = _selected_ref(
        "runtime.quality.model_input_obligation_set", "8", "9"
    )

    with pytest.raises(ValueError, match="n7_legacy_port_source_pre_numerical_fields_forbidden"):
        owner._N7ConfiguredCandidatePortSource.model_validate(payload)


def test_report_lineage_v2_requires_selected_model_compilation_and_v1_forbids_even_none() -> None:
    lineage_type = owner._N7CandidateReportLineage
    source_ref = _selected_ref("runtime.quality.n7_configured_candidate_port_source", "1", "a")
    compilation_ref = _selected_ref("data_requirement.model_input_compilation", "2", "b")

    selected = lineage_type.model_validate(
        {
            "schema_version": _V2_LINEAGE,
            "port_source_ref": source_ref,
            "bindings": (),
            "model_input_compilation_ref": compilation_ref,
        }
    )
    assert selected.model_input_compilation_ref == compilation_ref

    with pytest.raises(ValueError, match="n7_legacy_lineage_model_input_compiler_forbidden"):
        lineage_type.model_validate(
            {
                "schema_version": _V1_LINEAGE,
                "port_source_ref": source_ref,
                "bindings": (),
                "model_input_compilation_ref": None,
            }
        )

    with pytest.raises(ValueError, match="n7_model_input_compiler_ref_unselected"):
        lineage_type.model_validate(
            {
                "schema_version": _V2_LINEAGE,
                "port_source_ref": source_ref,
                "bindings": (),
                "model_input_compilation_ref": ArtifactRef(
                    artifact_id="sha256:" + "2" * 64,
                    kind="data_requirement.model_input_compilation",
                    media_type="application/json",
                ),
            }
        )


def test_pre_numerical_cycle_report_uses_only_its_narrow_wire_epoch() -> None:
    """A DTO-level plan is candidate routing, without a simulated result or N8 gap."""
    from polisyos.runtime.quality import generation_cycle as generation
    from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import (
        _ref,
        _routed_payload,
    )

    payload = _routed_payload()
    payload["schema_version"] = generation._GENERATION_CYCLE_MODEL_INPUT_ACQUISITION_SCHEMA_VERSION
    cycle = payload["cycles"][0]
    cycle["model_input_acquisition_report_ref"] = _ref(
        owner.ACQUISITION_PLANNER_KIND, "pre-numerical-plan-component-only"
    )
    run = generation.GenerationCycleRun.model_validate(payload)
    assert run.cycles[0].simulation.status == "simulation_blocked"
    assert run.cycles[0].simulation.simulation_result_ref is None
    assert run.cycles[0].acquisition_routing_report_ref is None
    assert run.model_dump(mode="json")["cycles"][0]["model_input_acquisition_report_ref"]
    assert (
        generation._generation_cycle_run_schema_version(
            cycles=run.cycles,
            candidate_summaries=run.candidate_summaries,
            basis_transitions=run.basis_transitions,
        )
        == generation._GENERATION_CYCLE_MODEL_INPUT_ACQUISITION_SCHEMA_VERSION
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("selection", "expected_reason"),
    [
        ("exact", "acquisition_reentry_overlay_receipt_invalid"),
        ("other_profile", "native_derivation_reentry_model_input_source_mismatch"),
        ("other_port", "native_derivation_reentry_model_input_source_mismatch"),
        ("absent", "native_derivation_reentry_model_input_source_mismatch"),
        ("legacy", "acquisition_reentry_source_not_acquisition_terminal"),
        ("non_native", "acquisition_reentry_source_not_acquisition_terminal"),
    ],
)
async def test_active_native_reentry_requires_exact_pre_numerical_source(
    tmp_path, monkeypatch, selection: str, expected_reason: str
) -> None:
    """Run the stock controller and lease with the surrounding owners isolated."""
    from contextlib import closing
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from polisyos.core import artifacts
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
    from polisyos.runtime.quality import acquisition_world_growth as world_growth
    from polisyos.runtime.quality import generation_cycle as generation
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionRouteLoop,
        VerifiedAcquisitionRouteClosure,
    )
    from polisyos.scientist import BudgetState
    from tests.unit.runtime.http.test_control_plane_store_evaluation_frontier import (
        _create_action_job,
    )
    from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import _routed_payload
    from tests.unit.runtime.quality.test_native_derivation_leaf_cost_profile import _profile_scope

    cas = artifacts.FileSystemCAS(tmp_path / "cas")
    scope, _quote = _profile_scope(cas)
    pre_numerical = selection != "legacy"
    lineage = owner._N7CandidateReportLineage(
        schema_version=_V2_LINEAGE if pre_numerical else _V1_LINEAGE,
        port_source_ref=scope.configured_port_source_ref,
        bindings=(),
        **(
            {
                "model_input_compilation_ref": _selected_ref(
                    "data_requirement.model_input_compilation", "2", "b"
                )
            }
            if pre_numerical
            else {}
        ),
    )
    report = owner.AcquisitionPlannerReport(
        schema_version=owner._N7_CONFIGURED_REPORT_SCHEMA,
        run_id="n7-pre-numerical-component",
        generated_at=datetime.now(UTC),
        status="pass",
        candidate_lineage=lineage,
    )
    report_refs = tuple(
        cas.put_json(
            report.model_dump(mode="json"),
            artifacts.ArtifactWriteOptions(
                kind=owner.ACQUISITION_PLANNER_KIND,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name="test.selected_planner_report", version=version),
            ),
            return_selected_profile=True,
        )
        for version in ("1.0", "2.0")
    )
    report_ref, other_view = report_refs
    assert report_ref.artifact_id == other_view.artifact_id
    assert report_ref.manifest_profile_sha256 != other_view.manifest_profile_sha256
    assert cas.get_bytes(report_ref) == cas.get_bytes(other_view)

    payload = _routed_payload()
    cycle_payload = payload["cycles"][0]
    problem = generation.DesignProblem.model_validate(
        cycle_payload["revision_request"]["revised_problem"]
    )
    basis_ref = generation._problem_ref(problem)
    payload["design_problem_ref"] = basis_ref
    payload["cycles"] = [cycle_payload]
    cycle_payload.update(design_problem_ref=basis_ref, design_problem_basis_ref=basis_ref)
    summary = generation.CandidateSummary.model_validate(payload["candidate_summaries"][0])
    payload["candidate_summaries"] = [summary]
    payload["fronts"] = generation._derive_fronts((summary,))
    if selection != "absent":
        payload["schema_version"] = (
            generation._GENERATION_CYCLE_MODEL_INPUT_ACQUISITION_SCHEMA_VERSION
        )
        cycle_payload["model_input_acquisition_report_ref"] = report_ref
    original = generation.GenerationCycleRun.model_validate(payload)
    (cycle,) = original.cycles
    assert cycle.terminal_kind == "search_ceiling_repair_required"
    assert cycle.acquisition_routing_report is None
    assert cycle.simulation.status == "simulation_blocked"
    collection_ref = _selected_ref("runtime_quality.native_derivation_input_collection", "3", "c")
    context = SimpleNamespace(world_model_record=object())
    requirement = _pre_numerical_source().source_gap
    selected_scope = scope.model_copy(
        update={
            "planner_report_ref": other_view if selection == "other_profile" else report_ref,
            "configured_port_source_ref": (
                _selected_ref("runtime.quality.n7_configured_candidate_port_source", "9", "a")
                if selection == "other_port"
                else scope.configured_port_source_ref
            ),
        },
    )
    route = VerifiedAcquisitionRouteClosure.model_construct(
        run_id=scope.run_id,
        route_id="sha256:" + "c" * 64,
        design_problem_ref=basis_ref,
        design_problem=problem,
        generation_run=original,
        source_cycle=cycle,
        route_source_cycle_index=cycle.cycle_index,
        planner_report=report,
        native_derivation_leaf_scope=selected_scope,
        cost_basis_record=object(),
    )
    checks: list[ArtifactRef] = []

    def verify_collection(store, *, closure, collection_ref, world_model):
        assert store is cas and closure is route and world_model is context.world_model_record
        checks.append(collection_ref)
        return requirement

    monkeypatch.setattr(
        world_growth, "verify_native_derivation_reentry_collection", verify_collection
    )
    with closing(
        ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    ) as store:
        action, worker, attempt = _create_action_job(store, job_id="native-reentry")
        service = object.__new__(ControlPlaneService)
        service._artifact_store = cas
        service._control_store = store
        service._acquisition_route_sink = None
        service._diagnostic_event_log = None
        controller = object.__new__(generation.GenerationCycleController)
        controller._artifact_store = cas
        controller._cycle_substrate_context = context

        def resolved_route(reader, *, run_id, route_id, action_job_id):
            assert reader._control_store is store
            assert (run_id, route_id, action_job_id) == (
                scope.run_id,
                route.route_id,
                action.job_id,
            )
            return route

        monkeypatch.setattr(AcquisitionRouteLoop, "resolve_current_route", resolved_route)
        native = selection != "non_native"
        with (
            store.job_execution_fence(job_id=action.job_id, worker_id=worker, attempt=attempt),
            pytest.raises(generation.GenerationCycleError) as refusal,
        ):
            await controller.reenter_after_active_acquisition_overlay(
                original_run=original,
                source_cycle=cycle,
                problem=problem,
                source_control_service=service if native else None,
                action_route_id=route.route_id if native else None,
                native_input_collection_ref=collection_ref if native else None,
                overlay_receipt=None,
                observation_projection=None,
                overlay_path=tmp_path / "no-overlay",
                baseline_path=tmp_path / "no-baseline",
                budget_state=BudgetState(),
            )
        assert refusal.value.code == expected_reason
    assert checks == ([collection_ref] if selection == "exact" else [])


@pytest.mark.parametrize("supplied", [None, "selected"])
def test_old_cycle_wire_rejects_even_null_new_acquisition_field(supplied: str | None) -> None:
    from polisyos.runtime.quality import generation_cycle as generation
    from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import (
        _ref,
        _routed_payload,
    )

    payload = _routed_payload()
    payload["cycles"][0]["model_input_acquisition_report_ref"] = (
        _ref(owner.ACQUISITION_PLANNER_KIND, "new-report") if supplied else None
    )
    with pytest.raises(ValueError, match="generation_cycle_model_input_acquisition_requires_v11"):
        generation.GenerationCycleRun.model_validate(payload)


def test_v11_refuses_route_without_an_actual_acquisition_report() -> None:
    from polisyos.runtime.quality import generation_cycle as generation
    from tests.unit.runtime.quality.test_generation_cycle_model_input_wire import _routed_payload

    payload = _routed_payload()
    payload["schema_version"] = generation._GENERATION_CYCLE_MODEL_INPUT_ACQUISITION_SCHEMA_VERSION
    with pytest.raises(ValueError, match="generation_cycle_v11_requires_model_input_acquisition"):
        generation.GenerationCycleRun.model_validate(payload)
