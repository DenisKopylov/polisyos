#!/usr/bin/env python3
"""Validate the CGF GY-CG3 free-grow admission contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

OUTPUT_PATH = "architecture/policy_design_case/grounding_admission_contract.json"
SCHEMA_VERSION = "policyos.policy_design_case.grounding_admission_contract.v1"
EXPECTED_MUTATIONS = {
    "denotation_comparison_removed",
    "direct_mechanism_witness_removed",
    "do_path_actuatability_resolution_removed",
    "full_universe_denotation_removed",
    "keyword_proxy_reject_restored",
    "mechanism_witness_resolution_removed",
    "novel_irreducible_removed",
    "positive_writability_removed",
    "stable_unique_removed",
    "reject_only_on_proven_removed",
    "registry_patch_reresolution_removed",
    "substrate_registry_authority_restored",
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
    """Recompute the CG3 contract from live CG0/CG1/CG2 owner paths."""

    _configure_validation_jax_platform()
    from polisyos.runtime.quality.credal_reference import build_credal_reference
    from polisyos.runtime.quality.grounding_admission import (
        GROUNDING_ADMISSION_SCHEMA_VERSION,
        GroundingAdmissionEngine,
        apply_grounding_admission_registry_patch,
    )
    from polisyos.runtime.quality.substrate_registry import (
        build_substrate_registry_from_existing_catalogs,
    )

    repo_root = (repo_root or _default_repo_root()).resolve()
    reference = build_credal_reference(repo_root)
    substrate_registry = build_substrate_registry_from_existing_catalogs(repo_root)

    admit_reference = _with_mechanism_edge(
        reference,
        source="cells.distress_score",
        outcome="cells.output",
        edge_id="cg3_free_grow_distress_output",
    )
    cg1_admit, cg2_admit = _cg2_pair(admit_reference, _free_grow_probe())
    admit = GroundingAdmissionEngine(admit_reference).decide(
        cg2_admit,
        cg1_certificate=cg1_admit,
    )

    second_admit_reference = _with_mechanism_edge(
        reference,
        source="global.tax_rate",
        outcome="government.balance",
        edge_id="cg3_free_grow_tax_rate_balance_increase",
    )
    cg1_second_admit, cg2_second_admit = _cg2_pair(
        second_admit_reference,
        _tax_surcharge_probe(),
    )
    second_admit = GroundingAdmissionEngine(second_admit_reference).decide(
        cg2_second_admit,
        cg1_certificate=cg1_second_admit,
    )

    missing_reference = reference
    cg1_missing, cg2_missing = _cg2_pair(missing_reference, _free_grow_probe())
    acquire = GroundingAdmissionEngine(missing_reference).decide(
        cg2_missing,
        cg1_certificate=cg1_missing,
    )

    hallucination_probes = {}
    for probe_id, probe in {
        "outcome_wish": _outcome_wish_probe(),
        "proxy_manipulation": _proxy_manipulation_probe(),
        "impossible_type": _impossible_type_probe(),
    }.items():
        cg1, cg2 = _cg2_pair(reference, probe)
        probe_reference = reference
        if probe_id == "proxy_manipulation":
            probe_reference = _with_mechanism_edge(
                reference,
                source="agents.reported_income",
                outcome="household_cells.disposable_income",
                edge_id="cg3_proxy_reported_income_income",
            )
            cg1, cg2 = _cg2_pair(probe_reference, probe)
        certificate = GroundingAdmissionEngine(probe_reference).decide(
            cg2,
            cg1_certificate=cg1,
        )
        hallucination_probes[probe_id] = {
            **_admission_summary(certificate),
            "cg2_decision": cg2.decision,
            "cg2_reason": cg2.decisive_reason,
        }

    paraphrase_reference = _with_mechanism_edge(
        reference,
        source="global.tax_rate",
        outcome="government.balance",
        edge_id="cg3_tax_rate_balance_mechanism",
    )
    cg1_paraphrase, cg2_paraphrase = _cg2_pair(paraphrase_reference, _paraphrase_probe())
    non_new = GroundingAdmissionEngine(paraphrase_reference).decide(
        cg2_paraphrase,
        cg1_certificate=cg1_paraphrase,
    )

    fabricated = _fabricated_mechanism_probe()
    cg1_fake, cg2_fake = _cg2_pair(reference, fabricated)
    fail_closed = GroundingAdmissionEngine(reference).decide(
        cg2_fake,
        cg1_certificate=cg1_fake,
    )

    self_loop_reference = _with_mechanism_edge(
        reference,
        source="household_cells.disposable_income",
        outcome="household_cells.disposable_income",
        edge_id="cg3_self_loop_income_goal",
    )
    cg1_self_loop, cg2_self_loop = _cg2_pair(
        self_loop_reference,
        _self_loop_outcome_wish_probe(),
    )
    self_loop = GroundingAdmissionEngine(self_loop_reference).decide(
        cg2_self_loop,
        cg1_certificate=cg1_self_loop,
    )

    proxy_slot_reference = _with_mechanism_edge(
        reference,
        source="agents.reported_income",
        outcome="household_cells.disposable_income",
        edge_id="cg3_proxy_slot_reported_income",
    )
    cg1_proxy_slot, cg2_proxy_slot = _cg2_pair(
        proxy_slot_reference,
        _reported_income_proxy_probe(),
    )
    proxy_slot = GroundingAdmissionEngine(proxy_slot_reference).decide(
        cg2_proxy_slot,
        cg1_certificate=cg1_proxy_slot,
    )

    low_trust_reference = _with_mechanism_edge(
        reference,
        source="cells.distress_score",
        outcome="cells.output",
        edge_id="cg3_low_trust_distress_output",
        trust_score=0.2,
        confidence=0.2,
    )
    cg1_low_trust, cg2_low_trust = _cg2_pair(low_trust_reference, _free_grow_probe())
    low_trust_acquire = GroundingAdmissionEngine(low_trust_reference).decide(
        cg2_low_trust,
        cg1_certificate=cg1_low_trust,
    )
    spoof_boundary = _spoofed_registry_boundary(
        low_trust_reference,
        cg2_low_trust,
        cg1_low_trust,
    )

    cg1_proxy_named, cg2_proxy_named = _cg2_pair(reference, _proxy_named_real_unproven_probe())
    proxy_named_boundary = GroundingAdmissionEngine(reference).decide(
        cg2_proxy_named,
        cg1_certificate=cg1_proxy_named,
    )

    two_hop_reference = _with_mechanism_edges(
        reference,
        (
            {
                "source": "cells.distress_score",
                "outcome": "audit.bridge",
                "edge_id": "cg3_two_hop_distress_bridge",
            },
            {
                "source": "audit.bridge",
                "outcome": "cells.output",
                "edge_id": "cg3_two_hop_bridge_output",
            },
        ),
    )
    cg1_two_hop, cg2_two_hop = _cg2_pair(two_hop_reference, _free_grow_probe())
    two_hop = GroundingAdmissionEngine(two_hop_reference).decide(
        cg2_two_hop,
        cg1_certificate=cg1_two_hop,
    )

    three_hop_reference = _with_mechanism_edges(
        reference,
        (
            {
                "source": "cells.distress_score",
                "outcome": "audit.bridge_one",
                "edge_id": "cg3_three_hop_distress_bridge_one",
            },
            {
                "source": "audit.bridge_one",
                "outcome": "audit.bridge_two",
                "edge_id": "cg3_three_hop_bridge_one_two",
            },
            {
                "source": "audit.bridge_two",
                "outcome": "cells.output",
                "edge_id": "cg3_three_hop_bridge_two_output",
            },
        ),
    )
    cg1_three_hop, cg2_three_hop = _cg2_pair(three_hop_reference, _free_grow_probe())
    three_hop = GroundingAdmissionEngine(three_hop_reference).decide(
        cg2_three_hop,
        cg1_certificate=cg1_three_hop,
    )

    low_trust_hop_reference = _with_mechanism_edges(
        reference,
        (
            {
                "source": "cells.distress_score",
                "outcome": "audit.low_trust_bridge",
                "edge_id": "cg3_low_trust_hop_distress_bridge",
                "trust_score": 0.95,
                "confidence": 0.95,
            },
            {
                "source": "audit.low_trust_bridge",
                "outcome": "cells.output",
                "edge_id": "cg3_low_trust_hop_bridge_output",
                "trust_score": 0.2,
                "confidence": 0.2,
            },
        ),
    )
    cg1_low_trust_hop, cg2_low_trust_hop = _cg2_pair(
        low_trust_hop_reference,
        _free_grow_probe(),
    )
    low_trust_hop = GroundingAdmissionEngine(low_trust_hop_reference).decide(
        cg2_low_trust_hop,
        cg1_certificate=cg1_low_trust_hop,
    )

    compatibility_reference = _with_mechanism_edge(
        reference,
        source="cells.output",
        outcome="cells.output",
        edge_id="cg3_compat_cells_output_self_loop",
    )
    cg1_compat, cg2_compat = _cg2_pair(
        compatibility_reference,
        _compatibility_derived_alias_probe(),
    )
    compatibility_alias = GroundingAdmissionEngine(compatibility_reference).decide(
        cg2_compat,
        cg1_certificate=cg1_compat,
    )

    outcome_map_reference = _with_mechanism_edge(
        reference,
        source="household_cells.disposable_income",
        outcome="government.balance",
        edge_id="cg3_outcome_slot_income_balance",
    )
    cg1_outcome_map, cg2_outcome_map = _cg2_pair(
        outcome_map_reference,
        _outcome_like_policy_map_probe(),
    )
    outcome_map = GroundingAdmissionEngine(outcome_map_reference).decide(
        cg2_outcome_map,
        cg1_certificate=cg1_outcome_map,
    )

    actuatability_denominator = _actuatability_denominator(reference)

    apply_resolution = apply_grounding_admission_registry_patch(
        admit,
        cg2_admit,
        admit_reference,
        cg1_certificate=cg1_admit,
    )
    deterministic_a = GroundingAdmissionEngine(admit_reference).decide(
        cg2_admit,
        cg1_certificate=cg1_admit,
    )
    deterministic_b = GroundingAdmissionEngine(admit_reference).decide(
        cg2_admit,
        cg1_certificate=cg1_admit,
    )

    real_n4 = _real_n4_probe(repo_root, reference)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "gy_lifecycle_marker": SCHEMA_VERSION,
        "contract_id": "policyos.runtime.grounding_admission_rt3",
        "runtime_schema_version": GROUNDING_ADMISSION_SCHEMA_VERSION,
        "owner": "polisyos.runtime.quality.grounding_admission",
        "source_modules": [
            "src/polisyos/runtime/quality/grounding_admission.py",
            "src/polisyos/runtime/quality/grounding_bind.py",
            "src/polisyos/runtime/quality/grounding_relation.py",
            "src/polisyos/runtime/quality/credal_reference.py",
            "src/polisyos/runtime/quality/substrate_registry.py",
            "tools/quality/validation/check_grounding_admission_contract.py",
        ],
        "reuse_existing_owners": [
            "CG2 GroundingDecisionCertificate novel_candidate handoff",
            "CG1 GroundingRelationCertificate as content-bound proposal replay carrier",
            "CG0 CredalReference built from real L2/L3/L6/WMR owners",
            "WMR_WORLD_SLOT and WMR_POLICY_SLOT_MAP edges for world bindability",
            "L2 SKG causal evidence edges for mechanism witness resolution",
            "CG0/L2 owner-lifted L5 trust signals on mechanism evidence edges for data_trust",
            "GY-S0/L6 intervention substrate named as registry patch owner; live write remains shadow",
        ],
        "no_parallel_reference_or_registry": True,
        "reference": {
            "reference_epoch": reference.reference_epoch,
            "reference_hash": reference.reference_hash,
            "edge_count": len(reference.essential_edges),
            "component_versions": dict(sorted(reference.component_versions.items())),
            "substrate_registry_id": substrate_registry.substrate_version_id,
            "substrate_registry_hash": substrate_registry.content_hash,
        },
        "probes": {
            "admit_real_novel_data_only_free_grow": _admission_summary(admit),
            "admit_second_generic_data_only_free_grow": _admission_summary(second_admit),
            "acquire_missing_mechanism_unknown_never_reject": _admission_summary(acquire),
            "reject_hallucination_subtypes": hallucination_probes,
            "non_new_paraphrase_no_registry_patch": _admission_summary(non_new),
            "fabricated_mechanism_proof_fail_closed": _admission_summary(fail_closed),
            "outcome_wish_with_crafted_self_loop_edge": _admission_summary(self_loop),
            "proxy_slot_with_crafted_edge": _admission_summary(proxy_slot),
            "spoofed_substrate_registry_production_boundary": {
                **_admission_summary(low_trust_acquire),
                **spoof_boundary,
            },
            "proxy_named_real_unproven_boundary": _admission_summary(proxy_named_boundary),
            "two_hop_unrelated_chain": _admission_summary(two_hop),
            "three_hop_unrelated_chain": _admission_summary(three_hop),
            "low_trust_hop_chain": _admission_summary(low_trust_hop),
            "compatibility_derived_alias_no_patch": _admission_summary(compatibility_alias),
            "outcome_like_map_mentioned_slot": _admission_summary(outcome_map),
            "live_actuatability_denominator": actuatability_denominator,
            "registry_patch_application_reresolved": {
                "applied": apply_resolution.applied,
                "reason": apply_resolution.reason,
                "patch_id": apply_resolution.certificate_patch_id,
            },
            "contract_testing_scope": _contract_testing_scope(
                admit_reference,
                substrate_registry,
                cg1_admit,
                cg2_admit,
            ),
            "deterministic_admission": {
                "first_content_hash": deterministic_a.content_hash,
                "second_content_hash": deterministic_b.content_hash,
                "same_content_hash": deterministic_a.content_hash == deterministic_b.content_hash,
            },
            "real_n4_recorded_handoff": real_n4,
        },
        "production_api_boundary_probes": _production_api_boundary_probes(),
        "behavioral_mutations": _mutation_reports(
            reference=reference,
            admit_reference=admit_reference,
            paraphrase_reference=paraphrase_reference,
            low_trust_reference=low_trust_reference,
            two_hop_reference=two_hop_reference,
            low_trust_hop_reference=low_trust_hop_reference,
            compatibility_reference=compatibility_reference,
            outcome_map_reference=outcome_map_reference,
            proxy_named_reference=reference,
            self_loop_reference=self_loop_reference,
            substrate_registry=substrate_registry,
        ),
        "capability_reality": {
            "typed_contract_artifact": (
                "GroundingAdmissionCertificate + StableUniqueResolution + "
                "GroundingLeverRegistryPatch + DeltaAdmissionLedger"
            ),
            "producer": "GroundingAdmissionEngine.decide",
            "persisted_artifact_event": OUTPUT_PATH,
            "orchestration_bridge": (
                "CG3 consumes CG2 novel handoff plus content-bound CG1 proposal "
                "certificate and live CG0/L5 owners"
            ),
            "consumer": "GY-S0 registry patch resolver in shadow scope; future CG1 can replay ledger",
            "verification": "this recomputing validator plus unit probes and mutations",
            "surface": "generated Policy Design Case CG3 contract artifact",
            "semantic_test": (
                "admit/acquire/reject/non-new/fail-closed probes and mutation-red "
                "checks over live owner-built reference"
            ),
        },
        "pattern_pass": {
            "relevant_ids": [
                "P01",
                "P03",
                "P04",
                "P05",
                "P10",
                "P15",
                "P27",
                "P28",
                "P29",
                "P31",
                "P32",
                "P33",
            ],
            "target_correct_pattern": (
                "certificate-as-claim envelope; admission and patching re-resolve "
                "mechanism, WMR, L5 trust, StableUnique, and registry effects from owners"
            ),
            "missing_capability_labels": [],
            "acceptance_signal": "contract check plus corrupt-field check pass; mutations are red",
        },
    }
    return _json_stable(payload)


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a CG3 payload against behavioral properties."""

    issues = _core_issues(payload, require_mutations=True)
    return {"status": "pass" if not issues else "fail", "issues": issues}


