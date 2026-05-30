#!/usr/bin/env python3
"""Audit W11.E compilation truthfulness against adjudicated corpus annotations."""

from __future__ import annotations

# ruff: noqa: ANN401
import argparse
import json
import re
import sys
import tempfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.core.contracts.runtime import UniversalAuthorityProfile  # noqa: E402
from polisyos.ir.governance.policy_composition import PolicyLayerLevel  # noqa: E402
from polisyos.ir.governance.problem_frame import ProblemDomain  # noqa: E402
from polisyos.obligation_graph import (  # noqa: E402
    ComplexityBudget,
    ObligationGraph,
    compile_obligation_graph,
)
from polisyos.obligation_rules import build_seed_obligation_rule_catalog  # noqa: E402
from polisyos.policy_grammar import (  # noqa: E402
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    facet_snapshots_for_obligation_graph,
)
from polisyos.runtime.quality.capability_ratchet import PURPOSE_MULTIPLIERS  # noqa: E402
from polisyos.runtime.quality.construct_registry import load_construct_registry  # noqa: E402
from polisyos.runtime.quality.producer_pipeline import (  # noqa: E402
    run_eight_stage_producer_pipeline,
)
from polisyos.scientist.policy_design.claim_decomposition import (  # noqa: E402
    ClaimDecompositionCompiler,
)

SCHEMA_VERSION = "policyos.policy_design_case.compilation_truthfulness.v1"
TOOL_NAME = "quality.validation.check-compilation-truthfulness"
GENERATED_AT = "2026-05-24T00:00:00Z"
DEFAULT_CORPUS_PATH = Path("tests/fixtures/universal-corpus")
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/compilation_truthfulness_report.json")

W11E_BUCKETS = (
    "true_positive_obligations",
    "missed_obligations",
    "hallucinated_obligations",
    "scope_drift_obligations",
    "authority_drift_obligations",
)
SCORE_WEIGHTS: Mapping[str, float] = {
    "true_positive_obligations": PURPOSE_MULTIPLIERS["evidence_producer"],
    "missed_obligations": PURPOSE_MULTIPLIERS["authority_gate"],
    "hallucinated_obligations": PURPOSE_MULTIPLIERS["authority_gate"],
    "scope_drift_obligations": PURPOSE_MULTIPLIERS["closeout_input"],
    "authority_drift_obligations": PURPOSE_MULTIPLIERS["authority_gate"],
}
EXPECTED_ANNOTATION_STATUSES = frozenset(
    {
        "",
        "required",
        "expected",
        "active",
        "governed",
        "mandatory",
        "review_required",
        "limitation_required",
        "contested",
    }
)
NON_EXPECTED_ANNOTATION_STATUSES = frozenset(
    {"not_required", "rejected", "out_of_scope", "withdrawn", "deprecated"}
)


class CompilationTruthfulnessInputError(ValueError):
    """Raised when a W11 corpus case cannot feed the compilation path."""


