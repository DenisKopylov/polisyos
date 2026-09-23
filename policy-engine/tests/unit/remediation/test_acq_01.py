"""ACQ-01 regression coverage for the N7 requirement handoff."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import polisyos.runtime.quality.generation_cycle as generation_cycle_module
from polisyos.data_requirement import (
    DataQualityMinimums,
    DataRequirementScope,
    DataRequirementSpec,
)
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionAffectedRegion,
    AcquisitionCaptureProvenance,
    AcquisitionOwnerArtifact,
    AcquisitionReceipt,
    AcquisitionWorldSnapshot,
    RecordedAcquisitionOwnerGateway,
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
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
    def __init__(self, *, issue_code: str = "acquire_data:fixture_panel") -> None:
        self.issue_code = issue_code

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
            issue_codes=(self.issue_code,),
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


def _fixture_candidate(
    problem: DesignProblem,
    *,
    world_ref: str,
    target_world_slots: tuple[str, ...] = ("fixture_panel",),
    candidate_id: str = "candidate_fixture_panel",
) -> Any:
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
            "target_world_slots": target_world_slots,
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
        candidate_id=candidate_id,
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


def _acq01_source_requirement_id(problem_id: str) -> str:
    from polisyos.runtime.quality.data_forge_binding import _gy_slug

    return f"req-{_gy_slug(problem_id)}"


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


@contextmanager
def _real_acq01_route(
    tmp_path: Path,
    problem: DesignProblem,
    *,
    candidate_content_hash: str,
) -> Any:
    """Build one recorded WorldBank route through the existing owners.

    This fixture deliberately stops at the owner-produced route payload.  The
    controller is expected to consume that payload during N7 re-entry; the
    tests below therefore exercise the missing orchestration bridge rather
    than minting a synthetic world-model reference in the test itself.
    """

    from polisyos.core.contracts.control import DataNeed, DataResolveRequest
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootProducer,
        build_fabric_measurement_requirement,
        persist_measurement_root_data_snapshot,
        resolve_measurement_root_evidence,
    )
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateCoverage,
        SubstrateLayer,
        SubstrateRegistration,
        default_substrate_catalog_paths,
        load_l5_catalog_authority,
        persist_measurement_root_substrate_registry,
        persist_substrate_registry,
        register_substrate_entry,
    )
    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        build_world_model_record,
    )
    from tests.unit.fabric.test_retrieval_fetch_custody import (
        build_worldbank_fetch_owner,
    )
    from tests.unit.runtime.quality.test_world_model_record import (
        _fabric_ref,
        _model_spec,
        _skg_ref,
        _substrate_registry,
        _write_data_forge_binding,
        _write_fabric_world_snapshot,
    )

    data_spec = _fixture_data_requirement_spec().model_copy(
        update={
            "requirement_id": "data-requirement:acq-01-file-tabular",
            "claim_id": "claim:acq-01-file-tabular",
            "required_data_families": ("metric.test",),
        }
    )
    capture_root = tmp_path / "capture"
    with build_worldbank_fetch_owner(capture_root) as owner:
        resolved = owner.service.resolve(
            DataResolveRequest(
                data_needs=[DataNeed(metric=owner.plan.metric_id)],
                mode="fastlane",
            )
        )
        execution = owner.service.execute_fetch_plans(
            list(resolved.fetch_plans),
            persist_payload=True,
            allow_fallback=False,
        )
        preview = execution.previews[0]
        assert preview.fetch_receipt_ref is not None
        assert preview.metric.payload_ref is not None

        catalog_binding = owner.graph.bind_fetch_target(
            metric_id=owner.plan.metric_id,
            connector_id=preview.metric.connector_id,
            request_dataset_id=preview.metric.dataset_id,
            profile_id=owner.plan.profile_id,
            filters=owner.plan.filters,
        )
        source_requirement = build_fabric_measurement_requirement(
            catalog=owner.graph,
            catalog_binding=catalog_binding,
            design_problem=problem,
        )
        data_spec = data_spec.model_copy(
            update={"source_requirement_refs": (source_requirement.requirement_id,)}
        )
        store = owner.store
        measurement_root = MeasurementRootProducer(artifact_store=store).produce_from_fabric_fetch(
            fetch_receipt_ref=preview.fetch_receipt_ref,
            catalog=owner.graph,
            providers=owner.providers,
            design_problem=problem,
            source_requirement=source_requirement,
        )
        evidence = resolve_measurement_root_evidence(
            store=store,
            measurement_root=measurement_root,
            catalog=owner.graph,
            providers=owner.providers,
        )
        data_snapshot_ref = persist_measurement_root_data_snapshot(
            store=store,
            evidence=evidence,
        )
        snapshot_id = str(evidence.payload.payload_ref.artifact_id)

        baseline_registry = _substrate_registry()
        baseline_registry_ref = persist_substrate_registry(store, baseline_registry)
        l5_authority = load_l5_catalog_authority(default_substrate_catalog_paths(REPO_ROOT))
        registration = SubstrateRegistration(
            source_id="acquisition:acq-01-file-tabular",
            family_id="metric.test",
            layer=SubstrateLayer.L4,
            coverage=SubstrateCoverage(
                coverage_score=0.42,
                coverage_kind="acquisition_receipt.coverage",
                coverage_rule_ref="receipt://acq-01/file-tabular#coverage",
                dataset_count=1,
                metric_binding_count=1,
                observation_count=evidence.payload.observed_row_count,
            ),
            trust_tier=l5_authority.trust_tiers["weak_anchor"],
            identification_mode="bounds_only",
            schema_regime=l5_authority.latest_schema_regime(),
            data_version="file-tabular-fixture-v1",
            snapshot_id=snapshot_id,
            source_snapshot_id=snapshot_id,
            provenance_refs=(f"cas://{evidence.measurement_root_ref.artifact_id}",),
            authority_refs=(l5_authority.measurement_registry_ref,),
        )
        admission = persist_measurement_root_substrate_registry(
            store,
            baseline_registry=baseline_registry,
            registration=registration,
            l5_authority=l5_authority,
            evidence=evidence,
            baseline_registry_ref=baseline_registry_ref,
        )
        # N7's accepted world write creates the runtime registry projection
        # that the receipt hashes.  Persist that exact projection while
        # retaining the canonical measurement-root admission as its evidence
        # and lineage source.
        route_registry = register_substrate_entry(
            baseline_registry,
            registration,
            producer_ref="polisyos.runtime.quality.acquisition_planner.N7",
        )
        route_registry_ref = persist_substrate_registry(
            store,
            route_registry,
            inputs=admission.input_refs,
        )

        world_root = tmp_path / "fresh-world"
        world_root.mkdir(parents=True, exist_ok=True)
        _write_fabric_world_snapshot(world_root, snapshot_id=snapshot_id)
        data_forge_binding_path = _write_data_forge_binding(
            world_root,
            snapshot_id=snapshot_id,
        )
        registry_bundle = build_default_registry_bundle(store)
        model_spec = _model_spec(data_snapshot_ref, registry_bundle.bundle_ref)
        world_build = build_world_model_record(
            store,
            fabric_world_ref=_fabric_ref(world_root, snapshot_id=snapshot_id),
            data_forge_snapshot_binding_path=data_forge_binding_path,
            data_snapshot_ref=data_snapshot_ref,
            model_spec=model_spec,
            skg_causal_prior_ref=_skg_ref(world_root, snapshot_id=snapshot_id),
            substrate_registry=route_registry,
            region_or_jurisdiction="UA-30",
            population_scope="recorded_file_tabular_fixture",
            policy_domain="fiscal_credit",
            valid_time_scope="2026-09-22/2026-09-22",
            tx_time_scope="2026-09-22T00:00:00+00:00",
            resolution="row",
            branch_mode=BranchMode.OBSERVED,
            policy_slot_ids=("agents.income", "government.balance"),
            producer_ref="tests.unit.remediation.test_acq_01.real_route",
            required_substrate_families=("metric.test",),
            substrate_registry_artifact_ref=route_registry_ref,
            _loaded_substrate_registry=route_registry,
        )
        selected_entry_hashes = tuple(
            entry.entry_content_hash
            for entry in route_registry.entries
            if entry.family_id == "metric.test"
        )
        context = build_cycle_substrate_context(
            design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
            domain=problem.domain,
            substrate_registry=route_registry,
            selected_registry_entry_hashes=selected_entry_hashes,
            world_model_record=world_build.record,
            intervention_substrate=None,
            candidate_levers=(),
            transport_context=None,
            source_pack_content_hash=None,
            substrate_input_content_hash=None,
        )
        captured_fetch = {
            "plan": preview.metric.plan_id,
            "payload_ref": preview.metric.payload_ref.model_dump(mode="json"),
            "fetch_receipt_ref": preview.fetch_receipt_ref.model_dump(mode="json"),
            "catalog_binding_ref": evidence.catalog_binding_ref.model_dump(mode="json"),
        }
        owner_response = {
            "owner_response_kind": "fabric_fetch_capture",
            "captured_fetches": [captured_fetch],
        }
        payload = {
            "owner_response_kind": "real_owner_capture",
            "owner_response": owner_response,
            "raw_owner_response_hash": gy_content_hash(owner_response),
            "acquired_substrate_registrations": [registration.model_dump(mode="json")],
            "candidate_bindings": [
                {
                    "candidate_id": "candidate_metric_test",
                    "candidate_content_hash": candidate_content_hash,
                    "target_world_slots": ["agents.income"],
                }
            ],
            "acq01_route": {
                "route_schema_version": "policyos.runtime.acq01_route.v1",
                "capture_store_root": str(store.root),
                "measurement_root": measurement_root.model_dump(mode="json"),
                "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
                "registry_ref": route_registry_ref.model_dump(mode="json"),
                "baseline_registry_ref": baseline_registry_ref.model_dump(mode="json"),
                "registry": route_registry.model_dump(mode="json"),
                "build_inputs": {
                    "fabric_world_ref": _fabric_ref(
                        world_root,
                        snapshot_id=snapshot_id,
                    ).model_dump(mode="json"),
                    "data_forge_snapshot_binding_path": str(data_forge_binding_path),
                    "data_snapshot_ref": data_snapshot_ref.model_dump(mode="json"),
                    "model_spec": model_spec.model_dump(mode="json"),
                    "skg_causal_prior_ref": _skg_ref(
                        world_root,
                        snapshot_id=snapshot_id,
                    ).model_dump(mode="json"),
                    "region_or_jurisdiction": "UA-30",
                    "population_scope": "recorded_file_tabular_fixture",
                    "policy_domain": "fiscal_credit",
                    "valid_time_scope": "2026-09-22/2026-09-22",
                    "tx_time_scope": "2026-09-22T00:00:00+00:00",
                    "resolution": "row",
                    "branch_mode": BranchMode.OBSERVED.value,
                    "policy_slot_ids": ["agents.income", "government.balance"],
                    "producer_ref": "tests.unit.remediation.test_acq_01.real_route",
                    "data_forge_role": "academic",
                    "required_substrate_families": ["metric.test"],
                },
            },
        }
        owner_artifact = AcquisitionOwnerArtifact.from_payload(
            owner_component="fabric.retrieval",
            requirement_ref=data_spec.requirement_id,
            artifact_ref="owner-capture://acq-01/file-tabular",
            payload=payload,
            cost_usd=0.0,
            quality={"owner_endpoint": "RetrievalService.resolve/execute_fetch_plans"},
            rights={"recording": "owner_response_replay_only"},
            binding_refs=(data_spec.requirement_id, "candidate_metric_test"),
            journal_ref="journal://n7/acq-01/file-tabular",
            capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
                owner_component="fabric.retrieval",
                owner_endpoint="RetrievalService.resolve/execute_fetch_plans",
                owner_request={"requirement_ref": data_spec.requirement_id},
                owner_response=payload,
                captured_at=datetime(2026, 9, 22, tzinfo=UTC),
                capture_mode="local_substrate_owner",
            ),
        )
        yield SimpleNamespace(
            data_spec=data_spec,
            owner_artifact=owner_artifact,
            store=store,
            measurement_root=measurement_root,
            evidence=evidence,
            data_snapshot_ref=data_snapshot_ref,
            admission=admission,
            world_build=world_build,
            context=context,
            catalog=owner.graph,
            providers=owner.providers,
        )


def _real_acq01_before_context(
    tmp_path: Path,
    problem: DesignProblem,
) -> Any:
    """Build the content-bound pre-acquisition context from existing owners."""

    from tests.unit.runtime.quality.test_world_model_record import (
        _build_record,
        _substrate_registry,
    )

    _, world_build, _, _ = _build_record(tmp_path / "before")
    registry = _substrate_registry()
    selected_entry_hashes = tuple(
        entry.entry_content_hash for entry in registry.entries
    )
    return build_cycle_substrate_context(
        design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=selected_entry_hashes,
        world_model_record=world_build.record,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=None,
    )


def _real_acq01_inputs(
    tmp_path: Path,
    *,
    problem_id: str,
    extra_runtime_hints: dict[str, Any] | None = None,
) -> Any:
    data_spec = _fixture_data_requirement_spec().model_copy(
        update={
            "requirement_id": "data-requirement:acq-01-file-tabular",
            "claim_id": "claim:acq-01-file-tabular",
            "required_data_families": ("metric.test",),
            "source_requirement_refs": (_acq01_source_requirement_id(problem_id),),
        }
    )
    runtime_hints = {"n7_data_requirement_specs": (data_spec,)}
    runtime_hints.update(extra_runtime_hints or {})
    problem = _problem(problem_id=problem_id, runtime_hints=runtime_hints)
    before_context = _real_acq01_before_context(tmp_path, problem)
    candidate = _fixture_candidate(
        problem,
        world_ref=before_context.world_model_record.world_model_record_id,
        target_world_slots=("agents.income",),
        candidate_id="candidate_metric_test",
    )
    return SimpleNamespace(
        data_spec=data_spec,
        problem=problem,
        before_context=before_context,
        candidate=candidate,
    )


class _ContextRecordingSimulation:
    def __init__(self) -> None:
        self.controller: GenerationCycleController | None = None
        self.observations: list[tuple[Any, str]] = []

    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        del problem, cycle_index
        context = self.controller._cycle_substrate_context if self.controller else None
        world_ref = str(candidate.atom.world_model_record_ref)
        self.observations.append((context, world_ref))
        return SimulationPortObservation(
            candidate_id=str(candidate.candidate_id),
            status="joint_simulated",
            simulation_ref=f"fixture-simulation:{world_ref}",
            k_world_ref_before=world_ref,
            k_world_ref_after=world_ref,
        )


def _build_acq01_real_route_controller(
    *,
    case: Any,
    route: Any,
    simulation: Any,
    repo_root: Path,
) -> GenerationCycleController:
    class _RouteGenerationPort:
        async def __call__(self, current: DesignProblem, *, cycle_index: int) -> Any:
            del current, cycle_index
            return SimpleNamespace(
                status="generated",
                candidates=(case.candidate,),
                surrogate_rankings=(
                    SimpleNamespace(
                        candidate_id=case.candidate.candidate_id,
                        score=0.2,
                        voi_estimate=0.2,
                    ),
                ),
                grounding_dispositions=(),
            )

    gateway = RecordedAcquisitionOwnerGateway(
        artifacts_by_requirement={
            case.data_spec.requirement_id: route.owner_artifact,
        }
    )
    gateway.catalog = route.catalog
    gateway.providers = route.providers
    controller = GenerationCycleController(
        generation_port=_RouteGenerationPort(),
        grounding_port=_FixtureAcquisitionGrounding(issue_code="acquire_data:metric.test"),
        simulation_port=simulation,
        value_port=_PendingFixtureValue(),
        acquisition_owner_gateway=gateway,
        repo_root=repo_root,
        cycle_substrate_context=case.before_context,
    )
    if isinstance(simulation, _ContextRecordingSimulation):
        simulation.controller = controller
    return controller


def _assert_n7_world_model_record_semantics(actual: Any, expected: Any) -> None:
    """Compare every stable WMR field while allowing reconstruction time to advance."""

    actual_projection = actual.model_dump(mode="json")
    expected_projection = expected.model_dump(mode="json")
    actual_created_at = datetime.fromisoformat(actual_projection.pop("created_at"))
    expected_created_at = datetime.fromisoformat(expected_projection.pop("created_at"))
    assert actual_projection == expected_projection
    assert actual.world_model_record_id == expected.world_model_record_id
    assert actual.content_hash == expected.content_hash
    assert actual_created_at >= expected_created_at


@pytest.mark.asyncio
async def test_n7_acq01_real_measurement_root_delta_builds_fresh_wmr(
    tmp_path: Path,
) -> None:
    """A real owner delta must rebind N5 to a content-bound WMR, not S0 URI."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_real_wmr")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        simulation = _WorldBoundSimulation()
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=simulation,
            repo_root=tmp_path,
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        receipt = run.acquisition_receipts[0]
        assert receipt["status"] == "completed"
        assert route.world_build.data_snapshot_ref == route.data_snapshot_ref
        assert (
            route.world_build.record.simulation_model_ref.data_snapshot_ref
            == str(route.data_snapshot_ref.artifact_id)
        )
        assert (
            simulation.world_refs[0]
            == case.before_context.world_model_record.world_model_record_id
        )
        assert simulation.world_refs[-1] in {
            route.world_build.record.world_model_record_id,
            route.world_build.record.content_hash,
        }
        assert simulation.world_refs[-1] != receipt["grown_world_after_ref"]


