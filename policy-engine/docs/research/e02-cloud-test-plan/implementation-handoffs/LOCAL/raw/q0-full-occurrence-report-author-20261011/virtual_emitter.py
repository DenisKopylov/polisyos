#!/usr/bin/env python3
"""Emit a provisional, source-qualified E02 full-occurrence decision packet.

This extension reuses the registered proposal emitter as the producer and
admission path. It emits a local review artifact only; it does not import
candidate outcomes, establish a final source freeze, or perform G adjudication.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


LEASE_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "q0-full-occurrence-report-author-20261011"
)
DECLARATION_REL = LEASE_REL / "preimage-declaration.json"
PACKET_REL = LEASE_REL / "proposal-decision-packet.json"
CONTROLS_REL = LEASE_REL / "controls.json"
MANIFEST_REL = LEASE_REL / "full-manifest.json"
CHECKS_REL = LEASE_REL / "checks"
COVERAGE_REL = Path("policy-engine/docs/research/e02-cloud-test-plan/closure-decisions/coverage.json")
CANONICAL_EMITTER_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/emit_proposals.py"
)
IDENTITY_HELPER_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "full-id-occurrence-identity-repair-r1-20261011/occurrence_identity.py"
)
DRAFT_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "crosswalk/occurrence-evaluations-draft.json"
)
PREFREEZE_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "crosswalk/full-id-prefreeze-current-proposal-intake-20261011-v1.json"
)
R9_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/"
    "full-id-evidence-intake-r9-20261011/full-id-evidence-intake.json"
)
READINESS_REL = Path(
    "policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/"
    "crosswalk/full-id-current-source-readiness-1ab7d354-20261011.json"
)


def repo_root() -> Path:
    """Find the repository root from this leased extension's location."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "AGENTS.md").is_file() and (parent / "policy-engine").is_dir():
            return parent
    raise RuntimeError("could not locate repository root")


def sha256_bytes(data: bytes) -> str:
    """Return a lowercase SHA-256 digest."""
    return hashlib.sha256(data).hexdigest()


def sha256_path(root: Path, relative: str | Path) -> str:
    """Hash one repository-relative file without transforming its bytes."""
    return sha256_bytes((root / relative).read_bytes())


def read_json(root: Path, relative: str | Path) -> dict[str, Any]:
    """Read a JSON object from a repository-relative path."""
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {relative}")
    return value