def build_compilation_truthfulness_report(
    *,
    repo_root: str | Path = REPO_ROOT,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Compile each corpus case and report W11.E truthfulness metrics.

    Args:
        repo_root: Product repository root. It is recorded for traceability.
        corpus_path: JSON case file or directory containing W11.D case fixtures.
        generated_at: Deterministic report timestamp.

    Returns:
        Machine-readable report with per-case W11.E buckets, weighted scores,
        aggregate truthfulness rate, and domain/authority slices.
    """

    root = Path(repo_root).resolve()
    corpus = Path(corpus_path)
    if not corpus.is_absolute():
        corpus = root / corpus
    cases, load_issues = _load_cases(corpus)
    case_reports = [
        _audit_case(case, repo_root=root, source_path=case.get("_source_path"))
        for case in cases
    ]
    issues = [*load_issues, *(issue for case in case_reports for issue in case["issues"])]
    if not cases:
        issues.append(
            _issue(
                "w11e_corpus_empty",
                "Compilation truthfulness requires at least one W11 outcome corpus case.",
                severity="fail",
            )
        )
    validation_status = (
        "fail" if any(issue.get("severity") == "fail" for issue in issues) else "pass"
    )
    summary = _summary(case_reports, status=validation_status)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "repo_root": str(root),
        "corpus_path": str(corpus),
        "score_weights": dict(SCORE_WEIGHTS),
        "summary": summary,
        "cases": case_reports,
        "issues": issues,
    }


def validate_compilation_truthfulness_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate that a W11.E report preserves the required error buckets."""

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            _issue(
                "compilation_truthfulness_schema_version_invalid",
                "Report schema_version does not match the W11.E contract.",
                severity="fail",
                expected=SCHEMA_VERSION,
                actual=payload.get("schema_version"),
            )
        )
    cases = payload.get("cases")
    if not isinstance(cases, list):
        issues.append(
            _issue(
                "compilation_truthfulness_cases_missing",
                "Report must contain a cases array.",
                severity="fail",
            )
        )
        cases = []
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping):
            issues.append(
                _issue(
                    "compilation_truthfulness_case_invalid",
                    "Each case report must be a mapping.",
                    severity="fail",
                    case_index=index,
                )
            )
            continue
        for bucket in W11E_BUCKETS:
            if bucket not in case:
                issues.append(
                    _issue(
                        "compilation_truthfulness_bucket_missing",
                        (
                            "W11.E reports must separate true_positive, missed, "
                            "hallucinated, scope_drift, and authority_drift buckets."
                        ),
                        severity="fail",
                        case_id=case.get("case_id"),
                        bucket=bucket,
                    )
                )
            elif not isinstance(case.get(bucket), list):
                issues.append(
                    _issue(
                        "compilation_truthfulness_bucket_invalid",
                        "W11.E bucket values must be arrays.",
                        severity="fail",
                        case_id=case.get("case_id"),
                        bucket=bucket,
                    )
                )
        if not isinstance(case.get("per_case_truthfulness_score"), int | float):
            issues.append(
                _issue(
                    "compilation_truthfulness_score_missing",
                    "Each case must report per_case_truthfulness_score.",
                    severity="fail",
                    case_id=case.get("case_id"),
                )
            )
    summary = payload.get("summary")
    if not isinstance(summary, Mapping) or "aggregate_compilation_truthfulness_rate" not in summary:
        issues.append(
            _issue(
                "compilation_truthfulness_summary_invalid",
                "Report summary must include aggregate_compilation_truthfulness_rate.",
                severity="fail",
            )
        )
    return {"status": "fail" if issues else "pass", "issues": issues}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for W11.E compilation truthfulness auditing."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        default=str(REPO_ROOT),
        help="Policy engine repository root.",
    )
    parser.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS_PATH),
        help="W11.D case file or directory. Ignored when --self-test is used.",
    )
    parser.add_argument("--output", default=None, help="Write report JSON to this path.")
    parser.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="Return non-zero when aggregate truthfulness is below this 0-100 score.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run a built-in W11.E smoke corpus instead of reading --corpus.",
    )
    args = parser.parse_args(argv)

    output = Path(args.output) if args.output else None
    if args.self_test:
        with tempfile.TemporaryDirectory(prefix="policyos-w11e-self-test-") as tmp:
            corpus_dir = Path(tmp) / "corpus"
            corpus_dir.mkdir(parents=True)
            atomic_write_json(corpus_dir / "self-test-case.json", _self_test_case_payload())
            report = build_compilation_truthfulness_report(
                repo_root=args.repo_root,
                corpus_path=corpus_dir,
            )
    else:
        report = build_compilation_truthfulness_report(
            repo_root=args.repo_root,
            corpus_path=args.corpus,
        )

    validation = validate_compilation_truthfulness_report(report)
    if validation["issues"]:
        report["issues"] = [*report.get("issues", []), *validation["issues"]]
        report["summary"]["status"] = "fail"
    if output is not None:
        atomic_write_json(output, report)
    else:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")

    aggregate = float(report["summary"]["aggregate_compilation_truthfulness_rate"])
    if validation["status"] == "fail" or report["summary"]["status"] == "fail":
        return 1
    if args.fail_under is not None and aggregate < args.fail_under:
        return 1
    return 0


def test_self_test_cli_contract(tmp_path: Path) -> None:
    """Pytest-compatible self-test for the documented W11.E command contract."""

    output = tmp_path / "compilation-truthfulness-self-test.json"
    exit_code = main(["--self-test", "--output", str(output)])
    if exit_code != 0:
        raise AssertionError(f"W11.E self-test exited with {exit_code}")
    payload = json.loads(output.read_text(encoding="utf-8"))
    validation = validate_compilation_truthfulness_report(payload)
    if validation["status"] != "pass":
        raise AssertionError(validation["issues"])


