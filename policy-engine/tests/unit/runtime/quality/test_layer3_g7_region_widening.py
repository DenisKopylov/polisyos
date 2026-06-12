from __future__ import annotations

import pytest
from pydantic import ValidationError

REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS = {
    "g5_unchanged_blocker_as_region_grounded",
    "g6_candidate_as_region_grounded",
    "fixture_breadth_as_grounded",
    "hardcoded_candidate_set_as_region_coverage",
    "search_hit_as_region_coverage",
    "grounded_case_without_governed_promotion",
    "g4_seed_promotion_as_region_governance",
    "g4_promotion_without_full_gate_shape",
    "g4_mapping_fallback_as_region_governance",
    "bespoke_patch_as_mechanism_reuse",
    "sublinear_cost_without_cost_ledger",
    "sublinear_cost_without_grounded_cases",
    "s12_growth_thermometer_missing",
    "s12_projection_bypasses_resource_economics_shape",
    "s12_growth_without_certified_delta",
    "s12_held_out_status_overclaimed",
    "s12_deny_list_omitted",
    "s13_certified_delta_missing",
    "pending_delta_as_region_expansion",
    "semantic_loss_hidden_by_region_score",
    "effective_independence_inflated",
    "g5_may_not_use_for_ignored",
    "g6_may_not_use_for_ignored",
    "s14_feed_missing",
    "s14_battery_input_manifest_missing",
    "s14_feed_uses_fixtures",
    "s14_manifest_as_runner_output",
    "universal_claim_without_s14_gate",
    "public_projection_authority_leak",
    "public_projection_raw_payload_leak",
    "public_projection_required_deny_list_missing",
    "public_projection_contract_missing_or_failed",
    "generated_artifacts_family_missing",
    "inventory_surface_missing",
    "reference_index_missing",
    "route_contract_registry_missing",
    "manifest_runtime_drift",
    "replay_manifest_missing",
    "orchestration_continuity_missing",
    "replay_helper_bypassed",
    "closed_case_replay_mutated",
}


def test_layer3_g7_constants_define_region_boundary() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    assert g7.G7_SCHEMA_VERSION == (
        "policyos.policy_design_case.layer3_g7_region_widening.v1"
    )
    assert g7.G7_RULE_VERSION == "policyos.layer3.g7.region_widening.v1"
    assert "layer3_g7_region_widening_audit" in g7.G7_AUTHORITATIVE_FOR
    assert "universal_claim_authority" in g7.G7_MAY_NOT_USE_FOR
    assert "policy_recommendation" in g7.G7_MAY_NOT_USE_FOR


def test_layer3_g7_base_model_forbids_extra_fields() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    class Probe(g7._G7Model):
        status: str

    with pytest.raises(ValidationError) as exc_info:
        Probe.model_validate({"status": "pass", "extra": "authority-leak"})

    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_g7_dependency_snapshot_reports_current_g5_blocker() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    snapshot = g7.build_g7_dependency_readiness_snapshot(g7.DEFAULT_REPO_ROOT)

    assert snapshot.engineering_readiness_status == "pass"
    assert snapshot.g5_conversion_outcome == "unchanged_blocker"
    assert snapshot.g5_grounded_region_seed_count == 0
    assert snapshot.region_value_closure_status == (
        "blocked_by_current_g5_unchanged_blocker"
    )
    assert "g7_region_widening" in snapshot.g5_may_not_use_for
    assert "g7_region_widening" in snapshot.g6_may_not_use_for


def test_g7_dependency_snapshot_preserves_control_plane_search_boundary() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    snapshot = g7.build_g7_dependency_readiness_snapshot(g7.DEFAULT_REPO_ROOT)

    assert snapshot.g1_substrate_search_control_plane_status == "pass"
    assert snapshot.g1_substrate_search_ledger_count >= 1
    assert snapshot.g1_substrate_search_authoritative_for == ()
    assert "search_hit_as_authority" in snapshot.g1_substrate_search_may_not_use_for


def test_g7_validation_blocks_current_overclaim_attempts() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    snapshot = g7.build_g7_dependency_readiness_snapshot(g7.DEFAULT_REPO_ROOT)
    bundle = g7.Layer3G7Bundle(
        dependency_readiness_snapshot=snapshot,
        region_grounded_case_count=1,
        g6_region_conversion_count=1,
        seed_g4_promotion_projected_to_region=True,
        status_composition_claim="pass",
        closed_replay_mutation_detected=True,
    )

    report = g7.validate_layer3_g7_bundle(g7.DEFAULT_REPO_ROOT, bundle)

    assert report.status == "fail"
    assert {
        "layer3_g7_g5_unchanged_blocker_counted_as_grounded",
        "layer3_g7_g6_candidate_counted_as_grounded",
        "layer3_g7_g4_seed_promotion_projected_to_region",
        "layer3_g7_status_composition_missing",
        "layer3_g7_closed_case_replay_mutated",
    } <= {issue.code for issue in report.issues}


