"""Real candidate-world scope checks over test-owned WDI and world substrates.

All responses, source provisions, model assumptions, and measurement registries
are controlled fixtures. This tests the software bridge and its limitations;
it does not establish external observations, source rights, or causal validity.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, load_core_json_artifact
from polisyos.core.contracts.fabric import (
    CandidateAcquisitionSourceDataSnapshotLineage,
    DataSnapshot,
)
from polisyos.core.contracts.foundry import FoundryInputBindingRule
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.fabric import resolve_world_snapshot
from polisyos.fabric.world import WorldSnapshotWriteRequest, write_world_snapshot
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.data_plane import load_input_bindings
from polisyos.foundry.execute import load_state_snapshot
from polisyos.ir.kernel.time_semantics import TimeSemantics
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import TimeFrequency
from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
from polisyos.runtime.quality.data_snapshot_lineage import (
    CANDIDATE_SOURCE_LIMITATIONS,
    DataSnapshotSourceRowNotEstablishedError,
    validate_data_snapshot_owner_lineage,
)
from polisyos.runtime.quality.data_state_substrate import (
    CandidateAcquisitionDataSnapshotResult,
    CandidateAcquisitionSourceSlotBinding,
    DataStateSubstrateError,
    _acquired_candidate_fabric_rows,
    _require_candidate_acquisition_world_values,
    _verify_actual_acquired_native_world,
    build_candidate_acquisition_world,
    materialize_candidate_acquisition_snapshot,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.substrate_registry import (
    SubstrateRegistry,
    persist_substrate_registry,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    WorldModelBuildResult,
    WorldModelLimitations,
    WorldModelRecord,
    build_world_model_record,
    consume_world_model_record_for_simulation,
    load_world_model_record,
    world_model_artifact_views,
)
from tests._helpers.lane01_candidate_source import (
    Lane01CandidateSourceFixture,
    build_lane01_candidate_source,
)
from tests._helpers.world_model_record import (
    _data_snapshot_ref,
    _fabric_ref,
    _model_spec,
    _skg_ref,
    _substrate_registry,
    _write_data_forge_binding,
    _write_fabric_world_snapshot,
)

TENANT_ID = "a845c69e-58b6-4928-848a-539f2ec44838"
CELL_ID = "29af6dbe-d72f-40ab-9a9c-353642d65f97"
TRANSACTION_TIME = datetime(2026, 11, 3, 12, tzinfo=UTC)
BASE_SNAPSHOT_ID = "lane01-usa-labor-2024-base"
BASE_FIXTURE_LIMITATION = "controlled_fixture_base_not_empirically_grounded"


@dataclass(frozen=True, slots=True)
class _CandidateWorldCase:
    store: FileSystemCAS
    source_case: Lane01CandidateSourceFixture
    problem: DesignProblem
    base: WorldModelBuildResult
    substrate_registry: SubstrateRegistry
    substrate_registry_ref: ArtifactRef
    binding: CandidateAcquisitionSourceSlotBinding
    materialization: CandidateAcquisitionDataSnapshotResult


def _problem(
    *,
    problem_id: str = "lane01_candidate_labor_world",
    region: str = "USA",
    data_year: int = 2024,
    outcome_slot: str = "global.unemployment_rate",
) -> DesignProblem:
    """Declare a real typed research problem without claiming a grounded effect."""
    return DesignProblem.model_validate(
        {
            "schema_version": "policyos.runtime.design_problem.v3",
            "design_problem_id": problem_id,
            "problem_statement": "Compare a controlled annual labor-market candidate scenario.",
            "domain": "social",
            "nl_provenance": {
                "raw_request": "Use a controlled modeled unemployment input for research only.",
                "source_surface": "test_candidate_acquisition_world",
                "source_context": {"fixture_scope": "controlled_country_year_model_output"},
            },
            "authority_profile": {
                "requester_authority": "test_research_owner",
                "requested_authority_level": "research",
                "mandate": "Controlled software-property fixture; no empirical authority.",
            },
            "jurisdiction_time": {
                "region": region,
                "valid_time": "2024",
                "as_of": "2026-11-03",
                "policy_time": "2024",
                "data_time": str(data_year),
            },
            "objectives": [
                {
                    "objective_id": "unemployment",
                    "description": "Compare the declared unemployment outcome.",
                    "metric_id": "unemployment_rate",
                    "direction": "minimize",
                }
            ],
            "stakeholders": [
                {
                    "stakeholder_id": "labor_force",
                    "name": "Declared total labor force",
                    "role": "candidate_population",
                }
            ],
            "outcome_of_interest": {
                "target_variable": outcome_slot,
                "metric_id": "unemployment_rate",
                "estimand": "candidate_scenario_comparison",
                "direction": "minimize",
            },
            "candidate_lever_space": {
                "allowed_operator_kinds": ["set_to"],
                "candidate_levers": [
                    {
                        "lever_id": "research_budget",
                        "operator_kind": "set_to",
                        "instrument": "Declared research budget scenario",
                        "target_slot": "government.balance",
                    }
                ],
            },
            "evidence_acquisition_needs": {
                "needs": [
                    {
                        "need_id": "measurement_validity",
                        "question": "What establishes the modeled rate's measurement validity?",
                        "required_for": "authority admission",
                    }
                ]
            },
        }
    )


def _candidate_world_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, control: str | None = None
) -> _CandidateWorldCase:
    """Issue all source, base-world and candidate-data artifacts through real owners."""
    store = FileSystemCAS(tmp_path / "cas")
    source_case = build_lane01_candidate_source(
        tmp_path / "source",
        monkeypatch,
        store=store,
        tenant_id=TENANT_ID,
        cell_id=CELL_ID,
    )
    problem = _problem(
        region="CAN" if control == "country" else "USA",
        data_year=2023 if control == "data_year" else 2024,
        outcome_slot="global.gdp" if control == "declared_slot" else "global.unemployment_rate",
    )
    substrate = _substrate_registry(
        source_id="controlled_labor_measurement_fixture",
        family_id="macro_state",
        trust_tier="weak_anchor",
        trust_cap=0.25,
        identification_mode="bounds_only",
    )
    substrate_ref = persist_substrate_registry(store, substrate)
    base_dir = tmp_path / "base-world"
    base_dir.mkdir(parents=True)
    _write_fabric_world_snapshot(
        base_dir,
        snapshot_id=BASE_SNAPSHOT_ID,
        fact_valid_time="2024-01-01T00:00:00Z",
    )
    base_data_ref = _data_snapshot_ref(store, snapshot_id=BASE_SNAPSHOT_ID)
    registry_ref = build_default_registry_bundle(store, return_selected_profile=True).bundle_ref
    model_values = _model_spec(base_data_ref, registry_ref).model_dump(mode="json")
    model = ModelSpec.model_validate(
        {
            **model_values,
            "model_id": "controlled_us_labor_annual_model",
            "calibrated": False,
            "calibration_ref": None,
            "time_semantics": TimeSemantics(
                frequency=TimeFrequency.YEAR, start_date="2024-01-01", step_count=1
            ),
            "notes": ["test_owned_unvalidated_country_year_model"],
        }
    )
    base_slots = [
        "global.gdp",
        "global.tax_rate",
        "government.balance",
    ]
    if control != "base_slot":
        base_slots.append("global.unemployment_rate")
    base = build_world_model_record(
        store,
        fabric_world_ref=_fabric_ref(base_dir, snapshot_id=BASE_SNAPSHOT_ID),
        data_forge_snapshot_binding_path=_write_data_forge_binding(
            base_dir, snapshot_id=BASE_SNAPSHOT_ID
        ),
        data_snapshot_ref=base_data_ref,
        model_spec=model,
        skg_causal_prior_ref=_skg_ref(base_dir, snapshot_id=BASE_SNAPSHOT_ID),
        substrate_registry=substrate,
        substrate_registry_artifact_ref=substrate_ref,
        registry_bundle_artifact_ref=registry_ref,
        region_or_jurisdiction=problem.jurisdiction_time.region,
        population_scope=(
            "working_age_population" if control == "population" else "total_labor_force"
        ),
        policy_domain="fiscal" if control == "domain" else problem.domain,
        valid_time_scope="2024-01-01/2024-12-31",
        tx_time_scope="2026-05-24T12:00:00+00:00",
        resolution="firm_year" if control == "resolution" else "country_year",
        branch_mode=BranchMode.SCENARIO,
        policy_slot_ids=base_slots,
        producer_ref="test_candidate_acquisition_world.controlled_base",
        foundry_binding_rules=[
            FoundryInputBindingRule(
                binding_id="base.tax_rate",
                source_path="tax_rate",
                target_slot_id="global.tax_rate",
                required=True,
            ),
            FoundryInputBindingRule(
                binding_id="base.government_balance",
                source_path="government_balance",
                target_slot_id="government.balance",
                required=True,
            ),
        ],
        limitations=WorldModelLimitations(admissibility_blockers=(BASE_FIXTURE_LIMITATION,)),
        candidate_only=True,
    )
    selected_profile = cycle_job_profile_selection_ref(problem)
    if control == "profile":
        selected_profile = cycle_job_profile_selection_ref(
            _problem(problem_id="other_controlled_labor_world")
        )
    binding = CandidateAcquisitionSourceSlotBinding(
        profile_selection_ref=selected_profile,
        candidate_digest=source_case.candidate_digest,
        canonical_variable_id=source_case.entry.target_variable,
        target_slot_id=source_case.source.target_slot_id,
    )
    selected_base_ref = base_data_ref
    if control == "base_ref":
        selected_base_ref = _data_snapshot_ref(store, snapshot_id=BASE_SNAPSHOT_ID + "-other")
    materialization = materialize_candidate_acquisition_snapshot(
        store,
        workspace_dir=tmp_path / "candidate-data",
        base_data_snapshot_ref=selected_base_ref,
        candidate_source_ref=source_case.source_ref,
        slot_binding=binding,
        transaction_time=TRANSACTION_TIME,
        authority=source_case.authority,
    )
    if control == "payload_digest":
        base_snapshot = DataSnapshot.model_validate(load_core_json_artifact(store, base_data_ref))
        materialization = replace(
            materialization, payload_content_hash=str(base_snapshot.data_ref.artifact_id)
        )
    return _CandidateWorldCase(
        store, source_case, problem, base, substrate, substrate_ref, binding, materialization
    )


def test_candidate_acquisition_world_reopens_limited_model_output_and_actual_foundry_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real bridge changes numerical state while retaining unresolved authority."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _candidate_world_case(tmp_path, monkeypatch)
        source = case.source_case.source
        assert source.status == "candidate_only"
        assert source.observation_class == "model_output"
        assert source.observation == pytest.approx(0.175)
        assert (source.country_code, source.year, source.population, source.denominator) == (
            "USA",
            2024,
            "total_labor_force",
            "total_labor_force",
        )
        assert (source.quantity_kind, source.canonical_unit) == ("share_of_denominator", "ratio")
        assert case.binding.profile_selection_ref == cycle_job_profile_selection_ref(case.problem)
        assert case.binding.profile_selection_ref != case.binding.candidate_digest
        built = build_candidate_acquisition_world(
            case.store,
            problem=case.problem,
            base_world_model=case.base.record,
            substrate_registry=case.substrate_registry,
            substrate_registry_artifact_ref=case.substrate_registry_ref,
            materialization=case.materialization,
            workspace_dir=tmp_path / "candidate-world",
            transaction_time=TRANSACTION_TIME,
            authority=case.source_case.authority,
        )
        fresh = FileSystemCAS(case.store.root)
        assert built.world_model.record_ref.manifest_profile_sha256
        record = load_world_model_record(fresh, built.world_model.record_ref)
        base = load_world_model_record(fresh, case.base.record_ref)
        assert record == built.world_model.record
        assert record.world_model_record_id != base.world_model_record_id
        assert record.authority_status == "limited"
        assert record.branch_mode is BranchMode.SCENARIO
        assert record.fabric_world_ref.branch == "candidate"
        assert (record.region_or_jurisdiction, record.population_scope, record.resolution) == (
            "USA",
            "total_labor_force",
            "country_year",
        )
        assert record.policy_domain == case.problem.domain == "social"
        assert record.valid_time_scope == "not_established"
        assert record.skg_causal_prior_ref == base.skg_causal_prior_ref
        assert record.policy_slot_map == base.policy_slot_map
        assert built.model_spec.calibrated is False
        assert built.model_spec.calibration_ref is None
        assert built.model_spec.time_semantics is not None
        assert built.model_spec.time_semantics.frequency is TimeFrequency.YEAR
        assert built.model_spec.time_semantics.start_date == "2024-01-01"
        blockers = set(record.limitations.admissibility_blockers)
        assert set(case.source_case.source.limitations).issubset(blockers)
        assert set(CANDIDATE_SOURCE_LIMITATIONS).issubset(blockers)
        assert {
            BASE_FIXTURE_LIMITATION,
            "source_currentness_not_established",
            "population_is_declared_source_scope_not_sample_denominator_evidence",
            "current_run_job_route_ownership_not_established",
            "measurement_validity_not_established",
            "causal_validity_not_established",
            "claim_evidence_not_established",
            "publication_authority_not_established",
            "candidate_source_not_an_observation",
        }.issubset(blockers)

        views = world_model_artifact_views(record)
        base_views = world_model_artifact_views(base)
        assert views.data_snapshot_ref == case.materialization.data_snapshot_ref
        assert views.registry_bundle_ref == base_views.registry_bundle_ref
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(fresh, views.data_snapshot_ref)
        )
        assert isinstance(snapshot.source_lineage, CandidateAcquisitionSourceDataSnapshotLineage)
        assert snapshot.source_lineage.base_data_snapshot_ref == base_views.data_snapshot_ref
        assert snapshot.source_lineage.candidate_source_ref == case.source_case.source_ref
        payload = load_core_json_artifact(fresh, snapshot.data_ref)
        assert isinstance(payload, dict)
        materialized_tx = payload["_policyos_candidate_acquisition"][
            "materialized_at_transaction_time"
        ]
        assert materialized_tx == TRANSACTION_TIME.isoformat()
        payload_hash = str(snapshot.data_ref.artifact_id)
        _verify_actual_acquired_native_world(record, payload_hash, materialized_tx)

        # Retain the producer's snapshot and issue a separate coherent native
        # snapshot with the same identities, payload and time. Only a real fact's
        # provenance differs, so marker/scope checks cannot reject this case.
        original_native = resolve_world_snapshot(
            Path(record.fabric_world_ref.snapshot_root),
            snapshot_id=record.fabric_world_ref.snapshot_id,
        )
        node, facts = _acquired_candidate_fabric_rows(
            snapshot_id=record.fabric_world_ref.snapshot_id,
            payload_hash=payload_hash,
            transaction_time=materialized_tx,
        )
        changed_fact = facts[0].model_copy(
            update={"provenance_json": {"producer": "test.changed-native-provenance"}}
        )
        assert changed_fact.provenance_json != facts[0].provenance_json
        changed_dir = tmp_path / "changed-native-provenance"
        changed_dir.mkdir()
        changed_root = changed_dir / "fabric-world"
        changed_native = write_world_snapshot(
            changed_dir / "fabric-world.duckdb",
            WorldSnapshotWriteRequest(
                snapshot_root=changed_root,
                snapshot_id=record.fabric_world_ref.snapshot_id,
                branch_name=record.fabric_world_ref.branch,
                as_of_valid_time=record.fabric_world_ref.as_of_valid_time,
                as_of_tx_time=materialized_tx,
                provenance=original_native.provenance,
                nodes=(node,),
                facts=(changed_fact,),
            ),
        )
        assert Path(changed_native.snapshot_path).is_file()
        changed_world = WorldModelRecord.model_validate(
            {
                **record.model_dump(mode="json"),
                "fabric_world_ref": {
                    **record.fabric_world_ref.model_dump(mode="json"),
                    "snapshot_root": str(changed_root),
                },
            }
        )
        assert changed_world.content_hash == record.content_hash
        with pytest.raises(
            DataStateSubstrateError, match="acquisition_world_native_recipe_mismatch"
        ):
            _verify_actual_acquired_native_world(changed_world, payload_hash, materialized_tx)
        _verify_actual_acquired_native_world(record, payload_hash, materialized_tx)

        bindings = load_input_bindings(fresh, views.input_bindings_ref)
        assert bindings.data_snapshot_ref == views.data_snapshot_ref
        assert case.materialization.foundry_binding_rule in bindings.rules
        assert {rule.binding_id for rule in bindings.rules} == {
            "base.tax_rate",
            "base.government_balance",
            case.materialization.foundry_binding_rule.binding_id,
        }
        state = load_state_snapshot(fresh, snapshot_ref=views.bound_state_snapshot_ref)
        initial = load_state_snapshot(fresh, snapshot_ref=base_views.bound_state_snapshot_ref)
        assert isinstance(state, GlobalState)
        assert float(initial.market.unemployment_rate) == 0.0
        assert float(state.market.unemployment_rate) == pytest.approx(0.175)
        assert float(state.gdp) == float(initial.gdp) == 0.0
        assert float(state.tax_rate) == float(initial.tax_rate) == 0.0
        slot = record.slot_binding("global.unemployment_rate")
        assert slot is not None
        assert (slot.state_path, slot.unit) == ("market.unemployment_rate", "ratio")
        assert consume_world_model_record_for_simulation(record) == built.simulation_input
        assert built.simulation_input.bound_state_snapshot_ref == str(
            views.bound_state_snapshot_ref.artifact_id
        )
        with pytest.raises(DataSnapshotSourceRowNotEstablishedError):
            validate_data_snapshot_owner_lineage(fresh, views.data_snapshot_ref, snapshot)


def test_candidate_world_scope_accepts_unconstrained_no_denominator_and_refuses_share_gap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The native world-scope owner permits no denominator only for unconstrained values."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _candidate_world_case(tmp_path, monkeypatch)
        problem = case.problem.model_copy(
            update={
                "design_problem_id": "lane01_candidate_generated_gdp_scope",
                "problem_statement": "Check a generated nominal GDP candidate value.",
                "domain": "economic",
                "outcome_of_interest": case.problem.outcome_of_interest.model_copy(
                    update={"target_variable": "global.gdp", "metric_id": "gdp"}
                ),
            }
        )
        base = case.base.record.model_copy(
            update={"population_scope": "national_economy", "policy_domain": "economic"}
        )
        slot = base.slot_binding("global.gdp")
        assert slot is not None and slot.unit == "usd"
        binding = CandidateAcquisitionSourceSlotBinding(
            profile_selection_ref=cycle_job_profile_selection_ref(problem),
            candidate_digest="sha256:" + hashlib.sha256(b"generated-gdp-scope-control").hexdigest(),
            canonical_variable_id="global.gdp",
            target_slot_id="global.gdp",
        )
        common = {
            "problem": problem,
            "base": base,
            "binding": binding,
            "candidate_digest": binding.candidate_digest,
            "canonical_variable_id": "global.gdp",
            "target_slot_id": "global.gdp",
            "country_code": "USA",
            "year": 2024,
            "population": "national_economy",
            "canonical_unit": "usd",
        }
        assert (
            _require_candidate_acquisition_world_values(
                **common, quantity_kind="unconstrained", denominator=None
            )
            is None
        )
        with pytest.raises(DataStateSubstrateError, match="candidate_source_world_scope_mismatch"):
            _require_candidate_acquisition_world_values(
                **common, quantity_kind="share_of_denominator", denominator=None
            )


@pytest.mark.parametrize(
    "control",
    [
        "country",
        "data_year",
        "transaction_time",
        "population",
        "profile",
        "payload_digest",
        "declared_slot",
        "base_slot",
        "base_ref",
        "resolution",
        "domain",
    ],
)
def test_candidate_acquisition_world_refuses_mismatched_scope_before_world_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, control: str
) -> None:
    """Coherent owner-issued inputs do not make a different scope compatible."""
    with tenant_scope(None, tenant_id=TENANT_ID, cell_id=CELL_ID):
        case = _candidate_world_case(tmp_path, monkeypatch, control=control)
        profile_matches = case.binding.profile_selection_ref == cycle_job_profile_selection_ref(
            case.problem
        )
        assert profile_matches is (control != "profile")
        assert case.binding.candidate_digest == case.source_case.candidate_digest
        transaction_time = (
            TRANSACTION_TIME.replace(hour=13) if control == "transaction_time" else TRANSACTION_TIME
        )
        workspace = tmp_path / "refused-candidate-world"
        with pytest.raises(DataStateSubstrateError, match="candidate_source_world_scope_mismatch"):
            build_candidate_acquisition_world(
                case.store,
                problem=case.problem,
                base_world_model=case.base.record,
                substrate_registry=case.substrate_registry,
                substrate_registry_artifact_ref=case.substrate_registry_ref,
                materialization=case.materialization,
                workspace_dir=workspace,
                transaction_time=transaction_time,
                authority=case.source_case.authority,
            )
        assert not workspace.exists()
