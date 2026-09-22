"""ACQ-01 regression coverage for the N7 requirement handoff."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
import pytest
from polisyos.data_requirement import (
    DataQualityMinimums,
    DataRequirementScope,
    DataRequirementSpec,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionCaptureProvenance,
    AcquisitionOwnerArtifact,
    AcquisitionWorldSnapshot,
    RecordedAcquisitionOwnerGateway,
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.design_problem import (
    CandidateLever,
    CandidateLeverSpace,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    JointSimulationPort,
    SimulationPortObservation,
    ValuePortObservation,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState

REPO_ROOT = Path(__file__).resolve().parents[3]


def _problem(
    *,
    problem_id: str = "acq_case",
    statement: str = "Ground firm survival with an owner-backed data source.",
    domain: str = "generic_policy",
    runtime_hints: dict[str, Any] | None = None,
) -> DesignProblem:
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement=statement,
        domain=domain,
        nl_provenance=NLProvenance(
            raw_request=statement,
            source_surface="test_acq_01",
        ),
        authority_profile={
            "requester_authority": "research_lab",
            "requested_authority_level": "research",
            "mandate": "test-only acquisition handoff",
        },
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-09-21",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="firm_survival",
                description="Improve firm survival",
                metric_id="firm_survival",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="firm_survival",
            metric_id="firm_survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(),
        runtime_hints=runtime_hints or {},
    )


def test_n7_explicit_specs_take_precedence_and_preserve_empty_primary() -> None:
    hinted = ({"source": "runtime-hint"},)
    alias = ({"source": "compiled-alias"},)
    explicit = ({"source": "explicit"},)
    controller = GenerationCycleController()
    problem = _problem(runtime_hints={"n7_data_requirement_specs": hinted})

    assert (
        controller._n7_data_requirement_specs(
            problem,
            acquisition_request={
                "data_requirement_specs": explicit,
                "compiled_requirement_specs": alias,
            },
        )
        == explicit
    )
    assert (
        controller._n7_data_requirement_specs(
            problem,
            acquisition_request={
                "data_requirement_specs": (),
                "compiled_requirement_specs": alias,
            },
        )
        == ()
    )
    assert (
        controller._n7_data_requirement_specs(
            problem,
            acquisition_request={"compiled_requirement_specs": alias},
        )
        == alias
    )


def test_n7_typed_any_of_gap_precedes_explicit_specs() -> None:
    gap = value_input_world_knowledge_requirement_gap(claim_ref="claim:acq")
    controller = GenerationCycleController()

    specs = controller._n7_data_requirement_specs(
        _problem(),
        acquisition_request={
            "requirement_gap": gap.model_dump(mode="json"),
            "data_requirement_specs": ({"source": "must-not-replace-gap"},),
            "compiled_requirement_specs": ({"source": "stale-alias"},),
        },
    )

    assert len(specs) == 1
    assert specs[0] == gap


def test_n7_fallback_handoff_preserves_statement_domain_scope_and_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _ResolverPort:
        def resolve(self, _query: object) -> object:
            return object()

    resolver = _ResolverPort()
    captured: list[tuple[object, dict[str, Any]]] = []

    class _RecordingCompiler:
        def __init__(self, *, capability_resolver: object | None = None) -> None:
            captured.append((capability_resolver, {}))

        def compile_for_scenario(self, scenario: dict[str, Any]) -> SimpleNamespace:
            resolver_arg, _ = captured[-1]
            captured[-1] = (resolver_arg, scenario)
            return SimpleNamespace(specs=())

    monkeypatch.setattr(generation_cycle_module, "DataRequirementCompiler", _RecordingCompiler)
    controller = GenerationCycleController(capability_resolver=resolver)
    scope_a = {
        "profile_id": "pilot:ua:2026",
        "jurisdiction": "UA",
        "time_window": {"start": "2026-01-01", "end": "2026-12-31"},
    }
    scope_b = {
        "profile_id": "pilot:pl:2027",
        "jurisdiction": "PL",
        "time_window": {"start": "2027-01-01", "end": "2027-12-31"},
    }

    controller._n7_data_requirement_specs(
        _problem(
            statement="Ground employment retention for Ukrainian firms.",
            domain="fiscal_policy",
        ),
        acquisition_request={
            "required_data_families": ("firm_panel",),
            "scope_profile": scope_a,
        },
    )
    controller._n7_data_requirement_specs(
        _problem(
            statement="Ground school attendance for Polish districts.",
            domain="education_policy",
        ),
        acquisition_request={
            "required_data_families": ("attendance_panel",),
            "scope_profile": scope_b,
        },
    )

    assert len(captured) == 2
    assert all(item[0] is resolver for item in captured)
    first, second = (item[1] for item in captured)
    assert first["text"] != second["text"]
    assert first["domain"] != second["domain"]
    assert first["scenario_profile"] == scope_a
    assert second["scenario_profile"] == scope_b


def test_n7_missing_resolver_or_empty_specs_does_not_call_closed_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    compiler_args: list[object | None] = []

    class _EmptyCompiler:
        def __init__(self, *, capability_resolver: object | None = None) -> None:
            compiler_args.append(capability_resolver)

        def compile_for_scenario(self, _scenario: dict[str, Any]) -> SimpleNamespace:
            return SimpleNamespace(specs=())

    monkeypatch.setattr(generation_cycle_module, "DataRequirementCompiler", _EmptyCompiler)
    controller = GenerationCycleController(repo_root=tmp_path)
    problem = _problem()
    assert (
        controller._n7_data_requirement_specs(
            problem,
            acquisition_request={"required_data_families": ("unresolved_family",)},
        )
        == ()
    )
    assert compiler_args == [None]

    monkeypatch.setattr(
        controller,
        "_n7_world_snapshot",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(controller, "_n7_owner_gateway", lambda *_args: object())

    def _unexpected_closed_loop(**_kwargs: object) -> object:
        raise AssertionError("empty specs must not mint an acquisition receipt")

    monkeypatch.setattr(
        generation_cycle_module,
        "run_acquisition_closed_loop",
        _unexpected_closed_loop,
    )
    cycle = SimpleNamespace(
        terminal_kind="acquisition_required",
        cycle_index=0,
        revision_request=SimpleNamespace(
            strategy_payload={
                "acquisition_request": {
                    "required_data_families": ("unresolved_family",),
                }
            }
        ),
    )

    assert controller._run_n7_acquisition_if_requested(problem, cycle=cycle) is None


class _FixtureGenerationPort:
    async def __call__(self, problem: DesignProblem, *, cycle_index: int) -> Any:
        del cycle_index
        candidate = _fixture_candidate(problem, world_ref="world://before/acq-01")
        return SimpleNamespace(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                SimpleNamespace(
                    candidate_id=candidate.candidate_id,
                    score=0.2,
                    voi_estimate=0.2,
                ),
            ),
            grounding_dispositions=(),
        )


class _FixtureAcquisitionGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.1,
            issue_codes=("acquire_data:fixture_panel",),
            current_valid=False,
        )


class _WorldBoundSimulation:
    def __init__(self) -> None:
        self.world_refs: list[str] = []

    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        del problem, cycle_index
        atom = candidate.atom
        from polisyos.runtime.quality.intervention_atom_binding import (
            InterventionAtomBinding,
        )

        assert isinstance(atom, InterventionAtomBinding)
        world_ref = str(atom.world_model_record_ref)
        self.world_refs.append(world_ref)
        return SimulationPortObservation(
            candidate_id=str(candidate.candidate_id),
            status="joint_simulated",
            simulation_ref=f"fixture-simulation:{world_ref}",
            k_world_ref_before=world_ref,
            k_world_ref_after=world_ref,
        )


class _PendingFixtureValue:
    def __call__(
        self,
        *,
        candidate: Any,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        del simulation, problem, cycle_index
        return ValuePortObservation(
            status="value_pending_n8",
            candidate_id=str(candidate.candidate_id),
            reason="fixture acquisition test leaves N8 pending",
        )


def _fixture_candidate(problem: DesignProblem, *, world_ref: str) -> Any:
    """Return a content-valid canonical atom for the bounded ACQ fixture."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    payload = json.loads(
        (
            REPO_ROOT / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
        ).read_text(encoding="utf-8")
    )
    raw_candidate = n4_contract.first_shadow_bound_recorded_candidate(payload)
    atom = InterventionAtomBinding.model_validate(raw_candidate["atom"])
    atom = atom.model_copy(
        update={
            "problem_frame_ref": gy_content_hash(problem.model_dump(mode="json")),
            "target_world_slots": ("fixture_panel",),
            "normalized_from": None,
            "world_model_record_ref": world_ref,
        }
    )
    atom = atom.model_copy(
        update={
            "atom_id": (
                f"atom_{intervention_atom_content_hash(atom).removeprefix('sha256:')[:16]}"
            ),
            "content_hash": intervention_atom_content_hash(atom),
        }
    )
    atom = InterventionAtomBinding.model_validate(atom.model_dump(mode="python"))
    return SimpleNamespace(
        candidate_id="candidate_fixture_panel",
        atom=atom,
        intervention_atoms=(atom,),
        diversity_key=("grant", "firms", "fixture", "baseline"),
    )


