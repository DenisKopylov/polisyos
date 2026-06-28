from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.runtime.quality.capability_authority import CapabilityBindingResult
from polisyos.runtime.quality.capability_resolver import RequirementToCapabilityResolver
from polisyos.runtime.quality.design_axes.substrate_acquisition import (
    AcquisitionState,
    ConstructDemandLedger,
    ConstructExpression,
    SubstrateAcquisitionLoop,
    SubstrateCoverageSnapshot,
    is_production_claim_admissible,
    max_admissible_posture,
    resolve_expression,
)

PINNED = "credit_program_enrollment"
SEED_FACETS = [
    "construct",
    "actor",
    "jurisdiction",
    "population_scope",
    "time_role",
    "evidence_status",
]
REPO_ROOT = Path(__file__).resolve().parents[4]


def _expression(construct: str = PINNED) -> ConstructExpression:
    return ConstructExpression(
        construct=construct,
        facets={
            "actor": "public_credit_program_operator",
            "jurisdiction": "ua",
            "population_scope": "wartime_msme",
            "time_role": "observation",
            "evidence_status": "demanded",
        },
        authority_posture="governed",
        rule_version_refs=[
            "repo://architecture/policy_design_case/layer2_minimal_seed_manifest.json"
        ],
    )


def test_construct_expression_composes_only_from_seed_facet_primitives() -> None:
    expr = _expression()

    assert expr.is_composed_from(SEED_FACETS)


def test_construct_expression_rejects_unknown_facet_primitive() -> None:
    with pytest.raises(
        ValidationError,
        match="facet primitive 'made_up' is not in the frozen seed",
    ):
        ConstructExpression(
            construct=PINNED,
            facets={"made_up": "x"},
            authority_posture="governed",
            rule_version_refs=[
                "repo://architecture/policy_design_case/layer2_minimal_seed_manifest.json"
            ],
            allowed_facet_primitives=SEED_FACETS,
        )


def test_construct_demand_ledger_is_denominator_never_evidence() -> None:
    ledger = ConstructDemandLedger(
        case_id="ua-msme-affordable-loans-2022",
        expressions=[_expression()],
        authority_posture="governed",
    )

    assert ledger.authority_boundary.may_not_use_for
    assert "claim_authority" in ledger.authority_boundary.may_not_use_for


def test_resolve_expression_binds_by_construct_not_scenario_family() -> None:
    # ADR-0174 C1 / P06: scenario-family strings are never authority selectors.
    binding = resolve_expression(
        _expression(),
        source="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
        resolver=RequirementToCapabilityResolver.governed_fixture(),
    )

    assert isinstance(binding, CapabilityBindingResult)
    assert binding.construct_ref == PINNED
    assert "production_msme_panel" not in (binding.selected_capability_ref or "")


def test_resolve_expression_without_resolver_blocks_legacy_fixture_fallback() -> None:
    binding = resolve_expression(
        _expression(),
        source="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
    )

    assert binding.status == "blocked_acquisition_required"
    assert "governed_capability_index_required" in binding.blocked_reasons


def test_proxy_status_is_limitation_not_production() -> None:
    assert max_admissible_posture("selected_proxy_with_limitation", "production") == "governed"
    assert is_production_claim_admissible("selected_proxy_with_limitation", "governed") is False
    assert is_production_claim_admissible("selected_exact", "production") is True


def test_substrate_coverage_snapshot_reports_bounded_abstention() -> None:
    snap = SubstrateCoverageSnapshot(
        demanded=5,
        observed=1,
        proxy_limited=1,
        construct_not_observed=3,
        authority_posture="governed",
    )

    assert 0.0 <= snap.bounded_abstention_rate() <= 1.0
    assert snap.construct_demand_coverage() == pytest.approx(2 / 5)


def test_acquisition_loop_full_state_machine_closes_as_binding() -> None:
    loop = SubstrateAcquisitionLoop.from_fixture(
        expression=_expression(),
        source_fixture="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
    )

    receipt = loop.run_to_closure()

    assert [s.state for s in receipt.transitions] == [
        AcquisitionState.GAP_DETECTED,
        AcquisitionState.ELIGIBILITY_CHECKED,
        AcquisitionState.RANKED_BY_VOI,
        AcquisitionState.TASK_OPENED,
        AcquisitionState.SOURCE_ACQUIRED,
        AcquisitionState.SOURCE_CONTRACT_VALIDATED,
        AcquisitionState.CAPABILITY_INDEX_UPDATED,
        AcquisitionState.RERUN_STARTED,
        AcquisitionState.RERUN_CONSUMED_DELTA,
        AcquisitionState.CLOSED_AS_BINDING,
    ]
    assert receipt.terminal == AcquisitionState.CLOSED_AS_BINDING
    assert receipt.voi_ref is not None


def test_task_done_without_rerun_is_not_closure() -> None:
    loop = SubstrateAcquisitionLoop.from_fixture(
        expression=_expression(),
        source_fixture="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
    )
    loop.advance_to(AcquisitionState.CAPABILITY_INDEX_UPDATED)

    with pytest.raises(
        RuntimeError,
        match="closure requires a rerun that consumes the index delta",
    ):
        loop.assert_closed()


def test_index_delta_does_not_mutate_closed_case_replay() -> None:
    # ADR-0174 C2: a closed case replays unchanged after a new index delta.
    loop = SubstrateAcquisitionLoop.from_fixture(
        expression=_expression(),
        source_fixture="tests/fixtures/layer2/s3/ua_msme_credit_program_enrollment_source.json",
    )

    frozen = loop.freeze_closed_case_refs()
    loop.run_to_closure()

    assert loop.replay_closed_case(frozen) == frozen.outcome


def test_s3_substrate_consumes_g1_grounded_binding_through_existing_resolver_port() -> None:
    g1 = import_module("polisyos.runtime.quality.proving_ground.substrate_grounding_search")
    resolver = g1.build_g1_requirement_to_capability_resolver(REPO_ROOT)

    binding = resolve_expression(_expression("credit_access"), resolver=resolver)

    assert isinstance(binding, CapabilityBindingResult)
    assert binding.construct_ref == "credit_access"
    assert str(binding.capability_index_ref).startswith("layer3-g1:")
    assert binding.lineage_refs
    assert "claim_authority" in binding.may_not_use_for
    assert "production_authority" in binding.may_not_use_for
