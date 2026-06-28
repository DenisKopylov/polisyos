#!/usr/bin/env python3
"""Validate the Layer 3 GY L2/L3 knowledge-substrate lift contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/layer3_gy_knowledge_substrate_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.knowledge_substrate_contract.v1"

L2_ESTIMATE_ID = "179aff173ec40e640b535514"
L2_EDGE_ID = "06fb46cd681818bc52d1cc01"
L2_ALIAS_CAUSE = "agriculture.organic_fertilizer_system"
L2_ALIAS_EFFECT = "agriculture.crop_yield"
L2_CONTESTED_EDGE_ID = "aa4d86b83f216207989339f6"
L3_THRESHOLD_ID = "a5429abb6621acb11ed10b20"
L3_AMENDMENT_ID = "17bd5016053d883db190603c"
L3_YEAR_GTE_THRESHOLD_ID = "0017d256e4c232f4e4831c6e"
L3_DAY_LTE_THRESHOLD_ID = "72d0367ea085795e811da112"
L3_MONTH_EQ_THRESHOLD_ID = "7bb54afa703ce2cc1ac8b22b"
L3_CURRENCY_EQ_THRESHOLD_ID = "019cab2db39f0f14b0051ed5"
L3_LINEAGE_DOC_FAMILY_ID = "05640c577d76bebf85"
L3_LINEAGE_METRIC = "днів"
L3_LINEAGE_OLD_THRESHOLD_ID = "2a516f4ad0a279af6cbc19cd"
L3_SUPERSEDED_THRESHOLD_ID = "9d73aecb2a07e040897f34bf"
L3_SUPERSEDED_AMENDMENT_ID = "bc9fb973e424dc841aa7487b"


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def knowledge_substrate_behavior_report(repo_root: Path) -> dict[str, Any]:
    """Exercise the live L2/L3 lift behavior against real DuckDB stores."""

    from polisyos.data_forge.domains.academic.knowledge.skg_query import SKGQuery
    from polisyos.lex.knowledge.store import LegalKnowledgeStore
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateLayer,
        build_substrate_registry_from_existing_catalogs,
    )

    l2_db = _l2_db_path(repo_root)
    l3_db = _l3_db_path(repo_root)
    skg = SKGQuery(l2_db, l2_db.parent)
    lex = LegalKnowledgeStore(l3_db, l3_db.parent)
    issues: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []

    def _record(
        *,
        case_id: str,
        passed: bool,
        expected: str,
        actual: str,
        detail: dict[str, Any],
    ) -> None:
        case = {
            "case_id": case_id,
            "expected": expected,
            "actual": actual,
            "detail": detail,
        }
        cases.append(case)
        if not passed:
            issues.append({"code": "knowledge_substrate_behavior_failed", **case})

    estimate = skg.parameter_estimate_value_outer_set(
        estimate_id=L2_ESTIMATE_ID,
        world_model_record_ref="repo://architecture/policy_design_case/layer3_gy_world_model_record_contract.json",
        epoch="skg:1",
    )
    weak_estimate = skg.parameter_estimate_value_outer_set(
        estimate_id=L2_ESTIMATE_ID,
        world_model_record_ref=estimate.world_model_record_ref,
        epoch=estimate.epoch,
        trust_score_override=0.12,
    )
    estimate_ok = (
        estimate.representation == "interval_box"
        and estimate.width[0] > 0.0
        and estimate.identification_status != "point"
        and estimate.data_trust.effective_score > weak_estimate.data_trust.effective_score
        and estimate.promotion_decision().capped_decision_grade
        != weak_estimate.promotion_decision().capped_decision_grade
    )
    _record(
        case_id="l2_estimate_ci_lowers_to_value_outer_set",
        passed=estimate_ok,
        expected="interval_nonpoint_with_numeric_trust_gradient",
        actual=(
            "interval_nonpoint_with_numeric_trust_gradient"
            if estimate_ok
            else "presence_or_point_laundered"
        ),
        detail={
            "estimate_id": L2_ESTIMATE_ID,
            "width": list(estimate.width),
            "identification_status": estimate.identification_status,
            "data_trust": estimate.data_trust.model_dump(mode="json"),
            "promotion_grade": estimate.promotion_decision().capped_decision_grade,
            "weak_promotion_grade": weak_estimate.promotion_decision().capped_decision_grade,
        },
    )

    transported = skg.transport_value_outer_set(
        estimate,
        edge_id=L2_EDGE_ID,
        target_context_id="UA",
    )
    transport_ok = (
        transported.width[0] > estimate.width[0]
        and transported.identification_status in {"partial", "proxy"}
        and transported.calibration_scope.get("lowering_status") == "transported_limited"
    )
    _record(
        case_id="l2_transport_score_widens_value_outer_set",
        passed=transport_ok,
        expected="transported_limited_wider_than_source",
        actual="transported_limited_wider_than_source" if transport_ok else "transport_not_widened",
        detail={
            "edge_id": L2_EDGE_ID,
            "source_width": list(estimate.width),
            "transported_width": list(transported.width),
            "transport_confidence": transported.calibration_scope.get("transport_confidence"),
            "widening_multiplier": transported.calibration_scope.get("widening_multiplier"),
        },
    )

    untransported = skg.transport_value_outer_set(
        estimate,
        edge_id=L2_EDGE_ID,
        target_context_id="ZZ_WRONG_SCOPE",
    )
    untransported_ok = (
        untransported.representation_status == "search_only"
        and untransported.calibration_scope.get("transport_reason")
        == "transport_unavailable_for_scope"
        and not untransported.promotion_decision().promotable
    )
    _record(
        case_id="l2_missing_transport_is_search_only_not_promotable",
        passed=untransported_ok,
        expected="untransported_search_only_non_promotable",
        actual=(
            "untransported_search_only_non_promotable"
            if untransported_ok
            else "missing_transport_laundered"
        ),
        detail={
            "edge_id": L2_EDGE_ID,
            "target_context_id": "ZZ_WRONG_SCOPE",
            "representation_status": untransported.representation_status,
            "identification_status": untransported.identification_status,
            "promotion": untransported.promotion_decision().model_dump(mode="json"),
            "calibration_scope": untransported.calibration_scope,
        },
    )

    contested = skg.contested_edge_value_outer_set(
        contested_edge_id=L2_CONTESTED_EDGE_ID,
        world_model_record_ref=estimate.world_model_record_ref,
        epoch=estimate.epoch,
    )
    contested_ok = (
        contested.lower[0] < 0.0 < contested.upper[0]
        and contested.width[0] > 0.0
        and contested.identification_status == "proxy"
        and contested.calibration_scope.get("lowering_status")
        == "structural_ambiguity_estimate_envelope"
        and int(contested.calibration_scope.get("resolved_claim_count", "0")) >= 3
        and int(contested.calibration_scope.get("estimate_count", "0")) >= 2
    )
    _record(
        case_id="l2_contested_edge_spans_structural_ambiguity",
        passed=contested_ok,
        expected="claim_ref_estimate_envelope_wide_signed_proxy_set",
        actual=(
            "claim_ref_estimate_envelope_wide_signed_proxy_set"
            if contested_ok
            else "aggregate_weight_or_silent_pick"
        ),
        detail={
            "contested_edge_id": L2_CONTESTED_EDGE_ID,
            "lower": list(contested.lower),
            "upper": list(contested.upper),
            "width": list(contested.width),
            "identification_status": contested.identification_status,
            "calibration_scope": contested.calibration_scope,
        },
    )

    matched = skg.resolve_grounded_causal_prior(
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        estimand="directional_effect",
        scope_context_id="UA",
        required_skg_version_id=1,
    )
    unrelated = skg.resolve_grounded_causal_prior(
        cause="astronomy.star_brightness",
        effect="agriculture.food_nutritional_quality",
        estimand="directional_effect",
        scope_context_id="UA",
        required_skg_version_id=1,
    )
    wrong_scope = skg.resolve_grounded_causal_prior(
        cause="agriculture.fertilizer_use",
        effect="agriculture.food_nutritional_quality",
        estimand="directional_effect",
        scope_context_id="ZZ_WRONG_SCOPE",
        required_skg_version_id=1,
    )
    alias_match = skg.resolve_grounded_causal_prior(
        cause=L2_ALIAS_CAUSE,
        effect=L2_ALIAS_EFFECT,
        estimand="directional_effect",
        scope_context_id="UA",
        required_skg_version_id=1,
    )
    grounding_ok = (
        matched.status == "bound"
        and matched.edge_id == L2_EDGE_ID
        and matched.relevance_score > 0.0
        and unrelated.status == "blocked"
        and wrong_scope.status == "search_only"
        and wrong_scope.transport_ref is None
        and "transport_unavailable_for_scope" in wrong_scope.blockers
        and alias_match.status == "bound"
        and alias_match.transport_ref is not None
        and unrelated.relevance_score < matched.relevance_score
    )
    _record(
        case_id="l2_skg_grounding_resolve_content_bind_validate_fail_closed",
        passed=grounding_ok,
        expected="true_and_alias_bound_wrong_cause_blocked_wrong_scope_search_only",
        actual=(
            "true_and_alias_bound_wrong_cause_blocked_wrong_scope_search_only"
            if grounding_ok
            else "presence_only_constant_or_scope_laundered"
        ),
        detail={
            "matched": matched.__dict__,
            "unrelated": unrelated.__dict__,
            "wrong_scope": wrong_scope.__dict__,
            "alias_match": alias_match.__dict__,
        },
    )

    threshold_admit = lex.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=24.0,
        candidate_unit="percent",
        applies_to="25 percent",
    )
    threshold_ratio = lex.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=0.24,
        candidate_unit="ratio",
        applies_to="25 percent",
    )
    threshold_block = lex.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=26.0,
        candidate_unit="percent",
        applies_to="25 percent",
    )
    threshold_missing = lex.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=None,
        candidate_unit="percent",
        applies_to="25 percent",
    )
    threshold_outside = lex.evaluate_rule_threshold(
        threshold_id=L3_THRESHOLD_ID,
        candidate_value=24.0,
        candidate_unit="percent",
        applies_to="completely different scope",
    )
    year_admit = lex.evaluate_rule_threshold(
        threshold_id=L3_YEAR_GTE_THRESHOLD_ID,
        candidate_value=22.0,
        candidate_unit="year",
        applies_to="неодружені діти віком до 21 року",
    )
    year_block = lex.evaluate_rule_threshold(
        threshold_id=L3_YEAR_GTE_THRESHOLD_ID,
        candidate_value=20.0,
        candidate_unit="year",
        applies_to="неодружені діти віком до 21 року",
    )
    day_admit = lex.evaluate_rule_threshold(
        threshold_id=L3_DAY_LTE_THRESHOLD_ID,
        candidate_value=179.0,
        candidate_unit="днів",
        applies_to="строк продовження не більше 180 днів",
    )
    day_block = lex.evaluate_rule_threshold(
        threshold_id=L3_DAY_LTE_THRESHOLD_ID,
        candidate_value=181.0,
        candidate_unit="днів",
        applies_to="строк продовження не більше 180 днів",
    )
    month_admit = lex.evaluate_rule_threshold(
        threshold_id=L3_MONTH_EQ_THRESHOLD_ID,
        candidate_value=30.0,
        candidate_unit="місяців",
        applies_to="заморожену яловичину",
    )
    currency_admit = lex.evaluate_rule_threshold(
        threshold_id=L3_CURRENCY_EQ_THRESHOLD_ID,
        candidate_value=8800.0,
        candidate_unit="грн",
        applies_to="максимальна інтервенційна ціна (з урахуванням податку на додану вартість) на цукор-пісок (буряковий)",
    )
    incompatible = lex.evaluate_rule_threshold(
        threshold_id=L3_DAY_LTE_THRESHOLD_ID,
        candidate_value=179.0,
        candidate_unit="грн",
        applies_to="строк продовження не більше 180 днів",
    )
    operator_range_ok = lex._operator_registry()["range"](15.0, (10.0, 20.0))
    operator_membership_ok = lex._operator_registry()["in"](15.0, (10.0, 15.0, 20.0))
    threshold_ok = (
        threshold_admit.status == "admitted"
        and threshold_ratio.status == "admitted"
        and threshold_ratio.normalized_candidate_value == 24.0
        and threshold_block.status == "blocked"
        and threshold_block.reason == "threshold_violated"
        and threshold_missing.status == "blocked"
        and threshold_missing.reason == "candidate_bound_missing"
        and threshold_outside.status == "not_applicable"
        and threshold_outside.reason == "threshold_not_applicable"
        and year_admit.status == "admitted"
        and year_block.status == "blocked"
        and day_admit.status == "admitted"
        and day_block.status == "blocked"
        and month_admit.status == "admitted"
        and currency_admit.status == "admitted"
        and incompatible.status == "blocked"
        and incompatible.reason == "unit_incompatible"
        and operator_range_ok
        and operator_membership_ok
    )
    _record(
        case_id="l3_rule_threshold_operator_unit_missing_bound_gate",
        passed=threshold_ok,
        expected="multi_unit_operator_scope_missing_bound_semantics",
        actual=(
            "multi_unit_operator_scope_missing_bound_semantics"
            if threshold_ok
            else "presence_unit_or_none_zero_laundered"
        ),
        detail={
            "admit": threshold_admit.model_dump(mode="json"),
            "ratio": threshold_ratio.model_dump(mode="json"),
            "block": threshold_block.model_dump(mode="json"),
            "missing": threshold_missing.model_dump(mode="json"),
            "outside": threshold_outside.model_dump(mode="json"),
            "year_admit": year_admit.model_dump(mode="json"),
            "year_block": year_block.model_dump(mode="json"),
            "day_admit": day_admit.model_dump(mode="json"),
            "day_block": day_block.model_dump(mode="json"),
            "month_admit": month_admit.model_dump(mode="json"),
            "currency_admit": currency_admit.model_dump(mode="json"),
            "incompatible": incompatible.model_dump(mode="json"),
            "operator_registry": {
                "present_operators": sorted(lex._operator_registry()),
                "range_probe": operator_range_ok,
                "membership_probe": operator_membership_ok,
            },
        },
    )

    before = lex.resolve_amendment_temporal_competence(
        amendment_id=L3_AMENDMENT_ID,
        as_of="2016-12-31",
    )
    after = lex.resolve_amendment_temporal_competence(
        amendment_id=L3_AMENDMENT_ID,
        as_of="2017-01-02",
    )
    lineage_old_mid = lex.resolve_threshold_temporal_competence(
        threshold_id=L3_LINEAGE_OLD_THRESHOLD_ID,
        as_of="2000-01-01",
    )
    lineage_mid_threshold = lex.resolve_rule_threshold(
        metric=L3_LINEAGE_METRIC,
        doc_family_id=L3_LINEAGE_DOC_FAMILY_ID,
        as_of="2021-12-01",
    )
    lineage_mid_status = (
        None
        if lineage_mid_threshold is None
        else lex.resolve_threshold_temporal_competence(
            threshold_id=lineage_mid_threshold.threshold_id,
            as_of="2021-12-01",
        )
    )
    superseded_threshold = lex.resolve_threshold_temporal_competence(
        threshold_id=L3_SUPERSEDED_THRESHOLD_ID,
        as_of="2036-12-31",
    )
    superseded_amendment = lex.resolve_amendment_temporal_competence(
        amendment_id=L3_SUPERSEDED_AMENDMENT_ID,
        as_of="2036-12-31",
    )
    temporal_ok = (
        before.status == "not_yet_in_force"
        and after.status == "in_force"
        and before.effective_from == after.effective_from == "2017-01-01"
        and lineage_old_mid.status == "in_force"
        and lineage_mid_threshold is not None
        and lineage_mid_threshold.doc_family_id == L3_LINEAGE_DOC_FAMILY_ID
        and lineage_mid_status is not None
        and lineage_mid_status.status == "in_force"
        and superseded_threshold.status == "stale"
        and superseded_amendment.status == "stale"
    )
    _record(
        case_id="l3_amendment_effective_from_temporal_gate",
        passed=temporal_ok,
        expected="effective_from_and_lineage_supersession",
        actual="effective_from_and_lineage_supersession" if temporal_ok else "latest_or_one_row_only",
        detail={
            "before": before.model_dump(mode="json"),
            "after": after.model_dump(mode="json"),
            "lineage_old_mid": lineage_old_mid.model_dump(mode="json"),
            "lineage_mid_threshold": (
                None if lineage_mid_threshold is None else lineage_mid_threshold.model_dump(mode="json")
            ),
            "lineage_mid_status": (
                None if lineage_mid_status is None else lineage_mid_status.model_dump(mode="json")
            ),
            "superseded_threshold": superseded_threshold.model_dump(mode="json"),
            "superseded_amendment": superseded_amendment.model_dump(mode="json"),
        },
    )

    registry = build_substrate_registry_from_existing_catalogs(repo_root)
    l2_entry = registry.resolve(
        source_id="l2_scholar_kg:scholar_knowledge.duckdb",
        family_id="l2_scholar_kg_causal_priors_transport",
        layer=SubstrateLayer.L2,
    )[0]
    l3_entry = registry.resolve(
        source_id="l3_lex_kg:lex_knowledge_graph.duckdb",
        family_id="l3_lex_kg_admissibility_obligations",
        layer=SubstrateLayer.L3,
    )[0]
    s0_ok = (
        l2_entry.coverage.coverage_dimensions["table_counts"]["ac_parameter_estimates"] > 0
        and l2_entry.coverage.coverage_dimensions["table_counts"]["ac_skg_transport_scores"] > 0
        and l3_entry.coverage.coverage_dimensions["table_counts"]["lex_rule_thresholds"] > 0
        and l3_entry.coverage.coverage_dimensions["table_counts"]["lex_amendments"] > 0
    )
    _record(
        case_id="s0_registers_l2_l3_real_knowledge_substrates",
        passed=s0_ok,
        expected="l2_l3_registered_with_live_counts",
        actual="l2_l3_registered_with_live_counts" if s0_ok else "substrate_surface_missing",
        detail={
            "l2": l2_entry.model_dump(mode="json"),
            "l3": l3_entry.model_dump(mode="json"),
        },
    )

    return {
        "status": "pass" if not issues else "fail",
        "case_count": len(cases),
        "cases": cases,
        "issues": issues,
    }


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the L2/L3 knowledge substrate lift contract from live code/data."""

    from polisyos.core.contracts import ValueOuterSet
    from polisyos.lex.knowledge.types import (
        LegalRuleThresholdRow,
        LegalTemporalCompetence,
        LegalThresholdEvaluation,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    behavior = knowledge_substrate_behavior_report(repo_root)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.knowledge_substrate_lift",
        "owner": "polisyos.data_forge.domains.academic.knowledge.skg_query + polisyos.lex.knowledge.store",
        "source_modules": [
            "src/polisyos/data_forge/domains/academic/knowledge/skg_query.py",
            "src/polisyos/lex/knowledge/store.py",
            "src/polisyos/lex/knowledge/types.py",
            "src/polisyos/runtime/quality/substrate_registry.py",
        ],
        "real_substrates": {
            "l2": _repo_relative(_l2_db_path(repo_root), repo_root),
            "l3": _repo_relative(_l3_db_path(repo_root), repo_root),
        },
        "reuse_existing_owners": [
            "SKGQuery.has_skg_version_id",
            "SKGQuery.skg_snapshot_ref",
            "WorldModelRecord.skg_causal_prior_ref",
            "LegalKnowledgeStore.search_facts_with_threshold",
            "SubstrateRegistry.register_substrate_entry",
        ],
        "capability_reality": {
            "typed_contract_artifact": "ValueOuterSet + LegalThresholdEvaluation + LegalTemporalCompetence",
            "producer": "SKGQuery/LegalKnowledgeStore real DuckDB accessors",
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": "WorldModelRecord SKG ref + DesignProblem/N2 consumable Lex DTOs",
            "consumer": "N4/N8/N1/N2 hooks via existing owners",
            "verification": "knowledge_substrate_behavior_report",
            "surface": "GY-S0 substrate registry + generated contract artifact",
            "semantic_test": "real-store integration + remove-property behavior probes",
        },
        "patterns_closed": ["P01", "P03", "P04", "P05", "P07", "P08", "P10", "P27", "P29", "P32", "P33"],
        "missing_capability_labels": [],
        "behavioral_checks": {
            "knowledge_substrate": {
                "status": behavior["status"],
                "case_count": behavior["case_count"],
                "case_ids": [case["case_id"] for case in behavior["cases"]],
            }
        },
        "json_schemas": {
            "value_outer_set": ValueOuterSet.model_json_schema(),
            "legal_rule_threshold_row": LegalRuleThresholdRow.model_json_schema(),
            "legal_threshold_evaluation": LegalThresholdEvaluation.model_json_schema(),
            "legal_temporal_competence": LegalTemporalCompetence.model_json_schema(),
        },
        "behavior_report": behavior,
    }
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def validate(repo_root: Path | None = None) -> dict[str, Any]:
    """Validate committed artifact drift and live behavior."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    output_path = repo_root / OUTPUT_PATH
    live = build_live_payload(repo_root)
    issues: list[dict[str, Any]] = []
    if live["behavior_report"]["status"] != "pass":
        issues.extend(live["behavior_report"]["issues"])
    if not output_path.exists():
        issues.append({"code": "knowledge_substrate_contract_missing", "path": OUTPUT_PATH})
    else:
        committed = json.loads(output_path.read_text(encoding="utf-8"))
        if committed != live:
            issues.append({"code": "knowledge_substrate_contract_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "artifact": OUTPUT_PATH,
        "issues": issues,
        "behavior_status": live["behavior_report"]["status"],
    }


def write(repo_root: Path | None = None) -> dict[str, Any]:
    """Write the recomputed artifact."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    payload = build_live_payload(repo_root)
    output_path = repo_root / OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return validate(repo_root)


def _l2_db_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "production_data/policyos_academic_runtime_slim_20260411T112032Z"
        / "academic/graph/scholar_knowledge.duckdb"
    )


def _l3_db_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "production_data/lex/lex-amendment-only-optimized-20260501-v3"
        / "finalize/lex_knowledge_graph.duckdb"
    )


def _repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=_default_repo_root())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output-format", choices=("json", "text"), default="text")
    args = parser.parse_args(argv)
    if args.write:
        report = write(args.repo_root)
    else:
        report = validate(args.repo_root)
    if args.output_format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"{report['status']}: {report['artifact']}")
        for issue in report["issues"]:
            print(f"- {issue['code']}: {issue.get('path', issue.get('case_id', ''))}")
    if args.check or not args.write:
        return 0 if report["status"] == "pass" else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