def validate(repo_root: Path | None = None) -> dict[str, Any]:
    """Validate committed artifact drift and live CG3 behavior."""

    repo_root = (repo_root or _default_repo_root()).resolve()
    path = repo_root / OUTPUT_PATH
    live = build_live_payload(repo_root)
    issues = _core_issues(live, require_mutations=True)
    if not path.is_file():
        issues.append({"code": "grounding_admission_contract_missing", "path": OUTPUT_PATH})
        committed: dict[str, Any] | None = None
    else:
        try:
            committed = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            committed = None
            issues.append(
                {
                    "code": "grounding_admission_contract_invalid_json",
                    "path": OUTPUT_PATH,
                    "error": str(exc),
                }
            )
    if committed is not None and committed != live:
        issues.append({"code": "grounding_admission_contract_drift", "path": OUTPUT_PATH})
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
    """Write the live CG3 contract artifact."""

    path = repo_root / OUTPUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    live = payload or build_live_payload(repo_root)
    path.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def corrupt_field_drift_check(repo_root: Path | None = None) -> dict[str, Any]:
    """Prove corrupt decisive fields turn validation red."""

    live = build_live_payload(repo_root)
    corrupted = _copy(live)
    corrupted["probes"]["admit_real_novel_data_only_free_grow"]["decision"] = (
        "acquire_then_decide"
    )
    corrupted["probes"]["acquire_missing_mechanism_unknown_never_reject"]["decision"] = (
        "reject_hallucination"
    )
    corrupted["probes"]["reject_hallucination_subtypes"]["outcome_wish"][
        "decision"
    ] = "admit_new_lever"
    corrupted["probes"]["fabricated_mechanism_proof_fail_closed"][
        "decision"
    ] = "admit_new_lever"
    corrupted["probes"]["low_trust_hop_chain"]["data_trust_cap"] = 0.95
    corrupted["behavioral_mutations"][0]["status"] = "green"
    report = validate_payload(corrupted)
    return {
        "status": "pass" if report["status"] == "fail" else "fail",
        "issues": []
        if report["status"] == "fail"
        else [{"code": "grounding_admission_corrupt_field_not_detected"}],
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
        issues.append({"code": "grounding_admission_schema_mismatch"})
    if payload.get("no_parallel_reference_or_registry") is not True:
        issues.append({"code": "grounding_admission_parallel_reference_or_registry"})
    probes = payload.get("probes", {})
    issues.extend(
        _expect_decision(
            probes,
            "admit_real_novel_data_only_free_grow",
            "admit_new_lever",
            "all_obligations_closed",
        )
    )
    admit = _probe(probes, "admit_real_novel_data_only_free_grow")
    if admit.get("registry_patch_id") in {None, ""}:
        issues.append({"code": "grounding_admission_admit_patch_missing"})
    if admit.get("decision_front_created") is not False:
        issues.append({"code": "grounding_admission_created_decision_front"})
    if admit.get("delta_within_budget") is not True:
        issues.append({"code": "grounding_admission_delta_budget_exceeded"})
    issues.extend(
        _expect_decision(
            probes,
            "admit_second_generic_data_only_free_grow",
            "admit_new_lever",
            "all_obligations_closed",
        )
    )
    issues.extend(
        _expect_decision(
            probes,
            "acquire_missing_mechanism_unknown_never_reject",
            "acquire_then_decide",
            "mechanism_witness_missing",
        )
    )
    acquire = _probe(probes, "acquire_missing_mechanism_unknown_never_reject")
    if acquire.get("acquisition_blocker") != "mechanism_witness_required":
        issues.append({"code": "grounding_admission_acquire_blocker_wrong"})
    hallucinations = _probe(probes, "reject_hallucination_subtypes")
    for subtype in ("outcome_wish", "proxy_manipulation", "impossible_type"):
        row = _probe(hallucinations, subtype)
        if row.get("decision") != "reject_hallucination":
            issues.append({"code": "grounding_admission_hallucination_not_rejected", "subtype": subtype})
        if row.get("decisive_reason") != subtype:
            issues.append({"code": "grounding_admission_hallucination_reason_wrong", "subtype": subtype})
    issues.extend(
        _expect_decision(
            probes,
            "non_new_paraphrase_no_registry_patch",
            "non_new",
            "novel_irreducible_failed_existing_atom",
        )
    )
    if _probe(probes, "non_new_paraphrase_no_registry_patch").get("registry_patch_id"):
        issues.append({"code": "grounding_admission_non_new_patched_registry"})
    issues.extend(
        _expect_decision(
            probes,
            "outcome_wish_with_crafted_self_loop_edge",
            "reject_hallucination",
            "outcome_wish",
        )
    )
    if _probe(probes, "outcome_wish_with_crafted_self_loop_edge").get("mechanism_status") != "open":
        issues.append({"code": "grounding_admission_self_loop_counted_as_mechanism"})
    issues.extend(
        _expect_decision(
            probes,
            "proxy_slot_with_crafted_edge",
            "reject_hallucination",
            "proxy_manipulation",
        )
    )
    if _probe(probes, "proxy_slot_with_crafted_edge").get("mechanism_status") != "open":
        issues.append({"code": "grounding_admission_proxy_slot_counted_as_mechanism"})
    spoofed = _probe(probes, "spoofed_substrate_registry_production_boundary")
    if spoofed.get("decision") != "acquire_then_decide":
        issues.append({"code": "grounding_admission_spoofed_registry_changed_decision"})
    if spoofed.get("spoof_constructor_accepted") is not False:
        issues.append({"code": "grounding_admission_production_constructor_accepted_registry"})
    issues.extend(
        _expect_decision(
            probes,
            "proxy_named_real_unproven_boundary",
            "acquire_then_decide",
            "mechanism_witness_missing",
        )
    )
    for probe_id, path_length in {
        "two_hop_unrelated_chain": 2,
        "three_hop_unrelated_chain": 3,
    }.items():
        issues.extend(
            _expect_decision(
                probes,
                probe_id,
                "acquire_then_decide",
                "mechanism_composition_unverified",
            )
        )
        row = _probe(probes, probe_id)
        if row.get("registry_patch_id"):
            issues.append({"code": f"{probe_id}_patched_registry"})
        if row.get("mechanism_evidence", {}).get("path_length") != path_length:
            issues.append({"code": f"{probe_id}_path_length_wrong"})
        if row.get("acquisition_blocker") != "mechanism_composition_unverified":
            issues.append({"code": f"{probe_id}_blocker_wrong"})
    issues.extend(
        _expect_decision(
            probes,
            "low_trust_hop_chain",
            "acquire_then_decide",
            "mechanism_composition_unverified",
        )
    )
    low_trust_hop = _probe(probes, "low_trust_hop_chain")
    if low_trust_hop.get("data_trust_cap") != 0.2:
        issues.append(
            {
                "code": "grounding_admission_low_trust_hop_not_min_aggregated",
                "observed": low_trust_hop.get("data_trust_cap"),
            }
        )
    issues.extend(
        _expect_decision(
            probes,
            "compatibility_derived_alias_no_patch",
            "non_new",
            "novel_irreducible_failed_existing_atom",
        )
    )
    compat = _probe(probes, "compatibility_derived_alias_no_patch")
    if compat.get("registry_patch_id"):
        issues.append({"code": "grounding_admission_compatibility_alias_patched_registry"})
    compat_evidence = compat.get("novel_irreducible_evidence", {})
    if compat_evidence.get("existing_atom_match_kind") != "signature_only":
        issues.append({"code": "grounding_admission_compatibility_alias_not_signature_only"})
    if compat_evidence.get("operator_denotation_proof") != "unresolved":
        issues.append({"code": "grounding_admission_compatibility_alias_operator_proof_wrong"})
    outcome_map = _probe(probes, "outcome_like_map_mentioned_slot")
    if outcome_map.get("decision") == "admit_new_lever":
        issues.append({"code": "grounding_admission_map_mentioned_outcome_admitted"})
    if outcome_map.get("mechanism_evidence", {}).get("actuatability", {}).get("actuatable") is not False:
        issues.append({"code": "grounding_admission_map_mentioned_outcome_actuatable"})
    denominator = _probe(probes, "live_actuatability_denominator")
    expected_targets = {
        "government.balance": False,
        "household_cells.disposable_income": False,
        "agents.reported_income": False,
        "global.tax_rate": True,
        "cells.distress_score": True,
    }
    target_results = denominator.get("targets", {})
    for target, expected in expected_targets.items():
        if _probe(target_results, target).get("actuatable") is not expected:
            issues.append(
                {
                    "code": "grounding_admission_live_actuatability_target_wrong",
                    "target": target,
                    "expected": expected,
                    "observed": _probe(target_results, target).get("actuatable"),
                }
            )
    fail_closed = _probe(probes, "fabricated_mechanism_proof_fail_closed")
    if fail_closed.get("decision") == "admit_new_lever":
        issues.append({"code": "grounding_admission_fabricated_mechanism_admitted"})
    if fail_closed.get("mechanism_status") != "open":
        issues.append({"code": "grounding_admission_fabricated_mechanism_trusted"})
    patch_resolution = _probe(probes, "registry_patch_application_reresolved")
    if patch_resolution.get("applied") is not True:
        issues.append({"code": "grounding_admission_patch_not_reresolved"})
    testing_scope = _probe(probes, "contract_testing_scope")
    if (
        testing_scope.get("decision") != "admit_new_lever"
        or testing_scope.get("authority_scope") != "contract_testing"
        or testing_scope.get("production_promotable") is not False
    ):
        issues.append({"code": "grounding_admission_contract_testing_scope_wrong"})
    deterministic = _probe(probes, "deterministic_admission")
    if deterministic.get("same_content_hash") is not True:
        issues.append({"code": "grounding_admission_not_deterministic"})
    boundary = payload.get("production_api_boundary_probes", {})
    for probe_id, row in sorted(boundary.items()):
        if row.get("accepted") is not False:
            issues.append(
                {"code": "grounding_admission_public_policy_accepted_authority_knob", "probe": probe_id}
            )
    real_n4 = _probe(probes, "real_n4_recorded_handoff")
    if real_n4.get("cg2_decision") != "novel_candidate":
        issues.append({"code": "grounding_admission_real_n4_not_cg2_novel_candidate"})
    if real_n4.get("decision") not in {"admit_new_lever", "acquire_then_decide", "reject_hallucination", "non_new"}:
        issues.append({"code": "grounding_admission_real_n4_no_verdict"})
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
                    "code": "grounding_admission_required_mutation_missing",
                    "missing_mutations": missing,
                }
            )
        not_red = sorted(
            mutation_id
            for mutation_id in EXPECTED_MUTATIONS.intersection(mutations)
            if mutations[mutation_id] != "red"
        )
        if not_red:
            issues.append(
                {
                    "code": "grounding_admission_required_mutation_not_red",
                    "mutation_ids": not_red,
                }
            )
    return issues


def _with_mechanism_edge(
    reference: Any,
    *,
    source: str,
    outcome: str,
    edge_id: str,
    trust_score: float = 0.91,
    confidence: float = 0.93,
) -> Any:
    from polisyos.runtime.quality.credal_reference import (
        AdmissibleCompletion,
        CredalReferenceEdge,
        replace_reference_edge,
    )

    return replace_reference_edge(
        reference,
        CredalReferenceEdge(
            modality="L2_CAUSAL_CLAIM",
            edge_id=edge_id,
            status="confirmed",
            admissible_completions=(
                AdmissibleCompletion(
                    "fixed",
                    {"direction": "positive", "dst": outcome, "src": source},
                    "cg3_validator_data_only_mechanism",
                ),
            ),
            provenance={
                "owner": "L2",
                "source": "ac_causal_claims",
                "version": "cg3_validator_data_only_probe",
                "signals": {
                    "confidence": confidence,
                    "strong_design_evidence": True,
                    "trust_score": trust_score,
                },
            },
        ).with_content_hash(),
    )


def _with_mechanism_edges(reference: Any, edges: tuple[dict[str, Any], ...]) -> Any:
    for edge in edges:
        reference = _with_mechanism_edge(reference, **edge)
    return reference


def _with_positive_policy_input_slot(reference: Any, target: str) -> Any:
    from polisyos.runtime.quality.credal_reference import (
        AdmissibleCompletion,
        CredalReferenceEdge,
        replace_reference_edge,
    )

    return replace_reference_edge(
        reference,
        CredalReferenceEdge(
            modality="WMR_WORLD_SLOT",
            edge_id=target,
            status="confirmed",
            admissible_completions=(
                AdmissibleCompletion(
                    "fixed",
                    {
                        "slot_id": target,
                        "slot_role": "policy_input",
                        "temporal_granularity": "stock",
                        "world_slot": target,
                    },
                    "cg3_validator_positive_policy_input",
                ),
            ),
            provenance={
                "owner": "WMR",
                "source": "cg3_validator_owner_shaped_wmr_slot",
                "signals": {
                    "slot_role": "policy_input",
                    "temporal_granularity": "stock",
                },
            },
        ).with_content_hash(),
    )


