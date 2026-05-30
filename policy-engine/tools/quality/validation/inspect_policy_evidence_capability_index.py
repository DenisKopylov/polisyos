#!/usr/bin/env python3
"""Inspect the Policy Evidence Capability Index for operator/audit review."""

from __future__ import annotations

# ruff: noqa: T201
import argparse
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.capability_index import (  # noqa: E402
    AcquisitionStrategy,
    CapabilityConflictRecord,
    EvidenceCapability,
    FailureModeNode,
)

SCHEMA_VERSION = "policyos.capability_index.inspection_report.v1"


def build_capability_index_inspection_report(capability_index_path: str | Path) -> dict[str, Any]:
    """Build an audit inspection report from a capability-index DuckDB.

    Args:
        capability_index_path: Path to ``capability_index_v1.duckdb``.

    Returns:
        Deterministic JSON-serializable report with counts by construct,
        authority posture, modality, evidence mode, and white-space status.
    """

    snapshot = load_capability_index_snapshot(capability_index_path)
    capabilities = snapshot["capabilities"]
    failure_modes = snapshot["failure_modes"]
    conflicts = snapshot["conflicts"]
    active = [
        capability
        for capability in capabilities
        if capability.capability_lifecycle.state == "active"
    ]
    authority_counts = {
        "research": _count_authority(active, "research"),
        "governed_pilot": _count_authority(active, "governed_pilot"),
        "production": _count_authority(active, "production"),
    }
    white_space_by_status = Counter(node.status for node in failure_modes)
    white_space_by_gap = Counter(node.gap_type for node in failure_modes)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "pass",
        "capability_index_path": str(Path(capability_index_path)),
        "index_metadata": snapshot["metadata"],
        "counts": {
            "capability_count": len(capabilities),
            "active_capability_count": len(active),
            "compatibility_only_capability_count": sum(
                1 for capability in active if capability.compatibility_only
            ),
            "source_asset_count": sum(
                len(capability.source_assets) for capability in capabilities
            ),
            "conflict_count": len(conflicts),
            "white_space_count": len(failure_modes),
            "acquisition_strategy_count": len(snapshot["acquisition_strategies"]),
        },
        "construct_coverage": {
            "covered_construct_count": len({capability.construct_id for capability in active}),
            "capability_count_by_construct": dict(
                sorted(Counter(capability.construct_id for capability in active).items())
            ),
            "white_space_count_by_construct": dict(
                sorted(Counter(node.construct_id for node in failure_modes).items())
            ),
        },
        "authority_posture_counts": authority_counts,
        "modality_counts": dict(
            sorted(
                Counter(
                    modality for capability in active for modality in capability.modality
                ).items()
            )
        ),
        "evidence_mode_counts": dict(
            sorted(Counter(capability.evidence_mode for capability in active).items())
        ),
        "white_space_counts": {
            "total": len(failure_modes),
            "by_status": dict(sorted(white_space_by_status.items())),
            "by_gap_type": dict(sorted(white_space_by_gap.items())),
        },
        "conflict_counts": dict(
            sorted(Counter(conflict.conflict_class for conflict in conflicts).items())
        ),
        "authority_boundary": {
            "authoritative_for": ["capability_index_audit_inspection"],
            "may_not_use_for": ["claim_evidence_satisfaction", "production_closeout_authority"],
        },
    }


def load_capability_index_snapshot(capability_index_path: str | Path) -> dict[str, Any]:
    """Load typed capability-index rows from DuckDB."""

    import duckdb

    path = Path(capability_index_path)
    with duckdb.connect(str(path), read_only=True) as con:
        capabilities = [
            EvidenceCapability.model_validate_json(row[0])
            for row in con.execute(
                "SELECT capability_json FROM capabilities ORDER BY capability_id"
            ).fetchall()
        ]
        failure_modes = [
            FailureModeNode.model_validate_json(row[0])
            for row in con.execute(
                "SELECT failure_json FROM failure_modes ORDER BY failure_id"
            ).fetchall()
        ]
        acquisition_strategies = [
            AcquisitionStrategy.model_validate_json(row[0])
            for row in con.execute(
                "SELECT strategy_json FROM acquisition_strategies ORDER BY strategy_id"
            ).fetchall()
        ]
        conflicts = [
            CapabilityConflictRecord.model_validate_json(row[0])
            for row in con.execute(
                "SELECT conflict_json FROM conflicts ORDER BY conflict_id"
            ).fetchall()
        ]
        metadata_rows = con.execute(
            "SELECT key, value_json FROM index_metadata ORDER BY key"
        ).fetchall()
    return {
        "capabilities": capabilities,
        "failure_modes": failure_modes,
        "acquisition_strategies": acquisition_strategies,
        "conflicts": conflicts,
        "metadata": {
            str(key): json.loads(str(value_json)) for key, value_json in metadata_rows
        },
    }


def active_capabilities(snapshot: Mapping[str, Any]) -> tuple[EvidenceCapability, ...]:
    """Return active capabilities from a loaded snapshot."""

    return tuple(
        capability
        for capability in snapshot.get("capabilities", ())
        if isinstance(capability, EvidenceCapability)
        and capability.capability_lifecycle.state == "active"
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability-index", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    report = build_capability_index_inspection_report(args.capability_index)
    if args.output:
        atomic_write_json(args.output, report)
    else:
        json.dump(report, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    return 0 if report["status"] == "pass" else 1


def _count_authority(
    capabilities: Sequence[EvidenceCapability],
    posture: str,
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                str(getattr(capability.authority_envelope, posture))
                for capability in capabilities
            ).items()
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
