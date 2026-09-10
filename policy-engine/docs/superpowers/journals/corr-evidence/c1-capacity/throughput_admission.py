"""Bind finite direct-extraction execution bytes and the successful verdict.

The campaign's existing source projection supplies the extraction-owner family.
Only its campaign orchestrator is excluded: direct ``_extract`` never runs it.
The lane entrypoints, observer and local estimator complete this finite boundary.
This is reproducible source binding, not process attestation or a recursive proof
about every transitive dependency installed on the host.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

_BASE = "docs/superpowers/journals/corr-evidence/c1-capacity/"
ADDITIONAL_PATHS = (
    _BASE + "throughput_admission.py",
    _BASE + "throughput_runner.py",
    _BASE + "throughput_declaration.py",
    _BASE + "throughput_analysis.py",
    _BASE + "contract_probe.py",
    _BASE + "capacity_common.py",
    _BASE + "process_telemetry.py",
    "src/polisyos/scientist/orchestration/llm/token_estimator.py",
)
_EXCLUDED = "src/polisyos/data_forge/domains/academic/batch/reextraction_campaign.py"


def bytes_digest(data: bytes) -> str:
    """Bind the exact bytes, including a correction that only changes whitespace."""
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _inherited_paths() -> tuple[str, ...]:
    from polisyos.data_forge.domains.academic.batch.reextraction_campaign import (
        campaign_owner_projection,
    )

    return tuple(campaign_owner_projection()["sources"])


def execution_projection(root: Path) -> dict[str, Any]:
    """Walk the complete finite inherited-plus-direct source identity set."""
    paths = (set(_inherited_paths()) - {_EXCLUDED}) | set(ADDITIONAL_PATHS)
    body = {
        "schema_version": "corr.direct_extraction_execution_sources.v1",
        "sources": {name: bytes_digest((root / name).read_bytes()) for name in sorted(paths)},
        "excluded_owner": _EXCLUDED,
        "exclusion_reason": "direct _extract does not execute campaign orchestration",
        "scope": (
            "finite extraction family plus direct entrypoints, observation and token estimation"
        ),
    }
    encoded = json.dumps(
        body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode()
    return {**body, "content_hash": bytes_digest(encoded)}


def _require_equal(actual: object, expected: object, reason: str) -> None:
    if actual != expected:
        raise ValueError(reason)


def require_admitted_execution(plan: dict[str, Any], root: Path) -> None:
    """Recompute actual bytes at worker admission, never trust declaration markers."""
    verdict = root / plan["contract_verdict_path"]
    _require_equal(
        bytes_digest(verdict.read_bytes()),
        plan.get("contract_verdict_sha256"),
        "throughput_contract_verdict_changed",
    )
    _require_equal(
        execution_projection(root),
        plan.get("execution_source_projection"),
        "throughput_execution_source_changed",
    )
