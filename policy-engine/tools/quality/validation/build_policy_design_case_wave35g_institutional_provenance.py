#!/usr/bin/env python3
"""Build Wave 35G.4 institutional provenance boundary ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = (
    "policyos.policy_design_case.wave35g.institutional_provenance_boundary.v1"
)
TOOL_NAME = (
    "quality.validation.build-policy-design-case-wave35g-institutional-provenance"
)
WAVE35E_DIR = Path("_build/policy-design-case/rebaseline/wave-35E")
WAVE35F_DIR = Path("_build/policy-design-case/rebaseline/wave-35F")
WAVE35G_DIR = Path("_build/policy-design-case/rebaseline/wave-35G")
OUTPUT_FILENAME = "institutional_provenance_boundary_ledger.json"

AFFECTED_FINDING_IDS = (
    "PDD-097-F001",
    "PDD-097-F002",
    "PDD-097-F003",
    "PDD-099-F001",
    "PDD-099-F002",
    "PDD-099-F003",
)
ALLOWED_EVIDENCE_AUTHORITIES = (
    "runtime_emitted",
    "runtime_derived",
    "test_observed",
    "not_closeout_authority",
)
RUNTIME_CLOSEOUT_AUTHORITIES = {
    "runtime_emitted",
    "runtime_derived",
    "test_observed",
}
SURFACE_BY_PDD = {
    "PDD-097": "implementation_feasibility",
    "PDD-099": "contestability_appeals",
}
SOURCE_ARTIFACTS = (
    "_build/policy-design-case/rebaseline/wave-35F/"
    "runtime_enforcement_gap_ledger.json",
    "_build/policy-design-case/rebaseline/wave-35E/"
    "implementation_feasibility_ledger.json",
    "_build/policy-design-case/rebaseline/wave-35E/"
    "contestability_appeals_ledger.json",
    "_build/policy-design-case/rebaseline/wave-33/readiness.json",
    "quality_evidence/evidence_provenance_manifest.json",
    "quality_evidence/public_export_bundle.json",
    "quality_evidence/continuous_governance_reissue_report.json",
    "quality_evidence/continuous_governance_stale_report.json",
    "quality_evidence/continuous_governance_withdraw_report.json",
)


def build_institutional_provenance_boundary_ledger(
    *,
    repo_root: Path = REPO_ROOT,
    wave35e_dir: Path = WAVE35E_DIR,
    wave35f_dir: Path = WAVE35F_DIR,
    wave35g_dir: Path = WAVE35G_DIR,
) -> dict[str, Any]:
    """Build and write the Phase 35G.4 boundary ledger."""

    repo_root = repo_root.resolve()
    wave35e_path = _resolve(repo_root, wave35e_dir)
    wave35f_path = _resolve(repo_root, wave35f_dir)
    wave35g_path = _resolve(repo_root, wave35g_dir)
    wave35g_path.mkdir(parents=True, exist_ok=True)

    gap_ledger = _load_json(wave35f_path / "runtime_enforcement_gap_ledger.json")
    implementation = _load_json(
        wave35e_path / "implementation_feasibility_ledger.json"
    )
    contestability = _load_json(wave35e_path / "contestability_appeals_ledger.json")
    generated_at = _utc_now()

    rows = _build_rows(
        repo_root=repo_root,
        gap_ledger=gap_ledger,
        implementation=implementation,
        contestability=contestability,
    )
    class_counts = Counter(str(row["evidence_authority"]) for row in rows)
    runtime_owned_count = sum(
        1 for row in rows if row.get("runtime_owned_provenance_present") is True
    )
    final_publication_allowed = any(
        row.get("manual_ledger_source_class") == "manual_assertion"
        and row.get("counts_toward_final_publication") is True
        for row in rows
    )
    deterministic_closeout_allowed = any(
        row.get("manual_ledger_source_class") == "manual_assertion"
        and row.get("counts_toward_deterministic_closeout") is True
        for row in rows
    )
    output_path = wave35g_path / OUTPUT_FILENAME
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": generated_at,
        "wave": "35G",
        "phase": "35G.4",
        "status": (
            "complete_with_runtime_provenance"
            if runtime_owned_count == len(rows)
            else "complete_with_enforceable_boundaries"
        ),
        "required_output_artifact": _rel_path(output_path, repo_root),
        "affected_findings": list(AFFECTED_FINDING_IDS),
        "source_artifacts": list(SOURCE_ARTIFACTS),
        "allowed_evidence_authorities": list(ALLOWED_EVIDENCE_AUTHORITIES),
        "summary": {
            "affected_finding_count": len(AFFECTED_FINDING_IDS),
            "source_ledger_row_count": len(_source_ledger_row_refs(rows)),
            "runtime_owned_provenance_count": runtime_owned_count,
            "not_closeout_authority_count": class_counts.get(
                "not_closeout_authority",
                0,
            ),
            "final_publication_allowed_by_manual_ledgers": final_publication_allowed,
            "deterministic_closeout_allowed_by_manual_ledgers": (
                deterministic_closeout_allowed
            ),
        },
        "publication_and_closeout_decision": {
            "manual_institutional_ledgers_count_toward_final_publication": (
                final_publication_allowed
            ),
            "manual_institutional_ledgers_count_toward_deterministic_closeout": (
                deterministic_closeout_allowed
            ),
            "runtime_owned_provenance_required": True,
            "boundary_decision": (
                "runtime_owned_provenance_required"
                if runtime_owned_count == len(rows)
                else "not_closeout_authority_until_runtime_owned_provenance"
            ),
        },
        "rows": rows,
    }
    atomic_write_json(output_path, payload)
    return payload


def validate_institutional_provenance_boundary_ledger(
    payload: Mapping[str, Any],
) -> list[str]:
    """Validate the Phase 35G.4 ledger invariants."""

    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("institutional boundary ledger schema_version drifted")
    if payload.get("wave") != "35G":
        errors.append("institutional boundary ledger wave must be 35G")
    if payload.get("phase") != "35G.4":
        errors.append("institutional boundary ledger phase must be 35G.4")
    if payload.get("tool") != TOOL_NAME:
        errors.append("institutional boundary ledger tool drifted")

    rows = _mapping_rows(payload, "rows")
    finding_ids = {str(row.get("finding_id")) for row in rows}
    expected_findings = set(AFFECTED_FINDING_IDS)
    if finding_ids != expected_findings:
        errors.append(
            "institutional boundary rows must cover the affected findings: "
            f"missing={sorted(expected_findings - finding_ids)} "
            f"extra={sorted(finding_ids - expected_findings)}"
        )

    for row in rows:
        row_id = str(row.get("row_id") or "<unknown>")
        authority = str(row.get("evidence_authority") or "")
        if authority not in ALLOWED_EVIDENCE_AUTHORITIES:
            errors.append(f"{row_id}: unknown evidence authority {authority!r}")
        if not row.get("explicit_caveat"):
            errors.append(f"{row_id}: missing explicit caveat")

        counts_publication = row.get("counts_toward_final_publication") is True
        counts_closeout = row.get("counts_toward_deterministic_closeout") is True
        has_runtime_authority = row_has_closeout_authority(row)
        if counts_publication and not has_runtime_authority:
            errors.append(
                f"{row_id}: manual institutional ledger cannot count toward final "
                "publication without runtime-owned provenance"
            )
        if counts_closeout and not has_runtime_authority:
            errors.append(
                f"{row_id}: manual institutional ledger cannot count toward "
                "deterministic closeout without runtime-owned provenance"
            )

        boundary = row.get("enforceable_boundary")
        if not has_runtime_authority:
            if not isinstance(boundary, Mapping) or boundary.get(
                "boundary_decision"
            ) != "not_closeout_authority":
                errors.append(
                    f"{row_id}: missing enforceable not_closeout_authority boundary"
                )
            elif (
                boundary.get("blocks_final_publication_closeout_authority") is not True
                or boundary.get("blocks_deterministic_closeout_authority") is not True
            ):
                errors.append(
                    f"{row_id}: boundary must block publication and deterministic "
                    "closeout authority"
                )
        elif boundary not in (None, {}):
            errors.append(f"{row_id}: runtime-owned authority must not need boundary")
    return errors


def row_has_closeout_authority(row: Mapping[str, Any]) -> bool:
    authority = str(row.get("evidence_authority") or "")
    if authority not in RUNTIME_CLOSEOUT_AUTHORITIES:
        return False
    if row.get("runtime_owned_provenance_present") is not True:
        return False
    provenance = _mapping(row.get("runtime_owned_provenance"))
    producer = str(provenance.get("producer") or provenance.get("producer_id") or "")
    refs = [
        *_as_string_list(provenance.get("event_refs")),
        *_as_string_list(provenance.get("artifact_refs")),
        *_as_string_list(provenance.get("trace_refs")),
    ]
    return bool(producer and refs)


def _build_rows(
    *,
    repo_root: Path,
    gap_ledger: Mapping[str, Any],
    implementation: Mapping[str, Any],
    contestability: Mapping[str, Any],
) -> list[dict[str, Any]]:
    impl_rows = _as_list(implementation.get("rows"))
    appeal_rows = _as_list(contestability.get("rows"))
    implementation_row = _mapping(impl_rows[0]) if impl_rows else {}
    appeal_by_finding = {
        finding_id: _mapping(row)
        for finding_id, row in zip(AFFECTED_FINDING_IDS[3:], appeal_rows, strict=False)
    }
    gap_rows = [
        row
        for row in _mapping_rows(gap_ledger, "rows")
        if row.get("finding_id") in AFFECTED_FINDING_IDS
        and Path(str(row.get("artifact_path") or "")).name
        in {
            "implementation_feasibility_ledger.json",
            "contestability_appeals_ledger.json",
        }
    ]
    gap_by_finding = {str(row.get("finding_id")): row for row in gap_rows}

    rows: list[dict[str, Any]] = []
    for finding_id in AFFECTED_FINDING_IDS:
        pdd_id = "-".join(finding_id.split("-")[:2])
        surface = SURFACE_BY_PDD[pdd_id]
        if surface == "implementation_feasibility":
            source_row = implementation_row
            source_ref = (
                "_build/policy-design-case/rebaseline/wave-35E/"
                "implementation_feasibility_ledger.json#/rows/0"
            )
        else:
            source_row = appeal_by_finding.get(finding_id, {})
            source_index = max(0, AFFECTED_FINDING_IDS[3:].index(finding_id))
            source_ref = (
                "_build/policy-design-case/rebaseline/wave-35E/"
                f"contestability_appeals_ledger.json#/rows/{source_index}"
            )
        gap = gap_by_finding.get(finding_id, {})
        rows.append(
            _boundary_row(
                repo_root=repo_root,
                finding_id=finding_id,
                pdd_id=pdd_id,
                surface=surface,
                source_row=source_row,
                source_ledger_row_ref=source_ref,
                gap=gap,
            )
        )
    return rows


def _boundary_row(
    *,
    repo_root: Path,
    finding_id: str,
    pdd_id: str,
    surface: str,
    source_row: Mapping[str, Any],
    source_ledger_row_ref: str,
    gap: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_provenance = _runtime_owned_provenance(source_row)
    runtime_present = bool(runtime_provenance)
    authority = "runtime_emitted" if runtime_present else "not_closeout_authority"
    row_seed = "|".join((finding_id, source_ledger_row_ref, surface))
    row: dict[str, Any] = {
        "row_id": "W35G4-INST-" + _stable_digest(row_seed),
        "wave35f_gap_id": gap.get("gap_id"),
        "wave35f_classification_row_id": gap.get("classification_row_id"),
        "pdd_id": pdd_id,
        "finding_id": finding_id,
        "surface": surface,
        "source_ledger_row_ref": source_ledger_row_ref,
        "source_ledger_row_key": _source_row_key(surface, source_row),
        "manual_ledger_source_class": gap.get("evidence_authority_class")
        or "manual_assertion",
        "evidence_authority": authority,
        "runtime_owned_provenance_present": runtime_present,
        "runtime_owned_provenance": runtime_provenance,
        "source_refs": _source_refs(repo_root, source_row, gap),
        "counts_toward_final_publication": runtime_present,
        "counts_toward_deterministic_closeout": runtime_present,
        "explicit_caveat": _caveat(surface),
        "required_runtime_provenance": _required_runtime_provenance(surface),
        "enforceable_boundary": None,
    }
    if not row_has_closeout_authority(row):
        row["evidence_authority"] = "not_closeout_authority"
        row["runtime_owned_provenance_present"] = False
        row["runtime_owned_provenance"] = None
        row["counts_toward_final_publication"] = False
        row["counts_toward_deterministic_closeout"] = False
        row["enforceable_boundary"] = {
            "boundary_id": "W35G4-BOUNDARY-" + _stable_digest(row_seed),
            "boundary_decision": "not_closeout_authority",
            "source_wave35f_boundary_id": _mapping(gap.get("accepted_boundary")).get(
                "boundary_id"
            ),
            "blocks_final_publication_closeout_authority": True,
            "blocks_deterministic_closeout_authority": True,
            "publication_readiness_effect": (
                "Final publication remains blocked from treating the manual "
                "institutional ledger as proof until runtime-owned provenance is "
                "present."
            ),
            "closeout_effect": (
                "Deterministic closeout must exclude this ledger row unless a "
                "runtime-emitted, runtime-derived, or test-observed provenance "
                "record is attached."
            ),
            "caveat": _caveat(surface),
        }
    return row


def _runtime_owned_provenance(row: Mapping[str, Any]) -> dict[str, Any] | None:
    for key in (
        "runtime_owned_provenance",
        "runtime_provenance",
        "runtime_lifecycle_provenance",
    ):
        provenance = _mapping(row.get(key))
        if _has_runtime_provenance(provenance):
            return dict(provenance)
    return None


def _has_runtime_provenance(provenance: Mapping[str, Any]) -> bool:
    producer = str(provenance.get("producer") or provenance.get("producer_id") or "")
    refs = [
        *_as_string_list(provenance.get("event_refs")),
        *_as_string_list(provenance.get("artifact_refs")),
        *_as_string_list(provenance.get("trace_refs")),
    ]
    return bool(producer and refs)


def _source_row_key(surface: str, row: Mapping[str, Any]) -> str:
    if surface == "implementation_feasibility":
        return str(row.get("recommendation_id") or "implementation_feasibility")
    return str(row.get("appeal_id") or "contestability_appeal")


def _source_refs(
    repo_root: Path,
    source_row: Mapping[str, Any],
    gap: Mapping[str, Any],
) -> list[str]:
    refs = set(SOURCE_ARTIFACTS)
    refs.update(_collect_ref_strings(source_row))
    refs.update(_collect_ref_strings(gap))
    return sorted(ref for ref in refs if _is_reasonable_ref(ref, repo_root))


def _is_reasonable_ref(value: str, repo_root: Path) -> bool:
    if len(value) > 360:
        return False
    if value.startswith("/"):
        return value.startswith(repo_root.as_posix())
    return True


def _required_runtime_provenance(surface: str) -> str:
    if surface == "implementation_feasibility":
        return (
            "runtime-owned implementation feasibility provenance with producer, "
            "event refs, artifact refs, claim binding, actor, risk, and "
            "monitoring outcome refs"
        )
    return (
        "runtime-owned contestability lifecycle outcome provenance with producer, "
        "event refs, artifact refs, appeal disposition, lifecycle transition, "
        "and publication-state effect"
    )


def _caveat(surface: str) -> str:
    if surface == "implementation_feasibility":
        return (
            "The implementation feasibility ledger is a manual remediation ledger; "
            "it may guide review but is not institutional proof for final "
            "publication or deterministic closeout until runtime-owned provenance "
            "is attached."
        )
    return (
        "The contestability appeals ledger is a manual remediation ledger; it may "
        "describe expected lifecycle outcomes but cannot authorize closeout until "
        "runtime-owned appeal outcome provenance is attached."
    )


def _source_ledger_row_refs(rows: Sequence[Mapping[str, Any]]) -> set[str]:
    return {str(row.get("source_ledger_row_ref")) for row in rows}


def _collect_ref_strings(value: object) -> list[str]:
    refs: set[str] = set()

    def visit(item: object) -> None:
        if isinstance(item, str):
            if _looks_like_ref(item):
                refs.add(item)
        elif isinstance(item, Mapping):
            for child in item.values():
                visit(child)
        elif isinstance(item, list | tuple):
            for child in item:
                visit(child)

    visit(value)
    return sorted(refs)


def _looks_like_ref(value: str) -> bool:
    markers = (
        "/",
        ".json",
        ".md",
        ".py",
        ".ts",
        ".tsx",
        "sha256:",
        "cas://",
        "ledger://",
        "appeal-ledger://",
        "scenario-contract://",
        "#",
    )
    return any(marker in value for marker in markers)


def _mapping_rows(payload: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    return [row for row in _as_list(payload.get(key)) if isinstance(row, Mapping)]


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON artifact must contain an object: {path}")
    return payload


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_string_list(value: object) -> list[str]:
    return [str(item) for item in _as_list(value) if item]


def _stable_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else (repo_root / path).resolve(strict=False)


def _rel_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve(strict=False).as_posix()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--wave35e-dir", type=Path, default=WAVE35E_DIR)
    parser.add_argument("--wave35f-dir", type=Path, default=WAVE35F_DIR)
    parser.add_argument("--wave35g-dir", type=Path, default=WAVE35G_DIR)
    args = parser.parse_args(argv)

    payload = build_institutional_provenance_boundary_ledger(
        repo_root=args.repo_root,
        wave35e_dir=args.wave35e_dir,
        wave35f_dir=args.wave35f_dir,
        wave35g_dir=args.wave35g_dir,
    )
    errors = validate_institutional_provenance_boundary_ledger(payload)
    if errors:
        for error in errors:
            sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(
        "wave35g-institutional-provenance-build: "
        f"rows={len(payload['rows'])} "
        f"not_closeout={payload['summary']['not_closeout_authority_count']}\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
