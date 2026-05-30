#!/usr/bin/env python3
"""Run the Wave 12.A local Policy Design Case validation ladder."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.runner import render_command, run_command

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.local_validation_ladder.v1"
MANIFEST_SCHEMA_VERSION = "policyos.policy_design_case.wave6.local_validation_ladder_manifest.v1"
TOOL_NAME = "quality.validation.run-policy-design-case-local-validation-ladder"
GENERATED_AT = "2026-05-23T00:00:00Z"
PHASE_ID = "W12.A"
LEGACY_PHASE_ID = "W6.A"
PHASE_NAME = "Local Validation Ladder (Re-Execution Over Universal Compilation)"
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/universal_pdc_local_validation_ladder.json")
DEFAULT_MANIFEST_OUTPUT = Path(
    "architecture/policy_design_case/wave6_local_validation_ladder_manifest.json"
)
DEFAULT_LOCAL_CORPUS_PATH = Path("architecture/policy_design_case/wave6_local_outcome_corpus.json")
DEFAULT_UNIVERSAL_CORPUS_PATH = Path("tests/fixtures/universal-corpus")
DEFAULT_W12D_REPORT = Path("_build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json")
LOCAL_PROD_QUICK_OUTPUT = Path("_build/.tmp/production-quality/universal_pdc_local_quick.json")
COMPILATION_TRUTHFULNESS_QUICK_OUTPUT = Path(
    "_build/.tmp/production-quality/compilation_truthfulness_smoke.json"
)
COMPILATION_TRUTHFULNESS_FULL_OUTPUT = Path(
    "_build/.tmp/production-quality/compilation_truthfulness_report.json"
)
DOMAIN_COVERAGE_QUICK_OUTPUT = Path(
    "_build/.tmp/production-quality/domain_coverage_breadth_smoke.json"
)
DOMAIN_COVERAGE_FULL_OUTPUT = Path(
    "_build/.tmp/production-quality/domain_coverage_breadth_report.json"
)
CRITIC_DIVERSITY_QUICK_OUTPUT = Path(
    "_build/.tmp/production-quality/critic_ensemble_diversity_smoke.json"
)
CRITIC_DIVERSITY_FULL_OUTPUT = Path(
    "_build/.tmp/production-quality/critic_ensemble_diversity_report.json"
)
UNIVERSAL_COMPILATION_CATEGORY = "universal_compilation_smoke"

HONEST_OUTCOMES = frozenset(
    {"pass", "publish_with_limitation", "accepted_deficit", "typed_blocker"}
)
USEFUL_DESIGN_OUTCOMES = frozenset({"pass", "publish_with_limitation"})
ROLLOUT_POSTURES = ("research-only", "governed-pilot", "production-capable")
PROFILES = ("quick", "full")


@dataclass(frozen=True)
class LadderCommand:
    """One command in the local validation ladder."""

    command_id: str
    category: str
    owner: str
    description: str
    argv: tuple[str, ...]
    timeout_s: int
    next_action: str
    output_refs: tuple[str, ...] = ()

    def as_manifest_row(self) -> dict[str, Any]:
        """Return a deterministic command row for manifests and reports."""

        return {
            "command_id": self.command_id,
            "category": self.category,
            "owner": self.owner,
            "description": self.description,
            "command": render_command(self.argv),
            "timeout_s": self.timeout_s,
            "output_refs": list(self.output_refs),
            "next_action": self.next_action,
        }


@dataclass(frozen=True)
class CommandResult:
    """Execution evidence for one command."""

    command_id: str
    status: str
    exit_code: int | None
    duration_ms: int
    stdout_tail: str = ""
    stderr_tail: str = ""
    error: str = ""


CommandExecutor = Callable[[LadderCommand, Path], CommandResult]


def build_ladder_commands(profile: str = "quick") -> tuple[LadderCommand, ...]:
    """Return the commands for a W12.A validation profile."""

    if profile not in PROFILES:
        raise ValueError(f"unknown W12.A local validation profile: {profile}")
    if profile == "full":
        return (
            LadderCommand(
                command_id="unit_runtime_quality",
                category="unit",
                owner="team-runtime-quality",
                description="Run the full runtime quality unit surface.",
                argv=("uv", "run", "pytest", "tests/unit/runtime/quality", "-q"),
                timeout_s=1800,
                next_action=(
                    "Repair the failing runtime-quality producer, bridge, consumer, "
                    "or semantic test before cloud validation."
                ),
            ),
            LadderCommand(
                command_id="unit_policy_producers",
                category="unit",
                owner="team-domain-producers",
                description="Run Scientist, Lex, Fabric, and Foundry unit surfaces.",
                argv=(
                    "uv",
                    "run",
                    "pytest",
                    "tests/unit/scientist",
                    "tests/unit/lex",
                    "tests/unit/fabric",
                    "tests/unit/foundry",
                    "-q",
                ),
                timeout_s=2400,
                next_action=(
                    "Repair producer adapter failures or emit typed producer blockers "
                    "before using live lanes."
                ),
            ),
            LadderCommand(
                command_id="repo_quality_closeout",
                category="repo_quality",
                owner="team-quality-closeout",
                description="Run evidence-bundle inspection and readiness repo-quality gates.",
                argv=(
                    "uv",
                    "run",
                    "pytest",
                    "tests/repo_quality/tools/test_evidence_bundle_inspection.py",
                    "tests/repo_quality/tools/test_policyos_production_quality_best_in_class.py",
                    "-q",
                ),
                timeout_s=900,
                next_action=(
                    "Repair bundle inspection/readiness findings or classify them as "
                    "typed blockers with owners."
                ),
            ),
            LadderCommand(
                command_id="repo_quality_public_docs",
                category="repo_quality",
                owner="team-docs-platform",
                description="Run public export and docs lifecycle repo-quality gates.",
                argv=(
                    "uv",
                    "run",
                    "pytest",
                    "tests/repo_quality/tools/test_policy_design_case_public_export.py",
                    "tests/repo_quality/tools/test_docs_lifecycle.py",
                    "tests/repo_quality/tools/test_docs_gate.py",
                    "-q",
                ),
                timeout_s=900,
                next_action=(
                    "Repair public/docs truthfulness or hold rollout until projection "
                    "surfaces preserve closeout truth."
                ),
            ),
            LadderCommand(
                command_id="semantic_evaluation",
                category="semantic",
                owner="team-evaluation",
                description="Run semantic gold-card and false-pass evaluation pack gates.",
                argv=(
                    "uv",
                    "run",
                    "pytest",
                    "tests/unit/runtime/quality/test_semantic_gold_cards.py",
                    "tests/repo_quality/tools/test_policy_design_case_w5b_semantic_evaluation_packs.py",
                    "-q",
                ),
                timeout_s=900,
                next_action=(
                    "Repair semantic false-pass coverage before declaring local "
                    "validation green."
                ),
            ),
            _compilation_truthfulness_command(profile="full"),
            _domain_coverage_breadth_command(profile="full"),
            _critic_ensemble_diversity_command(profile="full"),
            _capability_graph_exports_command(),
            _local_prod_debug_command(),
        )
    return (
        LadderCommand(
            command_id="unit_runtime_quality_smoke",
            category="unit",
            owner="team-runtime-quality",
            description=(
                "Run a bounded runtime quality smoke subset for "
                "closeout/projection semantics."
            ),
            argv=(
                "uv",
                "run",
                "pytest",
                "tests/unit/runtime/quality/test_closeout_reader.py",
                "tests/unit/runtime/quality/test_policy_design_case_projection_semantics.py",
                "tests/unit/runtime/quality/test_semantic_gold_cards.py",
                "-q",
            ),
            timeout_s=600,
            next_action=(
                "Repair closeout/projection/semantic smoke failures before running "
                "the full W12.A ladder."
            ),
        ),
        LadderCommand(
            command_id="unit_policy_producer_smoke",
            category="unit",
            owner="team-domain-producers",
            description="Run a bounded Scientist/Lex/Fabric/Foundry producer smoke subset.",
            argv=(
                "uv",
                "run",
                "pytest",
                "tests/unit/scientist/validation/test_claim_support.py",
                "tests/unit/lex/test_legal_authority_adapter.py",
                "tests/unit/fabric/test_source_selection_audit.py",
                "tests/unit/foundry/validation/test_method_quality.py",
                "-q",
            ),
            timeout_s=600,
            next_action=(
                "Repair producer smoke failures before broad unit or cloud validation."
            ),
        ),
        LadderCommand(
            command_id="repo_quality_smoke",
            category="repo_quality",
            owner="team-quality-closeout",
            description="Run capability-ratchet and evidence-bundle repo-quality smoke checks.",
            argv=(
                "uv",
                "run",
                "pytest",
                "tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py",
                "tests/repo_quality/tools/test_evidence_bundle_inspection.py",
                "-q",
            ),
            timeout_s=600,
            next_action=(
                "Repair repo-quality smoke failures or classify them as local typed "
                "blockers."
            ),
        ),
        LadderCommand(
            command_id="semantic_evaluation_smoke",
            category="semantic",
            owner="team-evaluation",
            description="Run semantic false-pass smoke checks.",
            argv=(
                "uv",
                "run",
                "pytest",
                "tests/repo_quality/tools/test_policy_design_case_w5b_semantic_evaluation_packs.py",
                "tests/unit/runtime/quality/test_policy_design_case_false_passes.py",
                "-q",
            ),
            timeout_s=600,
            next_action=(
                "Repair semantic smoke failures before declaring local validation green."
            ),
        ),
        _compilation_truthfulness_command(profile="quick"),
        _domain_coverage_breadth_command(profile="quick"),
        _critic_ensemble_diversity_command(profile="quick"),
        _capability_graph_exports_command(),
        _local_prod_debug_command(),
    )


def build_ladder_manifest() -> dict[str, Any]:
    """Build the repo-owned W12.A command and metric contract manifest."""

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "implemented",
        "phase_id": PHASE_ID,
        "legacy_phase_id": LEGACY_PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": GENERATED_AT,
        "owner": "team-runtime-quality",
        "implementation_plan_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            "#w12a-local-validation-ladder-re-execution-over-universal-compilation"
        ),
        "tool_ref": (
            "repo://tools/quality/validation/"
            "run_policy_design_case_local_validation_ladder.py"
        ),
        "manifest_path_compatibility": {
            "preserved_path": DEFAULT_MANIFEST_OUTPUT.as_posix(),
            "legacy_phase_id": LEGACY_PHASE_ID,
            "reason": (
                "The W6.A manifest path is retained for shim compatibility while "
                "W12.A re-executes the ladder over the compiled universal PDC."
            ),
            "sunset_policy": (
                "Record a dated architecture/shims.toml sunset only after the "
                "universal capability is production-capable."
            ),
        },
        "profile_commands": {
            profile: [command.as_manifest_row() for command in build_ladder_commands(profile)]
            for profile in PROFILES
        },
        "required_categories": [
            "unit",
            "repo_quality",
            "semantic",
            "local_production_debug",
            UNIVERSAL_COMPILATION_CATEGORY,
            "capability_graph_audit",
        ],
        "metric_policy": {
            "three_outcome_metrics": [
                "closeout_honesty",
                "useful_design",
                "compilation_truthfulness",
            ],
            "compilation_truthfulness_source": "W11.E",
            "domain_coverage_and_critic_diversity_source": "W11.F",
            "closeout_honesty_outcomes": sorted(HONEST_OUTCOMES),
            "useful_design_outcomes": sorted(USEFUL_DESIGN_OUTCOMES),
            "typed_blockers_count_as_closeout_honesty": True,
            "typed_blockers_count_as_useful_design": False,
            "accepted_deficits_count_as_useful_design": False,
            "structural_commitment": (
                "closeout honesty and useful-design capability are reported "
                "separately; typed blockers are diagnostics, not capability success"
            ),
        },
        "pattern_pass": {
            "relevant_patterns": ["P01", "P02", "P03", "P10", "P13", "P15"],
            "target_correct_pattern": (
                "Local validation is an executable command-evidence producer with "
                "typed blockers, owners, next actions, W11.E/W11.F command evidence, "
                "and separate capability metrics."
            ),
            "missing_capability_labels": [],
        },
        "validation": {
            "test_ref": (
                "repo://tests/repo_quality/tools/"
                "test_policy_design_case_local_validation_ladder.py"
            ),
            "command_ref": (
                "uv run python tools/quality/validation/"
                "run_policy_design_case_local_validation_ladder.py --repo-root . --profile quick"
            ),
        },
    }


def build_local_outcome_metrics(
    corpus_payload: Mapping[str, Any] | None,
    *,
    corpus_ref: str,
    rollout_posture: str,
    w12d_report_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute separate closeout-honesty and useful-design metrics."""

    if rollout_posture not in ROLLOUT_POSTURES:
        raise ValueError(f"unknown rollout posture: {rollout_posture}")
    if corpus_payload is None:
        if w12d_report_payload is not None:
            return _local_outcome_metrics_from_w12d(
                w12d_report_payload,
                corpus_ref=corpus_ref,
                rollout_posture=rollout_posture,
            )
        return {
            "status": "not_available",
            "source": "local_outcome_corpus",
            "corpus_ref": corpus_ref,
            "case_count": 0,
            "closeout_honesty": {
                "rate": None,
                "count": 0,
                "eligible_outcomes": sorted(HONEST_OUTCOMES),
            },
            "useful_design": {
                "rate": None,
                "count": 0,
                "eligible_outcomes": sorted(USEFUL_DESIGN_OUTCOMES),
                "typed_blockers_count_as_useful_design": False,
                "accepted_deficits_count_as_useful_design": False,
            },
            "capability_floor": {
                "rollout_posture": rollout_posture,
                "status": "not_evaluated",
                "reason": "local outcome corpus is not available",
            },
            "blocker_deficit": {
                "typed_blocker_count": 0,
                "accepted_deficit_count": 0,
                "counts_against_capability": True,
            },
            "issues": [
                {
                    "code": "local_outcome_corpus_missing",
                    "severity": "warn",
                    "owner": "team-evaluation",
                    "next_action": (
                        "Provide the W12.A local outcome corpus before making "
                        "useful-design capability claims."
                    ),
                }
            ],
        }

    cases = _sequence_of_mappings(corpus_payload.get("cases"))
    case_count = len(cases)
    honest_count = 0
    useful_count = 0
    typed_blocker_count = 0
    accepted_deficit_count = 0
    laundering_count = 0
    domain_totals: dict[str, int] = {}
    domain_useful: dict[str, int] = {}
    issues: list[dict[str, Any]] = []

    for index, case in enumerate(cases):
        case_id = str(case.get("case_id") or f"case_{index}")
        outcome = str(case.get("outcome") or "")
        domain = str(case.get("domain_slice") or "unspecified")
        laundering = bool(case.get("authority_laundering"))
        domain_totals[domain] = domain_totals.get(domain, 0) + 1
        if laundering:
            laundering_count += 1
            issues.append(
                {
                    "code": "local_case_authority_laundering",
                    "severity": "fail",
                    "case_id": case_id,
                    "owner": case.get("owner") or "team-runtime-quality",
                    "next_action": (
                        "Repair projection, LLM, packaging, bridge, historical-prior, "
                        "or raw-count laundering before counting the case as honest."
                    ),
                }
            )
        if outcome == "typed_blocker":
            typed_blocker_count += 1
        if outcome == "accepted_deficit":
            accepted_deficit_count += 1
        if outcome in HONEST_OUTCOMES and not laundering:
            honest_count += 1
        if outcome in USEFUL_DESIGN_OUTCOMES and not laundering:
            useful_count += 1
            domain_useful[domain] = domain_useful.get(domain, 0) + 1
        if outcome in {"typed_blocker", "accepted_deficit"} and case.get(
            "counts_as_useful_design"
        ):
            issues.append(
                {
                    "code": "non_capability_outcome_counted_as_useful_design",
                    "severity": "fail",
                    "case_id": case_id,
                    "outcome": outcome,
                    "owner": case.get("owner") or "team-evaluation",
                    "next_action": (
                        "Remove typed blockers and accepted deficits from useful-design "
                        "capability metrics."
                    ),
                }
            )

    domain_rows = []
    for domain, total in sorted(domain_totals.items()):
        useful = domain_useful.get(domain, 0)
        domain_rows.append(
            {
                "domain_slice": domain,
                "case_count": total,
                "useful_design_count": useful,
                "useful_design_rate": _rate(useful, total),
                "has_useful_design": useful > 0,
            }
        )

    useful_rate = _rate(useful_count, case_count)
    floor = _capability_floor(
        rollout_posture=rollout_posture,
        useful_rate=useful_rate,
        domain_rows=domain_rows,
    )
    status = "fail" if any(issue["severity"] == "fail" for issue in issues) else "pass"
    return {
        "status": status,
        "corpus_ref": corpus_ref,
        "schema_version": corpus_payload.get("schema_version"),
        "case_count": case_count,
        "closeout_honesty": {
            "rate": _rate(honest_count, case_count),
            "count": honest_count,
            "eligible_outcomes": sorted(HONEST_OUTCOMES),
            "authority_laundering_count": laundering_count,
        },
        "useful_design": {
            "rate": useful_rate,
            "count": useful_count,
            "eligible_outcomes": sorted(USEFUL_DESIGN_OUTCOMES),
            "typed_blockers_count_as_useful_design": False,
            "accepted_deficits_count_as_useful_design": False,
        },
        "domain_useful_coverage": domain_rows,
        "capability_floor": floor,
        "blocker_deficit": {
            "typed_blocker_count": typed_blocker_count,
            "accepted_deficit_count": accepted_deficit_count,
            "counts_against_capability": True,
        },
        "issues": issues,
    }


