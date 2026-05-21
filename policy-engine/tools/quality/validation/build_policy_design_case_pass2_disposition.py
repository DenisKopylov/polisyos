#!/usr/bin/env python3
"""Build Policy Design Case Wave 35 Pass 2 disposition artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation.check_policy_design_case_wave34_pass2 import (
    EXPECTED_PHASES,
)

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.pass2_disposition.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-pass2-disposition"
DEFAULT_DIAGNOSTICS_ROOT = Path("_build/diagnostics")
DEFAULT_OUTPUT_DIR = Path("_build/policy-design-case/rebaseline/wave-35")

BUILD_PASS2_DIAGNOSTICS_CMD = " ".join(
    (
        "uv run python",
        "tools/quality/validation/build_policy_design_case_pass2_diagnostics.py",
    )
)
CHECK_WAVE34_CMD = " ".join(
    (
        "uv run python",
        "tools/quality/validation/check_policy_design_case_wave34_pass2.py",
        "--repo-root .",
    )
)
RUN_PHASE34_3_CMD = " ".join(
    (
        "uv run python",
        "tools/quality/validation/run_policy_design_case_pass2_phase34_3.py",
    )
)
RUN_PHASE34_4_CMD = " ".join(
    (
        "uv run python",
        "tools/quality/validation/run_policy_design_case_pass2_phase34_4.py",
    )
)
RUN_PHASE34_5_CMD = " ".join(
    (
        "uv run python",
        "tools/quality/validation/run_policy_design_case_pass2_phase34_5.py",
    )
)
RUN_PHASE34_6_CMD = " ".join(
    (
        "uv run python",
        "tools/quality/validation/run_policy_design_case_pass2_phase34_6.py",
    )
)
CHECK_DISPOSITION_CMD = " ".join(
    (
        "uv run python",
        "tools/quality/validation/check_policy_design_case_pass2_disposition.py",
        "--repo-root . --require-passing",
    )
)
CLOSEOUT_READY_DISPOSITION_CMD = f"{CHECK_DISPOSITION_CMD} --require-closeout-ready"

ALLOWED_CLASSIFICATIONS = {
    "must_fix_before_closeout",
    "accepted_blocker",
    "next_plan_remediation",
    "false_alarm_with_evidence",
}

ACCEPTED_BLOCKER_CODES = {
    "pass2_wave33_baseline_fails_closed",
    "pass2_pdd064_snapshot_source_gaps_fail_closed",
    "publishable_artifact_scorecard_not_passing",
    "jurisdiction_spine_unresolved_competence_blocker",
}

FALSE_ALARM_CODES = {
    "pass2_pdd065_detailed_surfaces_preserve_root_cause",
}

CLUSTER_SPECS: dict[str, dict[str, Any]] = {
    "runtime_scenario_variant_coverage": {
        "title": "Runtime scenario, metamorphic, and language-variant evidence",
        "root_capability_gap": (
            "Wave 33 emitted one research-profile baseline instead of the "
            "cross-domain, metamorphic, multilingual, and adversarial runtime "
            "scenario matrix required for closeout."
        ),
        "owner": "team-runtime-quality",
        "affected_subsystem": "runtime canary matrix and scenario evidence",
        "target_plan_wave": "Wave 35A",
        "shared_remediation_surface": (
            "scenario matrix runner, variant registry, and Wave 33 rebaseline bundle "
            "publisher"
        ),
        "verification_command": (
            f"{BUILD_PASS2_DIAGNOSTICS_CMD} "
            f"&& {CHECK_WAVE34_CMD}"
        ),
        "closeout_impact": (
            "Wave 36 deterministic canary closeout cannot start until the missing "
            "scenario families have fresh runtime evidence or a superseding plan entry."
        ),
        "revisit_trigger": (
            "Any attempt to run Wave 36 deterministic closeout, or any new runtime "
            "scenario evidence generated for the affected PDDs."
        ),
    },
    "adversarial_fail_closed_and_strategic_gates": {
        "title": "Adversarial, poisoning, error-semantics, and strategic-risk gates",
        "root_capability_gap": (
            "Current evidence often fails closed, but the fail-closed condition is not "
            "yet backed by dedicated adversarial, poisoning, error taxonomy, and "
            "strategic-behavior runtime gates."
        ),
        "owner": "team-security",
        "affected_subsystem": "fail-closed security and strategic-risk diagnostics",
        "target_plan_wave": "Wave 35B",
        "shared_remediation_surface": (
            "negative-control harness, cache/index fingerprint ledger, error taxonomy, "
            "and strategic behavior ledger"
        ),
        "verification_command": (
            f"{BUILD_PASS2_DIAGNOSTICS_CMD} --phase 34.2 "
            f"&& {CHECK_WAVE34_CMD}"
        ),
        "closeout_impact": (
            "Closeout must not treat generic blockers as proof that adversarial and "
            "strategic-risk gates exist."
        ),
        "revisit_trigger": (
            "Any cache/index poisoning, prompt-injection, error-taxonomy, or strategic "
            "behavior gate evidence lands before deterministic closeout."
        ),
    },
    "claim_authority_and_extraction_measurement_binding": {
        "title": "Claim authority, extraction, and measurement binding",
        "root_capability_gap": (
            "Final claim refs, extraction quality, and measurement semantics are not "
            "bound through a publishable claim-authority registry."
        ),
        "owner": "team-claim-compiler",
        "affected_subsystem": (
            "claim compiler, producer evidence, extraction authority, and measurement semantics"
        ),
        "target_plan_wave": "Wave 35C",
        "shared_remediation_surface": (
            "claim registry, producer locator refs, extraction-quality ledger, and "
            "survey/measurement ledger"
        ),
        "verification_command": (
            f"{RUN_PHASE34_3_CMD} "
            f"&& {RUN_PHASE34_4_CMD} "
            f"&& {CHECK_WAVE34_CMD}"
        ),
        "closeout_impact": (
            "Major claims remain non-publishable until claim-bound producer evidence, "
            "extraction fidelity, and measurement authority are explicit."
        ),
        "revisit_trigger": (
            "Any claim compiler, Lex/Scholar locator, extraction QC, or survey "
            "measurement evidence changes."
        ),
    },
    "semantic_validity_monitoring_and_model_readiness": {
        "title": "Competence, transferability, uncertainty, monitoring, and model readiness",
        "root_capability_gap": (
            "Validity semantics exist as local text or blockers, not as end-to-end "
            "runtime refs that bind competence, transportability, uncertainty, "
            "monitoring, and model-readiness to final claims."
        ),
        "owner": "team-science-quality",
        "affected_subsystem": "Foundry, Scientist, DDM, jurisdiction spine, and model registry",
        "target_plan_wave": "Wave 35C",
        "shared_remediation_surface": (
            "semantic validity ledgers, method-result refs, jurisdiction competence "
            "refs, monitoring maps, and model-dependency records"
        ),
        "verification_command": (
            f"{RUN_PHASE34_3_CMD} "
            f"&& {CHECK_WAVE34_CMD}"
        ),
        "closeout_impact": (
            "Final readiness cannot rely on a claim whose competence, transportability, "
            "uncertainty, monitoring, or model dependencies are unbound."
        ),
        "revisit_trigger": (
            "Any jurisdiction-spine, Foundry method-result, uncertainty, DDM, or "
            "model-readiness evidence changes."
        ),
    },
    "operational_recovery_resource_and_archive_readiness": {
        "title": "Operational root cause, recovery, resource, live parity, and archive readiness",
        "root_capability_gap": (
            "Operational evidence has partial breadcrumbs and replay artifacts, but "
            "does not yet prove restore drills, resource-exhaustion semantics, "
            "live/polling parity, or archive-grade reproducibility."
        ),
        "owner": "team-core-audit",
        "affected_subsystem": "runtime operations, recovery, audit archive, and DDM events",
        "target_plan_wave": "Wave 35D",
        "shared_remediation_surface": (
            "operator diagnostic object, restore drill bundle, resource exhaustion "
            "ledger, live/polling parity proof, and archive verifier"
        ),
        "verification_command": (
            f"{RUN_PHASE34_5_CMD} "
            f"&& {CHECK_WAVE34_CMD}"
        ),
        "closeout_impact": (
            "Closeout cannot claim recoverability, reproducibility, or operator-grade "
            "failure diagnosis while these ledgers are absent."
        ),
        "revisit_trigger": (
            "Any restore, resource-exhaustion, live cursor, replay, archive, or "
            "operator-diagnostic evidence changes."
        ),
    },
    "human_facing_legitimacy_memory_and_trust_controls": {
        "title": "Human-facing projection, legitimacy, memory, implementation, and trust controls",
        "root_capability_gap": (
            "Dashboard/API projections, operator truthfulness, memory applicability, "
            "implementation feasibility, contestability, and trust framing are not "
            "proven by runtime ledgers or negative UI evidence."
        ),
        "owner": "team-quality-closeout",
        "affected_subsystem": (
            "runtime dashboard, public export, memory, human review, and UI trust"
        ),
        "target_plan_wave": "Wave 35E",
        "shared_remediation_surface": (
            "projection matrix, operator journey diff, memory/no-memory ledger, "
            "implementation ledger, contestability ledger, and trust-framing UI tests"
        ),
        "verification_command": (
            f"{RUN_PHASE34_6_CMD} "
            f"&& {CHECK_WAVE34_CMD}"
        ),
        "closeout_impact": (
            "Human-facing closeout waves cannot rely on projection-only or optimistic "
            "UI semantics until these controls are explicit."
        ),
        "revisit_trigger": (
            "Any dashboard/API projection, memory ledger, implementation, appeals, "
            "human-review, or trust-framing evidence changes."
        ),
    },
}

PDD_CLUSTER_MAP: dict[str, str] = {
    "PDD-037": "runtime_scenario_variant_coverage",
    "PDD-055": "runtime_scenario_variant_coverage",
    "PDD-056": "runtime_scenario_variant_coverage",
    "PDD-038": "adversarial_fail_closed_and_strategic_gates",
    "PDD-064": "adversarial_fail_closed_and_strategic_gates",
    "PDD-065": "adversarial_fail_closed_and_strategic_gates",
    "PDD-098": "adversarial_fail_closed_and_strategic_gates",
    "PDD-044": "claim_authority_and_extraction_measurement_binding",
    "PDD-100": "claim_authority_and_extraction_measurement_binding",
    "PDD-101": "claim_authority_and_extraction_measurement_binding",
    "PDD-048": "semantic_validity_monitoring_and_model_readiness",
    "PDD-050": "semantic_validity_monitoring_and_model_readiness",
    "PDD-051": "semantic_validity_monitoring_and_model_readiness",
    "PDD-057": "semantic_validity_monitoring_and_model_readiness",
    "PDD-087": "semantic_validity_monitoring_and_model_readiness",
    "PDD-046": "operational_recovery_resource_and_archive_readiness",
    "PDD-077": "operational_recovery_resource_and_archive_readiness",
    "PDD-078": "operational_recovery_resource_and_archive_readiness",
    "PDD-090": "operational_recovery_resource_and_archive_readiness",
    "PDD-104": "operational_recovery_resource_and_archive_readiness",
    "PDD-034": "human_facing_legitimacy_memory_and_trust_controls",
    "PDD-069": "human_facing_legitimacy_memory_and_trust_controls",
    "PDD-083": "human_facing_legitimacy_memory_and_trust_controls",
    "PDD-097": "human_facing_legitimacy_memory_and_trust_controls",
    "PDD-099": "human_facing_legitimacy_memory_and_trust_controls",
    "PDD-103": "human_facing_legitimacy_memory_and_trust_controls",
}

INSERTED_REMEDIATION_WAVES: tuple[dict[str, Any], ...] = (
    {
        "wave": "Wave 35A",
        "title": "Runtime Scenario And Variant Evidence Remediation",
        "owner": "team-runtime-quality",
        "cluster_ids": ("runtime_scenario_variant_coverage",),
    },
    {
        "wave": "Wave 35B",
        "title": "Adversarial Fail-Closed And Strategic Gate Remediation",
        "owner": "team-security",
        "cluster_ids": ("adversarial_fail_closed_and_strategic_gates",),
    },
    {
        "wave": "Wave 35C",
        "title": "Claim Authority, Producer Binding, And Semantic Validity Remediation",
        "owner": "team-claim-compiler",
        "cluster_ids": (
            "claim_authority_and_extraction_measurement_binding",
            "semantic_validity_monitoring_and_model_readiness",
        ),
    },
    {
        "wave": "Wave 35D",
        "title": "Operational Recovery, Resource, And Archive Remediation",
        "owner": "team-core-audit",
        "cluster_ids": ("operational_recovery_resource_and_archive_readiness",),
    },
    {
        "wave": "Wave 35E",
        "title": "Human-Facing Legitimacy, Memory, And Trust Remediation",
        "owner": "team-quality-closeout",
        "cluster_ids": ("human_facing_legitimacy_memory_and_trust_controls",),
    },
)


def build_wave35_payloads(
    *,
    repo_root: Path = REPO_ROOT,
    diagnostics_root: Path = DEFAULT_DIAGNOSTICS_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    ledger = build_findings_ledger_payload(
        repo_root=repo_root,
        diagnostics_root=diagnostics_root,
    )
    clusters = build_root_cause_clusters_payload(ledger)
    disposition = build_disposition_payload(
        ledger=ledger,
        clusters=clusters,
        repo_root=repo_root,
        output_dir=output_dir,
    )
    return ledger, clusters, disposition


def build_findings_ledger_payload(
    *,
    repo_root: Path = REPO_ROOT,
    diagnostics_root: Path = DEFAULT_DIAGNOSTICS_ROOT,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    diagnostics_path = _resolve(repo_root, diagnostics_root)
    phase_indexes: list[dict[str, Any]] = []
    detail_artifacts: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    generated_values: list[str] = []

    for phase, spec in EXPECTED_PHASES.items():
        index_path = diagnostics_path / "pass2" / str(spec["index"])
        index_payload = _load_json(index_path)
        generated = str(index_payload.get("generated_at") or "")
        if generated:
            generated_values.append(generated)
        phase_indexes.append(
            {
                "phase": phase,
                "artifact": _rel_path(index_path, repo_root),
                "schema_version": index_payload.get("schema_version"),
                "status": index_payload.get("status"),
                "runtime_acceptance_status": index_payload.get(
                    "runtime_acceptance_status"
                ),
                "pdd_count": len(spec["pdds"]),
            }
        )

        for pdd_id, slug in spec["pdds"].items():
            detail_path = diagnostics_path / pdd_id.lower() / f"{slug}.json"
            detail = _load_json(detail_path)
            if str(detail.get("generated_at") or ""):
                generated_values.append(str(detail["generated_at"]))
            detail_artifacts.append(
                {
                    "pdd_id": pdd_id,
                    "phase": phase,
                    "artifact": _rel_path(detail_path, repo_root),
                    "phase_index_artifact": _rel_path(index_path, repo_root),
                    "title": detail.get("title"),
                    "acceptance_gate_status": detail.get("acceptance_gate_status"),
                    "verdict": detail.get("verdict"),
                    "finding_count": len(_as_list(detail.get("findings"))),
                    "recommended_gate": detail.get("recommended_gate"),
                    "recommended_remediation_id": detail.get(
                        "recommended_remediation_id"
                    ),
                    "represented_in_ledger": True,
                }
            )
            for index, finding in enumerate(_as_list(detail.get("findings")), start=1):
                if not isinstance(finding, Mapping):
                    continue
                findings.append(
                    _canonical_finding_row(
                        repo_root=repo_root,
                        detail=detail,
                        finding=finding,
                        pdd_id=pdd_id,
                        phase=phase,
                        ordinal=index,
                        detail_path=detail_path,
                        index_path=index_path,
                    )
                )

    generated_at = max(generated_values) if generated_values else "2026-05-18T00:00:00+00:00"
    zero_finding = [
        item["pdd_id"] for item in detail_artifacts if int(item["finding_count"]) == 0
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35",
        "phase": "35.1",
        "source_wave": "34",
        "status": "ledger_built",
        "summary": {
            "phase_index_count": len(phase_indexes),
            "pdd_detail_artifact_count": len(detail_artifacts),
            "finding_count": len(findings),
            "zero_finding_detail_count": len(zero_finding),
            "zero_finding_pdd_ids": zero_finding,
        },
        "phase_indexes": phase_indexes,
        "pdd_detail_artifacts": detail_artifacts,
        "findings": findings,
    }


def build_root_cause_clusters_payload(ledger: Mapping[str, Any]) -> dict[str, Any]:
    findings = _as_list(ledger.get("findings"))
    by_cluster: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for finding in findings:
        if not isinstance(finding, Mapping):
            continue
        cluster_id = _cluster_id_for(str(finding.get("pdd_id") or ""))
        by_cluster[cluster_id].append(finding)

    clusters: list[dict[str, Any]] = []
    for cluster_id, spec in CLUSTER_SPECS.items():
        rows = by_cluster.get(cluster_id, [])
        finding_ids = [str(row["finding_id"]) for row in rows]
        clusters.append(
            {
                "cluster_id": cluster_id,
                "title": spec["title"],
                "owner": spec["owner"],
                "affected_subsystem": spec["affected_subsystem"],
                "root_capability_gap": spec["root_capability_gap"],
                "shared_remediation_surface": spec["shared_remediation_surface"],
                "target_plan_wave": spec["target_plan_wave"],
                "verification_command": spec["verification_command"],
                "revisit_trigger": spec["revisit_trigger"],
                "closeout_impact": spec["closeout_impact"],
                "finding_count": len(rows),
                "finding_ids": finding_ids,
                "pdd_ids": sorted({str(row.get("pdd_id")) for row in rows}),
                "phases": sorted({str(row.get("phase")) for row in rows}),
                "finding_codes": sorted(
                    {str(row.get("finding_code")) for row in rows}
                ),
                "recommended_remediation_ids": sorted(
                    {
                        str(row.get("recommended_remediation_id"))
                        for row in rows
                        if row.get("recommended_remediation_id")
                    }
                ),
                "source_artifacts": sorted(
                    {str(row.get("source_artifact")) for row in rows}
                ),
            }
        )

    covered = [finding_id for cluster in clusters for finding_id in cluster["finding_ids"]]
    unclustered = sorted(
        {
            str(row.get("finding_id"))
            for row in findings
            if str(row.get("finding_id")) not in set(covered)
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": ledger.get("generated_at"),
        "wave": "35",
        "phase": "35.1",
        "source_wave": "34",
        "status": "clustered" if not unclustered else "cluster_incomplete",
        "summary": {
            "cluster_count": len(clusters),
            "finding_count": len(findings),
            "covered_finding_count": len(covered),
            "unclustered_finding_count": len(unclustered),
        },
        "clusters": clusters,
        "unclustered_findings": unclustered,
    }


def build_disposition_payload(
    *,
    ledger: Mapping[str, Any],
    clusters: Mapping[str, Any],
    repo_root: Path = REPO_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_path = _resolve(repo_root, output_dir)
    findings = [row for row in _as_list(ledger.get("findings")) if isinstance(row, Mapping)]
    cluster_by_finding_id = _cluster_by_finding_id(clusters)
    dispositions = [
        _disposition_for(row, cluster_by_finding_id[str(row["finding_id"])])
        for row in findings
    ]
    artifact_dispositions = _artifact_dispositions(ledger)
    classification_counts = Counter(
        str(row.get("classification")) for row in dispositions
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": ledger.get("generated_at"),
        "wave": "35",
        "phase": "35.1",
        "source_wave": "34",
        "status": "pass",
        "summary": {
            "finding_count": len(findings),
            "disposition_count": len(dispositions),
            "artifact_disposition_count": len(artifact_dispositions),
            "classification_counts": dict(sorted(classification_counts.items())),
            "must_fix_unresolved_count": 0,
            "inserted_remediation_wave_count": len(INSERTED_REMEDIATION_WAVES),
            "accepted_blocker_count": classification_counts["accepted_blocker"],
            "next_plan_remediation_count": classification_counts[
                "next_plan_remediation"
            ],
            "false_alarm_with_evidence_count": classification_counts[
                "false_alarm_with_evidence"
            ],
        },
        "artifacts": {
            "findings_ledger": _rel_path(
                output_path / "pass2_findings_ledger.json", repo_root
            ),
            "root_cause_clusters": _rel_path(
                output_path / "pass2_root_cause_clusters.json", repo_root
            ),
            "disposition": _rel_path(output_path / "pass2_disposition.json", repo_root),
        },
        "dispositions": dispositions,
        "artifact_dispositions": artifact_dispositions,
        "plan_wave_impact": _plan_wave_impact(),
    }


def write_wave35_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    diagnostics_root: Path = DEFAULT_DIAGNOSTICS_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> tuple[Path, Path, Path]:
    repo_root = repo_root.resolve()
    output_path = _resolve(repo_root, output_dir)
    ledger, clusters, disposition = build_wave35_payloads(
        repo_root=repo_root,
        diagnostics_root=diagnostics_root,
        output_dir=output_dir,
    )
    ledger_path = output_path / "pass2_findings_ledger.json"
    clusters_path = output_path / "pass2_root_cause_clusters.json"
    disposition_path = output_path / "pass2_disposition.json"
    atomic_write_json(ledger_path, ledger)
    atomic_write_json(clusters_path, clusters)
    atomic_write_json(disposition_path, disposition)
    return ledger_path, clusters_path, disposition_path


def _canonical_finding_row(
    *,
    repo_root: Path,
    detail: Mapping[str, Any],
    finding: Mapping[str, Any],
    pdd_id: str,
    phase: str,
    ordinal: int,
    detail_path: Path,
    index_path: Path,
) -> dict[str, Any]:
    code = str(finding.get("code") or f"{pdd_id.lower()}_finding_{ordinal:03d}")
    title = str(finding.get("title") or detail.get("title") or code)
    summary = str(
        finding.get("summary")
        or finding.get("message")
        or finding.get("finding")
        or title
    )
    context = {
        key: value
        for key, value in finding.items()
        if key
        not in {
            "code",
            "severity",
            "summary",
            "title",
            "message",
            "evidence",
            "refs",
        }
    }
    return {
        "finding_id": f"{pdd_id}-F{ordinal:03d}",
        "finding_code": code,
        "severity": str(finding.get("severity") or "unknown"),
        "pdd_id": pdd_id,
        "phase": phase,
        "title": title,
        "summary": summary,
        "source_artifact": _rel_path(detail_path, repo_root),
        "phase_index_artifact": _rel_path(index_path, repo_root),
        "source_evidence": _source_evidence(
            detail=detail,
            finding=finding,
            detail_path=detail_path,
            index_path=index_path,
            repo_root=repo_root,
        ),
        "recommended_gate": str(detail.get("recommended_gate") or ""),
        "recommended_remediation_id": detail.get("recommended_remediation_id"),
        "finding_owner": finding.get("owner"),
        "finding_context": context,
    }


def _source_evidence(
    *,
    detail: Mapping[str, Any],
    finding: Mapping[str, Any],
    detail_path: Path,
    index_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    evidence = {
        "detail_artifact": _rel_path(detail_path, repo_root),
        "phase_index_artifact": _rel_path(index_path, repo_root),
        "wave33_source_artifacts": detail.get("source_artifacts") or {},
    }
    if finding.get("evidence") is not None:
        evidence["finding_evidence"] = finding["evidence"]
    if finding.get("refs") is not None:
        evidence["finding_refs"] = finding["refs"]
    if finding.get("missing_input") is not None:
        evidence["missing_input"] = finding["missing_input"]
    if finding.get("message") is not None:
        evidence["diagnostic_message"] = finding["message"]
    if "finding_evidence" not in evidence and "finding_refs" not in evidence:
        evidence["diagnostic_summary"] = (
            finding.get("summary") or finding.get("title") or finding.get("code")
        )
    return evidence


def _cluster_by_finding_id(clusters: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for cluster in _as_list(clusters.get("clusters")):
        if not isinstance(cluster, Mapping):
            continue
        for finding_id in _as_list(cluster.get("finding_ids")):
            result[str(finding_id)] = cluster
    return result


def _disposition_for(
    finding: Mapping[str, Any],
    cluster: Mapping[str, Any],
) -> dict[str, Any]:
    classification = _classification_for(finding)
    finding_id = str(finding["finding_id"])
    owner = _owner_for(finding=finding, cluster=cluster, classification=classification)
    verification_command = _verification_command_for(finding=finding, cluster=cluster)
    payload: dict[str, Any] = {
        "disposition_id": f"DISP-{finding_id}",
        "finding_id": finding_id,
        "finding_code": finding.get("finding_code"),
        "classification": classification,
        "rationale": _rationale_for(classification, finding, cluster),
        "owner": owner,
        "affected_subsystem": cluster.get("affected_subsystem"),
        "root_cause_cluster_id": cluster.get("cluster_id"),
        "closeout_impact": finding.get("finding_context", {}).get(
            "downstream_impact",
            cluster.get("closeout_impact"),
        ),
        "verification_command": verification_command,
        "source_evidence": finding.get("source_evidence"),
        "recommended_gate": finding.get("recommended_gate"),
        "recommended_remediation_id": finding.get("recommended_remediation_id"),
    }
    if classification == "next_plan_remediation":
        payload["target_plan_wave"] = cluster.get("target_plan_wave")
        payload["revisit_trigger"] = cluster.get("revisit_trigger")
        payload["deferral_evidence"] = {
            "deferral_kind": "inserted_pre_wave36_remediation_wave",
            "why_deferral_is_honest": (
                "The finding names missing runtime/product evidence, not a Wave 35 "
                "ledger defect. Wave 35 records the gap and inserts a remediation "
                "wave before Wave 36 can start."
            ),
            "target_plan_wave": cluster.get("target_plan_wave"),
            "source_artifact": finding.get("source_artifact"),
            "root_cause_cluster_id": cluster.get("cluster_id"),
        }
    elif classification == "accepted_blocker":
        payload["target_plan_wave"] = cluster.get("target_plan_wave")
        payload["revisit_trigger"] = cluster.get("revisit_trigger")
        payload["accepted_blocker_evidence"] = {
            "blocker_kind": "current_evidence_already_fails_closed",
            "why_acceptance_is_honest": (
                "The source finding records an existing blocker or fail-closed state. "
                "It is accepted only as a blocker, not as completed remediation."
            ),
            "target_plan_wave": cluster.get("target_plan_wave"),
            "source_artifact": finding.get("source_artifact"),
            "source_evidence": finding.get("source_evidence"),
        }
    elif classification == "false_alarm_with_evidence":
        payload["false_alarm_evidence"] = {
            "why_not_a_remediation_gap": (
                "The source row records a positive diagnostic fact rather than a "
                "missing capability that Wave 35 should remediate."
            ),
            "source_artifact": finding.get("source_artifact"),
            "source_evidence": finding.get("source_evidence"),
        }
    else:
        payload["remediation_evidence"] = {
            "status": "unresolved",
            "reason": "Wave 35 did not classify product capability gaps as local fixes.",
        }
    return payload


def _artifact_dispositions(ledger: Mapping[str, Any]) -> list[dict[str, Any]]:
    dispositions: list[dict[str, Any]] = []
    for artifact in _as_list(ledger.get("pdd_detail_artifacts")):
        if not isinstance(artifact, Mapping) or int(artifact.get("finding_count") or 0) != 0:
            continue
        pdd_id = str(artifact.get("pdd_id"))
        dispositions.append(
            {
                "artifact_disposition_id": f"DISP-{pdd_id}-NO-ACTIVE-FINDING",
                "pdd_id": pdd_id,
                "classification": "false_alarm_with_evidence",
                "rationale": (
                    "The Wave 34 detail artifact is represented and has zero active "
                    "findings because its gate was explicitly not triggered."
                ),
                "owner": "team-claim-compiler",
                "affected_subsystem": "BERL/explanation reliability binding",
                "closeout_impact": (
                    "No BERL remediation is required unless a later wave introduces "
                    "explanation support into claim evidence."
                ),
                "verification_command": (
                    f"{RUN_PHASE34_3_CMD} "
                    f"&& {CHECK_WAVE34_CMD}"
                ),
                "source_evidence": {
                    "detail_artifact": artifact.get("artifact"),
                    "phase_index_artifact": artifact.get("phase_index_artifact"),
                    "acceptance_gate_status": artifact.get("acceptance_gate_status"),
                    "verdict": artifact.get("verdict"),
                },
                "false_alarm_evidence": {
                    "why_not_a_remediation_gap": (
                        "Wave 34 found no BERL/explanation support usage, so the "
                        "BERL reliability binding diagnostic is a not-triggered boundary."
                    ),
                    "source_artifact": artifact.get("artifact"),
                },
            }
        )
    return dispositions


def _classification_for(finding: Mapping[str, Any]) -> str:
    code = str(finding.get("finding_code") or "")
    if code in FALSE_ALARM_CODES:
        return "false_alarm_with_evidence"
    if code in ACCEPTED_BLOCKER_CODES:
        return "accepted_blocker"
    return "next_plan_remediation"


def _owner_for(
    *,
    finding: Mapping[str, Any],
    cluster: Mapping[str, Any],
    classification: str,
) -> str:
    if classification == "false_alarm_with_evidence":
        return str(finding.get("finding_owner") or cluster.get("owner"))
    if finding.get("finding_owner"):
        return str(finding["finding_owner"])
    return str(cluster.get("owner"))


def _verification_command_for(
    *,
    finding: Mapping[str, Any],
    cluster: Mapping[str, Any],
) -> str:
    context = finding.get("finding_context")
    if isinstance(context, Mapping) and context.get("next_command"):
        return str(context["next_command"])
    return str(cluster.get("verification_command"))


def _rationale_for(
    classification: str,
    finding: Mapping[str, Any],
    cluster: Mapping[str, Any],
) -> str:
    if classification == "accepted_blocker":
        return (
            "Accepted as an honest blocker because Wave 34 records a fail-closed or "
            "already-blocking condition. It still targets "
            f"{cluster.get('target_plan_wave')} so the blocker cannot be mistaken "
            "for completed remediation."
        )
    if classification == "false_alarm_with_evidence":
        return (
            "Classified as false alarm with evidence because this row records a "
            "positive or not-remediation diagnostic fact rather than a missing "
            "capability."
        )
    if classification == "must_fix_before_closeout":
        return (
            "Local Wave 35 fix required before closeout because the disposition "
            "validator itself found a remediation-scoped defect."
        )
    return (
        "Requires a new pre-Wave-36 remediation wave because the evidence names a "
        "shared runtime/product capability gap rather than a local Wave 35 ledger fix."
    )


def _plan_wave_impact() -> dict[str, Any]:
    return {
        "current_plan_waves_remaining_valid": [
            "Wave 36 remains valid only after the Wave 35A-35E remediation waves exit.",
            "Wave 37 remains valid after Wave 36 preserves the disposition gate.",
            "Wave 38 remains valid after runtime API closeout still observes disposition blockers.",
            "Wave 39 remains valid after local integration smoke refuses unresolved Pass 2 gaps.",
            (
                "Wave 40 remains valid after dashboard journey smoke includes "
                "human-facing dispositions."
            ),
            "Wave 41 remains valid after backlog handoff records any remaining next-plan items.",
        ],
        "waves_requiring_strengthened_entry_criteria": [
            "Wave 36",
            "Wave 37",
            "Wave 38",
            "Wave 39",
            "Wave 40",
            "Wave 41",
        ],
        "inserted_remediation_waves": list(INSERTED_REMEDIATION_WAVES),
        "wave36_entry_criteria": [
            f"Run `{CHECK_DISPOSITION_CMD}`.",
            f"Run `{CLOSEOUT_READY_DISPOSITION_CMD}`.",
            (
                "Confirm `_build/policy-design-case/rebaseline/wave-35/"
                "pass2_disposition.json` reports zero unresolved "
                "`must_fix_before_closeout` findings."
            ),
            (
                "Confirm every `next_plan_remediation` and `accepted_blocker` "
                "target wave in Wave 35A through Wave 35E has completed or has a "
                "later decision-log supersession before Wave 36 starts."
            ),
        ],
    }


def _cluster_id_for(pdd_id: str) -> str:
    cluster_id = PDD_CLUSTER_MAP.get(pdd_id)
    if not cluster_id:
        raise KeyError(f"No Wave 35 root-cause cluster mapping for {pdd_id}")
    return cluster_id


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _resolve(repo_root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    return candidate.resolve(strict=False)


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--diagnostics-root",
        type=Path,
        default=DEFAULT_DIAGNOSTICS_ROOT,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    paths = write_wave35_outputs(
        repo_root=args.repo_root,
        diagnostics_root=args.diagnostics_root,
        output_dir=args.output_dir,
    )
    for path in paths:
        sys.stdout.write(f"{path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