def test_g7_validation_blocks_missing_readiness_and_dropped_deny_lists() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    snapshot = g7.build_g7_dependency_readiness_snapshot(g7.DEFAULT_REPO_ROOT).model_copy(
        update={
            "g5_readiness_status": "missing",
            "g6_readiness_status": "fail",
            "g5_may_not_use_for": (),
            "g6_may_not_use_for": (),
        }
    )
    bundle = g7.Layer3G7Bundle(dependency_readiness_snapshot=snapshot)

    report = g7.validate_layer3_g7_bundle(g7.DEFAULT_REPO_ROOT, bundle)

    assert report.status == "fail"
    assert {
        "layer3_g7_g5_readiness_missing",
        "layer3_g7_g6_readiness_missing",
        "layer3_g7_g5_may_not_use_for_ignored",
        "layer3_g7_g6_may_not_use_for_ignored",
    } <= {issue.code for issue in report.issues}


def test_g7_default_candidate_set_is_control_plane_not_coverage() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    candidate_set = g7.build_g7_region_candidate_set(
        region_ref="region://ua/msme-adjacent",
        case_rows=g7.default_readiness_candidate_rows(),
    )

    assert [row.case_id for row in candidate_set.cases] == [
        "ua-msme-affordable-loans-2022",
        "ua-msme-energy-resilience-2022",
        "ua-msme-export-credit-2022",
        "ua-msme-displaced-firm-recovery-2022",
    ]
    assert candidate_set.case_count == 4
    assert candidate_set.coverage_authority_status == "control_plane_only"
    assert all("universal_claim_authority" in row.may_not_use_for for row in candidate_set.cases)
    assert {
        row.candidate_source for row in candidate_set.cases if row.case_id != "ua-msme-affordable-loans-2022"
    } == {"readiness_control_plane_fixture"}


def test_g7_region_candidate_set_accepts_new_shaped_case_without_code_change() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    candidate_set = g7.build_g7_region_candidate_set(
        region_ref="region://ua/msme-adjacent",
        case_rows=[
            {
                "case_id": "ua-msme-working-capital-synthetic",
                "adjacency_basis_refs": ["adjacency://ua-msme/support-instrument"],
                "demand_refs": ["demand://s12/ua-msme/working-capital"],
                "search_ledger_refs": [
                    "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json"
                ],
                "declared_envelope_refs": ["envelope://g7/ua-msme-adjacent"],
            }
        ],
    )

    assert candidate_set.case_count == 1
    assert candidate_set.cases[0].case_id == "ua-msme-working-capital-synthetic"
    assert candidate_set.cases[0].candidate_source == "external_candidate_input"


def test_g7_hardcoded_candidate_rows_do_not_satisfy_coverage() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    candidate_set = g7.build_g7_region_candidate_set(
        region_ref="region://ua/msme-adjacent",
        case_rows=g7.default_readiness_candidate_rows(),
    )
    matrix = g7.build_g7_region_grounding_matrix(
        candidate_set=candidate_set,
        search_discovery_refs=(),
    )

    assert matrix.coverage_status == "blocked_control_plane_only"
    assert "layer3_g7_candidate_set_hardcoded_as_coverage" in matrix.issue_codes


def test_g7_grounding_matrix_joins_seed_case_and_blocks_missing_adjacent_refs() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    candidate_set = g7.build_g7_region_candidate_set(
        region_ref="region://ua/msme-adjacent",
        case_rows=g7.default_readiness_candidate_rows(),
    )
    matrix = g7.build_g7_region_grounding_matrix(
        candidate_set=candidate_set,
        search_discovery_refs=("search://g1/free-growth/ua-msme-adjacent",),
    )
    rows = {row.case_id: row for row in matrix.rows}

    seed = rows["ua-msme-affordable-loans-2022"]
    adjacent = rows["ua-msme-energy-resilience-2022"]

    assert seed.g5_conversion_outcome == "unchanged_blocker"
    assert seed.row_grounding_status == "blocked_current_g5_unchanged_blocker"
    assert "layer3_g7_current_g5_unchanged_blocker" in seed.issue_codes
    assert adjacent.row_grounding_status == "blocked_missing_grounding_matrix_refs"
    assert "layer3_g7_region_case_without_grounding_matrix" in adjacent.issue_codes
    assert matrix.search_recall_freshness_join.search_authoritative_for == ()
    assert "search_hit_as_authority" in matrix.search_recall_freshness_join.search_may_not_use_for


def test_g7_search_hits_without_grounded_records_remain_control_plane() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    candidate_set = g7.build_g7_region_candidate_set(
        region_ref="region://ua/msme-adjacent",
        case_rows=[
            {
                "case_id": "ua-msme-search-only-synthetic",
                "adjacency_basis_refs": ["adjacency://ua-msme/search-only"],
                "search_ledger_refs": ["search-ledger://synthetic/hit"],
                "declared_envelope_refs": ["envelope://g7/ua-msme-adjacent"],
            }
        ],
    )
    matrix = g7.build_g7_region_grounding_matrix(
        candidate_set=candidate_set,
        search_discovery_refs=("search://g1/search-hit-only",),
    )

    assert matrix.coverage_status == "blocked_search_control_plane_only"
    assert "layer3_g7_search_hit_counted_as_coverage" in matrix.issue_codes
    assert matrix.rows[0].row_grounding_status == "control_plane_candidate"


def test_g7_does_not_count_current_g5_unchanged_blocker_as_region_grounded() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    bundle = g7.build_layer3_g7_bundle(g7.DEFAULT_REPO_ROOT)

    assert bundle.region_conversion_status_matrix.grounded_region_case_count == 0
    assert bundle.region_value_closure_status == (
        "blocked_by_current_g5_unchanged_blocker"
    )
    assert "layer3_g7_g5_unchanged_blocker_counted_as_grounded" not in (
        bundle.region_conversion_status_matrix.issue_codes
    )


