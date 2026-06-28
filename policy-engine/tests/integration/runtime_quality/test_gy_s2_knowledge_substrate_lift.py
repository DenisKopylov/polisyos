"""GY-S2 runtime lift checks against the real L2/L3 knowledge stores."""

from __future__ import annotations

from pathlib import Path

from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
from polisyos.lex.knowledge.store import LegalKnowledgeStore
from polisyos.runtime.quality.substrate_registry import (
    SubstrateLayer,
    build_substrate_registry_from_existing_catalogs,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
L2_DB = (
    REPO_ROOT
    / "production_data/policyos_academic_runtime_slim_20260411T112032Z"
    / "academic/graph/scholar_knowledge.duckdb"
)
L3_DB = (
    REPO_ROOT
    / "production_data/lex/lex-amendment-only-optimized-20260501-v3"
    / "finalize/lex_knowledge_graph.duckdb"
)


L2_ESTIMATE_ID = "179aff173ec40e640b535514"
L2_EDGE_ID = "06fb46cd681818bc52d1cc01"
L2_CONTESTED_EDGE_ID = "aa4d86b83f216207989339f6"
L3_THRESHOLD_ID = "a5429abb6621acb11ed10b20"
L3_AMENDMENT_ID = "17bd5016053d883db190603c"
L3_YEAR_GTE_THRESHOLD_ID = "0017d256e4c232f4e4831c6e"
L3_DAY_LTE_THRESHOLD_ID = "72d0367ea085795e811da112"
L3_CURRENCY_EQ_THRESHOLD_ID = "019cab2db39f0f14b0051ed5"
L3_LINEAGE_DOC_FAMILY_ID = "05640c577d76bebf85"
L3_LINEAGE_OLD_THRESHOLD_ID = "2a516f4ad0a279af6cbc19cd"
L3_SUPERSEDED_THRESHOLD_ID = "9d73aecb2a07e040897f34bf"


def test_l2_parameter_estimate_lowers_to_interval_value_outer_set() -> None:
    query = SKGQuery(L2_DB, L2_DB.parent)

    value_set = query.parameter_estimate_value_outer_set(
        estimate_id=L2_ESTIMATE_ID,
        world_model_record_ref="repo://architecture/policy_design_case/layer3_gy_world_model_record_contract.json",
        epoch="skg:1",
    )
    lower_trust = query.parameter_estimate_value_outer_set(
        estimate_id=L2_ESTIMATE_ID,
        world_model_record_ref="repo://architecture/policy_design_case/layer3_gy_world_model_record_contract.json",
        epoch="skg:1",
        trust_score_override=0.12,
    )

    assert value_set.representation == "interval_box"
    assert value_set.lower[0] < value_set.upper[0]
    assert value_set.width[0] > 0.0
    assert value_set.identification_status != "point"
    assert value_set.data_trust.effective_score > lower_trust.data_trust.effective_score
    assert value_set.promotion_decision().capped_decision_grade != (
        lower_trust.promotion_decision().capped_decision_grade
    )
    assert "l2_design_tier:" in " ".join(value_set.assumptions)


def test_l2_transport_and_contested_edges_lower_to_bounded_nonpoint_sets() -> None:
    query = SKGQuery(L2_DB, L2_DB.parent)
    source = query.parameter_estimate_value_outer_set(
        estimate_id=L2_ESTIMATE_ID,
        world_model_record_ref="repo://architecture/policy_design_case/layer3_gy_world_model_record_contract.json",
        epoch="skg:1",
    )

    transported = query.transport_value_outer_set(
        source,
        edge_id=L2_EDGE_ID,
        target_context_id="UA",
    )
    contested = query.contested_edge_value_outer_set(
        contested_edge_id=L2_CONTESTED_EDGE_ID,
        world_model_record_ref="repo://architecture/policy_design_case/layer3_gy_world_model_record_contract.json",
        epoch="skg:1",
    )

    assert transported.identification_status in {"partial", "proxy"}
    assert transported.width[0] > source.width[0]
    assert "transported_limited" in transported.calibration_scope["lowering_status"]
    untransported = query.transport_value_outer_set(
        source,
        edge_id=L2_EDGE_ID,
        target_context_id="ZZ_WRONG_SCOPE",
    )
    assert untransported.representation_status == "search_only"
    assert untransported.calibration_scope["transport_reason"] == "transport_unavailable_for_scope"
    assert not untransported.promotion_decision().promotable
    assert contested.lower[0] < 0.0 < contested.upper[0]
    assert contested.identification_status == "proxy"
    assert contested.calibration_scope["lowering_status"] == (
        "structural_ambiguity_estimate_envelope"
    )
    assert int(contested.calibration_scope["resolved_claim_count"]) >= 3
    assert int(contested.calibration_scope["estimate_count"]) >= 2


def test_l2_grounding_resolves_content_and_fails_closed_for_unrelated_query() -> None:
    query = SKGQuery(L2_DB, L2_DB.parent)

    matched = query.resolve_grounded_causal_prior(
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        estimand="directional_effect",
        scope_context_id="UA",
        required_skg_version_id=1,
    )
    unrelated = query.resolve_grounded_causal_prior(
        cause="astronomy.star_brightness",
        effect="agriculture.food_nutritional_quality",
        estimand="directional_effect",
        scope_context_id="UA",
        required_skg_version_id=1,
    )
    wrong_scope = query.resolve_grounded_causal_prior(
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        estimand="directional_effect",
        scope_context_id="ZZ_WRONG_SCOPE",
        required_skg_version_id=1,
    )
    alias = query.resolve_grounded_causal_prior(
        cause="agriculture.organic_fertilizer_system",
        effect="agriculture.crop_yield",
        estimand="directional_effect",
        scope_context_id="UA",
        required_skg_version_id=1,
    )

    assert matched.status == "bound"
    assert matched.edge_id == L2_EDGE_ID
    assert matched.relevance_score > 0.0
    assert matched.content_bind_status == "content_bound"
    assert unrelated.status == "blocked"
    assert unrelated.edge_id is None
    assert unrelated.relevance_score < matched.relevance_score
    assert wrong_scope.status == "search_only"
    assert wrong_scope.transport_ref is None
    assert "transport_unavailable_for_scope" in wrong_scope.blockers
    assert alias.status == "bound"
    assert alias.transport_ref is not None


def test_l3_threshold_admits_blocks_units_and_missing_bound_fail_closed() -> None:
    store = LegalKnowledgeStore(L3_DB, L3_DB.parent)

    admitted = store.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=24.0,
        candidate_unit="percent",
        applies_to="25 percent",
    )
    admitted_from_ratio = store.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=0.24,
        candidate_unit="ratio",
        applies_to="25 percent",
    )
    blocked = store.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=26.0,
        candidate_unit="percent",
        applies_to="25 percent",
    )
    missing = store.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=None,
        candidate_unit="percent",
        applies_to="25 percent",
    )
    outside = store.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=24.0,
        candidate_unit="percent",
        applies_to="completely different scope",
    )
    year_admitted = store.evaluate_rule_threshold(
        threshold_id=L3_YEAR_GTE_THRESHOLD_ID,
        candidate_value=22.0,
        candidate_unit="year",
        applies_to="неодружені діти віком до 21 року",
    )
    year_blocked = store.evaluate_rule_threshold(
        threshold_id=L3_YEAR_GTE_THRESHOLD_ID,
        candidate_value=20.0,
        candidate_unit="year",
        applies_to="неодружені діти віком до 21 року",
    )
    day_admitted = store.evaluate_rule_threshold(
        threshold_id=L3_DAY_LTE_THRESHOLD_ID,
        candidate_value=179.0,
        candidate_unit="днів",
        applies_to="строк продовження не більше 180 днів",
    )
    day_blocked = store.evaluate_rule_threshold(
        threshold_id=L3_DAY_LTE_THRESHOLD_ID,
        candidate_value=181.0,
        candidate_unit="днів",
        applies_to="строк продовження не більше 180 днів",
    )
    currency_admitted = store.evaluate_rule_threshold(
        threshold_id=L3_CURRENCY_EQ_THRESHOLD_ID,
        candidate_value=8800.0,
        candidate_unit="грн",
        applies_to=(
            "максимальна інтервенційна ціна (з урахуванням податку на додану "
            "вартість) на цукор-пісок (буряковий)"
        ),
    )
    incompatible = store.evaluate_rule_threshold(
        threshold_id=L3_DAY_LTE_THRESHOLD_ID,
        candidate_value=179.0,
        candidate_unit="грн",
        applies_to="строк продовження не більше 180 днів",
    )

    assert admitted.status == "admitted"
    assert admitted_from_ratio.status == "admitted"
    assert admitted_from_ratio.normalized_candidate_value == 24.0
    assert blocked.status == "blocked"
    assert blocked.reason == "threshold_violated"
    assert missing.status == "blocked"
    assert missing.reason == "candidate_bound_missing"
    assert outside.status == "not_applicable"
    assert year_admitted.status == "admitted"
    assert year_blocked.status == "blocked"
    assert day_admitted.status == "admitted"
    assert day_blocked.status == "blocked"
    assert currency_admitted.status == "admitted"
    assert incompatible.status == "blocked"
    assert incompatible.reason == "unit_incompatible"