def _with_policy_slot_world_slot_map(reference: Any, target: str) -> Any:
    from polisyos.runtime.quality.credal_reference import (
        AdmissibleCompletion,
        CredalReferenceEdge,
        replace_reference_edge,
    )

    return replace_reference_edge(
        reference,
        CredalReferenceEdge(
            modality="WMR_POLICY_SLOT_MAP",
            edge_id=f"cg3_validator_policy_slot:{target}",
            status="confirmed",
            admissible_completions=(
                AdmissibleCompletion(
                    "fixed",
                    {
                        "policy_slot": f"cg3_validator_policy_slot:{target}",
                        "world_slot": target,
                    },
                    "cg3_validator_policy_slot_map",
                ),
            ),
            provenance={
                "owner": "WMR",
                "source": "cg3_validator_owner_shaped_policy_slot_map",
            },
        ).with_content_hash(),
    )


def _with_contested_completion(reference: Any) -> Any:
    from polisyos.runtime.quality.credal_reference import (
        AdmissibleCompletion,
        CredalReferenceEdge,
        replace_reference_edge,
    )

    return replace_reference_edge(
        reference,
        CredalReferenceEdge(
            modality="L2_CONTESTED_EDGE",
            edge_id="cg3_contested_transfer_intensity_income",
            status="contested",
            admissible_completions=(
                AdmissibleCompletion(
                    "alternative",
                    {
                        "direction": "positive",
                        "dst": "cells.output",
                        "src": "cells.distress_score",
                    },
                    "cg3_validator_contested_completion",
                ),
                AdmissibleCompletion(
                    "may_not_exist",
                    {
                        "direction": "positive",
                        "dst": "cells.output",
                        "src": "cells.distress_score",
                    },
                    "cg3_validator_contested_completion",
                ),
            ),
            provenance={
                "owner": "L2",
                "source": "ac_skg_contested_edges",
                "version": "cg3_validator_data_only_probe",
            },
        ).with_content_hash(),
    )