def test_n7_reentry_candidate_is_accepted_by_real_n5_request_builder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The re-entry shell supplies a canonical atom to the existing N5 seam."""

    problem = _problem(
        problem_id="acq_01_n5_shape",
        runtime_hints={
            "joint_simulation_resource": "method_registry_estimator",
            "joint_simulation_budget_ref": "budget://acq-01/n5-shape",
            "joint_simulation_horizon": {"start": 0, "end": 1, "step": 1},
        },
    )
    registry = _fixture_world_registry()
    world = generation_cycle_module._build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("fixture_panel",),
        substrate_registry=registry,
        selected_registry_entry_hashes=(registry.entries[0].entry_content_hash,),
    )
    candidate = _fixture_candidate(problem, world_ref=world.world_model_record_id)
    port = JointSimulationPort(repo_root=REPO_ROOT)
    monkeypatch.setattr(
        port,
        "_boundary_world_model_record",
        lambda *, candidate, problem: world,
    )

    request = port._build_joint_simulation_request(candidate=candidate, problem=problem)

    assert request.intervention_atoms == (candidate.atom,)


def _fixture_data_requirement_spec() -> DataRequirementSpec:
    return DataRequirementSpec(
        requirement_id="data-requirement:fixture-panel",
        claim_id="claim-fixture-panel",
        required_data_families=("fixture_panel",),
        scope=DataRequirementScope(
            population="firms",
            geography="UA",
            time="annual",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=("concept:firm",),
        authority_profile_refs=("authority_profile.research",),
    )


def _fixture_registration(*, source_id: str, snapshot_id: str) -> SubstrateRegistration:
    return SubstrateRegistration(
        source_id=source_id,
        family_id="fixture_panel",
        layer=SubstrateLayer.L1,
        coverage=SubstrateCoverage(
            coverage_score=0.9,
            coverage_kind="recorded_owner_response",
            coverage_rule_ref="test://coverage/fixture_panel",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=1,
        ),
        trust_tier=SubstrateTrustTier(
            tier="recorded",
            trust_cap=0.8,
            trust_multiplier=0.8,
            authority_ref="test://trust/fixture_panel",
        ),
        identification_mode="observed_panel",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id="manifest:fixture_panel",
            authority_ref="test://schema/fixture_panel",
        ),
        data_version="2026-09-22",
        snapshot_id=snapshot_id,
        source_snapshot_id=snapshot_id,
        provenance_refs=(f"test://provenance/{source_id}",),
        authority_refs=("test://authority/fixture_panel",),
    )


def _fixture_world_registry() -> Any:
    baseline = _fixture_registration(
        source_id="baseline.fixture_panel",
        snapshot_id="baseline:fixture_panel",
    )
    return build_substrate_registry(
        (build_substrate_registry_entry(baseline),),
        producer_ref="tests.unit.remediation.test_acq_01",
        source_catalog_refs=("test://acq-01/fixture-catalog",),
    )


def _fixture_owner_artifact(
    requirement_ref: str,
    *,
    candidate_content_hash: str | None = None,
    target_world_slots: tuple[str, ...] = ("fixture_panel",),
) -> AcquisitionOwnerArtifact:
    owner_response = {
        "owner_response_kind": "recorded_local_fixture_owner_response",
        "source_id": "fixture.owner_panel",
        "family_id": "fixture_panel",
        "snapshot_id": "fixture:fixture_panel:2026-09-22",
    }
    registration = _fixture_registration(
        source_id="fixture.owner_panel",
        snapshot_id="fixture:fixture_panel:2026-09-22",
    )
    payload = {
        "owner_response_kind": "real_owner_capture",
        "owner_response": owner_response,
        "raw_owner_response_hash": gy_content_hash(owner_response),
        "acquired_substrate_registrations": [registration.model_dump(mode="json")],
        "candidate_bindings": [
            {
                "candidate_id": "candidate_fixture_panel",
                "candidate_content_hash": (candidate_content_hash or "sha256:" + "1" * 64),
                "target_world_slots": list(target_world_slots),
            }
        ],
    }
    return AcquisitionOwnerArtifact.from_payload(
        owner_component="fabric.ingestion",
        requirement_ref=requirement_ref,
        artifact_ref="fixture://owner/fixture-panel",
        payload=payload,
        cost_usd=0.0,
        quality={"capture": "local_fixture_owner"},
        rights={"license": "test-fixture-only"},
        binding_refs=("candidate_fixture_panel",),
        journal_ref="journal://acq-01/fixture-panel",
        capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
            owner_component="fabric.ingestion",
            owner_endpoint="fixture.owner_panel.acquire",
            owner_request={"requirement_ref": requirement_ref},
            owner_response=payload,
            captured_at=datetime(2026, 9, 22, tzinfo=UTC),
            capture_mode="local_substrate_owner",
        ),
    )


@pytest.mark.asyncio
async def test_n7_run_recalculates_dependent_simulation_after_verified_owner_write() -> None:
    data_spec = _fixture_data_requirement_spec()
    registry = _fixture_world_registry()
    world = AcquisitionWorldSnapshot(
        world_ref="world://before/acq-01",
        known_slots=("fixture_panel",),
        dependency_index={"fixture_panel": ("candidate_fixture_panel",)},
        design_revalidation_stages={
            "candidate_fixture_panel": (
                "identification",
                "calibration",
                "value_set",
                "grounding",
            )
        },
        substrate_registry=registry.model_dump(mode="json"),
    )
    problem = _problem(
        problem_id="acq_01_fixture_reentry",
        runtime_hints={
            "n7_data_requirement_specs": (data_spec,),
            "n7_world_snapshot": world,
        },
    )
    simulation = _WorldBoundSimulation()
    candidate = _fixture_candidate(problem, world_ref=world.world_ref)
    controller = GenerationCycleController(
        generation_port=_FixtureGenerationPort(),
        grounding_port=_FixtureAcquisitionGrounding(),
        simulation_port=simulation,
        value_port=_PendingFixtureValue(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                data_spec.requirement_id: _fixture_owner_artifact(
                    data_spec.requirement_id,
                    candidate_content_hash=candidate.atom.content_hash,
                )
            }
        ),
    )

    run = await controller.run(
        problem,
        budget_state=BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}),
        max_cycles=1,
    )

    assert len(run.acquisition_receipts) == 1
    receipt = run.acquisition_receipts[0]
    assert receipt["status"] == "completed"
    assert receipt["grown_world_after_ref"] != world.world_ref
    assert receipt["world_write_outcomes"][0]["status"] == "written"
    assert run.cycles[0].grounding.status == "grounded_shadow"
    assert simulation.world_refs == [world.world_ref, receipt["grown_world_after_ref"]]
    assert run.cycles[0].selected_candidate_content_hash == run.candidate_summaries[0].content_hash
    assert run.cycles[0].selected_candidate_content_hash != candidate.atom.content_hash
    assert run.candidate_summaries[0].source_content_hash == candidate.atom.content_hash
    assert run.cycles[0].simulation.simulation_ref == (
        f"fixture-simulation:{receipt['grown_world_after_ref']}"
    )

    # A later overlay restore must project the persisted N4 identity (H0),
    # not the rebound world-bound occurrence (H1), into source custody.
    controller._restore_source_run(run)
    assert controller._source_expected_identities == [
        (
            run.design_problem_ref,
            candidate.candidate_id,
            candidate.atom.content_hash,
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("binding_mode", ("foreign_hash", "foreign_target_slots"))
async def test_n7_reentry_rejects_semantically_foreign_owner_binding(
    binding_mode: str,
) -> None:
    """A same-ID owner artifact cannot rebind a foreign candidate occurrence."""

    data_spec = _fixture_data_requirement_spec()
    registry = _fixture_world_registry()
    world = AcquisitionWorldSnapshot(
        world_ref="world://before/acq-01",
        known_slots=("fixture_panel",),
        dependency_index={"fixture_panel": ("candidate_fixture_panel",)},
        design_revalidation_stages={
            "candidate_fixture_panel": (
                "identification",
                "calibration",
                "value_set",
                "grounding",
            )
        },
        substrate_registry=registry.model_dump(mode="json"),
    )
    problem = _problem(
        problem_id="acq_01_fixture_binding_rejection",
        runtime_hints={
            "n7_data_requirement_specs": (data_spec,),
            "n7_world_snapshot": world,
        },
    )
    candidate = _fixture_candidate(problem, world_ref=world.world_ref)
    foreign_hash = (
        "sha256:" + "f" * 64
        if candidate.atom.content_hash != "sha256:" + "f" * 64
        else "sha256:" + "e" * 64
    )
    binding_hash = (
        candidate.atom.content_hash
        if binding_mode == "foreign_target_slots"
        else foreign_hash
    )
    binding_slots = (
        ("forged_panel",) if binding_mode == "foreign_target_slots" else ("fixture_panel",)
    )
    expected_error = (
        "n7_reentry_candidate_target_world_slots_mismatch"
        if binding_mode == "foreign_target_slots"
        else "n7_reentry_candidate_binding_mismatch"
    )
    controller = GenerationCycleController(
        generation_port=_FixtureGenerationPort(),
        grounding_port=_FixtureAcquisitionGrounding(),
        simulation_port=_WorldBoundSimulation(),
        value_port=_PendingFixtureValue(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                data_spec.requirement_id: _fixture_owner_artifact(
                    data_spec.requirement_id,
                    candidate_content_hash=binding_hash,
                    target_world_slots=binding_slots,
                )
            }
        ),
    )

    with pytest.raises(
        generation_cycle_module.GenerationCycleError,
        match=expected_error,
    ):
        await controller.run(
            problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )
