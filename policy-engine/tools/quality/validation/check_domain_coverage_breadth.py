#!/usr/bin/env python3
"""Measure W11.F domain coverage breadth and authority useful-design rates."""

from __future__ import annotations

# ruff: noqa: ANN401
import argparse
import json
import re
import sys
import tempfile
from collections import Counter, defaultdict
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

SCHEMA_VERSION = "policyos.policy_design_case.domain_coverage_breadth.v1"
TOOL_NAME = "quality.validation.check-domain-coverage-breadth"
GENERATED_AT = "2026-05-24T00:00:00Z"
DEFAULT_CORPUS_PATH = Path("tests/fixtures/universal-corpus")
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/domain_coverage_breadth_report.json")

AUTHORITY_LEVELS = ("research", "governed", "production")
USEFUL_CLOSEOUT_STATES = frozenset(
    {"pass", "publishable", "limited", "publish_with_limitation"}
)
NON_USEFUL_CLOSEOUT_STATES = frozenset(
    {"accepted_deficit", "blocked", "contested", "review_required", "typed_blocker"}
)
USEFUL_ADJUDICATION_LABELS = frozenset({"semantic_pass", "limitation_required"})
PATTERN_REFS = ("P01", "P02", "P03", "P05", "P10", "P13", "P15")


class DomainCoverageInputError(ValueError):
    """Raised when a case cannot produce a W6.C obligation graph."""

    code = "w6c_obligation_graph_unavailable"