@pytest.mark.asyncio
async def test_n7_acq01_reentry_rebuilds_fresh_context_before_n5_and_n7(
    tmp_path: Path,
) -> None:
    """N7 re-entry must replace the shared context before dependent owners run."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_real_context")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        simulation = _ContextRecordingSimulation()
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=simulation,
            repo_root=tmp_path,
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        assert len(simulation.observations) == 2
        before, after = simulation.observations
        assert before[0] is case.before_context
        assert after[0] is not None
        assert after[0] is not case.before_context
        _assert_n7_world_model_record_semantics(
            after[0].world_model_record,
            route.world_build.record,
        )
        assert after[0].content_hash != case.before_context.content_hash
        assert {
            "grounding_authority",
            "transport_authority",
            "promotion_authority",
        }.issubset(after[0].may_not_use_for)
        assert after[1] in {
            route.world_build.record.world_model_record_id,
            route.world_build.record.content_hash,
        }
        assert run.cycles[0].simulation.k_world_ref_before == after[1]


@pytest.mark.asyncio
async def test_n7_acq01_reentry_rebinds_real_n5_and_default_n8(
    tmp_path: Path,
) -> None:
    """The accepted route reaches the real JointSimulationPort and default N8."""

    case = _real_acq01_inputs(
        tmp_path,
        problem_id="acq_01_real_ports",
        extra_runtime_hints={
            "joint_simulation_resource": "method_registry_estimator",
            "joint_simulation_budget_ref": "budget://acq-01/real-ports",
            "joint_simulation_horizon": {"start": 0, "end": 1, "step": 1},
        },
    )
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        class _RouteGenerationPort:
            async def __call__(self, current: DesignProblem, *, cycle_index: int) -> Any:
                del current, cycle_index
                return SimpleNamespace(
                    status="generated",
                    candidates=(case.candidate,),
                    surrogate_rankings=(
                        SimpleNamespace(
                            candidate_id=case.candidate.candidate_id,
                            score=0.2,
                            voi_estimate=0.2,
                        ),
                    ),
                    grounding_dispositions=(),
                )

        class _RecordingN5Controller:
            def __init__(self) -> None:
                self.requests: list[Any] = []
                self._delegate = generation_cycle_module.JointSimulationHorizonController()

            def run(self, request: Any) -> Any:
                self.requests.append(request)
                return self._delegate.run(request)

        n5 = _RecordingN5Controller()
        gateway = RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                case.data_spec.requirement_id: route.owner_artifact,
            }
        )
        gateway.catalog = route.catalog
        gateway.providers = route.providers
        controller = GenerationCycleController(
            generation_port=_RouteGenerationPort(),
            grounding_port=_FixtureAcquisitionGrounding(issue_code="acquire_data:metric.test"),
            simulation_port=JointSimulationPort(
                controller=n5,
                repo_root=tmp_path,
                cycle_substrate_context=case.before_context,
            ),
            acquisition_owner_gateway=gateway,
            repo_root=tmp_path,
            cycle_substrate_context=case.before_context,
        )

        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        assert len(n5.requests) == 2
        before_request, after_request = n5.requests
        assert before_request.world_model_record == case.before_context.world_model_record
        _assert_n7_world_model_record_semantics(
            after_request.world_model_record,
            route.world_build.record,
        )
        assert after_request.world_model_record_ref == route.world_build.record.world_model_record_id
        assert isinstance(
            controller._value_port,
            generation_cycle_module._DefaultSimulationBoundFoundryValuePort,
        )
        assert controller._value_port.cycle_substrate_context is controller._cycle_substrate_context
        assert controller._cycle_substrate_context is not case.before_context
        _assert_n7_world_model_record_semantics(
            controller._cycle_substrate_context.world_model_record,
            route.world_build.record,
        )
        assert run.cycles[0].value_port.status == "value_conditional"
        assert (
            run.cycles[0].value_port.world_model_record_content_hash
            == route.world_build.record.content_hash
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["before_ref", "delta_hash"])
async def test_n7_acq01_reentry_rejects_tampered_receipt_world_binding(
    tmp_path: Path,
    mutation: str,
) -> None:
    """Receipt world refs and delta hashes remain bound to the revalidated CAS route."""

    case = _real_acq01_inputs(tmp_path, problem_id=f"acq_01_tampered_{mutation}")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )
        receipt = AcquisitionReceipt.model_validate(run.acquisition_receipts[0])
        tampered = receipt.model_copy(
            update={
                "grown_world_before_ref": (
                    "sha256:" + "f" * 64
                    if mutation == "before_ref"
                    else receipt.grown_world_before_ref
                ),
                "grown_world_delta_hash": (
                    "sha256:" + "e" * 64
                    if mutation == "delta_hash"
                    else receipt.grown_world_delta_hash
                ),
            }
        )
        controller._cycle_substrate_context = case.before_context
        with pytest.raises(
            generation_cycle_module.GenerationCycleError,
            match="n7_acq01_registry_binding_invalid",
        ):
            controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=tampered,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )


@pytest.mark.asyncio
async def test_n7_acq01_reentry_rejects_registry_version_content_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A version string forged over unchanged registry bytes cannot pass N7."""

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_tampered_version")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
        )
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )
        receipt = AcquisitionReceipt.model_validate(run.acquisition_receipts[0])
        route_payload = dict(route.owner_artifact.payload)
        route_projection = dict(route_payload["acq01_route"])
        inline_registry = dict(route_projection["registry"])
        forged_version = "substrate_version_" + "f" * 16
        inline_registry["substrate_version_id"] = forged_version
        route_projection["registry"] = inline_registry
        route_payload["acq01_route"] = route_projection
        forged_owner = route.owner_artifact.model_copy(
            update={
                "payload": route_payload,
                "content_hash": gy_content_hash(route_payload),
            }
        )
        outcomes = list(receipt.world_write_outcomes)
        outcomes[0] = outcomes[0].model_copy(
            update={
                "substrate_version_after": forged_version,
                "world_ref_after": f"s0://substrate-registry/{forged_version}",
            }
        )
        tampered = receipt.model_copy(
            update={
                "owner_artifacts": (forged_owner,),
                "world_write_outcomes": tuple(outcomes),
                "grown_world_after_ref": f"s0://substrate-registry/{forged_version}",
            }
        )
        controller._cycle_substrate_context = case.before_context
        import polisyos.runtime.quality.substrate_registry as substrate_registry_module

        original_loader = substrate_registry_module.load_substrate_registry

        def forged_loader(store: Any, ref: Any) -> Any:
            loaded = original_loader(store, ref)
            registry_ref = route_projection["registry_ref"]["artifact_id"]
            if str(ref.artifact_id) == registry_ref:
                return loaded.model_copy(update={"substrate_version_id": forged_version})
            return loaded

        monkeypatch.setattr(
            substrate_registry_module,
            "load_substrate_registry",
            forged_loader,
        )
        with pytest.raises(
            generation_cycle_module.GenerationCycleError,
            match="n7_acq01_registry_binding_invalid",
        ):
            controller._rebuild_n7_acq01_route_context(
                case.problem,
                acquisition_receipt=tampered,
                candidate_id=case.candidate.candidate_id,
                candidate_content_hash=case.candidate.atom.content_hash,
                target_world_slots=tuple(case.candidate.atom.target_world_slots),
            )