def import_module(name: str, path: Path) -> Any:
    """Import an existing Python module by its exact file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require(condition: bool, message: str) -> None:
    """Raise a clear validation failure when a report invariant is false."""
    if not condition:
        raise ValueError(message)


def row_keys(rows: list[dict[str, Any]], *, id_key: str, pointer_key: str, hash_key: str) -> list[tuple[str, str, str]]:
    """Adapt a source row array into exact occurrence identities."""
    result: list[tuple[str, str, str]] = []
    for index, row in enumerate(rows):
        finding_id = row.get(id_key)
        pointer = row.get(pointer_key)
        digest = row.get(hash_key)
        if not all(isinstance(value, str) and value for value in (finding_id, pointer, digest)):
            raise ValueError(f"invalid occurrence identity at row {index}")
        if len(digest) != 64:
            raise ValueError(f"invalid criterion digest at row {index}")
        result.append((finding_id, pointer, digest))
    return result


def load_declared_sources(root: Path, declaration: dict[str, Any]) -> None:
    """Content-bind every named preimage used by this local report."""
    for item in declaration.get("source_preimages", []):
        relative = item["path"]
        data = (root / relative).read_bytes()
        require(len(data) == item["bytes"], f"source byte count drift: {relative}")
        require(sha256_bytes(data) == item["sha256"], f"source SHA-256 drift: {relative}")
    emitter = declaration["generator"]["canonical_path"]
    helper = declaration["generator"]["identity_helper_path"]
    require(sha256_path(root, emitter) == declaration["generator"]["canonical_sha256"], "registered emitter SHA-256 drift")
    require(sha256_path(root, helper) == declaration["generator"]["identity_helper_sha256"], "identity helper SHA-256 drift")


def build_packet() -> tuple[dict[str, Any], dict[str, Any], list[tuple[str, str, str]], Any]:
    """Run the registered producer/admission path and build the report projection."""
    root = repo_root()
    declaration = read_json(root, DECLARATION_REL)
    load_declared_sources(root, declaration)
    canonical_path = root / CANONICAL_EMITTER_REL
    helper_path = root / IDENTITY_HELPER_REL
    canonical = import_module("e02_registered_emit_proposals", canonical_path)
    identity = import_module("e02_registered_occurrence_identity", helper_path)

    snapshot = canonical.load_sources(root, provisional=True)
    ledger = canonical.build_ledger(snapshot, None)
    canonical_validation = canonical.validate_ledger(ledger, snapshot)
    require(ledger.get("formal_closure_ids") == [], "registered emitter produced formal closures")
    require(ledger.get("evaluation_mode") == "provisional_author_review_pending_final_source_freeze", "registered emitter is not in provisional mode")
    require(ledger["source_boundary"]["source_freeze"]["status"] == "provisional_source_checkpoint_not_frozen", "source freeze is not provisional")

    draft = read_json(root, DRAFT_REL)
    prefreeze = read_json(root, PREFREEZE_REL)
    r9 = read_json(root, R9_REL)
    readiness = read_json(root, READINESS_REL)
    coverage_keys = identity.coverage_occurrence_keys(snapshot["coverage"], COVERAGE_REL.as_posix())
    ledger_keys = identity.ledger_occurrence_keys(ledger)
    draft_keys = identity.draft_occurrence_keys(draft)
    prefreeze_keys = [
        (row["key"]["finding_id"], row["key"]["coverage_occurrence_pointer"], row["key"]["criterion_sha256"])
        for row in prefreeze["occurrences"]
    ]
    r9_keys = row_keys(
        r9["occurrences"], id_key="id", pointer_key="coverage_pointer", hash_key="criterion_sha256"
    )
    readiness_keys = [
        (row["occurrence_key"]["finding_id"], row["occurrence_key"]["coverage_pointer"], row["occurrence_key"]["criterion_sha256"])
        for row in readiness["occurrences"]
    ]
    for label, keys in (
        ("registered ledger", ledger_keys),
        ("preparation draft", draft_keys),
        ("prefreeze proposal intake", prefreeze_keys),
        ("R9 evidence intake", r9_keys),
        ("source readiness intake", readiness_keys),
    ):
        identity.require_same_occurrence_multiset(coverage_keys, keys, label=label)
    require(len(coverage_keys) == 291 and len(set(coverage_keys)) == 291, "coverage denominator is not 291 unique full occurrence identities")

    ledger_by_id = {finding["finding_id"]: finding for finding in ledger["findings"]}
    ledger_occ_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for finding in ledger["findings"]:
        for occurrence in finding["occurrences"]:
            original = occurrence["original"]
            key = (finding["finding_id"], original["occurrence_pointer"], original["sha256"])
            require(key not in ledger_occ_by_key, f"duplicate exact ledger occurrence key: {key[0]}")
            ledger_occ_by_key[key] = occurrence
    draft_by_key = {
        (row["key"]["finding_id"], row["key"]["coverage_pointer"], row["key"]["criterion_sha256"]): row
        for row in draft["occurrences"]
    }
    prefreeze_by_key = {
        (row["key"]["finding_id"], row["key"]["coverage_occurrence_pointer"], row["key"]["criterion_sha256"]): row
        for row in prefreeze["occurrences"]
    }
    prefreeze_index_by_key = {
        (row["key"]["finding_id"], row["key"]["coverage_occurrence_pointer"], row["key"]["criterion_sha256"]): index
        for index, row in enumerate(prefreeze["occurrences"])
    }
    r9_by_key = {
        (row["id"], row["coverage_pointer"], row["criterion_sha256"]): row
        for row in r9["occurrences"]
    }
    readiness_by_key = {
        (row["occurrence_key"]["finding_id"], row["occurrence_key"]["coverage_pointer"], row["occurrence_key"]["criterion_sha256"]): row
        for row in readiness["occurrences"]
    }
    readiness_index_by_key = {
        (row["occurrence_key"]["finding_id"], row["occurrence_key"]["coverage_pointer"], row["occurrence_key"]["criterion_sha256"]): index
        for index, row in enumerate(readiness["occurrences"])
    }

    occurrences_by_id: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    route_assignment_ptrs: list[str] = []
    route_occurrence_ref_count = 0
    technical_status_counts: collections.Counter[str] = collections.Counter()
    candidate_counts: collections.Counter[str] = collections.Counter()
    for row_index, key in enumerate(coverage_keys):
        finding_id, pointer, digest = key
        ledger_occurrence = ledger_occ_by_key[key]
        draft_row = draft_by_key[key]
        prefreeze_row = prefreeze_by_key[key]
        r9_row = r9_by_key[key]
        readiness_row = readiness_by_key[key]
        raw_key = draft_row["key"]
        technical = draft_row["technical_assessment"]
        require(
            prefreeze_row["prefreeze_author_proposal_for_G_review"]["disposition"]
            == draft_row["proposal_disposition"]["status"],
            f"prefreeze and draft proposal dispositions differ at {finding_id}",
        )
        require(r9_row["candidate_evaluation"] == "UNRUN", f"R9 candidate status is not UNRUN at {finding_id}")
        require(r9_row["formal_closure_ids"] == [], f"R9 formal closure list changed at {finding_id}")
        require(prefreeze_row["candidate_evaluation"]["state"] == "UNRUN", f"prefreeze candidate status is not UNRUN at {finding_id}")
        require(prefreeze_row["candidate_evaluation"]["formal_closure"] is False, f"prefreeze formal closure claimed at {finding_id}")
        require(readiness_row["current_candidate_readiness"]["candidate_evaluation"] == "UNRUN", f"readiness candidate status is not UNRUN at {finding_id}")
        require(readiness_row["history_and_proposal"]["source_author_disposition"] == ledger_by_id[finding_id]["source_author_proposal"]["disposition"], f"source-author status differs at {finding_id}")
        current = technical["current_mechanism_or_bounded_path"]
        evidence_boundary = technical["evidence_boundary"]
        candidate = ledger_occurrence["candidate_evaluation"]
        routes = draft_row.get("task_routes", [])
        route_occurrence_ref_count += len(routes)
        route_assignment_ptrs.extend(route["assignment_pointer"] for route in routes)
        technical_status = draft_row["proposal_disposition"]["status"]
        technical_status_counts[technical_status] += 1
        candidate_counts[candidate["state"]] += 1

        source_span = raw_key["source_span"]
        occurrence = {
            "identity": {
                "finding_id": finding_id,
                "occurrence_pointer": pointer,
                "criterion_sha256": digest,
                "occurrence_ordinal_for_finding": raw_key["occurrence_ordinal_for_finding"],
                "document": raw_key["document"],
                "card_binding": raw_key["card_binding"],
                "owner_unit": raw_key["owner_unit"],
            },
            "original_criterion_source": {
                "path": source_span["path"],
                "source_commit": source_span["source_commit"],
                "git_blob": source_span["git_blob"],
                "lines_1_based_inclusive": source_span["lines_1_based_inclusive"],
                "criterion_sha256": digest,
                "current_worktree_span_sha256_matches_coverage": source_span["current_worktree_span_sha256_matches_coverage"],
                "source_pointer": pointer,
                "criterion_text_copied": False,
            },
            "history_and_authority": {
                "historical_ledger_status": ledger_by_id[finding_id]["historical"]["ledger_status"],
                "historical_appendix_c_status": ledger_by_id[finding_id]["historical"]["appendix_c_status"],
                "historical_closure_now": ledger_by_id[finding_id]["historical"]["closure_now"],
                "source_author_disposition": ledger_by_id[finding_id]["source_author_proposal"]["disposition"],
                "source_author_G_closure_field": ledger_by_id[finding_id]["source_author_proposal"]["G_closure_field"],
                "source_author_ref": ledger_by_id[finding_id]["source_author_proposal"]["finding_index_pointer"],
                "formal_G_status": "not_adjudicated",
                "formal_closure": False,
            },
            "proposal": {
                "current_prefreeze_technical_disposition": draft_row["proposal_disposition"]["status"],
                "basis": draft_row["proposal_disposition"]["basis"],
                "prefreeze_G_review_disposition": prefreeze_row["prefreeze_author_proposal_for_G_review"]["disposition"],
                "prefreeze_intake_pointer": f"{PREFREEZE_REL.as_posix()}#/occurrences/{prefreeze_index_by_key[key]}",
                "qualification": "source-qualified author proposal only; not a candidate result or formal closure",
            },
            "candidate_evaluation": candidate,
            "whole_property": {
                "owner_assessed_property": current.get("property"),
                "proxy_divergence": current.get("proxy_divergence"),
                "readout": current.get("readout"),
                "original_acceptance_boundary": draft_row["original_acceptance_boundary"],
                "capability_label": draft_row["original_acceptance_boundary"].get("coverage_capability_label"),
                "bounded_mechanism_or_path": current,
                "remaining_quantity_or_dependency": technical.get("remaining_whole_criterion_quantity_or_dependency"),
                "separate_external_or_G_boundary": technical.get("separate_external_or_G_boundary"),
                "minimum_next_input": technical.get("minimum_next_input"),
                "next_owner_or_decision_holder": technical.get("next_owner_or_decision_holder"),
                "owner_assignment_boundary": technical.get("owner_assignment_boundary"),
                "why_positive_is_not_claimed": technical.get("why_an_unqualified_positive_is_not_claimed"),
                "property_review_refs": {
                    "draft_occurrence": f"{DRAFT_REL.as_posix()}#/occurrences/{row_index}",
                    "owner_assessment_row": technical.get("owner_assessment_row_pointer"),
                    "owner_packet_refs": technical.get("owner_source_refs"),
                    "readiness_row": f"{READINESS_REL.as_posix()}#/occurrences/{readiness_index_by_key[key]}",
                },
            },
            "evidence_and_dependencies": {
                "source_review_status": evidence_boundary.get("owner_readout_status"),
                "candidate_source_binding": evidence_boundary.get("candidate_source_binding"),
                "source_evidence_ids": evidence_boundary.get("source_ref_ids", []),
                "retained_occurrence_evidence_refs": technical.get("retained_evidence_refs", []),
                "r9_bounded_evidence_ids": r9_row.get("relevant_bounded_evidence_ids", []),
                "r9_pointer": f"{R9_REL.as_posix()}#/occurrences/{r9_row['row_index']}",
                "current_route_overlay_refs": [
                    {
                        "evidence_id": overlay.get("evidence_id"),
                        "status": overlay.get("status"),
                        "source_head": overlay.get("source_head"),
                    }
                    for overlay in prefreeze_row.get("current_route_overlays", [])
                ],
                "task_routes_are_evidence": False,
                "no_external_fact_inference": evidence_boundary.get("no_external_fact_inference", True),
                "source_freeze_qualification": "prefreeze review only; retained references are not admitted candidate outcomes",
            },
            "P40": {
                "same_class_review_ref": draft_row.get("same_class_review_ref"),
                "owner_assessment_classification_ref": draft_row.get("owner_review_qualification_ref"),
                "P40_bucket_is_not_recomputed": True,
                "review_escape_adjudicated_here": False,
            },
            "next_check": {
                "after_final_source_freeze": draft_row.get("next_check_after_final_source_freeze"),
                "owner_exact_next_check": technical.get("exact_next_check"),
                "task_routes_navigation_only": routes,
            },
            "source_qualified_readiness": {
                "source_candidate_head": readiness_row["current_candidate_readiness"].get("candidate_head"),
                "source_candidate_tree": readiness_row["current_candidate_readiness"].get("candidate_tree"),
                "source_candidate_state": readiness_row["current_candidate_readiness"].get("candidate_state"),
                "source_candidate_evaluation": readiness_row["current_candidate_readiness"].get("candidate_evaluation"),
                "qualification": "prior source-readiness snapshot; its candidate checkpoint is not this report checkpoint",
            },
        }
        occurrences_by_id[finding_id].append(occurrence)

    source_author_by_id = {
        finding_id: finding["source_author_proposal"]["disposition"]
        for finding_id, finding in ledger_by_id.items()
    }
    author_id_counts = collections.Counter(source_author_by_id.values())
    author_occurrence_counts: collections.Counter[str] = collections.Counter()
    historical_id_counts: collections.Counter[str] = collections.Counter()
    historical_occurrence_counts: collections.Counter[str] = collections.Counter()
    for finding_id, finding in ledger_by_id.items():
        author_occurrence_counts[finding["source_author_proposal"]["disposition"]] += len(finding["occurrences"])
        historical_id_counts[finding["historical"]["ledger_status"]] += 1
        historical_occurrence_counts[finding["historical"]["ledger_status"]] += len(finding["occurrences"])

    task_definitions = len(snapshot["tasks"]["tasks"])
    q0_ids = ledger["route_census"]["q0_finding_ids"]
    q0_occurrences = ledger["route_census"]["q0_occurrences"]
    repeated_ids = sum(1 for rows in occurrences_by_id.values() if len(rows) > 1)
    repeated_rows = sum(len(rows) for rows in occurrences_by_id.values() if len(rows) > 1)

    packet = {
        "schema": "policyos.e02.q0_full_occurrence_proposal_decision_packet.v1",
        "status": "PROVISIONAL_SOURCE_QUALIFIED_AUTHOR_REPORT",
        "scope": "Full original criterion occurrence projection; not a candidate test result, formal adjudication, or product capability claim.",
        "authority_boundary": {
            "candidate_evaluation": "UNRUN for all occurrences until final source freeze and occurrence-specific semantic composition",
            "source_freeze": ledger["source_boundary"]["source_freeze"]["status"],
            "formal_G": "not_adjudicated",
            "formal_closure_ids": [],
            "source_author_status_is_not_current_evidence": True,
            "task_assignment_and_route_success_are_not_closure": True,
        },
        "pattern_pass": {
            "relevant_register_ids": ["P01", "P02", "P04", "P05", "P09", "P10", "P15", "P27", "P29", "P31", "P32", "P33", "P35", "P36", "P37", "P38", "P40", "P41"],
            "known_anti_pattern_avoided": "A standalone identity helper or unregistered report adapter is not treated as producer/admission; this projection calls the registered emitter and its validator.",
            "target_pattern": "Canonical typed occurrence rows joined by the exact (finding_id, coverage_pointer, criterion_sha256) multiset, with candidate/authority states preserved and row evidence kept source-qualified.",
            "P40_report_bucket": "No review escape is adjudicated by this authoring task; each occurrence's existing source P40 locator is preserved and no repair round is consumed.",
            "capability_state": {
                "producer": "registered proposal emitter invoked",
                "typed_artifact": "local proposal-decision-packet.json",
                "bridge": "local projection from registered ledger and source-qualified crosswalks",
                "consumer": "human/root review handoff",
                "verification": "exact full-occurrence multiset plus negative mutation controls",
                "surface": "surface_out_of_scope for this local handoff; no public API/dashboard claim",
                "candidate_execution": "not_established; all 291 remain UNRUN",
            },
        },
        "source_checkpoint": {
            "branch": ledger["source_boundary"]["report_checkout"]["branch"],
            "head": ledger["source_boundary"]["report_checkout"]["commit"],
            "tree": ledger["source_boundary"]["report_checkout"]["tree"],
            "source_freeze_status": ledger["source_boundary"]["source_freeze"]["status"],
            "source_freeze_candidate_source": ledger["source_boundary"]["source_freeze"]["candidate_source"],
            "source_change_census_ref": "/source_boundary/source_freeze/source_change_census",
            "qualification": "provisional source checkpoint; not final candidate identity",
        },
        "source_inputs": [
            {"path": item["path"], "bytes": item["bytes"], "sha256": item["sha256"]}
            for item in declaration["source_preimages"]
        ],
        "denominator": {
            "bundles": ledger["denominator"]["bundles"],
            "finding_ids": ledger["denominator"]["finding_ids"],
            "canonical_occurrences": ledger["denominator"]["canonical_occurrences"],
            "repeated_finding_ids": repeated_ids,
            "occurrences_for_repeated_finding_ids": repeated_rows,
            "task_definitions": task_definitions,
            "distinct_task_assignment_refs": len(set(route_assignment_ptrs)),
            "expanded_occurrence_route_refs": route_occurrence_ref_count,
            "Q0_finding_ids": q0_ids,
            "Q0_occurrences": q0_occurrences,
            "basis": "Complete canonical coverage walk joined against the complete registered ledger, preparation draft, prefreeze intake, R9 intake, and source-readiness rows.",
        },
        "status_summary": {
            "candidate_evaluation_by_occurrence": dict(sorted(candidate_counts.items())),
            "current_prefreeze_technical_disposition_by_occurrence": dict(sorted(technical_status_counts.items())),
            "source_author_disposition_by_finding_id": dict(sorted(author_id_counts.items())),
            "source_author_disposition_by_occurrence": dict(sorted(author_occurrence_counts.items())),
            "historical_ledger_status_by_finding_id": dict(sorted(historical_id_counts.items())),
            "historical_ledger_status_by_occurrence": dict(sorted(historical_occurrence_counts.items())),
            "route_assignments": ledger["route_census"]["route_assignments"],
            "route_gaps": ledger["route_census"]["route_gaps"],
            "all_task_routes_are_navigation_only": True,
        },
        "B198_preservation": None,
        "findings": [],
        "canonical_admission": {
            "producer_path": CANONICAL_EMITTER_REL.as_posix(),
            "producer_sha256": sha256_path(root, CANONICAL_EMITTER_REL),
            "identity_helper_path": IDENTITY_HELPER_REL.as_posix(),
            "identity_helper_sha256": sha256_path(root, IDENTITY_HELPER_REL),
            "calls": ["load_sources(provisional=True)", "build_ledger(snapshot, None)", "validate_ledger(ledger, snapshot)"],
            "validation_result": canonical_validation,
            "admission": "registered ledger passed canonical validator before this projection was built",
        },
    }
    for finding in ledger["findings"]:
        finding_id = finding["finding_id"]
        packet["findings"].append(
            {
                "finding_id": finding_id,
                "source_author_proposal": {
                    "disposition": finding["source_author_proposal"]["disposition"],
                    "source": finding["source_author_proposal"]["source"],
                    "source_author_pointer": finding["source_author_proposal"]["finding_index_pointer"],
                    "source_packet_refs": finding["source_author_proposal"]["source_packet_refs"],
                    "next_decision": finding["source_author_proposal"]["next_decision"],
                    "G_closure_field": finding["source_author_proposal"]["G_closure_field"],
                },
                "historical_statuses": finding["historical"],
                "occurrences": occurrences_by_id[finding_id],
            }
        )
    b198 = next(finding for finding in packet["findings"] if finding["finding_id"] == "B198")
    b198_occurrence = b198["occurrences"][0]
    packet["B198_preservation"] = {
        "finding_id": "B198",
        "occurrence_pointer": b198_occurrence["identity"]["occurrence_pointer"],
        "criterion_sha256": b198_occurrence["identity"]["criterion_sha256"],
        "historical_ledger_status": b198["historical_statuses"]["ledger_status"],
        "appendix_c_status": b198["historical_statuses"]["appendix_c_status"],
        "source_author_proposal": b198["source_author_proposal"]["disposition"],
        "prefreeze_technical_proposal": b198_occurrence["proposal"]["current_prefreeze_technical_disposition"],
        "candidate_evaluation": b198_occurrence["candidate_evaluation"]["state"],
        "formal_G": b198_occurrence["history_and_authority"]["formal_G_status"],
        "formal_closure": False,
        "qualification": "Prior source-author/historical decision is preserved; current technical proposal remains separate; candidate remains UNRUN; no formal closure is claimed.",
    }
    validate_packet(packet, coverage_keys)
    return packet, declaration, coverage_keys, identity


def packet_occurrence_rows(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten per-ID occurrence rows without deduplicating repeated IDs."""
    return [occurrence for finding in packet.get("findings", []) for occurrence in finding.get("occurrences", [])]