def _cg2_pair(reference: Any, probe: dict[str, Any]) -> tuple[Any, Any]:
    from polisyos.runtime.quality.grounding_bind import GroundingBindGate
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    engine = GroundingRelationEngine(reference)
    engine._fts_index = _BoundedReferenceIndex(reference)
    proposal_id = str(
        probe.get("proposal_id")
        or probe.get("candidate_id")
        or probe.get("id")
        or probe.get("atom", {}).get("atom_id")
        or "cg3-recorded-proposal"
    )
    cg1 = engine.certificate_for(
        probe,
        proposal_id=proposal_id,
    )
    cg2 = GroundingBindGate.for_contract_testing(
        reference,
        calibration_seed_anchor=True,
    ).certificate_for(cg1)
    return cg1, cg2


def _spoofed_registry_boundary(
    reference: Any,
    cg2: Any,
    cg1: Any,
) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_admission import GroundingAdmissionEngine

    try:
        GroundingAdmissionEngine(reference, substrate_registry=_spoofed_registry())  # type: ignore[call-arg]
    except TypeError as exc:
        constructor = {
            "spoof_constructor_accepted": False,
            "spoof_constructor_error": str(exc).split("\n", 1)[0],
        }
    else:
        constructor = {"spoof_constructor_accepted": True}
    mutated = GroundingAdmissionEngine.for_contract_testing(
        reference,
        substrate_registry=_spoofed_registry(),
        allow_substrate_registry_authority=True,
    ).decide(cg2, cg1_certificate=cg1)
    return {
        **constructor,
        "spoof_mutation_decision": mutated.decision,
        "spoof_mutation_reason": mutated.decisive_reason,
    }


class _BoundedReferenceIndex:
    """Bound CG1 validator replay without rebuilding the full DuckDB FTS index."""

    def __init__(self, reference: Any) -> None:
        self.indexed_edge_count = len(reference.essential_edges)

    def search(self, query: str, *, limit: int) -> list[dict[str, Any]]:
        """Return no lexical hits; CG1 still uses owner atom/token evidence."""

        return []


def _admission_summary(certificate: Any) -> dict[str, Any]:
    novel = next(
        (
            obligation
            for obligation in certificate.obligations
            if obligation.obligation_id == "novel_irreducible"
        ),
        None,
    )
    return {
        "certificate_id": certificate.certificate_id,
        "content_hash": certificate.content_hash,
        "decision": certificate.decision,
        "decisive_reason": certificate.decisive_reason,
        "authority_scope": certificate.authority_scope,
        "production_promotable": certificate.production_promotable,
        "open_obligations": list(certificate.open_obligations),
        "closed_obligations": list(certificate.closed_obligations),
        "stable_unique": certificate.stable_unique.stable,
        "stable_unique_reason": certificate.stable_unique.reason,
        "mechanism_status": certificate.mechanism_witness.status,
        "mechanism_evidence": certificate.mechanism_witness.evidence,
        "data_trust_status": certificate.data_trust.status,
        "data_trust_cap": certificate.data_trust.resolved_trust_cap,
        "acquisition_blocker": certificate.acquisition_need.blocker_id
        if certificate.acquisition_need
        else None,
        "registry_patch_id": certificate.registry_patch.patch_id
        if certificate.registry_patch
        else None,
        "registry_patch_status": certificate.registry_patch.application_status
        if certificate.registry_patch
        else None,
        "decision_front_created": certificate.registry_patch.decision_front_created
        if certificate.registry_patch
        else None,
        "delta_spend": certificate.delta_adm_ledger.total_spend,
        "delta_budget": certificate.delta_adm_ledger.delta_adm_budget,
        "delta_within_budget": certificate.delta_adm_ledger.within_budget,
        "n11_composition_status": certificate.delta_adm_ledger.n11_composition_status,
        "novel_irreducible_evidence": novel.evidence if novel else {},
    }