@pytest.mark.asyncio
async def test_n7_acq01_reentry_does_not_dispatch_gateway_source_echo(
    tmp_path: Path,
) -> None:
    """Canonical replay ignores an untrusted same-ID source echo from the gateway.

    The canonical producer/replay mismatch witness remains covered by
    ``test_n9_measurement_rechecks_source_requirement_and_problem``; this ACQ
    route falsifier proves that a gateway echo cannot carry this gate.
    """

    from polisyos.runtime.quality.data_forge_binding import (
        _fabric_measurement_envelope,
        _measurement_root_evidence_fingerprint,
        _validate_resolved_measurement_root_evidence,
        resolve_measurement_root_evidence,
    )

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_tampered_source")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        controller = _build_acq01_real_route_controller(
            case=case,
            route=route,
            simulation=_WorldBoundSimulation(),
            repo_root=tmp_path,
        )
        gateway = controller._acquisition_owner_gateway
        canonical_resolver = resolve_measurement_root_evidence
        invoked = False

        def altered_resolver(**kwargs: Any) -> Any:
            nonlocal invoked
            invoked = True
            evidence = canonical_resolver(**kwargs)
            source = evidence.payload.source_requirement
            altered_source = source.model_copy(
                update={
                    "scope": source.scope.model_copy(update={"geography": "ZZ"}),
                }
            )
            altered_payload = evidence.payload.model_copy(
                update={"source_requirement": altered_source}
            )
            altered_envelope = _fabric_measurement_envelope(
                altered_payload,
                evidence.envelope.payload_ref,
            )
            altered_fingerprint = _measurement_root_evidence_fingerprint(
                envelope=altered_envelope,
                payload=altered_payload,
                measurement_root_ref=evidence.measurement_root_ref,
                fetch_receipt_ref=evidence.fetch_receipt_ref,
                catalog_binding_ref=evidence.catalog_binding_ref,
            )
            altered = evidence.model_copy(
                update={
                    "envelope": altered_envelope,
                    "payload": altered_payload,
                    "evidence_fingerprint": altered_fingerprint,
                }
            )
            _validate_resolved_measurement_root_evidence(altered)
            return altered

        gateway.resolve_measurement_root_evidence = altered_resolver
        run = await controller.run(
            case.problem,
            budget_state=BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
            ),
            max_cycles=1,
        )

        assert invoked is False
        assert run.acquisition_receipts[0]["status"] == "completed"


