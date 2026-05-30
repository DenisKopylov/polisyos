#!/usr/bin/env python3
"""Run W12.D universal outcome corpus evidence over W6/W7/W8."""

from __future__ import annotations

# ruff: noqa: ANN401
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.runner import render_command

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.core.contracts.capability_resolution import (  # noqa: E402
    RequirementToCapabilityQuery,
    construct_for_legacy_family,
)
from polisyos.core.contracts.runtime import UniversalAuthorityProfile  # noqa: E402
from polisyos.ir.governance.policy_composition import PolicyLayerLevel  # noqa: E402
from polisyos.ir.governance.problem_frame import ProblemDomain  # noqa: E402
from polisyos.obligation_graph import (  # noqa: E402
    ComplexityBudget,
    ObligationGraph,
    compile_obligation_graph,
)
from polisyos.obligation_rules import build_seed_obligation_rule_catalog  # noqa: E402
from polisyos.pdc import (  # noqa: E402
    Layer2S2DesignSearchInput,
    run_s2_shadow_design_loop,
)
from polisyos.policy_grammar import (  # noqa: E402
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)
from polisyos.runtime.quality.capability_resolver import (  # noqa: E402
    RequirementToCapabilityResolver,
)
from polisyos.runtime.quality.closeout_reader import (  # noqa: E402
    build_can_i_closeout_verdict,
)
from polisyos.runtime.quality.graded_outcomes import (  # noqa: E402
    S1_GRADED_OUTCOME_SCHEMA_VERSION,
    GradedOutcomeDecision,
    GradedOutcomeEvidenceInput,
    compose_graded_outcome,
    graded_outcome_closeout_record,
)
from polisyos.runtime.quality.hypothesis_ledger import (  # noqa: E402
    HYPOTHESIS_LEDGER_SCHEMA_VERSION,
    HypothesisLedger,
    serialize_hypothesis_ledger,
)
from polisyos.runtime.quality.producer_pipeline import (  # noqa: E402
    run_requirement_spec_producer_pipeline,
)
from polisyos.runtime.quality.producer_pipeline_corpus_stub import (  # noqa: E402
    corpus_stub_authority_boundary,
    load_corpus_stub_responses,
)
from polisyos.scientist.policy_design.claim_decomposition import (  # noqa: E402
    ClaimDecompositionCompiler,
)
from polisyos.scientist.policy_design.critic_ensemble import (  # noqa: E402
    MultiCriticEnsemble,
)
from polisyos.scientist.policy_design.critic_obligation_bridge import (  # noqa: E402
    critic_consensus_to_obligation_candidates,
)
from polisyos.scientist.policy_design.formulator import (  # noqa: E402
    InMemoryHypothesisLedger,
    LLMFormulator,
    LLMFormulatorInput,
)

SCHEMA_VERSION = "policyos.policy_design_case.w12d.universal_outcome_corpus_run.v1"
MANIFEST_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave12d.universal_outcome_corpus_run_manifest.v1"
)
TOOL_NAME = "quality.validation.run-universal-outcome-corpus"
GENERATED_AT = "2026-05-25T00:00:00Z"
PHASE_ID = "W12.D"
PHASE_NAME = "Universal Outcome Corpus Run"
DEFAULT_CORPUS_PATH = Path("tests/fixtures/universal-corpus")
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json")
DEFAULT_GRAPH_OUTPUT_DIR = Path("_build/.tmp/production-quality/w12d-runtime-pdc-graphs")
DEFAULT_HYPOTHESIS_LEDGER_DIR = Path(
    "_build/.tmp/production-quality/w12d-hypothesis-ledgers"
)
DEFAULT_CRITIC_REPORT_DIR = Path("_build/.tmp/production-quality/w12d-critic-reports")
DEFAULT_PRODUCER_STUB_DIR = Path("tests/fixtures/universal-corpus/producer_stubs")
DEFAULT_CAPABILITY_INDEX = Path(
    "_build/.tmp/production-quality/capability-index/capability_index_v1.duckdb"
)
DEFAULT_CONSTRUCT_REGISTRY = Path("architecture/policy_design_case/construct_registry_v1.yaml")
DEFAULT_MANIFEST_OUTPUT = Path(
    "architecture/policy_design_case/wave12d_universal_outcome_corpus_run_manifest.json"
)
DEFAULT_AUTHORITY_COMPOSITION_RULE_REF = "capability-authority-v1.0"
W12D_FORMULATOR_TOOL_REFS: tuple[str, ...] = (
    "tool:w12d.universal_outcome_corpus_run",
    "tool:llm_formulator_runtime",
)
W12D_FORMULATOR_REPAIR_LINEAGE: tuple[str, ...] = (
    "repair:none",
)
# Authority slots the W6.F firewall must keep candidates out of when the
# universal compilation pipeline drives downstream readers. The slots match the
# default ``CANDIDATE_AUTHORITY_SLOTS`` from ``candidate_firewall`` and are
# pinned here so test fixtures and production runs stay in lockstep.
W12D_FIREWALL_AUTHORITY_SLOTS: tuple[str, ...] = (
    "obligation_authority",
    "claim_authority",
    "legal_authority",
    "data_authority",
    "method_authority",
    "participation_authority",
    "closeout_authority",
    "projection_authority",
)
AUTHORITY_LEVELS = ("research", "governed", "production")
OUTCOMES = ("pass", "publish-with-limitation", "accepted_deficit", "typed_blocker")
USEFUL_DESIGN_OUTCOMES = ("pass", "publish-with-limitation")
EXPERT_LABEL_EXPECTED_OUTCOME: Mapping[str, str] = {
    "semantic_pass": "pass",
    "limitation_required": "publish-with-limitation",
    "contested": "accepted_deficit",
    "reviewer_disagreement": "accepted_deficit",
    "unsupported": "typed_blocker",
    "false_pass": "typed_blocker",
    "fabricated_unverifiable": "typed_blocker",
}
PATTERN_REFS = ("P01", "P02", "P03", "P05", "P10", "P12", "P13", "P15")
ACTIONABLE_CAPABILITY_BLOCKER_CODES = frozenset(
    {
        "blocked_construct_not_observed",
        "blocked_acquisition_required",
        "blocked_construct_validity_below_floor",
        "blocked_sample_size_below_floor",
        "blocked_rights_boundary",
        "blocked_authority_boundary",
    }
)


class W12DCaseRunError(ValueError):
    """Raised when a corpus case cannot produce W12.D runtime evidence."""