def test_g7_future_grounded_region_cases_count_only_after_g5_grounding() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(),
    )

    assert sum(row.is_grounded for row in records) >= 2
    assert all(row.source_class != "fixture_only" for row in records)


def test_g7_grounded_record_without_governed_promotion_is_blocked() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(
            governed_promotion_status="missing"
        ),
    )

    assert sum(row.is_grounded for row in records) == 0
    assert "layer3_g7_grounded_case_without_governed_promotion" in {
        code for row in records for code in row.issue_codes
    }


def test_g7_governed_promotion_join_requires_full_g4_gate_shape() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(
            omit_g4_gate_ref="weakest_boundary_composition_ref",
        ),
    )

    assert sum(row.is_grounded for row in records) == 0
    assert "layer3_g7_g4_promotion_gate_shape_missing" in {
        code for row in records for code in row.issue_codes
    }


def test_g7_does_not_count_g4_mapping_fallback_as_governed() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(
            g4_record_source="mapping_fallback_blocked",
        ),
    )

    assert sum(row.is_grounded for row in records) == 0
    assert "layer3_g7_g4_mapping_fallback_counted_as_governed" in {
        code for row in records for code in row.issue_codes
    }


def test_g7_current_repo_blocks_sublinear_cost_without_grounded_cases() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    bundle = g7.build_layer3_g7_bundle(g7.DEFAULT_REPO_ROOT)
    reuse = g7.build_g7_mechanism_reuse_ledger(
        conversion_records=bundle.region_conversion_status_matrix.records
    )
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=bundle.region_conversion_status_matrix.records,
        mechanism_reuse_ledger=reuse,
    )

    assert cost.sublinear_marginal_cost_status == "blocked_insufficient_grounded_cases"
    assert "layer3_g7_sublinear_claim_without_grounded_cases" in cost.issue_codes


def test_g7_bespoke_patch_blocks_reuse_and_sublinear_cost() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    ledger = g7.build_g7_mechanism_reuse_ledger(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        bespoke_patch_refs=("one-off://ua-msme/custom-energy-template",),
    )
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        mechanism_reuse_ledger=ledger,
    )

    assert ledger.reuse_status == "blocked_by_bespoke_patch"
    assert cost.sublinear_marginal_cost_status != "pass"
    assert "layer3_g7_bespoke_patch_counted_as_reuse" in cost.issue_codes


def test_g7_sublinear_cost_requires_s12_growth_thermometer() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.synthetic_future_grounded_region_records()
    reuse = g7.build_g7_mechanism_reuse_ledger(conversion_records=records)
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=records,
        mechanism_reuse_ledger=reuse,
        s12_growth_thermometer_projection=None,
    )

    assert cost.sublinear_marginal_cost_status != "pass"
    assert "layer3_g7_s12_growth_thermometer_missing" in cost.issue_codes


def test_g7_s12_projection_requires_certified_delta_for_counted_growth() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    projection = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        growth_without_envelope_delta_count=1,
        growth_counting_disposition="counted_mechanism_growth",
    )

    assert projection.status != "pass"
    assert "layer3_g7_s12_growth_without_certified_delta" in projection.issue_codes


def test_g7_s12_projection_preserves_pending_s14_and_deny_list() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    projection = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        held_out_status="executed",
        may_not_use_for=("production_authority",),
    )

    assert projection.status != "pass"
    assert "layer3_g7_s12_held_out_status_overclaimed" in projection.issue_codes
    assert "layer3_g7_s12_deny_list_omitted" in projection.issue_codes


def test_g7_future_region_cost_passes_when_reuse_is_real() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.synthetic_future_grounded_region_records()
    growth = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=records,
        demand_pull_refs=("s12-growth://ua-msme-adjacent/future",),
        accountable_principal_refs=("principal://ua-msme/region-owner",),
    )
    reuse = g7.build_g7_mechanism_reuse_ledger(
        conversion_records=records,
        s12_growth_thermometer_projection=growth,
    )
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=records,
        mechanism_reuse_ledger=reuse,
        s12_growth_thermometer_projection=growth,
    )

    assert reuse.mechanism_reuse_rate >= 0.5
    assert cost.marginal_cost_ratio_to_seed < 1.0
    assert cost.sublinear_marginal_cost_status == "pass"


def test_g7_current_region_expansion_stays_flat_without_grounded_cases() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    bundle = g7.build_layer3_g7_bundle(g7.DEFAULT_REPO_ROOT)
    delta = g7.build_g7_region_envelope_expansion_delta(
        conversion_records=bundle.region_conversion_status_matrix.records
    )
    health = g7.build_g7_health_metric_delta(region_envelope_expansion_delta=delta)

    assert delta.envelope_expansion_rate == 0.0
    assert delta.expanded_case_count == 0
    assert delta.expansion_status == "flat"
    assert health.metrics["envelope-expansion-rate(region)"] == "flat"


def test_g7_future_grounded_fixture_yields_positive_region_expansion() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    delta = g7.build_g7_region_envelope_expansion_delta(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        certified_envelope_delta_refs=("s13-envelope-delta://ua-msme/expand-region",),
        materialized_from_s12_growth_entry_ref=(
            "s12-growth-entry://ua-msme-adjacent/future"
        ),
        assurance_case_delta_ref="s13-assurance-case-delta://ua-msme/expand-region",
    )

    assert delta.expansion_status == "pass"
    assert delta.expanded_case_count >= 2
    assert delta.envelope_expansion_rate > 0.0


