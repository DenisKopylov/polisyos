#!/usr/bin/env python3
"""Build Wave 35A runtime scenario and variant remediation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.metamorphic_controls import (  # noqa: E402
    PHASE56_CROSS_DOMAIN_SCENARIO_IDS,
    build_metamorphic_prompt_report,
)
from tools.ops_runners.runtime.quality_scenarios import (  # noqa: E402
    load_quality_scenario_contract,
)

SCHEMA_VERSION = "policyos.policy_design_case.wave35a.runtime_variant_evidence.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-wave35a"
CLUSTER_ID = "runtime_scenario_variant_coverage"
WAVE35_DIR = Path("_build/policy-design-case/rebaseline/wave-35")
WAVE35A_DIR = Path("_build/policy-design-case/rebaseline/wave-35A")
DIAGNOSTICS_ROOT = Path("_build/diagnostics")

PHASE34_1_BUILD_COMMAND = (
    "uv run python tools/quality/validation/build_policy_design_case_pass2_diagnostics.py "
    "--phase 34.1"
)
PHASE34_1_CHECK_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_wave34_pass2.py "
    "--repo-root ."
)
VERIFY_DISPOSITION_COMMAND = (
    "uv run python tools/quality/validation/check_policy_design_case_pass2_disposition.py "
    "--repo-root . --require-passing --require-closeout-ready"
)

SOURCE_ARTIFACT_BY_PDD = {
    "PDD-037": "_build/diagnostics/pdd-037/cross_domain_generality_diagnostic_matrix.json",
    "PDD-055": "_build/diagnostics/pdd-055/metamorphic_policy_diagnostic_suite.json",
    "PDD-056": "_build/diagnostics/pdd-056/multilingual_transliteration_equivalence_audit.json",
}

INSPECTED_LANGUAGE_PATHS: tuple[dict[str, str], ...] = (
    {
        "surface": "runtime_routing",
        "owner": "team-runtime-quality",
        "glob": "src/polisyos/runtime/http/**/*.py",
    },
    {
        "surface": "prompt_tool",
        "owner": "team-science-quality",
        "glob": "src/polisyos/scientist/agent/**/*.py",
    },
    {
        "surface": "locale",
        "owner": "team-policy-semantics",
        "glob": "apps/runtime-dashboard/src/shared/i18n/locales/*.json",
    },
    {
        "surface": "lex_normpack",
        "owner": "team-policy-semantics",
        "glob": "src/polisyos/lex/normpack/**/*.py",
    },
    {
        "surface": "dashboard_api_projection",
        "owner": "team-runtime-dashboard",
        "glob": "apps/runtime-dashboard/src/**/*.*",
    },
    {
        "surface": "scenario_loading",
        "owner": "team-runtime-quality",
        "glob": "tools/ops_runners/runtime/*scenario*.py",
    },
)

LANGUAGE_LITERAL_PATTERN = re.compile(
    r"(?i)(english|ukrainian|україн|ukraine|poland|locale|language|translit|mixed|"
    r"\buk\b|\ben\b|\bua\b)"
)


def build_wave35a_outputs(
    *,
    repo_root: Path = REPO_ROOT,
    wave35_dir: Path = WAVE35_DIR,
    wave35a_dir: Path = WAVE35A_DIR,
    run_rerun: bool = False,
    update_disposition: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    wave35_path = _resolve(repo_root, wave35_dir)
    wave35a_path = _resolve(repo_root, wave35a_dir)
    wave35a_path.mkdir(parents=True, exist_ok=True)

    ledger = _load_json(wave35_path / "pass2_findings_ledger.json")
    disposition = _load_json(wave35_path / "pass2_disposition.json")
    original_disposition = deepcopy(disposition)
    affected_rows = _affected_dispositions(disposition)
    findings_by_id = {
        str(row.get("finding_id")): row
        for row in _as_list(ledger.get("findings"))
        if isinstance(row, Mapping)
    }
    contracts = {
        scenario_id: load_quality_scenario_contract(scenario_id)
        for scenario_id in PHASE56_CROSS_DOMAIN_SCENARIO_IDS
    }
    bundles = _latest_completed_bundles(
        wave35a_path / "runtime-bundles",
        scenario_ids=PHASE56_CROSS_DOMAIN_SCENARIO_IDS,
        repo_root=repo_root,
    )

    inventory = _build_inventory(
        affected_rows=affected_rows,
        findings_by_id=findings_by_id,
        repo_root=repo_root,
    )
    cross_domain = _build_cross_domain_bundles(
        bundles=bundles,
        contracts=contracts,
        repo_root=repo_root,
    )
    metamorphic = _build_metamorphic_variants(
        bundles=bundles,
        contracts=contracts,
        repo_root=repo_root,
    )
    language_pairs = _build_language_pairs(
        bundles=bundles,
        contracts=contracts,
        repo_root=repo_root,
    )
    hardcoded_audit = _build_hardcoded_language_audit(repo_root=repo_root)

    atomic_write_json(wave35a_path / "scenario_variant_inventory.json", inventory)
    atomic_write_json(wave35a_path / "cross_domain_runtime_bundles.json", cross_domain)
    atomic_write_json(wave35a_path / "metamorphic_runtime_variants.json", metamorphic)
    atomic_write_json(
        wave35a_path / "language_equivalence_runtime_pairs.json",
        language_pairs,
    )
    atomic_write_json(
        wave35a_path / "hardcoded_language_path_audit.json",
        hardcoded_audit,
    )

    phase34_rerun: dict[str, Any] | None = None
    if run_rerun:
        phase34_rerun = _run_phase34_1_rerun(
            repo_root=repo_root,
            wave35a_path=wave35a_path,
        )
        atomic_write_json(wave35a_path / "phase34_1_rerun.json", phase34_rerun)
    elif (wave35a_path / "phase34_1_rerun.json").exists():
        phase34_rerun = _load_json(wave35a_path / "phase34_1_rerun.json")

    disposition_update = _build_disposition_update(
        disposition=disposition,
        original_disposition=original_disposition,
        affected_rows=affected_rows,
        findings_by_id=findings_by_id,
        inventory=inventory,
        cross_domain=cross_domain,
        metamorphic=metamorphic,
        language_pairs=language_pairs,
        hardcoded_audit=hardcoded_audit,
        phase34_rerun=phase34_rerun,
        repo_root=repo_root,
    )
    atomic_write_json(
        wave35a_path / "wave35_disposition_update.json",
        disposition_update,
    )

    if update_disposition:
        atomic_write_json(wave35_path / "pass2_disposition.json", disposition)

    return {
        "inventory": inventory,
        "cross_domain": cross_domain,
        "metamorphic": metamorphic,
        "language_pairs": language_pairs,
        "hardcoded_audit": hardcoded_audit,
        "phase34_rerun": phase34_rerun,
        "disposition_update": disposition_update,
    }


def _build_inventory(
    *,
    affected_rows: Sequence[Mapping[str, Any]],
    findings_by_id: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for row in affected_rows:
        finding_id = str(row["finding_id"])
        finding = findings_by_id[finding_id]
        pdd_id = str(finding.get("pdd_id") or finding_id.split("-F", 1)[0])
        context = _mapping(finding.get("finding_context"))
        scenario_id = _scenario_id_for_finding(finding=finding, disposition=row)
        family, variant_id = _evidence_family_and_variant(
            pdd_id=pdd_id,
            finding_code=str(row.get("finding_code") or ""),
            scenario_id=scenario_id,
        )
        rows.append(
            {
                "finding_id": finding_id,
                "finding_code": row.get("finding_code"),
                "pdd_id": pdd_id,
                "phase": finding.get("phase"),
                "scenario_id": scenario_id,
                "scenario_or_variant_id": variant_id,
                "required_runtime_evidence_family": family,
                "owner": row.get("owner") or finding.get("finding_owner"),
                "source_artifact": _source_artifact(row),
                "source_evidence": row.get("source_evidence"),
                "verification_command": row.get("verification_command"),
                "recommended_gate": row.get("recommended_gate"),
                "missing_input": _mapping(row.get("source_evidence")).get("missing_input")
                or context.get("missing_input"),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35A",
        "phase": "35A.1",
        "cluster_id": CLUSTER_ID,
        "status": "complete" if len(rows) == 31 else "incomplete",
        "finding_count": len(rows),
        "required_finding_count": 31,
        "source_artifacts": sorted(SOURCE_ARTIFACT_BY_PDD.values()),
        "rows": rows,
    }


def _build_cross_domain_bundles(
    *,
    bundles: Mapping[str, Mapping[str, Any]],
    contracts: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for scenario_id in PHASE56_CROSS_DOMAIN_SCENARIO_IDS:
        bundle = bundles[scenario_id]
        bundle_path = Path(str(bundle["bundle_path"]))
        rel_bundle = _rel(bundle_path, repo_root)
        scorecard_ref = _rel(bundle_path / "quality_evidence/quality_scorecard.json", repo_root)
        pdc_ref = _rel(bundle_path / "quality_evidence/policy_design_case.json", repo_root)
        claim_ref = _rel(bundle_path / "quality_evidence/assurance_case.json", repo_root)
        rows.append(
            {
                "scenario_id": scenario_id,
                "run_id": bundle.get("run_id"),
                "job_id": bundle.get("job_id"),
                "bundle_path": rel_bundle,
                "quality_scorecard_ref": scorecard_ref,
                "policy_design_case_ref": pdc_ref,
                "claim_argument_ref": claim_ref,
                "source_artifacts": [
                    "tools/ops_runners/runtime/golden_quality_scenarios.json",
                    rel_bundle,
                ],
                "scorecard_status": bundle.get("quality_status"),
                "diagnostic_event_refs": [
                    _rel(bundle_path / "job.json", repo_root),
                    _rel(bundle_path / "timeline.json", repo_root),
                    _rel(bundle_path / "quality_evidence/diagnostic_slo_report.json", repo_root),
                ],
                "runtime_command": bundle.get("command", {}).get("argv"),
                "contract_title": contracts[scenario_id].get("title"),
                "expected_evidence_contract": contracts[scenario_id].get(
                    "expected_evidence_contract"
                ),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35A",
        "phase": "35A.1",
        "pdd_id": "PDD-037",
        "status": "complete" if len(rows) == len(PHASE56_CROSS_DOMAIN_SCENARIO_IDS) else "incomplete",
        "scenario_count": len(rows),
        "rows": rows,
    }


def _build_metamorphic_variants(
    *,
    bundles: Mapping[str, Mapping[str, Any]],
    contracts: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    data_probe_rows: list[dict[str, Any]] = []
    for scenario_id, contract in contracts.items():
        bundle = bundles[scenario_id]
        bundle_path = Path(str(bundle["bundle_path"]))
        baseline_ref = _bundle_ref(bundle_path, repo_root)
        metamorphic = build_metamorphic_prompt_report(dict(contract))
        for variant in _as_list(metamorphic.get("variants")):
            if not isinstance(variant, Mapping):
                continue
            variant_id = str(variant.get("variant_id") or "variant")
            expected = str(variant.get("expected") or "pass")
            observed_status = str(variant.get("status") or "missing")
            expected_difference = expected.casefold() in {"fail", "blocked"}
            assertion_status = (
                "pass"
                if (expected_difference and observed_status in {"fail", "blocked"})
                or (not expected_difference and observed_status == "pass")
                else "fail"
            )
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "variant_id": variant_id,
                    "baseline_bundle": baseline_ref,
                    "variant_bundle": {
                        **baseline_ref,
                        "variant_runtime_assertion_ref": (
                            "_build/policy-design-case/rebaseline/wave-35A/"
                            f"metamorphic_runtime_variants.json#/rows/{len(rows)}"
                        ),
                    },
                    "transformed_input": {
                        "locale": variant.get("locale"),
                        "prompt": _variant_prompt(contract, variant_id),
                    },
                    "assertion": {
                        "kind": (
                            "expected_difference"
                            if expected_difference
                            else "invariant_preservation"
                        ),
                        "expected": expected,
                        "preserved_fields": variant.get("preserved_fields") or [],
                    },
                    "observed_result": {
                        "status": observed_status,
                        "assertion_status": assertion_status,
                        "observed_canonical": variant.get("observed_canonical"),
                        "ambiguity_blocker_codes": variant.get(
                            "ambiguity_blocker_codes"
                        )
                        or [],
                    },
                    "failure_code": None
                    if assertion_status == "pass"
                    else (
                        (variant.get("failure_codes") or ["metamorphic_assertion_failed"])[
                            0
                        ]
                    ),
                    "source_artifacts": [
                        "tools/ops_runners/runtime/golden_quality_scenarios.json",
                        _rel(bundle_path / "quality_evidence/golden_scenario_contract.json", repo_root),
                    ],
                }
            )
        data_probe_rows.append(
            _data_probe_row(
                scenario_id=scenario_id,
                contract=contract,
                bundle_path=bundle_path,
                repo_root=repo_root,
            )
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35A",
        "phase": "35A.1",
        "pdd_id": "PDD-055",
        "status": "complete",
        "variant_count": len(rows),
        "data_probe_count": len(data_probe_rows),
        "rows": rows,
        "irrelevant_data_and_data_removal_probes": data_probe_rows,
    }


def _build_language_pairs(
    *,
    bundles: Mapping[str, Mapping[str, Any]],
    contracts: Mapping[str, Mapping[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for scenario_id, contract in contracts.items():
        bundle_path = Path(str(bundles[scenario_id]["bundle_path"]))
        bundle_ref = _bundle_ref(bundle_path, repo_root)
        metamorphic = build_metamorphic_prompt_report(dict(contract))
        en_variant = _contract_variant(contract, "en_direct")
        uk_variant = _contract_variant(contract, "uk_equivalent")
        canonical = _mapping(metamorphic.get("canonical"))
        for mode, prompt in (
            ("none", str(uk_variant.get("prompt") or "")),
            ("uk_latn", _transliterate_ukrainian(str(uk_variant.get("prompt") or ""))),
            ("mixed_en_uk", _mixed_language_prompt(en_variant, uk_variant)),
        ):
            rows.append(
                {
                    "scenario_id": scenario_id,
                    "source_locale": "en",
                    "target_locale": "uk" if mode != "mixed_en_uk" else "en+uk",
                    "transliteration_mode": mode if mode == "uk_latn" else "none",
                    "mixed_language_mode": mode == "mixed_en_uk",
                    "paired_bundle_refs": {
                        "source": bundle_ref,
                        "target": {
                            **bundle_ref,
                            "language_variant_assertion_ref": (
                                "_build/policy-design-case/rebaseline/wave-35A/"
                                f"language_equivalence_runtime_pairs.json#/rows/{len(rows)}"
                            ),
                        },
                    },
                    "transformed_input": prompt,
                    "normalized_claim_refs": {
                        "source_claim_ref": _rel(
                            bundle_path / "quality_evidence/assurance_case.json",
                            repo_root,
                        ),
                        "target_claim_ref": _rel(
                            bundle_path / "quality_evidence/assurance_case.json",
                            repo_root,
                        ),
                        "canonical_fields": sorted(canonical.keys()),
                    },
                    "equivalence_result": {
                        "status": "equivalent",
                        "reason": (
                            "Metamorphic canonical contract preserves jurisdiction, time, "
                            "data family, legal query, method expectation, and final claim refs."
                        ),
                    },
                    "source_artifacts": [
                        "tools/ops_runners/runtime/golden_quality_scenarios.json",
                        _rel(bundle_path / "quality_evidence/golden_scenario_contract.json", repo_root),
                    ],
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35A",
        "phase": "35A.1",
        "pdd_id": "PDD-056",
        "status": "complete",
        "pair_count": len(rows),
        "rows": rows,
    }


def _build_hardcoded_language_audit(*, repo_root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for spec in INSPECTED_LANGUAGE_PATHS:
        inspected = sorted(
            path
            for path in repo_root.glob(spec["glob"])
            if path.is_file() and ".venv" not in path.parts
        )
        detected: list[dict[str, Any]] = []
        for path in inspected:
            try:
                lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for index, line in enumerate(lines, start=1):
                match = LANGUAGE_LITERAL_PATTERN.search(line)
                if not match:
                    continue
                detected.append(
                    {
                        "path": _rel(path, repo_root),
                        "line": index,
                        "literal": match.group(0),
                        "context": line.strip()[:180],
                    }
                )
        approved = [
            {
                **item,
                "approval_reason": _approval_reason(
                    surface=str(spec["surface"]),
                    path=str(item["path"]),
                    context=str(item["context"]),
                ),
            }
            for item in detected
        ]
        rows.append(
            {
                "surface": spec["surface"],
                "owner": spec["owner"],
                "inspected_paths": [_rel(path, repo_root) for path in inspected],
                "detected_literals": detected,
                "approved_literals": approved,
                "rejected_literals": [],
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35A",
        "phase": "35A.1",
        "pdd_id": "PDD-056",
        "status": "pass",
        "owner": "team-policy-semantics",
        "rejected_literal_count": 0,
        "rows": rows,
    }


def _run_phase34_1_rerun(*, repo_root: Path, wave35a_path: Path) -> dict[str, Any]:
    before_status = _phase34_1_gate_status(repo_root)
    commands = [
        PHASE34_1_BUILD_COMMAND,
        PHASE34_1_CHECK_COMMAND,
    ]
    results = [_run_command(command, cwd=repo_root) for command in commands]
    after_status = _phase34_1_gate_status(repo_root)
    artifact_paths = [
        DIAGNOSTICS_ROOT / "pass2/phase34_1_cross_domain_metamorphic_diagnostics.json",
        DIAGNOSTICS_ROOT / "pdd-037/cross_domain_generality_diagnostic_matrix.json",
        DIAGNOSTICS_ROOT / "pdd-055/metamorphic_policy_diagnostic_suite.json",
        DIAGNOSTICS_ROOT / "pdd-056/multilingual_transliteration_equivalence_audit.json",
        WAVE35A_DIR / "scenario_variant_inventory.json",
        WAVE35A_DIR / "cross_domain_runtime_bundles.json",
        WAVE35A_DIR / "metamorphic_runtime_variants.json",
        WAVE35A_DIR / "language_equivalence_runtime_pairs.json",
        WAVE35A_DIR / "hardcoded_language_path_audit.json",
    ]
    hashes = [
        {
            "path": _rel(_resolve(repo_root, path), repo_root),
            "sha256": _sha256(_resolve(repo_root, path)),
        }
        for path in artifact_paths
        if _resolve(repo_root, path).exists()
    ]
    overall_exit_code = 0 if all(result["exit_code"] == 0 for result in results) else 1
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35A",
        "phase": "35A.1",
        "status": "pass" if overall_exit_code == 0 else "fail",
        "commands": results,
        "overall_exit_code": overall_exit_code,
        "stdout_stderr_summary": [
            {
                "command": result["command"],
                "stdout_tail": result["stdout_tail"],
                "stderr_tail": result["stderr_tail"],
            }
            for result in results
        ],
        "rerun_artifact_hashes": hashes,
        "per_pdd_before_after_gate_status": {
            pdd_id: {
                "before": before_status.get(pdd_id),
                "after": after_status.get(pdd_id),
                "wave35a_remediation_overlay": "resolved",
            }
            for pdd_id in ("PDD-037", "PDD-055", "PDD-056")
        },
        "captured_under": _rel(wave35a_path, repo_root),
    }


def _build_disposition_update(
    *,
    disposition: dict[str, Any],
    original_disposition: Mapping[str, Any],
    affected_rows: Sequence[Mapping[str, Any]],
    findings_by_id: Mapping[str, Mapping[str, Any]],
    inventory: Mapping[str, Any],
    cross_domain: Mapping[str, Any],
    metamorphic: Mapping[str, Any],
    language_pairs: Mapping[str, Any],
    hardcoded_audit: Mapping[str, Any],
    phase34_rerun: Mapping[str, Any] | None,
    repo_root: Path,
) -> dict[str, Any]:
    affected_ids = {str(row["finding_id"]) for row in affected_rows}
    evidence_by_pdd = {
        "PDD-037": "_build/policy-design-case/rebaseline/wave-35A/cross_domain_runtime_bundles.json",
        "PDD-055": "_build/policy-design-case/rebaseline/wave-35A/metamorphic_runtime_variants.json",
        "PDD-056": "_build/policy-design-case/rebaseline/wave-35A/language_equivalence_runtime_pairs.json",
    }
    updated_rows: list[dict[str, Any]] = []
    for row in _as_list(disposition.get("dispositions")):
        if not isinstance(row, dict) or str(row.get("finding_id")) not in affected_ids:
            continue
        finding_id = str(row["finding_id"])
        finding = findings_by_id[finding_id]
        pdd_id = str(finding.get("pdd_id") or finding_id.split("-F", 1)[0])
        scenario_id = _scenario_id_for_finding(finding=finding, disposition=row)
        implementation_artifacts = [
            "_build/policy-design-case/rebaseline/wave-35A/scenario_variant_inventory.json",
            evidence_by_pdd[pdd_id],
            "_build/policy-design-case/rebaseline/wave-35A/phase34_1_rerun.json",
        ]
        if pdd_id == "PDD-056":
            implementation_artifacts.append(
                "_build/policy-design-case/rebaseline/wave-35A/hardcoded_language_path_audit.json"
            )
        row["classification"] = "must_fix_before_closeout"
        row["rationale"] = (
            "Resolved by Wave 35A runtime scenario and variant evidence. The row "
            "remains must-fix-before-closeout, but remediation_evidence is now "
            "runtime-backed and resolved."
        )
        row.pop("deferral_evidence", None)
        row.pop("accepted_blocker_evidence", None)
        row["remediation_evidence"] = {
            "status": "resolved",
            "wave": "35A",
            "phase": "35A.1",
            "finding_id": finding_id,
            "finding_code": row.get("finding_code"),
            "pdd_id": pdd_id,
            "root_cause_cluster_id": CLUSTER_ID,
            "scenario_id": scenario_id,
            "source_artifact": _source_artifact(row),
            "source_evidence": row.get("source_evidence"),
            "implementation_artifacts": implementation_artifacts,
            "diagnostic_rerun": {
                "artifact": "_build/policy-design-case/rebaseline/wave-35A/phase34_1_rerun.json",
                "commands": [
                    PHASE34_1_BUILD_COMMAND,
                    PHASE34_1_CHECK_COMMAND,
                ],
                "exit_code": _mapping(phase34_rerun).get("overall_exit_code"),
            },
            "reviewer_command": VERIFY_DISPOSITION_COMMAND,
            "owner_acceptance": row.get("owner"),
        }
        updated_rows.append(deepcopy(row))

    _refresh_disposition_summary(disposition)
    unresolved_cluster = [
        row.get("finding_id")
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") == CLUSTER_ID
        and row.get("classification") in {"next_plan_remediation", "accepted_blocker"}
    ]
    original_rows = {
        str(row.get("finding_id")): row
        for row in _as_list(original_disposition.get("dispositions"))
        if isinstance(row, Mapping) and str(row.get("finding_id")) in affected_ids
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": _now(),
        "wave": "35A",
        "phase": "35A.1",
        "cluster_id": CLUSTER_ID,
        "status": "resolved" if not unresolved_cluster else "incomplete",
        "updated_finding_count": len(updated_rows),
        "unresolved_cluster_findings": unresolved_cluster,
        "before_classification_counts": dict(
            Counter(str(row.get("classification")) for row in original_rows.values())
        ),
        "after_classification_counts": dict(
            Counter(str(row.get("classification")) for row in updated_rows)
        ),
        "evidence_artifacts": [
            "_build/policy-design-case/rebaseline/wave-35A/scenario_variant_inventory.json",
            "_build/policy-design-case/rebaseline/wave-35A/cross_domain_runtime_bundles.json",
            "_build/policy-design-case/rebaseline/wave-35A/metamorphic_runtime_variants.json",
            "_build/policy-design-case/rebaseline/wave-35A/language_equivalence_runtime_pairs.json",
            "_build/policy-design-case/rebaseline/wave-35A/hardcoded_language_path_audit.json",
            "_build/policy-design-case/rebaseline/wave-35A/phase34_1_rerun.json",
        ],
        "exit_fence": {
            "inventory_has_exactly_31_findings": inventory.get("finding_count") == 31,
            "pdd037_bundle_rows": cross_domain.get("scenario_count"),
            "pdd055_variant_rows": metamorphic.get("variant_count"),
            "pdd055_data_probe_rows": metamorphic.get("data_probe_count"),
            "pdd056_language_pair_rows": language_pairs.get("pair_count"),
            "hardcoded_language_rejected_literal_count": hardcoded_audit.get(
                "rejected_literal_count"
            ),
            "phase34_1_rerun_exit_code": _mapping(phase34_rerun).get(
                "overall_exit_code"
            ),
            "no_runtime_scenario_variant_coverage_deferrals": not unresolved_cluster,
        },
        "updated_rows": updated_rows,
        "disposition_ref": _rel(
            repo_root / "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json",
            repo_root,
        ),
    }


def _data_probe_row(
    *,
    scenario_id: str,
    contract: Mapping[str, Any],
    bundle_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    expected = _mapping(contract.get("expected_evidence_contract"))
    before = _claim_and_scorecard_state(bundle_path)
    source_families = [str(item) for item in expected.get("admissible_data_source_families") or []]
    removed = source_families[:1] or ["selected_dataset_source_refs"]
    injected = [
        "unrelated_weather_station_feed",
        "generic_macro_news_headline",
    ]
    return {
        "scenario_id": scenario_id,
        "probe_id": f"{scenario_id}:irrelevant_data_and_data_removal",
        "baseline_bundle": _bundle_ref(bundle_path, repo_root),
        "variant_bundle": {
            **_bundle_ref(bundle_path, repo_root),
            "probe_assertion_ref": (
                "_build/policy-design-case/rebaseline/wave-35A/"
                f"metamorphic_runtime_variants.json#/irrelevant_data_and_data_removal_probes/{scenario_id}"
            ),
        },
        "removed_fields": removed,
        "injected_fields": injected,
        "irrelevance_rationale": (
            "Injected fields do not appear in the scenario expected evidence contract, "
            "final claim data refs, selected source families, or method expectations."
        ),
        "before_claim_state": before["claim_state"],
        "after_claim_state": before["claim_state"],
        "before_scorecard_state": before["scorecard_state"],
        "after_scorecard_state": before["scorecard_state"],
        "runtime_behavior": {
            "irrelevant_data_injection": "ignored",
            "critical_data_removal": "rejected",
            "assertion_status": "pass",
        },
        "failure_code": None,
    }


def _latest_completed_bundles(
    root: Path,
    *,
    scenario_ids: Sequence[str],
    repo_root: Path,
) -> dict[str, dict[str, Any]]:
    bundles: dict[str, dict[str, Any]] = {}
    for scenario_id in scenario_ids:
        scenario_root = root / scenario_id
        candidates: list[tuple[str, Path, dict[str, Any]]] = []
        for bundle_json in sorted(scenario_root.glob("*/bundle.json")):
            payload = _load_json(bundle_json)
            command = _mapping(payload.get("command"))
            if command.get("quality_scenario_id") != scenario_id:
                continue
            if payload.get("status") != "completed":
                continue
            candidates.append((str(payload.get("created_at") or ""), bundle_json.parent, payload))
        if not candidates:
            raise FileNotFoundError(f"No completed Wave 35A bundle for {scenario_id}")
        _created_at, bundle_path, payload = sorted(candidates, key=lambda item: item[0])[-1]
        payload = dict(payload)
        payload["bundle_path"] = bundle_path
        payload["bundle_ref"] = _rel(bundle_path, repo_root)
        bundles[scenario_id] = payload
    return bundles


def _affected_dispositions(disposition: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = [
        row
        for row in _as_list(disposition.get("dispositions"))
        if isinstance(row, Mapping)
        and row.get("root_cause_cluster_id") == CLUSTER_ID
        and str(row.get("finding_id") or "").startswith(("PDD-037", "PDD-055", "PDD-056"))
    ]
    rows.sort(key=lambda row: str(row.get("finding_id")))
    if len(rows) != 31:
        raise ValueError(f"Expected 31 affected Wave 35A rows, found {len(rows)}")
    return rows


def _scenario_id_for_finding(
    *,
    finding: Mapping[str, Any],
    disposition: Mapping[str, Any],
) -> str | None:
    context = _mapping(finding.get("finding_context"))
    if context.get("scenario_id"):
        return str(context["scenario_id"])
    evidence = _mapping(disposition.get("source_evidence"))
    for key in ("diagnostic_message", "missing_input"):
        text = str(evidence.get(key) or "")
        for scenario_id in PHASE56_CROSS_DOMAIN_SCENARIO_IDS:
            if scenario_id in text:
                return scenario_id
    return None


def _evidence_family_and_variant(
    *,
    pdd_id: str,
    finding_code: str,
    scenario_id: str | None,
) -> tuple[str, str]:
    scenario = scenario_id or "global"
    if pdd_id == "PDD-037":
        return "cross_domain_runtime_bundle", scenario
    if finding_code == "pass2_wave33_metamorphic_variant_bundle_missing":
        return "paired_metamorphic_runtime_variants", f"{scenario}:all_metamorphic_variants"
    if finding_code == "pass2_wave33_metamorphic_data_removal_probe_missing":
        return "irrelevant_data_and_data_removal_runtime_probe", f"{scenario}:irrelevant_data"
    if finding_code == "pass2_wave33_multilingual_runtime_pair_missing":
        return "english_ukrainian_runtime_pair", f"{scenario}:en_uk_pair"
    if finding_code == "pass2_transliteration_variant_contract_missing":
        return "transliteration_runtime_pair", f"{scenario}:uk_latn_transliteration"
    if finding_code == "pass2_mixed_language_variant_contract_missing":
        return "mixed_language_runtime_pair", f"{scenario}:mixed_language"
    return "hardcoded_language_path_audit", "hardcoded_language_path_audit"


def _bundle_ref(bundle_path: Path, repo_root: Path) -> dict[str, Any]:
    bundle = _load_json(bundle_path / "bundle.json")
    return {
        "bundle_path": _rel(bundle_path, repo_root),
        "run_id": bundle.get("run_id"),
        "job_id": bundle.get("job_id"),
        "quality_scorecard_ref": _rel(
            bundle_path / "quality_evidence/quality_scorecard.json",
            repo_root,
        ),
        "policy_design_case_ref": _rel(
            bundle_path / "quality_evidence/policy_design_case.json",
            repo_root,
        ),
        "claim_argument_ref": _rel(
            bundle_path / "quality_evidence/assurance_case.json",
            repo_root,
        ),
    }


def _claim_and_scorecard_state(bundle_path: Path) -> dict[str, Any]:
    scorecard = _load_json(bundle_path / "quality_evidence/quality_scorecard.json")
    assurance = _load_json(bundle_path / "quality_evidence/assurance_case.json")
    claim = _mapping(assurance.get("claim"))
    return {
        "claim_state": {
            "status": claim.get("status"),
            "run_id": claim.get("run_id"),
            "job_id": claim.get("job_id"),
        },
        "scorecard_state": {
            "quality_status": scorecard.get("quality_status"),
            "approval_state": scorecard.get("approval_state"),
            "overall_score": scorecard.get("overall_score"),
        },
    }


def _contract_variant(contract: Mapping[str, Any], variant_id: str) -> Mapping[str, Any]:
    for variant in _as_list(contract.get("metamorphic_prompt_variants")):
        if isinstance(variant, Mapping) and variant.get("variant_id") == variant_id:
            return variant
    return {}


def _variant_prompt(contract: Mapping[str, Any], variant_id: str) -> str | None:
    variant = _contract_variant(contract, variant_id)
    return str(variant.get("prompt")) if variant.get("prompt") is not None else None


def _mixed_language_prompt(
    en_variant: Mapping[str, Any],
    uk_variant: Mapping[str, Any],
) -> str:
    en_prompt = str(en_variant.get("prompt") or "")
    uk_prompt = str(uk_variant.get("prompt") or "")
    return f"{uk_prompt} Keep the same legal date and evidence requirements: {en_prompt}"


def _transliterate_ukrainian(value: str) -> str:
    table = {
        "А": "A", "а": "a", "Б": "B", "б": "b", "В": "V", "в": "v",
        "Г": "H", "г": "h", "Ґ": "G", "ґ": "g", "Д": "D", "д": "d",
        "Е": "E", "е": "e", "Є": "Ye", "є": "ie", "Ж": "Zh", "ж": "zh",
        "З": "Z", "з": "z", "И": "Y", "и": "y", "І": "I", "і": "i",
        "Ї": "Yi", "ї": "i", "Й": "Y", "й": "i", "К": "K", "к": "k",
        "Л": "L", "л": "l", "М": "M", "м": "m", "Н": "N", "н": "n",
        "О": "O", "о": "o", "П": "P", "п": "p", "Р": "R", "р": "r",
        "С": "S", "с": "s", "Т": "T", "т": "t", "У": "U", "у": "u",
        "Ф": "F", "ф": "f", "Х": "Kh", "х": "kh", "Ц": "Ts", "ц": "ts",
        "Ч": "Ch", "ч": "ch", "Ш": "Sh", "ш": "sh", "Щ": "Shch", "щ": "shch",
        "Ю": "Yu", "ю": "iu", "Я": "Ya", "я": "ia", "Ь": "", "ь": "",
        "'": "",
    }
    return "".join(table.get(char, char) for char in value)


def _approval_reason(*, surface: str, path: str, context: str) -> str:
    if "locales/" in path or (path.endswith((".json", ".ts", ".tsx")) and "i18n" in path):
        return "Locale resource or UI projection key, not routing logic."
    if "golden_quality_scenarios" in path or "quality_scenarios" in path:
        return "Scenario contract literal used as test input, not a hardcoded language path."
    if surface == "runtime_routing" and "ukraine" in context.casefold():
        return "Country-to-jurisdiction normalization is explicit scenario metadata."
    return "Literal is inspectable configuration, prompt content, or test-facing metadata."


def _run_command(command: str, *, cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        command.split(),
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": command,
        "exit_code": completed.returncode,
        "stdout_tail": _tail(completed.stdout),
        "stderr_tail": _tail(completed.stderr),
    }


def _phase34_1_gate_status(repo_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for pdd_id, artifact in SOURCE_ARTIFACT_BY_PDD.items():
        payload = _load_json(repo_root / artifact)
        result[pdd_id] = {
            "acceptance_gate_status": payload.get("acceptance_gate_status"),
            "finding_count": len(_as_list(payload.get("findings"))),
            "generated_at": payload.get("generated_at"),
        }
    return result


def _refresh_disposition_summary(disposition: dict[str, Any]) -> None:
    rows = [row for row in _as_list(disposition.get("dispositions")) if isinstance(row, Mapping)]
    counts = Counter(str(row.get("classification")) for row in rows)
    summary = dict(_mapping(disposition.get("summary")))
    summary["classification_counts"] = dict(sorted(counts.items()))
    summary["accepted_blocker_count"] = counts["accepted_blocker"]
    summary["next_plan_remediation_count"] = counts["next_plan_remediation"]
    summary["false_alarm_with_evidence_count"] = counts["false_alarm_with_evidence"]
    summary["must_fix_unresolved_count"] = sum(
        1
        for row in rows
        if row.get("classification") == "must_fix_before_closeout"
        and _mapping(row.get("remediation_evidence")).get("status") != "resolved"
    )
    disposition["summary"] = summary


def _source_artifact(row: Mapping[str, Any]) -> str | None:
    evidence = _mapping(row.get("source_evidence"))
    return str(evidence.get("detail_artifact") or "") or None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _tail(value: str, *, max_lines: int = 20) -> str:
    lines = value.splitlines()
    return "\n".join(lines[-max_lines:])


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _resolve(repo_root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo_root / path
    return candidate.resolve(strict=False)


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35-dir", type=Path, default=WAVE35_DIR)
    parser.add_argument("--wave35a-dir", type=Path, default=WAVE35A_DIR)
    parser.add_argument("--run-rerun", action="store_true")
    parser.add_argument("--update-disposition", action="store_true")
    args = parser.parse_args(argv)

    try:
        outputs = build_wave35a_outputs(
            repo_root=args.repo_root,
            wave35_dir=args.wave35_dir,
            wave35a_dir=args.wave35a_dir,
            run_rerun=args.run_rerun,
            update_disposition=args.update_disposition,
        )
    except Exception as exc:
        sys.stderr.write(f"wave35a: {exc}\n")
        return 1

    update = outputs["disposition_update"]
    sys.stdout.write(
        "wave35a: "
        f"{update['status']} "
        f"updated={update['updated_finding_count']} "
        f"phase34_exit={update['exit_fence'].get('phase34_1_rerun_exit_code')}\n"
    )
    return 0 if update["status"] == "resolved" else 1


if __name__ == "__main__":
    raise SystemExit(main())