def build_compilation_truthfulness_metrics(
    report_payload: Mapping[str, Any] | None,
    *,
    report_ref: str,
    rollout_posture: str,
) -> dict[str, Any]:
    """Compute the W12.A compilation-truthfulness metric from a W11.E report."""

    if rollout_posture not in ROLLOUT_POSTURES:
        raise ValueError(f"unknown rollout posture: {rollout_posture}")
    if report_payload is None:
        return {
            "status": "not_available",
            "source": "W11.E",
            "report_ref": report_ref,
            "case_count": 0,
            "blocked_case_count": 0,
            "rate": None,
            "by_domain": {},
            "by_authority_level": {},
            "capability_floor": {
                "rollout_posture": rollout_posture,
                "status": "not_evaluated",
                "reason": "compilation truthfulness report is not available",
            },
            "issues": [
                {
                    "code": "compilation_truthfulness_report_missing",
                    "severity": "warn",
                    "owner": "team-evaluation",
                    "next_action": (
                        "Run the W11.E compilation truthfulness command before "
                        "making W12.A compilation-capability claims."
                    ),
                }
            ],
        }

    issues: list[dict[str, Any]] = []
    summary = report_payload.get("summary")
    if not isinstance(summary, Mapping):
        issues.append(
            {
                "code": "compilation_truthfulness_summary_missing",
                "severity": "fail",
                "owner": "team-evaluation",
                "next_action": (
                    "Regenerate the W11.E report with a valid summary before W12.A "
                    "can use it."
                ),
            }
        )
        summary = {}

    rate = _float_or_none(summary.get("aggregate_compilation_truthfulness_rate"))
    by_domain = _mapping_of_mappings(summary.get("by_domain"))
    by_authority_level = _mapping_of_mappings(summary.get("by_authority_level"))
    floor = _compilation_truthfulness_floor(
        rollout_posture=rollout_posture,
        aggregate_rate=rate,
        by_domain=by_domain,
    )

    if str(summary.get("status") or "fail") == "fail":
        issues.append(
            {
                "code": "compilation_truthfulness_report_failed",
                "severity": "fail",
                "owner": "team-evaluation",
                "next_action": (
                    "Repair W11.E blocked cases, missing adjudication, or validation "
                    "issues before treating compilation truthfulness as green."
                ),
            }
        )
    if floor["status"] == "not_met":
        if floor.get("aggregate_below_floor"):
            issues.append(
                {
                    "code": "compilation_truthfulness_aggregate_floor_not_met",
                    "severity": "fail",
                    "owner": "team-evaluation",
                    "next_action": (
                        "Repair missed, hallucinated, scope-drift, or authority-drift "
                        "obligations until the aggregate W11.E score meets the "
                        "declared rollout posture floor."
                    ),
                }
            )
        if floor.get("below_floor_domain_slices"):
            issues.append(
                {
                    "code": "compilation_truthfulness_domain_floor_not_met",
                    "severity": "fail",
                    "owner": "team-evaluation",
                    "domain_slices": floor["below_floor_domain_slices"],
                    "next_action": (
                        "Repair domain-specific compiler drift or mark the domain "
                        "slice research-only/held in the rollout decision."
                    ),
                }
            )

    return {
        "status": "fail" if any(issue["severity"] == "fail" for issue in issues) else "pass",
        "source": "W11.E",
        "report_ref": report_ref,
        "schema_version": report_payload.get("schema_version"),
        "case_count": int(summary.get("case_count") or 0),
        "blocked_case_count": int(summary.get("blocked_case_count") or 0),
        "rate": rate,
        "by_domain": by_domain,
        "by_authority_level": by_authority_level,
        "capability_floor": floor,
        "issues": issues,
    }