def test_n7_acq01_measurement_root_rejects_same_id_altered_source_requirement(
    tmp_path: Path,
) -> None:
    """The real MeasurementRoot producer rejects same-ID source drift."""

    from polisyos.runtime.quality.data_forge_binding import (
        FabricMeasurementRootBindingError,
        MeasurementRootProducer,
    )

    case = _real_acq01_inputs(tmp_path, problem_id="acq_01_source_requirement_drift")
    with _real_acq01_route(
        tmp_path,
        case.problem,
        candidate_content_hash=case.candidate.atom.content_hash,
    ) as route:
        source_requirement = route.evidence.payload.source_requirement
        altered_source_requirement = source_requirement.model_copy(
            update={
                "scope": source_requirement.scope.model_copy(update={"geography": "ZZ"}),
            }
        )
        assert altered_source_requirement.requirement_id == source_requirement.requirement_id
        with pytest.raises(
            FabricMeasurementRootBindingError,
            match="measurement_root_source_requirement_mismatch",
        ):
            MeasurementRootProducer(artifact_store=route.store).produce_from_fabric_fetch(
                fetch_receipt_ref=route.evidence.payload.fetch_receipt_ref,
                catalog=route.catalog,
                providers=route.providers,
                design_problem=case.problem,
                source_requirement=altered_source_requirement,
            )


