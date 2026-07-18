from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from polisyos.fabric.data_plane import content_sha256
from polisyos.runtime.quality.acquisition_planner import (
    l1_variable_availability_requirement_gap,
    plan_requirement_gap_acquisition,
)
from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
from tools.quality.validation.layer3_gy_acquisition_executor import (
    DEFAULT_D6_PRIMARY_METADATA_EVIDENCE,
    DEFAULT_D6_ROUTE_SELECTION,
    D6RouteSelection,
    MetadataProbeExecutionEvidence,
)
from tools.quality.validation.layer3_gy_n13b_acceptance import (
    DEFAULT_ACCEPTANCE_CASE,
    AcceptanceCaseReceipt,
)

POLICY_ENGINE_ROOT = Path(__file__).resolve().parents[3]


def _availability(*, status: str = "unavailable", observations: int = 0) -> object:
    return L1VariableAvailability(
        variable_id="government.balance",
        status=status,
        dataset_count=0,
        metric_binding_count=0,
        observation_count=observations,
        coverage_ref=("repo://production_data/dataset_catalog.duckdb#variable/government.balance"),
    )


def test_reentry_classifies_paid_primary_terminal_without_growth_as_deeper_state() -> None:
    from tools.quality.validation.layer3_gy_n13b_reentry import (
        derive_reentry_disposition,
    )

    result = derive_reentry_disposition(
        availability_before=_availability(),
        availability_after=_availability(),
        route_disposition="derivation_requirement",
        primary_response_admitted=False,
        primary_terminal_failure_code="metadata_retryexhaustederror",
    )

    assert result == "deeper_terminal_primary_carrier_characterization_failed"


def test_reentry_trace_binds_real_n7_plan_and_zero_world_growth() -> None:
    from tools.quality.validation.layer3_gy_n13b_reentry import (
        N7CatalogResolutionProjection,
        OverlayStateProjection,
        build_reentry_trace,
    )

    route = D6RouteSelection.model_validate_json(
        (POLICY_ENGINE_ROOT / DEFAULT_D6_ROUTE_SELECTION).read_bytes()
    )
    terminal = MetadataProbeExecutionEvidence.model_validate_json(
        (POLICY_ENGINE_ROOT / DEFAULT_D6_PRIMARY_METADATA_EVIDENCE).read_bytes()
    )
    acceptance = AcceptanceCaseReceipt.model_validate_json(
        (POLICY_ENGINE_ROOT / DEFAULT_ACCEPTANCE_CASE).read_bytes()
    )
    availability = _availability()
    substrate_projection = {"slot_id": route.target_variable, "units": ("usd",)}
    design_ref = content_sha256(substrate_projection)
    candidate_hash = content_sha256(
        {"candidate_id": "gy-n13b-government-balance-reentry", "design_ref": design_ref}
    )
    gap = l1_variable_availability_requirement_gap(
        candidate_id="gy-n13b-government-balance-reentry",
        candidate_content_hash=candidate_hash,
        design_problem_ref=design_ref,
        availability=availability,
        authority_level="research",
    )
    report = plan_requirement_gap_acquisition(
        run_id="gy-n13b-government-balance-reentry",
        requirement_gaps=(gap,),
        generated_at=datetime(2026, 7, 18, tzinfo=UTC),
    )

    trace = build_reentry_trace(
        baseline_sha256=route.baseline_sha256,
        substrate_slot_projection=substrate_projection,
        d6_route=route,
        primary_metadata_evidence=terminal,
        acceptance_case=acceptance,
        availability_before=availability,
        availability_after=availability,
        requirement_gap=gap,
        planner_report=report,
        catalog_resolution=N7CatalogResolutionProjection(
            target_variable=route.target_variable,
            mode="hybrid",
            fetch_plan_count=0,
            candidate_count=0,
            warnings=(
                "No FastLane candidates for metric 'government.balance'",
                "no_fetch_plans_resolved",
            ),
            fetch_plan_execution_count=0,
        ),
        overlay_state=OverlayStateProjection(
            overlay_ref="repo://architecture/policy_design_case/layer3_gy_acquisition_overlay.duckdb",
            exists=False,
            content_sha256=None,
            epoch_count=0,
            registration_count=0,
            admitted_observation_count=0,
        ),
    )

    assert trace.reentry_disposition == ("deeper_terminal_primary_carrier_characterization_failed")
    assert trace.world_growth_status == "no_growth"
    assert trace.availability_count_delta == 0
    assert trace.overlay_state.admitted_observation_count == 0
    assert trace.catalog_resolution.fetch_plan_execution_count == 0
    assert (
        trace.planner_report_projection["acquisition_records"][0]["terminal_disposition"]
        == "acquire"
    )