def _local_outcome_metrics_from_w12d(
    w12d_report_payload: Mapping[str, Any],
    *,
    corpus_ref: str,
    rollout_posture: str,
) -> dict[str, Any]:
    summary = _mapping(w12d_report_payload.get("summary"))
    closeout_rate = _float_or_none(summary.get("closeout_honesty_rate"))
    closeout_count = int(summary.get("closeout_honesty_count") or 0)
    case_count = int(summary.get("case_count") or 0)
    useful_rate = _float_or_none(summary.get("runtime_useful_design_rate"))
    useful_count = int(summary.get("runtime_useful_design_count") or 0)
    issues: list[dict[str, Any]] = []
    if closeout_rate is None:
        issues.append(
            {
                "code": "w12d_closeout_honesty_metric_missing",
                "severity": "warn",
                "owner": "team-evaluation",
                "next_action": (
                    "Regenerate W12.D with closeout_honesty_rate before W12.A "
                    "uses it as the fallback metric source."
                ),
            }
        )
    return {
        "status": "fail"
        if any(issue["severity"] == "fail" for issue in issues)
        else "pass"
        if closeout_rate is not None
        else "not_available",
        "source": "W12.D",
        "corpus_ref": corpus_ref,
        "case_count": case_count,
        "closeout_honesty": {
            "rate": closeout_rate,
            "count": closeout_count,
            "eligible_outcomes": sorted(HONEST_OUTCOMES),
            "source_phase": "W12.D",
        },
        "useful_design": {
            "rate": useful_rate,
            "count": useful_count,
            "eligible_outcomes": sorted(USEFUL_DESIGN_OUTCOMES),
            "typed_blockers_count_as_useful_design": False,
            "accepted_deficits_count_as_useful_design": False,
            "source_phase": "W12.D",
        },
        "capability_floor": _capability_floor(
            rollout_posture=rollout_posture,
            useful_rate=useful_rate,
            domain_rows=[],
        ),
        "blocker_deficit": {
            "typed_blocker_count": int(summary.get("typed_blocker_case_count") or 0),
            "accepted_deficit_count": int(
                _mapping(summary.get("outcome_counts")).get("accepted_deficit") or 0
            ),
            "counts_against_capability": True,
        },
        "issues": issues,
    }