def test_g7_region_expansion_requires_s13_certified_expand_delta() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    delta = g7.build_g7_region_envelope_expansion_delta(
        conversion_records=g7.synthetic_future_grounded_region_records(),
        certified_envelope_delta_refs=(),
    )

    assert delta.expansion_status != "pass"
    assert "layer3_g7_s13_certified_delta_missing" in delta.issue_codes


def test_g7_pending_delta_is_not_counted_as_region_expansion() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    for direction in ("pending", "hold", "shrink", "split"):
        delta = g7.build_g7_region_envelope_expansion_delta(
            conversion_records=g7.synthetic_future_grounded_region_records(),
            certified_envelope_delta_refs=(
                f"s13-envelope-delta://ua-msme/{direction}",
            ),
            envelope_revision_direction=direction,
        )

        assert delta.expanded_case_count == 0
        assert "layer3_g7_pending_delta_counted_as_expansion" in delta.issue_codes


def test_g7_semantic_loss_blocks_sublinear_cost_pass() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.synthetic_future_grounded_region_records()
    growth = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=records,
        demand_pull_refs=("s12-growth://ua-msme-adjacent/future",),
        accountable_principal_refs=("principal://ua-msme/region-owner",),
    )
    reuse = g7.build_g7_mechanism_reuse_ledger(
        conversion_records=records,
        s12_growth_thermometer_projection=growth,
    )
    semantic_loss = g7.build_g7_region_semantic_loss_ledger(
        conversion_records=records,
        source_truth_lost_case_ids=("ua-msme-energy-resilience-2022",),
    )
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=records,
        mechanism_reuse_ledger=reuse,
        s12_growth_thermometer_projection=growth,
        semantic_loss_ledger=semantic_loss,
    )

    assert semantic_loss.semantic_loss_status == "blocked"
    assert cost.marginal_cost_ratio_to_seed < 1.0
    assert cost.sublinear_marginal_cost_status == "blocked_semantic_loss"
    assert "layer3_g7_semantic_loss_hidden_by_region_score" in cost.issue_codes


def test_g7_status_composition_downgrades_conflicting_region_scorecard() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.build_g7_region_conversion_records(
        region_ref="region://ua/msme-adjacent",
        conversion_inputs=g7.synthetic_future_grounded_region_records(
            governed_promotion_status="missing"
        ),
    )
    matrix = g7.build_g7_region_conversion_status_matrix(
        region_ref="region://ua/msme-adjacent",
        records=records,
    )
    delta = g7.build_g7_region_envelope_expansion_delta(conversion_records=records)
    semantic_loss = g7.build_g7_region_semantic_loss_ledger(
        conversion_records=records,
        caveats_dropped_case_ids=("ua-msme-energy-resilience-2022",),
    )
    reuse = g7.build_g7_mechanism_reuse_ledger(conversion_records=records)
    cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=records,
        mechanism_reuse_ledger=reuse,
        semantic_loss_ledger=semantic_loss,
    )
    status = g7.build_g7_status_composition_ledger(
        region_conversion_status_matrix=matrix,
        region_envelope_expansion_delta=delta,
        semantic_loss_ledger=semantic_loss,
        marginal_cost_ledger=cost,
        s14_feed_status="blocked_no_real_grounded_breadth",
        public_projection_status_claim="pass",
    )

    assert status.status != "pass"
    assert "layer3_g7_status_composition_missing" in status.issue_codes
    assert "layer3_g7_s14_feed_missing" in status.issue_codes


def test_g7_s14_feed_blocks_fixture_breadth() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    feed = g7.build_g7_s14_grounded_breadth_feed(
        region_ref="region://ua/msme-adjacent",
        conversion_records=[],
        fixture_grounded_refs=("fixture://s14/dev-grounded-authority",),
    )

    assert feed.status == "blocked_no_real_grounded_breadth"
    assert "layer3_g7_s14_feed_uses_fixtures" in feed.issue_codes


def test_g7_s14_feed_blocks_current_g5_and_g6_candidates() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    current = g7.build_layer3_g7_bundle(g7.DEFAULT_REPO_ROOT)
    current_feed = g7.build_g7_s14_grounded_breadth_feed(
        region_ref="region://ua/msme-adjacent",
        conversion_records=current.region_conversion_status_matrix.records,
    )
    g6_feed = g7.build_g7_s14_grounded_breadth_feed(
        region_ref="region://ua/msme-adjacent",
        conversion_records=[],
        g6_candidate_refs=("g6-candidate://ua-msme/free-text",),
    )

    assert current_feed.status == "blocked_no_real_grounded_breadth"
    assert "layer3_g7_current_g5_unchanged_blocker" in current_feed.issue_codes
    assert g6_feed.status == "blocked_no_real_grounded_breadth"
    assert "layer3_g7_g6_candidate_counted_as_grounded" in g6_feed.issue_codes


