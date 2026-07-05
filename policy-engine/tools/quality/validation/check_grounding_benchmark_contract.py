#!/usr/bin/env python3
"""Validate the CGF GY-CG6 grounding benchmark scoreboard."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/grounding_benchmark_scoreboard.json"
SCHEMA_VERSION = "policyos.policy_design_case.grounding_benchmark_contract.v1"
EXPECTED_BASELINES = {
    "entity_linker_recorded_replay",
    "exact_match_alias_table",
    "full_cgf_stack",
    "greedy_per_axis",
    "lexical_similarity_duckdb_fts_top1",
    "llm_judge_recorded_replay",
    "passive_abstain",
}
EXPECTED_STRESS_FAMILIES = {
    "adversarial_mimicry",
    "compositional_multi_atom_bundle",
    "cross_modal_inconsistent",
    "false_analog_minimal_axis_swap",
    "high_lexical_similarity_false_analog",
    "joint_type_inconsistent",
    "name_collision_false_analog",
    "novel_lever_owner_backed",
}
EXPECTED_LIVENESS = {
    "cg1_critical_veto_disabled_only",
    "cg1_critical_veto_disabled_stacked_similarity",
    "cg2_calibration_owner_validation_bypassed_only",
    "cg2_calibration_owner_validation_bypassed_stacked_freeze",
    "cg3_allow_substrate_registry_authority_only",
    "cg3_disable_denotation_novelty_only",
    "cg3_disable_do_path_resolution_only",
    "cg3_disable_mechanism_witness_resolution_only",
    "cg3_disable_stable_unique_only",
    "cg3_mechanism_witness_trust_restored_stacked",
}


def declared_outputs() -> list[str]:
    """Return generated artifacts owned by this validator."""

    return [OUTPUT_PATH]


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _configure_validation_jax_platform() -> None:
    """Keep validator WMR builds reproducible without runtime env mutation."""

    os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
    os.environ.setdefault("JAX_PLATFORMS", "cpu")


def build_live_payload(repo_root: Path | None = None) -> dict[str, Any]:
    """Recompute the CG6 benchmark from the live CG0 reference."""

    _configure_validation_jax_platform()
    from polisyos.runtime.quality.credal_reference import build_credal_reference
    from polisyos.runtime.quality.grounding_benchmark import (
        GROUNDING_BENCHMARK_SCHEMA_VERSION,
        build_grounding_benchmark_live_slice_for_contract_testing,
        build_grounding_benchmark_reference_for_contract_testing,
        build_grounding_benchmark_scoreboard,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    reference = build_grounding_benchmark_reference_for_contract_testing()
    scoreboard = build_grounding_benchmark_scoreboard(reference)
    live_reference = build_credal_reference(repo_root)
    live_slice = build_grounding_benchmark_live_slice_for_contract_testing(
        representative_reference=reference,
        live_reference=live_reference,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.grounding_benchmark_rt6",
        "runtime_schema_version": GROUNDING_BENCHMARK_SCHEMA_VERSION,
        "owner": "polisyos.runtime.quality.grounding_benchmark",
        "source_modules": [
            "src/polisyos/runtime/quality/grounding_benchmark.py",
            "src/polisyos/runtime/quality/credal_reference.py",
            "src/polisyos/runtime/quality/grounding_relation.py",
            "src/polisyos/runtime/quality/grounding_bind.py",
            "src/polisyos/runtime/quality/grounding_admission.py",
            "src/polisyos/runtime/quality/grounding_phrasing_defense.py",
            "tools/quality/validation/check_grounding_benchmark_contract.py",
        ],
        "reuse_existing_owners": [
            "CG0 CredalReference DTO with validator-scoped owner-shaped L2/L3/L6/WMR insertion",
            "CG1 GroundingRelationEngine and DuckDB FTS candidate retrieval",
            "CG2 GroundingBindGate production and existing for_contract_testing mutations",
            "CG3 GroundingAdmissionEngine production and existing for_contract_testing mutations",
            "CG4 GroundingPhrasingDefenseEngine proxy-gap quarantine detector",
        ],
        "representative_scope": {
            "scope": "explicit_representative_owner_shaped_reference",
            "reason": (
                "The headline denominator is the deterministic owner-shaped "
                "representative CG0 reference. A fixed live CG0 slice is committed "
                "below as a reality anchor and divergence check; it is not silently "
                "folded into the representative-world headline."
            ),
            "case_set_selector": (
                "fixed seed over registered atoms, aliases, L2 causal edges, L3/L6 "
                "legal phrasings, and WMR slots in the representative reference"
            ),
        },
        "live_slice": live_slice,
        "scoreboard": scoreboard.model_dump(mode="json"),
        "contract_fixture_disjointness": _contract_fixture_disjointness(
            scoreboard.model_dump(mode="json"),
            reference=reference,
        ),
        "grounding_bind_unchanged_scope_guard": _grounding_bind_scope_guard(repo_root),
        "capability_reality": {
            "typed_contract_artifact": (
                "GroundingBenchmarkScoreboard + score slices + detector-liveness records"
            ),
            "producer": "build_grounding_benchmark_scoreboard",
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": (
                "benchmark drives CG1->CG2->CG3 and CG4 over CG0 references; "
                "calibration anchor set is produced but not wired"
            ),
            "consumer": "validator/audit surface and future CG2 calibration owner",
            "verification": "this recomputing validator plus corrupt-field drift check",
            "surface": "generated Policy Design Case CG6 scoreboard artifact",
            "semantic_test": (
                "false-bind-under-growth headline, honest baselines, label derivation, "
                "detector liveness, and fixture disjointness"
            ),
        },
        "pattern_pass": {
            "relevant_ids": ["P01", "P03", "P05", "P10", "P15", "P27", "P29", "P32", "P33"],
            "target_correct_pattern": (
                "live-pipeline benchmark over owner-derived cases; benchmark measures "
                "rather than asserts a flattering result"
            ),
            "missing_capability_labels": [],
            "acceptance_signal": (
                "--write then --check then --corrupt-field-drift-check pass; liveness "
                "broken variants degrade"
            ),
        },
    }
    return _json_stable(payload)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a recomputed or committed CG6 payload."""

    issues = _core_issues(payload)
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(repo_root: Path | None = None) -> dict[str, Any]:
    """Validate committed artifact drift and live CG6 behavior."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    path = repo_root / OUTPUT_PATH
    live = build_live_payload(repo_root)
    issues = _core_issues(live)
    committed: dict[str, Any] | None = None
    if not path.is_file():
        issues.append({"code": "grounding_benchmark_scoreboard_missing", "path": OUTPUT_PATH})
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                {
                    "code": "grounding_benchmark_scoreboard_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and _normalize_for_drift(committed) != _normalize_for_drift(live):
        issues.append({"code": "grounding_benchmark_scoreboard_drift", "path": OUTPUT_PATH})
    scoreboard = live["scoreboard"]
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
        "scoreboard_hash": scoreboard["content_hash"],
        "headline": scoreboard["headline"],
        "growth_epochs": [
            row["epoch_id"] for row in scoreboard.get("growth_epochs", [])
        ],
        "liveness": {
            row["variant_id"]: {
                "confident_wrong_count": row["confident_wrong_count"],
                "materially_degraded": row["materially_degraded"],
            }
            for row in scoreboard.get("detector_liveness", [])
        },
    }


def write(repo_root: Path, *, payload: dict[str, Any] | None = None) -> None:
    """Write the live CG6 scoreboard artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    live = payload or build_live_payload(repo_root)
    path.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def corrupt_field_drift_check(repo_root: Path | None = None) -> dict[str, Any]:
    """Prove decisive corruptions turn validation red."""

    live = build_live_payload(repo_root)
    corrupted = _copy(live)
    scoreboard = corrupted["scoreboard"]
    scoreboard["headline"]["growth_epoch_count"] = 0
    scoreboard["headline"]["false_bind"]["denominator"] = 0
    scoreboard["score_slices"][0]["false_bind"]["rate"] = 1.0
    scoreboard["score_slices"][0]["epoch_id"] = ""
    replayable_decision = next(
        decision for decision in scoreboard["decisions"] if decision["certificate_chain"]
    )
    replayable_decision["certificate_chain"][0]["content_hash"] = "sha256:" + "0" * 64
    scoreboard["baseline_configs"]["exact_match_alias_table"]["alias_table_hash"] = (
        "sha256:" + "0" * 64
    )
    scoreboard["baseline_configs"]["exact_match_alias_table"]["decision_boundary"] = (
        "name equality without alias table"
    )
    scoreboard["cases"][0]["label_derivation"]["derivation_kind"] = "hand_asserted"
    scoreboard["detector_liveness"] = [
        row for row in scoreboard["detector_liveness"] if row["variant_id"] == "working_stack"
    ]
    frozen_pr = _copy(scoreboard)
    frozen_pr["headline"] = {
        "metric_id": "frozen_precision_recall",
        "baseline_id": "full_cgf_stack",
        "precision": 1.0,
        "recall": 1.0,
    }
    frozen_pr["score_slices"] = [
        {key: value for key, value in row.items() if key != "epoch_id"}
        for row in frozen_pr["score_slices"]
    ]
    corrupted["frozen_precision_recall_mutation"] = frozen_pr
    scoreboard["content_hash"] = "sha256:" + "0" * 64
    report = validate_payload(corrupted)
    frozen_report = validate_payload(
        {**_copy(live), "scoreboard": frozen_pr}
    )
    return {
        "status": "pass"
        if report["status"] == "fail" and frozen_report["status"] == "fail"
        else "fail",
        "issues": []
        if report["status"] == "fail" and frozen_report["status"] == "fail"
        else [{"code": "grounding_benchmark_corrupt_field_not_detected"}],
        "corrupt_report_status": report["status"],
        "corrupt_issue_codes": [issue["code"] for issue in report["issues"]],
        "frozen_precision_recall_status": frozen_report["status"],
        "frozen_precision_recall_issue_codes": [
            issue["code"] for issue in frozen_report["issues"]
        ],
    }