def build_domain_coverage_metrics(
    report_payload: Mapping[str, Any] | None,
    *,
    report_ref: str,
) -> dict[str, Any]:
    """Summarize W11.F domain coverage breadth for the W12.A report."""

    if report_payload is None:
        return {
            "status": "not_available",
            "source": "W11.F",
            "report_ref": report_ref,
            "domain_coverage_breadth": None,
            # ``per_authority_expert_useful_design_ceiling`` reflects what
            # corpus annotations say is achievable per authority level. The
            # runtime achievement is reported separately in
            # ``runtime_useful_design_rate`` from the W12.D ladder block, and
            # the alignment between them is ``useful_design_alignment_rate``.
            "per_authority_expert_useful_design_ceiling": {},
            "issues": [
                {
                    "code": "domain_coverage_breadth_report_missing",
                    "severity": "warn",
                    "owner": "team-evaluation",
                    "next_action": (
                        "Run the W11.F domain coverage breadth command before "
                        "rollout posture decisions."
                    ),
                }
            ],
        }
    summary = report_payload.get("summary")
    issues: list[dict[str, Any]] = []
    if not isinstance(summary, Mapping):
        issues.append(
            {
                "code": "domain_coverage_breadth_summary_missing",
                "severity": "fail",
                "owner": "team-evaluation",
                "next_action": "Regenerate the W11.F domain coverage report.",
            }
        )
        summary = {}
    if str(summary.get("status") or "fail") == "fail":
        issues.append(
            {
                "code": "domain_coverage_breadth_report_failed",
                "severity": "fail",
                "owner": "team-evaluation",
                "next_action": (
                    "Repair W6.C graph availability or classify domain slices as "
                    "typed blockers before rollout."
                ),
            }
        )
    return {
        "status": "fail" if any(issue["severity"] == "fail" for issue in issues) else "pass",
        "source": "W11.F",
        "report_ref": report_ref,
        "schema_version": report_payload.get("schema_version"),
        "case_count": int(summary.get("case_count") or 0),
        "committed_domain_count": int(summary.get("committed_domain_count") or 0),
        "domain_coverage_breadth": summary.get("domain_coverage_breadth"),
        "non_trivial_domain_ids": list(summary.get("non_trivial_domain_ids") or []),
        "per_authority_expert_useful_design_ceiling": _mapping_of_mappings(
            summary.get("per_authority_expert_useful_design_ceiling")
        ),
        "issues": issues,
    }