def validate_packet(packet: dict[str, Any], expected_keys: list[tuple[str, str, str]]) -> None:
    """Validate report behavior against independent canonical occurrence keys."""
    identity_helper = import_module("e02_registered_occurrence_identity_validation", repo_root() / IDENTITY_HELPER_REL)
    findings = packet.get("findings")
    require(isinstance(findings, list), "packet findings must be an array")
    ids = [finding.get("finding_id") for finding in findings]
    require(len(ids) == 282 and len(set(ids)) == 282, "packet must contain exactly 282 unique finding IDs")
    rows = packet_occurrence_rows(packet)
    actual_keys = []
    for index, row in enumerate(rows):
        identity = row.get("identity", {})
        key = (identity.get("finding_id"), identity.get("occurrence_pointer"), identity.get("criterion_sha256"))
        if not all(isinstance(value, str) and value for value in key):
            raise ValueError(f"packet row {index} has invalid identity")
        actual_keys.append(key)
        span = row.get("original_criterion_source", {})
        require(span.get("criterion_sha256") == key[2], f"criterion hash binding differs at row {index}")
        require(span.get("source_pointer") == key[1], f"coverage pointer binding differs at row {index}")
        require(span.get("current_worktree_span_sha256_matches_coverage") is True, f"source span hash marker is false at row {index}")
        candidate = row.get("candidate_evaluation", {})
        require(candidate.get("state") == "UNRUN", f"candidate result is not UNRUN at row {index}")
        require(candidate.get("attempts") == [], f"UNRUN row has candidate attempts at row {index}")
        require(candidate.get("evidence_refs") == [], f"UNRUN row has candidate evidence refs at row {index}")
        require(row.get("history_and_authority", {}).get("formal_G_status") == "not_adjudicated", f"formal G state changed at row {index}")
        require(row.get("history_and_authority", {}).get("formal_closure") is False, f"formal closure claimed at row {index}")
        require(row.get("next_check", {}).get("task_routes_navigation_only") is not None, f"next check missing at row {index}")
    require(packet.get("denominator", {}).get("canonical_occurrences") == 291, "declared occurrence count changed")
    require(len(rows) == 291, "packet actual occurrence count differs from declared denominator")
    identity_helper.require_same_occurrence_multiset(expected_keys, actual_keys, label="proposal decision packet")
    require(packet.get("authority_boundary", {}).get("formal_closure_ids") == [], "packet formal closure list must remain empty")
    require(packet.get("authority_boundary", {}).get("formal_G") == "not_adjudicated", "packet G authority must remain not_adjudicated")
    require(packet.get("authority_boundary", {}).get("source_freeze") == "provisional_source_checkpoint_not_frozen", "packet source freeze must remain provisional")

    author_by_id: dict[str, str] = {}
    author_occurrences: collections.Counter[str] = collections.Counter()
    tech_counts: collections.Counter[str] = collections.Counter()
    task_refs: list[str] = []
    for finding in findings:
        author = finding.get("source_author_proposal", {}).get("disposition")
        require(isinstance(author, str), f"missing source-author status for {finding.get('finding_id')}")
        author_by_id[finding["finding_id"]] = author
        author_occurrences[author] += len(finding.get("occurrences", []))
        for row in finding["occurrences"]:
            tech_counts[row["proposal"]["current_prefreeze_technical_disposition"]] += 1
            task_refs.extend(route["assignment_pointer"] for route in row["next_check"]["task_routes_navigation_only"])
    require(collections.Counter(author_by_id.values()) == collections.Counter({"closed": 198, "limited": 54, "held": 23, "open": 7}), "source-author per-ID status counts changed")
    require(author_occurrences["closed"] == 202, "source-author closed occurrence count changed")
    require(tech_counts == collections.Counter({"limited": 194, "open": 62, "held": 35}), "prefreeze technical proposal occurrence counts changed")
    require(len(set(task_refs)) == 319, "distinct task assignment reference count changed")
    require(len(task_refs) == 331, "expanded occurrence route reference count changed")
    b198 = packet.get("B198_preservation", {})
    require(
        (b198.get("historical_ledger_status"), b198.get("appendix_c_status"), b198.get("source_author_proposal"), b198.get("prefreeze_technical_proposal"), b198.get("candidate_evaluation"), b198.get("formal_G"), b198.get("formal_closure"))
        == ("closed", "closed_bounded", "closed", "limited", "UNRUN", "not_adjudicated", False),
        "B198 historical/source-author/current-proposal/candidate/G states were conflated or changed",
    )


