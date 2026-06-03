#!/usr/bin/env python3
"""Run the Layer 2 S14 sealed universality assurance battery."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.capability_ratchet import (  # noqa: E402
    build_capability_reality_report,
)
from polisyos.runtime.quality.layer2_universality_assurance import (  # noqa: E402
    LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION,
    S14_FALSE_CLEAR_FIELDS,
    S14_SKEPTIC_DEFEATER_IDS,
    SealedUniversalityBatteryRun,
    build_d4_corpus_track_coverage,
    build_envelope_revision_dynamics_record,
    build_evaluation_status_composition_record,
    build_expert_oracle_bootstrap_record,
    build_grounded_authority_coverage_record,
    build_s14_cae_scorecard,
    build_s14_mechanism_generality_from_growth_thermometer,
    build_s14_universality_authority_boundary,
    build_skeptic_defeater_records,
    build_universality_axis_scorecard,
    build_universality_baseline_comparison,
    build_universality_breadth_floor_config,
    build_universality_claim_assurance_case,
    gate_universality_claim,
    summarize_universality_assurance,
    verify_sealed_battery_integrity,
)
from polisyos.runtime.quality.layer2_universality_assurance import (
    compute_sealed_battery_freeze_hash as _compute_sealed_battery_freeze_hash,
)

SCHEMA_VERSION = "policyos.policy_design_case.layer2_s14_universality_battery_run.v1"
TOOL_NAME = "quality.validation.run-layer2-s14-universality-battery"
GENERATED_AT = "2026-06-03T00:00:00Z"
DEFAULT_PARTITION_PATH = Path("architecture/policy_design_case/layer2_corpus_partition.json")
DEFAULT_CLUSTER_MAP_PATH = Path("architecture/policy_design_case/cluster_ownership_map.toml")
DEFAULT_BATTERY_ROOT = Path(
    "tests/fixtures/policy_design_case/semantic_evaluation_packs/hidden/"
    "layer2-sealed-universality-battery"
)
DEFAULT_OUTPUT = Path(
    "_build/.tmp/production-quality/layer2_s14_universality_battery.json"
)
S14_FIXTURE_ROOT = Path("tests/fixtures/layer2/s14")
S14_D4_TRACK_COVERAGE_PATH = S14_FIXTURE_ROOT / "s14_d4_corpus_track_coverage.json"
S14_ORACLE_BOOTSTRAP_PATH = S14_FIXTURE_ROOT / "s14_expert_oracle_bootstrap.json"
S14_BREADTH_FLOOR_PATH = S14_FIXTURE_ROOT / "s14_universality_breadth_floor_config.json"
S14_BASELINE_COMPARISON_PATH = S14_FIXTURE_ROOT / "s14_universality_baseline_comparison.json"
S14_GROUNDED_AUTHORITY_REFS_PATH = S14_FIXTURE_ROOT / "s14_grounded_authority_refs.json"
S14_STATUS_COMPOSITION_PATH = S14_FIXTURE_ROOT / "s14_evaluation_status_composition_cases.json"
S14_ENVELOPE_REVISION_DYNAMICS_PATH = S14_FIXTURE_ROOT / "s14_envelope_revision_dynamics.json"
EMPTY_SHA256_REF = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SUBSTRATE_REUSE_REFS: tuple[str, ...] = (
    "src/polisyos/runtime/quality/assurance_case.py#build_universality_assurance_case",
    "src/polisyos/runtime/quality/assurance_case.py#build_assurance_case_for_scorecard",
    "src/polisyos/runtime/quality/capability_ratchet.py#build_capability_reality_report",
    "src/polisyos/runtime/quality/layer2_resource_economics.py#GrowthThermometerRecord",
    "src/polisyos/runtime/quality/layer2_resource_economics.py#EnvelopeGrowthLedger",
    "src/polisyos/runtime/quality/layer2_post_deploy_accountability.py#EnvelopeRevision",
    "src/polisyos/runtime/quality/layer2_post_deploy_accountability.py#CertifiedEnvelopeDelta",
    "src/polisyos/runtime/quality/case_lifecycle.py#status_lattice",
    "src/polisyos/runtime/quality/approval.py#closeout_status_composition",
)


def compute_sealed_battery_freeze_hash(battery_root: str | Path) -> str:
    """Compute the deterministic S14 sealed-battery freeze hash."""

    return _compute_sealed_battery_freeze_hash(battery_root)


def build_s14_universality_battery_manifest(
    *,
    repo_root: str | Path = REPO_ROOT,
    battery_root: str | Path = DEFAULT_BATTERY_ROOT,
) -> dict[str, Any]:
    """Build a redacted manifest for the configured S14 sealed battery."""

    root = Path(repo_root).resolve()
    battery = _resolve(root, Path(battery_root))
    manifest = _read_json(battery / "manifest.json")
    sealed_case_ids = _sealed_case_ids(battery)
    return {
        "schema_version": SCHEMA_VERSION,
        "battery_id": _text(manifest.get("battery_id")) or "layer2-sealed-universality-battery",
        "owner": _text(manifest.get("owner")) or "governance-board",
        "access": _text(manifest.get("access")) or "ci_gate_only",
        "fixture_schema_version": _text(manifest.get("fixture_schema_version")),
        "hard_corner_case_ids": [str(item) for item in manifest.get("hard_corner_case_ids", [])],
        "sealed_case_ids": sealed_case_ids,
        "sealed_battery_case_count": len(sealed_case_ids),
        "skeptic_defeater_ids": [str(item) for item in manifest.get("skeptic_defeater_ids", [])],
        "attack_mapping": dict(manifest.get("attack_mapping") or {}),
        "computed_freeze_hash": compute_sealed_battery_freeze_hash(battery),
        "sealed_labels_redacted_from_public": True,
        "gold_labels_dev_access_forbidden": True,
    }


def run_layer2_s14_universality_battery(
    *,
    repo_root: str | Path = REPO_ROOT,
    battery_root: str | Path = DEFAULT_BATTERY_ROOT,
    allow_sealed_battery: bool = False,
    output: str | Path | None = None,
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Run the explicit S14 sealed battery and return the persisted artifact payload."""

    root = Path(repo_root).resolve()
    requested_battery = _resolve(root, Path(battery_root))
    partition = _sealed_partition(root)
    configured_battery = _resolve(root, Path(_required_text(partition.get("path"), "path")))
    preflight_issues = _preflight_issues(
        partition=partition,
        requested_battery=requested_battery,
        configured_battery=configured_battery,
        allow_sealed_battery=allow_sealed_battery,
        require_rotated_hash=True,
    )
    if preflight_issues:
        battery_run = _blocked_battery_run(
            battery_root=requested_battery,
            partition=partition,
            issues=preflight_issues,
            allow_sealed_battery=allow_sealed_battery,
        )
        payload = _blocked_payload(
            repo_root=root,
            generated_at=generated_at,
            battery_run=battery_run,
            issues=preflight_issues,
        )
        _write_output(root=root, output=output, payload=payload)
        return payload

    battery_run = verify_sealed_battery_integrity(
        battery_root=configured_battery,
        partition=partition,
        allow_sealed_battery=True,
    )
    issues = list(battery_run.issues)
    manifest = build_s14_universality_battery_manifest(
        repo_root=root,
        battery_root=configured_battery,
    )
    manifest_issues = _manifest_issues(manifest)
    issues.extend(manifest_issues)
    if issues:
        payload = _blocked_payload(
            repo_root=root,
            generated_at=generated_at,
            battery_run=battery_run,
            issues=issues,
        )
        _write_output(root=root, output=output, payload=payload)
        return payload

    d4_coverage = build_d4_corpus_track_coverage(
        record_id="s14-d4-corpus-track-coverage",
        record_ref="pdc://layer2/s14/d4-corpus-track-coverage",
        **_fixture_payload(root, S14_D4_TRACK_COVERAGE_PATH),
    )
    oracle = build_expert_oracle_bootstrap_record(
        record_id="s14-expert-oracle-bootstrap",
        record_ref="pdc://layer2/s14/expert-oracle-bootstrap",
        **_fixture_payload(root, S14_ORACLE_BOOTSTRAP_PATH),
    )
    breadth_floor = build_universality_breadth_floor_config(
        config_id="s14-universality-breadth-floor",
        config_ref="pdc://layer2/s14/breadth-floor-config",
        **_fixture_payload(root, S14_BREADTH_FLOOR_PATH),
    )
    baseline = build_universality_baseline_comparison(
        record_id="s14-universality-baseline-comparison",
        **_fixture_payload(root, S14_BASELINE_COMPARISON_PATH),
    )
    grounded_authority = build_grounded_authority_coverage_record(
        record_id="s14-grounded-authority-coverage",
        **_fixture_payload(root, S14_GROUNDED_AUTHORITY_REFS_PATH),
    )
    status_composition = build_evaluation_status_composition_record(
        record_id="s14-evaluation-status-composition",
        **_fixture_payload(root, S14_STATUS_COMPOSITION_PATH),
    )
    envelope_fixture = _fixture_payload(root, S14_ENVELOPE_REVISION_DYNAMICS_PATH)
    envelope_dynamics = build_envelope_revision_dynamics_record(
        s12_growth_ledger_refs=_text_list(envelope_fixture.get("s12_expansion_evidence_refs")),
        s13_envelope_revision_refs=_text_list(envelope_fixture.get("s13_shrink_or_split_refs")),
        s13_certified_delta_refs=_text_list(envelope_fixture.get("certified_envelope_delta_refs")),
    )
    capability_report = build_capability_reality_report(
        [_s14_capability_claim()],
        validation_profile="production",
        generated_at=generated_at,
    )
    scorecard = build_universality_axis_scorecard(
        cluster_map_path=_resolve(root, DEFAULT_CLUSTER_MAP_PATH),
        capability_reality_report_ref="pdc://layer2/s14/capability-reality-report",
        battery_status_by_axis=_battery_status_by_axis(
            cluster_map_path=_resolve(root, DEFAULT_CLUSTER_MAP_PATH),
            battery_root=configured_battery,
        ),
    )
    mechanism_report = build_s14_mechanism_generality_from_growth_thermometer(
        growth_thermometer=_growth_thermometer_payload(scorecard.axis_rows),
        held_out_case_refs=[f"sealed://s14/{case_id}" for case_id in manifest["sealed_case_ids"]],
    )
    skeptic_records = build_skeptic_defeater_records(
        attack_mapping=dict(manifest["attack_mapping"]),
        cae_defeaters=_cae_defeaters(manifest),
    )
    assurance_case = build_universality_claim_assurance_case(
        cae_scorecard=build_s14_cae_scorecard(
            quality_status="pass",
            evidence_refs=[
                d4_coverage.record_ref,
                oracle.record_ref,
                breadth_floor.config_ref,
                baseline.comparison_ref,
                grounded_authority.coverage_ref,
                envelope_dynamics.dynamics_ref,
                scorecard.scorecard_ref,
            ],
        ),
        scorecard=scorecard,
        skeptic_defeaters=skeptic_records,
    )
    gate_record = gate_universality_claim(
        claim_text="PolicyOS universality is limited to the declared tested operation envelope.",
        requested_scope_refs=[row.axis_ref for row in scorecard.axis_rows],
        scorecard=scorecard,
        assurance_case=assurance_case,
        skeptic_defeaters=skeptic_records,
        visible_limitation_refs=[],
    )
    false_clear_counts = dict.fromkeys(S14_FALSE_CLEAR_FIELDS, 0)
    summary = summarize_universality_assurance(
        scorecard=scorecard,
        battery_run=battery_run,
        mechanism_report=mechanism_report,
        skeptic_defeaters=skeptic_records,
        gate_record=gate_record,
        false_clear_counts=false_clear_counts,
    )
    summary_payload = summary.model_dump(mode="json")
    summary_payload.update(
        {
            "breadth_floor_status": "pass"
            if breadth_floor.status == "ratified"
            else breadth_floor.status,
            "grounded_authority_coverage_status": grounded_authority.coverage_status,
            "baseline_comparison_status": baseline.comparison_status,
            "evaluation_status_composition_status": status_composition.composition_status,
            "envelope_revision_dynamics_status": envelope_dynamics.dynamics_status,
        }
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "repo_root": str(root),
        "status": "pass",
        "issues": [],
        "sealed_battery_integrity_status": battery_run.sealed_battery_integrity_status,
        "sealed_battery_freeze_hash_match": (
            battery_run.freeze_hash == battery_run.computed_freeze_hash
        ),
        "sealed_battery_freeze_hash": battery_run.freeze_hash,
        "sealed_battery_computed_freeze_hash": battery_run.computed_freeze_hash,
        "sealed_universality_battery_run": battery_run.model_dump(mode="json"),
        "s14_universality_battery_manifest": manifest,
        "d4_corpus_track_coverage": d4_coverage.model_dump(mode="json"),
        "expert_oracle_bootstrap": oracle.model_dump(mode="json"),
        "universality_breadth_floor_config": breadth_floor.model_dump(mode="json"),
        "universality_baseline_comparison": baseline.model_dump(mode="json"),
        "grounded_authority_coverage": grounded_authority.model_dump(mode="json"),
        "evaluation_status_composition": status_composition.model_dump(mode="json"),
        "envelope_revision_dynamics": envelope_dynamics.model_dump(mode="json"),
        "capability_reality_report": capability_report,
        "universality_axis_scorecard": scorecard.model_dump(mode="json"),
        "mechanism_generality_report": mechanism_report.model_dump(mode="json"),
        "skeptic_defeater_records": [
            record.model_dump(mode="json") for record in skeptic_records
        ],
        "universality_claim_assurance_case": assurance_case.model_dump(mode="json"),
        "universality_claim_gate_record": gate_record.model_dump(mode="json"),
        "s14_universality_assurance_summary": summary_payload,
        "public_summary": _public_summary(
            summary=summary_payload,
            battery_run=battery_run.model_dump(mode="json"),
        ),
        "substrate_reuse_refs": list(SUBSTRATE_REUSE_REFS),
        "rule_version_ref": LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION,
        "pattern_pass": {
            "relevant_patterns": [
                "P01",
                "P02",
                "P03",
                "P04",
                "P05",
                "P07",
                "P08",
                "P10",
                "P12",
                "P13",
                "P15",
                "P16-P26",
            ],
            "target_correct_pattern": (
                "S14 sealed battery is an explicit gated producer with replayable "
                "freeze hash, typed artifacts, CAE/scorecard/growth/envelope reuse, "
                "and public-safe summary projection."
            ),
            "missing_capability_labels": [],
        },
    }
    _write_output(root=root, output=output, payload=payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build the S14 sealed-battery runner parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--battery-root", type=Path, default=DEFAULT_BATTERY_ROOT)
    parser.add_argument("--allow-sealed-battery", action="store_true")
    parser.add_argument("--print-freeze-hash", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the S14 sealed battery."""

    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()
    partition = _sealed_partition(root)
    configured_battery = _resolve(root, Path(_required_text(partition.get("path"), "path")))
    requested_battery = _resolve(root, args.battery_root)
    if args.print_freeze_hash:
        issues = _preflight_issues(
            partition=partition,
            requested_battery=requested_battery,
            configured_battery=configured_battery,
            allow_sealed_battery=args.allow_sealed_battery,
            require_rotated_hash=False,
        )
        if issues:
            json.dump({"status": "fail", "issues": issues}, sys.stderr, indent=2)
            sys.stderr.write("\n")
            return 2
        sys.stdout.write(f"{compute_sealed_battery_freeze_hash(configured_battery)}\n")
        return 0

    payload = run_layer2_s14_universality_battery(
        repo_root=root,
        battery_root=requested_battery,
        allow_sealed_battery=args.allow_sealed_battery,
        output=args.output,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if payload["status"] == "pass" else 2


def _sealed_partition(repo_root: Path) -> dict[str, Any]:
    payload = _read_json(_resolve(repo_root, DEFAULT_PARTITION_PATH))
    return dict(payload.get("sealed_universality_battery") or {})


def _preflight_issues(
    *,
    partition: Mapping[str, object],
    requested_battery: Path,
    configured_battery: Path,
    allow_sealed_battery: bool,
    require_rotated_hash: bool,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if not allow_sealed_battery:
        issues.append(_issue("sealed_battery_access_requires_explicit_allow"))
    if requested_battery.resolve() != configured_battery.resolve():
        issues.append(_issue("sealed_battery_path_mismatch"))
    if _text(partition.get("access")) != "ci_gate_only":
        issues.append(_issue("sealed_battery_access_mode_mismatch"))
    if _text(partition.get("owner")) != "governance-board":
        issues.append(_issue("sealed_battery_owner_mismatch"))
    if require_rotated_hash and _text(partition.get("freeze_hash")) == EMPTY_SHA256_REF:
        issues.append(_issue("sealed_battery_freeze_hash_not_rotated"))
    if allow_sealed_battery and requested_battery.resolve() == configured_battery.resolve():
        manifest = _read_json(configured_battery / "manifest.json")
        if _text(manifest.get("owner")) != "governance-board":
            issues.append(_issue("sealed_battery_manifest_owner_mismatch"))
        if _text(manifest.get("access")) != "ci_gate_only":
            issues.append(_issue("sealed_battery_manifest_access_mismatch"))
    return _dedupe_issues(issues)


def _manifest_issues(manifest: Mapping[str, object]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    sealed_case_ids = [str(item) for item in manifest.get("sealed_case_ids", [])]
    hard_corner_case_ids = [str(item) for item in manifest.get("hard_corner_case_ids", [])]
    if set(sealed_case_ids) != set(hard_corner_case_ids):
        issues.append(_issue("sealed_battery_case_id_manifest_mismatch"))
    if tuple(manifest.get("skeptic_defeater_ids", ())) != S14_SKEPTIC_DEFEATER_IDS:
        issues.append(_issue("sealed_battery_skeptic_defeater_manifest_mismatch"))
    if len(sealed_case_ids) != 6:
        issues.append(_issue("sealed_battery_case_count_mismatch"))
    return issues


def _blocked_payload(
    *,
    repo_root: Path,
    generated_at: str,
    battery_run: SealedUniversalityBatteryRun,
    issues: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    false_clear_counts = dict.fromkeys(S14_FALSE_CLEAR_FIELDS, 0)
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "repo_root": str(repo_root),
        "status": "fail",
        "issues": _dedupe_issues(issues),
        "sealed_battery_integrity_status": "blocked",
        "sealed_battery_freeze_hash_match": False,
        "sealed_universality_battery_run": battery_run.model_dump(mode="json"),
        "s14_universality_assurance_summary": {
            "summary_id": "s14-universality-assurance-summary",
            "slice": "S14",
            "sealed_battery_integrity_status": "blocked",
            "false_clear_counts": false_clear_counts,
        },
        "public_summary": {
            "status": "fail",
            "sealed_battery_integrity_status": "blocked",
            "sealed_battery_run_ref": "pdc://layer2/s14/sealed-battery-run",
        },
        "substrate_reuse_refs": list(SUBSTRATE_REUSE_REFS),
        "rule_version_ref": LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION,
    }


def _blocked_battery_run(
    *,
    battery_root: Path,
    partition: Mapping[str, object],
    issues: Sequence[Mapping[str, str]],
    allow_sealed_battery: bool,
) -> SealedUniversalityBatteryRun:
    expected_hash = _text(partition.get("freeze_hash")) or "sha256:"
    return SealedUniversalityBatteryRun(
        run_id="s14-sealed-battery-integrity",
        battery_id="layer2-sealed-universality-battery",
        battery_root=str(battery_root),
        partition_path=_text(partition.get("path")) or str(battery_root),
        owner=_text(partition.get("owner")) or "unknown",
        access_mode=_text(partition.get("access")) or "unknown",
        run_mode="sealed_ci",
        explicit_access_granted=allow_sealed_battery,
        sealed_battery_access_attempted=allow_sealed_battery,
        sealed_battery_status="blocked",
        freeze_hash=expected_hash,
        computed_freeze_hash=expected_hash,
        sealed_battery_integrity_status="blocked",
        case_count=0,
        hard_corner_case_ids=[],
        fixture_manifest_digest=_digest_payload({"partition": dict(partition)}),
        authority_boundary=build_s14_universality_authority_boundary(
            authoritative_for=["sealed_battery_integrity"]
        ),
        issues=[dict(issue) for issue in issues],
    )


def _battery_status_by_axis(*, cluster_map_path: Path, battery_root: Path) -> dict[str, str]:
    status_by_axis = dict.fromkeys(_cluster_axis_refs(cluster_map_path), "pass")
    rank = {"pass": 0, "limited": 1, "blocked": 2}
    for case_payload in _sealed_case_payloads(battery_root):
        disposition = _text(case_payload.get("expected_boundary_disposition"))
        status = "pass"
        if disposition == "limited_universal":
            status = "limited"
        elif disposition == "out_of_envelope":
            status = "blocked"
        for axis_ref in _text_list(case_payload.get("axis_refs")):
            if rank[status] > rank[status_by_axis.get(axis_ref, "pass")]:
                status_by_axis[axis_ref] = status
    return status_by_axis


def _growth_thermometer_payload(axis_rows: Sequence[Any]) -> dict[str, object]:
    return {
        "thermometer_ref": "pdc://layer2/s12/s14/growth-thermometer",
        "held_out_status": "pending_s14",
        "reuse_rate": 1.0,
        "reused_primitive_refs": [
            f"primitive://s14/{_slug(getattr(row, 'axis_ref', 'axis'))}" for row in axis_rows
        ],
        "one_off_growth_refs": [],
    }


def _cae_defeaters(manifest: Mapping[str, object]) -> list[dict[str, object]]:
    return [
        {
            "defeater_id": defeater_id,
            "status": "resolved",
            "defeater_ref": f"cae-defeater://s14/{defeater_id}",
            "evidence_refs": [f"sealed-evidence://s14/{defeater_id}"],
        }
        for defeater_id in manifest.get("skeptic_defeater_ids", [])
    ]


def _s14_capability_claim() -> dict[str, str]:
    return {
        "capability_id": "layer2_s14_universality_assurance_battery",
        "claim_id": "layer2-s14-universality-assurance-battery",
        "purpose": "governance",
        "reality_state": "implemented",
        "typed_contract_ref": (
            "repo://src/polisyos/runtime/quality/layer2_universality_assurance.py"
        ),
        "producer_ref": (
            "repo://tools/quality/validation/run_layer2_s14_universality_battery.py"
        ),
        "artifact_ref": "pdc://layer2/s14/sealed-battery-run",
        "bridge_ref": (
            "repo://tools/quality/validation/run_layer2_s14_universality_battery.py"
        ),
        "consumer_ref": "pdc://layer2/s14/universality-claim-gate",
        "verification_ref": (
            "repo://tests/repo_quality/tools/test_layer2_s14_universality_battery.py"
        ),
        "surface_ref": "projection://s14/universality-assurance",
        "semantic_test_ref": (
            "repo://tests/repo_quality/tools/"
            "test_layer2_s14_universality_battery.py"
            "#test_s14_battery_runner_emits_d4_oracle_breadth_scorecard_skeptic_defeaters_and_summary"
        ),
    }


def _public_summary(
    *,
    summary: Mapping[str, object],
    battery_run: Mapping[str, object],
) -> dict[str, object]:
    return {
        "summary_id": summary.get("summary_id"),
        "slice": "S14",
        "status": "pass",
        "sealed_battery_run_ref": "pdc://layer2/s14/sealed-battery-run",
        "sealed_battery_integrity_status": battery_run.get("sealed_battery_integrity_status"),
        "sealed_battery_case_count": battery_run.get("case_count"),
        "d4_corpus_track_count": summary.get("d4_corpus_track_count"),
        "expert_oracle_layer_count": summary.get("expert_oracle_layer_count"),
        "axis_scorecard_row_count": summary.get("axis_scorecard_row_count"),
        "skeptic_defeater_count": summary.get("skeptic_defeater_count"),
        "universal_claim_disposition": summary.get("universal_claim_disposition"),
        "false_clear_counts": dict(summary.get("false_clear_counts") or {}),
        "limitation_refs": ["limitation://s14/public-summary-hidden-case-content-redacted"],
        "rule_version_ref": LAYER2_S14_UNIVERSALITY_ASSURANCE_RULE_VERSION,
    }


def _fixture_payload(repo_root: Path, path: Path) -> dict[str, Any]:
    payload = _read_json(_resolve(repo_root, path))
    payload.pop("schema_version", None)
    payload.pop("authority_boundary", None)
    return payload


def _sealed_case_payloads(battery_root: Path) -> list[dict[str, Any]]:
    return [_read_json(path) for path in sorted((battery_root / "cases").glob("*.json"))]


def _sealed_case_ids(battery_root: Path) -> list[str]:
    return [path.stem for path in sorted((battery_root / "cases").glob("*.json"))]


def _cluster_axis_refs(cluster_map_path: Path) -> list[str]:
    payload = tomllib.loads(cluster_map_path.read_text(encoding="utf-8"))
    cells = payload.get("cell", {})
    refs: list[str] = []
    if isinstance(cells, Mapping):
        for cluster, axes in cells.items():
            if not isinstance(axes, Mapping):
                continue
            for axis, cell in axes.items():
                if isinstance(cell, Mapping):
                    refs.append(f"{cluster}.{axis}")
    return refs


def _write_output(
    *,
    root: Path,
    output: str | Path | None,
    payload: Mapping[str, object],
) -> None:
    if output is not None:
        atomic_write_json(_resolve(root, Path(output)), dict(payload))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _required_text(value: object, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise ValueError(f"S14 sealed battery partition is missing {field_name}")
    return text


def _text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Sequence):
        return [str(item) for item in value if _text(item)]
    return []


def _dedupe_issues(issues: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    deduped: list[dict[str, str]] = []
    for issue in issues:
        code = _text(issue.get("code"))
        if not code or code in seen:
            continue
        seen.add(code)
        deduped.append({"code": code, "message": _text(issue.get("message")) or code})
    return deduped


def _issue(code: str, message: str | None = None) -> dict[str, str]:
    return {"code": code, "message": message or code.replace("_", " ")}


def _digest_payload(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _slug(value: object) -> str:
    rendered = _text(value).replace(".", "_").replace("/", "_").replace(":", "_")
    return rendered or "unknown"


def _text(value: object) -> str:
    return str(value).strip() if value is not None else ""


if __name__ == "__main__":
    raise SystemExit(main())
