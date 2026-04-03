#!/usr/bin/env python3
"""Run the Phase 7 platform acceptance audit for the policy-engine workspace."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

PRODUCT_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = PRODUCT_ROOT.parent
if str(PRODUCT_ROOT) not in sys.path:
    sys.path.insert(0, str(PRODUCT_ROOT))

from tools.ci.check_workflow_policy import collect_findings
from tools.workspace._common import NODE_BASELINE, PYTHON_BASELINE, UV_BASELINE


@dataclass(frozen=True, slots=True)
class AuditCheck:
    """One acceptance-audit check result."""

    check_id: str
    title: str
    kind: str
    status: str
    detail: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ManualEvidenceEntry:
    """Optional structured evidence for one manual closeout item."""

    status: bool
    notes: str = ""
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AuditReport:
    """Structured acceptance-audit report."""

    checks: tuple[AuditCheck, ...]

    @property
    def blockers(self) -> tuple[AuditCheck, ...]:
        return tuple(check for check in self.checks if check.status == "fail")

    @property
    def pending(self) -> tuple[AuditCheck, ...]:
        return tuple(check for check in self.checks if check.status == "pending")


MANUAL_CHECKS: dict[str, tuple[str, str]] = {
    "clean_machine_bootstrap": (
        "Clean-machine bootstrap rehearsal",
        "Re-clone the repo on a clean machine and run ./scripts/bootstrap -> ./scripts/doctor -> ./scripts/verify.",
    ),
    "backend_walkthrough": (
        "Backend contributor walkthrough",
        "Follow docs/how-to/onboarding/backend-engineer.md on a representative contributor path.",
    ),
    "frontend_walkthrough": (
        "Frontend contributor walkthrough",
        "Follow docs/how-to/onboarding/frontend-engineer.md on a representative contributor path.",
    ),
    "platform_walkthrough": (
        "Platform contributor walkthrough",
        "Follow docs/how-to/onboarding/platform-ops-engineer.md and exercise bootstrap/doctor/verify surfaces.",
    ),
    "release_dry_run": (
        "Release rehearsal or dry run",
        "Exercise the local release-note/version/canary path or the GitHub release workflow dry run.",
    ),
    "incident_tabletop": (
        "Incident / runbook tabletop",
        "Walk one critical operational path from alert to runbook to postmortem follow-up.",
    ),
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the PolicyOS Phase 7 platform acceptance audit.",
    )
    parser.add_argument(
        "--manual-evidence",
        type=Path,
        help="Optional TOML file with [manual] boolean statuses for manual closeout rehearsals.",
    )
    parser.add_argument(
        "--require-manual-evidence",
        action="store_true",
        help="Fail when any manual rehearsal is missing or marked false.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="Optional markdown summary output path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _path_exists(path: Path) -> bool:
    return path.exists()


def _contains(path: Path, *needles: str) -> bool:
    text = _read_text(path)
    return all(needle in text for needle in needles)


def _result(
    check_id: str,
    title: str,
    *,
    kind: str,
    ok: bool,
    detail: str,
    evidence: tuple[Path, ...],
) -> AuditCheck:
    return AuditCheck(
        check_id=check_id,
        title=title,
        kind=kind,
        status="pass" if ok else "fail",
        detail=detail,
        evidence=tuple(str(path) for path in evidence),
    )


def _toolchain_consistency() -> AuditCheck:
    python_file = PRODUCT_ROOT / ".python-version"
    node_file = PRODUCT_ROOT / ".nvmrc"
    env_matrix = PRODUCT_ROOT / "docs" / "reference" / "environment-matrix.md"
    python_action = WORKSPACE_ROOT / ".github" / "actions" / "setup-policy-engine-python" / "action.yml"
    node_action = WORKSPACE_ROOT / ".github" / "actions" / "setup-runtime-dashboard" / "action.yml"

    issues: list[str] = []
    if python_file.read_text(encoding="utf-8").strip() != PYTHON_BASELINE:
        issues.append(f"{python_file} is not pinned to Python {PYTHON_BASELINE}.")
    if node_file.read_text(encoding="utf-8").strip() != NODE_BASELINE:
        issues.append(f"{node_file} is not pinned to Node {NODE_BASELINE}.")
    if not _contains(env_matrix, f"| {PYTHON_BASELINE}.x | Supported |", f"| {NODE_BASELINE}.x | Supported |"):
        issues.append("docs/reference/environment-matrix.md is missing the canonical Python/Node baseline rows.")
    if not _contains(python_action, f'default: "{PYTHON_BASELINE}"', f'version: "{UV_BASELINE}"'):
        issues.append("setup-policy-engine-python action defaults drift from the pinned Python/uv baseline.")
    if not _contains(node_action, f'default: "{NODE_BASELINE}"'):
        issues.append("setup-runtime-dashboard action default drifts from the pinned Node baseline.")

    detail = (
        f"Python {PYTHON_BASELINE}.x, Node {NODE_BASELINE}.x, and uv {UV_BASELINE} stay aligned across local docs and composite actions."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "toolchain-consistency",
        "Toolchain consistency",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(python_file, node_file, env_matrix, python_action, node_action),
    )


def _repo_root_coherence() -> AuditCheck:
    root_readme = WORKSPACE_ROOT / "README.md"
    product_readme = PRODUCT_ROOT / "README.md"
    adr = PRODUCT_ROOT / "docs" / "adr" / "0096-canonical-product-root-and-workspace-boundary.md"
    issues: list[str] = []
    if not _contains(root_readme, "workspace gateway", "policy-engine/"):
        issues.append("Repository root README no longer points contributors at policy-engine/ as the canonical product root.")
    if not _contains(product_readme, "Canonical product root", "./scripts/bootstrap"):
        issues.append("policy-engine/README.md no longer advertises the canonical contributor entry path.")
    if not _path_exists(adr):
        issues.append("ADR-0096 is missing.")
    detail = (
        "Root and product READMEs still agree on the workspace gateway vs canonical product-root split."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "repo-root-coherence",
        "Repo root coherence",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(root_readme, product_readme, adr),
    )


def _ownership_coverage() -> AuditCheck:
    codeowners = WORKSPACE_ROOT / ".github" / "CODEOWNERS"
    ownership_doc = PRODUCT_ROOT / "docs" / "reference" / "ownership.md"
    quality_gates = PRODUCT_ROOT / "docs" / "reference" / "quality-gates.md"
    issues: list[str] = []
    if not _path_exists(codeowners):
        issues.append(".github/CODEOWNERS is missing.")
    if not _path_exists(ownership_doc):
        issues.append("docs/reference/ownership.md is missing.")
    quality_gates_text = _read_text(quality_gates).lower()
    if "owned areas touched by the pr" not in quality_gates_text or "migration owner" not in quality_gates_text:
        issues.append("docs/reference/quality-gates.md no longer carries ownership metadata expectations.")
    detail = (
        "Ownership is covered in both repo control plane and product docs."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "ownership-coverage",
        "Ownership coverage",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(codeowners, ownership_doc, quality_gates),
    )


def _merge_governance() -> AuditCheck:
    ruleset = WORKSPACE_ROOT / ".github" / "repository-rulesets" / "main.yml"
    merge_doc = PRODUCT_ROOT / "docs" / "reference" / "merge-governance.md"
    pr_template = WORKSPACE_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
    labels = WORKSPACE_ROOT / ".github" / "labels.yml"
    ratchet_tool = PRODUCT_ROOT / "tools" / "ci" / "check_phase7_ratchet.py"
    fast_workflow = WORKSPACE_ROOT / ".github" / "workflows" / "abi.yml"
    issues: list[str] = []
    if not _path_exists(ruleset):
        issues.append("Repo-tracked default-branch ruleset is missing.")
    if not _path_exists(merge_doc):
        issues.append("docs/reference/merge-governance.md is missing.")
    if not _path_exists(pr_template):
        issues.append("Root PR template is missing.")
    if not _path_exists(labels):
        issues.append("Root labels taxonomy is missing.")
    if _path_exists(pr_template) and not _contains(pr_template, "This PR introduces a new subsystem or major surface."):
        issues.append("Root PR template no longer carries the Phase 7 ratchet declaration checkbox.")
    if not _path_exists(ratchet_tool):
        issues.append("Phase 7 ratchet enforcement tool is missing.")
    if not _contains(fast_workflow, "check_phase7_ratchet.py"):
        issues.append("Fast PR workflow no longer enforces the Phase 7 ratchet policy.")
    detail = (
        "Ruleset, merge-governance doc, PR template, labels taxonomy, and ratchet enforcement are all repo-tracked."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "merge-governance",
        "Repository ruleset and merge governance",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(ruleset, merge_doc, pr_template, labels, ratchet_tool, fast_workflow),
    )


def _required_checks() -> AuditCheck:
    ruleset = WORKSPACE_ROOT / ".github" / "repository-rulesets" / "main.yml"
    workflows_doc = PRODUCT_ROOT / "docs" / "how-to" / "operate-ci-cd-platform.md"
    abi_workflow = WORKSPACE_ROOT / ".github" / "workflows" / "abi.yml"
    ci_workflow = WORKSPACE_ROOT / ".github" / "workflows" / "ci.yml"
    issues: list[str] = []
    if not _contains(ruleset, "- Fast PR / Gate", "- Standard PR / Gate"):
        issues.append("Repository ruleset no longer requires the canonical Fast/Standard gate names.")
    if not _contains(workflows_doc, "Fast PR / Gate", "Standard PR / Gate"):
        issues.append("CI/CD operating model doc no longer documents the canonical required gates.")
    if not _path_exists(abi_workflow) or not _path_exists(ci_workflow):
        issues.append("One of the canonical PR workflows is missing.")
    detail = (
        "Required PR gates stay consistent between ruleset, docs, and workflow files."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "required-checks",
        "Required checks",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(ruleset, workflows_doc, abi_workflow, ci_workflow),
    )


def _release_path() -> AuditCheck:
    release_workflow = WORKSPACE_ROOT / ".github" / "workflows" / "release.yml"
    release_doc = PRODUCT_ROOT / "docs" / "how-to" / "release-policy.md"
    fragments_readme = PRODUCT_ROOT / "release-fragments" / "README.md"
    fragments_template = PRODUCT_ROOT / "release-fragments" / "template.toml"
    release_tools = (
        PRODUCT_ROOT / "tools" / "release" / "stage_release_snapshot.py",
        PRODUCT_ROOT / "tools" / "release" / "build_release_notes.py",
        PRODUCT_ROOT / "tools" / "release" / "run_release_canary.py",
    )
    issues: list[str] = []
    if not _path_exists(release_workflow):
        issues.append("Release workflow is missing.")
    if not _path_exists(release_doc):
        issues.append("Release policy doc is missing.")
    if not _path_exists(fragments_readme) or not _path_exists(fragments_template):
        issues.append("Release fragment guidance is incomplete.")
    for tool in release_tools:
        if not _path_exists(tool):
            issues.append(f"Release helper is missing: {tool.name}.")
    detail = (
        "Release workflow, release policy, immutable fragment snapshots, and release helpers are wired together."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "release-path",
        "Release path",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(release_workflow, release_doc, fragments_readme, fragments_template, *release_tools),
    )


def _runbook_presence() -> AuditCheck:
    runbook_root = PRODUCT_ROOT / "docs" / "runbooks"
    required = (
        runbook_root / "index.md",
        runbook_root / "dependency-upgrade-regression.md",
        runbook_root / "runtime-api-outage.md",
        runbook_root / "broken-contract-generation.md",
        runbook_root / "artifact-signing-sbom-failure.md",
        runbook_root / "canary-rollback-or-promotion-failure.md",
        runbook_root / "replay-or-restore.md",
        runbook_root / "retained-artifact-recovery.md",
        runbook_root / "docs-publication-failure.md",
        runbook_root / "benchmark-regression-triage.md",
    )
    missing = [str(path) for path in required if not _path_exists(path)]
    detail = (
        "Core incident, restore, docs, release, and benchmark runbooks are present."
        if not missing
        else f"Missing runbook docs: {', '.join(missing)}"
    )
    return _result(
        "runbook-presence",
        "Runbook presence",
        kind="automated",
        ok=not missing,
        detail=detail,
        evidence=required,
    )


def _bootstrap_and_doctor() -> AuditCheck:
    scripts = (
        PRODUCT_ROOT / "scripts" / "bootstrap",
        PRODUCT_ROOT / "scripts" / "doctor",
        PRODUCT_ROOT / "scripts" / "verify",
        PRODUCT_ROOT / "scripts" / "ci-parity",
        PRODUCT_ROOT / "scripts" / "acceptance-audit",
    )
    docs = (
        PRODUCT_ROOT / "tools" / "workspace" / "README.md",
        PRODUCT_ROOT / "docs" / "how-to" / "install.md",
        PRODUCT_ROOT / "docs" / "reference" / "contributor-start-here.md",
        PRODUCT_ROOT / "docs" / "how-to" / "onboarding" / "index.md",
    )
    missing = [str(path) for path in (*scripts, *docs) if not _path_exists(path)]
    detail = (
        "Bootstrap, doctor, verify, ci-parity, acceptance-audit, and the contributor journey docs are in place."
        if not missing
        else f"Missing workspace command or contributor docs: {', '.join(missing)}"
    )
    return _result(
        "bootstrap-doctor-quality",
        "Bootstrap and doctor quality",
        kind="automated",
        ok=not missing,
        detail=detail,
        evidence=(*scripts, *docs),
    )


def _dependency_freshness() -> AuditCheck:
    renovate = WORKSPACE_ROOT / "renovate.json"
    nightly = WORKSPACE_ROOT / ".github" / "workflows" / "frontend-nightly.yml"
    freshness_tool = PRODUCT_ROOT / "tools" / "ci" / "check_action_freshness.py"
    workflows_doc = PRODUCT_ROOT / "docs" / "how-to" / "operate-ci-cd-platform.md"
    issues: list[str] = []
    if not _path_exists(renovate):
        issues.append("renovate.json is missing.")
    if not _path_exists(nightly):
        issues.append("Nightly workflow is missing.")
    if not _path_exists(freshness_tool):
        issues.append("Action freshness audit tooling is missing.")
    if not _contains(workflows_doc, "dependency review", "Scheduled action freshness audit"):
        issues.append("CI/CD operating model doc no longer captures dependency freshness governance.")
    detail = (
        "Dependency freshness is covered by Renovate, nightly workflow audits, and repo-tracked docs."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "dependency-freshness",
        "Dependency freshness process",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(renovate, nightly, freshness_tool, workflows_doc),
    )


def _workflow_identity_hardening() -> AuditCheck:
    workflow_doc = PRODUCT_ROOT / "docs" / "how-to" / "operate-ci-cd-platform.md"
    findings = collect_findings(WORKSPACE_ROOT)
    issues: list[str] = []
    if findings:
        issues.extend(f"{finding.path.relative_to(WORKSPACE_ROOT)}: {finding.message}" for finding in findings)
    if not _contains(workflow_doc, "GitHub-hosted runners are the default trust model", "OIDC"):
        issues.append("CI/CD operating model doc no longer documents the runner trust model and OIDC posture.")
    detail = (
        "Workflow policy checks pass and the trust model is documented."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "workflow-identity",
        "Workflow identity hardening and runner trust model",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(workflow_doc, WORKSPACE_ROOT / ".github" / "workflows", WORKSPACE_ROOT / ".github" / "actions"),
    )


def _config_and_secrets() -> AuditCheck:
    config_profiles = PRODUCT_ROOT / "docs" / "reference" / "configuration-profiles.md"
    product_env = PRODUCT_ROOT / ".env.example"
    frontend_env = PRODUCT_ROOT / "frontend" / "runtime-dashboard" / ".env.example"
    missing = [str(path) for path in (config_profiles, product_env, frontend_env) if not _path_exists(path)]
    detail = (
        "Config and secrets governance is documented with safe example env files."
        if not missing
        else f"Missing config/secrets governance asset: {', '.join(missing)}"
    )
    return _result(
        "config-secrets-governance",
        "Config and secrets governance",
        kind="automated",
        ok=not missing,
        detail=detail,
        evidence=(config_profiles, product_env, frontend_env),
    )


def _generated_artifacts() -> AuditCheck:
    artifacts_doc = PRODUCT_ROOT / "docs" / "reference" / "generated-artifacts.md"
    artifacts_toml = PRODUCT_ROOT / "architecture" / "generated_artifacts.toml"
    guardrails = PRODUCT_ROOT / "tools" / "architecture" / "guardrails.py"
    missing = [str(path) for path in (artifacts_doc, artifacts_toml, guardrails) if not _path_exists(path)]
    detail = (
        "Generated artifact lifecycle is tracked in repo policy and automation."
        if not missing
        else f"Missing generated-artifact lifecycle source: {', '.join(missing)}"
    )
    return _result(
        "generated-artifacts",
        "Generated artifact lifecycle",
        kind="automated",
        ok=not missing,
        detail=detail,
        evidence=(artifacts_doc, artifacts_toml, guardrails),
    )


def _external_security_signals() -> AuditCheck:
    nightly = WORKSPACE_ROOT / ".github" / "workflows" / "frontend-nightly.yml"
    release_workflow = WORKSPACE_ROOT / ".github" / "workflows" / "release.yml"
    security_md = WORKSPACE_ROOT / "SECURITY.md"
    issues: list[str] = []
    if not _contains(nightly, "scorecard"):
        issues.append("Nightly workflow no longer carries Scorecard coverage.")
    release_text = _read_text(release_workflow)
    if "attest" not in release_text and "cosign" not in release_text:
        issues.append("Release workflow no longer advertises provenance or signing steps.")
    if not _path_exists(security_md):
        issues.append("SECURITY.md is missing.")
    detail = (
        "External supply-chain posture is covered by Scorecard, release provenance/signing, and SECURITY.md."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "external-security-signals",
        "External security signals",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(nightly, release_workflow, security_md),
    )


def _delivery_performance_signals() -> AuditCheck:
    scorecard_doc = PRODUCT_ROOT / "docs" / "reference" / "operations" / "handoff-and-platform-review.md"
    issues: list[str] = []
    if not _contains(
        scorecard_doc,
        "Deployment frequency",
        "Lead time for change",
        "Change failure rate",
        "Mean time to restore",
    ):
        issues.append("Platform review scorecard is missing one or more DORA-style indicators.")
    detail = (
        "Platform scorecard keeps throughput and instability metrics visible."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "delivery-performance-signals",
        "Delivery-performance signals",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(scorecard_doc,),
    )


def _retention_and_restore() -> AuditCheck:
    retention = PRODUCT_ROOT / "docs" / "reference" / "operations" / "retention-and-recovery.md"
    replay = PRODUCT_ROOT / "docs" / "runbooks" / "replay-or-restore.md"
    retained = PRODUCT_ROOT / "docs" / "runbooks" / "retained-artifact-recovery.md"
    missing = [str(path) for path in (retention, replay, retained) if not _path_exists(path)]
    detail = (
        "Retention policy and recovery runbooks cover restore posture."
        if not missing
        else f"Missing retention or restore asset: {', '.join(missing)}"
    )
    return _result(
        "retention-restore-posture",
        "Retention and restore posture",
        kind="automated",
        ok=not missing,
        detail=detail,
        evidence=(retention, replay, retained),
    )


def _observability_ownership() -> AuditCheck:
    observability = PRODUCT_ROOT / "docs" / "reference" / "operations" / "observability-topology.md"
    issues: list[str] = []
    if not _contains(observability, "Owner", "@platform-owners", "runbook"):
        issues.append("Observability topology doc no longer shows signal ownership and runbook routing.")
    detail = (
        "Observability signals stay routed through named owners and runbooks."
        if not issues
        else " ".join(issues)
    )
    return _result(
        "observability-ownership",
        "Observability ownership",
        kind="automated",
        ok=not issues,
        detail=detail,
        evidence=(observability,),
    )


def load_manual_evidence(path: Path | None) -> dict[str, ManualEvidenceEntry]:
    """Load optional structured manual evidence entries from a TOML file."""

    if path is None:
        return {}
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    manual = payload.get("manual", payload)
    if not isinstance(manual, dict):
        raise SystemExit("manual evidence file must contain a [manual] table or top-level key/value pairs.")
    result: dict[str, ManualEvidenceEntry] = {}
    for key, value in manual.items():
        if key not in MANUAL_CHECKS:
            continue
        if isinstance(value, bool):
            result[key] = ManualEvidenceEntry(status=value)
            continue
        if not isinstance(value, dict):
            raise SystemExit(
                f"manual evidence value for `{key}` must be true/false or a table with `status`."
            )
        status = value.get("status")
        if not isinstance(status, bool):
            raise SystemExit(f"manual evidence table for `{key}` must contain boolean `status`.")
        notes = value.get("notes", "")
        if notes is None:
            notes = ""
        if not isinstance(notes, str):
            raise SystemExit(f"manual evidence table for `{key}` must use string `notes`.")
        evidence_value = value.get("evidence", [])
        if evidence_value is None:
            evidence_value = []
        if not isinstance(evidence_value, list) or not all(isinstance(item, str) for item in evidence_value):
            raise SystemExit(f"manual evidence table for `{key}` must use string-list `evidence`.")
        result[key] = ManualEvidenceEntry(
            status=status,
            notes=notes.strip(),
            evidence=tuple(evidence_value),
        )
    return result


def _manual_checks(
    manual_evidence: dict[str, ManualEvidenceEntry],
    *,
    require_manual_evidence: bool,
    manual_path: Path | None,
) -> tuple[AuditCheck, ...]:
    checks: list[AuditCheck] = []
    default_evidence = (str(manual_path),) if manual_path is not None else ()
    for key, (title, expectation) in MANUAL_CHECKS.items():
        entry = manual_evidence.get(key)
        notes_suffix = f" Notes: {entry.notes}" if entry and entry.notes else ""
        evidence = (
            *default_evidence,
            *(entry.evidence if entry is not None else ()),
        )
        if entry is not None and entry.status is True:
            checks.append(
                AuditCheck(
                    check_id=f"manual.{key}",
                    title=title,
                    kind="manual",
                    status="pass",
                    detail=f"{expectation}{notes_suffix}",
                    evidence=evidence,
                )
            )
            continue
        if require_manual_evidence:
            detail = f"{expectation} Record it in --manual-evidence before final closeout.{notes_suffix}"
            status = "fail"
        else:
            detail = f"{expectation} Not yet recorded in manual evidence.{notes_suffix}"
            status = "pending"
        checks.append(
            AuditCheck(
                check_id=f"manual.{key}",
                title=title,
                kind="manual",
                status=status,
                detail=detail,
                evidence=evidence,
            )
        )
    return tuple(checks)


def run_audit(
    *,
    manual_evidence: dict[str, ManualEvidenceEntry] | None = None,
    require_manual_evidence: bool = False,
    manual_path: Path | None = None,
) -> AuditReport:
    """Collect the Phase 7 acceptance audit report."""

    automated = (
        _toolchain_consistency(),
        _repo_root_coherence(),
        _ownership_coverage(),
        _merge_governance(),
        _required_checks(),
        _release_path(),
        _runbook_presence(),
        _bootstrap_and_doctor(),
        _dependency_freshness(),
        _workflow_identity_hardening(),
        _config_and_secrets(),
        _generated_artifacts(),
        _external_security_signals(),
        _delivery_performance_signals(),
        _retention_and_restore(),
        _observability_ownership(),
    )
    manual = _manual_checks(
        manual_evidence or {},
        require_manual_evidence=require_manual_evidence,
        manual_path=manual_path,
    )
    return AuditReport(checks=(*automated, *manual))


def write_summary(path: Path, report: AuditReport) -> None:
    """Write a markdown summary for the acceptance audit."""

    lines = [
        "# Platform Acceptance Audit",
        "",
        f"- Automated blockers: {sum(1 for check in report.blockers if check.kind == 'automated')}",
        f"- Manual blockers: {sum(1 for check in report.blockers if check.kind == 'manual')}",
        f"- Manual checks still pending: {sum(1 for check in report.pending if check.kind == 'manual')}",
        "",
        "| Check | Kind | Status | Detail |",
        "|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            f"| {check.title} | {check.kind} | {check.status} | {check.detail} |"
        )
    lines.append("")

    if report.blockers:
        lines.extend(["## Gap List", ""])
        lines.extend(f"- {check.title}: {check.detail}" for check in report.blockers)
        lines.append("")
    elif report.pending:
        lines.extend(["## Remaining Manual Evidence", ""])
        lines.extend(f"- {check.title}: {check.detail}" for check in report.pending)
        lines.append("")
    else:
        lines.extend(["## Gap List", "", "- No blockers remain in the current acceptance audit.", ""])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    manual_evidence = load_manual_evidence(args.manual_evidence)
    report = run_audit(
        manual_evidence=manual_evidence,
        require_manual_evidence=args.require_manual_evidence,
        manual_path=args.manual_evidence,
    )

    if args.summary:
        write_summary(args.summary.resolve(), report)
    if args.json_output:
        args.json_output.resolve().write_text(
            json.dumps(
                {
                    "checks": [asdict(check) for check in report.checks],
                    "blockers": [asdict(check) for check in report.blockers],
                    "pending": [asdict(check) for check in report.pending],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    for check in report.checks:
        print(f"[{check.status.upper()}] {check.title}: {check.detail}")

    if report.blockers:
        print(f"acceptance audit failed with {len(report.blockers)} blocker(s).")
        return 1

    print("acceptance audit passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
