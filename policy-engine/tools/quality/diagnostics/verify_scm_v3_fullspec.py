#!/usr/bin/env python3
"""Build detailed SCM v3 full-spec verification (DoD 162 + Laws + SL layers)."""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from tools.lib.imports import repo_root_from

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root_from(__file__)))

from tools.lib.runner import run_command

_ALLOWED_COMMAND_PREFIXES: tuple[tuple[str, ...], ...] = (("uv", "run", "python"),)


@dataclass(frozen=True)
class DoDRow:
    id: str
    phase: str
    requirement: str
    status: str
    evidence: list[str]
    severity: str
    notes: str = ""


@dataclass(frozen=True)
class SummaryRow:
    id: str
    status: str
    evidence: list[str]
    severity: str
    notes: str = ""


_PHASE_CHECKS: dict[str, tuple[str, ...]] = {
    "-1": (
        "gate_lint_imports",
        "gate_lint_foundry",
        "gate_schema_ir",
        "gate_schema_fabric",
        "workflow_guards",
    ),
    "0A": ("phase0_quality_integration",),
    "0B": ("phase0_quality_integration",),
    "0C": ("phase0_quality_integration", "phase12_transportability"),
    "0D": ("phase0_quality_integration",),
    "1": ("workflow_guards",),
    "2": ("causal_methods_suite",),
    "3": ("causal_methods_suite",),
    "4": ("causal_methods_suite",),
    "5": ("causal_methods_suite", "ir_contracts_suite"),
    "6": ("phase6_7_jax_ci_backend",),
    "7": ("phase6_7_jax_ci_backend",),
    "8A": ("governance_suite", "phase12_transportability"),
    "8B": ("governance_suite", "phase12_transportability"),
    "9": ("phase9_reconciliation",),
    "10": ("causal_methods_suite", "ir_contracts_suite"),
    "11": ("causal_methods_suite", "ir_contracts_suite"),
    "12": ("phase12_transportability",),
    "13": ("causal_methods_suite",),
    "14": ("causal_methods_suite",),
    "15": ("phase15_parameters",),
}

_LAW_SPECS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("LAW-A (Import Gate)", ("gate_lint_imports", "gate_lint_foundry"), "Import/lint gates."),
    ("LAW-B (Foundry Pure)", ("causal_methods_suite",), "Foundry causal method suites."),
    ("LAW-C (Contract-first snapshots)", ("gate_schema_ir", "gate_schema_fabric"), "Schema gates."),
    ("LAW-D (Reproducibility)", ("causal_methods_suite",), "Deterministic/statistical tests."),
    (
        "LAW-E (Evidence)",
        ("ir_contracts_suite", "phase12_transportability"),
        "Lineage/evidence path.",
    ),
    ("LAW-F (Pure Step)", ("causal_methods_suite",), "Pure-step contracts."),
    ("LAW-G (Graph Closure)", ("phase12_transportability",), "Three-graph transport closure."),
    ("LAW-H (Stable Digest)", ("ir_contracts_suite",), "Canonical serialization/digests."),
    ("LAW-K (Governance)", ("governance_suite",), "Validation pipeline gates."),
    ("LAW-L (Literature-first)", ("phase9_reconciliation",), "Literature prior checks."),
    (
        "LAW-S (Three-Layer)",
        ("phase9_reconciliation", "phase12_transportability"),
        "Layered conflict handling.",
    ),
    ("LAW-T (Transport-aware)", ("phase12_transportability",), "Transportability contract checks."),
    ("LAW-V (SUTVA)", ("phase12_transportability",), "SUTVA-aware transport checks."),
)