def test_g7_s14_feed_builds_consumer_ready_manifest_for_future_grounded_breadth() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.synthetic_future_grounded_region_records()
    expansion = g7.build_g7_region_envelope_expansion_delta(
        conversion_records=records,
        certified_envelope_delta_refs=("s13-envelope-delta://ua-msme/expand-region",),
        materialized_from_s12_growth_entry_ref=(
            "s12-growth-entry://ua-msme-adjacent/future"
        ),
        assurance_case_delta_ref="s13-assurance-case-delta://ua-msme/expand-region",
    )
    feed = g7.build_g7_s14_grounded_breadth_feed(
        region_ref="region://ua/msme-adjacent",
        conversion_records=records,
        region_envelope_expansion_delta=expansion,
    )
    projection = g7.build_g7_s14_mechanism_generality_projection(
        s12_growth_thermometer_projection=g7.build_g7_s12_growth_thermometer_projection(
            conversion_records=records,
            demand_pull_refs=("s12-growth://ua-msme-adjacent/future",),
            accountable_principal_refs=("principal://ua-msme/region-owner",),
        )
    )
    manifest = g7.build_g7_s14_battery_input_manifest(
        grounded_breadth_feed=feed,
        mechanism_generality_projection=projection,
    )

    assert feed.status == "pass"
    assert feed.grounded_region_case_refs
    assert manifest.sealed_battery_mutation_status == "not_mutated"
    assert manifest.hidden_case_access_status == "not_accessed_by_g7"
    assert "s14_universality" in manifest.may_not_use_for


def test_g7_s14_consumer_gate_blocks_missing_manifest_and_bare_universal_claim() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    gate = g7.build_g7_s14_consumer_gate(
        s14_battery_input_manifest=None,
        universality_claim_text="This region result is universal.",
    )

    assert gate.status == "blocked"
    assert gate.missing_capability_label == "consumer_missing"
    assert "layer3_g7_s14_battery_input_manifest_missing" in gate.issue_codes
    assert "layer3_g7_universal_claim_without_s14_gate" in gate.issue_codes


def test_g7_s14_consumer_gate_blocks_aggregate_score_and_hidden_payload() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    records = g7.synthetic_future_grounded_region_records()
    feed = g7.build_g7_s14_grounded_breadth_feed(
        region_ref="region://ua/msme-adjacent",
        conversion_records=records,
        region_envelope_expansion_delta=g7.build_g7_region_envelope_expansion_delta(
            conversion_records=records,
            certified_envelope_delta_refs=("s13-envelope-delta://ua-msme/expand-region",),
            materialized_from_s12_growth_entry_ref=(
                "s12-growth-entry://ua-msme-adjacent/future"
            ),
            assurance_case_delta_ref="s13-assurance-case-delta://ua-msme/expand-region",
        ),
    )
    projection = g7.build_g7_s14_mechanism_generality_projection(
        s12_growth_thermometer_projection=g7.build_g7_s12_growth_thermometer_projection(
            conversion_records=records,
            demand_pull_refs=("s12-growth://ua-msme-adjacent/future",),
            accountable_principal_refs=("principal://ua-msme/region-owner",),
        ),
        one_off_growth_refs=("one-off://ua-msme/custom-template",),
    )
    manifest = g7.build_g7_s14_battery_input_manifest(
        grounded_breadth_feed=feed,
        mechanism_generality_projection=projection,
    )
    gate = g7.build_g7_s14_consumer_gate(
        s14_battery_input_manifest=manifest,
        public_projection_payload={
            "aggregate_universal_score": 0.91,
            "sealed_gold_label_ref": "sealed://s14/gold/secret",
            "authority_boundary": {"authoritative_for": ["production_authority"]},
        },
    )

    assert gate.status == "blocked"
    assert "layer3_g7_s14_manifest_runner_output_conflated" not in gate.issue_codes
    assert "aggregate_universal_number_laundering" in gate.s14_authority_issue_codes
    assert "gold_label_leak_into_dev_signal" in gate.s14_authority_issue_codes
    assert "layer3_g7_public_projection_authority_leak" in gate.issue_codes
    assert "layer3_g7_bespoke_patch_counted_as_reuse" in gate.issue_codes