def _audit_case(
    case: Mapping[str, Any],
    *,
    repo_root: Path,
    source_path: object | None = None,
) -> dict[str, Any]:
    case_id = _required_text(
        case.get("case_id") or case.get("id") or case.get("name"),
        field_name="case_id",
    )
    domain = _normalized_token(case.get("domain") or _nested(case, ("intent", "problem_domain")))
    authority_level = _normalized_token(
        case.get("authority_level")
        or _nested(case, ("intent", "authority_level"))
        or _nested(case, ("expert_adjudication", "authority_level"))
        or _nested(case, ("claim_evidence_annotations", "authority_level"))
        or "research"
    )
    issues: list[dict[str, Any]] = []
    if not _annotation_obligations(case):
        issues.append(
            _issue(
                "w11b_annotations_missing",
                "W11.E cannot score a case without W11.B obligation annotations.",
                severity="fail",
                case_id=case_id,
            )
        )
    adjudication = _mapping(case.get("expert_adjudication") or case.get("adjudication"))
    if not adjudication:
        issues.append(
            _issue(
                "w11c_adjudication_missing",
                "W11.E cannot count truthfulness without W11.C expert adjudication.",
                severity="fail",
                case_id=case_id,
            )
        )

    compiled_obligations: list[dict[str, Any]] = []
    obligation_graph_ref = None
    claim_decomposition_ref = None
    producer_pipeline_status = "blocked"
    producer_pipeline_ref = None
    compilation_status = "blocked"
    try:
        compiled = _run_w6_w7(case, repo_root=repo_root, case_id=case_id)
        compiled_obligations = _compiled_obligation_records(compiled["obligation_graph"])
        obligation_graph_ref = compiled["obligation_graph"].graph_id
        claim_decomposition_ref = compiled["claim_decomposition_ref"]
        producer_pipeline_status = str(compiled["producer_pipeline"].get("status") or "blocked")
        producer_pipeline_ref = compiled["producer_pipeline"].get("producer_pipeline_ref")
        compilation_status = "pass"
    except Exception as exc:
        code = getattr(exc, "code", "w11e_compilation_failed")
        issues.append(
            _issue(
                str(code),
                str(exc),
                severity="fail",
                case_id=case_id,
            )
        )

    annotations = _expected_annotation_records(case)
    buckets = _compare_obligations(
        compiled_obligations=compiled_obligations,
        annotations=annotations,
    )
    construct_vocabulary = _compare_construct_vocabulary(
        case_id=case_id,
        case=case,
        compiled_obligations=compiled_obligations,
        annotations=annotations,
        obligation_buckets=buckets,
    )
    score = (
        0.0
        if any(issue.get("severity") == "fail" for issue in issues)
        else _score_buckets(buckets)
    )
    status = "blocked" if any(issue.get("severity") == "fail" for issue in issues) else "pass"
    return {
        "case_id": case_id,
        "source_path": str(source_path) if source_path else None,
        "domain": domain,
        "authority_level": authority_level,
        "status": status,
        "compilation_status": compilation_status,
        "producer_pipeline_status": producer_pipeline_status,
        "obligation_graph_ref": obligation_graph_ref,
        "claim_decomposition_ref": claim_decomposition_ref,
        "producer_pipeline_ref": producer_pipeline_ref,
        "adjudication_label": _text(adjudication.get("case_label") if adjudication else None),
        "score_weights": dict(SCORE_WEIGHTS),
        **buckets,
        "construct_vocabulary": construct_vocabulary,
        "per_case_truthfulness_score": score,
        "issues": issues,
    }


def _run_w6_w7(
    case: Mapping[str, Any],
    *,
    repo_root: Path,
    case_id: str,
) -> dict[str, Any]:
    del repo_root
    run_id = _required_text(case.get("run_id") or f"run-{case_id}", field_name="run_id")
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
        raise CompilationTruthfulnessInputError(
            "W6.A grammar compilation blocked: " + ", ".join(blocker_codes)
        )

    compilation_inputs = _mapping(case.get("compilation_inputs"))
    governed_rules: Sequence[Any]
    if "governed_rules" in compilation_inputs:
        governed_rules = _sequence(compilation_inputs.get("governed_rules"))
    elif compilation_inputs.get("use_seed_rule_catalog") is False:
        governed_rules = ()
    else:
        governed_rules = build_seed_obligation_rule_catalog().rules
    graph = compile_obligation_graph(
        run_id=run_id,
        facets=facet_snapshots_for_obligation_graph(compiled_case),
        governed_rules=governed_rules,
        candidate_sources=_sequence(
            compilation_inputs.get("candidate_sources") or case.get("candidate_sources")
        ),
        complexity_budget=ComplexityBudget.model_validate(
            _mapping(compilation_inputs.get("complexity_budget")) or {}
        ),
        generated_at=datetime(2026, 5, 24, tzinfo=UTC),
        graph_id=f"obligation-graph-{_slug(case_id)}",
        intent_text=intent_text,
    )
    if not graph.blocking_frontier:
        raise CompilationTruthfulnessInputError(
            "W6.C compiled no blocking frontier obligations for W11.E audit."
        )

    claim_payload = {
        "run_id": run_id,
        "intent": intent_text,
        "facets": _claim_facets(compiled_case),
        "obligations": _claim_obligations(graph),
        "named_alternatives": _named_alternatives(case, case_id=case_id),
        "concept_spine_refs": [compiled_case.concept_spine_ref],
        "authority_profile_refs": [compiled_case.authority_profile.profile_id],
        "metadata": {"producer": "w11e_compilation_truthfulness_audit"},
    }
    claim_ledger = ClaimDecompositionCompiler().compile(claim_payload)
    claim_decomposition_ref = f"claim-ledger:{_slug(run_id)}"
    pipeline = _run_producer_pipeline(
        case,
        run_id=run_id,
        authority_level=authority_level,
        compiled_case=compiled_case,
        graph=graph,
        claim_ledger=claim_ledger,
        claim_decomposition_ref=claim_decomposition_ref,
    )
    return {
        "compiled_case": compiled_case,
        "obligation_graph": graph,
        "claim_ledger": claim_ledger,
        "claim_decomposition_ref": claim_decomposition_ref,
        "producer_pipeline": pipeline,
    }


def _run_producer_pipeline(
    case: Mapping[str, Any],
    *,
    run_id: str,
    authority_level: str,
    compiled_case: Any,
    graph: ObligationGraph,
    claim_ledger: Any,
    claim_decomposition_ref: str,
) -> dict[str, Any]:
    pipeline_payload = _mapping(case.get("producer_pipeline"))
    producers = _sequence(pipeline_payload.get("producers") or case.get("producers"))
    claims = _pipeline_claims(
        claim_ledger,
        requirement_refs=[item.frontier_id for item in graph.blocking_frontier],
    )
    return run_eight_stage_producer_pipeline(
        run_id=run_id,
        job_id=_text(case.get("job_id")) or f"job-{_slug(run_id)}",
        tenant_id=_text(case.get("tenant_id")) or "w11e-truthfulness-audit",
        request_ref=_text(case.get("request_ref")) or f"request:{_slug(run_id)}",
        authority_profile=authority_level,
        spine_context=_spine_context(case, compiled_case=compiled_case),
        claims=claims,
        producers=producers,
        scenario_refs=_sequence(case.get("scenario_refs")),
        universal_grammar_compilation={
            "status": "pass",
            "artifact_ref": compiled_case.case_id,
        },
        obligation_graph={"status": "pass", "graph_ref": graph.graph_id},
        claim_decomposition={"status": "pass", "artifact_ref": claim_decomposition_ref},
    )