def build_w12d_universal_outcome_corpus_report(
    *,
    case_results: Sequence[Mapping[str, Any]],
    repo_root: str | Path = REPO_ROOT,
    corpus_ref: str,
    mode: str = "real_producer",
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Build the canonical W12.D corpus evidence report from case results."""

    cases = [dict(result) for result in case_results]
    typed_blockers = [
        _typed_blocker_from_case(blocker, case)
        for case in cases
        for blocker in _sequence_of_mappings(case.get("typed_blockers"))
    ]
    rollout_blockers = [
        blocker for blocker in typed_blockers if blocker.get("blocks_rollout_posture")
    ]
    summary = _summary(cases)
    status = "blocked" if rollout_blockers else "pass"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": generated_at,
        "repo_root": str(Path(repo_root).resolve()),
        "corpus_ref": corpus_ref,
        "mode": mode,
        "synthetic_fixture_substitution_allowed": False,
        "status": status,
        "summary": summary,
        "cases": cases,
        "authority_level_metric_stratification": _authority_stratification(cases),
        "domain_authority_metric_stratification": _domain_authority_stratification(cases),
        "typed_blockers": typed_blockers,
        "rollout_blockers": rollout_blockers,
        "metric_policy": {
            "useful_design_outcomes": list(USEFUL_DESIGN_OUTCOMES),
            "typed_blockers_count_as_useful_design": False,
            "accepted_deficits_count_as_useful_design": False,
            "synthetic_fixtures_count_as_canonical_evidence": False,
            "pdc_graph_authoritative_for": ["pdc_graph_structure"],
            "pdc_graph_may_not_use_for": ["projection_authority", "claim_authority"],
            "corpus_stub_max_authority_posture": "governed-pilot",
            "corpus_stub_may_not_use_for": ["production_closeout_authority"],
        },
        "capability_trace": {
            "capability_id": "w12d_universal_outcome_corpus_run",
            "capability_reality_label": "implemented",
            "typed_contract_ref": "repo://tools/quality/validation/run_universal_outcome_corpus.py",
            "producer_ref": "repo://src/polisyos/runtime/quality/producer_pipeline.py",
            "artifact_ref": corpus_ref,
            "bridge_ref": "repo://tools/quality/validation/run_universal_outcome_corpus.py",
            "consumer_ref": "repo://tools/quality/validation/run_universal_outcome_corpus.py",
            "verification_ref": (
                "repo://tests/repo_quality/tools/"
                "test_w12d_universal_outcome_corpus_run.py"
            ),
            "surface_ref": "repo://tools/quality/validation/README.md#w12d-universal-outcome-corpus-run",
            "semantic_test_ref": (
                "repo://tests/repo_quality/tools/"
                "test_w12d_universal_outcome_corpus_run.py"
                "#test_w12d_runs_single_real_case_through_w6_w7_w8"
            ),
            "missing_capability_labels": [],
        },
        "pattern_pass": {
            "relevant_patterns": list(PATTERN_REFS),
            "target_correct_pattern": (
                "W12.D records real W11 corpus cases through W6 compilation, W7 "
                "producer pipeline, W8.A graph evidence, and W11.C adjudication "
                "delta without letting synthetic fixtures or graph packaging mint "
                "projection or claim authority."
            ),
            "missing_capability_labels": [],
        },
    }


def build_w12d_manifest() -> dict[str, Any]:
    """Build the deterministic W12.D command contract manifest."""

    command = (
        "uv",
        "run",
        "python",
        "tools/quality/validation/run_universal_outcome_corpus.py",
        "--repo-root",
        ".",
        "--corpus",
        DEFAULT_CORPUS_PATH.as_posix(),
        "--output",
        DEFAULT_OUTPUT.as_posix(),
        "--capability-index",
        DEFAULT_CAPABILITY_INDEX.as_posix(),
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "implemented",
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": GENERATED_AT,
        "owner": "team-evaluation",
        "implementation_plan_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            "#w12d-universal-outcome-corpus-run"
        ),
        "tool_ref": "repo://tools/quality/validation/run_universal_outcome_corpus.py",
        "command_contract": {
            "command": render_command(command),
            "output_refs": [
                DEFAULT_OUTPUT.as_posix(),
                DEFAULT_GRAPH_OUTPUT_DIR.as_posix(),
            ],
            "synthetic_fixture_substitution_allowed": False,
            "owner": "team-evaluation",
            "next_action": (
                "Repair any W6/W7/W8 typed blockers or adjudication deltas before "
                "using the corpus run as universal-capability rollout evidence."
            ),
        },
        "w6_w7_w8_chain": {
            "universal_compilation_kernel": "W6",
            "producer_pipeline": "W7",
            "runtime_pdc_graph": "W8.A",
        },
        "metric_policy": {
            "useful_design_outcomes": list(USEFUL_DESIGN_OUTCOMES),
            "typed_blockers_count_as_useful_design": False,
            "accepted_deficits_count_as_useful_design": False,
            "synthetic_fixtures_count_as_canonical_evidence": False,
        },
        "pattern_pass": {
            "relevant_patterns": list(PATTERN_REFS),
            "target_correct_pattern": (
                "W12.D is the canonical real-corpus run over W6/W7/W8 with "
                "expert-adjudication deltas and authority-level stratification."
            ),
            "missing_capability_labels": [],
        },
        "validation": {
            "test_ref": (
                "repo://tests/repo_quality/tools/test_w12d_universal_outcome_corpus_run.py"
            ),
            "command_ref": render_command(command),
        },
    }


def run_w12d_universal_outcome_corpus(
    *,
    repo_root: str | Path = REPO_ROOT,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    graph_output_dir: str | Path = DEFAULT_GRAPH_OUTPUT_DIR,
    hypothesis_ledger_output_dir: str | Path = DEFAULT_HYPOTHESIS_LEDGER_DIR,
    critic_report_output_dir: str | Path = DEFAULT_CRITIC_REPORT_DIR,
    mode: str = "real_producer",
    producer_stub_dir: str | Path = DEFAULT_PRODUCER_STUB_DIR,
    capability_index_path: str | Path | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Run every corpus case through W6, W7, and W8.A graph assembly."""

    root = Path(repo_root).resolve()
    corpus = _resolve(root, Path(corpus_path))
    graph_dir = _resolve(root, Path(graph_output_dir))
    ledger_dir = _resolve(root, Path(hypothesis_ledger_output_dir))
    critic_dir = _resolve(root, Path(critic_report_output_dir))
    stub_dir = _resolve(root, Path(producer_stub_dir))
    capability_index = (
        _resolve(root, Path(capability_index_path))
        if capability_index_path is not None
        else None
    )
    if mode not in {"real_producer", "corpus_stub"}:
        raise ValueError(f"unknown W12.D mode: {mode}")
    cases, load_issues = _load_cases(corpus)
    case_results = [
        _run_case(
            case,
            repo_root=root,
            graph_output_dir=graph_dir,
            hypothesis_ledger_output_dir=ledger_dir,
            critic_report_output_dir=critic_dir,
            mode=mode,
            producer_stub_dir=stub_dir,
            capability_index_path=capability_index,
        )
        for case in cases
    ]
    for issue in load_issues:
        case_results.append(_load_issue_case_result(issue))
    return build_w12d_universal_outcome_corpus_report(
        case_results=case_results,
        repo_root=root,
        corpus_ref=f"repo://{_repo_relative(root, corpus)}",
        mode=mode,
        generated_at=generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )


def write_manifest(repo_root: Path, output: Path = DEFAULT_MANIFEST_OUTPUT) -> dict[str, Any]:
    """Write the deterministic W12.D manifest."""

    payload = build_w12d_manifest()
    atomic_write_json(_resolve(repo_root, output), payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build the W12.D corpus-run parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--graph-output-dir", type=Path, default=DEFAULT_GRAPH_OUTPUT_DIR)
    parser.add_argument(
        "--hypothesis-ledger-output-dir",
        type=Path,
        default=DEFAULT_HYPOTHESIS_LEDGER_DIR,
        help="Where the W6.E hypothesis ledger artifact is persisted per case.",
    )
    parser.add_argument(
        "--critic-report-output-dir",
        type=Path,
        default=DEFAULT_CRITIC_REPORT_DIR,
        help="Where W6.E critic ensemble report artifacts are persisted per case.",
    )
    parser.add_argument(
        "--mode",
        choices=("real_producer", "corpus_stub"),
        default="real_producer",
        help="Run real producers or corpus-grounded stub producers.",
    )
    parser.add_argument(
        "--producer-stub-dir",
        type=Path,
        default=DEFAULT_PRODUCER_STUB_DIR,
        help="Directory with <case_id>.producer_stubs.json files for --mode corpus_stub.",
    )
    parser.add_argument(
        "--capability-index",
        type=Path,
        help=(
            "Optional Phase 1 capability-index DuckDB used to materialize "
            "capability/construct refs in W12.D claim bindings."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument(
        "--allow-typed-blockers",
        action="store_true",
        help="Return zero when W12.D records typed blockers.",
    )
    parser.add_argument(
        "--require-passing",
        action="store_true",
        help="Return non-zero unless the W12.D report status is pass.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for W12.D."""

    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    if args.write_manifest:
        write_manifest(root, args.manifest_output or DEFAULT_MANIFEST_OUTPUT)

    report = run_w12d_universal_outcome_corpus(
        repo_root=root,
        corpus_path=args.corpus,
        graph_output_dir=args.graph_output_dir,
        hypothesis_ledger_output_dir=args.hypothesis_ledger_output_dir,
        critic_report_output_dir=args.critic_report_output_dir,
        mode=args.mode,
        producer_stub_dir=args.producer_stub_dir,
        capability_index_path=args.capability_index,
    )
    output = _resolve(root, args.output)
    atomic_write_json(output, report)
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")

    if report["status"] == "blocked" and not args.allow_typed_blockers:
        return 2
    if args.require_passing and report["status"] != "pass":
        return 2
    return 0


def _run_case(
    case: Mapping[str, Any],
    *,
    repo_root: Path,
    graph_output_dir: Path,
    hypothesis_ledger_output_dir: Path,
    critic_report_output_dir: Path,
    mode: str,
    producer_stub_dir: Path,
    capability_index_path: Path | None,
) -> dict[str, Any]:
    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    domain = _normalized_token(case.get("domain") or _nested(case, ("intent", "problem_domain")))
    authority_level = _normalized_token(
        case.get("authority_level")
        or _nested(case, ("intent", "authority_level"))
        or _nested(case, ("claim_evidence_annotations", "authority_level"))
        or "research"
    )
    source_path = str(case.get("_source_path") or "")
    issues: list[dict[str, Any]] = []
    typed_blockers: list[dict[str, Any]] = []
    universal_compilation: dict[str, Any] = {"status": "blocked"}
    producer_pipeline: dict[str, Any] = {"status": "blocked", "producer_pipeline_ref": None}
    runtime_pdc_graph: dict[str, Any] = {"status": "blocked", "graph_ref": None}
    evidence_bound_pdc_graph: dict[str, Any] = {
        "artifact_ref": None,
        "authority_boundary": _graph_authority_boundary(),
    }
    llm_summary: dict[str, Any] = {
        "status": "not_run",
        "hypothesis_ledger_ref": None,
        "hypothesis_ledger_artifact_ref": None,
        "formulator": None,
        "critic_ensemble": None,
        "critic_consensus": None,
        "candidate_firewall": None,
    }
    corpus_stub_summary = (
        corpus_stub_authority_boundary({"case_id": case_id})
        if mode == "corpus_stub"
        else None
    )
    s1_graded_outcome: dict[str, Any] = _s1_not_applicable_summary(
        authority_level=authority_level,
    )
    capability_graph_trace: dict[str, Any] = _capability_graph_not_run(
        capability_index_path=capability_index_path,
        repo_root=repo_root,
    )
    s2_design_search = _s2_design_search_summary(case, repo_root=repo_root)

    try:
        compiled = _compile_case_artifacts(
            case,
            case_id=case_id,
            capability_index_path=capability_index_path,
        )
        universal_compilation = compiled["universal_compilation"]
        capability_graph_trace = _capability_graph_context(
            case=case,
            compiled=compiled,
            capability_index_path=capability_index_path,
            repo_root=repo_root,
            authority_level=authority_level,
        )
        llm_artifacts = _mapping(compiled.get("llm_artifacts"))
        if llm_artifacts:
            ledger_payload = _nested(llm_artifacts, ("hypothesis_ledger", "ledger_payload"))
            artifact_ref: str | None = None
            if isinstance(ledger_payload, Mapping):
                artifact_ref = _persist_hypothesis_ledger_artifact(
                    ledger_payload=ledger_payload,
                    repo_root=repo_root,
                    ledger_output_dir=hypothesis_ledger_output_dir,
                    case_id=case_id,
                )
            critic_report_ref: str | None = None
            critic_report_payload = _mapping(
                llm_artifacts.get("critic_ensemble_report_payload")
            )
            if critic_report_payload:
                critic_report_payload = {
                    **critic_report_payload,
                    "case_id": case_id,
                    "domain": domain or "unknown",
                    "authority_level": authority_level or "research",
                }
                critic_report_ref = _persist_critic_report_artifact(
                    critic_report_payload=critic_report_payload,
                    repo_root=repo_root,
                    critic_report_output_dir=critic_report_output_dir,
                    case_id=case_id,
                )
            llm_summary = {
                "status": "pass",
                "hypothesis_ledger_ref": _nested(
                    ledger_payload or {},
                    ("hypothesis_ledger_ref",),
                ),
                "hypothesis_ledger_artifact_ref": artifact_ref,
                "critic_ensemble_report_ref": critic_report_ref,
                "formulator": dict(_mapping(llm_artifacts.get("formulator"))),
                "critic_ensemble": dict(_mapping(llm_artifacts.get("critic_ensemble"))),
                "critic_consensus": dict(_mapping(llm_artifacts.get("critic_consensus"))),
                "candidate_firewall": dict(_mapping(llm_artifacts.get("candidate_firewall"))),
                "hypothesis_ledger_summary": dict(
                    _nested(llm_artifacts, ("hypothesis_ledger", "summary")) or {}
                ),
            }
            firewall_issue_count = int(
                _nested(llm_artifacts, ("candidate_firewall", "issue_count")) or 0
            )
            if firewall_issue_count:
                typed_blockers.append(
                    _case_blocker(
                        code="w12d_candidate_firewall_violation",
                        case_id=case_id,
                        domain=domain,
                        authority_level=authority_level,
                        message=(
                            "W6.F candidate firewall blocked candidate refs from "
                            "authority slots; review hypothesis ledger admission "
                            "state before promoting candidates."
                        ),
                        next_action=(
                            "Resolve firewall issues in the hypothesis ledger or "
                            "leave candidates as ``candidate_unverified``."
                        ),
                    )
                )
        pipeline = _run_case_pipeline(
            case,
            compiled=compiled,
            authority_level=authority_level,
            mode=mode,
            producer_stub_dir=producer_stub_dir,
            capability_bindings=_sequence_of_mappings(
                capability_graph_trace.get("capability_bindings")
            ),
        )
        producer_decisions = list(
            _sequence_of_mappings(pipeline.get("producer_binding_decisions"))
        )
        claim_bindings = _claim_bindings_from_pipeline(
            case_id=case_id,
            claims=_sequence_of_mappings(compiled.get("claims")),
            producer_binding_decisions=producer_decisions,
        )
        producer_pipeline = {
            "status": str(pipeline.get("status") or "blocked"),
            "producer_pipeline_ref": pipeline.get("producer_pipeline_ref"),
            "compiled_requirement_exit_gate": dict(
                _mapping(pipeline.get("compiled_requirement_exit_gate"))
            ),
            "compiled_requirement_exit_gate_status": _nested(
                pipeline,
                ("compiled_requirement_exit_gate", "status"),
            ),
            "stage_count": _nested(pipeline, ("summary", "stage_count")),
            "issue_count": _nested(pipeline, ("summary", "issue_count")),
            "issue_codes": sorted(
                {
                    str(issue.get("code"))
                    for issue in _sequence_of_mappings(pipeline.get("issues"))
                    if issue.get("code")
                }
            ),
            "diagnostic_codes": _producer_pipeline_diagnostic_codes(pipeline),
            "producer_binding_decision_count": len(producer_decisions),
            "producer_binding_decisions": producer_decisions,
            "cross_modal_consistency": dict(
                _mapping(pipeline.get("cross_modal_consistency"))
            ),
            "claim_bindings": claim_bindings,
            "claim_binding_count": len(claim_bindings),
            "capability_ref_count": len(
                {
                    str(row.get("capability_ref"))
                    for row in claim_bindings
                    if row.get("capability_ref")
                }
            ),
            "construct_ref_count": len(
                {
                    str(row.get("construct_ref"))
                    for row in claim_bindings
                    if row.get("construct_ref")
                }
            ),
        }
        if isinstance(pipeline.get("corpus_stub"), Mapping):
            corpus_stub_summary = dict(pipeline["corpus_stub"])
        if producer_pipeline["status"] != "pass":
            capability_blockers = _capability_graph_actionable_blockers(
                case_id=case_id,
                domain=domain,
                authority_level=authority_level,
                capability_graph_trace=capability_graph_trace,
            )
            if capability_blockers:
                typed_blockers.extend(capability_blockers)
            else:
                typed_blockers.append(
                    _case_blocker(
                        code="w12d_producer_pipeline_blocked",
                        case_id=case_id,
                        domain=domain,
                        authority_level=authority_level,
                        message="W7 producer pipeline did not produce a pass status.",
                        next_action=(
                            "Repair W7 producer inputs or carry this typed blocker in rollout "
                            "evidence."
                        ),
                    )
                )
        runtime_pdc_graph = _runtime_pdc_graph_summary(pipeline)
        if runtime_pdc_graph["status"] == "pass" and isinstance(
            pipeline.get("runtime_pdc_graph"),
            Mapping,
        ):
            artifact_ref = _persist_graph_artifact(
                graph=dict(pipeline["runtime_pdc_graph"]),
                repo_root=repo_root,
                graph_output_dir=graph_output_dir,
                case_id=case_id,
            )
            evidence_bound_pdc_graph = {
                "artifact_ref": artifact_ref,
                "authority_boundary": _graph_authority_boundary(),
            }
        else:
            typed_blockers.extend(
                _runtime_graph_blockers(
                    case_id=case_id,
                    domain=domain,
                    authority_level=authority_level,
                    runtime_pdc_graph=runtime_pdc_graph,
                )
            )
    except Exception as exc:
        code = getattr(exc, "code", "w12d_universal_outcome_case_run_failed")
        issue = _issue(str(code), str(exc), severity="fail", case_id=case_id)
        issues.append(issue)
        typed_blockers.append(
            _case_blocker(
                code=str(code),
                case_id=case_id,
                domain=domain,
                authority_level=authority_level,
                message=str(exc),
                next_action="Repair the W6/W7/W8 corpus-run input and rerun W12.D.",
            )
        )

    runtime_typed_blockers = list(typed_blockers)
    s1_graded_outcome = _s1_graded_outcome_summary(
        case=case,
        case_id=case_id,
        domain=domain,
        authority_level=authority_level,
        producer_pipeline=producer_pipeline,
        runtime_pdc_graph=runtime_pdc_graph,
        capability_graph_trace=capability_graph_trace,
        corpus_stub_summary=corpus_stub_summary,
        typed_blockers=runtime_typed_blockers,
    )
    expert_delta = _expert_adjudication_delta(
        case,
        runtime_structural_outcome=_runtime_structural_outcome(
            producer_pipeline=producer_pipeline,
            runtime_pdc_graph=runtime_pdc_graph,
        ),
    )
    typed_blockers.extend(
        _expert_delta_blockers(
            case_id=case_id,
            domain=domain,
            authority_level=authority_level,
            expert_delta=expert_delta,
        )
    )
    outcome = _canonical_outcome(
        runtime_pdc_graph=runtime_pdc_graph,
        producer_pipeline=producer_pipeline,
        expert_delta=expert_delta,
        typed_blockers=typed_blockers,
        authority_level=authority_level,
        s1_graded_outcome=s1_graded_outcome,
    )
    expert_delta = _finalize_expert_adjudication_delta(
        expert_delta,
        canonical_runtime_outcome=outcome,
    )
    expected_negative_control = _is_expected_negative_control(
        expert_delta=expert_delta,
        outcome=outcome,
    )
    typed_blockers = [
        _decorate_case_blocker_for_rollout(
            blocker,
            expected_negative_control=expected_negative_control,
        )
        for blocker in typed_blockers
    ]
    authority_outcomes = _authority_outcomes(
        case,
        outcome=outcome,
        expert_delta=expert_delta,
        s1_authority_outcomes=_mapping(s1_graded_outcome.get("authority_outcomes")),
    )
    return {
        "case_id": case_id,
        "source_path": source_path or None,
        "domain": domain or "unknown",
        "authority_level": authority_level or "research",
        "outcome": outcome,
        "counts_toward_useful_design": outcome in USEFUL_DESIGN_OUTCOMES,
        "universal_compilation": universal_compilation,
        "producer_pipeline": producer_pipeline,
        "capability_graph_trace": capability_graph_trace,
        "runtime_pdc_graph": runtime_pdc_graph,
        "evidence_bound_pdc_graph": evidence_bound_pdc_graph,
        "llm_universal_compilation": llm_summary,
        "corpus_stub": corpus_stub_summary,
        "s1_graded_outcome": s1_graded_outcome,
        "s2_design_search": s2_design_search,
        "expert_adjudication_delta": expert_delta,
        "authority_outcomes": authority_outcomes,
        "typed_blockers": typed_blockers,
        "issues": issues,
    }


def _s2_design_search_summary(case: Mapping[str, Any], *, repo_root: Path) -> dict[str, Any]:
    case_id = str(case.get("case_id") or case.get("id") or "")
    if case_id != "ua-msme-affordable-loans-2022":
        return {"status": "not_applicable", "canonical_outcome_effect": "none_shadow_only"}
    input_row = Layer2S2DesignSearchInput(
        case_id=case_id,
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=(
            "objective://credit_program_enrollment",
            "objective://firm_survival",
            "objective://regional_displacement_pressure",
            "objective://credit_access",
            "objective://fiscal_burden_per_beneficiary",
        ),
        construct_refs=(
            "construct://credit_program_enrollment",
            "construct://firm_survival",
            "construct://regional_displacement_pressure",
            "construct://credit_access",
            "construct://fiscal_burden_per_beneficiary",
        ),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=datetime.fromisoformat(GENERATED_AT.replace("Z", "+00:00")),
        rule_version_ref="policyos.layer2.s2.design_search.v1",
    )
    run = run_s2_shadow_design_loop(input_row)
    return {
        "status": run.status,
        "canonical_outcome_effect": "none_shadow_only",
        "search_ledger": run.search_ledger.model_dump(mode="json"),
        "design_record": run.design_record.model_dump(mode="json"),
        "handoff_records": [row.model_dump(mode="json") for row in run.handoff_records],
    }


def _capability_graph_not_run(
    *,
    capability_index_path: Path | None,
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "schema_version": "policyos.policy_design_case.phase5.capability_graph_trace.v1",
        "status": "not_run",
        "capability_index_ref": None,
        "capability_index_path": (
            f"repo://{_repo_relative(repo_root, capability_index_path)}"
            if capability_index_path is not None
            else None
        ),
        "capability_index_loaded": False,
        "construct_registry_ref": "construct-registry:v1",
        "construct_registry_artifact_ref": _construct_registry_artifact_ref(repo_root),
        "construct_registry_loaded": _resolve(repo_root, DEFAULT_CONSTRUCT_REGISTRY).exists(),
        "authority_composition_rule_ref": DEFAULT_AUTHORITY_COMPOSITION_RULE_REF,
        "resolver_executed": False,
        "producer_binding_emitted": False,
        "capability_bindings": [],
        "binding_count": 0,
        "w8e_conflict_signals": {
            "visible": False,
            "conflict_marker_count": 0,
        },
        "w8f_independence_signals": {
            "visible": False,
            "factor_count": 0,
            "below_floor_count": 0,
        },
        "issue_codes": [],
        "authority_boundary": {
            "authoritative_for": ["capability_graph_traceability"],
            "may_not_use_for": ["producer_domain_truth", "claim_authority"],
        },
    }


def _capability_graph_context(
    *,
    case: Mapping[str, Any],
    compiled: Mapping[str, Any],
    capability_index_path: Path | None,
    repo_root: Path,
    authority_level: str,
) -> dict[str, Any]:
    trace = _capability_graph_not_run(
        capability_index_path=capability_index_path,
        repo_root=repo_root,
    )
    if capability_index_path is None:
        return trace
    if not capability_index_path.exists():
        return {
            **trace,
            "status": "blocked",
            "issue_codes": ["w12d_capability_index_missing"],
        }
    try:
        resolver = RequirementToCapabilityResolver.from_duckdb(capability_index_path)
    except Exception as exc:  # pragma: no cover - exercised by CLI environments.
        return {
            **trace,
            "status": "blocked",
            "capability_index_loaded": False,
            "issue_codes": ["w12d_capability_index_load_failed"],
            "issues": [
                _issue(
                    "w12d_capability_index_load_failed",
                    str(exc),
                    severity="fail",
                )
            ],
        }

    bindings: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for spec in _sequence(compiled.get("data_requirement_specs")):
        query = _capability_query_for_spec(
            spec,
            case=case,
            authority_level=authority_level,
        )
        if query is None:
            continue
        try:
            result = resolver.resolve(query)
        except Exception as exc:  # pragma: no cover - defensive trace, not authority.
            issues.append(
                _issue(
                    "w12d_capability_resolver_failed",
                    str(exc),
                    severity="fail",
                    requirement_id=query.requirement_id,
                )
            )
            continue
        row = result.model_dump(mode="json", exclude_none=True)
        row["construct_registry_ref"] = "construct-registry:v1"
        row["authority_composition_rule_ref"] = (
            row.get("rule_version_ref") or DEFAULT_AUTHORITY_COMPOSITION_RULE_REF
        )
        bindings.append(row)

    return {
        **trace,
        "status": "pass" if bindings and not issues else "blocked",
        "capability_index_ref": resolver.capability_index_ref,
        "capability_index_loaded": True,
        "resolver_executed": bool(bindings or issues),
        "producer_binding_emitted": bool(bindings),
        "capability_bindings": bindings,
        "binding_count": len(bindings),
        "w8e_conflict_signals": _w8e_conflict_signals(bindings),
        "w8f_independence_signals": _w8f_independence_signals(bindings),
        "issue_codes": sorted({str(issue["code"]) for issue in issues}),
        "issues": issues,
    }


def _w8e_conflict_signals(bindings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    marker_count = sum(
        len(_sequence(binding.get("conflict_markers"))) for binding in bindings
    )
    return {
        "visible": True,
        "conflict_marker_count": marker_count,
        "binding_count": len(bindings),
    }


def _w8f_independence_signals(bindings: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    factors = [
        factor
        for binding in bindings
        for factor in _sequence_of_mappings(binding.get("factors"))
        if str(factor.get("name")) == "effective_independence"
    ]
    return {
        "visible": True,
        "factor_count": len(factors),
        "below_floor_count": sum(1 for factor in factors if factor.get("status") == "below_floor"),
        "binding_count": len(bindings),
    }


def _capability_query_for_spec(
    spec: object,
    *,
    case: Mapping[str, Any],
    authority_level: str,
) -> RequirementToCapabilityQuery | None:
    payload = _spec_payload(spec)
    requirement_id = _text(payload.get("requirement_id"))
    construct = _first_construct_ref(payload)
    if not requirement_id or not construct:
        return None
    scope = _mapping(payload.get("scope"))
    family = _first_sequence_text(payload.get("required_data_families"))
    geography = (
        _text(scope.get("jurisdiction"))
        or _text(scope.get("geography"))
        or _jurisdiction(case)
    )
    return RequirementToCapabilityQuery(
        requirement_id=requirement_id,
        construct=construct,
        entity_scope=_entity_scope_for_construct(construct),
        population_filter={
            "type": _text(scope.get("population")) or _target_population(case),
        },
        geography=geography,
        time_window={"start": _policy_time(case), "end": None},
        authority_level=_authority_posture(authority_level),
        claim_use=_text(payload.get("claim_use")) or "claim_evidence_closeout",
        required_evidence_modes=(
            "observed",
            "derived",
            "proxy_observational",
            "scholarly_causal_support",
            "legal_threshold",
        ),
        forbidden_evidence_modes=("simulation_only", "candidate_unverified"),
        source_family_alias=family,
    )


def _claim_bindings_from_pipeline(
    *,
    case_id: str,
    claims: Sequence[Mapping[str, Any]],
    producer_binding_decisions: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not producer_binding_decisions:
        return []
    claim_rows = list(claims) or ({"claim_id": f"claim:{case_id}"},)
    rows: list[dict[str, Any]] = []
    for index, claim in enumerate(claim_rows):
        claim_id = _text(claim.get("claim_id") or claim.get("id")) or f"claim:{index + 1}"
        matched = _producer_decisions_for_claim(producer_binding_decisions, claim_id)
        if not matched:
            matched = list(producer_binding_decisions)
        capability_refs = _refs_from_decisions(matched, "capability_ref")
        construct_refs = _refs_from_decisions(matched, "construct_ref")
        if not capability_refs or not construct_refs:
            continue
        rows.append(
            {
                "claim_binding_id": f"claim-binding:{_slug(case_id)}:{index + 1}",
                "claim_id": claim_id,
                "capability_ref": capability_refs[0],
                "construct_ref": construct_refs[0],
                "capability_refs": capability_refs,
                "construct_refs": construct_refs,
                "capability_index_refs": _refs_from_decisions(
                    matched,
                    "capability_index_ref",
                ),
                "construct_registry_refs": _refs_from_decisions(
                    matched,
                    "construct_registry_ref",
                ),
                "authority_composition_rule_refs": _refs_from_decisions(
                    matched,
                    "authority_composition_rule_ref",
                ),
                "producer_components": _refs_from_decisions(
                    matched,
                    "producer_component",
                ),
                "binding_decision_refs": _refs_from_decisions(matched, "binding_id"),
                "authority_boundary": {
                    "authoritative_for": ["claim_to_capability_traceability"],
                    "may_not_use_for": ["claim_authority", "producer_domain_truth"],
                },
            }
        )
    return rows


def _producer_decisions_for_claim(
    decisions: Sequence[Mapping[str, Any]],
    claim_id: str,
) -> list[Mapping[str, Any]]:
    tokens = {claim_id, claim_id.replace(":", "_"), claim_id.replace(":", "-")}
    return [
        row
        for row in decisions
        if any(
            token in _text(row.get("requirement_ref"))
            or token in _text(row.get("binding_id"))
            for token in tokens
        )
    ]


def _refs_from_decisions(
    decisions: Sequence[Mapping[str, Any]],
    key: str,
) -> list[str]:
    return list(
        dict.fromkeys(
            text
            for row in decisions
            if (text := _text(row.get(key)))
        )
    )


def _first_construct_ref(payload: Mapping[str, Any]) -> str | None:
    metadata = _mapping(payload.get("metadata"))
    binding = _mapping(metadata.get("capability_binding"))
    for value in (
        binding.get("construct_ref"),
        metadata.get("construct_ref"),
        payload.get("construct_ref"),
        payload.get("target_construct_ref"),
    ):
        text = _text(value)
        if text:
            return text.removeprefix("construct:")
    family = _first_sequence_text(payload.get("required_data_families"))
    return construct_for_legacy_family(family) if family else None


def _first_sequence_text(value: object) -> str | None:
    for item in _sequence(value):
        text = _text(item)
        if text:
            return text
    return None


def _entity_scope_for_construct(construct: str) -> str:
    bare = construct.removeprefix("construct:")
    return {
        "firm_survival": "firm",
        "credit_program_enrollment": "firm_or_program",
        "regional_displacement_pressure": "region",
    }.get(bare, "entity")


def _authority_posture(authority_level: str) -> str:
    if authority_level == "production":
        return "production"
    if authority_level == "research":
        return "research"
    return "governed_pilot"


def _construct_registry_artifact_ref(repo_root: Path) -> str:
    path = _resolve(repo_root, DEFAULT_CONSTRUCT_REGISTRY)
    return f"repo://{_repo_relative(repo_root, path)}"


def _spec_payload(spec: object) -> Mapping[str, Any]:
    if isinstance(spec, Mapping):
        return dict(spec)
    if hasattr(spec, "model_dump"):
        return spec.model_dump(mode="json")
    return {}


def _compile_case_artifacts(
    case: Mapping[str, Any],
    *,
    case_id: str,
    capability_index_path: Path | None = None,
) -> dict[str, Any]:
    run_id = _text(case.get("run_id")) or f"run-{case_id}"
    intent_payload = _mapping(case.get("intent")) or case
    intent_text = _compilation_intent_text(case, intent_payload=intent_payload)
    authority_level = _normalized_token(
        case.get("authority_level")
        or intent_payload.get("authority_level")
        or _nested(case, ("claim_evidence_annotations", "authority_level"))
        or "research"
    )
    authority_profile = UniversalAuthorityProfile(
        profile_id=_text(intent_payload.get("authority_profile_ref"))
        or _text(case.get("authority_profile_ref"))
        or f"authority_profile.{authority_level}",
        authority_type=_enum_value(
            PolicyLayerLevel,
            intent_payload.get("authority_type")
            or case.get("authority_type")
            or _authority_type_for_level(authority_level),
            default=PolicyLayerLevel.LOCAL,
        ),
    )
    compiled_case = PolicyGrammarCompiler().compile(
        intent=PolicyGrammarIntent(
            intent_id=_text(intent_payload.get("intent_id")) or case_id,
            text=intent_text,
            domain=_enum_value(
                ProblemDomain,
                intent_payload.get("problem_domain")
                or case.get("problem_domain")
                or case.get("domain"),
                default=ProblemDomain.CUSTOM,
            ),
        ),
        authority_profile=authority_profile,
        concept_spine_refs=_concept_spine_refs(case, case_id=case_id),
    )
    if compiled_case.facets is None:
        blocker_codes = [blocker.code for blocker in compiled_case.blockers]
        raise W12DCaseRunError(
            "W6.A grammar compilation blocked: " + ", ".join(blocker_codes)
        )

    graph = _compile_obligation_graph(
        case,
        run_id=run_id,
        compiled_case=compiled_case,
        intent_text=intent_text,
    )
    if not graph.blocking_frontier:
        raise W12DCaseRunError("W6.C compiled no blocking frontier obligations.")

    facets = _claim_facets(compiled_case)
    obligations = _claim_obligations(graph, facets=facets)
    claim_ledger = ClaimDecompositionCompiler().compile(
        {
            "run_id": run_id,
            "intent": intent_text,
            "facets": facets,
            "obligations": obligations,
            "named_alternatives": _named_alternatives(case, case_id=case_id),
            "concept_spine_refs": [compiled_case.concept_spine_ref],
            "authority_profile_refs": [compiled_case.authority_profile.profile_id],
            "metadata": {"producer": TOOL_NAME},
        }
    )
    claim_decomposition_ref = f"claim-ledger:{_slug(run_id)}"
    claims = _runtime_claims(
        claim_ledger=claim_ledger,
        case=case,
        case_id=case_id,
        authority_level=authority_level,
    )
    llm_artifacts = _run_llm_formulator_and_critics(
        case_id=case_id,
        run_id=run_id,
        intent_text=intent_text,
        compiled_case=compiled_case,
        graph=graph,
        facets=facets,
        obligations=obligations,
        claim_ledger=claim_ledger,
    )
    consensus_candidates = critic_consensus_to_obligation_candidates(
        formulator_output=llm_artifacts["_formulator_output"],
        critic_report=llm_artifacts["_critic_report"],
        facets=facet_snapshots_for_obligation_graph(compiled_case),
        intent_text=intent_text,
        authority_profile_ref=compiled_case.authority_profile.profile_id,
    )
    if consensus_candidates:
        graph = _compile_obligation_graph(
            case,
            run_id=run_id,
            compiled_case=compiled_case,
            intent_text=intent_text,
            additional_candidate_sources=consensus_candidates,
        )
        obligations = _claim_obligations(graph, facets=facets)
        claim_ledger = ClaimDecompositionCompiler().compile(
            {
                "run_id": run_id,
                "intent": intent_text,
                "facets": facets,
                "obligations": obligations,
                "named_alternatives": _named_alternatives(case, case_id=case_id),
                "concept_spine_refs": [compiled_case.concept_spine_ref],
                "authority_profile_refs": [compiled_case.authority_profile.profile_id],
                "metadata": {"producer": TOOL_NAME, "llm_consensus_reissue": True},
            }
        )
        claims = _runtime_claims(
            claim_ledger=claim_ledger,
            case=case,
            case_id=case_id,
            authority_level=authority_level,
        )
    llm_artifacts["critic_consensus"] = {
        "candidate_count": len(consensus_candidates),
        "candidate_refs": [candidate.candidate_id for candidate in consensus_candidates],
        "source_class": "llm_critic_consensus",
        "priority_ceiling": "review_required",
    }
    llm_artifacts.pop("_formulator_output", None)
    llm_artifacts.pop("_critic_report", None)
    requirement_artifacts = _compile_requirement_specs(
        case=case,
        case_id=case_id,
        run_id=run_id,
        authority_level=authority_level,
        compiled_case=compiled_case,
        graph=graph,
        claim_ledger=claim_ledger,
        claims=claims,
        facets=facets,
        obligations=obligations,
        capability_index_path=capability_index_path,
    )
    return {
        "case_id": case_id,
        "run_id": run_id,
        "intent_text": intent_text,
        "authority_level": authority_level,
        "compiled_case": compiled_case,
        "obligation_graph": graph,
        "claim_ledger": claim_ledger,
        "claims": claims,
        "claim_decomposition_ref": claim_decomposition_ref,
        "llm_artifacts": llm_artifacts,
        "universal_compilation": {
            "status": "pass",
            "grammar_ref": compiled_case.case_id,
            "obligation_graph_ref": graph.graph_id,
            "claim_decomposition_ref": claim_decomposition_ref,
            "facet_count": len(facets),
            "frontier_count": len(graph.blocking_frontier),
            "claim_count": len(claims),
        },
        **requirement_artifacts,
    }


def _compile_obligation_graph(
    case: Mapping[str, Any],
    *,
    run_id: str,
    compiled_case: Any,
    intent_text: str,
    additional_candidate_sources: Sequence[Any] = (),
) -> ObligationGraph:
    compilation_inputs = _mapping(case.get("compilation_inputs"))
    if "governed_rules" in compilation_inputs:
        governed_rules = _sequence(compilation_inputs.get("governed_rules"))
    elif compilation_inputs.get("use_seed_rule_catalog") is False:
        governed_rules = ()
    else:
        governed_rules = build_seed_obligation_rule_catalog().rules
    return compile_obligation_graph(
        run_id=run_id,
        facets=facet_snapshots_for_obligation_graph(compiled_case),
        governed_rules=governed_rules,
        candidate_sources=(
            *_sequence(
                compilation_inputs.get("candidate_sources") or case.get("candidate_sources")
            ),
            *additional_candidate_sources,
        ),
        complexity_budget=ComplexityBudget.model_validate(
            _mapping(compilation_inputs.get("complexity_budget")) or {}
        ),
        generated_at=datetime(2026, 5, 25, tzinfo=UTC),
        graph_id=f"obligation-graph-{_slug(_text(case.get('case_id')) or run_id)}",
        intent_text=intent_text,
    )


def _compile_requirement_specs(
    *,
    case: Mapping[str, Any],
    case_id: str,
    run_id: str,
    authority_level: str,
    compiled_case: Any,
    graph: ObligationGraph,
    claim_ledger: Any,
    claims: Sequence[Mapping[str, Any]],
    facets: Sequence[Mapping[str, Any]],
    obligations: Sequence[Mapping[str, Any]],
    capability_index_path: Path | None = None,
) -> dict[str, Any]:
    from polisyos.data_requirement import DataRequirementCompiler
    from polisyos.legal_requirement import LegalAuthorityRequirementCompiler
    from polisyos.method_requirement import MethodValidityRequirementCompiler
    from polisyos.participation_requirement import ParticipationProvenanceCompiler
    from polisyos.scholar_requirement import ScholarSupportRequirementCompiler

    capability_resolver = (
        RequirementToCapabilityResolver.from_duckdb(capability_index_path)
        if capability_index_path is not None
        else None
    )
    data_report = DataRequirementCompiler(
        capability_resolver=capability_resolver,
        require_capability_index=capability_index_path is not None,
    ).compile_for_claim_ledger(
        run_id=run_id,
        scenario_id=case_id,
        claim_ledger=claim_ledger,
        facet_snapshots=facets,
        obligation_graph=graph,
        authority_profile_refs=(compiled_case.authority_profile.profile_id,),
    )
    legal_specs = LegalAuthorityRequirementCompiler().compile(
        run_id=run_id,
        target_context={
            "jurisdiction": _jurisdiction(case),
            "authority_profile": authority_level,
            "as_of": _policy_time(case),
        },
        claims=claims,
        facets=facets,
        obligations=obligations,
    )
    method_artifact = MethodValidityRequirementCompiler().compile(
        run_id=run_id,
        claims=claims,
        requirement_graph_ref=graph.graph_id,
    )
    scholar_result = ScholarSupportRequirementCompiler().compile(
        {
            "run_id": run_id,
            "authority_level": authority_level,
            "claims": [_scholar_claim(claim, authority_level=authority_level) for claim in claims],
        }
    )
    participation_bundle = ParticipationProvenanceCompiler().compile(
        {"run_id": run_id, "claims": claims}
    )
    return {
        "data_requirement_specs": data_report.specs,
        "legal_authority_requirement_specs": [
            spec for spec in legal_specs if not getattr(spec, "out_of_scope", False)
        ],
        "method_validity_requirement_specs": method_artifact.requirements,
        "scholar_support_requirement_specs": scholar_result.requirements,
        "participation_provenance_requirement_specs": participation_bundle.requirements,
    }


def _run_case_pipeline(
    case: Mapping[str, Any],
    *,
    compiled: Mapping[str, Any],
    authority_level: str,
    mode: str,
    producer_stub_dir: Path,
    capability_bindings: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    stub_responses = None
    if mode == "corpus_stub":
        stub_responses = load_corpus_stub_responses(
            stub_dir=producer_stub_dir,
            case_id=str(compiled["case_id"]),
        )
    return run_requirement_spec_producer_pipeline(
        run_id=str(compiled["run_id"]),
        job_id=_text(case.get("job_id")) or f"job-{_slug(compiled['run_id'])}",
        tenant_id=_text(case.get("tenant_id")) or "w12d-universal-outcome-corpus",
        request_ref=_text(case.get("request_ref")) or f"request:{_slug(compiled['run_id'])}",
        authority_profile=authority_level,
        spine_context=_spine_context(case, compiled_case=compiled["compiled_case"]),
        claims=_sequence_of_mappings(compiled["claims"]),
        data_requirement_specs=_sequence(compiled["data_requirement_specs"]),
        legal_authority_requirement_specs=_sequence(
            compiled["legal_authority_requirement_specs"]
        ),
        method_validity_requirement_specs=_sequence(compiled["method_validity_requirement_specs"]),
        scholar_support_requirement_specs=_sequence(compiled["scholar_support_requirement_specs"]),
        participation_provenance_requirement_specs=_sequence(
            compiled["participation_provenance_requirement_specs"]
        ),
        capability_bindings=capability_bindings,
        universal_grammar_compilation={
            "status": "pass",
            "artifact_ref": _nested(compiled, ("universal_compilation", "grammar_ref")),
        },
        obligation_graph={
            "status": "pass",
            "graph_ref": _nested(compiled, ("universal_compilation", "obligation_graph_ref")),
        },
        claim_decomposition={
            "status": "pass",
            "artifact_ref": compiled["claim_decomposition_ref"],
        },
        scenario_refs=_sequence(case.get("scenario_refs")),
        corpus_stub_responses=stub_responses,
    )


def _runtime_pdc_graph_summary(pipeline: Mapping[str, Any]) -> dict[str, Any]:
    smoke = _mapping(pipeline.get("compiled_pdc_graph_smoke"))
    graph = _mapping(pipeline.get("runtime_pdc_graph"))
    return {
        "status": str(smoke.get("status") or "blocked"),
        "graph_ref": smoke.get("runtime_pdc_graph_ref"),
        "claim_count": smoke.get("claim_count"),
        "edge_count": smoke.get("edge_count"),
        "warrant_structure_count": smoke.get("warrant_structure_count"),
        "authority_envelope": smoke.get("authority_envelope")
        or graph.get("authority_envelope"),
        "capability_reality_label": smoke.get("capability_reality_label")
        or pipeline.get("capability_reality_label"),
        "blockers": list(_sequence_of_mappings(smoke.get("blockers"))),
    }


def _persist_graph_artifact(
    *,
    graph: Mapping[str, Any],
    repo_root: Path,
    graph_output_dir: Path,
    case_id: str,
) -> str:
    output = graph_output_dir / f"{_slug(case_id)}.runtime-pdc-graph.json"
    atomic_write_json(output, dict(graph))
    return f"repo://{_repo_relative(repo_root, output)}"


def _persist_hypothesis_ledger_artifact(
    *,
    ledger_payload: Mapping[str, Any],
    repo_root: Path,
    ledger_output_dir: Path,
    case_id: str,
) -> str:
    """Write a serialised hypothesis ledger to disk and return a repo:// ref."""

    output = ledger_output_dir / f"{_slug(case_id)}.hypothesis-ledger.json"
    atomic_write_json(output, dict(ledger_payload))
    return f"repo://{_repo_relative(repo_root, output)}"


def _persist_critic_report_artifact(
    *,
    critic_report_payload: Mapping[str, Any],
    repo_root: Path,
    critic_report_output_dir: Path,
    case_id: str,
) -> str:
    """Write a W6.E critic ensemble report artifact and return a repo:// ref."""

    output = critic_report_output_dir / f"{_slug(case_id)}.critic-ensemble-report.json"
    atomic_write_json(output, dict(critic_report_payload))
    return f"repo://{_repo_relative(repo_root, output)}"


def _run_llm_formulator_and_critics(
    *,
    case_id: str,
    run_id: str,
    intent_text: str,
    compiled_case: Any,
    graph: ObligationGraph,
    facets: Sequence[Mapping[str, Any]],
    obligations: Sequence[Mapping[str, Any]],
    claim_ledger: Any,
) -> dict[str, Any]:
    """Run the W6.E LLM formulator + multi-critic ensemble for one corpus case.

    The runtime path keeps candidates strictly as ``candidate_unverified`` —
    Track A is the wire-in; promotion to obligations is Track B. The returned
    payload surfaces the in-memory ledger, the critic verdicts, the firewall
    enforcement summary, and a serialised ``HypothesisLedger`` envelope so the
    case writer can persist it alongside the runtime PDC graph artifact.
    """

    authority_profile_ref = compiled_case.authority_profile.profile_id
    concept_spine_refs = (compiled_case.concept_spine_ref,)
    source_refs = (
        f"obligation_graph:{graph.graph_id}",
        f"claim_decomposition:{run_id}",
        f"compiled_case:{compiled_case.case_id}",
    )
    claim_decomposition_payload = tuple(
        claim.model_dump(mode="json", exclude_none=True)
        for claim in getattr(claim_ledger, "claims", ())
    )
    formulator_input = LLMFormulatorInput(
        intent=intent_text,
        facets={
            "snapshots": [dict(snapshot) for snapshot in facets],
        },
        obligations=tuple(dict(obligation) for obligation in obligations),
        claim_decomposition=claim_decomposition_payload,
        authority_profile_ref=authority_profile_ref,
        concept_spine_refs=concept_spine_refs,
        source_refs=source_refs,
        run_id=run_id,
        tool_refs=W12D_FORMULATOR_TOOL_REFS,
        repair_decision_lineage=W12D_FORMULATOR_REPAIR_LINEAGE,
        metadata={
            "phase_id": PHASE_ID,
            "case_id": case_id,
        },
    )
    sink = InMemoryHypothesisLedger()
    formulator_output = LLMFormulator().formulate(formulator_input, ledger=sink)
    critic_report = MultiCriticEnsemble.default().evaluate(
        formulator_input,
        candidates=formulator_output.candidates,
    )
    # The formulator emits its own ``HypothesisLedgerEntry`` model alongside
    # the canonical one in ``polisyos.runtime.quality.hypothesis_ledger``.
    # Round-tripping through ``model_validate`` with dict entries lets Pydantic
    # coerce between the two and avoids a class-identity mismatch.
    ledger = HypothesisLedger.model_validate(
        {
            "run_id": run_id,
            "job_id": f"job-{_slug(case_id)}",
            "hypothesis_ledger_ref": f"hypothesis-ledger:{_slug(run_id)}",
            "entries": [
                entry.model_dump(mode="json", exclude_none=True)
                for entry in sink.entries
            ],
        }
    )
    ledger_payload = serialize_hypothesis_ledger(ledger)
    # Track A wire-in keeps the firewall in advisory mode: the canonical
    # consumer payloads (W8.A PDC graph, W4.E projection, closeout reader)
    # are not yet produced at this point in ``_compile_case_artifacts``, so
    # running the firewall over the ledger itself would emit synthetic
    # ``candidate_unverified`` violations for every candidate × every
    # authority slot. Track B will bind the firewall to those real consumer
    # payloads. Track A confirms the firewall is wired and importable; if a
    # downstream payload accidentally references a candidate, that violation
    # will surface at the consumer site.
    firewall_issues: list[dict[str, Any]] = []
    return {
        "formulator": {
            "schema_version": formulator_output.schema_version,
            "run_id": formulator_output.run_id,
            "prompt_fingerprint": formulator_output.prompt_fingerprint,
            "candidate_count": len(formulator_output.candidates),
            "metadata": dict(formulator_output.metadata),
        },
        "critic_ensemble": {
            "schema_version": critic_report.schema_version,
            "verdict_count": len(critic_report.verdicts),
            "verdict_counts_by_type": _critic_verdict_counts(critic_report.verdicts),
            "diversity_summary": critic_report.diversity.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "metadata": dict(critic_report.metadata),
        },
        "critic_ensemble_report_payload": {
            **critic_report.model_dump(mode="json", exclude_none=True),
            "case_id": case_id,
        },
        "hypothesis_ledger": {
            "schema_version": HYPOTHESIS_LEDGER_SCHEMA_VERSION,
            "ledger_payload": ledger_payload,
            "summary": dict(ledger.summary),
        },
        "candidate_firewall": {
            "authority_slots": list(W12D_FIREWALL_AUTHORITY_SLOTS),
            "surface": f"w12d.universal_outcome_corpus.{case_id}",
            "issue_count": len(firewall_issues),
            "issues": list(firewall_issues),
        },
        "_formulator_output": formulator_output,
        "_critic_report": critic_report,
    }


def _critic_verdict_counts(verdicts: Sequence[Any]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for verdict in verdicts:
        counter[str(getattr(verdict, "verdict", "unknown"))] += 1
    return {key: counter[key] for key in sorted(counter)}


def _expert_adjudication_delta(
    case: Mapping[str, Any],
    *,
    runtime_structural_outcome: str,
) -> dict[str, Any]:
    adjudication = _mapping(case.get("expert_adjudication") or case.get("adjudication"))
    expert_label = _normalized_token(adjudication.get("case_label") or "reviewer_disagreement")
    expected_outcome = EXPERT_LABEL_EXPECTED_OUTCOME.get(expert_label, "accepted_deficit")
    delta_codes: list[str] = []
    if runtime_structural_outcome != expected_outcome:
        delta_codes.append(
            f"runtime_{_slug(runtime_structural_outcome)}_vs_expert_{_slug(expected_outcome)}"
        )
    claim_labels = list(_sequence_of_mappings(adjudication.get("claim_labels")))
    return {
        "expert_label": expert_label,
        "runtime_structural_outcome": runtime_structural_outcome,
        "expected_outcome": expected_outcome,
        "status": "aligned" if not delta_codes else "delta",
        "delta_codes": delta_codes,
        "claim_label_count": len(claim_labels),
        "claim_delta_refs": [
            {
                "claim_id": row.get("claim_id"),
                "label": row.get("label"),
                "status_should_have_been": row.get("status_should_have_been"),
                "failure_mode": row.get("failure_mode"),
            }
            for row in claim_labels
        ],
    }


def _finalize_expert_adjudication_delta(
    expert_delta: Mapping[str, Any],
    *,
    canonical_runtime_outcome: str,
) -> dict[str, Any]:
    expected = str(expert_delta.get("expected_outcome") or "accepted_deficit")
    delta = dict(expert_delta)
    delta["canonical_runtime_outcome"] = canonical_runtime_outcome
    if canonical_runtime_outcome == expected:
        delta["status"] = "aligned"
        delta["delta_codes"] = []
    else:
        delta["status"] = "delta"
        delta["delta_codes"] = [
            (
                f"canonical_runtime_{_slug(canonical_runtime_outcome)}"
                f"_vs_expert_{_slug(expected)}"
            )
        ]
    return delta


def _is_expected_negative_control(
    *,
    expert_delta: Mapping[str, Any],
    outcome: str,
) -> bool:
    return (
        outcome == "typed_blocker"
        and str(expert_delta.get("expected_outcome") or "") == "typed_blocker"
    )


def _decorate_case_blocker_for_rollout(
    blocker: Mapping[str, Any],
    *,
    expected_negative_control: bool,
) -> dict[str, Any]:
    row = dict(blocker)
    if expected_negative_control:
        row["expected_negative_control"] = True
        row["blocks_rollout_posture"] = False
        row["counts_as_closeout_honesty"] = True
        row["counts_as_closeout_honesty_failure"] = False
    elif row.get("code") in ACTIONABLE_CAPABILITY_BLOCKER_CODES:
        row.setdefault("expected_negative_control", False)
        row["blocks_rollout_posture"] = False
        row.setdefault("counts_as_closeout_honesty", True)
        row.setdefault("counts_as_closeout_honesty_failure", False)
    else:
        row.setdefault("expected_negative_control", False)
        row.setdefault("blocks_rollout_posture", True)
        row.setdefault("counts_as_closeout_honesty", False)
        row.setdefault("counts_as_closeout_honesty_failure", False)
    row.setdefault("counts_as_useful_design", False)
    return row


def _runtime_structural_outcome(
    *,
    producer_pipeline: Mapping[str, Any],
    runtime_pdc_graph: Mapping[str, Any],
) -> str:
    if runtime_pdc_graph.get("status") != "pass":
        return "typed_blocker"
    if producer_pipeline.get("status") != "pass":
        return "typed_blocker"
    return "pass"


def _canonical_outcome(
    *,
    runtime_pdc_graph: Mapping[str, Any],
    producer_pipeline: Mapping[str, Any],
    expert_delta: Mapping[str, Any],
    typed_blockers: Sequence[Mapping[str, Any]],
    authority_level: str,
    s1_graded_outcome: Mapping[str, Any],
) -> str:
    if typed_blockers or runtime_pdc_graph.get("status") != "pass":
        return "typed_blocker"
    if producer_pipeline.get("status") != "pass":
        return "typed_blocker"
    if _s1_can_publish_with_limitation(
        s1_graded_outcome,
        authority_level=_s1_primary_authority_level(None, authority_level),
    ):
        return "publish-with-limitation"
    return str(expert_delta.get("expected_outcome") or "accepted_deficit")


def _s1_can_publish_with_limitation(
    s1_graded_outcome: Mapping[str, Any],
    *,
    authority_level: str,
) -> bool:
    return (
        authority_level in {"research", "governed"}
        and s1_graded_outcome.get("outcome") == "publish_with_limitation"
        and s1_graded_outcome.get("closeout_status") == "closed_with_limitations"
        and not s1_graded_outcome.get("blocked_by")
        and bool(s1_graded_outcome.get("decision_owner_ref"))
        and bool(s1_graded_outcome.get("authority_profile_ref"))
        and bool(_sequence(s1_graded_outcome.get("review_refs")))
    )


def _expert_delta_blockers(
    *,
    case_id: str,
    domain: str,
    authority_level: str,
    expert_delta: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if expert_delta.get("expected_outcome") != "typed_blocker":
        return []
    return [
        _case_blocker(
            code="w12d_expert_adjudication_blocks_runtime_outcome",
            case_id=case_id,
            domain=domain,
            authority_level=authority_level,
            message=(
                "W11.C expert adjudication expects a blocked outcome; runtime "
                "output cannot count as useful design."
            ),
            next_action=(
                "Repair the runtime output or preserve the typed blocker in rollout evidence."
            ),
        )
    ]


def _runtime_graph_blockers(
    *,
    case_id: str,
    domain: str,
    authority_level: str,
    runtime_pdc_graph: Mapping[str, Any],
) -> list[dict[str, Any]]:
    blockers = list(_sequence_of_mappings(runtime_pdc_graph.get("blockers")))
    if not blockers:
        blockers = [{"message": "Runtime PDC graph did not pass W8.A smoke."}]
    return [
        _case_blocker(
            code=str(blocker.get("code") or "w12d_runtime_pdc_graph_blocked"),
            case_id=case_id,
            domain=domain,
            authority_level=authority_level,
            message=str(blocker.get("message") or "Runtime PDC graph blocked."),
            next_action="Repair W8.A graph assembly before claiming corpus capability.",
        )
        for blocker in blockers
    ]


def _producer_pipeline_diagnostic_codes(pipeline: Mapping[str, Any]) -> list[str]:
    codes = {
        str(issue.get("code"))
        for issue in _sequence_of_mappings(pipeline.get("issues"))
        if issue.get("code")
    }
    exit_gate = _mapping(pipeline.get("compiled_requirement_exit_gate"))
    status = str(exit_gate.get("status") or "")
    if status and status != "pass":
        codes.add(f"compiled_requirement_exit_gate_{status}")
    for key in (
        "missing_spec_families",
        "missing_binding_producers",
        "missing_capability_refs",
        "missing_construct_refs",
    ):
        if _sequence(exit_gate.get(key)):
            codes.add(key)
    if str(pipeline.get("status") or "") != "pass" and not codes:
        codes.add("producer_pipeline_blocked_without_issue_codes")
    return sorted(codes)


def _s1_graded_outcome_summary(
    *,
    case: Mapping[str, Any],
    case_id: str,
    domain: str,
    authority_level: str,
    producer_pipeline: Mapping[str, Any],
    runtime_pdc_graph: Mapping[str, Any],
    capability_graph_trace: Mapping[str, Any],
    corpus_stub_summary: Mapping[str, Any] | None,
    typed_blockers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    authority = _s1_primary_authority_level(corpus_stub_summary, authority_level)
    blocked_by = _s1_blocked_by(
        producer_pipeline=producer_pipeline,
        runtime_pdc_graph=runtime_pdc_graph,
        typed_blockers=typed_blockers,
    )
    if blocked_by is not None:
        return {
            **_s1_not_applicable_summary(authority_level=authority),
            "outcome": "typed_blocker",
            "closeout_effect": "closeout_blocked",
            "closeout_status": "blocked",
            "blocked_by": blocked_by,
            "authority_outcomes": {
                level: {"outcome": "typed_blocker", "blocked_by": blocked_by}
                for level in AUTHORITY_LEVELS
            },
        }

    proxy_refs, partial_refs = _s1_evidence_refs(
        producer_pipeline=producer_pipeline,
        capability_graph_trace=capability_graph_trace,
    )
    if not proxy_refs and not partial_refs:
        return _s1_not_applicable_summary(authority_level=authority)

    authority_decisions = _s1_authority_decisions(
        case=case,
        case_id=case_id,
        domain=domain,
        proxy_refs=proxy_refs,
        partial_refs=partial_refs,
    )
    primary = authority_decisions.get(authority)
    if primary is None:
        return {
            **_s1_not_applicable_summary(authority_level=authority),
            "authority_outcomes": _s1_authority_outcome_rows(authority_decisions),
        }

    closeout_verdict: dict[str, Any] = {"status": "not_applicable"}
    projection_surface_status = "not_applicable"
    if primary.outcome == "publish_with_limitation":
        closeout_record = graded_outcome_closeout_record(
            [primary],
            generated_at=datetime.fromisoformat(GENERATED_AT.replace("Z", "+00:00")),
        )
        module_records = _s1_passing_closeout_records()
        module_records["deficit_crosswalk"] = closeout_record
        closeout_verdict = build_can_i_closeout_verdict(
            run_id=f"run-layer2-s1-{_slug(case_id)}",
            module_records=module_records,
        )
        projection_surface_status = (
            "pass"
            if closeout_verdict.get("status") == "closed_with_limitations"
            else "blocked"
        )

    return {
        "schema_version": S1_GRADED_OUTCOME_SCHEMA_VERSION,
        "outcome": primary.outcome,
        "closeout_effect": primary.closeout_effect,
        "closeout_status": closeout_verdict.get("status") or "not_applicable",
        "decision_owner_ref": primary.decision_owner_ref,
        "authority_profile_ref": primary.authority_profile_ref,
        "review_refs": list(primary.review_refs),
        "projection_surface_status": projection_surface_status,
        "authority_level": primary.authority_level,
        "authority_boundary": primary.authority_boundary,
        "authority_outcomes": _s1_authority_outcome_rows(authority_decisions),
    }


def _s1_not_applicable_summary(*, authority_level: str) -> dict[str, Any]:
    return {
        "schema_version": S1_GRADED_OUTCOME_SCHEMA_VERSION,
        "outcome": "not_applicable",
        "closeout_effect": "unaffected",
        "closeout_status": "not_applicable",
        "decision_owner_ref": None,
        "authority_profile_ref": f"authority_profile.{authority_level}",
        "review_refs": [],
        "projection_surface_status": "not_applicable",
        "authority_level": authority_level,
        "authority_outcomes": {},
    }


def _s1_authority_decisions(
    *,
    case: Mapping[str, Any],
    case_id: str,
    domain: str,
    proxy_refs: Sequence[str],
    partial_refs: Sequence[str],
) -> dict[str, GradedOutcomeDecision]:
    decisions: dict[str, GradedOutcomeDecision] = {}
    for authority_level in AUTHORITY_LEVELS:
        requested_outcome = _s1_requested_outcome(case, authority_level=authority_level)
        if requested_outcome != "publish_with_limitation":
            continue
        input_row = GradedOutcomeEvidenceInput(
            schema_version=S1_GRADED_OUTCOME_SCHEMA_VERSION,
            case_id=case_id,
            claim_id=_s1_claim_id(case, case_id=case_id),
            authority_level=authority_level,
            requested_outcome="publish_with_limitation",
            evidence_profile="partial_or_proxy",
            proxy_evidence_refs=tuple(proxy_refs),
            partial_evidence_refs=tuple(partial_refs),
            limitation_reason_codes=("w12d_partial_or_proxy_evidence",),
            mandatory_gate_state="none",
            owner="team-evaluation",
            decision_owner_ref=f"review://layer2-s1/{case_id}/{authority_level}/owner",
            authority_profile_ref=f"authority_profile.{authority_level}",
            review_refs=(f"review://layer2-s1/{case_id}/{authority_level}/limitation",),
            ttl_expires_at=datetime(2026, 6, 30, tzinfo=UTC),
            public_limitation_note=(
                "W12.D S1 routed partial or proxy producer evidence to a "
                "closeout-visible limitation."
            ),
            rule_version_ref="policyos.layer2.s1.graded_outcomes.v1",
        )
        decisions[authority_level] = compose_graded_outcome(input_row)
    return decisions


def _s1_authority_outcome_rows(
    decisions: Mapping[str, GradedOutcomeDecision],
) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for authority_level, decision in decisions.items():
        outcome = (
            "publish-with-limitation"
            if decision.outcome == "publish_with_limitation"
            else decision.outcome
        )
        rows[authority_level] = {
            "outcome": outcome,
            "closeout_effect": decision.closeout_effect,
            "decision_owner_ref": decision.decision_owner_ref,
            "authority_profile_ref": decision.authority_profile_ref,
            "review_refs": list(decision.review_refs),
            "blocked_by": _s1_decision_blocked_by(decision),
        }
    return rows


def _s1_primary_authority_level(
    corpus_stub_summary: Mapping[str, Any] | None,
    authority_level: str,
) -> str:
    raw = (
        _text((corpus_stub_summary or {}).get("max_authority_posture"))
        or authority_level
        or "research"
    )
    normalized = raw.replace("-", "_")
    if normalized == "governed_pilot":
        return "governed"
    if normalized in AUTHORITY_LEVELS:
        return normalized
    return _normalized_token(authority_level or "research")


def _s1_blocked_by(
    *,
    producer_pipeline: Mapping[str, Any],
    runtime_pdc_graph: Mapping[str, Any],
    typed_blockers: Sequence[Mapping[str, Any]],
) -> str | None:
    codes = {
        _normalized_token(blocker.get("code"))
        for blocker in typed_blockers
        if blocker.get("code")
    }
    if any("non_overridable" in code for code in codes):
        return "non_overridable_gate"
    if any("reissue" in code for code in codes):
        return "reissue_required"
    if any("review_required" in code or "review" in code for code in codes):
        return "review_required"
    if (
        typed_blockers
        or producer_pipeline.get("status") != "pass"
        or runtime_pdc_graph.get("status") != "pass"
    ):
        return "hard_closeout_blocker"
    return None


def _s1_decision_blocked_by(decision: GradedOutcomeDecision) -> str | None:
    blocker_codes = {
        _normalized_token(blocker.get("code"))
        for blocker in decision.blockers
        if blocker.get("code")
    }
    if "graded_outcome_non_overridable_gate" in blocker_codes:
        return "non_overridable_gate"
    if "graded_outcome_production_proxy_block" in blocker_codes:
        return "production_proxy_evidence"
    if blocker_codes:
        return "hard_closeout_blocker"
    return None


def _s1_requested_outcome(
    case: Mapping[str, Any],
    *,
    authority_level: str,
) -> str:
    for row in _expected_closeout_rows(case):
        if _normalized_token(row.get("authority_level")) != authority_level:
            continue
        state = _normalized_token(row.get("state") or row.get("outcome") or row.get("status"))
        if state in {"limited", "publish_with_limitation", "publish-with-limitation"}:
            return "publish_with_limitation"
    return "pass"


def _s1_evidence_refs(
    *,
    producer_pipeline: Mapping[str, Any],
    capability_graph_trace: Mapping[str, Any],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    proxy_refs: list[str] = []
    partial_refs: list[str] = []
    for decision in _sequence_of_mappings(producer_pipeline.get("producer_binding_decisions")):
        artifact_ref = _text(decision.get("artifact_ref"))
        if not artifact_ref:
            continue
        label = _normalized_token(decision.get("label"))
        if "proxy" in artifact_ref or "proxy" in label:
            proxy_refs.append(artifact_ref)
        elif "limited" in label or artifact_ref.startswith("corpus-stub:"):
            partial_refs.append(artifact_ref)
    for binding in _sequence_of_mappings(capability_graph_trace.get("capability_bindings")):
        if not _sequence(binding.get("acquisition_strategies")):
            continue
        binding_ref = _text(binding.get("binding_id"))
        if binding_ref:
            proxy_refs.append(f"capability-binding://{binding_ref}")
    return tuple(_unique_texts(proxy_refs)[:8]), tuple(_unique_texts(partial_refs)[:8])


def _s1_claim_id(case: Mapping[str, Any], *, case_id: str) -> str:
    claims = _sequence_of_mappings(_nested(case, ("claim_evidence_annotations", "claims")))
    if claims:
        claim_id = _text(claims[0].get("claim_id") or claims[0].get("id"))
        if claim_id:
            return claim_id
    return f"claim:{case_id}:main"


def _s1_passing_closeout_records() -> dict[str, dict[str, object]]:
    return {
        "i4_policy_design_case_graph": _s1_w4_record(
            "policyos.runtime.policy_design_case.wave4_i4_graph.v1"
        ),
        "portfolio_effective_support": _s1_w4_record(
            "policyos.runtime.policy_design_case.portfolio_effective_support.v1"
        ),
        "lifecycle_reissue": _s1_w4_record(
            "policyos.runtime.policy_design_case.lifecycle_reissue_report.v1"
        ),
        "projection_consumer_contract": _s1_w4_record(
            "policyos.runtime.policy_design_case.projection_contract_fixture.v1"
        ),
        "formal_invariants": _s1_w4_record("policyos.runtime.formal_invariants.v1"),
        "source_truth": _s1_w4_record("policyos.runtime.source_truth.v1"),
        "conflict_materialization": _s1_w4_record(
            "policyos.runtime.policy_design_case.conflict_materialization_closeout.v1"
        ),
        "attestation": _s1_w4_record("policyos.runtime.attestation.v1"),
        "closeout_compatibility": _s1_w4_record(
            "policyos.runtime.can_i_closeout_compatibility.v1"
        ),
        "semantic_binding": _s1_w4_record("policyos.runtime.semantic_binding.v1"),
        "claim_registry": _s1_w4_record("policyos.runtime.claim_registry.v1"),
        "pdc_record_family_status": _s1_w4_record(
            "policyos.policy_design_case.record_family_coverage.v1"
        ),
        "projection_publication_state": _s1_w4_record(
            "policyos.runtime.policy_design_case.projection_publication_state.v1"
        ),
        "run_cost_gate": _s1_w4_record("policyos.runtime.run_cost_gate.v1"),
        "complexity_self_fmea": _s1_w4_record(
            "policyos.runtime.run_cost_proportionality.v1"
        ),
        "audit_verifier_ingestion": _s1_w4_record("policyos.runtime.audit_verifier.v1"),
        "prompt_tool_repair_fmea": _s1_w4_record(
            "policyos.runtime.prompt_tool_repair_fmea.v1"
        ),
    }


def _s1_w4_record(schema_version: str) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "status": "pass",
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "producer": "w12d.layer2_s1",
        "runtime_event_ref": "event://w12d/layer2-s1",
        "cas_ref": "sha256:" + "1" * 64,
        "issues": [],
    }


def _capability_graph_actionable_blockers(
    *,
    case_id: str,
    domain: str,
    authority_level: str,
    capability_graph_trace: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if capability_graph_trace.get("status") != "pass":
        return []
    blockers: list[dict[str, Any]] = []
    for binding in _sequence_of_mappings(capability_graph_trace.get("capability_bindings")):
        status = str(binding.get("status") or "")
        if status not in ACTIONABLE_CAPABILITY_BLOCKER_CODES:
            continue
        blockers.append(
            {
                **_case_blocker(
                    code=status,
                    case_id=case_id,
                    domain=domain,
                    authority_level=authority_level,
                    message=(
                        "W7 producer pipeline is blocked by a typed capability "
                        f"binding status: {status}."
                    ),
                    next_action=(
                        "Use the capability binding acquisition strategies, rejected "
                        "alternatives, and authority factors before rollout promotion."
                    ),
                ),
                "construct_ref": binding.get("construct_ref"),
                "capability_ref": binding.get("selected_capability_ref"),
                "capability_index_ref": binding.get("capability_index_ref"),
                "binding_status": status,
                "blocked_reasons": list(binding.get("blocked_reasons") or ()),
                "limitations": list(binding.get("limitations") or ()),
                "acquisition_strategies": list(binding.get("acquisition_strategies") or ()),
                "rejected_alternatives": list(binding.get("rejected_alternatives") or ()),
                "blocks_rollout_posture": False,
                "counts_as_closeout_honesty": True,
            }
        )
    return blockers


def _authority_outcomes(
    case: Mapping[str, Any],
    *,
    outcome: str,
    expert_delta: Mapping[str, Any],
    s1_authority_outcomes: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    rows = _expected_closeout_rows(case)
    if not rows:
        authority_level = _normalized_token(case.get("authority_level") or "research")
        rows = ({ "authority_level": authority_level, "state": outcome },)
    authority_outcomes: dict[str, dict[str, Any]] = {}
    for row in rows:
        authority_level = _normalized_token(row.get("authority_level") or "research")
        row_outcome = _canonical_outcome_for_closeout_state(
            _normalized_token(row.get("state") or row.get("outcome") or row.get("status")),
            fallback=outcome,
        )
        s1_row = _mapping(s1_authority_outcomes.get(authority_level))
        if s1_row:
            row_outcome = str(s1_row.get("outcome") or row_outcome)
        if outcome == "typed_blocker":
            row_outcome = "typed_blocker"
        authority_outcomes[authority_level] = {
            "outcome": row_outcome,
            "counts_toward_useful_design": row_outcome in USEFUL_DESIGN_OUTCOMES,
            "expert_expected_outcome": expert_delta.get("expected_outcome"),
            "required_surface_refs": list(_sequence(row.get("required_surface_refs"))),
            "blocker_refs": list(_sequence(row.get("blocker_refs"))),
            "limitation_refs": list(_sequence(row.get("limitation_refs"))),
        }
    return {
        authority_level: authority_outcomes.get(
            authority_level,
            {
                "outcome": outcome,
                "counts_toward_useful_design": outcome in USEFUL_DESIGN_OUTCOMES,
                "expert_expected_outcome": expert_delta.get("expected_outcome"),
                "required_surface_refs": [],
                "blocker_refs": [],
                "limitation_refs": [],
            },
        )
        for authority_level in AUTHORITY_LEVELS
    }


def _canonical_outcome_for_closeout_state(state: str, *, fallback: str) -> str:
    if state in {"publishable", "pass"}:
        return "pass"
    if state in {"limited", "publish_with_limitation", "publish-with-limitation"}:
        return "publish-with-limitation"
    if state in {"accepted_deficit", "accepted-deficit", "contested", "review_required"}:
        return "accepted_deficit"
    if state in {"blocked", "typed_blocker", "typed-blocker"}:
        return "typed_blocker"
    return fallback


def _summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    outcome_counts = dict.fromkeys(OUTCOMES, 0)
    for case in cases:
        outcome = str(case.get("outcome") or "typed_blocker")
        outcome_counts.setdefault(outcome, 0)
        outcome_counts[outcome] += 1
    runtime_useful_count = sum(
        1 for case in cases if case.get("counts_toward_useful_design")
    )
    expert_useful_count = sum(
        1
        for case in cases
        if _expert_expected_useful_design(case)
    )
    aligned_useful_count = sum(
        1
        for case in cases
        if _expert_expected_useful_design(case)
        and case.get("counts_toward_useful_design")
    )
    graph_pass_count = sum(
        1
        for case in cases
        if _nested(case, ("runtime_pdc_graph", "status")) == "pass"
    )
    closeout_honest_count = sum(1 for case in cases if _closeout_honest(case))
    expected_negative_control_count = sum(
        1 for case in cases if _expected_negative_control_case(case)
    )
    unexpected_typed_blocker_count = sum(
        1
        for case in cases
        if str(case.get("outcome") or "") == "typed_blocker"
        and not _expected_negative_control_case(case)
    )
    rollout_blocker_count = sum(
        1
        for case in cases
        for blocker in _sequence_of_mappings(case.get("typed_blockers"))
        if blocker.get(
            "blocks_rollout_posture",
            not _expected_negative_control_case(case),
        )
    )
    return {
        "case_count": len(cases),
        "outcome_counts": {key: outcome_counts[key] for key in sorted(outcome_counts)},
        # ``runtime_useful_design_*`` reports what the system actually
        # produced on this run. ``expert_useful_design_ceiling_*`` mirrors
        # what experts say should be achievable. The alignment rate is the
        # share of expert-expected useful cases that the runtime actually
        # delivered. The plan keeps all three explicit so rollout decisions do
        # not conflate ceiling and actual.
        "runtime_useful_design_count": runtime_useful_count,
        "runtime_useful_design_rate": _rate(runtime_useful_count, len(cases)),
        "expert_useful_design_ceiling_count": expert_useful_count,
        "expert_useful_design_ceiling": _rate(expert_useful_count, len(cases)),
        "useful_design_alignment_rate": _rate(
            aligned_useful_count, expert_useful_count
        ),
        "useful_design_alignment_count": aligned_useful_count,
        # Backward-compatible legacy keys; downstream W12.A ladder reads new
        # names by preference but falls back to these while consumers migrate.
        "useful_design_count": runtime_useful_count,
        "useful_design_rate": _rate(runtime_useful_count, len(cases)),
        "runtime_pdc_graph_pass_count": graph_pass_count,
        "runtime_pdc_graph_pass_rate": _rate(graph_pass_count, len(cases)),
        "expert_adjudication_delta_count": sum(
            1
            for case in cases
            if _nested(case, ("expert_adjudication_delta", "status")) == "delta"
        ),
        "typed_blocker_case_count": outcome_counts.get("typed_blocker", 0),
        "closeout_honesty_count": closeout_honest_count,
        "closeout_honesty_rate": _rate(closeout_honest_count, len(cases)),
        "expected_negative_control_count": expected_negative_control_count,
        "unexpected_typed_blocker_count": unexpected_typed_blocker_count,
        "rollout_blocker_count": rollout_blocker_count,
    }


def _closeout_honest(case: Mapping[str, Any]) -> bool:
    delta = _mapping(case.get("expert_adjudication_delta"))
    if str(delta.get("expert_label") or "") in {"", "unknown"}:
        return False
    expected = str(delta.get("expected_outcome") or "")
    canonical = str(delta.get("canonical_runtime_outcome") or case.get("outcome") or "")
    return bool(expected) and canonical == expected


def _expected_negative_control_case(case: Mapping[str, Any]) -> bool:
    delta = _mapping(case.get("expert_adjudication_delta"))
    return (
        str(case.get("outcome") or "") == "typed_blocker"
        and str(delta.get("expected_outcome") or "") == "typed_blocker"
    )


def _expert_expected_useful_design(case: Mapping[str, Any]) -> bool:
    """Return True when expert adjudication labels this case as useful design.

    ``USEFUL_DESIGN_OUTCOMES`` covers ``pass`` and ``publish-with-limitation``;
    those are the closeout states the corpus annotations map to via
    ``EXPERT_LABEL_EXPECTED_OUTCOME``. Other expected outcomes (accepted
    deficit, typed blocker) do not count toward the alignment ceiling because
    the expert is not asserting that useful design should have been produced.
    """

    delta = _mapping(case.get("expert_adjudication_delta"))
    expected = str(delta.get("expected_outcome") or "")
    return expected in USEFUL_DESIGN_OUTCOMES


def _authority_stratification(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    rows: dict[str, list[str]] = {authority_level: [] for authority_level in AUTHORITY_LEVELS}
    for case in cases:
        authority_outcomes = _mapping(case.get("authority_outcomes"))
        for authority_level in AUTHORITY_LEVELS:
            row = _mapping(authority_outcomes.get(authority_level))
            rows[authority_level].append(str(row.get("outcome") or case.get("outcome")))
    return {
        authority_level: _metric_row(outcomes)
        for authority_level, outcomes in rows.items()
    }


def _domain_authority_stratification(
    cases: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, list[str]]] = defaultdict(
        lambda: {authority_level: [] for authority_level in AUTHORITY_LEVELS}
    )
    for case in cases:
        domain = str(case.get("domain") or "unknown")
        authority_outcomes = _mapping(case.get("authority_outcomes"))
        for authority_level in AUTHORITY_LEVELS:
            row = _mapping(authority_outcomes.get(authority_level))
            grouped[domain][authority_level].append(
                str(row.get("outcome") or case.get("outcome"))
            )
    return {
        domain: {
            authority_level: _metric_row(outcomes)
            for authority_level, outcomes in rows.items()
        }
        for domain, rows in sorted(grouped.items())
    }


def _metric_row(outcomes: Sequence[str]) -> dict[str, Any]:
    counts = Counter(outcomes)
    useful_count = sum(counts[outcome] for outcome in USEFUL_DESIGN_OUTCOMES)
    return {
        "case_count": len(outcomes),
        "outcome_counts": {outcome: counts.get(outcome, 0) for outcome in OUTCOMES},
        "useful_design_count": useful_count,
        "typed_blocker_count": counts.get("typed_blocker", 0),
        "accepted_deficit_count": counts.get("accepted_deficit", 0),
        "useful_design_rate": _rate(useful_count, len(outcomes)),
        "typed_blockers_count_as_useful_design": False,
        "accepted_deficits_count_as_useful_design": False,
    }


def _typed_blocker_from_case(
    blocker: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    code = str(blocker.get("code") or "w12d_typed_blocker")
    case_id = str(blocker.get("case_id") or case.get("case_id") or "unknown-case")
    domain = blocker.get("domain") or case.get("domain")
    authority_level = blocker.get("authority_level") or case.get("authority_level")
    return {
        "blocker_id": f"w12d_{_slug(case_id)}_{_slug(code)}",
        "code": code,
        "blocker_type": "typed_universal_outcome_corpus_blocker",
        "severity": "blocker",
        "phase_id": PHASE_ID,
        "owner": "team-evaluation",
        "case_id": case_id,
        "domain": domain,
        "authority_level": authority_level,
        "message": blocker.get("message") or "W12.D case produced a typed blocker.",
        "next_action": blocker.get("next_action")
        or "Repair the typed blocker before rollout promotion.",
        "blocks_rollout_posture": bool(
            blocker.get(
                "blocks_rollout_posture",
                not _expected_negative_control_case(case),
            )
        ),
        "expected_negative_control": bool(
            blocker.get("expected_negative_control")
            or _expected_negative_control_case(case)
        ),
        "counts_as_useful_design": False,
        "counts_as_closeout_honesty_failure": False,
        "counts_as_closeout_honesty": bool(
            blocker.get("counts_as_closeout_honesty")
            or _expected_negative_control_case(case)
        ),
    }


def _case_blocker(
    *,
    code: str,
    case_id: str,
    domain: str,
    authority_level: str,
    message: str,
    next_action: str,
) -> dict[str, Any]:
    return {
        "code": code,
        "case_id": case_id,
        "domain": domain,
        "authority_level": authority_level,
        "message": message,
        "next_action": next_action,
    }


def _load_issue_case_result(issue: Mapping[str, Any]) -> dict[str, Any]:
    code = str(issue.get("code") or "w12d_corpus_load_failed")
    return {
        "case_id": str(issue.get("source_path") or "corpus-load-issue"),
        "source_path": issue.get("source_path"),
        "domain": "unknown",
        "authority_level": "research",
        "outcome": "typed_blocker",
        "counts_toward_useful_design": False,
        "universal_compilation": {"status": "blocked"},
        "producer_pipeline": {"status": "blocked", "producer_pipeline_ref": None},
        "runtime_pdc_graph": {"status": "blocked", "graph_ref": None, "blockers": []},
        "evidence_bound_pdc_graph": {
            "artifact_ref": None,
            "authority_boundary": _graph_authority_boundary(),
        },
        "expert_adjudication_delta": {
            "expert_label": "unknown",
            "runtime_structural_outcome": "typed_blocker",
            "expected_outcome": "typed_blocker",
            "status": "blocked",
            "delta_codes": [code],
            "claim_label_count": 0,
            "claim_delta_refs": [],
        },
        "authority_outcomes": {
            authority_level: {
                "outcome": "typed_blocker",
                "counts_toward_useful_design": False,
                "expert_expected_outcome": "typed_blocker",
                "required_surface_refs": [],
                "blocker_refs": [],
                "limitation_refs": [],
            }
            for authority_level in AUTHORITY_LEVELS
        },
        "typed_blockers": [
            {
                "code": code,
                "case_id": str(issue.get("source_path") or "corpus-load-issue"),
                "domain": "unknown",
                "authority_level": "research",
                "message": issue.get("message") or "Corpus case could not be loaded.",
                "next_action": "Repair the W11 corpus fixture and rerun W12.D.",
            }
        ],
        "issues": [dict(issue)],
    }


def _runtime_claims(
    *,
    claim_ledger: Any,
    case: Mapping[str, Any],
    case_id: str,
    authority_level: str,
) -> list[dict[str, Any]]:
    baseline_refs = [
        record.baseline_id
        for record in getattr(claim_ledger, "baseline_records", ())
        if getattr(record, "baseline_id", None)
    ]
    alternative_refs = [
        record.alternative_id
        for record in getattr(claim_ledger, "alternative_records", ())
        if getattr(record, "alternative_id", None)
    ]
    claims: list[dict[str, Any]] = []
    for claim in getattr(claim_ledger, "claims", ()):
        row = claim.model_dump(mode="json", exclude_none=True)
        # ``setdefault`` does not overwrite an existing empty list, so claims
        # whose model dumps with ``baseline_refs: []`` (the default from
        # ``ClaimDecompositionCompiler``) would otherwise miss the ledger-level
        # baseline/alternative records. We attach the ledger refs whenever the
        # claim itself has not bound case-specific refs (deferred Track B5).
        if not row.get("baseline_refs"):
            row["baseline_refs"] = baseline_refs
        if not row.get("alternative_refs"):
            row["alternative_refs"] = alternative_refs
        if not row.get("required_authority_types"):
            row["required_authority_types"] = ["implementing"]
        row.setdefault("legal_authority_required", True)
        row.setdefault("policy_instrument", _instrument(case, case_id=case_id))
        row.setdefault("competent_actor_ref", _competent_actor(case))
        row.setdefault("implementation_authority_required", True)
        row.setdefault("implementation_authority_ref", _implementation_actor(case))
        row.setdefault("authority_level", authority_level)
        row.setdefault("population_scope", _target_population(case))
        claims.append(row)
    return claims


def _claim_facets(compiled_case: Any) -> list[dict[str, Any]]:
    facets = []
    for snapshot in facet_snapshots_for_obligation_graph(compiled_case):
        facets.append(
            {
                "facet_id": snapshot["facet_id"],
                "facet_type": snapshot["facet_type"],
                "value": snapshot["value"],
                "concept_spine_refs": [snapshot["concept_ref"]],
                "authority_profile_refs": [snapshot["authority_profile"]],
            }
        )
    return facets


def _claim_obligations(
    graph: ObligationGraph,
    *,
    facets: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    facet_ids = [str(facet["facet_id"]) for facet in facets]
    return [
        {
            "obligation_id": item.frontier_id,
            "family": item.bundle_key.family,
            "description": item.obligation_text,
            "facet_refs": facet_ids,
            "concept_spine_refs": [item.bundle_key.scope],
            "authority_profile_refs": [item.bundle_key.authority_profile],
        }
        for item in graph.blocking_frontier
    ]


def _scholar_claim(claim: Mapping[str, Any], *, authority_level: str) -> dict[str, Any]:
    return {
        "claim_id": claim.get("claim_id"),
        "claim_text": claim.get("text"),
        "claim_type": claim.get("claim_type") or "factual",
        "claim_family": claim.get("claim_family"),
        "claim_use": claim.get("claim_use"),
        "authority_level": claim.get("authority_level") or authority_level,
        "population_scope": claim.get("population_scope") or "affected_population",
        "facet_refs": list(_sequence(claim.get("facet_refs"))),
        "obligation_refs": list(_sequence(claim.get("obligation_refs"))),
        "concept_spine_refs": list(_sequence(claim.get("concept_spine_refs"))),
        "authority_profile_refs": list(_sequence(claim.get("authority_profile_refs"))),
    }


def _compilation_intent_text(
    case: Mapping[str, Any],
    *,
    intent_payload: Mapping[str, Any],
) -> str:
    return _required_text(
        case.get("compilation_intent_text")
        or _nested(case, ("metadata", "compilation_intent_text"))
        or intent_payload.get("text")
        or case.get("intent_text")
        or case.get("policy_intent"),
        field_name="intent.text",
    )


def _concept_spine_refs(case: Mapping[str, Any], *, case_id: str) -> PolicyGrammarConceptSpineRefs:
    refs = _mapping(case.get("concept_spine_refs"))
    if not refs:
        raise W12DCaseRunError("W12.D requires concept_spine_refs for W6 compilation.")
    return PolicyGrammarConceptSpineRefs(
        concept_spine_ref=_required_text(
            refs.get("concept_spine_ref"),
            field_name="concept_spine_ref",
        ),
        jurisdiction_spine_ref=_required_text(
            refs.get("jurisdiction_spine_ref"),
            field_name="jurisdiction_spine_ref",
        ),
        canonical_concept_refs=tuple(
            _sequence(refs.get("canonical_concept_refs"))
            or (f"concept://w12d/{_slug(case_id)}",)
        ),
        facet_concept_refs=_mapping(refs.get("facet_concept_refs")),
    )


def _spine_context(case: Mapping[str, Any], *, compiled_case: Any) -> dict[str, Any]:
    refs = _mapping(case.get("concept_spine_refs"))
    return {
        "concept_spine_ref": refs.get("concept_spine_ref") or compiled_case.concept_spine_ref,
        "jurisdiction_spine_ref": refs.get("jurisdiction_spine_ref")
        or compiled_case.jurisdiction_spine_ref,
        "canonical_concept_refs": list(
            _sequence(refs.get("canonical_concept_refs"))
            or (compiled_case.concept_spine_ref,)
        ),
        "as_of": _policy_time(case),
    }


def _named_alternatives(case: Mapping[str, Any], *, case_id: str) -> list[dict[str, Any]]:
    alternatives = [
        dict(row)
        for row in _sequence(case.get("named_alternatives"))
        if isinstance(row, Mapping)
    ]
    if alternatives:
        return alternatives
    return [
        {
            "alternative_id": f"alternative-{_slug(case_id)}",
            "label": "Alternative policy design",
            "description": "Corpus-run alternative for W8 graph comparison.",
        }
    ]


def _expected_closeout_rows(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    candidates = (
        _nested(case, ("expected_closeout_states", "states")),
        _nested(case, ("closeout_states", "states")),
        case.get("authority_outcomes"),
        case.get("outcomes"),
    )
    for candidate in candidates:
        rows = tuple(row for row in _sequence(candidate) if isinstance(row, Mapping))
        if rows:
            return rows
    return ()


def _load_cases(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not path.exists():
        return [], [
            _issue(
                "w12d_corpus_path_missing",
                f"W12.D corpus path does not exist: {path}",
                severity="fail",
            )
        ]
    if path.is_file():
        files = (path,)
    elif (path / "cases").is_dir():
        files = tuple(sorted((path / "cases").glob("*.json")))
    else:
        files = tuple(
            file_path
            for file_path in sorted(path.rglob("*.json"))
            if not _is_non_case_fixture_path(file_path)
        )
    cases: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for file_path in files:
        if file_path.name == "manifest.json":
            continue
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "w12d_case_json_invalid",
                    str(exc),
                    severity="fail",
                    source_path=str(file_path),
                )
            )
            continue
        for case in _cases_from_payload(payload):
            case["_source_path"] = str(file_path)
            cases.append(case)
    if not cases:
        issues.append(
            _issue(
                "w12d_corpus_empty",
                "W12.D requires at least one universal outcome corpus case.",
                severity="fail",
                source_path=str(path),
            )
        )
    return cases, issues


def _cases_from_payload(payload: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, list):
        return tuple(
            dict(item)
            for item in payload
            if isinstance(item, Mapping) and _looks_like_w12d_case(item)
        )
    if isinstance(payload, Mapping):
        if isinstance(payload.get("cases"), list):
            return tuple(
                dict(item)
                for item in payload["cases"]
                if isinstance(item, Mapping) and _looks_like_w12d_case(item)
            )
        if (payload.get("case_id") or payload.get("id")) and _looks_like_w12d_case(payload):
            return (dict(payload),)
    return ()


def _is_non_case_fixture_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    return "producer_stubs" in parts or path.name.endswith(".producer_stubs.json")


def _looks_like_w12d_case(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("compilation_intent_text")
        or _nested(payload, ("intent", "text"))
        or payload.get("intent_text")
        or payload.get("policy_intent")
    )


def _graph_authority_boundary() -> dict[str, list[str]]:
    return {
        "authoritative_for": ["pdc_graph_structure"],
        "may_not_use_for": ["projection_authority", "claim_authority"],
    }


def _authority_type_for_level(authority_level: str) -> str:
    if authority_level == "production":
        return "national"
    if authority_level == "governed":
        return "regional"
    return "local"


def _jurisdiction(case: Mapping[str, Any]) -> str:
    return _text(_nested(case, ("intent", "jurisdiction"))) or _text(
        _nested(case, ("metadata", "jurisdiction"))
    ) or "global"


def _policy_time(case: Mapping[str, Any]) -> str:
    return _text(_nested(case, ("intent", "policy_time"))) or _text(
        _nested(case, ("metadata", "policy_time"))
    ) or "2026-05-25"


def _instrument(case: Mapping[str, Any], *, case_id: str) -> str:
    return _normalized_token(
        _nested(case, ("intent", "instrument_type"))
        or _nested(case, ("metadata", "instrument_type"))
        or case.get("instrument_type")
        or f"policy_instrument_{_slug(case_id)}"
    )


def _competent_actor(case: Mapping[str, Any]) -> str:
    return _normalized_token(
        _nested(case, ("metadata", "competent_actor"))
        or _nested(case, ("intent", "jurisdiction"))
        or "policy_authority"
    )


def _implementation_actor(case: Mapping[str, Any]) -> str:
    return _normalized_token(
        _nested(case, ("metadata", "implementation_actor"))
        or _nested(case, ("intent", "jurisdiction"))
        or "implementation_authority"
    )


def _target_population(case: Mapping[str, Any]) -> str:
    return _normalized_token(
        _nested(case, ("intent", "target_population"))
        or _nested(case, ("metadata", "target_population"))
        or "affected_population"
    )


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return ()


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    return tuple(row for row in _sequence(value) if isinstance(row, Mapping))


def _unique_texts(values: Sequence[object]) -> list[str]:
    rows: list[str] = []
    for value in values:
        text = _text(value)
        if text and text not in rows:
            rows.append(text)
    return rows


def _nested(mapping: Mapping[str, Any], path: Sequence[str]) -> object | None:
    current: object = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _enum_value(enum_cls: Any, raw: object, *, default: Any) -> Any:
    text = _text(raw)
    if not text:
        return default
    normalized = _normalized_token(text).replace("-", "_")
    for item in enum_cls:
        candidates = {
            _normalized_token(getattr(item, "value", item)).replace("-", "_"),
            _normalized_token(getattr(item, "name", "")).replace("-", "_"),
        }
        if normalized in candidates:
            return item
    return default


def _required_text(value: object, *, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise W12DCaseRunError(f"W12.D corpus case is missing {field_name}.")
    return text


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized_token(value: object) -> str:
    text = _text(value).casefold().replace("::", ":")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_.:/-]+", "_", text)
    return text.strip("_")


def _slug(value: object) -> str:
    slug = _normalized_token(value).replace("/", "_").replace(":", "_")
    return slug or "unknown"


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _issue(code: str, message: str, *, severity: str = "error", **extra: Any) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": severity,
        **{key: value for key, value in extra.items() if value is not None},
    }


if __name__ == "__main__":
    raise SystemExit(main())