def build_domain_coverage_breadth_report(
    *,
    repo_root: str | Path = REPO_ROOT,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    min_candidates_per_family_layer: int = 1,
    min_family_layers: int = 2,
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Build the W11.F domain breadth and authority useful-design report.

    Args:
        repo_root: Product repository root recorded in the report.
        corpus_path: JSON case file or directory of W11.D fixtures.
        min_candidates_per_family_layer: Minimum frontier candidates required
            for a family layer to count as non-trivial.
        min_family_layers: Minimum qualifying family layers required for a
            case graph to count as non-trivial.
        generated_at: Deterministic report timestamp.

    Returns:
        A JSON-serializable W11.F report with domain breadth, case-level graph
        summaries, and useful-design rates stratified by authority level.
    """

    if min_candidates_per_family_layer < 1:
        raise ValueError("min_candidates_per_family_layer must be >= 1")
    if min_family_layers < 1:
        raise ValueError("min_family_layers must be >= 1")

    root = Path(repo_root).resolve()
    corpus = _resolve_path(root, Path(corpus_path))
    cases, load_issues = _load_cases(corpus)
    case_reports = [
        _evaluate_case(
            case,
            source_path=case.get("_source_path"),
            min_candidates_per_family_layer=min_candidates_per_family_layer,
            min_family_layers=min_family_layers,
        )
        for case in cases
    ]
    issues = [*load_issues, *(issue for case in case_reports for issue in case["issues"])]
    if not cases:
        issues.append(
            _issue(
                "w11f_corpus_empty",
                "Domain coverage breadth requires at least one committed corpus case.",
                severity="fail",
            )
        )
    summary = _summary(
        case_reports,
        issues=issues,
        min_candidates_per_family_layer=min_candidates_per_family_layer,
        min_family_layers=min_family_layers,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "repo_root": str(root),
        "corpus_path": str(corpus),
        "thresholds": {
            "min_candidates_per_family_layer": min_candidates_per_family_layer,
            "min_family_layers": min_family_layers,
        },
        "summary": summary,
        "domains": _domain_summary(case_reports),
        "cases": case_reports,
        "issues": issues,
        "capability_trace": {
            "capability_id": "w11f_domain_coverage_breadth",
            "capability_reality_label": (
                "implemented" if summary["status"] != "fail" else "verification_missing"
            ),
            "typed_contract_ref": "repo://tools/quality/validation/check_domain_coverage_breadth.py",
            "producer_ref": "repo://src/polisyos/obligation_graph",
            "artifact_ref": "repo://tests/fixtures/universal-corpus",
            "bridge_ref": "repo://tools/quality/validation/check_domain_coverage_breadth.py",
            "consumer_ref": "repo://tools/quality/validation/check_domain_coverage_breadth.py",
            "verification_ref": (
                "repo://tests/repo_quality/tools/test_domain_coverage_breadth.py"
            ),
            "surface_ref": "repo://tools/quality/validation/README.md#w11f-domain-coverage-breadth",
            "semantic_test_ref": (
                "repo://tests/repo_quality/tools/test_domain_coverage_breadth.py"
                "#test_domain_coverage_breadth_does_not_launder_expected_fixture_slice_as_w6c_graph"
            ),
            "missing_capability_labels": (
                [] if summary["status"] != "fail" else ["verification_missing"]
            ),
        },
        "pattern_pass": {
            "relevant_patterns": list(PATTERN_REFS),
            "target_correct_pattern": (
                "W11.F counts committed domains only when a W6.C frontier graph is "
                "actually produced and non-trivial; expected fixture slices remain "
                "annotations, not producer authority."
            ),
            "existing_anti_patterns_found": _anti_patterns(case_reports),
            "acceptance_signal": (
                "report exposes domain breadth, per-case graph provenance/status, "
                "and per-authority useful-design rates with blockers excluded"
            ),
        },
    }


def validate_domain_coverage_breadth_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the machine-readable shape of a W11.F domain breadth report."""

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            _issue(
                "domain_coverage_schema_version_invalid",
                "Report schema_version does not match the W11.F contract.",
                severity="fail",
                expected=SCHEMA_VERSION,
                actual=payload.get("schema_version"),
            )
        )
    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        issues.append(
            _issue(
                "domain_coverage_summary_missing",
                "Report must contain a summary mapping.",
                severity="fail",
            )
        )
        summary = {}
    if not isinstance(summary.get("domain_coverage_breadth"), int):
        issues.append(
            _issue(
                "domain_coverage_breadth_missing",
                "Summary must include integer domain_coverage_breadth.",
                severity="fail",
            )
        )
    authority_rates = summary.get("per_authority_expert_useful_design_ceiling")
    if not isinstance(authority_rates, Mapping):
        issues.append(
            _issue(
                "per_authority_expert_useful_design_ceiling_missing",
                "Summary must stratify expert useful-design ceiling by authority level.",
                severity="fail",
            )
        )
    else:
        for authority_level in AUTHORITY_LEVELS:
            row = authority_rates.get(authority_level)
            if not isinstance(row, Mapping) or "expert_useful_design_ceiling" not in row:
                issues.append(
                    _issue(
                        "per_authority_expert_useful_design_ceiling_incomplete",
                        "Authority ceiling rows must include expert_useful_design_ceiling.",
                        severity="fail",
                        authority_level=authority_level,
                    )
                )
    cases = payload.get("cases")
    if not isinstance(cases, list):
        issues.append(
            _issue(
                "domain_coverage_cases_missing",
                "Report must contain a cases array.",
                severity="fail",
            )
        )
    else:
        for index, case in enumerate(cases):
            if not isinstance(case, Mapping):
                issues.append(
                    _issue(
                        "domain_coverage_case_invalid",
                        "Each case report must be a mapping.",
                        severity="fail",
                        case_index=index,
                    )
                )
                continue
            for field_name in ("case_id", "domain", "graph_status", "family_layer_count"):
                if field_name not in case:
                    issues.append(
                        _issue(
                            "domain_coverage_case_field_missing",
                            "Case report is missing a required W11.F field.",
                            severity="fail",
                            case_id=case.get("case_id"),
                            field=field_name,
                        )
                    )
    return {"status": "fail" if issues else "pass", "issues": issues}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for W11.F domain coverage breadth measurement."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Policy engine repo root.")
    parser.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS_PATH),
        help="W11.D case file or directory. Ignored when --self-test is used.",
    )
    parser.add_argument("--output", default=None, help="Write report JSON to this path.")
    parser.add_argument(
        "--min-candidates-per-family-layer",
        type=int,
        default=1,
        help="Minimum W6.C frontier items required in a family layer.",
    )
    parser.add_argument(
        "--min-family-layers",
        type=int,
        default=2,
        help="Minimum qualifying family layers for a non-trivial graph.",
    )
    parser.add_argument(
        "--fail-under-breadth",
        type=int,
        default=None,
        help="Return non-zero when domain_coverage_breadth is below this floor.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run a built-in W11.F smoke corpus instead of reading --corpus.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        with tempfile.TemporaryDirectory(prefix="policyos-w11f-domain-self-test-") as tmp:
            corpus_dir = Path(tmp) / "corpus"
            corpus_dir.mkdir(parents=True)
            atomic_write_json(corpus_dir / "health.json", _self_test_case_payload())
            report = build_domain_coverage_breadth_report(
                repo_root=args.repo_root,
                corpus_path=corpus_dir,
                min_candidates_per_family_layer=args.min_candidates_per_family_layer,
                min_family_layers=args.min_family_layers,
            )
    else:
        report = build_domain_coverage_breadth_report(
            repo_root=args.repo_root,
            corpus_path=args.corpus,
            min_candidates_per_family_layer=args.min_candidates_per_family_layer,
            min_family_layers=args.min_family_layers,
        )

    validation = validate_domain_coverage_breadth_report(report)
    if validation["issues"]:
        report["issues"] = [*report.get("issues", []), *validation["issues"]]
        report["summary"]["status"] = "fail"

    output = Path(args.output) if args.output else None
    if output is not None:
        atomic_write_json(output, report)
    else:
        json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")

    if validation["status"] == "fail" or report["summary"]["status"] == "fail":
        return 1
    if (
        args.fail_under_breadth is not None
        and report["summary"]["domain_coverage_breadth"] < args.fail_under_breadth
    ):
        return 1
    return 0


def test_self_test_cli_contract(tmp_path: Path) -> None:
    """Pytest-compatible self-test for the documented W11.F breadth command."""

    output = tmp_path / "domain-coverage-self-test.json"
    exit_code = main(["--self-test", "--output", str(output)])
    if exit_code != 0:
        raise AssertionError(f"W11.F domain self-test exited with {exit_code}")
    payload = json.loads(output.read_text(encoding="utf-8"))
    validation = validate_domain_coverage_breadth_report(payload)
    if validation["status"] != "pass":
        raise AssertionError(validation["issues"])


def _evaluate_case(
    case: Mapping[str, Any],
    *,
    source_path: object | None,
    min_candidates_per_family_layer: int,
    min_family_layers: int,
) -> dict[str, Any]:
    case_id = _required_text(case.get("case_id") or case.get("id"), field_name="case_id")
    domain = _normalized_token(case.get("domain") or _nested(case, ("intent", "problem_domain")))
    issues: list[dict[str, Any]] = []
    graph_ref = None
    graph_status = "blocked"
    records: list[dict[str, Any]] = []
    try:
        graph = _compile_w6c_graph(case, case_id=case_id)
        graph_ref = graph.graph_id
        graph_status = "pass"
        records = _compiled_obligation_records(graph)
    except Exception as exc:
        code = getattr(exc, "code", "w6c_obligation_graph_unavailable")
        issues.append(
            _issue(
                str(code),
                str(exc),
                severity="warn",
                case_id=case_id,
            )
        )

    family_counts = dict(sorted(Counter(row["family"] for row in records).items()))
    qualifying_layers = [
        family
        for family, count in family_counts.items()
        if count >= min_candidates_per_family_layer
    ]
    non_trivial_graph = len(qualifying_layers) >= min_family_layers
    return {
        "case_id": case_id,
        "source_path": str(source_path) if source_path else None,
        "domain": domain or "unknown",
        "graph_status": graph_status,
        "obligation_graph_ref": graph_ref,
        "family_layer_counts": family_counts,
        "qualifying_family_layers": qualifying_layers,
        "family_layer_count": len(qualifying_layers),
        "frontier_candidate_count": len(records),
        "non_trivial_graph": non_trivial_graph,
        "authority_useful_design": _authority_useful_design_rows(case, case_id=case_id),
        "issues": issues,
    }


def _compile_w6c_graph(case: Mapping[str, Any], *, case_id: str) -> ObligationGraph:
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
        raise DomainCoverageInputError(
            "W6.A grammar compilation blocked before W6.C: " + ", ".join(blocker_codes)
        )

    compilation_inputs = _mapping(case.get("compilation_inputs"))
    governed_rules: Sequence[Any]
    if "governed_rules" in compilation_inputs:
        governed_rules = _sequence(compilation_inputs.get("governed_rules"))
    elif compilation_inputs.get("use_seed_rule_catalog") is False:
        governed_rules = ()
    else:
        governed_rules = build_seed_obligation_rule_catalog().rules

    return compile_obligation_graph(
        run_id=_text(case.get("run_id")) or f"run-{case_id}",
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
    )


def _compiled_obligation_records(graph: ObligationGraph) -> list[dict[str, Any]]:
    records = [
        {
            "compiled_obligation_id": item.frontier_id,
            "family": _normalized_token(item.bundle_key.family),
            "remedy_path": item.bundle_key.remedy_path,
            "scope": item.bundle_key.scope,
            "authority_level": item.bundle_key.authority_profile,
            "candidate_refs": list(item.candidate_refs),
        }
        for item in graph.blocking_frontier
    ]
    records.sort(
        key=lambda row: (
            str(row["family"]),
            str(row["remedy_path"]),
            str(row["compiled_obligation_id"]),
        )
    )
    return records


def _authority_useful_design_rows(
    case: Mapping[str, Any],
    *,
    case_id: str,
) -> list[dict[str, Any]]:
    adjudication_labels = _adjudication_labels(case)
    adjudication_useful = bool(adjudication_labels) and set(adjudication_labels).issubset(
        USEFUL_ADJUDICATION_LABELS
    )
    rows = _closeout_state_rows(case)
    if not rows:
        outcome = _normalized_token(
            case.get("outcome") or case.get("closeout_state") or case.get("status")
        )
        authority_level = _normalized_token(case.get("authority_level") or "research")
        rows = ({"authority_level": authority_level, "state": outcome},)

    authority_rows: list[dict[str, Any]] = []
    for row in rows:
        authority_level = _normalized_token(row.get("authority_level") or "research")
        state = _normalized_token(row.get("state") or row.get("outcome") or row.get("status"))
        structurally_useful = state in USEFUL_CLOSEOUT_STATES
        non_useful = state in NON_USEFUL_CLOSEOUT_STATES
        useful = structurally_useful and adjudication_useful
        blocker_code = None
        if structurally_useful and not adjudication_useful:
            blocker_code = "expert_adjudication_missing_or_not_useful_design"
        elif non_useful:
            blocker_code = "closeout_state_not_useful_design"
        authority_rows.append(
            {
                "case_id": case_id,
                "authority_level": authority_level or "research",
                "closeout_state": state or "unknown",
                "structurally_useful": structurally_useful,
                "adjudication_labels": adjudication_labels,
                "counts_toward_useful_design": useful,
                "blocker_code": blocker_code,
            }
        )
    return authority_rows


def _closeout_state_rows(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
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


def _adjudication_labels(case: Mapping[str, Any]) -> tuple[str, ...]:
    adjudication = _mapping(case.get("expert_adjudication") or case.get("adjudication"))
    labels: list[str] = []
    if adjudication.get("case_label"):
        labels.append(_normalized_token(adjudication.get("case_label")))
    for row in _sequence(adjudication.get("claim_labels")):
        if isinstance(row, Mapping) and row.get("label"):
            labels.append(_normalized_token(row.get("label")))
    return tuple(dict.fromkeys(label for label in labels if label))


def _summary(
    case_reports: Sequence[Mapping[str, Any]],
    *,
    issues: Sequence[Mapping[str, Any]],
    min_candidates_per_family_layer: int,
    min_family_layers: int,
) -> dict[str, Any]:
    domains = _domain_summary(case_reports)
    non_trivial_domains = [
        domain for domain, row in domains.items() if row["non_trivial_graph"]
    ]
    return {
        "status": "fail" if any(issue.get("severity") == "fail" for issue in issues) else "pass",
        "case_count": len(case_reports),
        "committed_domain_count": len(domains),
        "domain_coverage_breadth": len(non_trivial_domains),
        "non_trivial_domain_ids": non_trivial_domains,
        "min_candidates_per_family_layer": min_candidates_per_family_layer,
        "min_family_layers": min_family_layers,
        # W11.F reports the expert ceiling — the rate of corpus cases whose
        # expert adjudication says the system SHOULD be able to deliver useful
        # design. It is not the runtime achievement; that comes from W12.D
        # under the name ``runtime_useful_design_rate``. The plan distinguishes
        # the two so rollout decisions do not conflate ceiling and actual.
        "per_authority_expert_useful_design_ceiling": _per_authority_rates(case_reports),
    }


def _domain_summary(case_reports: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for case in case_reports:
        grouped[str(case.get("domain") or "unknown")].append(case)
    return {
        domain: {
            "case_count": len(rows),
            "non_trivial_graph": any(bool(row.get("non_trivial_graph")) for row in rows),
            "non_trivial_case_ids": [
                str(row["case_id"]) for row in rows if row.get("non_trivial_graph")
            ],
            "graph_blocked_case_count": sum(
                1 for row in rows if row.get("graph_status") == "blocked"
            ),
            "max_family_layer_count": max(
                (int(row.get("family_layer_count") or 0) for row in rows),
                default=0,
            ),
        }
        for domain, rows in sorted(grouped.items())
    }


def _per_authority_rates(
    case_reports: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    rows_by_authority: dict[str, list[Mapping[str, Any]]] = {
        authority_level: [] for authority_level in AUTHORITY_LEVELS
    }
    for case in case_reports:
        for row in _sequence(case.get("authority_useful_design")):
            if not isinstance(row, Mapping):
                continue
            authority_level = _normalized_token(row.get("authority_level") or "research")
            rows_by_authority.setdefault(authority_level, []).append(row)

    return {
        authority_level: _authority_rate_row(rows)
        for authority_level, rows in sorted(rows_by_authority.items())
    }


def _authority_rate_row(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    case_count = len(rows)
    useful_count = sum(1 for row in rows if row.get("counts_toward_useful_design"))
    return {
        "case_count": case_count,
        "expert_useful_design_ceiling_count": useful_count,
        "blocked_or_non_useful_count": case_count - useful_count,
        # ``expert_useful_design_ceiling`` is the share of cases whose closeout
        # state AND expert adjudication say useful design is achievable. It is
        # the upper bound the universal compiler must aim for; the runtime
        # rate from W12.D is reported separately as
        # ``runtime_useful_design_rate`` so rollout decisions do not collapse
        # ceiling and actual.
        "expert_useful_design_ceiling": _rate(useful_count, case_count),
        "typed_blockers_count_as_useful_design": False,
        "accepted_deficits_count_as_useful_design": False,
    }


def _load_cases(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if not path.exists():
        return [], [
            _issue(
                "w11f_corpus_path_missing",
                f"W11.F corpus path does not exist: {path}",
                severity="fail",
            )
        ]
    files = _case_json_files(path)
    cases: list[dict[str, Any]] = []
    for file_path in files:
        try:
            payload = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            issues.append(
                _issue(
                    "w11f_case_json_invalid",
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
    if _is_corpus_stub_payload(payload):
        return ()
    if isinstance(payload, list):
        return tuple(
            dict(item)
            for item in payload
            if isinstance(item, Mapping) and not _is_corpus_stub_payload(item)
        )
    if isinstance(payload, Mapping):
        if isinstance(payload.get("cases"), list):
            return tuple(
                dict(item)
                for item in payload["cases"]
                if isinstance(item, Mapping) and not _is_corpus_stub_payload(item)
            )
        if payload.get("case_id") or payload.get("id"):
            return (dict(payload),)
    return ()


def _case_json_files(path: Path) -> tuple[Path, ...]:
    if path.is_file():
        return (path,)
    cases_dir = path / "cases"
    if cases_dir.is_dir():
        return tuple(sorted(cases_dir.glob("*.json")))
    return tuple(
        file_path
        for file_path in sorted(path.rglob("*.json"))
        if not _is_non_case_fixture_path(file_path)
    )


def _is_non_case_fixture_path(path: Path) -> bool:
    parts = {part.casefold() for part in path.parts}
    return "producer_stubs" in parts or path.name.endswith(".producer_stubs.json")


def _is_corpus_stub_payload(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    schema = str(payload.get("schema_version") or payload.get("schema") or "")
    return (
        schema == "policyos.runtime.producer_pipeline.corpus_stub.v1"
        or str(payload.get("mode") or "") == "corpus_stub"
    )


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
        raise DomainCoverageInputError(
            "W11.F requires actual W6.C compilation inputs; "
            "expected_obligation_graph fixture slices cannot count as produced graphs."
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
            or (f"concept://w11f/{_slug(case_id)}",)
        ),
        facet_concept_refs=_mapping(refs.get("facet_concept_refs")),
    )


def _self_test_case_payload() -> dict[str, Any]:
    return {
        "case_id": "w11f-domain-self-test",
        "domain": "public_health_intervention",
        "authority_level": "production",
        "intent": {
            "intent_id": "w11f-domain-self-test",
            "text": (
                "Provide a means-tested housing voucher subsidy for low-income renters "
                "in Kyiv oblast through municipal service centres, with annual "
                "appropriations and public monitoring in 2026."
            ),
            "problem_domain": "social",
            "authority_type": "local",
        },
        "concept_spine_refs": {
            "concept_spine_ref": "concept-spine://w11f/domain-self-test",
            "jurisdiction_spine_ref": "jurisdiction-spine://w11f/domain-self-test",
            "canonical_concept_refs": ["concept://w11f/public-health"],
        },
        "compilation_inputs": {
            "use_seed_rule_catalog": False,
            "complexity_budget": {"max_frontier_items": 10},
            "candidate_sources": [
                _self_test_candidate("data"),
                _self_test_candidate("legal"),
                _self_test_candidate("method"),
            ],
        },
        "expected_closeout_states": {
            "states": [
                {"authority_level": "research", "state": "publishable"},
                {"authority_level": "governed", "state": "limited"},
                {"authority_level": "production", "state": "limited"},
            ]
        },
        "expert_adjudication": {
            "case_label": "semantic_pass",
            "claim_labels": [{"claim_id": "claim:self-test", "label": "semantic_pass"}],
        },
    }


def _self_test_candidate(family: str) -> dict[str, Any]:
    return {
        "candidate_id": f"candidate-self-test-{family}",
        "family": family,
        "obligation_text": f"Resolve {family} obligation for self-test.",
        "source_class": "producer_blocker",
        "source_ref": f"fixture://w11f/domain-self-test/{family}",
        "owner": "team-evaluation",
        "scope": "self-test:public-health",
        "authority_profile": "production",
        "temporal_window": "2026",
        "remedy_path": f"{family}_review",
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
        "lineage_refs": [f"fixture://lineage/w11f/{family}"],
        "escalation_owner": "team-evaluation",
    }


def _anti_patterns(case_reports: Sequence[Mapping[str, Any]]) -> list[str]:
    found: list[str] = []
    if any(row.get("graph_status") == "blocked" for row in case_reports):
        found.append(
            "producer_missing: one or more committed cases lack actual W6.C graph inputs"
        )
    if any(
        issue.get("code") == "w6c_obligation_graph_unavailable"
        for case in case_reports
        for issue in _sequence(case.get("issues"))
        if isinstance(issue, Mapping)
    ):
        found.append(
            "P10: expected fixture slices are present but cannot be counted as produced graphs"
        )
    return found


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


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


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _required_text(value: object, *, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise DomainCoverageInputError(f"{field_name} is required")
    return text


def _text(value: object) -> str:
    return str(value or "").strip()


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