_SL_SPECS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "SL-1 (Canonicalization Layer)",
        ("phase0_quality_integration",),
        "Phase 0 canonicalization path.",
    ),
    (
        "SL-2 (Lineage Chain)",
        ("ir_contracts_suite", "phase12_transportability"),
        "End-to-end lineage evidence.",
    ),
    (
        "SL-3 (Method Selection Diagnostics)",
        ("phase9_reconciliation",),
        "Graph reconciliation diagnostics.",
    ),
    (
        "SL-4 (Three-Graph Closure)",
        ("phase12_transportability",),
        "Transportability three-graph closure.",
    ),
    ("SL-5 (Canonical SCM Fixtures)", ("causal_methods_suite",), "Causal fixture-rich suites."),
    (
        "SL-6 (Integration Test Matrix)",
        ("phase12_transportability", "governance_suite"),
        "Cross-layer integration.",
    ),
    ("SL-7 (Operational SLO)", ("phase0_quality_integration",), "Operational quality baseline."),
    ("SL-8 (Data Governance)", ("governance_suite",), "Governance checks."),
)


def _run_base_verification(repo_root: Path, output_dir: Path, timeout_sec: int) -> Path:
    argv = (
        "uv",
        "run",
        "python",
        "tools/quality/diagnostics/verify_scm_v3.py",
        "--profile",
        "full",
        "--output-dir",
        output_dir.as_posix(),
        "--timeout-sec",
        str(int(timeout_sec)),
    )
    proc = run_command(
        argv,
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
        allowed_prefixes=_ALLOWED_COMMAND_PREFIXES,
    )
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    for line in (stdout + "\n" + stderr).splitlines():
        marker = "[verify_scm_v3] wrote:"
        if (
            marker in line
            and "scm_v3_verification_evidence_" in line
            and line.strip().endswith(".json")
        ):
            path = line.split(marker, 1)[1].strip()
            candidate = Path(path)
            if candidate.exists():
                return candidate
    # Fallback: latest timestamped evidence produced by base verifier.
    candidates = sorted(
        glob.glob(str(output_dir / "scm_v3_verification_evidence_*.json")),
        key=lambda item: Path(item).stat().st_mtime,
    )
    if not candidates:
        raise RuntimeError("base verifier did not produce evidence json")
    return Path(candidates[-1])


def _phase_severity(phase: str) -> str:
    token = phase.upper()
    if token == "-1":
        return "P0 blocker"
    if token in {"2", "3", "6", "7", "11", "12", "15"}:
        return "P1 high"
    if token in {"8A", "8B", "9", "10"}:
        return "P2 medium"
    return "P3 low"


def _normalize_phase(raw: str) -> str:
    return raw.replace("−", "-").strip().upper()


def _parse_dod_items(spec_path: Path) -> list[tuple[str, str]]:
    lines = spec_path.read_text(encoding="utf-8").splitlines()
    phase = "UNKNOWN"
    rows: list[tuple[str, str]] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            match_phase = re.search(r"Фаза\s+([−\-]?\d+[A-Za-z]?)", stripped)
            if match_phase:
                phase = _normalize_phase(match_phase.group(1))
            else:
                match_sub = re.search(r"Подфаза\s+(\d+[a-z])", stripped, flags=re.IGNORECASE)
                if match_sub:
                    phase = _normalize_phase(match_sub.group(1))
        match_item = re.match(r"- \[ \] (.+)$", stripped)
        if match_item:
            rows.append((phase, match_item.group(1).strip()))
    return rows


def _required_checks_for_item(phase: str, requirement: str) -> list[str]:
    checks = list(_PHASE_CHECKS.get(phase, ("causal_methods_suite",)))
    lowered = requirement.lower()
    if any(token in lowered for token in ("y0", "causaleffect", "symbolic", "12b")):
        checks.append("phase12b_symbolic_bridge")
    if any(token in lowered for token in ("pcmci", "constraint", "jax ci", "ci backend=jax")):
        checks.append("phase6_7_jax_ci_backend")
    transport_tokens = ("transport", "p*(z)", "s-node", "proxy", "manski", "lineage")
    if any(token in lowered for token in transport_tokens):
        checks.append("phase12_transportability")
    if any(token in lowered for token in ("parameter", "phase 15", "uncertainty_multiplier")):
        checks.append("phase15_parameters")
    return sorted(set(checks))


