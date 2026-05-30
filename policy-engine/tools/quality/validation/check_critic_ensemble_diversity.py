#!/usr/bin/env python3
"""Measure W11.F critic ensemble diversity over flagged failure modes."""

from __future__ import annotations

# ruff: noqa: ANN401
import argparse
import itertools
import json
import re
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.critic_ensemble_diversity.v1"
TOOL_NAME = "quality.validation.check-critic-ensemble-diversity"
GENERATED_AT = "2026-05-24T00:00:00Z"
DEFAULT_INPUT_PATH = Path("tests/fixtures/universal-corpus")
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/critic_ensemble_diversity_report.json")
DEFAULT_DIVERSITY_FLOOR = 0.25

REQUIRED_CRITIC_ROLES = (
    "legal",
    "fiscal",
    "equity",
    "data",
    "implementation",
    "affected_person",
    "adversarial",
    "monitoring",
)
PATTERN_REFS = ("P05", "P10", "P13", "P15")


def build_critic_ensemble_diversity_report(
    *,
    repo_root: str | Path = REPO_ROOT,
    input_path: str | Path = DEFAULT_INPUT_PATH,
    diversity_floor: float = DEFAULT_DIVERSITY_FLOOR,
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Build the W11.F critic ensemble diversity report.

    Args:
        repo_root: Product repository root recorded in the report.
        input_path: JSON report file or directory. The loader accepts per-case
            W6.E-style `critic_ensemble.verdicts`, top-level `verdicts`, or
            report-level `cases`.
        diversity_floor: Minimum acceptable `1 - mean(pairwise Jaccard
            similarity)` score. Lower values warn that critics are collapsing
            into a single persona.
        generated_at: Deterministic report timestamp.

    Returns:
        A JSON-serializable report with per-case failure-mode sets by critic,
        Jaccard similarity/diversity, and monoculture warnings.
    """

    if not 0.0 <= diversity_floor <= 1.0:
        raise ValueError("diversity_floor must be between 0.0 and 1.0")
    root = Path(repo_root).resolve()
    source = _resolve_path(root, Path(input_path))
    cases, load_issues = _load_cases(source)
    return build_critic_ensemble_diversity_report_from_cases(
        cases=cases,
        repo_root=root,
        input_path=source,
        load_issues=load_issues,
        diversity_floor=diversity_floor,
        generated_at=generated_at,
    )


def build_critic_ensemble_diversity_report_from_cases(
    *,
    cases: Sequence[Mapping[str, Any]],
    repo_root: str | Path = REPO_ROOT,
    input_path: str | Path = DEFAULT_INPUT_PATH,
    load_issues: Sequence[Mapping[str, Any]] = (),
    diversity_floor: float = DEFAULT_DIVERSITY_FLOOR,
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Build a W11.F critic diversity report from already-loaded case payloads."""

    if not 0.0 <= diversity_floor <= 1.0:
        raise ValueError("diversity_floor must be between 0.0 and 1.0")
    root = Path(repo_root).resolve()
    source = _resolve_path(root, Path(input_path))
    case_payloads = [dict(case) for case in cases]
    case_reports = [
        _evaluate_case(case, source_path=case.get("_source_path"), diversity_floor=diversity_floor)
        for case in case_payloads
    ]
    issues = [*load_issues, *(issue for case in case_reports for issue in case["issues"])]
    warnings = [warning for case in case_reports for warning in case["warnings"]]
    if not case_payloads:
        issues.append(
            _issue(
                "w11f_critic_input_empty",
                "Critic ensemble diversity requires at least one case/report with verdicts.",
                severity="fail",
            )
        )
    summary = _summary(
        case_reports,
        issues=issues,
        diversity_floor=diversity_floor,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "repo_root": str(root),
        "input_path": str(source),
        "thresholds": {"diversity_floor": diversity_floor},
        "summary": summary,
        "cases": case_reports,
        "warnings": warnings,
        "issues": issues,
        "capability_trace": {
            "capability_id": "w11f_critic_ensemble_diversity",
            "capability_reality_label": (
                "implemented" if summary["status"] != "fail" else "verification_missing"
            ),
            "typed_contract_ref": "repo://src/polisyos/scientist/policy_design/critic_ensemble.py",
            "producer_ref": "repo://src/polisyos/scientist/policy_design/critic_ensemble.py#MultiCriticEnsemble",
            "artifact_ref": "repo://architecture/policy_design_case/wave6e_llm_formulator_critic_ensemble_manifest.json",
            "bridge_ref": "repo://tools/quality/validation/check_critic_ensemble_diversity.py",
            "consumer_ref": "repo://tools/quality/validation/check_critic_ensemble_diversity.py",
            "verification_ref": (
                "repo://tests/repo_quality/tools/test_critic_ensemble_diversity.py"
            ),
            "surface_ref": "repo://tools/quality/validation/README.md#w11f-critic-ensemble-diversity",
            "semantic_test_ref": (
                "repo://tests/repo_quality/tools/test_critic_ensemble_diversity.py"
                "#test_critic_ensemble_diversity_reports_jaccard_floor_and_monoculture_warning"
            ),
            "missing_capability_labels": (
                [] if summary["status"] != "fail" else ["verification_missing"]
            ),
        },
        "pattern_pass": {
            "relevant_patterns": list(PATTERN_REFS),
            "target_correct_pattern": (
                "Critic reports preserve candidate-only authority and expose whether "
                "substantively different critics flagged distinct failure modes rather "
                "than the same persona-shaped output."
            ),
            "existing_anti_patterns_found": _anti_patterns(case_reports),
            "acceptance_signal": (
                "per-case Jaccard diversity, role coverage, unique failure modes, "
                "and critic_monoculture warnings are machine-readable"
            ),
        },
    }


def validate_critic_ensemble_diversity_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the machine-readable shape of a W11.F critic diversity report."""

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            _issue(
                "critic_diversity_schema_version_invalid",
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
                "critic_diversity_summary_missing",
                "Report must contain a summary mapping.",
                severity="fail",
            )
        )
        summary = {}
    if "aggregate_critic_ensemble_diversity_jaccard" not in summary:
        issues.append(
            _issue(
                "critic_diversity_aggregate_missing",
                "Summary must include aggregate_critic_ensemble_diversity_jaccard.",
                severity="fail",
            )
        )
    cases = payload.get("cases")
    if not isinstance(cases, list):
        issues.append(
            _issue(
                "critic_diversity_cases_missing",
                "Report must contain a cases array.",
                severity="fail",
            )
        )
    else:
        for index, case in enumerate(cases):
            if not isinstance(case, Mapping):
                issues.append(
                    _issue(
                        "critic_diversity_case_invalid",
                        "Each case report must be a mapping.",
                        severity="fail",
                        case_index=index,
                    )
                )
                continue
            for field_name in (
                "case_id",
                "failure_modes_by_critic",
                "pairwise_jaccard_similarity",
                "critic_ensemble_diversity_jaccard",
            ):
                if field_name not in case:
                    issues.append(
                        _issue(
                            "critic_diversity_case_field_missing",
                            "Case report is missing a required W11.F field.",
                            severity="fail",
                            case_id=case.get("case_id"),
                            field=field_name,
                        )
                    )
    return {"status": "fail" if issues else "pass", "issues": issues}


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for W11.F critic ensemble diversity measurement."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(REPO_ROOT), help="Policy engine repo root.")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Critic report JSON file or directory. Ignored when --self-test is used.",
    )
    parser.add_argument("--output", default=None, help="Write report JSON to this path.")
    parser.add_argument(
        "--diversity-floor",
        type=float,
        default=DEFAULT_DIVERSITY_FLOOR,
        help="Warn when case diversity Jaccard falls below this floor.",
    )
    parser.add_argument(
        "--fail-under-diversity",
        type=float,
        default=None,
        help="Return non-zero when aggregate diversity is below this floor.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run built-in W11.F critic-report fixtures instead of reading --input.",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        with tempfile.TemporaryDirectory(prefix="policyos-w11f-critic-self-test-") as tmp:
            input_dir = Path(tmp) / "critic-reports"
            input_dir.mkdir(parents=True)
            atomic_write_json(input_dir / "collapsed.json", _self_test_case_payload(collapsed=True))
            atomic_write_json(input_dir / "diverse.json", _self_test_case_payload(collapsed=False))
            report = build_critic_ensemble_diversity_report(
                repo_root=args.repo_root,
                input_path=input_dir,
                diversity_floor=args.diversity_floor,
            )
    else:
        report = build_critic_ensemble_diversity_report(
            repo_root=args.repo_root,
            input_path=args.input,
            diversity_floor=args.diversity_floor,
        )

    validation = validate_critic_ensemble_diversity_report(report)
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
        args.fail_under_diversity is not None
        and report["summary"]["aggregate_critic_ensemble_diversity_jaccard"]
        < args.fail_under_diversity
    ):
        return 1
    return 0


def test_self_test_cli_contract(tmp_path: Path) -> None:
    """Pytest-compatible self-test for the documented W11.F critic command."""

    output = tmp_path / "critic-diversity-self-test.json"
    exit_code = main(["--self-test", "--output", str(output)])
    if exit_code != 0:
        raise AssertionError(f"W11.F critic self-test exited with {exit_code}")
    payload = json.loads(output.read_text(encoding="utf-8"))
    validation = validate_critic_ensemble_diversity_report(payload)
    if validation["status"] != "pass":
        raise AssertionError(validation["issues"])


def _evaluate_case(
    case: Mapping[str, Any],
    *,
    source_path: object | None,
    diversity_floor: float,
) -> dict[str, Any]:
    case_id = _case_id(case)
    verdicts = _verdicts_from_case(case)
    issues: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    failure_modes_by_critic = _failure_modes_by_critic(verdicts)
    if not verdicts:
        issues.append(
            _issue(
                "critic_verdicts_missing",
                "Case has no critic verdicts to measure.",
                severity="warn",
                case_id=case_id,
            )
        )
    missing_roles = [
        role for role in REQUIRED_CRITIC_ROLES if role not in failure_modes_by_critic
    ]
    if missing_roles:
        warnings.append(
            _warning(
                "critic_roles_missing",
                "Critic report does not include all eight W6.E roles.",
                case_id=case_id,
                missing_roles=missing_roles,
            )
        )

    similarity = _mean_pairwise_jaccard_similarity(failure_modes_by_critic)
    diversity = round(1.0 - similarity, 4)
    if _is_monoculture(failure_modes_by_critic):
        warnings.append(
            _warning(
                "critic_monoculture",
                "All eight critics flagged the same failure-mode set.",
                case_id=case_id,
            )
        )
    if diversity < diversity_floor:
        warnings.append(
            _warning(
                "critic_diversity_below_floor",
                "Critic ensemble diversity Jaccard is below the W11.F floor.",
                case_id=case_id,
                diversity_jaccard=diversity,
                diversity_floor=diversity_floor,
            )
        )
    if not _unique_failure_modes(failure_modes_by_critic):
        warnings.append(
            _warning(
                "critic_failure_modes_absent",
                "Critic verdicts did not flag any failure modes.",
                case_id=case_id,
            )
        )

    return {
        "case_id": case_id,
        "source_path": str(source_path) if source_path else None,
        "domain": _normalized_token(case.get("domain") or "unknown"),
        "authority_level": _normalized_token(case.get("authority_level") or "unknown"),
        "critic_count": len(failure_modes_by_critic),
        "required_critic_roles": list(REQUIRED_CRITIC_ROLES),
        "missing_critic_roles": missing_roles,
        "failure_modes_by_critic": {
            role: sorted(modes) for role, modes in sorted(failure_modes_by_critic.items())
        },
        "unique_failure_modes": sorted(_unique_failure_modes(failure_modes_by_critic)),
        "unique_failure_mode_count": len(_unique_failure_modes(failure_modes_by_critic)),
        "pairwise_jaccard_similarity": similarity,
        "critic_ensemble_diversity_jaccard": diversity,
        "below_diversity_floor": diversity < diversity_floor,
        "warnings": warnings,
        "issues": issues,
    }


def _failure_modes_by_critic(
    verdicts: Sequence[Mapping[str, Any]],
) -> dict[str, set[str]]:
    by_critic: dict[str, set[str]] = {}
    for verdict in verdicts:
        envelope = _mapping(verdict.get("envelope"))
        role = _normalized_token(
            envelope.get("critic_role")
            or envelope.get("role")
            or verdict.get("critic_role")
            or verdict.get("role")
        )
        if not role:
            continue
        modes = {
            _normalized_token(mode)
            for mode in _sequence(
                verdict.get("failure_modes")
                or _nested(verdict, ("metadata", "failure_modes"))
            )
            if _normalized_token(mode)
        }
        by_critic.setdefault(role, set()).update(modes)
    return by_critic


def _mean_pairwise_jaccard_similarity(failure_modes_by_critic: Mapping[str, set[str]]) -> float:
    mode_sets = list(failure_modes_by_critic.values())
    if len(mode_sets) < 2:
        return 1.0
    scores = [
        _jaccard_similarity(left, right)
        for left, right in itertools.combinations(mode_sets, 2)
    ]
    return round(sum(scores) / len(scores), 4)


def _jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 1.0
    return len(left & right) / len(union)


def _is_monoculture(failure_modes_by_critic: Mapping[str, set[str]]) -> bool:
    if set(failure_modes_by_critic) != set(REQUIRED_CRITIC_ROLES):
        return False
    mode_sets = [frozenset(failure_modes_by_critic[role]) for role in REQUIRED_CRITIC_ROLES]
    return bool(mode_sets) and len(set(mode_sets)) == 1


def _unique_failure_modes(failure_modes_by_critic: Mapping[str, set[str]]) -> set[str]:
    unique: set[str] = set()
    for modes in failure_modes_by_critic.values():
        unique.update(modes)
    return unique


def _summary(
    case_reports: Sequence[Mapping[str, Any]],
    *,
    issues: Sequence[Mapping[str, Any]],
    diversity_floor: float,
) -> dict[str, Any]:
    diversities = [
        float(case.get("critic_ensemble_diversity_jaccard") or 0.0)
        for case in case_reports
    ]
    return {
        "status": "fail" if any(issue.get("severity") == "fail" for issue in issues) else "pass",
        "case_count": len(case_reports),
        "diversity_floor": diversity_floor,
        "aggregate_critic_ensemble_diversity_jaccard": _average(diversities),
        "cases_below_diversity_floor": sum(
            1 for case in case_reports if case.get("below_diversity_floor")
        ),
        "cases_with_monoculture_warning": sum(
            1
            for case in case_reports
            if any(
                warning.get("code") == "critic_monoculture"
                for warning in _sequence(case.get("warnings"))
                if isinstance(warning, Mapping)
            )
        ),
        "required_critic_roles": list(REQUIRED_CRITIC_ROLES),
    }


def _load_cases(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if not path.exists():
        return [], [
            _issue(
                "w11f_critic_input_path_missing",
                f"W11.F critic input path does not exist: {path}",
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
                    "w11f_critic_json_invalid",
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
    if not isinstance(payload, Mapping):
        return ()
    if isinstance(payload.get("cases"), list):
        return tuple(
            dict(item)
            for item in payload["cases"]
            if isinstance(item, Mapping) and not _is_corpus_stub_payload(item)
        )
    if _verdicts_from_case(payload) or payload.get("case_id") or payload.get("run_id"):
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


def _verdicts_from_case(case: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    candidates = (
        _nested(case, ("critic_ensemble", "verdicts")),
        _nested(case, ("critic_ensemble_report", "verdicts")),
        case.get("critic_verdicts"),
        case.get("verdicts"),
    )
    for candidate in candidates:
        rows = tuple(row for row in _sequence(candidate) if isinstance(row, Mapping))
        if rows:
            return rows
    return ()


def _case_id(case: Mapping[str, Any]) -> str:
    return (
        _text(case.get("case_id"))
        or _text(case.get("id"))
        or _text(case.get("run_id"))
        or "unknown-case"
    )


def _self_test_case_payload(*, collapsed: bool) -> dict[str, Any]:
    case_id = "w11f-critic-collapsed" if collapsed else "w11f-critic-diverse"
    return {
        "case_id": case_id,
        "domain": "housing",
        "authority_level": "governed",
        "critic_ensemble": {
            "run_id": f"run-{case_id}",
            "verdicts": [
                {
                    "verdict": "contest",
                    "envelope": {
                        "critic_role": role,
                        "substantive_basis": f"{role}_basis",
                        "critic_version": "self-test",
                    },
                    "target_candidate_ids": [f"candidate-{case_id}"],
                    "message": f"{role} critique",
                    "failure_modes": (
                        ["shared_failure_mode"]
                        if collapsed
                        else [f"{role}_specific_failure"]
                    ),
                }
                for role in REQUIRED_CRITIC_ROLES
            ],
        },
    }


def _anti_patterns(case_reports: Sequence[Mapping[str, Any]]) -> list[str]:
    found: list[str] = []
    if any(
        warning.get("code") == "critic_monoculture"
        for case in case_reports
        for warning in _sequence(case.get("warnings"))
        if isinstance(warning, Mapping)
    ):
        found.append("P15/P10: critic ensemble collapsed into indistinguishable outputs")
    if any(row.get("missing_critic_roles") for row in case_reports):
        found.append("producer_missing: at least one W6.E critic role is absent")
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


def _average(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _normalized_token(value: object) -> str:
    text = _text(value).casefold().replace("::", ":")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_.:/-]+", "_", text)
    return text.strip("_")


def _text(value: object) -> str:
    return str(value or "").strip()


def _warning(code: str, message: str, *, case_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": "warn",
        "case_id": case_id,
        **{key: value for key, value in extra.items() if value is not None},
    }


def _issue(code: str, message: str, *, severity: str = "error", **extra: Any) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "severity": severity,
        **{key: value for key, value in extra.items() if value is not None},
    }


if __name__ == "__main__":
    raise SystemExit(main())
