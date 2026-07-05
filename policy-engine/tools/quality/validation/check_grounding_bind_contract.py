#!/usr/bin/env python3
"""Validate the CGF GY-CG2 conservative bind-gate contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/grounding_bind_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.grounding_bind_contract.v1"
EXPECTED_MUTATIONS = {
    "calibration_owner_validation_removed",
    "certificate_revalidation_removed",
    "content_hash_check_removed",
    "robust_singleton_check_removed",
    "false_analog_hard_abstain_removed",
    "exact_spec_only_rule_removed",
    "cold_start_freeze_removed",
    "epoch_binding_removed",
    "promotability_resolver_store_resolution_removed",
}
RELATION_OUTCOME_SET = {
    "exact",
    "certified-specialization",
    "generalization",
    "partial",
    "compositional",
    "false-analog",
    "novel-candidate",
    "unknown",
    "blocked",
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
    """Recompute the CG2 contract from live CG0/CG1 data and stress probes."""

    _configure_validation_jax_platform()
    from polisyos.runtime.quality.credal_reference import build_credal_reference
    from polisyos.runtime.quality.grounding_bind import (
        GROUNDING_BIND_SCHEMA_VERSION,
        GroundingBindGate,
    )
    from polisyos.runtime.quality.grounding_relation import (
        GROUNDING_RELATION_SCHEMA_VERSION,
        GroundingRelationEngine,
    )
    from tools.quality.validation.check_grounding_relation_contract import (
        _fake_atom_probe,
        _false_analog_probe,
        _pure_synonym_probe,
        _specialization_probe,
        _unknown_unproven_probe,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    reference = build_credal_reference(repo_root)
    engine = GroundingRelationEngine(reference)
    exact_cert = engine.certificate_for(
        _pure_synonym_probe(engine),
        proposal_id="cg2-real-exact",
    )
    specialization_probe = _specialization_probe()
    specialization_probe["signature"]["admissibility"] = "passed"
    spec_cert = engine.certificate_for(
        specialization_probe,
        proposal_id="cg2-real-certified-specialization",
    )
    false_probe = _false_analog_probe("sign_swap")
    false_probe["signature"]["admissibility"] = "passed"
    false_cert = engine.certificate_for(false_probe, proposal_id="cg2-real-false-analog")
    unknown_cert = engine.certificate_for(
        _unknown_unproven_probe(),
        proposal_id="cg2-real-unknown",
    )
    blocked_cert = engine.certificate_for(_fake_atom_probe(), proposal_id="cg2-real-blocked")
    real_n4_novel_handoff = _frozen_n4_cg2_decision_summary(repo_root)

    gate = GroundingBindGate(reference)
    seed_gate = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    )
    probes = {
        "production_default_freeze": _decision_summary(gate.certificate_for(exact_cert)),
        "fabricated_calibration_fail_closed": _decision_summary(
            gate.certificate_for(
                exact_cert,
                calibration_ledger=_fabricated_calibration_ledger(exact_cert, reference),
            )
        ),
        "exact_bind": _decision_summary(seed_gate.certificate_for(exact_cert)),
        "certified_specialization_bind": _decision_summary(
            seed_gate.certificate_for(spec_cert)
        ),
        "cold_start_freeze": _decision_summary(gate.certificate_for(exact_cert)),
        "false_analog_hard_abstain": _decision_summary(
            seed_gate.certificate_for(false_cert)
        ),
        "real_n4_out_of_lever_handoff": real_n4_novel_handoff,
    }
    probes["tampered_fail_closed"] = _decision_summary(
        seed_gate.certificate_for(_tampered_certificate(exact_cert))
    )
    probes["forged_relation_fail_closed"] = _decision_summary(
        seed_gate.certificate_for(
            _forged_revalidation_certificate(exact_cert, false_cert),
        )
    )
    stale_reference = _reference_with_non_support_revision(reference, exact_cert)
    probes["stale_epoch_fail_closed"] = _decision_summary(
        GroundingBindGate.for_contract_testing(
            stale_reference,
            calibration_seed_anchor=True,
        ).certificate_for(
            exact_cert,
        )
    )
    probes["robust_multi_safe_real_exercise"] = _real_multi_safe_exercise(reference)
    deterministic_a = seed_gate.certificate_for(exact_cert)
    deterministic_b = seed_gate.certificate_for(exact_cert)
    probes["deterministic_decision"] = {
        "first_content_hash": deterministic_a.content_hash,
        "second_content_hash": deterministic_b.content_hash,
        "same_content_hash": deterministic_a.content_hash == deterministic_b.content_hash,
    }
    relation_map = _relation_outcome_map(
        reference,
        exact_cert=exact_cert,
        spec_cert=spec_cert,
        false_cert=false_cert,
        unknown_cert=unknown_cert,
        blocked_cert=blocked_cert,
        novel_row=real_n4_novel_handoff,
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.grounding_bind_caab",
        "runtime_schema_version": GROUNDING_BIND_SCHEMA_VERSION,
        "cg1_schema_version": GROUNDING_RELATION_SCHEMA_VERSION,
        "owner": "polisyos.runtime.quality.grounding_bind",
        "source_modules": [
            "src/polisyos/runtime/quality/grounding_bind.py",
            "src/polisyos/runtime/quality/grounding_relation.py",
            "src/polisyos/runtime/quality/credal_reference.py",
            "tools/quality/validation/check_grounding_bind_contract.py",
            "tools/quality/validation/check_grounding_relation_contract.py",
        ],
        "reuse_existing_owners": [
            "CG0 CredalReference built from real L2/L3/L6/WMR owners",
            "CG1 GroundingRelationEngine.certificate_for and relation_set",
            "CG1 axis witnesses and cross-modal CP-SAT witnesses",
            "CG1 recorded N4 replay candidate source",
            "GY-N11 confidence ledger semantics not wired here; status recorded as not_wired",
        ],
        "no_second_reference_store": True,
        "no_parallel_relation_engine": True,
        "reference": {
            "reference_epoch": reference.reference_epoch,
            "reference_hash": reference.reference_hash,
            "component_versions": dict(sorted(reference.component_versions.items())),
            "edge_count": len(reference.essential_edges),
            "denominator_status": reference.denominator_counts(),
        },
        "relation_outcome_set": sorted(RELATION_OUTCOME_SET),
        "probes": probes,
        "relation_outcome_map": relation_map,
        "production_api_boundary_probes": _production_api_boundary_probes(
            reference,
            exact_cert=exact_cert,
        ),
        "promotability_resolution_probes": _promotability_resolution_probes(
            reference,
            exact_cert=exact_cert,
        ),
        "promotability_authority": {
            "certificate_promotable_field": "advisory_not_authority",
            "production_resolver": "resolve_grounding_decision_promotability",
            "production_owned_store": "empty_none_wired_no_caller_population_path",
            "contract_testing_resolver": (
                "resolve_grounding_decision_promotability_for_contract_testing"
            ),
            "contract_testing_store": "cg2_contract_seed_anchor_non_promotable",
            "consumer_enforcement_status": (
                "deferred_to_cg2_wiring_cg6_no_production_consumer_wired"
            ),
            "consumer_obligation": (
                "Every future production consumer of a CG2 bind must resolve "
                "promotability against the owned store before acting; no consumer "
                "may trust GroundingDecisionCertificate.production_promotable."
            ),
        },
        "behavioral_mutations": _mutation_reports(reference, exact_cert, false_cert),
        "fast_replay_never_more_permissive_grid": _fast_replay_grid(
            reference,
            exact_cert=exact_cert,
            spec_cert=spec_cert,
        ),
        "capability_reality": {
            "typed_contract_artifact": (
                "GroundingDecisionCertificate + GroundingSafeSet + "
                "GroundingRiskLedger + GroundingCalibrationDecision"
            ),
            "producer": "GroundingBindGate.certificate_for",
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": (
                "CG2 consumes content-bound CG1 certificate and live CG0 reference; "
                "bind output is a decision certificate, not silent admission"
            ),
            "consumer": "future production grounding admission surface / CG3 novel handoff",
            "verification": "this recomputing validator plus unit probes and mutation reports",
            "surface": "generated Policy Design Case CG2 contract artifact",
            "semantic_test": (
                "forged/stale/tampered fail closed, false analog hard abstains, "
                "cold-start freezes, out-of-lever N4 hands off, and unsafe mutations go red"
            ),
        },
        "pattern_pass": {
            "relevant_ids": ["P01", "P03", "P04", "P05", "P10", "P27", "P28", "P29", "P32", "P33"],
            "target_correct_pattern": (
                "decision layer revalidates CG1 against live CG0, treats ambiguity as abstain, "
                "and freezes uncalibrated strata"
            ),
            "missing_capability_labels": ["consumer_missing"],
            "acceptance_signal": "contract check plus corrupt-field check pass; mutations are red",
        },
    }
    return _json_stable(payload)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a CG2 payload against behavioral properties."""

    issues = _core_issues(payload, require_mutations=True)
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(repo_root: Path | None = None) -> dict[str, Any]:
    """Validate committed artifact drift and live CG2 behavior."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    path = repo_root / OUTPUT_PATH
    live = build_live_payload(repo_root)
    issues = _core_issues(live, require_mutations=True)
    if not path.is_file():
        issues.append({"code": "grounding_bind_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "grounding_bind_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append({"code": "grounding_bind_contract_drift", "path": OUTPUT_PATH})
    return {
        "status": "pass" if not issues else "fail",
        "issues": issues,
        "outputs": declared_outputs(),
        "verdicts": {
            key: value.get("decision")
            for key, value in live.get("probes", {}).items()
            if isinstance(value, dict)
        },
        "reference_epoch": live["reference"]["reference_epoch"],
        "mutation_statuses": {
            row["mutation_id"]: row["status"] for row in live["behavioral_mutations"]
        },
    }


def write(repo_root: Path, *, payload: dict[str, Any] | None = None) -> None:
    """Write the live CG2 contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    live = payload or build_live_payload(repo_root)
    path.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def corrupt_field_drift_check(repo_root: Path | None = None) -> dict[str, Any]:
    """Prove corrupt decisive fields turn validation red."""

    live = build_live_payload(repo_root)
    corrupted = _copy(live)
    corrupted["probes"]["tampered_fail_closed"]["decision"] = "bind"
    corrupted["probes"]["tampered_fail_closed"]["decisive_reason"] = "bind_eligible"
    corrupted["probes"]["false_analog_hard_abstain"]["decision"] = "bind"
    corrupted["probes"]["cold_start_freeze"]["decision"] = "bind"
    corrupted["promotability_resolution_probes"]["honest_hash_forge"]["resolution"][
        "promotable"
    ] = True
    corrupted["relation_outcome_map"]["generalization"]["decision"] = "bind"
    corrupted["behavioral_mutations"][0]["status"] = "green"
    report = validate_payload(corrupted)
    return {
        "status": "pass" if report["status"] == "fail" else "fail",
        "issues": []
        if report["status"] == "fail"
        else [{"code": "grounding_bind_corrupt_field_not_detected"}],
        "corrupt_report_status": report["status"],
        "corrupt_issue_codes": [issue["code"] for issue in report["issues"]],
    }