def _core_issues(payload: dict[str, Any]) -> list[dict[str, Any]]:
    from polisyos.runtime.quality.grounding_benchmark import (
        GroundingBenchmarkScoreboard,
        validate_grounding_benchmark_payload,
    )

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "grounding_benchmark_contract_schema_mismatch"})
    raw_scoreboard = payload.get("scoreboard")
    scoreboard = None
    if not isinstance(raw_scoreboard, Mapping):
        issues.append({"code": "grounding_benchmark_scoreboard_missing_payload"})
    else:
        runtime_report = validate_grounding_benchmark_payload(raw_scoreboard)
        for code in runtime_report["issue_codes"]:
            issues.append({"code": code})
        try:
            scoreboard = GroundingBenchmarkScoreboard.model_validate(raw_scoreboard)
        except Exception as exc:  # noqa: BLE001 - validator reports model errors.
            issues.append(
                {
                    "code": "grounding_benchmark_scoreboard_model_invalid",
                    "error": str(exc).split("\n", 1)[0],
                }
            )
    if scoreboard is not None:
        baseline_ids = set(scoreboard.baseline_configs)
        missing_baselines = sorted(EXPECTED_BASELINES.difference(baseline_ids))
        if missing_baselines:
            issues.append(
                {
                    "code": "grounding_benchmark_baseline_missing",
                    "missing": missing_baselines,
                }
            )
        score_keys = {
            (row.baseline_id, row.epoch_id, row.stream, row.family)
            for row in scoreboard.score_slices
        }
        case_groups = {
            (case.epoch_id, case.stream, case.family) for case in scoreboard.cases
        }
        for baseline in EXPECTED_BASELINES:
            for epoch_id, stream, family in case_groups:
                if (baseline, epoch_id, stream, family) not in score_keys:
                    issues.append(
                        {
                            "code": "grounding_benchmark_full_denominator_missing",
                            "baseline": baseline,
                            "epoch_id": epoch_id,
                            "stream": stream,
                            "family": family,
                        }
                    )
        stress_families = {
            case.family for case in scoreboard.cases if case.stream == "stress"
        }
        missing_stress = sorted(EXPECTED_STRESS_FAMILIES.difference(stress_families))
        if missing_stress:
            issues.append(
                {
                    "code": "grounding_benchmark_stress_family_missing",
                    "missing": missing_stress,
                }
            )
        if len(scoreboard.growth_epochs) < 3:
            issues.append({"code": "grounding_benchmark_growth_epoch_count_too_small"})
        if not any(row.admitted_lever_groundable for row in scoreboard.growth_epochs):
            issues.append({"code": "grounding_benchmark_growth_loop_not_closed"})
        if not any(row.fresh_mimicry_caught for row in scoreboard.growth_epochs):
            issues.append({"code": "grounding_benchmark_growth_mimicry_not_caught"})
        if scoreboard.calibration_anchor_set.wired_into_cg2:
            issues.append({"code": "grounding_benchmark_calibration_set_wired"})
        if "grounding_bind.py" not in scoreboard.calibration_anchor_set.unfreeze_pathway:
            issues.append({"code": "grounding_benchmark_cg2_unfreeze_path_missing"})
        if scoreboard.headline.growth_epoch_count < 2:
            issues.append({"code": "grounding_benchmark_headline_growth_missing"})
        if scoreboard.headline.metric_id != "false_bind_rate_under_growth":
            issues.append({"code": "grounding_benchmark_wrong_headline_metric"})
        for row in scoreboard.score_slices:
            if row.total_cases != row.evaluated_cases + row.dropped_cases:
                issues.append(
                    {
                        "code": "grounding_benchmark_denominator_inconsistent",
                        "baseline": row.baseline_id,
                        "epoch_id": row.epoch_id,
                        "stream": row.stream,
                        "family": row.family,
                    }
                )
            for metric_name in (
                "false_bind",
                "hallucination_admit",
                "confident_wrong",
                "useful_recall",
                "certificate_replay_completeness",
            ):
                metric = getattr(row, metric_name)
                if metric.denominator < metric.numerator:
                    issues.append(
                        {
                            "code": "grounding_benchmark_metric_numerator_exceeds_denominator",
                            "metric": metric_name,
                        }
                    )
                if metric.lower > metric.rate or metric.rate > metric.upper:
                    issues.append(
                        {
                            "code": "grounding_benchmark_interval_does_not_cover_rate",
                            "metric": metric_name,
                        }
                    )
        liveness = {
            row.variant_id: row for row in scoreboard.detector_liveness
        }
        missing_liveness = sorted(EXPECTED_LIVENESS.difference(liveness))
        if missing_liveness:
            issues.append(
                {
                    "code": "grounding_benchmark_detector_liveness_missing",
                    "missing": missing_liveness,
                }
            )
        for variant_id in EXPECTED_LIVENESS.intersection(liveness):
            if liveness[variant_id].detection_floor == "not_applicable":
                issues.append(
                    {
                        "code": "grounding_benchmark_detector_liveness_floor_missing",
                        "variant": variant_id,
                    }
                )
            if liveness[variant_id].confident_wrong_interval.denominator != liveness[variant_id].denominator:
                issues.append(
                    {
                        "code": "grounding_benchmark_detector_liveness_interval_missing",
                        "variant": variant_id,
                    }
                )
        if not scoreboard.latency_bound_asserted:
            issues.append({"code": "grounding_benchmark_latency_bound_not_asserted"})
        case_ids = {case.case_id for case in scoreboard.cases}
        dropped_ids = {case.case_id for case in scoreboard.dropped_cases}
        for case in scoreboard.cases:
            if case.label_derivation.derivation_kind == "hand_asserted" and case.case_id not in dropped_ids:
                issues.append(
                    {
                        "code": "grounding_benchmark_label_authoring_accepted",
                        "case_id": case.case_id,
                    }
                )
        if case_ids & dropped_ids:
            # Dropped cases stay listed in cases and dropped_cases; this is expected.
            pass
    disjoint = payload.get("contract_fixture_disjointness", {})
    if isinstance(disjoint, Mapping):
        if disjoint.get("disjoint") is not True:
            issues.append(
                {
                    "code": "grounding_benchmark_contract_fixture_overlap",
                    "overlap": disjoint.get("overlap_hashes"),
                }
            )
    else:
        issues.append({"code": "grounding_benchmark_disjointness_missing"})
    live_slice = payload.get("live_slice")
    if not isinstance(live_slice, Mapping):
        issues.append({"code": "grounding_benchmark_live_slice_missing"})
    else:
        composition = live_slice.get("composition")
        if not isinstance(composition, Mapping) or int(composition.get("live_cases") or 0) < 5:
            issues.append({"code": "grounding_benchmark_live_slice_too_small"})
        if live_slice.get("content_hash") != _live_slice_hash(live_slice):
            issues.append({"code": "grounding_benchmark_live_slice_hash_mismatch"})
    bind_guard = payload.get("grounding_bind_unchanged_scope_guard", {})
    if isinstance(bind_guard, Mapping) and bind_guard.get("grounding_bind_touched_by_cg6") is True:
        issues.append({"code": "grounding_benchmark_grounding_bind_touched"})
    return _dedupe_issues(issues)