def _adr_missing(requirement: str, adr_dir: Path) -> str | None:
    matches = re.findall(r"ADR-(\d{4})", requirement, flags=re.IGNORECASE)
    if not matches:
        return None
    for code in matches:
        pattern = f"{code}*.md"
        found = list(adr_dir.glob(pattern))
        if not found:
            return f"ADR-{code} not found in docs/adr"
    return None


def _row_status(
    required_checks: list[str],
    checks_index: dict[str, dict[str, object]],
) -> tuple[str, str]:
    missing = [label for label in required_checks if label not in checks_index]
    if missing:
        return "FAIL", f"Missing check labels: {', '.join(missing)}"
    failed = [
        label
        for label in required_checks
        if str(checks_index[label].get("status", "")).upper() != "PASS"
    ]
    if failed:
        return "FAIL", f"Failed checks: {', '.join(failed)}"
    return "PASS", ""


def _render_matrix_markdown(
    *,
    generated_at: str,
    spec_path: Path,
    base_evidence_path: Path,
    dod_rows: list[DoDRow],
    law_rows: list[SummaryRow],
    sl_rows: list[SummaryRow],
) -> str:
    dod_counts = Counter(row.status for row in dod_rows)
    law_counts = Counter(row.status for row in law_rows)
    sl_counts = Counter(row.status for row in sl_rows)

    lines: list[str] = []
    lines.append("# SCM v3 Fullspec Verification")
    lines.append("")
    lines.append(f"- Generated (UTC): `{generated_at}`")
    lines.append(f"- Spec: `{spec_path}`")
    lines.append(f"- Base verification: `{base_evidence_path}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- DoD PASS: **{dod_counts.get('PASS', 0)} / {len(dod_rows)}**")
    lines.append(f"- Laws PASS: **{law_counts.get('PASS', 0)} / {len(law_rows)}**")
    lines.append(f"- SL PASS: **{sl_counts.get('PASS', 0)} / {len(sl_rows)}**")
    lines.append("")
    lines.append("## DoD Matrix")
    lines.append("")
    lines.append("| ID | Phase | Requirement | Status | Evidence | Severity | Notes |")
    lines.append("|---|---|---|---|---|---|---|")
    for row in dod_rows:
        evidence = "; ".join(row.evidence)
        lines.append(
            f"| {row.id} | {row.phase} | {row.requirement} | {row.status} | "
            f"{evidence} | {row.severity} | {row.notes} |"
        )
    lines.append("")
    lines.append("## Laws")
    lines.append("")
    lines.append("| Law | Status | Evidence | Severity | Notes |")
    lines.append("|---|---|---|---|---|")
    for row in law_rows:
        lines.append(
            f"| {row.id} | {row.status} | {'; '.join(row.evidence)} | "
            f"{row.severity} | {row.notes} |"
        )
    lines.append("")
    lines.append("## SL Layers")
    lines.append("")
    lines.append("| Layer | Status | Evidence | Severity | Notes |")
    lines.append("|---|---|---|---|---|")
    for row in sl_rows:
        lines.append(
            f"| {row.id} | {row.status} | {'; '.join(row.evidence)} | "
            f"{row.severity} | {row.notes} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Detailed SCM v3 full-spec verification.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/reports"),
        help="Directory for generated reports.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=2400,
        help="Per-check timeout passed to base verifier.",
    )
    args = parser.parse_args()

    repo_root = repo_root_from(__file__)
    workspace_root = repo_root.parent
    spec_path = (workspace_root / "scm-implementation-spec-v3.md").resolve()
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    base_evidence_path = _run_base_verification(
        repo_root=repo_root,
        output_dir=output_dir,
        timeout_sec=int(args.timeout_sec),
    )
    base_evidence = json.loads(base_evidence_path.read_text(encoding="utf-8"))
    checks = list(base_evidence.get("checks", []))
    checks_index: dict[str, dict[str, object]] = {}
    for item in checks:
        if isinstance(item, dict):
            label = str(item.get("label", "")).strip()
            if label:
                checks_index[label] = item

    parsed_items = _parse_dod_items(spec_path)
    if len(parsed_items) != 162:
        raise RuntimeError(f"Expected 162 DoD items from spec, got {len(parsed_items)}")

    adr_dir = repo_root / "docs" / "adr"
    dod_rows: list[DoDRow] = []
    for idx, (phase, requirement) in enumerate(parsed_items, start=1):
        required_checks = _required_checks_for_item(phase, requirement)
        status, notes = _row_status(required_checks, checks_index)
        missing_adr = _adr_missing(requirement, adr_dir)
        if missing_adr is not None:
            status = "FAIL"
            notes = f"{notes}; {missing_adr}".strip("; ")
        dod_rows.append(
            DoDRow(
                id=f"DOD-{idx:03d}",
                phase=phase,
                requirement=requirement,
                status=status,
                evidence=required_checks,
                severity=_phase_severity(phase),
                notes=notes,
            )
        )

    law_rows: list[SummaryRow] = []
    for law_id, checks_needed, note in _LAW_SPECS:
        status, notes = _row_status(list(checks_needed), checks_index)
        law_rows.append(
            SummaryRow(
                id=law_id,
                status=status,
                evidence=list(checks_needed),
                severity="P0 blocker" if status != "PASS" else "P3 low",
                notes=notes or note,
            )
        )

    sl_rows: list[SummaryRow] = []
    for layer_id, checks_needed, note in _SL_SPECS:
        status, notes = _row_status(list(checks_needed), checks_index)
        sl_rows.append(
            SummaryRow(
                id=layer_id,
                status=status,
                evidence=list(checks_needed),
                severity="P1 high" if status != "PASS" else "P3 low",
                notes=notes or note,
            )
        )

    generated_at = datetime.now(UTC).isoformat()
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    dod_counts = Counter(row.status for row in dod_rows)
    law_counts = Counter(row.status for row in law_rows)
    sl_counts = Counter(row.status for row in sl_rows)

    summary = {
        "dod_total": len(dod_rows),
        "dod_status_counts": dict(sorted(dod_counts.items())),
        "laws_total": len(law_rows),
        "laws_status_counts": dict(sorted(law_counts.items())),
        "sl_total": len(sl_rows),
        "sl_status_counts": dict(sorted(sl_counts.items())),
        "all_pass": (
            dod_counts.get("PASS", 0) == len(dod_rows)
            and law_counts.get("PASS", 0) == len(law_rows)
            and sl_counts.get("PASS", 0) == len(sl_rows)
        ),
    }

    evidence = {
        "generated_at_utc": generated_at,
        "spec_path": str(spec_path),
        "workspace_root": str(repo_root),
        "base_verification_evidence": str(base_evidence_path),
        "checks_index": checks_index,
        "dod_rows": [asdict(row) for row in dod_rows],
        "law_rows": [asdict(row) for row in law_rows],
        "sl_rows": [asdict(row) for row in sl_rows],
        "summary": summary,
    }

    matrix_text = _render_matrix_markdown(
        generated_at=generated_at,
        spec_path=spec_path,
        base_evidence_path=base_evidence_path,
        dod_rows=dod_rows,
        law_rows=law_rows,
        sl_rows=sl_rows,
    )

    evidence_path = output_dir / f"scm_v3_fullspec_evidence_{stamp}.json"
    matrix_path = output_dir / f"scm_v3_fullspec_matrix_{stamp}.md"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    matrix_path.write_text(matrix_text, encoding="utf-8")

    canonical_evidence = output_dir / "scm_v3_verification_evidence.json"
    canonical_matrix = output_dir / "scm_v3_verification_matrix.md"
    canonical_evidence.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    canonical_matrix.write_text(matrix_text, encoding="utf-8")

    print(f"[verify_scm_v3_fullspec] wrote: {evidence_path}")
    print(f"[verify_scm_v3_fullspec] wrote: {matrix_path}")
    print(f"[verify_scm_v3_fullspec] synced: {canonical_evidence}")
    print(f"[verify_scm_v3_fullspec] synced: {canonical_matrix}")
    print(f"[verify_scm_v3_fullspec] summary: {summary}")

    if not bool(summary["all_pass"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