def expect_rejection(name: str, packet: dict[str, Any], expected_keys: list[tuple[str, str, str]], identity: Any) -> dict[str, Any]:
    """Record one negative control only when the behavioral validator rejects."""
    try:
        validate_packet(packet, expected_keys)
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        return {"name": name, "result": "REJECTED_AS_REQUIRED", "reason": str(exc).splitlines()[0][:240]}
    raise ValueError(f"negative control accepted mutation: {name}")


def run_negative_controls(packet: dict[str, Any], expected_keys: list[tuple[str, str, str]], identity: Any) -> dict[str, Any]:
    """Exercise full identity and authority properties with corrupt packets."""
    rows = packet_occurrence_rows(packet)
    controls: list[dict[str, Any]] = []

    mutated = copy.deepcopy(packet)
    mutated["findings"][0]["occurrences"].pop(0)
    controls.append(expect_rejection("delete_occurrence_with_291_marker_preserved", mutated, expected_keys, identity))

    mutated = copy.deepcopy(packet)
    mutable_rows = packet_occurrence_rows(mutated)
    first, second = copy.deepcopy(mutable_rows[0]), copy.deepcopy(mutable_rows[1])
    first_id = first["identity"]["finding_id"]
    first_pointer = first["identity"]["occurrence_pointer"]
    original_finding = next(item for item in mutated["findings"] if item["finding_id"] == first_id)
    original_finding["occurrences"] = [row for row in original_finding["occurrences"] if row["identity"]["occurrence_pointer"] != first_pointer]
    second_id = second["identity"]["finding_id"]
    second_finding = next(item for item in mutated["findings"] if item["finding_id"] == second_id)
    second_finding["occurrences"].append(second)
    controls.append(expect_rejection("count_preserving_delete_plus_duplicate", mutated, expected_keys, identity))

    mutated = copy.deepcopy(packet)
    mutable_rows = packet_occurrence_rows(mutated)
    first = mutable_rows[0]
    first["identity"]["criterion_sha256"] = "0" * 64
    controls.append(expect_rejection("count_preserving_criterion_sha_mutation", mutated, expected_keys, identity))

    mutated = copy.deepcopy(packet)
    packet_occurrence_rows(mutated)[0]["original_criterion_source"]["current_worktree_span_sha256_matches_coverage"] = False
    controls.append(expect_rejection("source_span_hash_marker_corruption", mutated, expected_keys, identity))

    mutated = copy.deepcopy(packet)
    packet_occurrence_rows(mutated)[0]["candidate_evaluation"]["state"] = "PASS"
    controls.append(expect_rejection("candidate_promotion_without_admitted_attempt", mutated, expected_keys, identity))

    mutated = copy.deepcopy(packet)
    packet_occurrence_rows(mutated)[0]["candidate_evaluation"]["attempts"] = [{"status": "PASS"}]
    controls.append(expect_rejection("candidate_attempt_marker_without_source_bound_execution", mutated, expected_keys, identity))

    altered_basis = list(expected_keys)
    first_key = altered_basis[0]
    altered_basis[0] = (first_key[0], first_key[1], "f" * 64)
    try:
        identity.require_same_occurrence_multiset(expected_keys, altered_basis, label="criterion mutation source control")
    except ValueError as exc:
        criterion_helper_rejected = True
        criterion_helper_reason = str(exc).splitlines()[0][:240]
    else:
        raise ValueError("criterion mutation control unexpectedly accepted substituted criterion digest")

    return {
        "schema": "policyos.e02.q0_full_occurrence_report_controls.v1",
        "status": "PASS",
        "property": "A report is admitted only when the full multiset (finding_id, coverage_pointer, criterion_sha256), whole-property/source bindings, candidate status, and authority boundaries match the producer inputs.",
        "positive": {
            "exact_multiset": "PASS",
            "unique_keys": len(set(expected_keys)),
            "rows": len(rows),
            "candidate_states": "291 UNRUN",
        },
        "negative_controls": controls,
        "standalone_source_sha_mutation": {
            "result": "PASS",
            "helper_rejection": criterion_helper_rejected,
            "helper_reason": criterion_helper_reason,
            "method": "A count-preserving criterion digest substitution is rejected by the packet validator and exact multiset helper.",
        },
    }


