#!/usr/bin/env python3
"""Run I7-bis universal compilation integration realism check."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.argument_graph import (
    build_argument_graph,
    inspect_argument_graph,
)
from tools.quality.validation import (
    generate_policy_evidence_capability_cards as cards,
)
from tools.quality.validation import run_universal_outcome_corpus as w12d

SCHEMA_VERSION = "policyos.policy_design_case.i7bis.integration_realism.v1"
TOOL_NAME = "quality.validation.run-universal-compilation-integration-realism-check"
PHASE_ID = "I7-bis"
DEFAULT_CASE = Path("tests/fixtures/universal-corpus/cases/ua-msme-affordable-loans-2022.json")
DEFAULT_PRODUCER_STUB_DIR = Path("tests/fixtures/universal-corpus/producer_stubs")
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/i7bis_integration_realism_check.json")
DEFAULT_GRAPH_OUTPUT_DIR = Path("_build/.tmp/production-quality/i7bis-runtime-pdc-graphs")
DEFAULT_HYPOTHESIS_LEDGER_DIR = Path("_build/.tmp/production-quality/i7bis-hypothesis-ledgers")
DEFAULT_AUDIT_CARD_DIR = Path("_build/.tmp/production-quality/i7bis-capability-cards")
DEFAULT_CAPABILITY_INDEX = w12d.DEFAULT_CAPABILITY_INDEX


def run_i7bis_universal_compilation_integration_realism_check(
    *,
    repo_root: str | Path = REPO_ROOT,
    case_path: str | Path = DEFAULT_CASE,
    producer_stub_dir: str | Path = DEFAULT_PRODUCER_STUB_DIR,
    graph_output_dir: str | Path = DEFAULT_GRAPH_OUTPUT_DIR,
    hypothesis_ledger_output_dir: str | Path = DEFAULT_HYPOTHESIS_LEDGER_DIR,
    audit_card_output_dir: str | Path = DEFAULT_AUDIT_CARD_DIR,
    capability_index_path: str | Path | None = DEFAULT_CAPABILITY_INDEX,
) -> dict[str, Any]:
    """Run one complete W6/W7/W8 path and report missing integration links."""

    root = Path(repo_root).resolve()
    w12d_report = w12d.run_w12d_universal_outcome_corpus(
        repo_root=root,
        corpus_path=_resolve(root, case_path),
        graph_output_dir=_resolve(root, graph_output_dir),
        hypothesis_ledger_output_dir=_resolve(root, hypothesis_ledger_output_dir),
        mode="corpus_stub",
        producer_stub_dir=_resolve(root, producer_stub_dir),
        capability_index_path=(
            _resolve(root, capability_index_path)
            if capability_index_path is not None
            else None
        ),
    )
    case = _first_case(w12d_report)
    audit_card_manifest = _generate_audit_cards(
        repo_root=root,
        capability_index_path=capability_index_path,
        audit_card_output_dir=audit_card_output_dir,
    )
    checks = _checks(case, repo_root=root, audit_card_manifest=audit_card_manifest)
    typed_blockers = [
        _typed_blocker(code=code, message=message, check_id=check_id)
        for check_id, row in checks.items()
        if row["status"] != "pass"
        for code, message in ((row["blocker_code"], row["message"]),)
    ]
    authority_boundary = dict(_mapping(case.get("corpus_stub")))
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "phase_id": PHASE_ID,
        "status": "blocked" if typed_blockers else "pass",
        "repo_root": str(root),
        "case_id": case.get("case_id"),
        "underlying_w12d_status": w12d_report.get("status"),
        "checks": checks,
        "typed_blockers": typed_blockers,
        "audit_card_manifest": audit_card_manifest,
        "authority_boundary": authority_boundary,
        "pattern_pass": {
            "relevant_patterns": ["P01", "P02", "P05", "P10", "P12", "P15"],
            "target_correct_pattern": (
                "One toy policy intent exercises grammar, governed rules, LLM "
                "formulator, critic ensemble, hypothesis ledger, requirement specs, "
                "producer pipeline, runtime PDC graph, and graph warrant visibility."
            ),
            "missing_capability_labels": [
                row["missing_capability_label"]
                for row in checks.values()
                if row["status"] != "pass"
            ],
        },
        "w12d_summary": w12d_report.get("summary"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for I7-bis integration realism check."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--case", type=Path, default=DEFAULT_CASE)
    parser.add_argument("--producer-stub-dir", type=Path, default=DEFAULT_PRODUCER_STUB_DIR)
    parser.add_argument("--graph-output-dir", type=Path, default=DEFAULT_GRAPH_OUTPUT_DIR)
    parser.add_argument(
        "--hypothesis-ledger-output-dir",
        type=Path,
        default=DEFAULT_HYPOTHESIS_LEDGER_DIR,
    )
    parser.add_argument("--audit-card-output-dir", type=Path, default=DEFAULT_AUDIT_CARD_DIR)
    parser.add_argument("--capability-index", type=Path, default=DEFAULT_CAPABILITY_INDEX)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--allow-typed-blockers", action="store_true")
    args = parser.parse_args(argv)

    report = run_i7bis_universal_compilation_integration_realism_check(
        repo_root=args.repo_root,
        case_path=args.case,
        producer_stub_dir=args.producer_stub_dir,
        graph_output_dir=args.graph_output_dir,
        hypothesis_ledger_output_dir=args.hypothesis_ledger_output_dir,
        audit_card_output_dir=args.audit_card_output_dir,
        capability_index_path=args.capability_index,
    )
    output = _resolve(Path(args.repo_root).resolve(), args.output)
    atomic_write_json(output, report)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if report["status"] == "pass" or args.allow_typed_blockers:
        return 0
    return 1


def _checks(
    case: Mapping[str, Any],
    *,
    repo_root: Path,
    audit_card_manifest: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    llm = _mapping(case.get("llm_universal_compilation"))
    formulator = _mapping(llm.get("formulator"))
    critic = _mapping(llm.get("critic_ensemble"))
    firewall = _mapping(llm.get("candidate_firewall"))
    pipeline = _mapping(case.get("producer_pipeline"))
    graph = _mapping(case.get("runtime_pdc_graph"))
    capability_graph = _mapping(case.get("capability_graph_trace"))
    capability_bindings = _sequence_of_mappings(capability_graph.get("capability_bindings"))
    argument_graph_observed = _argument_graph_observed(case, repo_root=repo_root)
    return {
        "capability_index_loaded": _check(
            passed=bool(capability_graph.get("capability_index_loaded"))
            and bool(capability_graph.get("capability_index_ref")),
            blocker_code="i7bis_capability_index_not_loaded",
            missing_label="artifact_missing",
            message="Capability index was not loaded before producer binding.",
            observed={
                "capability_index_ref": capability_graph.get("capability_index_ref"),
                "status": capability_graph.get("status"),
            },
        ),
        "construct_registry_loaded": _check(
            passed=bool(capability_graph.get("construct_registry_loaded"))
            and bool(capability_graph.get("construct_registry_ref")),
            blocker_code="i7bis_construct_registry_not_loaded",
            missing_label="artifact_missing",
            message="Construct registry ref was not loaded for capability bindings.",
            observed={
                "construct_registry_ref": capability_graph.get("construct_registry_ref"),
                "artifact_ref": capability_graph.get("construct_registry_artifact_ref"),
            },
        ),
        "capability_resolver_executed": _check(
            passed=bool(capability_graph.get("resolver_executed"))
            and int(capability_graph.get("binding_count") or 0) > 0,
            blocker_code="i7bis_capability_resolver_not_executed",
            missing_label="bridge_missing",
            message="Requirement-to-capability resolver did not emit binding results.",
            observed={
                "resolver_executed": capability_graph.get("resolver_executed"),
                "binding_count": capability_graph.get("binding_count"),
                "issue_codes": capability_graph.get("issue_codes"),
            },
        ),
        "selected_capability_binding": _check(
            passed=any(
                str(binding.get("status", "")).startswith("selected_")
                for binding in capability_bindings
            ),
            blocker_code="i7bis_capability_binding_status_missing",
            missing_label="semantic_test_missing",
            message=(
                "Capability resolver executed without at least one selected binding."
            ),
            observed={
                "statuses": sorted(
                    {str(binding.get("status")) for binding in capability_bindings}
                ),
                "binding_count": len(capability_bindings),
            },
        ),
        "typed_blocked_capability_binding": _check(
            passed=any(
                str(binding.get("status", "")).startswith("blocked_")
                for binding in capability_bindings
            ),
            blocker_code="i7bis_typed_blocked_binding_missing",
            missing_label="semantic_test_missing",
            message=(
                "Capability resolver executed without at least one typed-blocked "
                "binding status."
            ),
            observed={
                "statuses": sorted(
                    {str(binding.get("status")) for binding in capability_bindings}
                ),
                "binding_count": len(capability_bindings),
            },
        ),
        "rejected_alternative_recorded": _check(
            passed=any(binding.get("rejected_alternatives") for binding in capability_bindings),
            blocker_code="i7bis_rejected_alternative_missing",
            missing_label="semantic_test_missing",
            message="Capability bindings did not preserve rejected alternatives.",
            observed={
                "rejected_alternative_count": sum(
                    len(_sequence(binding.get("rejected_alternatives")))
                    for binding in capability_bindings
                )
            },
        ),
        "llm_formulator_invoked": _check(
            passed=int(formulator.get("candidate_count") or 0) > 0,
            blocker_code="i7bis_llm_formulator_missing",
            missing_label="implemented_but_not_orchestrated",
            message="LLM formulator did not emit candidates in the runtime path.",
            observed={"candidate_count": formulator.get("candidate_count")},
        ),
        "critic_ensemble_invoked": _check(
            passed=int(critic.get("verdict_count") or 0) > 0,
            blocker_code="i7bis_critic_ensemble_missing",
            missing_label="implemented_but_not_orchestrated",
            message="Multi-critic ensemble did not emit verdicts in the runtime path.",
            observed={"verdict_count": critic.get("verdict_count")},
        ),
        "hypothesis_ledger_persisted": _check(
            passed=bool(llm.get("hypothesis_ledger_artifact_ref")),
            blocker_code="i7bis_hypothesis_ledger_artifact_missing",
            missing_label="artifact_missing",
            message="Hypothesis ledger artifact was not persisted for the case.",
            observed={"artifact_ref": llm.get("hypothesis_ledger_artifact_ref")},
        ),
        "producer_pipeline_bound": _check(
            passed=pipeline.get("status") == "pass",
            blocker_code="i7bis_producer_pipeline_not_bound",
            missing_label="bridge_missing",
            message="Requirement specs did not bind through the producer pipeline.",
            observed={"status": pipeline.get("status"), "stage_count": pipeline.get("stage_count")},
        ),
        "producer_binding_emitted": _check(
            passed=int(pipeline.get("producer_binding_decision_count") or 0) > 0
            and int(pipeline.get("claim_binding_count") or 0) > 0,
            blocker_code="i7bis_producer_binding_not_emitted",
            missing_label="bridge_missing",
            message="Producer pipeline did not emit capability-backed claim bindings.",
            observed={
                "producer_binding_decision_count": pipeline.get(
                    "producer_binding_decision_count"
                ),
                "claim_binding_count": pipeline.get("claim_binding_count"),
                "capability_ref_count": pipeline.get("capability_ref_count"),
                "construct_ref_count": pipeline.get("construct_ref_count"),
            },
        ),
        "audit_card_generated": _check(
            passed=(
                audit_card_manifest.get("status") == "pass"
                and int(audit_card_manifest.get("card_count") or 0) > 0
            ),
            blocker_code="i7bis_audit_card_generation_missing",
            missing_label="surface_missing",
            message="Capability audit cards were not generated for the loaded index.",
            observed={
                "status": audit_card_manifest.get("status"),
                "card_count": audit_card_manifest.get("card_count"),
                "output_dir": audit_card_manifest.get("output_dir"),
            },
        ),
        "candidate_firewall_enforced_with_audit": _check(
            passed=isinstance(firewall.get("issues"), list)
            and bool(llm.get("hypothesis_ledger_artifact_ref")),
            blocker_code="i7bis_candidate_firewall_audit_missing",
            missing_label="verification_missing",
            message=(
                "Candidate firewall did not expose an auditable runtime check "
                "alongside the persisted hypothesis ledger."
            ),
            observed={
                "issue_count": firewall.get("issue_count"),
                "authority_slots": firewall.get("authority_slots"),
                "hypothesis_ledger_artifact_ref": llm.get(
                    "hypothesis_ledger_artifact_ref"
                ),
            },
        ),
        "runtime_pdc_graph_emitted": _check(
            passed=graph.get("status") == "pass" and int(graph.get("edge_count") or 0) > 0,
            blocker_code="i7bis_runtime_pdc_graph_missing",
            missing_label="consumer_missing",
            message="Runtime PDC graph did not materialize with non-zero edges.",
            observed={"status": graph.get("status"), "edge_count": graph.get("edge_count")},
        ),
        "nonzero_warrants": _check(
            passed=(
                argument_graph_observed.get("argument_graph_inspection_status") == "pass"
                and int(argument_graph_observed.get("machine_inspectable_warrant_count") or 0)
                > 0
            ),
            blocker_code="i7bis_warrant_structure_missing",
            missing_label="bridge_missing",
            message=(
                "W8.B argument graph has no machine-inspectable warrants from "
                "selected bindings."
            ),
            observed=argument_graph_observed,
        ),
    }


def _generate_audit_cards(
    *,
    repo_root: Path,
    capability_index_path: str | Path | None,
    audit_card_output_dir: str | Path,
) -> Mapping[str, Any]:
    if capability_index_path is None:
        return {"status": "not_run", "card_count": 0, "reason": "capability_index_missing"}
    index_path = _resolve(repo_root, capability_index_path)
    if not index_path.exists():
        return {"status": "blocked", "card_count": 0, "reason": "capability_index_missing"}
    try:
        return cards.generate_capability_cards(
            capability_index_path=index_path,
            output_dir=_resolve(repo_root, audit_card_output_dir),
        )
    except Exception as exc:  # pragma: no cover - defensive operator reporting.
        return {"status": "blocked", "card_count": 0, "reason": str(exc)}


def _argument_graph_observed(case: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    graph = _mapping(case.get("runtime_pdc_graph"))
    evidence_graph = _mapping(case.get("evidence_bound_pdc_graph"))
    artifact_ref = str(evidence_graph.get("artifact_ref") or "")
    graph_path = _resolve_artifact_ref(repo_root, artifact_ref)
    observed: dict[str, Any] = {
        "runtime_warrant_structure_count": graph.get("warrant_structure_count"),
        "artifact_ref": artifact_ref or None,
    }
    if graph_path is None or not graph_path.exists():
        observed["argument_graph_inspection_status"] = "missing"
        return observed
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        observed["argument_graph_inspection_status"] = "invalid"
        return observed
    argument_graph = build_argument_graph(payload)
    inspection = inspect_argument_graph(argument_graph)
    summary = _mapping(inspection.get("summary"))
    observed.update(
        {
            "argument_graph_status": argument_graph.get("status"),
            "argument_graph_inspection_status": inspection.get("status"),
            "machine_inspectable_warrant_count": int(
                summary.get("machine_inspectable_warrant_count") or 0
            ),
            "complete_claim_path_count": int(summary.get("complete_claim_path_count") or 0),
        }
    )
    return observed


def _resolve_artifact_ref(repo_root: Path, ref: str) -> Path | None:
    if not ref:
        return None
    if "#" in ref:
        ref = ref.split("#", 1)[0]
    if ref.startswith("repo://"):
        value = ref.removeprefix("repo://")
        candidate = Path(value)
        return candidate if candidate.is_absolute() else repo_root / candidate
    candidate = Path(ref)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _check(
    *,
    passed: bool,
    blocker_code: str,
    missing_label: str,
    message: str,
    observed: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "status": "pass" if passed else "blocked",
        "blocker_code": blocker_code,
        "missing_capability_label": "" if passed else missing_label,
        "message": "ok" if passed else message,
        "observed": dict(observed),
    }


def _typed_blocker(*, code: str, message: str, check_id: str) -> dict[str, Any]:
    return {
        "code": code,
        "phase_id": PHASE_ID,
        "check_id": check_id,
        "severity": "blocker",
        "message": message,
        "next_action": "Wire the missing integration signal before Wave 6/W12 exit.",
    }


def _first_case(report: Mapping[str, Any]) -> Mapping[str, Any]:
    cases = report.get("cases")
    if isinstance(cases, Sequence) and cases and isinstance(cases[0], Mapping):
        return cases[0]
    return {}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, str):
        return tuple(value)
    return ()


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    return tuple(item for item in _sequence(value) if isinstance(item, Mapping))


def _resolve(root: Path, path: str | Path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else root / candidate


if __name__ == "__main__":
    raise SystemExit(main())