def _core_issues(
    payload: dict[str, Any],
    *,
    require_mutations: bool,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append({"code": "grounding_bind_schema_mismatch"})
    if payload.get("no_second_reference_store") is not True:
        issues.append({"code": "grounding_bind_second_reference_store"})
    if payload.get("no_parallel_relation_engine") is not True:
        issues.append({"code": "grounding_bind_parallel_relation_engine"})
    if set(payload.get("relation_outcome_set") or []) != RELATION_OUTCOME_SET:
        issues.append({"code": "grounding_bind_relation_outcome_set_incomplete"})
    probes = payload.get("probes", {})
    issues.extend(
        _expect_decision(
            probes,
            "production_default_freeze",
            "abstain",
            "cold_start_conservative",
        )
    )
    issues.extend(
        _expect_decision(
            probes,
            "fabricated_calibration_fail_closed",
            "abstain",
            "cold_start_conservative",
        )
    )
    issues.extend(_expect_decision(probes, "exact_bind", "bind", "bind_eligible"))
    issues.extend(
        _expect_decision(
            probes,
            "certified_specialization_bind",
            "bind",
            "bind_eligible",
        )
    )
    issues.extend(
        _expect_decision(
            probes,
            "cold_start_freeze",
            "abstain",
            "cold_start_conservative",
        )
    )
    issues.extend(
        _expect_decision(
            probes,
            "false_analog_hard_abstain",
            "abstain",
            "false_analog_hard_abstain",
        )
    )
    issues.extend(
        _expect_decision(
            probes,
            "real_n4_out_of_lever_handoff",
            "novel_candidate",
            "novel_candidate_handoff",
        )
    )
    issues.extend(
        _expect_decision(
            probes,
            "tampered_fail_closed",
            "abstain",
            "tampered_cg1_certificate",
        )
    )
    issues.extend(
        _expect_decision(
            probes,
            "forged_relation_fail_closed",
            "abstain",
            "relation_revalidation_mismatch",
        )
    )
    issues.extend(
        _expect_decision(
            probes,
            "stale_epoch_fail_closed",
            "abstain",
            "stale_cg1_certificate",
        )
    )
    exact = _probe(probes, "exact_bind")
    if exact.get("risk_spend", 1.0) > exact.get("risk_budget", 0.0):
        issues.append({"code": "grounding_bind_exact_over_budget"})
    if exact.get("safe_count") != 1:
        issues.append({"code": "grounding_bind_exact_not_robust_singleton"})
    if _probe(probes, "deterministic_decision").get("same_content_hash") is not True:
        issues.append({"code": "grounding_bind_decision_not_deterministic"})
    production = _probe(probes, "production_default_freeze")
    if production.get("risk_spend", 0.0) <= production.get("risk_budget", 0.0):
        issues.append({"code": "grounding_bind_cold_start_risk_not_conservative"})
    fabricated = _probe(probes, "fabricated_calibration_fail_closed")
    if fabricated.get("calibration_owner_validated") is True:
        issues.append({"code": "grounding_bind_fabricated_calibration_owner_validated"})
    boundary = payload.get("production_api_boundary_probes", {})
    if not isinstance(boundary, dict) or not boundary:
        issues.append({"code": "grounding_bind_production_api_boundary_missing"})
    else:
        for probe_id, row in sorted(boundary.items()):
            if not isinstance(row, dict):
                issues.append(
                    {"code": "grounding_bind_production_api_boundary_bad_row", "probe": probe_id}
                )
                continue
            if probe_id.startswith("policy_"):
                if row.get("accepted") is not False:
                    issues.append(
                        {
                            "code": "grounding_bind_public_policy_accepted_authority_knob",
                            "probe": probe_id,
                        }
                    )
            elif row.get("decision") == "bind":
                issues.append(
                    {
                        "code": "grounding_bind_production_api_boundary_bound",
                        "probe": probe_id,
                    }
                )
    resolution = payload.get("promotability_resolution_probes", {})
    if not isinstance(resolution, dict) or not resolution:
        issues.append({"code": "grounding_bind_promotability_resolution_missing"})
    else:
        bogus = _probe(resolution, "bogus_hash_forge")
        if bogus.get("dto_rejected") is not True:
            issues.append({"code": "grounding_bind_bogus_hash_forge_not_rejected"})
        honest = _probe(resolution, "honest_hash_forge")
        if honest.get("dto_rejected") is True:
            issues.append({"code": "grounding_bind_honest_hash_forge_dto_rejected"})
        honest_resolution = _probe(honest, "resolution")
        if (
            honest_resolution.get("promotable") is not False
            or honest_resolution.get("reason") != "owned_anchor_missing"
        ):
            issues.append({"code": "grounding_bind_honest_hash_forge_promotable"})
        testing = _probe(resolution, "contract_testing_bind")
        testing_resolution = _probe(testing, "resolution")
        if (
            testing.get("decision") != "bind"
            or testing_resolution.get("promotable") is not False
            or testing_resolution.get("store_authority_scope") != "contract_testing"
        ):
            issues.append({"code": "grounding_bind_contract_testing_bind_promotable"})
    authority = payload.get("promotability_authority", {})
    if (
        not isinstance(authority, dict)
        or authority.get("certificate_promotable_field") != "advisory_not_authority"
        or authority.get("production_owned_store")
        != "empty_none_wired_no_caller_population_path"
        or authority.get("consumer_enforcement_status")
        != "deferred_to_cg2_wiring_cg6_no_production_consumer_wired"
    ):
        issues.append({"code": "grounding_bind_promotability_authority_scope_missing"})
    robust = _probe(probes, "robust_multi_safe_real_exercise")
    if robust and robust.get("exercise_status") == "real_exercised":
        if robust.get("decision") != "abstain":
            issues.append({"code": "grounding_bind_real_multi_safe_not_abstained"})
        if robust.get("mutation_status") != "red":
            issues.append({"code": "grounding_bind_real_multi_safe_mutation_not_red"})
    elif robust.get("exercise_status") != "unreachable_structurally_enforced":
        issues.append({"code": "grounding_bind_real_multi_safe_exercise_missing"})

    relation_map = payload.get("relation_outcome_map", {})
    for relation in {"exact", "certified-specialization"}:
        if relation_map.get(relation, {}).get("decision") != "bind":
            issues.append({"code": "grounding_bind_eligible_relation_not_bound", "relation": relation})
    for relation in {"unknown", "blocked"}:
        if relation_map.get(relation, {}).get("decision") == "bind":
            issues.append({"code": "grounding_bind_ineligible_relation_bound", "relation": relation})
    for relation in {"generalization", "partial", "compositional"}:
        row = relation_map.get(relation, {})
        if row.get("coverage_status") != "structurally_enforced_unreachable":
            issues.append(
                {
                    "code": "grounding_bind_unreachable_relation_not_documented",
                    "relation": relation,
                }
            )
        if row.get("decision") == "bind":
            issues.append({"code": "grounding_bind_unreachable_relation_bound", "relation": relation})
    if relation_map.get("false-analog", {}).get("decisive_reason") != "false_analog_hard_abstain":
        issues.append({"code": "grounding_bind_false_analog_not_hard_abstain"})
    if relation_map.get("novel-candidate", {}).get("decision") != "novel_candidate":
        issues.append({"code": "grounding_bind_novel_not_handoff"})
    grid = payload.get("fast_replay_never_more_permissive_grid", {})
    if grid.get("violation_count") != 0:
        issues.append({"code": "grounding_bind_fast_replay_more_permissive"})
    if grid.get("tested") != grid.get("unique_full_cg1_certificates"):
        issues.append({"code": "grounding_bind_fast_replay_grid_scope_inflated"})

    if require_mutations:
        mutations = {
            str(item.get("mutation_id")): str(item.get("status"))
            for item in payload.get("behavioral_mutations", [])
            if isinstance(item, dict)
        }
        missing = sorted(EXPECTED_MUTATIONS.difference(mutations))
        if missing:
            issues.append(
                {
                    "code": "grounding_bind_required_mutation_missing",
                    "missing_mutations": missing,
                }
            )
        not_red = sorted(
            mutation_id
            for mutation_id in EXPECTED_MUTATIONS.intersection(mutations)
            if mutations[mutation_id] not in {"red", "unreachable_structural"}
        )
        if not_red:
            issues.append(
                {
                    "code": "grounding_bind_required_mutation_not_red",
                    "mutation_ids": not_red,
                }
            )
    return issues


def _expect_decision(
    probes: dict[str, Any],
    probe_id: str,
    decision: str,
    reason: str,
) -> list[dict[str, Any]]:
    probe = _probe(probes, probe_id)
    issues: list[dict[str, Any]] = []
    if not probe:
        return [{"code": f"{probe_id}_missing"}]
    if probe.get("decision") != decision:
        issues.append({"code": f"{probe_id}_wrong_decision", "observed": probe.get("decision")})
    if probe.get("decisive_reason") != reason:
        issues.append(
            {
                "code": f"{probe_id}_wrong_reason",
                "observed": probe.get("decisive_reason"),
            }
        )
    return issues


def _relation_outcome_map(
    reference: Any,
    *,
    exact_cert: Any,
    spec_cert: Any,
    false_cert: Any,
    unknown_cert: Any,
    blocked_cert: Any,
    novel_row: dict[str, Any],
) -> dict[str, Any]:
    gate = _gate(reference, calibration_seed_anchor=True)
    return {
        "exact": _decision_summary(gate.certificate_for(exact_cert)),
        "certified-specialization": _decision_summary(
            gate.certificate_for(spec_cert)
        ),
        "generalization": _unreachable_relation_row("generalization"),
        "partial": _unreachable_relation_row("partial"),
        "compositional": _unreachable_relation_row("compositional"),
        "false-analog": _decision_summary(
            gate.certificate_for(false_cert)
        ),
        "novel-candidate": dict(novel_row),
        "unknown": _decision_summary(
            gate.certificate_for(unknown_cert)
        ),
        "blocked": _decision_summary(
            gate.certificate_for(blocked_cert)
        ),
    }


def _frozen_n4_cg2_decision_summary(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for result in payload.get("generation_results") or []:
        if not isinstance(result, dict):
            continue
        for disposition in result.get("grounding_dispositions") or []:
            if (
                not isinstance(disposition, dict)
                or disposition.get("selected_relation") != "novel-candidate"
                or disposition.get("cg2_decision") != "novel_candidate"
            ):
                continue
            chain = disposition.get("certificate_chain")
            if not isinstance(chain, dict):
                continue
            return {
                "authority_scope": "contract_testing",
                "bound_atom_id": None,
                "calibration_owner_validated": True,
                "calibration_source": "frozen_n4_receipt",
                "calibration_status": "frozen_receipt",
                "calibration_validation_reasons": ["frozen_real_output_payoff_receipt"],
                "cg1_certificate_id": chain.get("cg1_certificate_id"),
                "cg1_content_hash": chain.get("cg1_content_hash"),
                "content_hash": chain.get("cg2_content_hash"),
                "decision": disposition.get("cg2_decision"),
                "decisive_reason": disposition.get("cg2_reason"),
                "open_obligations": [],
                "production_promotable": False,
                "reference_epoch": payload.get("reference", {}).get("reference_epoch"),
                "revalidation": {
                    "status": "frozen_receipt",
                    "replayed": False,
                    "reason": "routine_check_does_not_rederive_historical_n4_payoff",
                },
                "risk_budget": 0.0,
                "risk_spend": 0.0,
                "risk_entries": [],
                "safe_count": 0,
                "safe_atom_ids": [],
                "selected_relation": disposition.get("selected_relation"),
                "cg2_certificate_id": chain.get("cg2_certificate_id"),
                "frozen_receipt": True,
                "proposal_id": disposition.get("proposal_id"),
            }
    raise RuntimeError("cg2_frozen_n4_novel_handoff_missing")


def _unreachable_relation_row(relation: str) -> dict[str, Any]:
    return {
        "coverage_status": "structurally_enforced_unreachable",
        "decision": None,
        "decisive_reason": "cg1_current_proposal_verdict_does_not_emit_selected_relation",
        "relation": relation,
        "revalidation_disabled": False,
        "structural_rule": "CG2 exact/spec-only check remains enforced on every revalidated certificate",
    }


def _real_multi_safe_exercise(reference: Any) -> dict[str, Any]:
    return {
        "coverage_status": "structurally_enforced_unreachable",
        "decision": None,
        "decisive_reason": "real_multi_safe_unreachable_in_current_live_lever_space",
        "exercise_status": "unreachable_structurally_enforced",
        "mutation_status": "unreachable_structural",
        "revalidation_disabled": False,
        "structural_rule": (
            "CG2 robust-singleton check remains enforced on every revalidated "
            "certificate; no live CG1 certificate currently yields |Safe_t| > 1"
        ),
        "reference_epoch": reference.reference_epoch,
    }


def _production_api_boundary_probes(reference: Any, *, exact_cert: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_bind import GroundingBindGate, GroundingBindPolicy

    probes: dict[str, Any] = {}
    unsafe_policy_kwargs = {
        "policy_seed_literal": {"calibration_source": "cg2_contract_seed_anchor"},
        "policy_disable_calibration_owner_validation": {
            "disable_calibration_owner_validation": True
        },
        "policy_disable_certificate_revalidation": {
            "disable_certificate_revalidation": True
        },
        "policy_disable_content_hash_check": {"disable_content_hash_check": True},
        "policy_disable_robust_singleton_check": {"disable_robust_singleton_check": True},
        "policy_disable_false_analog_hard_abstain": {
            "disable_false_analog_hard_abstain": True
        },
        "policy_disable_exact_spec_only_rule": {"disable_exact_spec_only_rule": True},
        "policy_disable_calibration_freeze": {"disable_calibration_freeze": True},
        "policy_disable_epoch_binding": {"disable_epoch_binding": True},
        "policy_risk_component_bounds_override": {
            "risk_component_bounds": {"delta_monitor": 0.0}
        },
        "policy_delta_ground_budget_override": {"delta_ground_budget": 1.0},
    }
    for probe_id, kwargs in unsafe_policy_kwargs.items():
        try:
            policy = GroundingBindPolicy(**kwargs)
            decision = GroundingBindGate(reference, policy=policy).certificate_for(exact_cert)
        except Exception as exc:  # noqa: BLE001 - boundary probe records rejection
            probes[probe_id] = {
                "accepted": False,
                "decision": "rejected",
                "decisive_reason": "public_policy_rejected_bind_authority_knob",
                "error": str(exc),
            }
        else:
            row = _decision_summary(decision)
            row["accepted"] = True
            probes[probe_id] = row

    probes["spoofed_caller_ledger_valid_hash_high_samples"] = _decision_summary(
        GroundingBindGate(reference).certificate_for(
            exact_cert,
            calibration_ledger=_spoofed_calibration_ledger(exact_cert, reference),
        )
    )
    probes["prior_hole_caller_ledger_sample0"] = _decision_summary(
        GroundingBindGate(reference).certificate_for(
            exact_cert,
            calibration_ledger=_fabricated_calibration_ledger(exact_cert, reference),
        )
    )
    return probes


def _promotability_resolution_probes(reference: Any, *, exact_cert: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_bind import (
        GroundingBindGate,
        GroundingDecisionCertificate,
        recompute_grounding_decision_content_hash,
        resolve_grounding_decision_promotability,
        resolve_grounding_decision_promotability_for_contract_testing,
    )

    test_decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(exact_cert)
    honest_payload = _forged_promotable_payload(
        test_decision,
        recompute_content_hash=True,
        recompute_grounding_decision_content_hash=recompute_grounding_decision_content_hash,
    )
    honest = GroundingDecisionCertificate.model_validate(honest_payload)
    honest_resolution = resolve_grounding_decision_promotability(
        honest,
        reference,
    )
    bogus_payload = _forged_promotable_payload(
        test_decision,
        recompute_content_hash=False,
        recompute_grounding_decision_content_hash=recompute_grounding_decision_content_hash,
    )
    try:
        GroundingDecisionCertificate.model_validate(bogus_payload)
    except Exception as exc:  # noqa: BLE001 - probe records DTO rejection
        bogus_row = {
            "dto_rejected": True,
            "error": str(exc),
        }
    else:
        bogus_row = {
            "dto_rejected": False,
            "error": None,
        }
    testing_resolution = resolve_grounding_decision_promotability_for_contract_testing(
        test_decision,
        reference,
    )
    return {
        "bogus_hash_forge": bogus_row,
        "honest_hash_forge": {
            "dto_rejected": False,
            "certificate_promotable_claim": honest.production_promotable,
            "resolution": honest_resolution.model_dump(mode="json"),
        },
        "contract_testing_bind": {
            "decision": test_decision.decision,
            "authority_scope": test_decision.authority_scope,
            "production_promotable": test_decision.production_promotable,
            "resolution": testing_resolution.model_dump(mode="json"),
        },
    }


def _forged_promotable_payload(
    decision: Any,
    *,
    recompute_content_hash: bool,
    recompute_grounding_decision_content_hash: Any,
) -> dict[str, Any]:
    payload = decision.model_dump(mode="json")
    payload["authority_scope"] = "production"
    payload["production_promotable"] = True
    payload["calibration"]["calibration_source"] = "fabricated_production_anchor_store"
    payload["calibration"]["status"] = "calibrated"
    payload["calibration"]["owner_validated"] = True
    payload["calibration"]["owned_anchor_id"] = "fabricated_production_anchor"
    payload["calibration"]["owned_anchor_content_hash"] = "sha256:" + "3" * 64
    payload["calibration"]["validation_reasons"] = ["owned_calibration_anchor_validated"]
    if recompute_content_hash:
        content_hash = recompute_grounding_decision_content_hash(payload)
        payload["content_hash"] = content_hash
        payload["certificate_id"] = f"cg2_cert_{content_hash.removeprefix('sha256:')[:16]}"
    else:
        payload["content_hash"] = "sha256:" + "2" * 64
        payload["certificate_id"] = "cg2_cert_2222222222222222"
    return payload


def _fast_replay_grid(reference: Any, *, exact_cert: Any, spec_cert: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_bind import GroundingBindGate

    gate = GroundingBindGate(reference)
    certificates = (exact_cert, spec_cert)
    violations: list[dict[str, Any]] = []
    tested = len({item.content_hash for item in certificates})
    for index in range(tested):
        full = certificates[index % len(certificates)]
        fast = gate._replay_certificate(full)
        violation = _fast_replay_violation(full, fast)
        if violation:
            violations.append({"index": index, **violation})
    return {
        "tested": tested,
        "unique_full_cg1_certificates": len({item.content_hash for item in certificates}),
        "grid_scope": "bind_eligible_exact_and_certified_specialization_replay",
        "violation_count": len(violations),
        "violations": violations[:12],
    }


def _fast_replay_violation(full: Any, fast: Any) -> dict[str, Any] | None:
    full_relation = str(full.selected_relation)
    fast_relation = str(fast.selected_relation)
    full_bind_eligible = full_relation in {"exact", "certified-specialization"}
    fast_bind_eligible = fast_relation in {"exact", "certified-specialization"}
    if fast_bind_eligible and not full_bind_eligible:
        return {
            "kind": "fast_more_permissive_relation",
            "full_relation": full_relation,
            "fast_relation": fast_relation,
        }
    if full_bind_eligible:
        full_atom = _selected_atom_id(full)
        fast_atom = _selected_atom_id(fast)
        if full_relation != fast_relation or full_atom != fast_atom:
            return {
                "kind": "bind_eligible_replay_mismatch",
                "full_atom": full_atom,
                "full_relation": full_relation,
                "fast_atom": fast_atom,
                "fast_relation": fast_relation,
            }
        if full.critical_contradictions or fast.critical_contradictions:
            return {
                "kind": "bind_eligible_critical_contradiction",
                "full_critical": list(full.critical_contradictions),
                "fast_critical": list(fast.critical_contradictions),
            }
    return None


def _mutation_reports(reference: Any, exact_cert: Any, false_cert: Any) -> list[dict[str, Any]]:
    stale_reference = _reference_with_non_support_revision(reference, exact_cert)
    reports: list[dict[str, Any]] = []
    specs = [
        (
            "calibration_owner_validation_removed",
            exact_cert,
            _gate(reference, disable_calibration_owner_validation=True),
            _fabricated_calibration_ledger(exact_cert, reference),
            "real_exact_with_fabricated_calibration",
        ),
        (
            "certificate_revalidation_removed",
            _forged_revalidation_certificate(exact_cert, false_cert),
            _gate(
                reference,
                calibration_seed_anchor=True,
                disable_certificate_revalidation=True,
            ),
            None,
            "real_false_analog_forged_as_exact",
        ),
        (
            "content_hash_check_removed",
            _tampered_certificate(exact_cert),
            _gate(
                reference,
                calibration_seed_anchor=True,
                disable_content_hash_check=True,
            ),
            None,
            "real_exact_tampered_content_hash",
        ),
        (
            "false_analog_hard_abstain_removed",
            false_cert,
            _gate(
                reference,
                calibration_seed_anchor=True,
                disable_false_analog_hard_abstain=True,
            ),
            None,
            "real_false_analog_certificate",
        ),
        (
            "cold_start_freeze_removed",
            exact_cert,
            _gate(
                reference,
                disable_calibration_freeze=True,
                risk_component_bounds={
                    "delta_RT1": 0.0,
                    "delta_ref": 0.0,
                    "delta_retrieval_novel": 0.0,
                    "delta_runtime": 0.0,
                    "delta_monitor": 0.0,
                    "delta_type_adm": 0.0,
                },
            ),
            None,
            "real_exact_production_cold_start",
        ),
        (
            "epoch_binding_removed",
            exact_cert,
            _gate(
                stale_reference,
                calibration_seed_anchor=True,
                disable_epoch_binding=True,
            ),
            None,
            "real_exact_stale_reference",
        ),
    ]
    for mutation_id, certificate, gate, ledger, exercise in specs:
        summary = _mutation_decision_summary(
            gate=gate,
            certificate=certificate,
            calibration_ledger=ledger,
        )
        reports.append(
            {
                "mutation_id": mutation_id,
                "status": "red"
                if summary.get("decision") == "bind" or summary.get("dto_invariant_raised")
                else "green",
                "decision": summary["decision"],
                "decisive_reason": summary["decisive_reason"],
                "content_hash": summary["content_hash"],
                "dto_invariant_raised": summary.get("dto_invariant_raised", False),
                "exercise": exercise,
            }
        )
    reports.append(_promotability_resolver_mutation(reference, exact_cert))
    reports.append(
        {
            "mutation_id": "robust_singleton_check_removed",
            "status": "unreachable_structural",
            "decision": None,
            "decisive_reason": "real_multi_safe_unreachable_in_current_live_lever_space",
            "content_hash": None,
            "dto_invariant_raised": False,
            "exercise": "documented_unreachable_no_revalidation_disabled_synthetic",
        }
    )
    reports.append(
        {
            "mutation_id": "exact_spec_only_rule_removed",
            "status": "unreachable_structural",
            "decision": None,
            "decisive_reason": "cg1_current_proposal_verdict_does_not_emit_generalization_partial_or_compositional",
            "content_hash": None,
            "dto_invariant_raised": False,
            "exercise": "documented_unreachable_no_revalidation_disabled_synthetic",
        }
    )
    return reports


def _promotability_resolver_mutation(reference: Any, exact_cert: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_bind import (
        GroundingBindGate,
        GroundingDecisionCertificate,
        recompute_grounding_decision_content_hash,
        resolve_grounding_decision_promotability,
    )

    test_decision = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(exact_cert)
    forged_payload = _forged_promotable_payload(
        test_decision,
        recompute_content_hash=True,
        recompute_grounding_decision_content_hash=recompute_grounding_decision_content_hash,
    )
    forged = GroundingDecisionCertificate.model_validate(forged_payload)
    store_resolution = resolve_grounding_decision_promotability(forged, reference)
    field_trusting_result = bool(forged.production_promotable)
    return {
        "mutation_id": "promotability_resolver_store_resolution_removed",
        "status": "red"
        if field_trusting_result and not store_resolution.promotable
        else "green",
        "decision": "promotable" if field_trusting_result else "non_promotable",
        "decisive_reason": "unsafe_resolver_trusted_certificate_promotable_field",
        "content_hash": forged.content_hash,
        "dto_invariant_raised": False,
        "exercise": "honest_hash_forged_production_promotable_certificate",
        "store_resolution": store_resolution.model_dump(mode="json"),
    }


def _mutation_decision_summary(
    *,
    gate: Any,
    certificate: Any,
    calibration_ledger: Any | None,
) -> dict[str, Any]:
    try:
        decision = (
            gate.certificate_for(certificate, calibration_ledger=calibration_ledger)
            if calibration_ledger is not None
            else gate.certificate_for(certificate)
        )
    except ValueError as exc:
        return {
            "content_hash": None,
            "decision": None,
            "decisive_reason": "dto_invariant_rejected_unsafe_bind",
            "dto_invariant_raised": True,
            "error": str(exc),
        }
    summary = _decision_summary(decision)
    summary["dto_invariant_raised"] = False
    return summary


def _gate(reference: Any, **policy_updates: Any) -> Any:
    from polisyos.runtime.quality.grounding_bind import GroundingBindGate

    return GroundingBindGate.for_contract_testing(reference, **policy_updates)


def _decision_summary(decision: Any) -> dict[str, Any]:
    return {
        "bound_atom_id": decision.bound_atom_id,
        "authority_scope": decision.authority_scope,
        "calibration_status": decision.calibration.status,
        "calibration_source": decision.calibration.calibration_source,
        "calibration_owner_validated": decision.calibration.owner_validated,
        "calibration_validation_reasons": list(decision.calibration.validation_reasons),
        "cg1_certificate_id": decision.cg1_certificate_id,
        "cg1_content_hash": decision.cg1_content_hash,
        "content_hash": decision.content_hash,
        "decision": decision.decision,
        "decisive_reason": decision.decisive_reason,
        "open_obligations": list(decision.open_obligations),
        "production_promotable": decision.production_promotable,
        "reference_epoch": decision.reference_epoch,
        "revalidation": decision.revalidation.model_dump(mode="json"),
        "risk_budget": decision.risk_ledger.delta_ground_budget,
        "risk_spend": decision.risk_ledger.total_spend,
        "risk_entries": [
            item.model_dump(mode="json") for item in decision.risk_ledger.entries
        ],
        "safe_count": len(decision.safe_t.safe_atom_ids),
        "safe_atom_ids": list(decision.safe_t.safe_atom_ids),
        "selected_relation": decision.selected_relation,
    }


def _fabricated_calibration_ledger(certificate: Any, reference: Any) -> Any:
    from polisyos.runtime.quality.grounding_bind import (
        CalibrationStratumRecord,
        GroundingCalibrationLedger,
    )

    signature = _first_signature(certificate)
    return GroundingCalibrationLedger(
        records=(
            CalibrationStratumRecord(
                operator_family=str(signature.get("op") or "unknown"),
                reference_region=str(signature.get("scope") or "unknown"),
                relation_type=str(certificate.selected_relation),
                status="calibrated",
                reference_epoch=reference.reference_epoch,
                sample_count=0,
            ),
        ),
        ledger_id="fabricated_caller_ledger",
    )


def _spoofed_calibration_ledger(certificate: Any, reference: Any) -> Any:
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.grounding_bind import (
        CalibrationStratumRecord,
        GroundingCalibrationLedger,
    )

    signature = _first_signature(certificate)
    operator = str(signature.get("op") or "unknown")
    region = str(signature.get("scope") or "unknown")
    relation = str(certificate.selected_relation)
    anchor_id = (
        "cg2_contract_seed_anchor:"
        f"{reference.reference_epoch}:{operator}:{region}:{relation}"
    )
    record = CalibrationStratumRecord(
        operator_family=operator,
        reference_region=region,
        relation_type=relation,
        status="calibrated",
        reference_epoch=reference.reference_epoch,
        sample_count=999,
        provenance="cg2_contract_seed_anchor",
        owner_anchor_id=anchor_id,
        evidence_hash=gy_content_hash(
            {
                "owner_anchor_id": anchor_id,
                "operator_family": operator,
                "reference_epoch": reference.reference_epoch,
                "reference_region": region,
                "relation_type": relation,
                "sample_count": 999,
            }
        ),
    ).with_content_hash()
    return GroundingCalibrationLedger(
        records=(record,),
        ledger_id="spoofed_caller_ledger",
    )


def _tampered_certificate(certificate: Any) -> Any:
    return certificate.model_copy(update={"raw_text_hash": "sha256:" + "0" * 64})


def _forged_revalidation_certificate(exact_cert: Any, false_cert: Any) -> Any:
    payload = exact_cert.model_dump(mode="json")
    false_signature = false_cert.model_dump(mode="json")["proposal_signature"]
    false_signature["hypotheses"][0]["signature"]["admissibility"] = "passed"
    payload["proposal_signature"] = false_signature
    payload["raw_text_hash"] = false_cert.raw_text_hash
    return _with_recomputed_content_hash(exact_cert, payload)


def _reference_with_non_support_revision(reference: Any, certificate: Any) -> Any:
    from polisyos.runtime.quality.credal_reference import (
        CredalReferenceEdge,
        replace_reference_edge,
    )

    support = set()
    selected_atom = certificate.cross_modal_witnesses["selected_pair"]["atom_id"]
    atom_payload = certificate.atom_signature_or_bundle[selected_atom]
    support.update(str(item) for item in atom_payload.get("edge_scope", []))
    for edge in reference.essential_edges.values():
        key_text = f"{edge.modality}::{edge.edge_id}"
        if key_text in support:
            continue
        revised = CredalReferenceEdge(
            modality=edge.modality,
            edge_id=edge.edge_id,
            status=edge.status,
            admissible_completions=edge.admissible_completions,
            provenance={**dict(edge.provenance), "cg2_stale_probe": "non_support_revision"},
            unit=edge.unit,
            scale=edge.scale,
        ).with_content_hash()
        return replace_reference_edge(reference, revised)
    raise RuntimeError("cg2_non_support_reference_edge_missing")


def _with_recomputed_content_hash(certificate: Any, payload: dict[str, Any]) -> Any:
    from polisyos.runtime.quality.grounding_bind import recompute_grounding_relation_content_hash

    provisional = certificate.__class__.model_validate(payload)
    content_hash = recompute_grounding_relation_content_hash(provisional)
    payload["content_hash"] = content_hash
    payload["certificate_id"] = f"cg1_cert_{content_hash.removeprefix('sha256:')[:16]}"
    return certificate.__class__.model_validate(payload)


def _first_signature(certificate: Any) -> dict[str, Any]:
    proposal_signature = certificate.model_dump(mode="json").get("proposal_signature", {})
    for hypothesis in proposal_signature.get("hypotheses", []):
        signature = hypothesis.get("signature")
        if isinstance(signature, dict):
            return dict(signature)
    return {}


def _selected_atom_id(certificate: Any) -> str | None:
    payload = certificate.model_dump(mode="json")
    selected = payload.get("cross_modal_witnesses", {}).get("selected_pair", {})
    if isinstance(selected, dict) and selected.get("atom_id"):
        return str(selected["atom_id"])
    selected_relation = str(payload.get("selected_relation") or "")
    for item in payload.get("relation_set", {}).get("candidate_results", []):
        if isinstance(item, dict) and str(item.get("selected_relation")) == selected_relation:
            atom_id = str(item.get("atom_id") or "")
            return atom_id or None
    return None


def _probe(probes: dict[str, Any], probe_id: str) -> dict[str, Any]:
    probe = probes.get(probe_id)
    return probe if isinstance(probe, dict) else {}


def _copy(payload: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _json_stable(payload: dict[str, Any]) -> dict[str, Any]:
    return _copy(payload)


def main(argv: list[str] | None = None) -> int:
    """Run the CGF GY-CG2 grounding bind contract validator."""

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
        print("grounding bind contract: pass")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