def test_l3_amendment_effective_from_gates_temporal_competence() -> None:
    store = LegalKnowledgeStore(L3_DB, L3_DB.parent)

    before = store.resolve_amendment_temporal_competence(
        amendment_id=L3_AMENDMENT_ID,
        as_of="2016-12-31",
    )
    after = store.resolve_amendment_temporal_competence(
        amendment_id=L3_AMENDMENT_ID,
        as_of="2017-01-02",
    )
    old_mid = store.resolve_threshold_temporal_competence(
        threshold_id=L3_LINEAGE_OLD_THRESHOLD_ID,
        as_of="2000-01-01",
    )
    mid_threshold = store.resolve_rule_threshold(
        metric="днів",
        doc_family_id=L3_LINEAGE_DOC_FAMILY_ID,
        as_of="2021-12-01",
    )
    superseded = store.resolve_threshold_temporal_competence(
        threshold_id=L3_SUPERSEDED_THRESHOLD_ID,
        as_of="2036-12-31",
    )

    assert before.status == "not_yet_in_force"
    assert after.status == "in_force"
    assert before.effective_from == after.effective_from == "2017-01-01"
    assert old_mid.status == "in_force"
    assert mid_threshold is not None
    assert mid_threshold.doc_family_id == L3_LINEAGE_DOC_FAMILY_ID
    assert superseded.status == "stale"


def test_s0_registers_l2_and_l3_real_knowledge_substrates() -> None:
    registry = build_substrate_registry_from_existing_catalogs(REPO_ROOT)

    l2 = registry.resolve(
        source_id="l2_scholar_kg:scholar_knowledge.duckdb",
        family_id="l2_scholar_kg_causal_priors_transport",
        layer=SubstrateLayer.L2,
    )[0]
    l3 = registry.resolve(
        source_id="l3_lex_kg:lex_knowledge_graph.duckdb",
        family_id="l3_lex_kg_admissibility_obligations",
        layer=SubstrateLayer.L3,
    )[0]

    assert l2.coverage.coverage_dimensions["table_counts"]["ac_parameter_estimates"] > 0
    assert l2.coverage.coverage_dimensions["table_counts"]["ac_skg_transport_scores"] > 0
    assert l3.coverage.coverage_dimensions["table_counts"]["lex_rule_thresholds"] > 0
    assert l3.coverage.coverage_dimensions["table_counts"]["lex_amendments"] > 0
    assert l2.snapshot_id.startswith("l2_scholar_kg_causal_priors_transport:sha256:")
    assert l3.snapshot_id.startswith("l3_lex_kg_admissibility_obligations:sha256:")