def build_critic_diversity_metrics(
    report_payload: Mapping[str, Any] | None,
    *,
    report_ref: str,
) -> dict[str, Any]:
    """Summarize W11.F critic diversity for the W12.A report."""

    if report_payload is None:
        return {
            "status": "not_available",
            "source": "W11.F",
            "report_ref": report_ref,
            "aggregate_critic_ensemble_diversity_jaccard": None,
            "cases_with_monoculture_warning": 0,
            "issues": [
                {
                    "code": "critic_ensemble_diversity_report_missing",
                    "severity": "warn",
                    "owner": "team-evaluation",
                    "next_action": (
                        "Run the W11.F critic ensemble diversity command before "
                        "rollout posture decisions."
                    ),
                }
            ],
        }
    summary = report_payload.get("summary")
    issues: list[dict[str, Any]] = []
    if not isinstance(summary, Mapping):
        issues.append(
            {
                "code": "critic_ensemble_diversity_summary_missing",
                "severity": "fail",
                "owner": "team-evaluation",
                "next_action": "Regenerate the W11.F critic diversity report.",
            }
        )
        summary = {}
    if str(summary.get("status") or "fail") == "fail":
        issues.append(
            {
                "code": "critic_ensemble_diversity_report_failed",
                "severity": "fail",
                "owner": "team-evaluation",
                "next_action": (
                    "Repair malformed critic reports before treating ensemble "
                    "diversity as inspectable."
                ),
            }
        )
    return {
        "status": "fail" if any(issue["severity"] == "fail" for issue in issues) else "pass",
        "source": "W11.F",
        "report_ref": report_ref,
        "schema_version": report_payload.get("schema_version"),
        "case_count": int(summary.get("case_count") or 0),
        "diversity_floor": summary.get("diversity_floor"),
        "aggregate_critic_ensemble_diversity_jaccard": summary.get(
            "aggregate_critic_ensemble_diversity_jaccard"
        ),
        "cases_below_diversity_floor": int(summary.get("cases_below_diversity_floor") or 0),
        "cases_with_monoculture_warning": int(
            summary.get("cases_with_monoculture_warning") or 0
        ),
        "warnings": list(report_payload.get("warnings") or []),
        "issues": issues,
    }


