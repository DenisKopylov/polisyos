"""Runtime-oriented benchmark stage for the academic knowledge graph."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.academic.knowledge.runtime_canonical_registry import (
    RUNTIME_CANONICAL_REGISTRY_VERSION,
)
from polisyos.academic.knowledge.search import ScholarKnowledgeGraph
from polisyos.academic.knowledge.skg_query import SKGQuery
from polisyos.academic.knowledge.skg_store import EVIDENCE_WEIGHTS as _SKG_EVIDENCE_WEIGHTS
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.scientist.cross_graph.feedback import (
    AcademicBenchmarkScenario,
    AcademicBenchmarkSuite,
    BenchmarkCausalEdge,
    BenchmarkCredibilityPolicy,
    BenchmarkScholarQuery,
    load_benchmark_suite,
    write_need_backlog,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.academic.batch.config import AcademicBatchConfig

READINESS_THRESHOLDS: dict[str, float] = {
    "parameter_supported_ratio": 0.60,
    "parameter_quality_weighted_ratio": 0.40,
    "causal_supported_ratio": 0.50,
    "causal_supported_plus_mixed_ratio": 0.80,
    "scholar_query_coverage_ratio": 0.70,
    "non_default_transport_evidence_ratio": 0.60,
}


@dataclass(frozen=True)
class BenchmarkOutcome:
    """Readiness report emitted by the academic runtime benchmark stage."""

    report_path: Path
    metrics: dict[str, float | int]
    passed: bool
    failed_checks: tuple[str, ...]


def _default_suite() -> AcademicBenchmarkSuite:
    return AcademicBenchmarkSuite(
        suite_id="policyos_runtime_sota",
        scenarios=[
            AcademicBenchmarkScenario(
                scenario_id="fiscal_growth",
                title="Fiscal capacity and growth",
                policy_domain="fiscal",
                causal_edges=[
                    BenchmarkCausalEdge(cause="tax_revenue", effect="economic.gdp_growth")
                ],
                parameters=["tax_revenue"],
                scholar_queries=[
                    BenchmarkScholarQuery(cause="tax_revenue", effect="economic.gdp_growth")
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="public_investment_jobs",
                title="Public investment and employment",
                policy_domain="fiscal",
                causal_edges=[
                    BenchmarkCausalEdge(cause="public_investment", effect="labor.employment_rate")
                ],
                parameters=["public_investment"],
                scholar_queries=[
                    BenchmarkScholarQuery(cause="public_investment", effect="labor.employment_rate")
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="savings_gender_power",
                title="Savings and women's agency",
                policy_domain="social_policy",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="access_to_commitment_savings",
                        effect="governance.female_decision_making_power",
                    )
                ],
                parameters=["access_to_commitment_savings"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="access_to_commitment_savings",
                        effect="governance.female_decision_making_power",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="education_preferences",
                title="Early childhood education and social preferences",
                policy_domain="education",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="early_childhood_education",
                        effect="social.preferences",
                    )
                ],
                parameters=["early_childhood_education"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="early_childhood_education",
                        effect="social.preferences",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="health_prevention",
                title="Prevention campaigns and disease incidence",
                policy_domain="health",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="health.handwashing_campaign",
                        effect="health.diarrhea_incidence",
                    )
                ],
                parameters=["health.handwashing_campaign"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="health.handwashing_campaign",
                        effect="health.diarrhea_incidence",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="agriculture_productivity",
                title="Fertilizer systems and crop yields",
                policy_domain="agriculture",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="organic_mineral_fertilizer_system",
                        effect="winter_wheat_yield",
                    )
                ],
                parameters=["winter_wheat_yield"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="organic_mineral_fertilizer_system",
                        effect="winter_wheat_yield",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="climate_irrigation",
                title="Climate adaptation and crop resilience",
                policy_domain="climate",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="climate.drought_resilient_irrigation",
                        effect="agriculture.crop_yield",
                    )
                ],
                parameters=["agriculture.crop_yield"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="climate.drought_resilient_irrigation",
                        effect="agriculture.crop_yield",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="labor_growth_unemployment",
                title="Growth and labor markets",
                policy_domain="labor",
                credibility_policy=BenchmarkCredibilityPolicy(
                    min_confidence=0.65,
                    min_unique_works=2,
                    require_conflict_free=False,
                ),
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="economic.gdp_growth",
                        effect="unemployment_rate",
                    )
                ],
                parameters=["unemployment_rate"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="economic.gdp_growth",
                        effect="unemployment_rate",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="education_human_capital",
                title="Teacher coaching and learning outcomes",
                policy_domain="education",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="education.teacher_coaching",
                        effect="education.learning_outcomes",
                    )
                ],
                parameters=["education.learning_outcomes"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="education.teacher_coaching",
                        effect="education.learning_outcomes",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="energy_reliability",
                title="Energy reliability and firm productivity",
                policy_domain="energy",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="energy.electricity_reliability",
                        effect="economic.firm_productivity",
                    )
                ],
                parameters=["economic.firm_productivity"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="energy.electricity_reliability",
                        effect="economic.firm_productivity",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="urban_transit_access",
                title="Transit access and labor inclusion",
                policy_domain="urban",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="urban.mass_transit_access",
                        effect="labor.formal_employment",
                    )
                ],
                parameters=["labor.formal_employment"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="urban.mass_transit_access",
                        effect="labor.formal_employment",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="social_protection_consumption",
                title="Cash transfers and consumption smoothing",
                policy_domain="social_policy",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="social.cash_transfer_program",
                        effect="economic.household_consumption",
                    )
                ],
                parameters=["economic.household_consumption"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="social.cash_transfer_program",
                        effect="economic.household_consumption",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="governance_state_capacity",
                title="State capacity reforms and compliance",
                policy_domain="governance",
                credibility_policy=BenchmarkCredibilityPolicy(
                    min_confidence=0.6,
                    min_unique_works=1,
                    require_conflict_free=False,
                ),
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="governance.state_capacity_reform",
                        effect="governance.tax_compliance",
                    )
                ],
                parameters=["governance.tax_compliance"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="governance.state_capacity_reform",
                        effect="governance.tax_compliance",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="governance_rule_of_law",
                title="Rule of law and firm investment",
                policy_domain="governance",
                credibility_policy=BenchmarkCredibilityPolicy(
                    min_confidence=0.7,
                    min_unique_works=2,
                    max_evidence_age_years=15,
                ),
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="governance.rule_of_law",
                        effect="economic.firm_investment",
                    )
                ],
                parameters=["economic.firm_investment"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="governance.rule_of_law",
                        effect="economic.firm_investment",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="housing_security_wellbeing",
                title="Housing security and wellbeing",
                policy_domain="urban",
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="urban.housing_security",
                        effect="social.subjective_wellbeing",
                    )
                ],
                parameters=["social.subjective_wellbeing"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="urban.housing_security",
                        effect="social.subjective_wellbeing",
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="contested_minimum_wage",
                title="Minimum wage and employment under contested evidence",
                policy_domain="labor",
                credibility_policy=BenchmarkCredibilityPolicy(
                    min_confidence=0.6,
                    min_unique_works=2,
                    require_conflict_free=False,
                ),
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="labor.minimum_wage",
                        effect="labor.employment_rate",
                    )
                ],
                parameters=["labor.employment_rate"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="labor.minimum_wage",
                        effect="labor.employment_rate",
                        support_mode="contested_summary",
                        min_results=1,
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="transport_eu_to_ua",
                title="Transport-sensitive EU evidence for Ukraine",
                policy_domain="governance",
                credibility_policy=BenchmarkCredibilityPolicy(
                    min_confidence=0.65,
                    min_unique_works=1,
                    require_conflict_free=False,
                ),
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="governance.procurement_digitization",
                        effect="governance.procurement_compliance",
                    )
                ],
                parameters=["governance.procurement_compliance"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="governance.procurement_digitization",
                        effect="governance.procurement_compliance",
                        min_results=1,
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="digital_economy_effects",
                title="Digital infrastructure and productivity with recency gate",
                policy_domain="digital",
                credibility_policy=BenchmarkCredibilityPolicy(
                    min_confidence=0.7,
                    min_unique_works=2,
                    require_conflict_free=True,
                    max_evidence_age_years=10,
                ),
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="digital.infrastructure_quality",
                        effect="economic.firm_productivity",
                    )
                ],
                parameters=["economic.firm_productivity"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="digital.infrastructure_quality",
                        effect="economic.firm_productivity",
                        min_results=1,
                    )
                ],
            ),
            AcademicBenchmarkScenario(
                scenario_id="governance_anticorruption_sparse",
                title="Sparse anti-corruption evidence",
                policy_domain="governance",
                credibility_policy=BenchmarkCredibilityPolicy(
                    min_confidence=0.55,
                    min_unique_works=1,
                    require_conflict_free=False,
                ),
                causal_edges=[
                    BenchmarkCausalEdge(
                        cause="governance.anticorruption_enforcement",
                        effect="governance.procurement_integrity",
                    )
                ],
                parameters=["governance.procurement_integrity"],
                scholar_queries=[
                    BenchmarkScholarQuery(
                        cause="governance.anticorruption_enforcement",
                        effect="governance.procurement_integrity",
                        min_results=1,
                    )
                ],
            ),
        ],
    )


def _ensure_suite(path: Path) -> AcademicBenchmarkSuite:
    if path.exists():
        return load_benchmark_suite(path)
    suite = _default_suite()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(suite.model_dump(mode="json"), fh, ensure_ascii=False, indent=2)
    return suite


def _evaluate_readiness(metrics: dict[str, float | int]) -> tuple[bool, tuple[str, ...]]:
    failed: list[str] = []
    for key, threshold in READINESS_THRESHOLDS.items():
        value = float(metrics.get(key, 0.0))
        if value < threshold:
            failed.append(key)
    return (len(failed) == 0, tuple(failed))


def _best_design_tier_for_edge(query: SKGQuery, edge_id: str) -> int | None:
    """Return the best (lowest) design quality tier among evidence for *edge_id*."""
    try:
        result = query._con.execute(
            "SELECT MIN(design_quality_tier) FROM ac_skg_edge_evidence "
            "WHERE edge_id = ? AND design_quality_tier IS NOT NULL",
            [edge_id],
        ).fetchone()
        return int(result[0]) if result and result[0] is not None else None
    except Exception:
        return None


def _article_years_for_refs(query: SKGQuery, article_refs: tuple[str, ...]) -> list[int]:
    refs = [str(ref).strip() for ref in article_refs if str(ref).strip()]
    if not refs:
        return []
    placeholders = ", ".join("?" for _ in refs)
    try:
        rows = query._con.execute(
            f"SELECT year FROM ac_skg_articles WHERE openalex_id IN ({placeholders}) AND year IS NOT NULL",
            refs,
        ).fetchall()
    except Exception:
        return []
    return [int(row[0]) for row in rows if row and row[0] is not None]


def _matches_credibility_policy(
    row: Any,
    policy: BenchmarkCredibilityPolicy,
    *,
    query: SKGQuery,
    current_year: int,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if float(row.confidence) < float(policy.min_confidence):
        reasons.append("low_confidence")
    if int(row.n_unique_works) < int(policy.min_unique_works):
        reasons.append("insufficient_replication")
    if bool(policy.require_conflict_free) and bool(row.conflict_flag):
        reasons.append("conflict_flagged")
    if policy.max_evidence_age_years is not None:
        years = _article_years_for_refs(query, row.article_refs)
        if not years:
            reasons.append("missing_article_years")
        elif (current_year - max(years)) > int(policy.max_evidence_age_years):
            reasons.append("evidence_too_old")
    if policy.min_design_tier is not None:
        best_tier = _best_design_tier_for_edge(query, row.edge_id)
        if best_tier is not None and best_tier > int(policy.min_design_tier):
            reasons.append("design_tier_too_low")
    return (len(reasons) == 0, reasons)


def _best_edge_runtime_status(
    records: list[Any],
    policy: BenchmarkCredibilityPolicy,
    *,
    query: SKGQuery,
    current_year: int,
) -> tuple[str, list[dict[str, Any]]]:
    if not records:
        return "unsupported", []
    policy_checks: list[dict[str, Any]] = []
    credible: list[Any] = []
    maybe: list[Any] = []
    for row in records:
        passed, reasons = _matches_credibility_policy(
            row, policy, query=query, current_year=current_year
        )
        policy_checks.append(
            {
                "edge_id": row.edge_id,
                "passed": passed,
                "reasons": reasons,
                "confidence": float(row.confidence),
                "n_unique_works": int(row.n_unique_works),
                "conflict_flag": bool(row.conflict_flag),
            }
        )
        if passed:
            credible.append(row)
        elif float(row.confidence) >= 0.40 and int(row.n_unique_works) >= max(
            1, int(policy.min_unique_works) - 1
        ):
            maybe.append(row)
    if credible:
        return "supported", policy_checks
    return ("mixed" if maybe else "unsupported"), policy_checks


def _canonical_resolution_payload(
    query: SKGQuery,
    raw_name: str,
    *,
    need_type: str,
) -> dict[str, Any]:
    result = query.resolve_runtime_canonical(
        raw_name,
        need_type=need_type,
        runtime_priority=True,
    )
    return {
        "raw_name": str(raw_name),
        "canonical_name": result.canonical_name,
        "approved": bool(result.approved),
        "method": result.method,
        "confidence": round(float(result.confidence), 6),
        "review_required": bool(result.review_required),
    }


def _workflow_impacts_for_need(need_type: str) -> list[str]:
    if need_type == "parameter":
        return ["resolve_parameters", "cross_graph"]
    if need_type == "causal_edge":
        return ["literature_prior", "cross_graph", "scholar"]
    if need_type == "scholar_query":
        return ["scholar", "cross_graph"]
    return ["cross_graph"]


def _recommended_actions(
    *,
    canonical_missing: bool,
    status: str,
    demand_type: str,
    blocking_reasons: list[str],
) -> list[str]:
    actions: list[str] = []
    if canonical_missing:
        actions.extend(
            [
                "add_runtime_canonical_mapping",
                "add_runtime_synonym_seed",
            ]
        )
    if demand_type == "parameter":
        if status == "unsupported":
            actions.append("harvest_simulation_ready_parameter_evidence")
        if "simulation_ready_missing" in blocking_reasons or "no_uncertainty" in blocking_reasons:
            actions.append("improve_numeric_lane_uncertainty_capture")
    if demand_type == "causal_edge":
        if status == "unsupported":
            actions.append("harvest_literature_for_causal_pair")
        if "insufficient_replication" in blocking_reasons:
            actions.append("increase_family_edge_replication")
        if "conflict_flagged" in blocking_reasons:
            actions.append("inspect_contested_or_moderated_support")
    if demand_type == "scholar_query" and status != "supported":
        actions.append("improve_scholar_retrieval_coverage")
    if not actions:
        actions.append("review_runtime_demand_item")
    return list(dict.fromkeys(actions))


def _stratified_edge_analysis(
    query: SKGQuery,
    edge_ids: list[str],
    current_year: int,
) -> dict[str, Any]:
    """Compute stratified quality metrics for a set of edges."""
    tier_counts: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
    years: list[int] = []
    fulltext_count = 0
    abstract_count = 0

    for edge_id in edge_ids:
        try:
            rows = query._con.execute(
                "SELECT design_quality_tier FROM ac_skg_edge_evidence "
                "WHERE edge_id = ? AND design_quality_tier IS NOT NULL",
                [edge_id],
            ).fetchall()
            for row in rows:
                tier = int(row[0])
                if 1 <= tier <= 4:
                    tier_counts[tier] = tier_counts.get(tier, 0) + 1
        except Exception:
            pass

    for edge_id in edge_ids:
        try:
            rows = query._con.execute(
                "SELECT a.year, a.source_basis FROM ac_skg_edge_evidence ee "
                "JOIN ac_skg_articles a ON ee.openalex_id = a.openalex_id "
                "WHERE ee.edge_id = ?",
                [edge_id],
            ).fetchall()
            for row in rows:
                if row[0] is not None:
                    years.append(int(row[0]))
                basis = str(row[1] or "fulltext").lower()
                if basis == "abstract_only":
                    abstract_count += 1
                else:
                    fulltext_count += 1
        except Exception:
            pass

    sorted_years = sorted(years) if years else []
    total_sources = fulltext_count + abstract_count

    return {
        "design_tier_distribution": tier_counts,
        "median_evidence_year": sorted_years[len(sorted_years) // 2] if sorted_years else None,
        # sorted_years ascending: low index = old years = high age, high index = recent = low age
        # p25 of *age* = 25th percentile of (current_year - year) = current_year - year_at_75th_pct
        "evidence_age_p25": (
            current_year - sorted_years[min(len(sorted_years) - 1, int(len(sorted_years) * 0.75))]
        )
        if len(sorted_years) >= 4
        else None,
        "evidence_age_p75": (current_year - sorted_years[max(0, int(len(sorted_years) * 0.25))])
        if len(sorted_years) >= 4
        else None,
        "fulltext_share": round(fulltext_count / max(1, total_sources), 4),
        "total_evidence_sources": total_sources,
    }


def _quality_weighted_parameter_score(
    query: SKGQuery,
    param_name: str,
    *,
    current_year: int,
) -> float:
    """Compute quality-weighted score for a parameter (0.0-1.0)."""
    try:
        rows = query._con.execute(
            "SELECT point_estimate, evidence_strength, confidence_interval_json, "
            "std_error, source_layer FROM ac_skg_simulation_parameters "
            "WHERE canonical_name = ? AND source_layer IN ('simulation_ready', 'curated_numeric')",
            [param_name],
        ).fetchall()
    except Exception:
        return 0.0

    if not rows:
        return 0.0

    best_score = 0.0
    for row in rows:
        evidence_str = str(row[1] or "unknown")
        base = _SKG_EVIDENCE_WEIGHTS.get(evidence_str, 0.15)
        ci_json = row[2] or "[]"
        has_uncertainty = (ci_json not in ("[]", "null", "")) or (row[3] is not None)
        uncertainty_factor = 1.0 if has_uncertainty else 0.7
        score = base * uncertainty_factor
        if score > best_score:
            best_score = score
    return min(1.0, best_score)


def run_benchmark(config: AcademicBatchConfig) -> BenchmarkOutcome:
    """Run the SKG benchmark suite and persist readiness/backlog artifacts.

    The benchmark probes canonical-name resolution, causal-edge support, parameter availability,
    scholar-query coverage, and transport evidence quality, then writes a need backlog for missing
    runtime demands.
    """
    if not config.db_path.exists():
        raise FileNotFoundError(f"Academic knowledge graph not found: {config.db_path}")

    started_at = datetime.now(UTC).isoformat()
    suite = _ensure_suite(config.benchmark_suite_path)
    query = SKGQuery(db_path=config.db_path, index_dir=config.index_dir)
    graph = ScholarKnowledgeGraph(db_path=config.db_path, index_dir=config.index_dir)
    try:
        current_year = datetime.now(UTC).year
        scenario_payloads: list[dict[str, Any]] = []
        causal_total = 0
        causal_supported = 0
        causal_mixed = 0
        parameter_total = 0
        parameter_supported = 0
        parameter_mixed = 0
        scholar_total = 0
        scholar_supported = 0
        transport_total = 0
        transport_non_default = 0
        family_covered = 0
        contested_covered = 0
        runtime_demand_total = 0
        runtime_demand_hits = 0
        canonical_miss_total = 0
        parameter_quality_scores: list[float] = []
        all_edge_ids: list[str] = []
        runtime_demand_backlog: list[dict[str, Any]] = []

        for scenario in suite.scenarios:
            edge_rows: list[dict[str, Any]] = []
            for edge in scenario.causal_edges:
                causal_total += 1
                cause_resolution = _canonical_resolution_payload(
                    query, edge.cause, need_type="causal_edge"
                )
                effect_resolution = _canonical_resolution_payload(
                    query, edge.effect, need_type="causal_edge"
                )
                runtime_demand_total += 2
                runtime_demand_hits += int(bool(cause_resolution["approved"])) + int(
                    bool(effect_resolution["approved"])
                )
                canonical_missing = not bool(cause_resolution["approved"]) or not bool(
                    effect_resolution["approved"]
                )
                if canonical_missing:
                    canonical_miss_total += int(not bool(cause_resolution["approved"])) + int(
                        not bool(effect_resolution["approved"])
                    )
                supports = query.query_edge_support(
                    cause=edge.cause,
                    effect=edge.effect,
                    min_confidence=0.25,
                    support_mode="hybrid",
                    limit=8,
                )
                family_supports = query.query_edge_support(
                    cause=edge.cause,
                    effect=edge.effect,
                    min_confidence=0.25,
                    support_mode="family",
                    limit=8,
                )
                contested_supports = query.query_edge_support(
                    cause=edge.cause,
                    effect=edge.effect,
                    min_confidence=0.25,
                    support_mode="contested",
                    limit=8,
                )
                status, policy_checks = _best_edge_runtime_status(
                    supports,
                    scenario.credibility_policy,
                    query=query,
                    current_year=current_year,
                )
                if status == "supported":
                    causal_supported += 1
                elif status == "mixed":
                    causal_mixed += 1
                if family_supports:
                    family_covered += 1
                if contested_supports:
                    contested_covered += 1
                transport_records = query.query_edge_transport(
                    [row.edge_id for row in supports],
                    target_context_id=config.transport_target_context_id or "UA",
                )
                all_edge_ids.extend(row.edge_id for row in supports)
                transport_total += 1
                if any(
                    (
                        record.matched_moderators_count > 0
                        or bool(record.match_mode)
                        or float(record.context_match_reward) > 0.0
                        or float(record.generic_penalty) > 0.0
                    )
                    for record in transport_records
                ):
                    transport_non_default += 1
                edge_rows.append(
                    {
                        "cause": edge.cause,
                        "effect": edge.effect,
                        "canonical_resolution": {
                            "cause": cause_resolution,
                            "effect": effect_resolution,
                        },
                        "status": status,
                        "credibility_policy": scenario.credibility_policy.model_dump(mode="json"),
                        "policy_checks": policy_checks,
                        "matches": [
                            {
                                "edge_id": row.edge_id,
                                "source_layer": row.source_layer,
                                "confidence": row.confidence,
                                "n_unique_works": row.n_unique_works,
                                "n_claims": row.n_claims,
                                "conflict_flag": row.conflict_flag,
                                "resolution_status": row.resolution_status,
                                "dominant_direction_agreement": row.dominant_direction_agreement,
                                "positive_weight": row.positive_weight,
                                "negative_weight": row.negative_weight,
                                "mixed_weight": row.mixed_weight,
                            }
                            for row in supports
                        ],
                        "family_matches": [
                            {
                                "edge_id": row.edge_id,
                                "confidence": row.confidence,
                                "n_unique_works": row.n_unique_works,
                                "n_claims": row.n_claims,
                            }
                            for row in family_supports
                        ],
                        "contested_matches": [
                            {
                                "edge_id": row.edge_id,
                                "confidence": row.confidence,
                                "n_unique_works": row.n_unique_works,
                                "n_claims": row.n_claims,
                                "quality_flags": list(row.quality_flags),
                            }
                            for row in contested_supports
                        ],
                        "transport": [
                            {
                                "edge_id": record.edge_id,
                                "transport_confidence": record.transport_confidence,
                                "match_mode": record.match_mode,
                                "matched_moderators_count": record.matched_moderators_count,
                                "generic_penalty": record.generic_penalty,
                                "context_match_reward": record.context_match_reward,
                            }
                            for record in transport_records
                        ],
                    }
                )
                if status != "supported" or canonical_missing:
                    reasons = sorted(
                        {
                            reason
                            for check in policy_checks
                            for reason in list(check.get("reasons") or [])
                        }
                    )
                    if canonical_missing:
                        reasons.append("canonical_gap")
                    runtime_demand_backlog.append(
                        {
                            "need_id": f"{scenario.scenario_id}:edge:{edge.cause}->{edge.effect}",
                            "need_type": "causal_edge",
                            "priority_weight": round(
                                float(scenario.weight) * (1.25 if status == "unsupported" else 1.0),
                                4,
                            ),
                            "terms": [edge.cause, edge.effect],
                            "cause": edge.cause,
                            "effect": edge.effect,
                            "parameter_name": None,
                            "scenario_id": scenario.scenario_id,
                            "policy_domain": scenario.policy_domain,
                            "blocking_reasons": reasons,
                            "recommended_actions": _recommended_actions(
                                canonical_missing=canonical_missing,
                                status=status,
                                demand_type="causal_edge",
                                blocking_reasons=reasons,
                            ),
                            "labels": [scenario.policy_domain, scenario.scenario_id],
                            "evidence_status": status,
                            "transport_status": "non_default" if transport_records else "unknown",
                            "confidence": max(
                                (float(row.confidence) for row in supports), default=0.0
                            ),
                            "workflow_impacts": _workflow_impacts_for_need("causal_edge"),
                        }
                    )

            parameter_rows: list[dict[str, Any]] = []
            for parameter_name in scenario.parameters:
                parameter_total += 1
                parameter_resolution = _canonical_resolution_payload(
                    query, parameter_name, need_type="parameter"
                )
                runtime_demand_total += 1
                runtime_demand_hits += int(bool(parameter_resolution["approved"]))
                canonical_missing = not bool(parameter_resolution["approved"])
                if canonical_missing:
                    canonical_miss_total += 1
                candidates = query.query_parameters(
                    parameter_name,
                    layer="auto",
                    require_simulation_ready=True,
                    limit=12,
                )
                sim_candidates = [
                    row
                    for row in candidates
                    if row.source_layer in {"simulation_ready", "simulation"}
                    and not row.requires_expert_review
                ]
                quality_score = _quality_weighted_parameter_score(
                    query,
                    parameter_name,
                    current_year=current_year,
                )
                parameter_quality_scores.append(quality_score)
                if sim_candidates:
                    parameter_supported += 1
                    status = "supported"
                elif candidates:
                    parameter_mixed += 1
                    status = "mixed"
                else:
                    status = "unsupported"
                parameter_rows.append(
                    {
                        "parameter_name": parameter_name,
                        "canonical_resolution": parameter_resolution,
                        "status": status,
                        "candidates": [
                            {
                                "source_layer": row.source_layer,
                                "requires_expert_review": row.requires_expert_review,
                                "quality_flags": list(row.quality_flags),
                                "linked_claim_ids": list(row.linked_claim_ids),
                                "linked_edge_ids": list(row.linked_edge_ids),
                                "uncertainty_source": row.uncertainty_source,
                            }
                            for row in candidates
                        ],
                    }
                )
                if status != "supported" or canonical_missing:
                    candidate_reasons = sorted(
                        {flag for row in candidates for flag in row.quality_flags}
                    )
                    if not candidates:
                        candidate_reasons.append("no_parameter_candidates")
                    if canonical_missing:
                        candidate_reasons.append("canonical_gap")
                    runtime_demand_backlog.append(
                        {
                            "need_id": f"{scenario.scenario_id}:parameter:{parameter_name}",
                            "need_type": "parameter",
                            "priority_weight": round(
                                float(scenario.weight) * (1.25 if status == "unsupported" else 1.0),
                                4,
                            ),
                            "terms": [parameter_name],
                            "cause": None,
                            "effect": None,
                            "parameter_name": parameter_name,
                            "scenario_id": scenario.scenario_id,
                            "policy_domain": scenario.policy_domain,
                            "blocking_reasons": candidate_reasons,
                            "recommended_actions": _recommended_actions(
                                canonical_missing=canonical_missing,
                                status=status,
                                demand_type="parameter",
                                blocking_reasons=candidate_reasons,
                            ),
                            "labels": [scenario.policy_domain, scenario.scenario_id],
                            "evidence_status": status,
                            "transport_status": "unknown",
                            "confidence": 1.0 if sim_candidates else (0.5 if candidates else 0.0),
                            "workflow_impacts": _workflow_impacts_for_need("parameter"),
                        }
                    )

            scholar_rows: list[dict[str, Any]] = []
            for scholar_query in scenario.scholar_queries:
                scholar_total += 1
                cause_resolution = _canonical_resolution_payload(
                    query, scholar_query.cause, need_type="scholar_query"
                )
                effect_resolution = _canonical_resolution_payload(
                    query, scholar_query.effect, need_type="scholar_query"
                )
                runtime_demand_total += 2
                runtime_demand_hits += int(bool(cause_resolution["approved"])) + int(
                    bool(effect_resolution["approved"])
                )
                canonical_missing = not bool(cause_resolution["approved"]) or not bool(
                    effect_resolution["approved"]
                )
                if canonical_missing:
                    canonical_miss_total += int(not bool(cause_resolution["approved"])) + int(
                        not bool(effect_resolution["approved"])
                    )
                rows = graph.find_causal_evidence(
                    scholar_query.cause,
                    scholar_query.effect,
                    min_trust=scholar_query.min_trust,
                    support_mode=scholar_query.support_mode,
                )
                supported = len(rows) >= int(scholar_query.min_results)
                if supported:
                    scholar_supported += 1
                scholar_rows.append(
                    {
                        "cause": scholar_query.cause,
                        "effect": scholar_query.effect,
                        "canonical_resolution": {
                            "cause": cause_resolution,
                            "effect": effect_resolution,
                        },
                        "support_mode": scholar_query.support_mode,
                        "results": len(rows),
                        "supported": supported,
                    }
                )
                if not supported or canonical_missing:
                    reasons = []
                    if not supported:
                        reasons.append("scholar_coverage_gap")
                    if canonical_missing:
                        reasons.append("canonical_gap")
                    runtime_demand_backlog.append(
                        {
                            "need_id": f"{scenario.scenario_id}:scholar:{scholar_query.cause}->{scholar_query.effect}",
                            "need_type": "scholar_query",
                            "priority_weight": round(float(scenario.weight), 4),
                            "terms": [scholar_query.cause, scholar_query.effect],
                            "cause": scholar_query.cause,
                            "effect": scholar_query.effect,
                            "parameter_name": None,
                            "scenario_id": scenario.scenario_id,
                            "policy_domain": scenario.policy_domain,
                            "blocking_reasons": reasons,
                            "recommended_actions": _recommended_actions(
                                canonical_missing=canonical_missing,
                                status=("supported" if supported else "unsupported"),
                                demand_type="scholar_query",
                                blocking_reasons=reasons,
                            ),
                            "labels": [scenario.policy_domain, scenario.scenario_id],
                            "evidence_status": "supported" if supported else "unsupported",
                            "transport_status": "unknown",
                            "confidence": float(len(rows)),
                            "workflow_impacts": _workflow_impacts_for_need("scholar_query"),
                        }
                    )

            scenario_payloads.append(
                {
                    "scenario_id": scenario.scenario_id,
                    "title": scenario.title,
                    "policy_domain": scenario.policy_domain,
                    "causal_edges": edge_rows,
                    "parameters": parameter_rows,
                    "scholar_queries": scholar_rows,
                }
            )

        # Compute stratified analysis while query is still open
        stratified = _stratified_edge_analysis(query, all_edge_ids, current_year)
    finally:
        graph.close()
        query.close()

    metrics: dict[str, float | int] = {
        "scenarios": len(suite.scenarios),
        "causal_needs_total": causal_total,
        "causal_needs_supported": causal_supported,
        "causal_needs_mixed": causal_mixed,
        "parameter_needs_total": parameter_total,
        "parameter_needs_supported": parameter_supported,
        "parameter_needs_mixed": parameter_mixed,
        "scholar_queries_total": scholar_total,
        "scholar_queries_supported": scholar_supported,
        "transport_edges_total": transport_total,
        "transport_edges_non_default": transport_non_default,
        "family_edge_coverage_total": causal_total,
        "family_edge_coverage_hits": family_covered,
        "contested_edge_coverage_total": causal_total,
        "contested_edge_coverage_hits": contested_covered,
        "causal_supported_ratio": round(causal_supported / max(1, causal_total), 4),
        "causal_mixed_ratio": round(causal_mixed / max(1, causal_total), 4),
        "causal_supported_plus_mixed_ratio": round(
            (causal_supported + causal_mixed) / max(1, causal_total), 4
        ),
        "parameter_supported_ratio": round(parameter_supported / max(1, parameter_total), 4),
        "parameter_mixed_ratio": round(parameter_mixed / max(1, parameter_total), 4),
        "scholar_query_coverage_ratio": round(scholar_supported / max(1, scholar_total), 4),
        "non_default_transport_evidence_ratio": round(
            transport_non_default / max(1, transport_total), 4
        ),
        "family_edge_coverage_ratio": round(family_covered / max(1, causal_total), 4),
        "contested_edge_coverage_ratio": round(contested_covered / max(1, causal_total), 4),
        "simulation_ready_parameter_ratio": round(parameter_supported / max(1, parameter_total), 4),
        "runtime_demand_total": runtime_demand_total,
        "runtime_demanded_canonical_hits": runtime_demand_hits,
        "runtime_demanded_canonical_resolution_rate_pct": round(
            (runtime_demand_hits / max(1, runtime_demand_total)) * 100.0,
            3,
        ),
        "canonical_miss_total": canonical_miss_total,
        "parameter_quality_weighted_ratio": round(
            sum(parameter_quality_scores) / max(1, len(parameter_quality_scores)),
            4,
        ),
    }
    passed, failed_checks = _evaluate_readiness(metrics)
    runtime_demand_backlog.sort(
        key=lambda item: (
            -float(item.get("priority_weight") or 0.0),
            str(item.get("need_type") or ""),
            str(item.get("need_id") or ""),
        )
    )
    write_need_backlog(config.runtime_demand_backlog_path, runtime_demand_backlog)
    report = {
        "kind": "academic_benchmark",
        "generated_at": datetime.now(UTC).isoformat(),
        "snapshot_root": str(config.snapshot_root),
        "component_dir": str(config.component_dir),
        "runtime_canonical_registry_version": RUNTIME_CANONICAL_REGISTRY_VERSION,
        "thresholds": READINESS_THRESHOLDS,
        "suite": suite.model_dump(mode="json"),
        "metrics": metrics,
        "readiness": {
            "passed": passed,
            "failed_checks": list(failed_checks),
        },
        "runtime_demand_backlog": {
            "path": str(config.runtime_demand_backlog_path),
            "items": len(runtime_demand_backlog),
        },
        "scenarios": scenario_payloads,
        "stratified": stratified,
    }
    config.benchmark_report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    write_stage_manifest(
        manifest_path=config.manifests_dir / "benchmark.json",
        stage="benchmark",
        status="ok" if passed else "failed",
        metrics={**metrics, "readiness_passed": int(passed)},
        artifacts=[
            config.benchmark_suite_path,
            config.benchmark_report_path,
            config.runtime_demand_backlog_path,
        ],
        started_at=started_at,
    )
    return BenchmarkOutcome(
        report_path=config.benchmark_report_path,
        metrics=metrics,
        passed=passed,
        failed_checks=failed_checks,
    )


__all__ = ["READINESS_THRESHOLDS", "BenchmarkOutcome", "run_benchmark"]
