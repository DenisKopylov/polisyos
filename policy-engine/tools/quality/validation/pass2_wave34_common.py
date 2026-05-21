#!/usr/bin/env python3
"""Shared helpers for Policy Design Case Wave 34 Pass 2 diagnostics."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json, atomic_write_text
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

WAVE_ID = "34"
DEFAULT_WAVE33_DIR = Path("_build/policy-design-case/rebaseline/wave-33")
DEFAULT_OUTPUT_ROOT = Path("_build/diagnostics")
BACKLOG_FRAGMENT_DIR = Path("pass2/backlog_fragments")

REQUIRED_WAVE33_ARTIFACTS: tuple[str, ...] = (
    "real_domain_baseline.json",
    "research_real_domain_matrix.json",
    "policy_design_case_sample.json",
    "quality_scorecard.json",
    "readiness.json",
    "production_data_evidence.json",
    "claim_argument.json",
    "policy_grounding_matrix.json",
)

OPTIONAL_WAVE33_ARTIFACTS: tuple[str, ...] = (
    "coverage.json",
)

COMMON_QUALITY_EVIDENCE_FILES: tuple[str, ...] = (
    "attestation_records.json",
    "canary_performance_budget.json",
    "continuous_governance_reissue_report.json",
    "continuous_governance_stale_report.json",
    "continuous_governance_supersede_report.json",
    "continuous_governance_withdraw_report.json",
    "decision_artifact_quality.json",
    "drift_explanation.json",
    "evidence_provenance_manifest.json",
    "fabric_retrieval_trace.json",
    "foundry_method_report.json",
    "human_review_calibration_report.json",
    "normative_evidence.json",
    "policy_design_case.json",
    "production_data_quality.json",
    "provider_model_quality_ledger.json",
    "public_export_bundle.json",
    "quality_scorecard.json",
    "replay_manifest.json",
    "semantic_binding_ledger.json",
)


class Pass2Wave34InputError(ValueError):
    """Raised when required Wave 33 input evidence is absent or unreadable."""


def load_wave33_context(
    *,
    repo_root: Path = REPO_ROOT,
    wave33_dir: Path = DEFAULT_WAVE33_DIR,
) -> dict[str, Any]:
    """Load Wave 33 evidence and return normalized context for diagnostics."""

    repo_root = repo_root.resolve()
    wave33_path = resolve_path(repo_root, wave33_dir)
    wave_files = {
        filename: load_json(wave33_path / filename)
        for filename in REQUIRED_WAVE33_ARTIFACTS
    }
    for filename in OPTIONAL_WAVE33_ARTIFACTS:
        wave_files[filename] = load_optional_json(wave33_path / filename)

    baseline = expect_mapping(
        wave_files["real_domain_baseline.json"],
        "real_domain_baseline",
    )
    research_case = expect_mapping(
        baseline.get("research_profile_case"),
        "real_domain_baseline.research_profile_case",
    )
    bundle_rel = str(research_case.get("bundle_path") or "")
    if not bundle_rel:
        raise Pass2Wave34InputError(
            "Wave 33 baseline is missing research_profile_case.bundle_path."
        )
    bundle_path = resolve_path(repo_root, Path(bundle_rel), must_exist=False)
    quality_dir = bundle_path / "quality_evidence"
    quality_files = {
        filename: load_optional_json(quality_dir / filename)
        for filename in COMMON_QUALITY_EVIDENCE_FILES
    }
    scorecard = expect_mapping(
        wave_files["quality_scorecard.json"],
        "quality_scorecard",
        required=False,
    )
    claim_argument = expect_mapping(
        wave_files["claim_argument.json"],
        "claim_argument",
        required=False,
    )
    claim = expect_mapping(
        claim_argument.get("claim"),
        "claim_argument.claim",
        required=False,
    )
    generated_at = str(
        baseline.get("generated_at")
        or research_case.get("generated_at")
        or "2026-05-18T00:00:00+00:00"
    )
    source_artifacts = _source_artifacts(
        repo_root=repo_root,
        wave33_path=wave33_path,
        bundle_path=bundle_path,
        quality_dir=quality_dir,
    )
    return {
        "repo_root": repo_root,
        "wave33_dir": wave33_path,
        "bundle_path": bundle_path,
        "generated_at": generated_at,
        "baseline": baseline,
        "research_case": research_case,
        "wave_files": wave_files,
        "quality_files": quality_files,
        "source_artifacts": source_artifacts,
        "wave33": {
            "run_id": research_case.get("run_id"),
            "job_id": research_case.get("job_id"),
            "case_id": research_case.get("case_id"),
            "lane_id": research_case.get("lane_id"),
            "bundle_path": rel_path(bundle_path, repo_root),
            "matrix_status": research_case.get("matrix_status"),
            "scorecard_status": research_case.get("scorecard_status")
            or scorecard.get("quality_status"),
            "approval_state": scorecard.get("approval_state"),
            "failure_code": research_case.get("failure_code"),
            "claim_argument_status": claim.get("status"),
            "scorecard_blocking_code_count": len(blocking_codes(scorecard)),
        },
    }


def canonical_diagnostic(
    *,
    context: Mapping[str, Any],
    spec: Mapping[str, Any],
    tool_name: str,
    schema_version: str,
    phase: str,
    verdict: str,
    acceptance_gate_status: str,
    findings: Sequence[Mapping[str, Any]],
    evidence: Mapping[str, Any] | None,
    recommended_gate: str,
    backlog_summary: str,
    recommended_remediation_id: str | None = None,
) -> dict[str, Any]:
    """Build a normalized Pass 2 detail JSON payload."""

    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "tool": tool_name,
        "generated_at": context["generated_at"],
        "wave": WAVE_ID,
        "phase": phase,
        "pdd_id": spec["pdd_id"],
        "title": spec["title"],
        "question": spec["question"],
        "diagnostic_status": "diagnosed",
        "acceptance_gate_status": acceptance_gate_status,
        "verdict": verdict,
        "wave33": context["wave33"],
        "source_artifacts": context["source_artifacts"],
        "findings": [canonical_finding(finding) for finding in findings],
        "recommended_gate": recommended_gate,
        "backlog_summary": backlog_summary,
    }
    if evidence is not None:
        payload["evidence"] = dict(evidence)
    if recommended_remediation_id:
        payload["recommended_remediation_id"] = recommended_remediation_id
    return payload


def canonical_finding(finding: Mapping[str, Any]) -> dict[str, Any]:
    code = str(
        finding.get("code")
        or finding.get("id")
        or _slugify(str(finding.get("title") or finding.get("summary") or "finding"))
    )
    summary = str(
        finding.get("summary") or finding.get("title") or finding.get("finding") or code
    )
    payload: dict[str, Any] = {
        "code": code,
        "severity": str(finding.get("severity") or "blocker"),
        "summary": summary,
    }
    if "evidence" in finding:
        payload["evidence"] = finding["evidence"]
    if "requirement" in finding:
        payload["requirement"] = finding["requirement"]
    return payload


def write_phase_outputs(
    *,
    diagnostics: Mapping[str, Mapping[str, Any]],
    specs: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
    output_root: Path,
    phase: str,
    phase_title: str,
    phase_file_stem: str,
    index_schema_version: str,
    tool_name: str,
    context: Mapping[str, Any],
) -> tuple[dict[str, Any], list[Path]]:
    """Write detail JSON, detail MD, summaries, fragments, and phase index."""

    repo_root = repo_root.resolve()
    output_dir = resolve_path(repo_root, output_root, must_exist=False)
    written: list[Path] = []
    output_refs: dict[str, str] = {}
    phase_rows: dict[str, dict[str, Any]] = {}

    for pdd_id, diagnostic in diagnostics.items():
        spec = specs[pdd_id]
        slug = str(spec["slug"])
        pdd_dir = output_dir / pdd_id.lower()
        json_path = pdd_dir / f"{slug}.json"
        md_path = pdd_dir / f"{slug}.md"
        summary_path = pdd_dir / "summary.md"
        fragment_path = output_dir / BACKLOG_FRAGMENT_DIR / f"{pdd_id.lower()}.md"

        atomic_write_json(json_path, diagnostic)
        atomic_write_text(md_path, render_detail_markdown(diagnostic))
        atomic_write_text(summary_path, render_summary_markdown(diagnostic, slug))
        atomic_write_text(fragment_path, render_backlog_fragment(diagnostic, slug))
        written.extend([json_path, md_path, summary_path, fragment_path])

        output_refs[f"{pdd_id}:json"] = rel_path(json_path, repo_root)
        output_refs[f"{pdd_id}:detail"] = rel_path(md_path, repo_root)
        output_refs[f"{pdd_id}:summary"] = rel_path(summary_path, repo_root)
        output_refs[f"{pdd_id}:fragment"] = rel_path(fragment_path, repo_root)
        phase_rows[pdd_id] = {
            "pdd_id": pdd_id,
            "diagnostic_status": diagnostic["diagnostic_status"],
            "acceptance_gate_status": diagnostic["acceptance_gate_status"],
            "verdict": diagnostic["verdict"],
            "artifact": rel_path(json_path, repo_root),
            "detail": rel_path(md_path, repo_root),
            "summary": rel_path(summary_path, repo_root),
            "backlog_fragment": rel_path(fragment_path, repo_root),
        }
        if diagnostic.get("recommended_remediation_id"):
            phase_rows[pdd_id]["recommended_remediation_id"] = diagnostic[
                "recommended_remediation_id"
            ]

    payload = {
        "schema_version": index_schema_version,
        "tool": tool_name,
        "generated_at": context["generated_at"],
        "wave": WAVE_ID,
        "phase": phase,
        "status": "diagnosed",
        "runtime_acceptance_status": aggregate_acceptance(diagnostics.values()),
        "repo_root": str(repo_root),
        "wave33": context["wave33"],
        "summary": {
            "pdd_count": len(diagnostics),
            "diagnosed_count": len(diagnostics),
            "failed_or_blocking_gate_count": sum(
                1
                for diagnostic in diagnostics.values()
                if gate_is_failed_or_blocked(str(diagnostic["acceptance_gate_status"]))
            ),
            "not_triggered_count": sum(
                1
                for diagnostic in diagnostics.values()
                if str(diagnostic["acceptance_gate_status"]).startswith(
                    "not_triggered"
                )
            ),
            "backlog_fragment_count": len(diagnostics),
        },
        "diagnostics": phase_rows,
        "output": output_refs,
    }
    index_path = output_dir / "pass2" / f"{phase_file_stem}.json"
    index_md_path = output_dir / "pass2" / f"{phase_file_stem}.md"
    atomic_write_json(index_path, payload)
    atomic_write_text(index_md_path, render_phase_markdown(payload, phase_title))
    written.extend([index_path, index_md_path])
    return payload, written


def render_detail_markdown(diagnostic: Mapping[str, Any]) -> str:
    findings = as_list(diagnostic.get("findings"))
    lines = [
        f"# {diagnostic['pdd_id']} Diagnostic: {diagnostic['title']}",
        "",
        f"Generated: {diagnostic['generated_at']}",
        "",
        f"Wave: `{diagnostic['wave']}`",
        "",
        f"Phase: `{diagnostic['phase']}`",
        "",
        f"Diagnostic status: `{diagnostic['diagnostic_status']}`",
        "",
        f"Acceptance gate status: `{diagnostic['acceptance_gate_status']}`",
        "",
        f"Verdict: `{diagnostic['verdict']}`",
        "",
        "## Question",
        "",
        str(diagnostic["question"]),
        "",
        "## Wave 33 Evidence",
        "",
        table(
            ("Field", "Observed value"),
            [
                ("run_id", string(diagnostic["wave33"].get("run_id"))),
                ("job_id", string(diagnostic["wave33"].get("job_id"))),
                ("case_id", string(diagnostic["wave33"].get("case_id"))),
                ("lane_id", string(diagnostic["wave33"].get("lane_id"))),
                ("bundle_path", code(diagnostic["wave33"].get("bundle_path"))),
                (
                    "scorecard_status",
                    string(diagnostic["wave33"].get("scorecard_status")),
                ),
                (
                    "approval_state",
                    string(diagnostic["wave33"].get("approval_state")),
                ),
            ],
        ),
        "",
        "## Findings",
        "",
    ]
    if findings:
        for finding in findings:
            if isinstance(finding, Mapping):
                lines.append(
                    "- `{code}` ({severity}): {summary}".format(
                        code=finding.get("code"),
                        severity=finding.get("severity"),
                        summary=finding.get("summary"),
                    )
                )
                if finding.get("evidence") is not None:
                    lines.append(f"  Evidence: {string(finding.get('evidence'))}")
    else:
        lines.append("- No active Wave 33 violation detected.")

    evidence = expect_mapping(diagnostic.get("evidence"), "evidence", required=False)
    if evidence:
        lines.extend(["", "## Diagnostic Evidence", ""])
        for key, value in evidence.items():
            lines.append(f"### {key}")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(value, indent=2, ensure_ascii=False))
            lines.append("```")
            lines.append("")

    lines.extend(
        [
            "## Recommended Gate",
            "",
            str(diagnostic["recommended_gate"]),
            "",
            "## Backlog Summary",
            "",
            str(diagnostic["backlog_summary"]),
            "",
        ]
    )
    if diagnostic.get("recommended_remediation_id"):
        lines.extend(
            [
                "## Recommended Remediation Id",
                "",
                str(diagnostic["recommended_remediation_id"]),
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def render_summary_markdown(diagnostic: Mapping[str, Any], slug: str) -> str:
    pdd_id = str(diagnostic["pdd_id"])
    findings = as_list(diagnostic.get("findings"))
    lines = [
        f"# {pdd_id} Summary",
        "",
        f"Diagnostic status: `{diagnostic['diagnostic_status']}`",
        "",
        f"Acceptance gate status: `{diagnostic['acceptance_gate_status']}`",
        "",
        f"Verdict: `{diagnostic['verdict']}`",
        "",
        str(diagnostic["backlog_summary"]),
        "",
        "## Strongest Findings",
        "",
    ]
    if findings:
        for index, finding in enumerate(findings, start=1):
            if isinstance(finding, Mapping):
                lines.append(
                    f"{index}. `{finding.get('code')}` - {finding.get('summary')}"
                )
    else:
        lines.append("1. No active violation detected in Wave 33 evidence.")
    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            f"- `_build/diagnostics/{pdd_id.lower()}/{slug}.md`",
            f"- `_build/diagnostics/{pdd_id.lower()}/{slug}.json`",
            f"- `_build/diagnostics/pass2/backlog_fragments/{pdd_id.lower()}.md`",
            "",
        ]
    )
    return "\n".join(lines)


def render_backlog_fragment(diagnostic: Mapping[str, Any], slug: str) -> str:
    pdd_id = str(diagnostic["pdd_id"])
    findings = as_list(diagnostic.get("findings"))
    lines = [
        f"### {pdd_id} - {diagnostic['title']}",
        "",
        f"- Wave: {diagnostic['wave']}",
        f"- Phase: {diagnostic['phase']}",
        f"- Diagnostic status: `{diagnostic['diagnostic_status']}`",
        f"- Acceptance gate status: `{diagnostic['acceptance_gate_status']}`",
        f"- Verdict: `{diagnostic['verdict']}`",
        f"- Finding count: {len(findings)}",
        f"- Detail artifact: `_build/diagnostics/{pdd_id.lower()}/{slug}.md`",
        f"- Machine artifact: `_build/diagnostics/{pdd_id.lower()}/{slug}.json`",
        "",
        str(diagnostic["backlog_summary"]),
        "",
    ]
    if findings:
        lines.extend(["Finding seeds:", ""])
        for finding in findings:
            if isinstance(finding, Mapping):
                lines.append(f"- `{finding.get('code')}`: {finding.get('summary')}")
        lines.append("")
    return "\n".join(lines)


def render_phase_markdown(payload: Mapping[str, Any], title: str) -> str:
    diagnostics = expect_mapping(payload.get("diagnostics"), "diagnostics")
    rows = [
        (
            pdd_id,
            code(item.get("diagnostic_status")),
            code(item.get("acceptance_gate_status")),
            code(item.get("verdict")),
        )
        for pdd_id, item in diagnostics.items()
        if isinstance(item, Mapping)
    ]
    return "\n".join(
        [
            f"# {title}",
            "",
            f"Generated: {payload['generated_at']}",
            "",
            f"Status: `{payload['status']}`",
            "",
            f"Runtime acceptance status: `{payload['runtime_acceptance_status']}`",
            "",
            table(("PDD", "Diagnostic", "Gate", "Verdict"), rows),
            "",
        ]
    )


def aggregate_acceptance(diagnostics: Sequence[Mapping[str, Any]]) -> str:
    statuses = [str(item.get("acceptance_gate_status") or "") for item in diagnostics]
    if any(gate_is_failed_or_blocked(status) for status in statuses):
        return "failed"
    if statuses and all(status.startswith("not_triggered") for status in statuses):
        return "not_triggered"
    return "passed"


def gate_is_failed_or_blocked(status: str) -> bool:
    return status.startswith("failed") or status == "blocked"


def blocking_codes(scorecard: Mapping[str, Any]) -> list[str]:
    rows = as_list(scorecard.get("blocking_quality_failures")) or as_list(
        scorecard.get("quality_gates")
    )
    codes: list[str] = []
    for row in rows:
        if isinstance(row, Mapping) and (
            row.get("blocking") is True
            or row.get("status") == "fail"
            or row.get("severity") in {"blocker", "critical"}
        ):
            if row.get("code"):
                codes.append(str(row["code"]))
    return codes


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise Pass2Wave34InputError(f"Required Wave 33 artifact not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Pass2Wave34InputError(
            f"Wave 33 artifact is invalid JSON: {path}: {exc.msg}"
        ) from exc
    if not isinstance(payload, dict):
        raise Pass2Wave34InputError(f"Wave 33 artifact must be a JSON object: {path}")
    return payload


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def expect_mapping(
    value: Any,
    label: str,
    *,
    required: bool = True,
) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if required:
        raise Pass2Wave34InputError(f"{label} must be a JSON object.")
    return {}


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def resolve_path(repo_root: Path, path: Path, *, must_exist: bool = True) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    candidate = candidate.resolve(strict=False)
    if must_exist and not candidate.exists():
        raise Pass2Wave34InputError(f"Path not found: {candidate}")
    return candidate


def rel_path(path: Path, base: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(base.resolve()).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(string(cell) for cell in row) + " |")
    return "\n".join(lines)


def code(value: object) -> str:
    return f"`{string(value)}`"


def string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).replace("\n", " ")


def _source_artifacts(
    *,
    repo_root: Path,
    wave33_path: Path,
    bundle_path: Path,
    quality_dir: Path,
) -> dict[str, str]:
    artifacts = {
        filename.removesuffix(".json"): rel_path(wave33_path / filename, repo_root)
        for filename in (*REQUIRED_WAVE33_ARTIFACTS, *OPTIONAL_WAVE33_ARTIFACTS)
        if (wave33_path / filename).exists()
    }
    artifacts["bundle"] = rel_path(bundle_path, repo_root)
    for filename in COMMON_QUALITY_EVIDENCE_FILES:
        path = quality_dir / filename
        if path.exists():
            key = f"quality_evidence.{filename.removesuffix('.json')}"
            artifacts[key] = rel_path(path, repo_root)
    timeline = bundle_path / "timeline.json"
    if timeline.exists():
        artifacts["runtime_timeline"] = rel_path(timeline, repo_root)
    return artifacts


def _slugify(value: str) -> str:
    lowered = value.lower()
    return re.sub(r"[^a-z0-9]+", "_", lowered).strip("_") or "finding"