def write_json(path: Path, value: dict[str, Any]) -> bytes:
    """Write stable UTF-8 JSON and return the exact bytes written."""
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


def emit() -> dict[str, Any]:
    """Build and write the packet and its semantic mutation controls."""
    root = repo_root()
    packet, _, expected_keys, identity = build_packet()
    controls = run_negative_controls(packet, expected_keys, identity)
    packet_bytes = write_json(root / PACKET_REL, packet)
    controls_bytes = write_json(root / CONTROLS_REL, controls)
    return {
        "status": "PASS",
        "mode": "emit",
        "packet_path": PACKET_REL.as_posix(),
        "packet_sha256": sha256_bytes(packet_bytes),
        "packet_bytes": len(packet_bytes),
        "controls_path": CONTROLS_REL.as_posix(),
        "controls_sha256": sha256_bytes(controls_bytes),
        "denominator": packet["denominator"],
        "candidate_states": packet["status_summary"]["candidate_evaluation_by_occurrence"],
    }


def check() -> dict[str, Any]:
    """Rebuild from source and validate the persisted packet byte-for-byte."""
    root = repo_root()
    expected_packet, _, expected_keys, identity = build_packet()
    persisted = read_json(root, PACKET_REL)
    validate_packet(persisted, expected_keys)
    expected_bytes = (json.dumps(expected_packet, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    persisted_bytes = (root / PACKET_REL).read_bytes()
    require(persisted_bytes == expected_bytes, "persisted proposal decision packet differs from current registered producer inputs")
    controls = run_negative_controls(persisted, expected_keys, identity)
    persisted_controls = read_json(root, CONTROLS_REL)
    require(persisted_controls == controls, "persisted negative controls differ from fresh control run")
    return {
        "status": "PASS",
        "mode": "check",
        "packet_sha256": sha256_bytes(persisted_bytes),
        "controls_sha256": sha256_path(root, CONTROLS_REL),
        "exact_multiset_rows": len(expected_keys),
        "count_preserving_controls": len(controls["negative_controls"]),
    }


def finalize_manifest() -> dict[str, Any]:
    """Write a source/output hash manifest for this local report lease."""
    root = repo_root()
    declaration = read_json(root, DECLARATION_REL)
    load_declared_sources(root, declaration)
    packet = read_json(root, PACKET_REL)
    controls = read_json(root, CONTROLS_REL)
    checks = read_json(root, CHECKS_REL / "source-bound-checks.json")
    source_preimages = []
    for item in declaration["source_preimages"]:
        data = (root / item["path"]).read_bytes()
        require(sha256_bytes(data) == item["sha256"] and len(data) == item["bytes"], f"manifest source preimage mismatch: {item['path']}")
        source_preimages.append({"path": item["path"], "bytes": len(data), "sha256": sha256_bytes(data)})
    artifact_paths = [
        DECLARATION_REL,
        LEASE_REL / "virtual_emitter.py",
        LEASE_REL / "virtual-emitter.patch",
        PACKET_REL,
        CONTROLS_REL,
        CHECKS_REL / "source-bound-checks.json",
        *sorted(CHECKS_REL.glob("*.txt")),
    ]
    artifacts = []
    for relative in artifact_paths:
        path = root / relative
        if not path.is_file():
            raise ValueError(f"manifest artifact missing: {relative}")
        data = path.read_bytes()
        artifacts.append({"path": relative.as_posix(), "bytes": len(data), "sha256": sha256_bytes(data)})
    manifest = {
        "schema": "policyos.e02.q0_full_occurrence_report_manifest.v1",
        "status": "PROVISIONAL_SOURCE_QUALIFIED_REPORT_VERIFIED",
        "source_checkpoint": packet["source_checkpoint"],
        "authority_boundary": packet["authority_boundary"],
        "denominator": packet["denominator"],
        "source_preimages": source_preimages,
        "generated_artifacts": artifacts,
        "command_results": checks,
        "control_status": controls["status"],
        "manifest_self_reference": "Omitted by construction; this manifest lists the exact source and output files it binds.",
        "qualification": "This is an author handoff artifact. It does not establish final candidate-source freeze, candidate execution, or formal G adjudication.",
    }
    write_json(root / MANIFEST_REL, manifest)
    return {
        "status": "PASS",
        "mode": "finalize_manifest",
        "manifest_path": MANIFEST_REL.as_posix(),
        "source_preimages": len(source_preimages),
        "generated_artifacts": len(artifacts),
        "command_results": checks.get("commands", {}),
    }


def main() -> int:
    """Run local report emission, readback validation, or manifest finalization."""
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--emit", action="store_true", help="build the provisional packet and controls")
    modes.add_argument("--check", action="store_true", help="rebuild and validate persisted packet and controls")
    modes.add_argument("--finalize-manifest", action="store_true", help="write the final source/output manifest")
    args = parser.parse_args()
    if args.emit:
        result = emit()
    elif args.check:
        result = check()
    else:
        result = finalize_manifest()
    print(json.dumps(result, ensure_ascii=False, indent=2))  # noqa: T201 -- CLI JSON output.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