def _contract_fixture_disjointness(
    scoreboard: Mapping[str, Any],
    *,
    reference: Any,
) -> dict[str, Any]:
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from tools.quality.validation import check_grounding_admission_contract as cg3
    from tools.quality.validation import check_grounding_phrasing_defense_contract as cg4
    from tools.quality.validation import check_grounding_relation_contract as cg1

    engine = GroundingRelationEngine(reference)
    fixtures: list[Mapping[str, Any]] = [
        cg1._false_analog_probe("sign_swap"),  # noqa: SLF001
        cg1._greedy_inconsistent_probe(),  # noqa: SLF001
        cg1._cross_modal_inconsistent_probe(),  # noqa: SLF001
        cg1._pure_synonym_probe(engine),  # noqa: SLF001
        cg1._unknown_unproven_probe(),  # noqa: SLF001
        cg3._free_grow_probe(),  # noqa: SLF001
        cg3._outcome_wish_probe(),  # noqa: SLF001
        cg3._impossible_type_probe(),  # noqa: SLF001
        cg4._tax_unregistered_mimic_probe("tax relief rate adjustment"),  # noqa: SLF001
        cg4._self_loop_outcome_wish_probe(),  # noqa: SLF001
    ]
    cg5_low_cost_probe = cg3._free_grow_probe()  # noqa: SLF001
    cg5_low_cost_probe = {
        **cg5_low_cost_probe,
        "proposal_id": "cg5.low_cost.high_human_admissibility",
        "signature": {
            **cg5_low_cost_probe["signature"],
            "admissibility": "candidate_unverified",
        },
    }
    cg5_fixtures: list[Mapping[str, Any]] = [
        cg3._free_grow_probe(),  # noqa: SLF001
        cg5_low_cost_probe,
        cg1._unknown_unproven_probe(),  # noqa: SLF001
        cg4._tax_unregistered_mimic_probe("tax relief rate adjustment"),  # noqa: SLF001
        cg3._outcome_like_policy_map_probe(),  # noqa: SLF001
    ]
    fixtures.extend(cg5_fixtures)
    fixture_hashes = {gy_content_hash(_json_ready(item)) for item in fixtures}
    case_hashes = {
        gy_content_hash(_json_ready(case.get("proposal")))
        for case in _sequence(scoreboard.get("cases"))
        if isinstance(case, Mapping)
    }
    overlap = sorted(fixture_hashes & case_hashes)
    return {
        "checked": True,
        "covered_contracts": ("CG1", "CG3", "CG4", "CG5"),
        "fixture_count": len(fixture_hashes),
        "benchmark_case_count": len(case_hashes),
        "disjoint": not overlap,
        "overlap_hashes": overlap,
    }