def _contract_testing_scope(reference: Any, substrate_registry: Any, cg1: Any, cg2: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_admission import GroundingAdmissionEngine

    certificate = GroundingAdmissionEngine.for_contract_testing(
        reference,
        substrate_registry=substrate_registry,
    ).decide(cg2, cg1_certificate=cg1)
    return _admission_summary(certificate)


def _actuatability_denominator(reference: Any) -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_admission import (
        _first_text,
        _target_actuatability,
    )
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine

    atoms = GroundingRelationEngine(reference).reference_atoms
    targets: dict[str, dict[str, Any]] = {}
    reason_counts: dict[str, int] = {}
    for edge in reference.essential_edges.values():
        if edge.modality != "WMR_POLICY_SLOT_MAP" or edge.status != "confirmed":
            continue
        for completion in edge.admissible_completions:
            for field in ("world_slot", "slot_id", "state_path"):
                target = _first_text(completion.value.get(field))
                if not target or target in targets:
                    continue
                resolution = _target_actuatability(reference, target, atoms=atoms)
                targets[target] = {
                    "actuatable": resolution["actuatable"],
                    "field": field,
                    "reason": resolution["reason"],
                }
                reason = str(resolution["reason"])
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
    accepted = sorted(target for target, row in targets.items() if row["actuatable"])
    rejected = sorted(target for target, row in targets.items() if not row["actuatable"])
    return {
        "accepted_count": len(accepted),
        "accepted_targets": accepted,
        "reason_counts": dict(sorted(reason_counts.items())),
        "rejected_count": len(rejected),
        "rejected_targets": rejected,
        "targets": dict(sorted(targets.items())),
        "total_policy_map_targets": len(targets),
    }


def _production_api_boundary_probes() -> dict[str, Any]:
    from polisyos.runtime.quality.grounding_admission import (
        GroundingAdmissionEngine,
        GroundingAdmissionPolicy,
    )

    probes = {}
    for probe_id, kwargs in {
        "policy_force_admit": {"force_admit": True},
        "policy_disable_mechanism": {"disable_mechanism_witness_resolution": True},
        "policy_delta_override": {"delta_adm_budget": 1.0},
        "policy_mechanism_inject": {"mechanism_witness": True},
    }.items():
        try:
            GroundingAdmissionPolicy(**kwargs)
        except ValueError as exc:
            probes[probe_id] = {"accepted": False, "error": str(exc).split("\n", 1)[0]}
        else:
            probes[probe_id] = {"accepted": True}
    try:
        GroundingAdmissionEngine(object(), substrate_registry=_spoofed_registry())  # type: ignore[arg-type,call-arg]
    except TypeError as exc:
        probes["engine_substrate_registry_argument"] = {
            "accepted": False,
            "error": str(exc).split("\n", 1)[0],
        }
    else:
        probes["engine_substrate_registry_argument"] = {"accepted": True}
    return probes


def _mutation_reports(
    *,
    reference: Any,
    admit_reference: Any,
    paraphrase_reference: Any,
    low_trust_reference: Any,
    two_hop_reference: Any,
    low_trust_hop_reference: Any,
    compatibility_reference: Any,
    outcome_map_reference: Any,
    proxy_named_reference: Any,
    self_loop_reference: Any,
    substrate_registry: Any,
) -> list[dict[str, Any]]:
    from polisyos.runtime.quality.grounding_admission import (
        GroundingAdmissionCertificate,
        GroundingAdmissionEngine,
        recompute_grounding_admission_content_hash,
    )

    reports: list[dict[str, Any]] = []

    cg1_fake, cg2_fake = _cg2_pair(reference, _fabricated_mechanism_probe())
    mechanism_mut = GroundingAdmissionEngine.for_contract_testing(
        reference,
        substrate_registry=substrate_registry,
        disable_mechanism_witness_resolution=True,
        allow_substrate_registry_authority=True,
    ).decide(cg2_fake, cg1_certificate=cg1_fake)
    reports.append(
        _mutation_row(
            "mechanism_witness_resolution_removed",
            mechanism_mut.decision == "admit_new_lever",
            _admission_summary(mechanism_mut),
            note=(
                "Exact outcome-wish+mechanism mutation remains structurally rejected by "
                "the reject-proof firewall; reachable fabricated-proof real-shaped lever flips."
            ),
        )
    )

    cg1_para, cg2_para = _cg2_pair(paraphrase_reference, _paraphrase_probe())
    novel_mut = GroundingAdmissionEngine.for_contract_testing(
        paraphrase_reference,
        substrate_registry=substrate_registry,
        disable_novel_irreducible=True,
    ).decide(cg2_para, cg1_certificate=cg1_para)
    reports.append(
        _mutation_row(
            "novel_irreducible_removed",
            novel_mut.decision == "admit_new_lever",
            _admission_summary(novel_mut),
        )
    )
    denotation_mut = GroundingAdmissionEngine.for_contract_testing(
        paraphrase_reference,
        disable_denotation_novelty=True,
    ).decide(cg2_para, cg1_certificate=cg1_para)
    reports.append(
        _mutation_row(
            "denotation_comparison_removed",
            denotation_mut.decision == "admit_new_lever",
            _admission_summary(denotation_mut),
        )
    )
    cg1_compat, cg2_compat = _cg2_pair(
        compatibility_reference,
        _compatibility_derived_alias_probe(),
    )
    full_universe_mut = GroundingAdmissionEngine.for_contract_testing(
        compatibility_reference,
        allow_policy_map_mention_actuatability=True,
        disable_do_path_resolution=True,
        explicit_only_denotation_match=True,
    ).decide(cg2_compat, cg1_certificate=cg1_compat)
    reports.append(
        _mutation_row(
            "full_universe_denotation_removed",
            full_universe_mut.decision == "admit_new_lever",
            _admission_summary(full_universe_mut),
        )
    )

    ambiguous_reference = _with_contested_completion(admit_reference)
    cg1_amb, cg2_amb = _cg2_pair(ambiguous_reference, _free_grow_probe())
    stable_mut = GroundingAdmissionEngine.for_contract_testing(
        ambiguous_reference,
        substrate_registry=substrate_registry,
        disable_stable_unique=True,
    ).decide(cg2_amb, cg1_certificate=cg1_amb)
    reports.append(
        _mutation_row(
            "stable_unique_removed",
            stable_mut.decision == "admit_new_lever",
            _admission_summary(stable_mut),
        )
    )

    cg1_missing, cg2_missing = _cg2_pair(reference, _free_grow_probe())
    reject_mut = GroundingAdmissionEngine.for_contract_testing(
        reference,
        substrate_registry=substrate_registry,
        reject_unknown=True,
    ).decide(cg2_missing, cg1_certificate=cg1_missing)
    reports.append(
        _mutation_row(
            "reject_only_on_proven_removed",
            reject_mut.decision == "reject_hallucination",
            _admission_summary(reject_mut),
        )
    )

    cg1_good, cg2_good = _cg2_pair(admit_reference, _free_grow_probe())
    good = GroundingAdmissionEngine(admit_reference).decide(
        cg2_good,
        cg1_certificate=cg1_good,
    )
    acquire = GroundingAdmissionEngine(reference).decide(
        cg2_missing,
        cg1_certificate=cg1_missing,
    )
    forged_payload = acquire.model_dump(mode="json")
    forged_payload["decision"] = "admit_new_lever"
    forged_payload["decisive_reason"] = "all_obligations_closed"
    forged_payload["production_promotable"] = True
    forged_payload["registry_patch"] = good.registry_patch.model_dump(mode="json")
    forged_payload["content_hash"] = recompute_grounding_admission_content_hash(forged_payload)
    forged_payload["certificate_id"] = (
        f"cg3_cert_{forged_payload['content_hash'].removeprefix('sha256:')[:16]}"
    )
    forged = GroundingAdmissionCertificate.model_validate(forged_payload)
    patched = GroundingAdmissionEngine.for_contract_testing(
        reference,
        disable_registry_patch_reresolution=True,
    ).apply_registry_patch(forged, cg2_missing, cg1_certificate=cg1_missing)
    reports.append(
        _mutation_row(
            "registry_patch_reresolution_removed",
            patched.applied is True,
            {"applied": patched.applied, "reason": patched.reason},
        )
    )
    cg1_self_loop, cg2_self_loop = _cg2_pair(
        self_loop_reference,
        _self_loop_outcome_wish_probe(),
    )
    self_loop_mut = GroundingAdmissionEngine.for_contract_testing(
        self_loop_reference,
        disable_do_path_resolution=True,
        allow_policy_map_mention_actuatability=True,
    ).decide(cg2_self_loop, cg1_certificate=cg1_self_loop)
    reports.append(
        _mutation_row(
            "do_path_actuatability_resolution_removed",
            self_loop_mut.decision == "admit_new_lever",
            _admission_summary(self_loop_mut),
        )
    )

    cg1_low_trust, cg2_low_trust = _cg2_pair(low_trust_reference, _fabricated_mechanism_probe())
    substrate_mut = GroundingAdmissionEngine.for_contract_testing(
        low_trust_reference,
        substrate_registry=_spoofed_registry(),
        disable_mechanism_witness_resolution=True,
        allow_substrate_registry_authority=True,
    ).decide(cg2_low_trust, cg1_certificate=cg1_low_trust)
    reports.append(
        _mutation_row(
            "substrate_registry_authority_restored",
            substrate_mut.decision == "admit_new_lever",
            _admission_summary(substrate_mut),
        )
    )
    cg1_two_hop, cg2_two_hop = _cg2_pair(two_hop_reference, _free_grow_probe())
    cg1_low_hop, cg2_low_hop = _cg2_pair(low_trust_hop_reference, _free_grow_probe())
    composed_mut = GroundingAdmissionEngine.for_contract_testing(
        low_trust_hop_reference,
        allow_composed_mechanism_witness=True,
        use_best_edge_trust=True,
    ).decide(cg2_low_hop, cg1_certificate=cg1_low_hop)
    two_hop_mut = GroundingAdmissionEngine.for_contract_testing(
        two_hop_reference,
        allow_composed_mechanism_witness=True,
    ).decide(cg2_two_hop, cg1_certificate=cg1_two_hop)
    reports.append(
        _mutation_row(
            "direct_mechanism_witness_removed",
            composed_mut.decision == "admit_new_lever"
            and two_hop_mut.decision == "admit_new_lever",
            {
                "best_edge_low_trust_hop": _admission_summary(composed_mut),
                "composed_two_hop": _admission_summary(two_hop_mut),
            },
        )
    )

    cg1_outcome_map, cg2_outcome_map = _cg2_pair(
        outcome_map_reference,
        _outcome_like_policy_map_probe(),
    )
    actuatability_mut = GroundingAdmissionEngine.for_contract_testing(
        outcome_map_reference,
        allow_policy_map_mention_actuatability=True,
    ).decide(cg2_outcome_map, cg1_certificate=cg1_outcome_map)
    reports.append(
        _mutation_row(
            "positive_writability_removed",
            actuatability_mut.decision == "admit_new_lever",
            _admission_summary(actuatability_mut),
        )
    )

    cg1_proxy_named, cg2_proxy_named = _cg2_pair(
        proxy_named_reference,
        _proxy_named_real_unproven_probe(),
    )
    proxy_keyword_mut = GroundingAdmissionEngine.for_contract_testing(
        proxy_named_reference,
        enable_keyword_proxy_reject=True,
    ).decide(cg2_proxy_named, cg1_certificate=cg1_proxy_named)
    reports.append(
        _mutation_row(
            "keyword_proxy_reject_restored",
            proxy_keyword_mut.decision == "reject_hallucination",
            _admission_summary(proxy_keyword_mut),
        )
    )

    return reports


def _mutation_row(
    mutation_id: str,
    flipped_bad: bool,
    payload: dict[str, Any],
    *,
    note: str | None = None,
) -> dict[str, Any]:
    row = {
        "mutation_id": mutation_id,
        "status": "red" if flipped_bad else "green",
        "probe": payload,
    }
    if note:
        row["note"] = note
    return row


def _real_n4_probe(repo_root: Path, reference: Any) -> dict[str, Any]:
    del reference
    contract_path = repo_root / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
    payload = json.loads(contract_path.read_text(encoding="utf-8"))
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
                "certificate_id": chain.get("cg3_certificate_id"),
                "content_hash": chain.get("cg3_content_hash"),
                "decision": disposition.get("cg3_decision"),
                "decisive_reason": disposition.get("cg3_reason"),
                "authority_scope": "shadow_only",
                "production_promotable": False,
                "open_obligations": disposition.get("cg3_open_obligations", []),
                "closed_obligations": [],
                "stable_unique": None,
                "stable_unique_reason": "frozen_real_output_payoff_receipt",
                "mechanism_status": disposition.get("cg3_reason"),
                "mechanism_evidence": {},
                "data_trust_status": "frozen_receipt",
                "data_trust_cap": None,
                "acquisition_blocker": disposition.get("cg3_reason"),
                "registry_patch_id": None,
                "registry_patch_status": None,
                "decision_front_created": None,
                "delta_spend": 0.0,
                "delta_budget": 0.0,
                "delta_within_budget": True,
                "n11_composition_status": "frozen_receipt",
                "novel_irreducible_evidence": {},
                "cg1_certificate_id": chain.get("cg1_certificate_id"),
                "cg1_selected_relation": disposition.get("selected_relation"),
                "cg2_certificate_id": chain.get("cg2_certificate_id"),
                "cg2_decision": disposition.get("cg2_decision"),
                "cg2_reason": disposition.get("cg2_reason"),
                "frozen_receipt": True,
                "proposal_id": disposition.get("proposal_id"),
            }
    raise RuntimeError("cg3_recorded_n4_novel_handoff_missing")


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