def build_three_outcome_metric_summary(
    *,
    local_outcome_metrics: Mapping[str, Any],
    compilation_truthfulness_metrics: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the W12.A three-metric outcome summary without collapsing metrics."""

    return {
        "closeout_honesty": local_outcome_metrics.get(
            "closeout_honesty",
            {"rate": None, "count": 0},
        ),
        "useful_design": local_outcome_metrics.get(
            "useful_design",
            {"rate": None, "count": 0},
        ),
        "compilation_truthfulness": {
            "status": compilation_truthfulness_metrics.get("status"),
            "rate": compilation_truthfulness_metrics.get("rate"),
            "source": compilation_truthfulness_metrics.get("source"),
            "capability_floor": compilation_truthfulness_metrics.get("capability_floor"),
        },
    }


def run_local_validation_ladder(
    *,
    repo_root: Path,
    profile: str = "quick",
    rollout_posture: str = "research-only",
    local_corpus_json: Path | None = None,
    compilation_truthfulness_json: Path | None = None,
    domain_coverage_json: Path | None = None,
    critic_diversity_json: Path | None = None,
    w12d_report_json: Path | None = None,
    plan_only: bool = False,
    only_command_ids: Sequence[str] = (),
    executor: CommandExecutor | None = None,
) -> dict[str, Any]:
    """Run or plan the W12.A local validation ladder."""

    repo_root = repo_root.resolve()
    commands = list(build_ladder_commands(profile))
    if only_command_ids:
        requested = set(only_command_ids)
        commands = [command for command in commands if command.command_id in requested]
        missing = requested - {command.command_id for command in commands}
        if missing:
            raise ValueError(f"unknown command id(s) for profile {profile}: {sorted(missing)}")
    runner = executor or execute_command
    command_rows: list[dict[str, Any]] = []
    typed_blockers: list[dict[str, Any]] = []

    for command in commands:
        if plan_only:
            result = CommandResult(
                command_id=command.command_id,
                status="skipped",
                exit_code=None,
                duration_ms=0,
            )
        else:
            result = runner(command, repo_root)
        row = {
            **command.as_manifest_row(),
            "status": result.status,
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
            "stdout_tail": result.stdout_tail,
            "stderr_tail": result.stderr_tail,
            "error": result.error,
        }
        if result.status != "pass" and not plan_only:
            blocker = _typed_blocker_for_command(command, result, repo_root=repo_root)
            row["typed_blocker"] = blocker
            typed_blockers.append(blocker)
        command_rows.append(row)

    corpus_path = local_corpus_json or DEFAULT_LOCAL_CORPUS_PATH
    resolved_corpus = _resolve(repo_root, corpus_path)
    corpus_payload = None
    if resolved_corpus.exists():
        corpus_payload = json.loads(resolved_corpus.read_text(encoding="utf-8"))
    w12d_report_path = _resolve(repo_root, w12d_report_json or DEFAULT_W12D_REPORT)
    local_metrics = build_local_outcome_metrics(
        corpus_payload,
        corpus_ref=f"repo://{_repo_relative(repo_root, resolved_corpus)}",
        rollout_posture=rollout_posture,
        w12d_report_payload=_load_json_if_available(w12d_report_path, plan_only=plan_only),
    )
    compilation_report_path = _resolve(
        repo_root,
        compilation_truthfulness_json or _compilation_truthfulness_output(profile),
    )
    domain_report_path = _resolve(
        repo_root,
        domain_coverage_json or _domain_coverage_output(profile),
    )
    critic_report_path = _resolve(
        repo_root,
        critic_diversity_json or _critic_diversity_output(profile),
    )
    compilation_metrics = build_compilation_truthfulness_metrics(
        _load_json_if_available(compilation_report_path, plan_only=plan_only),
        report_ref=f"repo://{_repo_relative(repo_root, compilation_report_path)}",
        rollout_posture=rollout_posture,
    )
    domain_metrics = build_domain_coverage_metrics(
        _load_json_if_available(domain_report_path, plan_only=plan_only),
        report_ref=f"repo://{_repo_relative(repo_root, domain_report_path)}",
    )
    critic_metrics = build_critic_diversity_metrics(
        _load_json_if_available(critic_report_path, plan_only=plan_only),
        report_ref=f"repo://{_repo_relative(repo_root, critic_report_path)}",
    )
    metric_reports = (local_metrics, compilation_metrics, domain_metrics, critic_metrics)
    typed_blockers.extend(_typed_blockers_for_metric_reports(metric_reports))
    command_summary = _command_summary(command_rows)
    status = _overall_status(
        plan_only=plan_only,
        command_summary=command_summary,
        typed_blockers=typed_blockers,
        metric_reports=metric_reports,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "phase_id": PHASE_ID,
        "legacy_phase_id": LEGACY_PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "repo_root": str(repo_root),
        "profile": profile,
        "rollout_posture": rollout_posture,
        "status": status,
        "command_summary": command_summary,
        "commands": command_rows,
        "typed_blockers": typed_blockers,
        "local_outcome_metrics": local_metrics,
        "compilation_truthfulness_metrics": compilation_metrics,
        "domain_coverage_metrics": domain_metrics,
        "critic_ensemble_diversity_metrics": critic_metrics,
        "capability_graph_validation_hooks": {
            "capability_index_load_required": True,
            "construct_registry_load_required": True,
            "resolver_execution_required": True,
            "selected_binding_required": True,
            "typed_blocked_binding_visible": True,
            "rejected_alternative_required": True,
            "hypothesis_ledger_required": True,
            "audit_card_generation_required": True,
            "source": "Policy Evidence Capability Graph Phase 7",
        },
        "outcome_metrics": build_three_outcome_metric_summary(
            local_outcome_metrics=local_metrics,
            compilation_truthfulness_metrics=compilation_metrics,
        ),
        "capability_statement": {
            "closeout_honesty_is_safety_floor": True,
            "useful_design_is_capability_floor": True,
            "compilation_truthfulness_is_universal_compilation_floor": True,
            "capability_graph_audit_required": True,
            "typed_blockers_are_useful_diagnostics": True,
            "typed_blockers_count_as_capability_success": False,
        },
        "next_actions": _next_actions(typed_blockers=typed_blockers, metrics=metric_reports),
        "manifest_ref": f"repo://{DEFAULT_MANIFEST_OUTPUT.as_posix()}",
    }


def execute_command(command: LadderCommand, repo_root: Path) -> CommandResult:
    """Execute a ladder command and return bounded command evidence."""

    started = time.monotonic()
    try:
        completed = run_command(
            command.argv,
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=command.timeout_s,
            check=False,
        )
        duration_ms = int((time.monotonic() - started) * 1000)
        return CommandResult(
            command_id=command.command_id,
            status="pass" if completed.returncode == 0 else "fail",
            exit_code=completed.returncode,
            duration_ms=duration_ms,
            stdout_tail=_tail(completed.stdout),
            stderr_tail=_tail(completed.stderr),
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return CommandResult(
            command_id=command.command_id,
            status="fail",
            exit_code=124,
            duration_ms=duration_ms,
            stdout_tail=_tail(exc.stdout),
            stderr_tail=_tail(exc.stderr),
            error=f"command timed out after {command.timeout_s}s",
        )
    except OSError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        return CommandResult(
            command_id=command.command_id,
            status="fail",
            exit_code=127,
            duration_ms=duration_ms,
            error=str(exc),
        )


def write_manifest(repo_root: Path, output: Path = DEFAULT_MANIFEST_OUTPUT) -> dict[str, Any]:
    """Write the deterministic W12.A ladder manifest."""

    payload = build_ladder_manifest()
    atomic_write_json(_resolve(repo_root, output), payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build the W12.A local validation ladder CLI parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--profile", choices=PROFILES, default="quick")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--local-corpus-json", type=Path)
    parser.add_argument("--compilation-truthfulness-json", type=Path)
    parser.add_argument("--domain-coverage-json", type=Path)
    parser.add_argument("--critic-diversity-json", type=Path)
    parser.add_argument("--w12d-report-json", type=Path)
    parser.add_argument(
        "--rollout-posture",
        choices=ROLLOUT_POSTURES,
        default="research-only",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Write command/metric evidence without executing subprocesses.",
    )
    parser.add_argument(
        "--only-command",
        action="append",
        default=[],
        help="Run only a command id from the selected profile; repeatable.",
    )
    parser.add_argument(
        "--allow-typed-blockers",
        action="store_true",
        help="Exit zero when failures are classified as typed blockers.",
    )
    parser.add_argument(
        "--require-passing",
        action="store_true",
        help="Exit non-zero unless every command and available corpus metric passes.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the W12.A local validation ladder."""

    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.write_manifest or args.manifest_output:
        write_manifest(repo_root, output=args.manifest_output or DEFAULT_MANIFEST_OUTPUT)
    payload = run_local_validation_ladder(
        repo_root=repo_root,
        profile=args.profile,
        rollout_posture=args.rollout_posture,
        local_corpus_json=args.local_corpus_json,
        compilation_truthfulness_json=args.compilation_truthfulness_json,
        domain_coverage_json=args.domain_coverage_json,
        critic_diversity_json=args.critic_diversity_json,
        w12d_report_json=args.w12d_report_json,
        plan_only=args.plan_only,
        only_command_ids=args.only_command,
    )
    atomic_write_json(_resolve(repo_root, args.output), payload)
    sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")
    if payload["status"] == "pass" or payload["status"] == "planned":
        return 0
    if args.allow_typed_blockers and payload["status"] == "blocked":
        return 0
    if args.require_passing:
        return 1
    return 2


def _local_prod_debug_command() -> LadderCommand:
    return LadderCommand(
        command_id="local_prod_debug_quick",
        category="local_production_debug",
        owner="team-platform-runtime",
        description="Run the local production-debug quick path before cloud lanes.",
        argv=(
            "uv",
            "run",
            "--extra",
            "runtime",
            "--extra",
            "multi-tenant",
            "--extra",
            "ml",
            "python",
            "tools/quality/testing/local_prod_debug_probe.py",
            "--repo-root",
            ".",
            "--checks",
            "quick,production-data-static,docs-repro",
            "--output",
            LOCAL_PROD_QUICK_OUTPUT.as_posix(),
        ),
        timeout_s=1200,
        output_refs=(LOCAL_PROD_QUICK_OUTPUT.as_posix(),),
        next_action=(
            "Repair local production-debug wiring or keep cloud validation held "
            "with a typed blocker owner."
        ),
    )


def _compilation_truthfulness_command(*, profile: str) -> LadderCommand:
    output = _compilation_truthfulness_output(profile)
    if profile == "quick":
        command_id = "compilation_truthfulness_smoke"
        description = "Run the W11.E compilation truthfulness self-test smoke."
        argv = (
            "uv",
            "run",
            "python",
            "tools/quality/validation/check_compilation_truthfulness.py",
            "--self-test",
            "--repo-root",
            ".",
            "--output",
            output.as_posix(),
        )
        timeout_s = 600
    else:
        command_id = "compilation_truthfulness_corpus"
        description = "Run W11.E compilation truthfulness over the universal outcome corpus."
        argv = (
            "uv",
            "run",
            "python",
            "tools/quality/validation/check_compilation_truthfulness.py",
            "--corpus",
            DEFAULT_UNIVERSAL_CORPUS_PATH.as_posix(),
            "--repo-root",
            ".",
            "--output",
            output.as_posix(),
        )
        timeout_s = 1200
    return LadderCommand(
        command_id=command_id,
        category=UNIVERSAL_COMPILATION_CATEGORY,
        owner="team-evaluation",
        description=description,
        argv=argv,
        timeout_s=timeout_s,
        output_refs=(output.as_posix(),),
        next_action=(
            "Repair W11.E missed, hallucinated, scope-drift, or authority-drift "
            "obligations before using W12 rollout evidence."
        ),
    )


def _domain_coverage_breadth_command(*, profile: str) -> LadderCommand:
    output = _domain_coverage_output(profile)
    if profile == "quick":
        command_id = "domain_coverage_breadth_smoke"
        description = "Run the W11.F domain coverage breadth self-test smoke."
        argv = (
            "uv",
            "run",
            "python",
            "tools/quality/validation/check_domain_coverage_breadth.py",
            "--self-test",
            "--repo-root",
            ".",
            "--output",
            output.as_posix(),
        )
        timeout_s = 600
    else:
        command_id = "domain_coverage_breadth_corpus"
        description = "Run W11.F domain coverage breadth over the universal outcome corpus."
        argv = (
            "uv",
            "run",
            "python",
            "tools/quality/validation/check_domain_coverage_breadth.py",
            "--corpus",
            DEFAULT_UNIVERSAL_CORPUS_PATH.as_posix(),
            "--repo-root",
            ".",
            "--output",
            output.as_posix(),
        )
        timeout_s = 1200
    return LadderCommand(
        command_id=command_id,
        category=UNIVERSAL_COMPILATION_CATEGORY,
        owner="team-evaluation",
        description=description,
        argv=argv,
        timeout_s=timeout_s,
        output_refs=(output.as_posix(),),
        next_action=(
            "Repair W11.F domain graph coverage or mark uncovered domains as "
            "research-only/held before rollout."
        ),
    )


def _critic_ensemble_diversity_command(*, profile: str) -> LadderCommand:
    output = _critic_diversity_output(profile)
    if profile == "quick":
        command_id = "critic_ensemble_diversity_smoke"
        description = "Run the W11.F critic ensemble diversity self-test smoke."
        argv = (
            "uv",
            "run",
            "python",
            "tools/quality/validation/check_critic_ensemble_diversity.py",
            "--self-test",
            "--repo-root",
            ".",
            "--output",
            output.as_posix(),
        )
        timeout_s = 600
    else:
        command_id = "critic_ensemble_diversity_corpus"
        description = "Run W11.F critic ensemble diversity over universal critic fixtures."
        argv = (
            "uv",
            "run",
            "python",
            "tools/quality/validation/check_critic_ensemble_diversity.py",
            "--input",
            DEFAULT_UNIVERSAL_CORPUS_PATH.as_posix(),
            "--repo-root",
            ".",
            "--output",
            output.as_posix(),
        )
        timeout_s = 1200
    return LadderCommand(
        command_id=command_id,
        category=UNIVERSAL_COMPILATION_CATEGORY,
        owner="team-evaluation",
        description=description,
        argv=argv,
        timeout_s=timeout_s,
        output_refs=(output.as_posix(),),
        next_action=(
            "Repair critic monoculture or classify the diversity warning before "
            "promotion beyond governed pilot."
        ),
    )


def _capability_graph_exports_command() -> LadderCommand:
    return LadderCommand(
        command_id="capability_graph_exports",
        category="capability_graph_audit",
        owner="team-runtime-quality",
        description="Run Phase 7 capability graph export, PROV, inspection, and card gates.",
        argv=(
            "uv",
            "run",
            "pytest",
            "tests/repo_quality/tools/test_policy_evidence_capability_exports.py",
            "-q",
        ),
        timeout_s=600,
        next_action=(
            "Repair DCAT/PROV/card/inspection generation before treating the "
            "capability graph as externally inspectable."
        ),
    )


def _typed_blocker_for_command(
    command: LadderCommand,
    result: CommandResult,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    environment_blocker_code = _environment_blocker_code(
        result,
        command=command,
        repo_root=repo_root,
    )
    code = (
        "local_validation_environment_blocker"
        if environment_blocker_code
        else
        "universal_compilation_smoke_command_failed"
        if command.category == UNIVERSAL_COMPILATION_CATEGORY
        else "local_validation_command_failed"
    )
    blocker = {
        "blocker_id": f"w12a_{command.command_id}_blocked",
        "code": code,
        "severity": "blocker",
        "command_id": command.command_id,
        "category": command.category,
        "owner": command.owner,
        "exit_code": result.exit_code,
        "message": (
            "A W12.A local validation command failed. This is useful diagnostic "
            "evidence, not useful-design capability success."
        ),
        "next_action": command.next_action,
        "blocks_cloud_validation": True,
        "counts_as_closeout_honesty": environment_blocker_code is None,
        "counts_as_useful_design": False,
    }
    if environment_blocker_code:
        blocker["environment_blocker_code"] = environment_blocker_code
        blocker["next_action"] = (
            "Provide the missing local/cloud environment dependency before "
            "treating production-debug evidence as available."
        )
    return blocker


def _environment_blocker_code(
    result: CommandResult,
    *,
    command: LadderCommand | None = None,
    repo_root: Path | None = None,
) -> str | None:
    combined = "\n".join(
        part
        for part in (result.stdout_tail, result.stderr_tail, result.error)
        if part
    )
    for code in ("postgres_dsn_missing", "database_url_missing"):
        if code in combined:
            return code
    if command is None or repo_root is None:
        return None
    for output_ref in command.output_refs:
        output_path = _resolve(repo_root, Path(output_ref))
        if not output_path.exists():
            continue
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        code = _environment_blocker_code_from_payload(payload)
        if code:
            return code
    return None


def _environment_blocker_code_from_payload(payload: object) -> str | None:
    if isinstance(payload, Mapping):
        code = payload.get("code")
        if code in {"postgres_dsn_missing", "database_url_missing"}:
            return str(code)
        for key in ("checks", "typed_blockers", "issues", "failures", "results"):
            code = _environment_blocker_code_from_payload(payload.get(key))
            if code:
                return code
        for value in payload.values():
            code = _environment_blocker_code_from_payload(value)
            if code:
                return code
    if isinstance(payload, Sequence) and not isinstance(payload, str | bytes):
        for item in payload:
            code = _environment_blocker_code_from_payload(item)
            if code:
                return code
    return None


def _command_summary(command_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"total": len(command_rows), "pass": 0, "fail": 0, "skipped": 0}
    for row in command_rows:
        status = str(row.get("status") or "fail")
        if status not in counts:
            counts[status] = 0
        counts[status] += 1
    return counts


def _overall_status(
    *,
    plan_only: bool,
    command_summary: Mapping[str, int],
    typed_blockers: Sequence[Mapping[str, Any]],
    metric_reports: Sequence[Mapping[str, Any]],
) -> str:
    if plan_only:
        return "planned"
    if typed_blockers:
        return "blocked"
    if any(metric.get("status") == "fail" for metric in metric_reports):
        return "blocked"
    if command_summary.get("fail", 0) > 0:
        return "fail"
    return "pass"


def _next_actions(
    *,
    typed_blockers: Sequence[Mapping[str, Any]],
    metrics: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for blocker in typed_blockers:
        actions.append(
            {
                "owner": blocker["owner"],
                "reason": blocker["code"],
                "next_action": blocker["next_action"],
            }
        )
    for metric in metrics:
        for issue in _sequence_of_mappings(metric.get("issues")):
            actions.append(
                {
                    "owner": issue.get("owner") or "team-runtime-quality",
                    "reason": issue.get("code") or "local_outcome_metric_issue",
                    "next_action": issue.get("next_action") or "Classify the metric issue.",
                }
            )
    if not actions:
        actions.append(
            {
                "owner": "team-runtime-quality",
                "reason": "local_validation_green",
                "next_action": (
                    "Proceed to bundle/replay/cloud validation using the same "
                    "revision and config."
                ),
            }
        )
    return actions


def _typed_blockers_for_metric_reports(
    metric_reports: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for metric in metric_reports:
        source = str(metric.get("source") or "local_outcome")
        for issue in _sequence_of_mappings(metric.get("issues")):
            if issue.get("severity") not in {"fail", "blocker"}:
                continue
            code = str(issue.get("code") or "local_outcome_metric_issue")
            blockers.append(
                {
                    "blocker_id": f"w12a_metric_{code}",
                    "code": code,
                    "severity": "blocker",
                    "category": "outcome_metric",
                    "source": source,
                    "owner": issue.get("owner") or "team-runtime-quality",
                    "message": (
                        "A W12.A outcome metric failed. This is typed blocker "
                        "evidence, not useful-design capability success."
                    ),
                    "next_action": issue.get("next_action")
                    or "Classify and repair the metric failure.",
                    "blocks_cloud_validation": True,
                    "counts_as_closeout_honesty": True,
                    "counts_as_useful_design": False,
                }
            )
    return blockers


def _capability_floor(
    *,
    rollout_posture: str,
    useful_rate: float | None,
    domain_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if rollout_posture == "research-only":
        return {
            "rollout_posture": rollout_posture,
            "status": "not_required",
            "minimum_useful_design_rate": None,
            "requires_each_domain_useful": False,
        }
    if useful_rate is None:
        return {
            "rollout_posture": rollout_posture,
            "status": "not_evaluated",
            "reason": "useful design rate is unavailable",
        }
    missing_domains = [
        str(row["domain_slice"])
        for row in domain_rows
        if int(row.get("useful_design_count") or 0) <= 0
    ]
    if rollout_posture == "governed-pilot":
        met = useful_rate >= 0.5 and not missing_domains
        return {
            "rollout_posture": rollout_posture,
            "status": "met" if met else "not_met",
            "minimum_useful_design_rate": 0.5,
            "requires_each_domain_useful": True,
            "missing_useful_domain_slices": missing_domains,
        }
    below_floor = [
        str(row["domain_slice"])
        for row in domain_rows
        if float(row.get("useful_design_rate") or 0.0) < 0.4
    ]
    met = useful_rate >= 0.7 and not missing_domains and not below_floor
    return {
        "rollout_posture": rollout_posture,
        "status": "met" if met else "not_met",
        "minimum_useful_design_rate": 0.7,
        "minimum_domain_useful_design_rate": 0.4,
        "requires_each_domain_useful": True,
        "missing_useful_domain_slices": missing_domains,
        "below_floor_domain_slices": below_floor,
    }


def _compilation_truthfulness_floor(
    *,
    rollout_posture: str,
    aggregate_rate: float | None,
    by_domain: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if rollout_posture == "research-only":
        return {
            "rollout_posture": rollout_posture,
            "status": "not_required",
            "minimum_aggregate_rate": None,
            "minimum_domain_rate": None,
        }
    if aggregate_rate is None:
        return {
            "rollout_posture": rollout_posture,
            "status": "not_evaluated",
            "reason": "aggregate compilation truthfulness rate is unavailable",
        }
    if rollout_posture == "governed-pilot":
        minimum_aggregate = 60.0
        minimum_domain = 50.0
    else:
        minimum_aggregate = 80.0
        minimum_domain = 70.0
    below_domains = [
        domain
        for domain, row in sorted(by_domain.items())
        if (_float_or_none(row.get("aggregate_compilation_truthfulness_rate")) or 0.0)
        < minimum_domain
    ]
    aggregate_below = aggregate_rate < minimum_aggregate
    return {
        "rollout_posture": rollout_posture,
        "status": "not_met" if aggregate_below or below_domains else "met",
        "minimum_aggregate_rate": minimum_aggregate,
        "minimum_domain_rate": minimum_domain,
        "aggregate_below_floor": aggregate_below,
        "below_floor_domain_slices": below_domains,
    }


def _compilation_truthfulness_output(profile: str) -> Path:
    return (
        COMPILATION_TRUTHFULNESS_FULL_OUTPUT
        if profile == "full"
        else COMPILATION_TRUTHFULNESS_QUICK_OUTPUT
    )


def _domain_coverage_output(profile: str) -> Path:
    return DOMAIN_COVERAGE_FULL_OUTPUT if profile == "full" else DOMAIN_COVERAGE_QUICK_OUTPUT


def _critic_diversity_output(profile: str) -> Path:
    return CRITIC_DIVERSITY_FULL_OUTPUT if profile == "full" else CRITIC_DIVERSITY_QUICK_OUTPUT


def _rate(count: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(count / total, 6)


def _tail(value: object, *, max_chars: int = 4000) -> str:
    if value is None:
        return ""
    text = value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _load_json_if_available(path: Path, *, plan_only: bool) -> Mapping[str, Any] | None:
    if plan_only or not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, Mapping) else None


def _sequence_of_mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_of_mappings(value: object) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): item for key, item in value.items() if isinstance(item, Mapping)}


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