def _pipeline_claims(claim_ledger: Any, *, requirement_refs: Sequence[str]) -> list[dict[str, Any]]:
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
        if not row.get("baseline_refs"):
            row["baseline_refs"] = baseline_refs
        if not row.get("alternative_refs"):
            row["alternative_refs"] = alternative_refs
        if not row.get("requirement_refs"):
            row["requirement_refs"] = list(requirement_refs)
        claims.append(row)
    return claims


def _compare_obligations(
    *,
    compiled_obligations: Sequence[Mapping[str, Any]],
    annotations: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    matches: list[tuple[Mapping[str, Any], Mapping[str, Any], str]] = []
    unmatched_compiled = list(compiled_obligations)
    missed: list[dict[str, Any]] = []
    for annotation in annotations:
        match = _best_compiled_match(annotation, unmatched_compiled)
        if match is None:
            missed.append(dict(annotation))
            continue
        compiled, basis = match
        unmatched_compiled.remove(compiled)
        matches.append((annotation, compiled, basis))

    true_positive: list[dict[str, Any]] = []
    scope_drift: list[dict[str, Any]] = []
    authority_drift: list[dict[str, Any]] = []
    for annotation, compiled, basis in matches:
        scope_changed = _scope_drift(annotation, compiled)
        authority_changed = _authority_drift(annotation, compiled)
        row = _match_row(annotation, compiled, match_basis=basis)
        if scope_changed:
            scope_drift.append(
                {
                    **row,
                    "expected_scope": _text(annotation.get("scope")),
                    "compiled_scope": _text(compiled.get("scope")),
                }
            )
        if authority_changed:
            authority_drift.append(
                {
                    **row,
                    "expected_authority_level": _annotation_authority(annotation),
                    "compiled_authority_level": _compiled_authority(compiled),
                }
            )
        if not scope_changed and not authority_changed:
            true_positive.append(row)

    return {
        "true_positive_obligations": true_positive,
        "missed_obligations": missed,
        "hallucinated_obligations": [dict(item) for item in unmatched_compiled],
        "scope_drift_obligations": scope_drift,
        "authority_drift_obligations": authority_drift,
    }


def _score_buckets(buckets: Mapping[str, Sequence[Any]]) -> float:
    positive = len(buckets["true_positive_obligations"]) * SCORE_WEIGHTS[
        "true_positive_obligations"
    ]
    penalty = sum(
        len(buckets[bucket]) * SCORE_WEIGHTS[bucket]
        for bucket in W11E_BUCKETS
        if bucket != "true_positive_obligations"
    )
    if positive == 0.0 and penalty == 0.0:
        return 100.0
    return round(100.0 * positive / (positive + penalty), 2)


def _best_compiled_match(
    annotation: Mapping[str, Any],
    compiled_obligations: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], str] | None:
    if not compiled_obligations:
        return None
    scored = [
        (_match_score(annotation, compiled), compiled)
        for compiled in compiled_obligations
    ]
    scored.sort(key=lambda item: item[0][0], reverse=True)
    (score, basis), compiled = scored[0]
    if score >= 40:
        return compiled, basis
    family = _normalized_token(annotation.get("family"))
    if family:
        family_matches = [
            compiled
            for compiled in compiled_obligations
            if _normalized_token(compiled.get("family")) == family
        ]
        if len(family_matches) == 1:
            return family_matches[0], "unique_family"
    return None


def _match_score(
    annotation: Mapping[str, Any],
    compiled: Mapping[str, Any],
) -> tuple[int, str]:
    annotation_ids = {
        _normalized_token(value)
        for value in (
            annotation.get("annotation_id"),
            annotation.get("compiled_obligation_id"),
            annotation.get("compiled_ref"),
            annotation.get("obligation_id"),
            annotation.get("id"),
        )
        if _text(value)
    }
    compiled_ids = {
        _normalized_token(value)
        for value in (
            compiled.get("compiled_obligation_id"),
            compiled.get("frontier_id"),
            compiled.get("bundle_id"),
            compiled.get("annotation_id"),
            compiled.get("annotation_obligation_id"),
            *(_sequence(compiled.get("candidate_refs"))),
        )
        if _text(value)
    }
    if annotation_ids.intersection(compiled_ids):
        return 100, "explicit_id"
    score = 0
    basis: list[str] = []
    if _normalized_token(annotation.get("family")) == _normalized_token(compiled.get("family")):
        score += 20
        basis.append("family")
    if _annotation_remedy(annotation) and _annotation_remedy(annotation) == _normalized_token(
        compiled.get("remedy_path")
    ):
        score += 25
        basis.append("remedy_path")
    similarity = _text_similarity(_annotation_text(annotation), _compiled_text(compiled))
    if similarity >= 0.45:
        score += 20
        basis.append("text_similarity")
    return score, "+".join(basis) or "no_match"