def _probe(payload: Any, key: str) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get(key), dict):
        return payload[key]
    return {}


def _free_grow_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg3.free_grow.regional_resilience_credit",
        "raw_text": "regional resilience credit raises distress-score intervention intensity for cells.",
        "signature": {
            "op": "regional_resilience_credit",
            "target": ["cells.distress_score"],
            "sign": "increase",
            "params": {"rate": 0.4},
            "x_do": {"rate": 0.4},
            "scope": "regional_cells",
            "population": "cells",
            "unit": "ratio",
            "outcome": ["cells.output"],
            "effect_path": [
                "regional_resilience_credit",
                "cells.distress_score",
                "cells.output",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": {
                "NL": {
                    "op": "regional_resilience_credit",
                    "target": "cells.distress_score",
                    "outcome": "cells.output",
                    "estimand": "average_treatment_effect",
                },
                "do_AST": {
                    "op": "regional_resilience_credit",
                    "target": "cells.distress_score",
                    "do_value": {"rate": 0.4},
                },
            },
        },
    }


def _tax_surcharge_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg3.free_grow.tax_surcharge_adjustment",
        "raw_text": "temporary tax surcharge raises the global tax-rate setting and budget balance.",
        "signature": {
            "op": "temporary_tax_surcharge",
            "target": ["global.tax_rate"],
            "sign": "increase",
            "params": {"rate": 0.2},
            "x_do": {"rate": 0.2},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": ["temporary_tax_surcharge", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="temporary_tax_surcharge",
                target="global.tax_rate",
                outcome="government.balance",
                do_value={"rate": 0.2},
            ),
        },
    }


def _outcome_wish_probe() -> dict[str, Any]:
    probe = _copy(_free_grow_probe())
    signature = probe["signature"]
    signature["op"] = None
    signature["target"] = []
    signature["x_do"] = {}
    signature["effect_path"] = []
    return {**probe, "proposal_id": "cg3.reject.outcome_wish"}