def _build_g7_task8_inputs() -> dict[str, object]:
    from polisyos.runtime.quality import layer3_region_widening as g7

    region_ref = "region://ua/msme-adjacent"
    records = g7.build_g7_region_conversion_records(
        region_ref=region_ref,
        conversion_inputs=g7.synthetic_future_grounded_region_records(),
    )
    conversion_matrix = g7.build_g7_region_conversion_status_matrix(
        region_ref=region_ref,
        records=records,
    )
    s12_projection = g7.build_g7_s12_growth_thermometer_projection(
        conversion_records=records,
        demand_pull_refs=("s12-growth://ua-msme-adjacent/future",),
        accountable_principal_refs=("principal://ua-msme/region-owner",),
    )
    mechanism_reuse = g7.build_g7_mechanism_reuse_ledger(
        conversion_records=records,
        s12_growth_thermometer_projection=s12_projection,
    )
    expansion = g7.build_g7_region_envelope_expansion_delta(
        conversion_records=records,
        certified_envelope_delta_refs=("s13-envelope-delta://ua-msme/expand-region",),
        materialized_from_s12_growth_entry_ref="s12-growth-entry://ua-msme/future",
        assurance_case_delta_ref="s13-assurance-case-delta://ua-msme/expand-region",
    )
    semantic_loss = g7.build_g7_region_semantic_loss_ledger(conversion_records=records)
    marginal_cost = g7.build_g7_marginal_grounding_cost_ledger(
        conversion_records=records,
        s12_growth_thermometer_projection=s12_projection,
        mechanism_reuse_ledger=mechanism_reuse,
        semantic_loss_ledger=semantic_loss,
    )
    s14_feed = g7.build_g7_s14_grounded_breadth_feed(
        region_ref=region_ref,
        conversion_records=records,
        region_envelope_expansion_delta=expansion,
    )
    status_ledger = g7.build_g7_status_composition_ledger(
        region_conversion_status_matrix=conversion_matrix,
        region_envelope_expansion_delta=expansion,
        semantic_loss_ledger=semantic_loss,
        marginal_cost_ledger=marginal_cost,
        s14_feed_status=s14_feed.status,
        public_projection_status_claim="pass",
    )
    s14_generality = g7.build_g7_s14_mechanism_generality_projection(
        s12_growth_thermometer_projection=s12_projection,
    )
    s14_manifest = g7.build_g7_s14_battery_input_manifest(
        grounded_breadth_feed=s14_feed,
        mechanism_generality_projection=s14_generality,
    )
    s14_gate = g7.build_g7_s14_consumer_gate(
        s14_battery_input_manifest=s14_manifest,
    )
    return {
        "region_ref": region_ref,
        "records": records,
        "conversion_matrix": conversion_matrix,
        "s12_projection": s12_projection,
        "mechanism_reuse": mechanism_reuse,
        "expansion": expansion,
        "semantic_loss": semantic_loss,
        "marginal_cost": marginal_cost,
        "s14_feed": s14_feed,
        "status_ledger": status_ledger,
        "s14_manifest": s14_manifest,
        "s14_gate": s14_gate,
    }


def test_g7_region_scorecard_and_public_surface_are_projection_only() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    inputs = _build_g7_task8_inputs()
    scorecard = g7.build_g7_region_scorecard(
        region_ref=inputs["region_ref"],
        region_conversion_status_matrix=inputs["conversion_matrix"],
        status_composition_ledger=inputs["status_ledger"],
        mechanism_reuse_ledger=inputs["mechanism_reuse"],
        marginal_cost_ledger=inputs["marginal_cost"],
        s14_grounded_breadth_feed=inputs["s14_feed"],
    )
    surface = g7.build_g7_region_widening_audit_surface(
        scorecard=scorecard,
        s12_growth_thermometer_projection=inputs["s12_projection"],
        region_envelope_expansion_delta=inputs["expansion"],
        semantic_loss_ledger=inputs["semantic_loss"],
        s14_battery_input_manifest=inputs["s14_manifest"],
        s14_consumer_gate=inputs["s14_gate"],
    )
    public_refs = g7.build_g7_public_export_projection_refs(audit_surface=surface)

    public = surface.PUBLIC
    assert scorecard.region_ref == "region://ua/msme-adjacent"
    assert scorecard.grounded_case_count == 2
    assert public["authority_role"] == "projection_only"
    assert public["official_use_limited_to"] == [
        "public_audit",
        "operator_triage",
        "external_explanation",
    ]
    assert {"approval_authority", "scorecard_authority", "runtime_closeout_authority"} <= set(
        public["may_not_be_used_for"]
    )
    assert public["s12_resource_projection_contract_status"] == "pass"
    assert public["s13_post_deploy_accountability_projection_contract_status"] == "pass"
    assert public["s14_universality_projection_contract_status"] == "pass"
    assert public_refs.status == "pass"
    assert public_refs.PUBLIC["authority_role"] == "projection_only"
    assert "raw_case_payload" not in public
    assert "recommendation_text" not in public
    assert "aggregate_universal_score" not in public


def test_g7_public_surface_blocks_raw_hidden_or_authority_shaped_projection() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    inputs = _build_g7_task8_inputs()
    scorecard = g7.build_g7_region_scorecard(
        region_ref=inputs["region_ref"],
        region_conversion_status_matrix=inputs["conversion_matrix"],
        status_composition_ledger=inputs["status_ledger"],
        mechanism_reuse_ledger=inputs["mechanism_reuse"],
        marginal_cost_ledger=inputs["marginal_cost"],
        s14_grounded_breadth_feed=inputs["s14_feed"],
    )
    surface = g7.build_g7_region_widening_audit_surface(
        scorecard=scorecard,
        s12_growth_thermometer_projection=inputs["s12_projection"],
        region_envelope_expansion_delta=inputs["expansion"],
        semantic_loss_ledger=inputs["semantic_loss"],
        s14_battery_input_manifest=inputs["s14_manifest"],
        s14_consumer_gate=inputs["s14_gate"],
        public_projection_overrides={
            "authority_role": "producer_authority",
            "hidden_case_payload": {"case_id": "sealed-s14-case"},
            "raw_evidence_payload": {"private": True},
            "legal_advice": "approve rollout",
            "aggregate_universal_score": 0.97,
        },
    )

    assert surface.status == "fail"
    assert "layer3_g7_public_raw_payload_leak" in surface.issue_codes
    assert "layer3_g7_public_projection_authority_leak" in surface.issue_codes
    assert "layer3_g7_universal_claim_without_s14_gate" in surface.issue_codes
    assert "layer3_g7_public_projection_contract_failed" in surface.issue_codes


