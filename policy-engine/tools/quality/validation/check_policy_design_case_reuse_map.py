#!/usr/bin/env python3
"""Generate and validate the Policy Design Case capability reuse map."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.reuse_map.v1"
TOOL_NAME = "quality.validation.check-policy-design-case-reuse-map"
GENERATED_AT = "2026-05-17T00:00:00Z"
DEFAULT_SDD_PATH = Path(
    "docs/system-design-decisions/policy-design-best-in-class-operating-model.md"
)
DEFAULT_MAP_PATH = Path("architecture/policy_design_case/capability_reuse_map.json")
CAPABILITY_SECTION = "Capability Realization Map"
ALLOWED_CLASSIFICATIONS = frozenset(
    {
        "wire-existing",
        "extend-existing",
        "consolidate-existing",
        "build-new",
    }
)
CLASSIFICATION_PRECEDENCE = (
    "build-new",
    "consolidate-existing",
    "extend-existing",
    "wire-existing",
)
REQUIRED_ENTRY_FIELDS = frozenset(
    {
        "target_capability_id",
        "target_capability",
        "existing_owner_or_surface",
        "sdd_status",
        "classification",
        "design_implication",
        "source",
        "rejected_reuse_evidence",
    }
)
SENSITIVE_OVERLAP_DOMAINS: Mapping[str, tuple[str, ...]] = {
    "runtime_quality": (
        "src/polisyos/runtime/quality",
        "runtime quality",
        "runtime assurance-case",
        "substrate quality",
        "formal substrate",
        "honest diagnostics substrate",
        "substrate invariant",
        "scorecard.py",
        "phase_barriers.py",
        "invariants.py",
    ),
    "data_forge": (
        "src/polisyos/data_forge",
        "data forge",
        "read-api",
        "read snapshots",
    ),
    "scholar": (
        "src/polisyos/scholar",
        "scholar",
        "grey-literature",
    ),
    "foundry_consensus_equivalence": (
        "src/polisyos/foundry/methods/consensus.py",
        "src/polisyos/foundry/methods/components/consensus.py",
        "src/polisyos/foundry/methods/equivalence",
        "method consensus",
        "equivalence",
        "independence collapse",
    ),
    "scientist_doe_discovery": (
        "src/polisyos/scientist/methods/doe",
        "src/polisyos/scientist/methods/discovery",
        "doe",
        "discovery",
        "specification curves",
    ),
    "ir_analytics": (
        "src/polisyos/ir/analytics",
        "ir analytical",
        "ir analytics",
        "causal ensemble",
        "falsification",
    ),
    "berl": (
        "src/polisyos/berl",
        "berl",
        "bounded explanation reliability",
    ),
    "ddm": (
        "src/polisyos/ddm",
        "ddm",
        "driftanddegradationmonitor",
        "drift, degradation",
    ),
    "core_governance": (
        "src/polisyos/core/governance",
        "src/polisyos/core/contracts/control.py",
        "core governance",
        "execution profiles",
    ),
    "core_audit": (
        "src/polisyos/core/audit",
        "prov/slsa",
        "standalone verification",
        "standalone_verifier",
        "safe archive",
    ),
}


def build_reuse_map_payload(
    repo_root: Path = REPO_ROOT,
    *,
    sdd_path: Path = DEFAULT_SDD_PATH,
) -> dict[str, Any]:
    """Build a machine-readable reuse map from the SDD markdown table."""

    repo_root = Path(repo_root)
    resolved_sdd_path = _resolve_repo_path(repo_root, sdd_path)
    rows = _extract_capability_rows(resolved_sdd_path.read_text(encoding="utf-8"))
    entries = [
        _entry_from_sdd_row(row=row, row_number=index + 1, sdd_path=sdd_path)
        for index, row in enumerate(rows)
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "generated_at": GENERATED_AT,
        "source": {
            "sdd_path": sdd_path.as_posix(),
            "sdd_section": CAPABILITY_SECTION,
        },
        "summary": _summary(entries),
        "entries": entries,
    }


def load_reuse_map(
    repo_root: Path = REPO_ROOT,
    *,
    map_path: Path = DEFAULT_MAP_PATH,
) -> dict[str, Any]:
    """Load the committed machine-readable reuse map."""

    resolved_map_path = _resolve_repo_path(Path(repo_root), map_path)
    return json.loads(resolved_map_path.read_text(encoding="utf-8"))


def validate_reuse_map_payload(
    payload: Mapping[str, Any],
    *,
    repo_root: Path | None = None,
    sdd_path: Path = DEFAULT_SDD_PATH,
) -> dict[str, Any]:
    """Validate reuse classification completeness and build-new reuse evidence."""

    issues: list[dict[str, Any]] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        issues.append(
            _issue(
                "pdc_reuse_map_schema_version_invalid",
                "$.schema_version",
                f"schema_version must be {SCHEMA_VERSION}",
            )
        )

    raw_entries = payload.get("entries")
    if not isinstance(raw_entries, list) or not raw_entries:
        issues.append(
            _issue(
                "pdc_reuse_map_entries_missing",
                "$.entries",
                "reuse map must contain at least one capability entry",
            )
        )
        entries: list[Mapping[str, Any]] = []
    else:
        entries = [
            entry for entry in raw_entries if isinstance(entry, Mapping)
        ]
        if len(entries) != len(raw_entries):
            issues.append(
                _issue(
                    "pdc_reuse_map_entry_invalid",
                    "$.entries",
                    "every reuse map entry must be a JSON object",
                )
            )

    seen_targets: set[str] = set()
    for index, entry in enumerate(entries):
        path = f"$.entries[{index}]"
        missing_fields = sorted(REQUIRED_ENTRY_FIELDS - set(entry))
        for field in missing_fields:
            code = (
                "pdc_reuse_classification_missing"
                if field == "classification"
                else "pdc_reuse_entry_field_missing"
            )
            issues.append(
                _issue(code, f"{path}.{field}", f"{field} is required")
            )

        target = str(entry.get("target_capability", "")).strip()
        if not target:
            issues.append(
                _issue(
                    "pdc_reuse_target_missing",
                    f"{path}.target_capability",
                    "target_capability must not be empty",
                )
            )
        elif target in seen_targets:
            issues.append(
                _issue(
                    "pdc_reuse_target_duplicate",
                    f"{path}.target_capability",
                    f"duplicate target capability: {target}",
                    target_capability=target,
                )
            )
        else:
            seen_targets.add(target)

        classification = entry.get("classification")
        if classification is not None and classification not in ALLOWED_CLASSIFICATIONS:
            issues.append(
                _issue(
                    "pdc_reuse_classification_invalid",
                    f"{path}.classification",
                    "classification must be one of: "
                    + ", ".join(sorted(ALLOWED_CLASSIFICATIONS)),
                    target_capability=target or None,
                )
            )

        domains = _detect_sensitive_domains(entry)
        evidence = entry.get("rejected_reuse_evidence")
        if (
            classification == "build-new"
            and (domains or not evidence)
            and not _has_rejected_reuse_evidence(evidence)
        ):
            issues.append(
                _issue(
                    "pdc_build_new_reuse_evidence_missing",
                    f"{path}.rejected_reuse_evidence",
                    (
                        "build-new entries must carry rejected-reuse evidence"
                        + (
                            " before overlapping sensitive domains: " + ", ".join(domains)
                            if domains
                            else ""
                        )
                    ),
                    target_capability=target or None,
                    sensitive_overlap_domains=domains,
                )
            )

    if repo_root is not None:
        generated = build_reuse_map_payload(Path(repo_root), sdd_path=sdd_path)
        expected_by_target = {
            entry["target_capability"]: entry for entry in generated["entries"]
        }
        actual_by_target = {
            str(entry.get("target_capability", "")): entry for entry in entries
        }
        for target in sorted(set(expected_by_target) - set(actual_by_target)):
            issues.append(
                _issue(
                    "pdc_reuse_target_missing",
                    "$.entries",
                    f"reuse map is missing SDD target capability: {target}",
                    target_capability=target,
                )
            )
        for target in sorted(set(actual_by_target) - set(expected_by_target)):
            if target:
                issues.append(
                    _issue(
                        "pdc_reuse_target_unknown",
                        "$.entries",
                        f"reuse map entry is not present in the SDD capability map: {target}",
                        target_capability=target,
                    )
                )
        for target, expected in expected_by_target.items():
            actual = actual_by_target.get(target)
            if not actual:
                continue
            if actual.get("classification") != expected["classification"]:
                issues.append(
                    _issue(
                        "pdc_reuse_classification_drift",
                        "$.entries",
                        (
                            f"{target} classification must be "
                            f"{expected['classification']!r} from the SDD status"
                        ),
                        target_capability=target,
                    )
                )

    status = "pass" if not issues else "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "status": status,
        "summary": _summary(entries),
        "issues": issues,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate or validate the Policy Design Case capability reuse map."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--sdd", type=Path, default=DEFAULT_SDD_PATH)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP_PATH)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write the generated reuse map before validating it.",
    )
    parser.add_argument(
        "--output-format",
        choices=("text", "json"),
        default="text",
    )
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root)
    if args.write:
        payload = build_reuse_map_payload(repo_root, sdd_path=args.sdd)
        atomic_write_json(_resolve_repo_path(repo_root, args.map), payload)
    else:
        payload = load_reuse_map(repo_root, map_path=args.map)

    validation = validate_reuse_map_payload(
        payload,
        repo_root=repo_root,
        sdd_path=args.sdd,
    )
    if args.output_format == "json":
        sys.stdout.write(json.dumps(validation, indent=2, ensure_ascii=False) + "\n")
    else:
        _print_text(validation)
    return 0 if validation["status"] == "pass" else 1


def _extract_capability_rows(markdown: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    in_section = False
    for line in markdown.splitlines():
        if line.strip() == f"## {CAPABILITY_SECTION}":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section or not line.startswith("|"):
            continue
        cells = [_clean_cell(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        if cells[0] == "Target capability" or set(cells[0]) <= {"-", " "}:
            continue
        rows.append(
            {
                "target_capability": cells[0],
                "existing_owner_or_surface": cells[1],
                "sdd_status": cells[2],
                "design_implication": cells[3],
            }
        )
    if not rows:
        raise ValueError(f"Could not find {CAPABILITY_SECTION!r} rows in SDD")
    return rows


def _entry_from_sdd_row(
    *,
    row: Mapping[str, str],
    row_number: int,
    sdd_path: Path,
) -> dict[str, Any]:
    target = row["target_capability"]
    entry = {
        "target_capability_id": _slugify(target),
        "target_capability": target,
        "existing_owner_or_surface": row["existing_owner_or_surface"],
        "sdd_status": row["sdd_status"],
        "classification": _classification_from_status(row["sdd_status"]),
        "design_implication": row["design_implication"],
        "source": {
            "sdd_path": sdd_path.as_posix(),
            "sdd_section": CAPABILITY_SECTION,
            "sdd_row_number": row_number,
        },
        "rejected_reuse_evidence": _rejected_reuse_evidence(target),
    }
    entry["sensitive_overlap_domains"] = _detect_sensitive_domains(entry)
    return entry


def _classification_from_status(status: str) -> str:
    tokens = {
        token.strip()
        for token in re.split(r"/|,", status)
        if token.strip()
    }
    unknown = tokens - ALLOWED_CLASSIFICATIONS
    if unknown:
        raise ValueError(f"Unknown reuse classification in SDD status {status!r}")
    for classification in CLASSIFICATION_PRECEDENCE:
        if classification in tokens:
            return classification
    raise ValueError(f"Missing reuse classification in SDD status {status!r}")


def _rejected_reuse_evidence(target_capability: str) -> list[dict[str, str]]:
    if target_capability != "Formal substrate invariant specification":
        return []
    return [
        {
            "rejected_owner_or_surface": "Honest diagnostics substrate tests and validation tools",
            "finding": (
                "Existing substrate tests and validation tools prove runtime behavior, "
                "but no existing owner emits lightweight formal/model specs for "
                "closeout-critical state-machine invariants."
            ),
            "decision_ref": (
                "docs/system-design-decisions/"
                "policy-design-best-in-class-operating-model.md#capability-realization-map"
            ),
        }
    ]


def _detect_sensitive_domains(entry: Mapping[str, Any]) -> list[str]:
    haystack = " ".join(
        str(entry.get(field, ""))
        for field in (
            "target_capability",
            "existing_owner_or_surface",
            "design_implication",
        )
    ).lower()
    return [
        domain
        for domain, needles in SENSITIVE_OVERLAP_DOMAINS.items()
        if any(needle.lower() in haystack for needle in needles)
    ]


def _has_rejected_reuse_evidence(value: object) -> bool:
    if not isinstance(value, list) or not value:
        return False
    for item in value:
        if isinstance(item, Mapping) and item.get("finding"):
            return True
        if isinstance(item, str) and item.strip():
            return True
    return False


def _summary(entries: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    entry_list = list(entries)
    counts = Counter(str(entry.get("classification", "missing")) for entry in entry_list)
    return {
        "target_capability_count": len(entry_list),
        "classification_counts": {
            classification: counts.get(classification, 0)
            for classification in sorted(ALLOWED_CLASSIFICATIONS)
        },
        "missing_classification_count": counts.get("missing", 0),
        "build_new_count": counts.get("build-new", 0),
        "sensitive_overlap_domain_count": len(
            {
                domain
                for entry in entry_list
                for domain in _detect_sensitive_domains(entry)
            }
        ),
    }


def _issue(
    code: str,
    path: str,
    message: str,
    *,
    target_capability: str | None = None,
    sensitive_overlap_domains: Sequence[str] = (),
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": "error",
        "path": path,
        "message": message,
    }
    if target_capability:
        payload["target_capability"] = target_capability
    if sensitive_overlap_domains:
        payload["sensitive_overlap_domains"] = list(sensitive_overlap_domains)
    return payload


def _clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value.replace("`", "").strip())


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", slug)


def _resolve_repo_path(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _print_text(validation: Mapping[str, Any]) -> None:
    sys.stdout.write(f"Policy Design Case reuse map: {validation['status']}\n")
    for issue in validation["issues"]:
        sys.stdout.write(f"- {issue['code']}: {issue['path']}: {issue['message']}\n")


if __name__ == "__main__":
    sys.exit(main())