def _grounding_bind_scope_guard(repo_root: Path) -> dict[str, Any]:
    bind_path = "src/polisyos/runtime/quality/grounding_bind.py"
    try:
        import subprocess

        result = subprocess.run(
            ["git", "diff", "--name-only", "--", bind_path],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        touched = bool(result.stdout.strip())
    except Exception:  # noqa: BLE001 - scope guard falls back to unknown.
        return {"checked": False, "grounding_bind_touched_by_cg6": None}
    return {
        "checked": True,
        "grounding_bind_touched_by_cg6": touched,
        "path": bind_path,
        "scope_note": "CG6 must not unfreeze production bind paths.",
    }


def _normalize_for_drift(payload: Mapping[str, Any]) -> Any:
    return _without_latency(_json_ready(payload))


def _live_slice_hash(live_slice: Mapping[str, Any]) -> str:
    body = dict(_json_ready(live_slice))
    body.pop("content_hash", None)
    body.pop("latency_ms", None)
    return _content_hash(_without_latency(body))


def _content_hash(value: object) -> str:
    from polisyos.pdc import gy_content_hash

    return gy_content_hash(value)


def _without_latency(value: object) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _without_latency(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in {"latency_ms", "latency_ms_p50", "latency_ms_max"}
        }
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_without_latency(item) for item in value]
    return value


def _json_ready(value: object) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


def _sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return value
    return ()


def _copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _json_stable(payload: dict[str, Any]) -> dict[str, Any]:
    return _copy(payload)


def _dedupe_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        key = json.dumps(issue, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(issue)
    return deduped


def main(argv: list[str] | None = None) -> int:
    """Run the CGF GY-CG6 grounding benchmark validator."""

    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--corrupt-field-drift-check", action="store_true")
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    inserted = [str(repo_root), str(repo_root / "src")]
    for item in reversed(inserted):
        if item not in sys.path:
            sys.path.insert(0, item)

    if args.corrupt_field_drift_check:
        report = corrupt_field_drift_check(repo_root)
    else:
        live_payload = build_live_payload(repo_root) if args.write else None
        if args.write:
            write(repo_root, payload=live_payload)
        report = validate(repo_root) if not args.write else validate_payload(live_payload)

    if args.output_format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif report["status"] != "pass":
        for issue in report["issues"]:
            print(f"{issue.get('code')}: {issue}")
    else:
        print("grounding benchmark contract: pass")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