def test_g7_public_surface_blocks_missing_deny_list_and_contract_status() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    inputs = _build_g7_task8_inputs()
    scorecard = g7.build_g7_region_scorecard(
        region_ref=inputs["region_ref"],
        region_conversion_status_matrix=inputs["conversion_matrix"],
        status_composition_ledger=inputs["status_ledger"],
        mechanism_reuse_ledger=inputs["mechanism_reuse"],
        marginal_cost_ledger=inputs["marginal_cost"],
        s14_grounded_breadth_feed=inputs["s14_feed"],
    )
    surface = g7.build_g7_region_widening_audit_surface(
        scorecard=scorecard,
        s12_growth_thermometer_projection=inputs["s12_projection"],
        region_envelope_expansion_delta=inputs["expansion"],
        semantic_loss_ledger=inputs["semantic_loss"],
        s14_battery_input_manifest=inputs["s14_manifest"],
        s14_consumer_gate=inputs["s14_gate"],
        public_projection_overrides={
            "may_not_be_used_for": ("claim_authority",),
            "official_use_limited_to": ("public_audit",),
            "s12_public_growth_limitation": "",
        },
    )

    assert surface.status == "fail"
    assert "layer3_g7_projection_omits_required_deny_list" in surface.issue_codes
    assert "layer3_g7_public_projection_contract_failed" in surface.issue_codes


def test_g7_replay_manifest_uses_shared_helpers_and_preserves_closed_refs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    inputs = _build_g7_task8_inputs()
    scorecard = g7.build_g7_region_scorecard(
        region_ref=inputs["region_ref"],
        region_conversion_status_matrix=inputs["conversion_matrix"],
        status_composition_ledger=inputs["status_ledger"],
        mechanism_reuse_ledger=inputs["mechanism_reuse"],
        marginal_cost_ledger=inputs["marginal_cost"],
        s14_grounded_breadth_feed=inputs["s14_feed"],
    )
    surface = g7.build_g7_region_widening_audit_surface(
        scorecard=scorecard,
        s12_growth_thermometer_projection=inputs["s12_projection"],
        region_envelope_expansion_delta=inputs["expansion"],
        semantic_loss_ledger=inputs["semantic_loss"],
        s14_battery_input_manifest=inputs["s14_manifest"],
        s14_consumer_gate=inputs["s14_gate"],
    )
    calls = {"continuity": 0, "replay": 0}
    real_continuity = g7.build_nl_replay_orchestration_continuity
    real_replay = g7.build_replay_manifest

    def spy_continuity(**kwargs: object) -> dict[str, object]:
        calls["continuity"] += 1
        return real_continuity(**kwargs)

    def spy_replay(**kwargs: object) -> dict[str, object]:
        calls["replay"] += 1
        return real_replay(**kwargs)

    monkeypatch.setattr(g7, "build_nl_replay_orchestration_continuity", spy_continuity)
    monkeypatch.setattr(g7, "build_replay_manifest", spy_replay)
    upstream_refs = {
        "g5": {
            "ref": "repo://architecture/policy_design_case/layer3_g5_replay_manifest.json",
            "fingerprint": "sha256:" + "5" * 64,
        },
        "g6": {
            "ref": "repo://architecture/policy_design_case/layer3_g6_replay_manifest.json",
            "fingerprint": "sha256:" + "6" * 64,
        },
    }
    continuity = g7.build_g7_orchestration_continuity(
        scorecard=scorecard,
        audit_surface=surface,
        upstream_closed_case_replay_refs=upstream_refs,
    )
    replay = g7.build_g7_replay_manifest(
        scorecard=scorecard,
        audit_surface=surface,
        orchestration_continuity=continuity,
        upstream_closed_case_replay_refs=upstream_refs,
    )

    assert calls == {"continuity": 1, "replay": 1}
    assert continuity.status == "pass"
    assert replay.status == "pass"
    assert replay.manifest["dependency_fingerprints"][
        "upstream_closed_g5_replay_fingerprint"
    ] == upstream_refs["g5"]["fingerprint"]
    assert replay.manifest["dependency_fingerprints"][
        "scorecard_fingerprint"
    ] == scorecard.scorecard_fingerprint
    assert replay.manifest["orchestration_continuity"]["status"] == "pass"


def test_g7_replay_continuity_blocks_mutated_closed_payloads() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    inputs = _build_g7_task8_inputs()
    scorecard = g7.build_g7_region_scorecard(
        region_ref=inputs["region_ref"],
        region_conversion_status_matrix=inputs["conversion_matrix"],
        status_composition_ledger=inputs["status_ledger"],
        mechanism_reuse_ledger=inputs["mechanism_reuse"],
        marginal_cost_ledger=inputs["marginal_cost"],
        s14_grounded_breadth_feed=inputs["s14_feed"],
    )
    surface = g7.build_g7_region_widening_audit_surface(
        scorecard=scorecard,
        s12_growth_thermometer_projection=inputs["s12_projection"],
        region_envelope_expansion_delta=inputs["expansion"],
        semantic_loss_ledger=inputs["semantic_loss"],
        s14_battery_input_manifest=inputs["s14_manifest"],
        s14_consumer_gate=inputs["s14_gate"],
    )
    continuity = g7.build_g7_orchestration_continuity(
        scorecard=scorecard,
        audit_surface=surface,
        upstream_closed_case_replay_refs={
            "g5": {
                "ref": "repo://architecture/policy_design_case/layer3_g5_replay_manifest.json",
                "fingerprint": "sha256:" + "5" * 64,
            }
        },
        upstream_closed_case_payloads={
            "g5": {"status": "rewritten_by_g7", "closed_payload": {"mutated": True}},
        },
    )

    assert continuity.status == "fail"
    assert "layer3_g7_closed_case_replay_mutated" in continuity.issue_codes