def test_n7_grounding_fails_closed_without_structural_dependency_membership() -> None:
    """A policy target slot cannot replace a missing data dependency edge."""

    from polisyos.runtime.quality.acquisition_planner import (
        _rederive_grounding_for_affected_region,
    )

    region = AcquisitionAffectedRegion(
        source_slots=("metric.test",),
        neighborhood_slots=("metric.test",),
        dependency_index={"metric.test": ("candidate_other",)},
        design_ids=("candidate_fixture_panel",),
        rederived_design_ids=("candidate_fixture_panel",),
        revalidation_stages={"candidate_fixture_panel": ("grounding",)},
        over_approximation_basis="test_dependency_membership",
    )
    rows = _rederive_grounding_for_affected_region(
        world=AcquisitionWorldSnapshot(world_ref="world://dependency-negative"),
        world_after_ref="world://dependency-negative/after",
        affected_region=region,
        owner_artifacts=(
            _fixture_owner_artifact(
                _fixture_data_requirement_spec().requirement_id,
                target_world_slots=("agents.income",),
            ),
        ),
        design_problem=_problem(problem_id="acq_01_dependency_negative"),
    )

    assert len(rows) == 1
    assert rows[0].status == "grounding_unavailable"
    assert rows[0].issue_codes == ("candidate_not_in_dependency_index",)


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
@pytest.mark.parametrize(
    "binding_mode",
    [("foreign_hash",), ("foreign_target_slots",)],
)
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
        ("fixture_panel", "forged_panel")
        if binding_mode == "foreign_target_slots"
        else ("fixture_panel",)
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