def _compiled_obligation_records(graph: ObligationGraph) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in graph.blocking_frontier:
        metadata = dict(getattr(item, "metadata", {}) or {})
        records.append(
            {
                "compiled_obligation_id": item.frontier_id,
                "bundle_id": item.bundle_id,
                "annotation_obligation_id": _text(metadata.get("annotation_obligation_id")),
                "family": item.bundle_key.family,
                "remedy_path": item.bundle_key.remedy_path,
                "scope": item.bundle_key.scope,
                "authority_level": item.bundle_key.authority_profile,
                "temporal_window": item.bundle_key.temporal_window,
                "obligation_text": item.obligation_text,
                "priority_class": item.priority_class.value,
                "source_classes": [source.value for source in item.source_classes],
                "candidate_refs": list(item.candidate_refs),
                "required_evidence_constructs": _construct_refs(
                    metadata.get("required_evidence_constructs")
                    or metadata.get("construct_refs")
                ),
                "truthfulness_scope": (
                    "vertical_case_annotation"
                    if metadata.get("annotation_obligation_id")
                    else "horizontal_governance"
                ),
            }
        )
    vertical_annotation_records = [
        row for row in records if row.get("annotation_obligation_id")
    ]
    if vertical_annotation_records:
        records = vertical_annotation_records
    records.sort(
        key=lambda row: (
            str(row["family"]),
            str(row["remedy_path"]),
            str(row["compiled_obligation_id"]),
        )
    )
    return records