def test_g7_conformance_report_covers_every_required_negative() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    inputs = _build_g7_task8_inputs()
    scorecard = g7.build_g7_region_scorecard(
        region_ref=inputs["region_ref"],
        region_conversion_status_matrix=inputs["conversion_matrix"],
        status_composition_ledger=inputs["status_ledger"],
        mechanism_reuse_ledger=inputs["mechanism_reuse"],
        marginal_cost_ledger=inputs["marginal_cost"],
        s14_grounded_breadth_feed=inputs["s14_feed"],
    )
    surface = g7.build_g7_region_widening_audit_surface(
        scorecard=scorecard,
        s12_growth_thermometer_projection=inputs["s12_projection"],
        region_envelope_expansion_delta=inputs["expansion"],
        semantic_loss_ledger=inputs["semantic_loss"],
        s14_battery_input_manifest=inputs["s14_manifest"],
        s14_consumer_gate=inputs["s14_gate"],
    )
    upstream_refs = {
        "g5": {
            "ref": "repo://architecture/policy_design_case/layer3_g5_replay_manifest.json",
            "fingerprint": "sha256:" + "5" * 64,
        },
        "g6": {
            "ref": "repo://architecture/policy_design_case/layer3_g6_replay_manifest.json",
            "fingerprint": "sha256:" + "6" * 64,
        },
    }
    continuity = g7.build_g7_orchestration_continuity(
        scorecard=scorecard,
        audit_surface=surface,
        upstream_closed_case_replay_refs=upstream_refs,
    )
    replay = g7.build_g7_replay_manifest(
        scorecard=scorecard,
        audit_surface=surface,
        orchestration_continuity=continuity,
        upstream_closed_case_replay_refs=upstream_refs,
    )

    report = g7.build_g7_conformance_report(
        repo_root=g7.DEFAULT_REPO_ROOT,
        dependency_readiness_snapshot=g7.build_g7_dependency_readiness_snapshot(
            g7.DEFAULT_REPO_ROOT
        ),
        region_grounding_matrix=g7.build_g7_region_grounding_matrix(
            candidate_set=g7.build_g7_region_candidate_set(
                region_ref="region://ua/msme-adjacent",
                case_rows=g7.default_readiness_candidate_rows(),
            ),
            search_discovery_refs=("search://g1/free-growth/ua-msme-adjacent",),
        ),
        region_conversion_status_matrix=inputs["conversion_matrix"],
        status_composition_ledger=inputs["status_ledger"],
        s12_growth_thermometer_projection=inputs["s12_projection"],
        mechanism_reuse_ledger=inputs["mechanism_reuse"],
        marginal_cost_ledger=inputs["marginal_cost"],
        region_envelope_expansion_delta=inputs["expansion"],
        semantic_loss_ledger=inputs["semantic_loss"],
        s14_grounded_breadth_feed=inputs["s14_feed"],
        s14_battery_input_manifest=inputs["s14_manifest"],
        s14_consumer_gate=inputs["s14_gate"],
        audit_surface=surface,
        replay_manifest=replay,
        orchestration_continuity=continuity,
        registration_statuses={
            "generated_artifacts": "pass",
            "inventory": "pass",
            "docs": "pass",
            "route_contract_registry": "pass",
        },
        manifest_runtime_drift_keys=(),
        replay_helper_status="pass",
    )
    results = {result.negative_id: result for result in report.negative_results}

    assert set(g7.REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS) == (
        REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS
    )
    assert set(results) == REQUIRED_G7_CONFORMANCE_NEGATIVE_IDS
    assert report.status == "pass"
    assert all(result.status == "pass" for result in report.negative_results)
    assert all(result.expected_issue_codes for result in report.negative_results)
    assert all(result.observed_issue_codes for result in report.negative_results)
    assert set(results["public_projection_authority_leak"].expected_issue_codes) == {
        "layer3_g7_public_projection_authority_leak"
    }
    assert "layer3_g7_public_projection_authority_leak" in (
        results["public_projection_authority_leak"].observed_issue_codes
    )
    assert "layer3_g7_replay_helper_bypassed" in (
        results["replay_helper_bypassed"].observed_issue_codes
    )


def test_g7_conformance_report_fails_closed_when_negative_missing_or_unobserved() -> None:
    from polisyos.runtime.quality import layer3_region_widening as g7

    missing = g7.build_g7_conformance_report(
        repo_root=g7.DEFAULT_REPO_ROOT,
        required_negative_ids=("public_projection_authority_leak", "missing_negative"),
        observed_negative_issue_codes={
            "public_projection_authority_leak": (
                "layer3_g7_public_projection_authority_leak",
            )
        },
    )
    unobserved = g7.build_g7_conformance_report(
        repo_root=g7.DEFAULT_REPO_ROOT,
        required_negative_ids=("public_projection_authority_leak",),
        observed_negative_issue_codes={"public_projection_authority_leak": ()},
    )

    assert missing.status == "fail"
    assert "missing_negative" in missing.missing_negative_ids
    assert "missing_negative" in missing.issue_codes
    assert unobserved.status == "fail"
    assert "public_projection_authority_leak" in unobserved.failing_negative_ids