@pytest.mark.asyncio
async def test_n7_reentry_does_not_run_n5_from_registry_only_world_ref(
    tmp_path: Path,
) -> None:
    """A registry URI cannot substitute for a content-bound WMR/context."""

    data_spec = _fixture_data_requirement_spec()
    registry = _fixture_world_registry()
    problem = _problem(
        problem_id="acq_01_registry_only_reentry",
        runtime_hints={
            "n7_data_requirement_specs": (data_spec,),
            "joint_simulation_resource": "method_registry_estimator",
            "joint_simulation_budget_ref": "budget://acq-01/registry-only-reentry",
            "joint_simulation_horizon": {"start": 0, "end": 1, "step": 1},
        },
    )
    world = generation_cycle_module._build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="firm_survival",
        policy_slot_ids=("fixture_panel",),
        substrate_registry=registry,
        selected_registry_entry_hashes=(registry.entries[0].entry_content_hash,),
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(registry.entries[0].entry_content_hash,),
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(),
        transport_context=None,
        source_pack_content_hash=None,
        substrate_input_content_hash=None,
    )
    assert {
        "grounding_authority",
        "transport_authority",
        "promotion_authority",
    }.issubset(context.may_not_use_for)

    class _BoundFixtureGenerationPort:
        async def __call__(self, current: DesignProblem, *, cycle_index: int) -> Any:
            del cycle_index
            candidate = _fixture_candidate(
                current,
                world_ref=world.world_model_record_id,
            )
            return SimpleNamespace(
                status="generated",
                candidates=(candidate,),
                surrogate_rankings=(
                    SimpleNamespace(
                        candidate_id=candidate.candidate_id,
                        score=0.95,
                        voi_estimate=0.95,
                    ),
                ),
                grounding_dispositions=(),
            )

    class _RecordingN5Controller:
        def __init__(self) -> None:
            self.requests: list[object] = []
            self._delegate = generation_cycle_module.JointSimulationHorizonController()

        def run(self, request: object) -> Any:
            self.requests.append(request)
            return self._delegate.run(request)

    n5 = _RecordingN5Controller()
    controller = GenerationCycleController(
        generation_port=_BoundFixtureGenerationPort(),
        grounding_port=_FixtureAcquisitionGrounding(),
        simulation_port=JointSimulationPort(
            controller=n5,
            repo_root=tmp_path,
            cycle_substrate_context=context,
        ),
        value_port=_PendingFixtureValue(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={
                data_spec.requirement_id: _fixture_owner_artifact(
                    data_spec.requirement_id,
                    candidate_content_hash=_fixture_candidate(
                        problem,
                        world_ref=world.world_model_record_id,
                    ).atom.content_hash,
                )
            }
        ),
        repo_root=tmp_path,
        cycle_substrate_context=context,
    )

    run = await controller.run(
        problem,
        budget_state=BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("5.0"))}
        ),
        min_cycles=1,
        max_cycles=1,
    )

    cycle = run.cycles[0]
    receipt = cycle.acquisition_receipt
    assert receipt is not None
    assert receipt["status"] == "completed"
    grown_world_ref = receipt["grown_world_after_ref"]
    assert grown_world_ref.startswith("s0://substrate-registry/")
    assert grown_world_ref != context.world_model_record_content_hash
    assert grown_world_ref != context.world_model_record.world_model_record_id
    assert len(n5.requests) == 1
    assert cycle.simulation.status == "simulation_blocked"
    assert "world_identity_unresolved" in cycle.simulation.authority_blockers
    assert cycle.simulation.simulation_ref is None