def _expected_annotation_records(case: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(_annotation_obligations(case)):
        status = _normalized_token(row.get("status"))
        if status in NON_EXPECTED_ANNOTATION_STATUSES:
            continue
        if status not in EXPECTED_ANNOTATION_STATUSES:
            status = status or "expected"
        records.append(
            {
                "annotation_id": _text(row.get("obligation_id") or row.get("id"))
                or f"annotation-obligation-{index:04d}",
                "family": _normalized_token(
                    _annotation_family(row)
                ),
                "remedy_path": _annotation_remedy(row),
                "scope": _normalized_scope(row.get("scope")),
                "authority_level": _annotation_authority(row),
                "description": _annotation_text(row),
                "construct_refs": _construct_refs(
                    row.get("construct_refs")
                    or row.get("required_evidence_constructs")
                    or row.get("construct_ref")
                ),
                "status": status,
                "source_ref": _text(row.get("source_ref") or row.get("text_ref")),
            }
        )
    return records


def _compare_construct_vocabulary(
    *,
    case_id: str,
    case: Mapping[str, Any],
    compiled_obligations: Sequence[Mapping[str, Any]],
    annotations: Sequence[Mapping[str, Any]],
    obligation_buckets: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
) -> dict[str, Any]:
    compiled = tuple(
        dict.fromkeys(
            construct
            for obligation in compiled_obligations
            for construct in _construct_refs(obligation.get("required_evidence_constructs"))
        )
    )
    annotation_expected = tuple(
        construct
        for annotation in annotations
        for construct in _construct_refs(annotation.get("construct_refs"))
    )
    registry_expected = _construct_registry_refs_for_case(case_id)
    case_expected = _case_level_construct_refs(case)
    expected = tuple(dict.fromkeys((*annotation_expected, *registry_expected, *case_expected)))
    expectation_status = "labeled" if expected else "unlabeled"
    expected_sources = tuple(
        source
        for source, rows in (
            ("obligation_annotations", annotation_expected),
            ("construct_registry_corpus_bindings", registry_expected),
            ("case_annotations", case_expected),
        )
        if rows
    )
    compiled_set = set(compiled)
    expected_set = set(expected)
    authority_drift_constructs = {
        construct
        for row in _sequence(
            (obligation_buckets or {}).get("authority_drift_obligations")
        )
        if isinstance(row, Mapping)
        for construct in _construct_refs(row.get("construct_refs"))
    }
    return {
        "reported": True,
        "construct_expectation_status": expectation_status,
        "expected_construct_sources": sorted(expected_sources),
        "compiled_constructs": sorted(compiled_set),
        "expected_constructs": sorted(expected_set),
        "true_positive_constructs": sorted(compiled_set & expected_set),
        "missed_constructs": sorted(expected_set - compiled_set),
        "hallucinated_constructs": (
            sorted(compiled_set - expected_set) if expectation_status == "labeled" else []
        ),
        "authority_drift_constructs": sorted(authority_drift_constructs),
    }


def _construct_registry_refs_for_case(case_id: str) -> tuple[str, ...]:
    try:
        registry = load_construct_registry()
    except Exception:
        return ()
    return tuple(
        dict.fromkeys(
            construct.construct_id
            for construct in registry.constructs
            for binding in construct.corpus_bindings
            if binding.case_id == case_id
        )
    )


def _case_level_construct_refs(case: Mapping[str, Any]) -> tuple[str, ...]:
    annotations = _mapping(case.get("annotations"))
    claim_evidence = _mapping(case.get("claim_evidence_annotations"))
    return tuple(
        dict.fromkeys(
            [
                *_construct_refs(case.get("construct_refs")),
                *_construct_refs(case.get("expected_constructs")),
                *_construct_refs(annotations.get("construct_refs")),
                *_construct_refs(annotations.get("expected_constructs")),
                *_construct_refs(claim_evidence.get("construct_refs")),
                *_construct_refs(claim_evidence.get("expected_constructs")),
            ]
        )
    )


def _annotation_obligations(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    annotations = _mapping(case.get("annotations"))
    candidates = (
        annotations.get("obligations"),
        annotations.get("expected_obligations"),
        case.get("obligations"),
        _nested(case, ("claim_evidence_decomposition", "obligations")),
        _nested(case, ("claim_evidence_annotations", "obligations")),
    )
    for candidate in candidates:
        rows = tuple(item for item in _sequence(candidate) if isinstance(item, Mapping))
        if rows:
            return rows
    return ()


def _load_cases(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if not path.exists():
        return [], [
            _issue(
                "w11e_corpus_path_missing",
                f"W11.E corpus path does not exist: {path}",
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
    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "w11e_case_json_invalid",
                    str(exc),
                    severity="fail",
                    source_path=str(file_path),
                )
            )
            continue
        for case in _cases_from_payload(payload):
            case["_source_path"] = str(file_path)
            cases.append(case)
    return cases, issues


def _cases_from_payload(payload: Any) -> tuple[dict[str, Any], ...]:
    if isinstance(payload, list):
        return tuple(
            dict(item)
            for item in payload
            if isinstance(item, Mapping) and _looks_like_w11e_case(item)
        )
    if isinstance(payload, Mapping):
        if isinstance(payload.get("cases"), list):
            return tuple(
                dict(item)
                for item in payload["cases"]
                if isinstance(item, Mapping) and _looks_like_w11e_case(item)
            )
        if (payload.get("case_id") or payload.get("id")) and _looks_like_w11e_case(payload):
            return (dict(payload),)
    return ()


def _is_non_case_fixture_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    return "producer_stubs" in parts or path.name.endswith(".producer_stubs.json")


def _looks_like_w11e_case(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("compilation_intent_text")
        or _nested(payload, ("intent", "text"))
        or payload.get("intent_text")
        or payload.get("policy_intent")
    )


def _summary(case_reports: Sequence[Mapping[str, Any]], *, status: str) -> dict[str, Any]:
    scores = [float(case.get("per_case_truthfulness_score") or 0.0) for case in case_reports]
    construct_rows = [
        _mapping(case.get("construct_vocabulary"))
        for case in case_reports
        if isinstance(case.get("construct_vocabulary"), Mapping)
    ]
    return {
        "status": status,
        "case_count": len(case_reports),
        "blocked_case_count": sum(1 for case in case_reports if case.get("status") == "blocked"),
        "aggregate_compilation_truthfulness_rate": _average(scores),
        "construct_vocabulary": {
            "reported": True,
            "case_count": len(construct_rows),
            "compiled_construct_count": len(
                {
                    construct
                    for row in construct_rows
                    for construct in _sequence(row.get("compiled_constructs"))
                }
            ),
            "true_positive_construct_count": len(
                {
                    construct
                    for row in construct_rows
                    for construct in _sequence(row.get("true_positive_constructs"))
                }
            ),
            "missed_construct_count": sum(
                len(_sequence(row.get("missed_constructs"))) for row in construct_rows
            ),
            "hallucinated_construct_count": sum(
                len(_sequence(row.get("hallucinated_constructs")))
                for row in construct_rows
            ),
            "authority_drift_construct_count": sum(
                len(_sequence(row.get("authority_drift_constructs")))
                for row in construct_rows
            ),
        },
        "by_domain": _slice_summary(case_reports, "domain"),
        "by_authority_level": _slice_summary(case_reports, "authority_level"),
    }


def _slice_summary(
    case_reports: Sequence[Mapping[str, Any]],
    field_name: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in case_reports:
        grouped[_normalized_token(case.get(field_name)) or "unknown"].append(case)
    return {
        key: {
            "case_count": len(rows),
            "blocked_case_count": sum(1 for row in rows if row.get("status") == "blocked"),
            "aggregate_compilation_truthfulness_rate": _average(
                [float(row.get("per_case_truthfulness_score") or 0.0) for row in rows]
            ),
        }
        for key, rows in sorted(grouped.items())
    }


def _claim_facets(compiled_case: Any) -> list[dict[str, Any]]:
    return [
        {
            "facet_id": snapshot["facet_id"],
            "facet_type": snapshot["facet_type"],
            "value": snapshot["value"],
            "concept_spine_refs": [snapshot["concept_ref"]],
            "authority_profile_refs": [snapshot["authority_profile"]],
        }
        for snapshot in facet_snapshots_for_obligation_graph(compiled_case)
    ]


def _claim_obligations(graph: ObligationGraph) -> list[dict[str, Any]]:
    facet_refs = [facet.facet_id for facet in graph.facets]
    concept_refs = [facet.concept_ref for facet in graph.facets]
    authority_refs = [facet.authority_profile for facet in graph.facets]
    return [
        {
            "obligation_id": item.frontier_id,
            "family": item.bundle_key.family,
            "description": item.obligation_text,
            "facet_refs": facet_refs,
            "concept_spine_refs": concept_refs,
            "authority_profile_refs": authority_refs,
        }
        for item in graph.blocking_frontier
    ]


def _named_alternatives(case: Mapping[str, Any], *, case_id: str) -> list[dict[str, str]]:
    alternatives = [
        dict(item)
        for item in _sequence(case.get("named_alternatives"))
        if isinstance(item, Mapping)
    ]
    if alternatives:
        return alternatives
    return [
        {
            "alternative_id": f"alternative-{_slug(case_id)}-direct-transfer",
            "label": "Direct transfer alternative",
            "description": "A direct transfer comparator retained for W6.D superiority claims.",
        }
    ]


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
        raise CompilationTruthfulnessInputError(
            "W11.D case fixture must provide concept_spine_refs for W6.A compilation."
        )
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
            or (f"concept://w11e/{_slug(case_id)}",)
        ),
        facet_concept_refs=_mapping(refs.get("facet_concept_refs")),
    )


def _spine_context(case: Mapping[str, Any], *, compiled_case: Any) -> dict[str, Any]:
    pipeline_context = _mapping(_nested(case, ("producer_pipeline", "spine_context")))
    if pipeline_context:
        return dict(pipeline_context)
    concept_refs = [
        snapshot["concept_ref"] for snapshot in facet_snapshots_for_obligation_graph(compiled_case)
    ]
    return {
        "concept_spine_ref": compiled_case.concept_spine_ref,
        "jurisdiction_spine_ref": compiled_case.jurisdiction_spine_ref,
        "canonical_concept_refs": list(dict.fromkeys(concept_refs)),
    }


def _self_test_case_payload() -> dict[str, Any]:
    return {
        "case_id": "w11e-self-test",
        "domain": "housing",
        "authority_level": "production",
        "intent": {
            "intent_id": "w11e-self-test",
            "text": (
                "Provide a means-tested housing voucher subsidy for low-income renters "
                "in Kyiv oblast through municipal service centres, with annual "
                "appropriations and public monitoring in 2026."
            ),
            "problem_domain": "social",
            "authority_type": "local",
        },
        "concept_spine_refs": {
            "concept_spine_ref": "concept-spine://w11e/self-test",
            "jurisdiction_spine_ref": "jurisdiction-spine://w11e/self-test",
            "canonical_concept_refs": ["concept://w11e/housing"],
        },
        "compilation_inputs": {
            "use_seed_rule_catalog": False,
            "complexity_budget": {"max_frontier_items": 5},
            "candidate_sources": [
                {
                    "candidate_id": "candidate-data-freshness",
                    "family": "data",
                    "obligation_text": "Resolve data obligation through source freshness.",
                    "source_class": "producer_blocker",
                    "source_ref": "fixture://candidate-data-freshness",
                    "owner": "team-evaluation",
                    "scope": "kyiv:housing",
                    "authority_profile": "production",
                    "temporal_window": "2026",
                    "remedy_path": "source_freshness",
                    "priority_hint": "mandatory",
                    "authority_allowance_passed": True,
                    "admissibility_passed": True,
                    "current_run_relevance_passed": True,
                    "material_public_risk_passed": True,
                    "marginal_assurance_value": 10.0,
                    "expected_cost": 0.0,
                    "degradation_risk": 0.0,
                    "reviewer_burden_minutes": 0.0,
                    "complexity_cost": 1.0,
                    "lineage_refs": ["fixture://lineage/candidate-data-freshness"],
                    "escalation_owner": "team-evaluation",
                }
            ],
        },
        "producer_pipeline": {"producers": [_self_test_producer()]},
        "annotations": {
            "obligations": [
                {
                    "obligation_id": "ann-data-freshness",
                    "family": "data",
                    "remedy_path": "source_freshness",
                    "scope": "kyiv:housing",
                    "authority_level": "production",
                    "description": "Data freshness must cover the housing voucher claim time.",
                }
            ]
        },
        "expert_adjudication": {
            "case_label": "semantic_pass",
            "reviewer_role": "policy_domain_expert",
            "rubric_revision": "w11.c-self-test",
        },
    }


def _self_test_producer() -> dict[str, Any]:
    return {
        "producer_component": "fabric",
        "consumed_concept_refs": ["concept://w11e/housing"],
        "consumed_requirement_refs": ["req://w11e/data"],
        "expected_output_families": ["fabric.source_contract_binding.v1"],
        "first_pass_bindings": [
            {
                "binding_id": "label.fabric.context",
                "binding_kind": "label",
                "disposition": "context_only",
                "concept_ref": "concept://w11e/housing",
                "label": "fabric context label",
            }
        ],
        "second_pass_bindings": [
            {
                "binding_id": "binding.fabric.source",
                "binding_kind": "dataset",
                "disposition": "selected",
                "concept_ref": "concept://w11e/housing",
                "requirement_ref": "req://w11e/data",
                "artifact_ref": "source://w11e/housing-admin",
                "time_role": "observation_time",
            }
        ],
        "requested_deadline_s": 5.0,
    }


def _scope_drift(annotation: Mapping[str, Any], compiled: Mapping[str, Any]) -> bool:
    expected = _normalized_scope(annotation.get("scope"))
    actual = _normalized_scope(compiled.get("scope"))
    return bool(expected and actual and expected != actual)


def _authority_drift(annotation: Mapping[str, Any], compiled: Mapping[str, Any]) -> bool:
    expected = _annotation_authority(annotation)
    actual = _compiled_authority(compiled)
    return bool(expected and actual and expected != actual)


def _match_row(
    annotation: Mapping[str, Any],
    compiled: Mapping[str, Any],
    *,
    match_basis: str,
) -> dict[str, Any]:
    return {
        "annotation_id": _text(annotation.get("annotation_id")),
        "compiled_obligation_id": _text(compiled.get("compiled_obligation_id")),
        "family": _normalized_token(compiled.get("family") or annotation.get("family")),
        "remedy_path": _normalized_token(
            compiled.get("remedy_path") or annotation.get("remedy_path")
        ),
        "scope": _normalized_scope(compiled.get("scope") or annotation.get("scope")),
        "authority_level": _compiled_authority(compiled) or _annotation_authority(annotation),
        "construct_refs": list(
            dict.fromkeys(
                [
                    *_construct_refs(annotation.get("construct_refs")),
                    *_construct_refs(compiled.get("required_evidence_constructs")),
                ]
            )
        ),
        "match_basis": match_basis,
    }


def _annotation_remedy(row: Mapping[str, Any]) -> str:
    return _normalized_token(
        row.get("remedy_path")
        or row.get("required_evidence_family")
        or row.get("required_evidence")
        or row.get("obligation_type")
    )


def _annotation_family(row: Mapping[str, Any]) -> str:
    explicit = _normalized_token(row.get("family") or row.get("obligation_family"))
    if explicit:
        return explicit
    return _required_evidence_family_to_obligation_family(row.get("required_evidence_family"))


def _required_evidence_family_to_obligation_family(value: object) -> str:
    text = _normalized_token(value)
    if not text:
        return ""
    if any(token in text for token in ("legal", "court", "statute", "competence")):
        return "legal"
    if any(token in text for token in ("budget", "fiscal", "funding", "cost", "tax")):
        return "fiscal"
    if any(
        token in text
        for token in ("data", "registry", "source", "lineage", "snapshot", "administrative")
    ):
        return "data"
    if any(token in text for token in ("method", "evaluation", "causal", "counterfactual")):
        return "method"
    if any(token in text for token in ("participation", "consultation", "stakeholder")):
        return "participation"
    if any(token in text for token in ("equity", "distributional", "exclusion", "access")):
        return "equity"
    if any(token in text for token in ("delivery", "capacity", "implementation", "monitoring")):
        return "implementation"
    return text


def _annotation_authority(row: Mapping[str, Any]) -> str:
    return _normalized_token(
        row.get("authority_level")
        or row.get("authority_profile")
        or row.get("authority_profile_ref")
    )


def _compiled_authority(row: Mapping[str, Any]) -> str:
    return _normalized_token(
        row.get("authority_level")
        or row.get("authority_profile")
        or row.get("authority_profile_ref")
    )


def _annotation_text(row: Mapping[str, Any]) -> str:
    return _text(
        row.get("description")
        or row.get("obligation_text")
        or row.get("text")
        or row.get("reviewer_notes")
    )


def _compiled_text(row: Mapping[str, Any]) -> str:
    return _text(row.get("obligation_text") or row.get("description") or row.get("text"))


def _text_similarity(left: str, right: str) -> float:
    left_tokens = set(_tokens(left))
    right_tokens = set(_tokens(right))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens.intersection(right_tokens)) / len(left_tokens.union(right_tokens))


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(token for token in re.split(r"[^a-z0-9]+", value.casefold()) if len(token) > 2)


def _construct_refs(value: object) -> tuple[str, ...]:
    refs: list[str] = []
    for item in _sequence(value):
        text = _text(item)
        if not text:
            continue
        normalized = text if text.startswith("construct:") else f"construct:{text}"
        if normalized not in refs:
            refs.append(normalized)
    return tuple(refs)


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


def _nested(mapping: Mapping[str, Any], path: Sequence[str]) -> object | None:
    current: object = mapping
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _enum_value(enum_cls: Any, value: object, *, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, enum_cls):
        return value
    text = str(value).strip()
    try:
        return enum_cls(text)
    except ValueError:
        pass
    try:
        return enum_cls[text.upper().replace("-", "_")]
    except KeyError:
        return default


def _authority_type_for_level(authority_level: str) -> str:
    if authority_level in {"federal", "state", "local", "organizational"}:
        return authority_level
    return "local"


def _average(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _required_text(value: object, *, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise CompilationTruthfulnessInputError(f"{field_name} is required")
    return text


def _text(value: object) -> str:
    return str(value or "").strip()


def _normalized_scope(value: object) -> str:
    return _normalized_token(value)


def _normalized_token(value: object) -> str:
    text = _text(value).casefold().replace("::", ":")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_.:/-]+", "_", text)
    return text.strip("_")


def _slug(value: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9_.-]+", "-", _text(value))
    return text.strip("-").casefold() or "unknown"


def _issue(code: str, message: str, *, severity: str = "error", **extra: Any) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": severity,
        **{key: value for key, value in extra.items() if value is not None},
    }


if __name__ == "__main__":
    raise SystemExit(main())