def _self_loop_outcome_wish_probe() -> dict[str, Any]:
    probe = _copy(_free_grow_probe())
    signature = probe["signature"]
    signature["op"] = "raise_household_income_goal"
    signature["target"] = ["household_cells.disposable_income"]
    signature["params"] = {"goal": 1.0}
    signature["x_do"] = {"goal": 1.0}
    signature["unit"] = "usd"
    signature["outcome"] = ["household_cells.disposable_income"]
    signature["effect_path"] = [
        "raise_household_income_goal",
        "household_cells.disposable_income",
        "household_cells.disposable_income",
    ]
    signature["modal_claims"] = _modal_claims(
        op="raise_household_income_goal",
        target="household_cells.disposable_income",
        outcome="household_cells.disposable_income",
        do_value={"goal": 1.0},
    )
    return {**probe, "proposal_id": "cg3.reject.self_loop_outcome_wish"}


def _proxy_manipulation_probe() -> dict[str, Any]:
    probe = _copy(_free_grow_probe())
    signature = probe["signature"]
    signature["op"] = "reported_income_adjustment"
    signature["target"] = ["agents.reported_income"]
    signature["params"] = {"reporting_delta": 0.2}
    signature["x_do"] = {"reporting_delta": 0.2}
    signature["unit"] = "usd"
    signature["outcome"] = ["household_cells.disposable_income"]
    signature["effect_path"] = [
        "reported_income_adjustment",
        "agents.reported_income",
        "household_cells.disposable_income",
    ]
    signature["modal_claims"] = _modal_claims(
        op="reported_income_adjustment",
        target="agents.reported_income",
        outcome="household_cells.disposable_income",
        do_value={"reporting_delta": 0.2},
    )
    return {**probe, "proposal_id": "cg3.reject.proxy_manipulation"}


def _reported_income_proxy_probe() -> dict[str, Any]:
    return {**_proxy_manipulation_probe(), "proposal_id": "cg3.reject.reported_income_proxy"}


def _proxy_named_real_unproven_probe() -> dict[str, Any]:
    probe = _copy(_free_grow_probe())
    signature = probe["signature"]
    signature["op"] = "proxy_means_test_transfer_adjustment"
    signature["target"] = ["household_cells.transfer_intensity"]
    signature["params"] = {"rate": 0.25}
    signature["x_do"] = {"rate": 0.25}
    signature["outcome"] = ["household_cells.disposable_income"]
    signature["effect_path"] = [
        "proxy_means_test_transfer_adjustment",
        "household_cells.transfer_intensity",
        "household_cells.disposable_income",
    ]
    signature["modal_claims"] = _modal_claims(
        op="proxy_means_test_transfer_adjustment",
        target="household_cells.transfer_intensity",
        outcome="household_cells.disposable_income",
        do_value={"rate": 0.25},
    )
    return {**probe, "proposal_id": "cg3.acquire.proxy_named_real_unproven"}


def _impossible_type_probe() -> dict[str, Any]:
    probe = _copy(_free_grow_probe())
    signature = probe["signature"]
    signature["op"] = "malformed_slot_write"
    signature["target"] = ["not-a-world-slot"]
    signature["outcome"] = ["household_cells.disposable_income"]
    signature["effect_path"] = [
        "malformed_slot_write",
        "not-a-world-slot",
        "household_cells.disposable_income",
    ]
    signature["modal_claims"] = _modal_claims(
        op="malformed_slot_write",
        target="not-a-world-slot",
        outcome="household_cells.disposable_income",
        do_value={"rate": 0.1},
    )
    return {**probe, "proposal_id": "cg3.reject.impossible_type"}


def _fabricated_mechanism_probe() -> dict[str, Any]:
    probe = _copy(_free_grow_probe())
    signature = probe["signature"]
    signature["evidence"] = ["mechanism_witness=true", "caller_says_l2_proof"]
    signature["modal_claims"]["LLM"] = {
        "mechanism_witness": True,
        "rationale": "looks causal",
    }
    return {**probe, "proposal_id": "cg3.fail_closed.fabricated_mechanism"}


def _paraphrase_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg3.non_new.tax_support_rate",
        "raw_text": "tax support rate changes the tax slot with the same do-query.",
        "signature": {
            "op": "tax_support_rate",
            "target": ["global.tax_rate"],
            "sign": "decrease",
            "params": {"rate": 0.1},
            "x_do": {"rate": 0.1},
            "scope": "global",
            "population": "all",
            "unit": "ratio",
            "outcome": ["government.balance"],
            "effect_path": ["tax_support_rate", "global.tax_rate", "government.balance"],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": {
                "NL": {
                    "op": "tax_support_rate",
                    "target": "global.tax_rate",
                    "outcome": "government.balance",
                    "estimand": "average_treatment_effect",
                },
                "do_AST": {"op": "tax_support_rate", "target": "global.tax_rate"},
            },
        },
    }


def _compatibility_derived_alias_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg3.non_new.compatibility_cells_output_alias",
        "raw_text": "output procurement alias writes the same cells output do-query.",
        "signature": {
            "op": "output_procurement_alias",
            "target": ["cells.output"],
            "sign": "decrease",
            "params": {"rate": 0.2},
            "x_do": {"rate": 0.2},
            "scope": "regional_cells",
            "population": "cells",
            "unit": "ratio",
            "outcome": ["cells.output"],
            "effect_path": [
                "output_procurement_alias",
                "cells.output",
                "cells.output",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="output_procurement_alias",
                target="cells.output",
                outcome="cells.output",
                do_value={"rate": 0.2},
            ),
        },
    }


def _outcome_like_policy_map_probe() -> dict[str, Any]:
    return {
        "proposal_id": "cg3.acquire.outcome_like_policy_map_target",
        "raw_text": "directly set disposable income as a policy control.",
        "signature": {
            "op": "direct_disposable_income_control",
            "target": ["household_cells.disposable_income"],
            "sign": "increase",
            "params": {"amount": 100.0},
            "x_do": {"amount": 100.0},
            "scope": "households",
            "population": "households",
            "unit": "usd",
            "outcome": ["government.balance"],
            "effect_path": [
                "direct_disposable_income_control",
                "household_cells.disposable_income",
                "government.balance",
            ],
            "estimand": "average_treatment_effect",
            "admissibility": "passed",
            "modal_claims": _modal_claims(
                op="direct_disposable_income_control",
                target="household_cells.disposable_income",
                outcome="government.balance",
                do_value={"amount": 100.0},
            ),
        },
    }


def _spoofed_registry() -> object:
    class _Trust:
        trust_cap = 0.99

    class _Entry:
        layer = "L2"
        family_id = "spoof_causal_family"
        trust_tier = _Trust()
        authority_refs = ("spoof://caller",)

    class _Registry:
        entries = (_Entry(),)

    return _Registry()


def _modal_claims(
    *,
    op: str,
    target: str,
    outcome: str,
    do_value: dict[str, float],
) -> dict[str, dict[str, Any]]:
    return {
        "NL": {
            "op": op,
            "target": target,
            "outcome": outcome,
            "estimand": "average_treatment_effect",
        },
        "do_AST": {
            "do_value": do_value,
            "op": op,
            "target": target,
        },
    }


def _copy(payload: Any) -> Any:
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _json_stable(payload: dict[str, Any]) -> dict[str, Any]:
    return _copy(payload)


def main(argv: list[str] | None = None) -> int:
    """Run the CGF GY-CG3 admission contract validator."""

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
        print("grounding admission contract: pass")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
