# GY-PR1a data-only first governed promotion execution journal

This is the append-only execution and custody record for GY-PR1a. The first event below was
committed before any row in the owner Academic SKG database was inspected. Later events may append
facts; they must not revise the preregistration, erase a deviation, or replace the selected case.

## Event 0 — prospective registration before owner-data inspection

- Recorded at: `2026-09-02T12:36:00+03:00`.
- Branch: `codex/gy-pr1a-data-only-promotion`.
- Ratified Phase-1 plan commit: `7781da8e9a47f13d39a035dc3bc2f6810d9fa0e8`.
- Ratified Phase-1 plan blob: `b5d50b8f397733e99afa84f9634d4dfcf40c4d43`.
- Pre-ratification plan commit: `3de7a3f26a8fa16f49e6daf19e00d04226eb97c6`.
- Ratified plan commit time: `2026-09-02T11:57:37+03:00`.
- Bound interpreter: Python `3.14.0` at
  `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python`.
- Confirmed environment prefix, measured once before Phase 2:
  `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv`.
- Registered feasibility instrument SHA-256:
  `3a7b23508d1947a1f8733a246080d1c2fb8fe2056771c29e1836c3afe8d7b627`.
- Registered selector SQL SHA-256:
  `a69f142d098b4e6f3feb382f9ba0427a399415421bc918813eeb7300a2d770c6`.
- The instrument contains 1,632 lines / 63,174 bytes. Its complete source is preserved below.

### INT-R9 Option-B claim boundary

This execution can support only a custody claim about a prospectively selected first case and the
faithful preservation of its chronology. It supports no statistical family-control, population
performance, compliance, competence, or production-readiness claim, and carries no probability.
Result-informed repair is permitted and will be recorded as a deviation; result-informed case
selection or an unrecorded substitution is prohibited. A failed selected case remains an
append-only negative terminal and is never rerun or rescored as the first attempt. Any later
implementation repair is recorded as adaptive continuation; it cannot erase, replace, or
reclassify that terminal. A genuinely unsuitable case may be explicitly closed only with the
terminal preserved, followed by a newly preregistered protocol before any replacement is
inspected.

The public `INT-K06` fields are not asserted by this local journal. Their initial status is:

- prospectivity: `not_established` externally; repository chronology is recorded below;
- firstness: `not_established` externally; this is the only registered invocation in this lane;
- substitutions: none registered;
- chronology: selection not started;
- adjudication: not started;
- deviations: none;
- negative terminals: none;
- publication: `not_established`;
- correction: none;
- prohibited substitution found: `false`.

### Fixed population and case-selection rule

The population is every row returned by the plan's exact committed SQL from the maximum
`ac_skg_versions.version_id` of the one fixed production Academic SKG database, after only the
structural joins and disqualifiers in that SQL. There is no calibration result, relationship
eligibility, outcome, effect size, uncertainty width, sample-count, or pass/fail filter in the
selector. Its nine fields are `skg_snapshot_ref`, `numeric_id`, `edge_id`, `openalex_id`,
`claim_id`, `edge_src`, `edge_dst`, `target_context_id`, and `estimate_type`.

The fixed selection seed is `GY-PR1A-INT-R9-PRIMARY-2026-09-02-V1`. The instrument normalizes and
deduplicates the complete result, sorts it deterministically, computes its population hash, then
chooses the minimum SHA-256 digest of `seed|skg_snapshot_ref|numeric_id|edge_id|openalex_id|claim_id`.
No second row, rescue row, or post-result choice exists.

A row is structurally disqualified only by one of the committed SQL exclusions: missing pinned
version; malformed/non-string claim linkage; blank required identity; non-finite point estimate;
join failure across numeric, claim, evidence, edge, article, and transport ownership; retracted
article; version after the pin; or cause/effect/direction mismatch. After selection, the selected
row is separately and exactly bound to the owner Credal Reference: a confirmed L6 knob operator,
the confirmed L6 operator-to-target-world-slot mapping, and an exact WMR write mapping must all
agree. Aliases do not count. The selected effect estimate is never repurposed as a caller-chosen
intervention value.

### Fixed custody paths and invocation order

- Owner database, always opened read-only:
  `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`.
- One-shot invocation lock:
  `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/selection-invocation.lock.json`.
- Selection receipt:
  `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/selection-receipt.json`.
- Binding receipt:
  `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/binding-receipt.json`.
- Feasibility receipt:
  `/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/calibration-feasibility-receipt.json`.

The enforced order is `select -> commit selection seal -> bind -> commit binding seal -> measure`.
The lock and every receipt use exclusive creation. Binding and measurement refuse an uncommitted or
dirty journal, a mismatched receipt, a changed instrument, a changed database, a changed Credal
Reference, a wrong branch, or a missing/duplicate seal.

Exact selection command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/task-0-feasibility.py --mode select --database /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb
```

Exact binding command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/task-0-feasibility.py --mode bind --database /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb --repo-root /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine
```

Exact measurement command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/src:/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/task-0-feasibility.py --mode measure --database /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb --repo-root /Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine
```

`select` emits a versioned receipt containing the source hashes, full population denominator and
hash, deterministic winner, selection digest, provisional candidate identity, and the explicit
`not_yet_inspected` owner-binding state. `bind` replays the selection and emits a versioned receipt
containing the exact owner binding, numeric value/uncertainty evidence, candidate identity, Credal
Reference epoch/hash, and fail-closed outcome. `measure` replays both earlier stages and emits raw,
rejected, duplicate, structural, and eligible calibration denominators per
`operator_family|reference_region|relation_type` stratum, with the source/CAS/reference lineages
that determine whether the selected stratum has at least 20 eligible observations.

### Authorized production-CG2 projection

The legacy Academic Claim Authorization Store (CAS) is competent only to authorize
`academic_claim_edge_publishability`. A CAS row with `publishable_edge=false` is excluded and never
converted into negative relationship evidence. Under the separately ratified additive production
CG2 family, Runtime must independently recompute exact source identity, exact confirmed L6
operator-to-target compatibility, exact WMR writability, and CAS batch lineage. Only their
composition may produce the positive exact-eligibility observation
`cg2_production_academic_skg_adjudication_v1`. Presence, names, aliases, or a caller assertion do
not satisfy it. This engineering projection does not assert institutional authority, probability,
population performance, compliance, competence, or readiness.

### Instrument self-test before owner-data inspection

The selector was exercised only against a synthetic temporary DuckDB fixture. It returned
`task0_selector_selftest=PASS`. No production/Academic SKG/calibration/numeric owner row was read by
that test. The repository-bound owner source remains uninspected at this event.

### Complete registered instrument source

The following source is the exact 63,174-byte instrument whose SHA-256 is registered above. It is
included so the first owner-data query is reviewable without relying on an untracked path.

```python
#!/usr/bin/env python3
"""Read-only, prospectively bound feasibility measurement for GY-PR1a Task 0."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import duckdb


SELECTION_SEED: Final = "GY-PR1A-INT-R9-PRIMARY-2026-09-02-V1"
PLAN_COMMIT: Final = "7781da8e9a47f13d39a035dc3bc2f6810d9fa0e8"
PLAN_BLOB: Final = "b5d50b8f397733e99afa84f9634d4dfcf40c4d43"
SELECTION_LOCK_PATH: Final = Path(
    "/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/"
    ".superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/"
    "selection-invocation.lock.json"
)
SELECTION_RECEIPT_PATH: Final = SELECTION_LOCK_PATH.with_name("selection-receipt.json")
BINDING_RECEIPT_PATH: Final = SELECTION_LOCK_PATH.with_name("binding-receipt.json")
MEASUREMENT_RECEIPT_PATH: Final = SELECTION_LOCK_PATH.with_name(
    "calibration-feasibility-receipt.json"
)
JOURNAL_PATH: Final = Path(
    "/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/"
    "policy-engine/docs/superpowers/journals/"
    "2026-09-02-gy-pr1a-data-only-promotion.md"
)
JOURNAL_GIT_PATH: Final = (
    "policy-engine/docs/superpowers/journals/"
    "2026-09-02-gy-pr1a-data-only-promotion.md"
)
SELECTOR_QUERY_SHA256: Final = (
    "a69f142d098b4e6f3feb382f9ba0427a399415421bc918813eeb7300a2d770c6"
)
SELECTOR_FIELDS: Final = (
    "skg_snapshot_ref",
    "numeric_id",
    "edge_id",
    "openalex_id",
    "claim_id",
    "edge_src",
    "edge_dst",
    "target_context_id",
    "estimate_type",
)
CALIBRATION_FIELDS: Final = SELECTOR_FIELDS[1:]
REQUIRED_TABLES: Final = (
    "ac_skg_articles",
    "ac_skg_edge_evidence",
    "ac_skg_edges",
    "ac_skg_simulation_parameters",
    "ac_skg_span_grounded_claims",
    "ac_skg_transport_scores",
    "ac_skg_versions",
)

SELECTOR_SQL: Final = """WITH pinned_version AS (
    SELECT MAX(version_id) AS version_id
    FROM ac_skg_versions
)
SELECT
    CAST(? AS VARCHAR) || '#v' || CAST(v.version_id AS VARCHAR)
        AS skg_snapshot_ref,
    TRIM(p.numeric_id) AS numeric_id,
    TRIM(e.edge_id) AS edge_id,
    TRIM(p.openalex_id) AS openalex_id,
    TRIM(c.claim_id) AS claim_id,
    TRIM(e.src) AS edge_src,
    TRIM(e.dst) AS edge_dst,
    TRIM(t.target_context_id) AS target_context_id,
    TRIM(p.estimate_type) AS estimate_type
FROM pinned_version AS v
CROSS JOIN ac_skg_simulation_parameters AS p
CROSS JOIN LATERAL json_each(
    CASE
        WHEN json_valid(p.linked_claim_ids_json)
        THEN p.linked_claim_ids_json
        ELSE '[]'
    END
) AS claim_ref
JOIN ac_skg_span_grounded_claims AS c
  ON c.claim_id = json_extract_string(claim_ref.value, '$')
 AND c.openalex_id = p.openalex_id
JOIN ac_skg_edge_evidence AS ee
  ON ee.claim_id = c.claim_id
 AND ee.openalex_id = c.openalex_id
JOIN ac_skg_edges AS e
  ON e.edge_id = ee.edge_id
 AND e.src = ee.src
 AND e.dst = ee.dst
 AND e.direction = ee.direction
JOIN ac_skg_articles AS a
  ON a.openalex_id = p.openalex_id
JOIN ac_skg_transport_scores AS t
  ON t.edge_id = e.edge_id
WHERE v.version_id IS NOT NULL
  AND claim_ref.type = 'VARCHAR'
  AND TRIM(p.numeric_id) <> ''
  AND TRIM(p.openalex_id) <> ''
  AND TRIM(p.estimate_type) <> ''
  AND isfinite(p.point_estimate)
  AND TRIM(c.claim_id) <> ''
  AND TRIM(e.edge_id) <> ''
  AND TRIM(e.src) <> ''
  AND TRIM(e.dst) <> ''
  AND TRIM(t.target_context_id) <> ''
  AND a.retracted = FALSE
  AND a.skg_version <= v.version_id
  AND c.skg_version <= v.version_id
  AND ee.skg_version <= v.version_id
  AND t.skg_version <= v.version_id
  AND c.cause = ee.src
  AND c.effect = ee.dst
  AND c.direction = ee.direction
"""

BINDING_SQL: Final = """SELECT
    p.point_estimate,
    p.unit,
    p.confidence_interval_json,
    p.std_error,
    p.uncertainty_source,
    p.context_json,
    p.source_layer,
    p.quality_flags_json
FROM ac_skg_simulation_parameters AS p
WHERE TRIM(p.numeric_id) = ?
  AND TRIM(p.openalex_id) = ?
"""

CALIBRATION_SQL: Final = """WITH pinned_version AS (
    SELECT MAX(version_id) AS version_id
    FROM ac_skg_versions
)
SELECT
    TRIM(p.numeric_id) AS numeric_id,
    TRIM(e.edge_id) AS edge_id,
    TRIM(p.openalex_id) AS openalex_id,
    TRIM(c.claim_id) AS claim_id,
    TRIM(e.src) AS edge_src,
    TRIM(e.dst) AS edge_dst,
    TRIM(t.target_context_id) AS target_context_id,
    TRIM(p.estimate_type) AS estimate_type
FROM pinned_version AS v
CROSS JOIN ac_skg_simulation_parameters AS p
CROSS JOIN LATERAL json_each(
    CASE
        WHEN json_valid(p.linked_claim_ids_json)
        THEN p.linked_claim_ids_json
        ELSE '[]'
    END
) AS claim_ref
JOIN ac_skg_span_grounded_claims AS c
  ON c.claim_id = json_extract_string(claim_ref.value, '$')
 AND c.openalex_id = p.openalex_id
JOIN ac_skg_edge_evidence AS ee
  ON ee.claim_id = c.claim_id
 AND ee.openalex_id = c.openalex_id
JOIN ac_skg_edges AS e
  ON e.edge_id = ee.edge_id
 AND e.src = ee.src
 AND e.dst = ee.dst
 AND e.direction = ee.direction
JOIN ac_skg_articles AS a
  ON a.openalex_id = p.openalex_id
JOIN ac_skg_transport_scores AS t
  ON t.edge_id = e.edge_id
WHERE v.version_id IS NOT NULL
  AND claim_ref.type = 'VARCHAR'
  AND TRIM(p.numeric_id) <> ''
  AND TRIM(p.openalex_id) <> ''
  AND TRIM(p.estimate_type) <> ''
  AND isfinite(p.point_estimate)
  AND TRIM(c.claim_id) <> ''
  AND TRIM(e.edge_id) <> ''
  AND TRIM(e.src) <> ''
  AND TRIM(e.dst) <> ''
  AND TRIM(t.target_context_id) <> ''
  AND a.retracted = FALSE
  AND a.skg_version <= v.version_id
  AND c.skg_version <= v.version_id
  AND ee.skg_version <= v.version_id
  AND t.skg_version <= v.version_id
  AND c.cause = ee.src
  AND c.effect = ee.dst
  AND c.direction = ee.direction
"""


class ReadOnlyClaimConfig:
    """Minimum read-only configuration consumed by the canonical CAS verifier."""

    def __init__(self, snapshot_root: Path) -> None:
        component = snapshot_root / "academic"
        self.claim_adjudication_cas_root = component / "claim_adjudication_cas"
        self.claim_adjudication_result_ref_path = (
            component / "claim_adjudication_result_ref.json"
        )
        self.claim_adjudications_path = component / "claim_adjudications.jsonl"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _script_identity() -> dict[str, str]:
    script_path = Path(__file__).resolve()
    return {
        "path": str(script_path),
        "sha256": _sha256_file(script_path),
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "selector_query_sha256": _sha256_bytes(SELECTOR_SQL.encode("utf-8")),
        "binding_query_sha256": _sha256_bytes(BINDING_SQL.encode("utf-8")),
        "calibration_query_sha256": _sha256_bytes(CALIBRATION_SQL.encode("utf-8")),
        "plan_commit": PLAN_COMMIT,
        "plan_blob": PLAN_BLOB,
    }


def _claim_selection_invocation(lock_path: Path) -> tuple[bool, dict[str, Any]]:
    """Atomically consume the sole selection invocation before any owner query."""

    claim = {
        "schema_version": "gy-pr1a-selection-invocation-lock.v1",
        "claimed_at": _now(),
        "status": "selection_invocation_consumed",
        "selection_seed": SELECTION_SEED,
        "selector_output_schema": SELECTOR_FIELDS,
        "script": _script_identity(),
    }
    payload = (json.dumps(claim, indent=2, sort_keys=True) + "\n").encode("utf-8")
    try:
        descriptor = os.open(
            lock_path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o600,
        )
    except FileExistsError:
        existing: dict[str, Any] = {}
        try:
            candidate = json.loads(lock_path.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                existing = candidate
        except (OSError, json.JSONDecodeError):
            pass
        return False, existing
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return True, claim


def _verified_lock(lock_path: Path) -> dict[str, Any]:
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("selection invocation lock must be an object")
    script = payload.get("script")
    if not isinstance(script, dict):
        raise ValueError("selection invocation lock lacks script identity")
    current = _script_identity()
    for field in ("sha256", "selector_query_sha256", "plan_commit", "plan_blob"):
        if script.get(field) != current[field]:
            raise ValueError(f"selection invocation lock mismatch: {field}")
    if payload.get("status") != "selection_invocation_consumed":
        raise ValueError("selection invocation lock has wrong status")
    if payload.get("schema_version") != "gy-pr1a-selection-invocation-lock.v1":
        raise ValueError("selection invocation lock has wrong schema")
    if payload.get("selection_seed") != SELECTION_SEED:
        raise ValueError("selection invocation lock has wrong seed")
    if payload.get("selector_output_schema") != list(SELECTOR_FIELDS):
        raise ValueError("selection invocation lock has wrong output schema")
    return payload


def _receipt_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _persist_receipt(path: Path, payload: dict[str, Any]) -> bytes:
    data = _receipt_bytes(payload)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        os.write(descriptor, data)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return data


def _encoded_fields(values: tuple[str, ...]) -> bytes:
    payload = bytearray()
    for value in values:
        encoded = value.encode("utf-8")
        payload.extend(len(encoded).to_bytes(8, byteorder="big", signed=False))
        payload.extend(encoded)
    return bytes(payload)


def _row_tuple(row: tuple[Any, ...]) -> tuple[str, ...] | None:
    if len(row) != len(SELECTOR_FIELDS) or not all(isinstance(value, str) for value in row):
        return None
    return tuple(row)


def _terminal(
    *,
    mode: str,
    database: Path,
    code: str,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": "gy-pr1a-task0-feasibility.v1",
        "mode": mode,
        "recorded_at": _now(),
        "status": "negative_terminal",
        "terminal_code": code,
        "terminal_detail": detail,
        "database_path": str(database),
        "database_exists": database.is_file(),
        "script": _script_identity(),
    }
    if extra:
        payload.update(extra)
    return payload


def _database_inventory(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    table_names = tuple(sorted(str(row[0]) for row in connection.execute("SHOW TABLES").fetchall()))
    missing = tuple(name for name in REQUIRED_TABLES if name not in table_names)
    return {
        "table_denominator": len(table_names),
        "table_names": table_names,
        "required_table_denominator": len(REQUIRED_TABLES),
        "required_tables_present": len(REQUIRED_TABLES) - len(missing),
        "missing_required_tables": missing,
    }


def _binding_row(
    connection: duckdb.DuckDBPyConnection,
    selected: dict[str, str],
) -> dict[str, Any]:
    cursor = connection.execute(
        BINDING_SQL,
        [selected["numeric_id"], selected["openalex_id"]],
    )
    rows = cursor.fetchall()
    if len(rows) != 1:
        return {
            "status": "disqualified",
            "reasons": ["numeric_binding_not_unique"],
            "row_count": len(rows),
        }
    row = rows[0]
    interval_raw = str(row[2] or "")
    interval: Any
    try:
        interval = json.loads(interval_raw)
    except json.JSONDecodeError:
        interval = None
    interval_native = (
        isinstance(interval, list)
        and len(interval) == 2
        and all(isinstance(value, int | float) and not isinstance(value, bool) for value in interval)
    )
    reasons: list[str] = []
    if not interval_native:
        reasons.append("non_native_interval")
    if not str(row[4] or "").strip():
        reasons.append("uncertainty_source_missing")
    return {
        "status": "bound" if not reasons else "disqualified",
        "reasons": reasons,
        "point_estimate": row[0],
        "unit": str(row[1] or ""),
        "confidence_interval_raw": interval_raw,
        "std_error": row[3],
        "uncertainty_source": str(row[4] or ""),
        "context_json_raw": str(row[5] or ""),
        "source_layer": str(row[6] or ""),
        "quality_flags_json_raw": str(row[7] or ""),
    }


def select_case(database: Path, lock_path: Path) -> dict[str, Any]:
    claimed, existing_claim = _claim_selection_invocation(lock_path)
    if not claimed:
        return _terminal(
            mode="select",
            database=database,
            code="selection_invocation_already_consumed",
            detail="the exclusive pre-registered selection invocation was already claimed",
            extra={
                "selection_lock_path": str(lock_path),
                "selection_lock_sha256": (
                    _sha256_file(lock_path) if lock_path.is_file() else None
                ),
                "existing_claim": existing_claim,
            },
        )
    if _sha256_bytes(SELECTOR_SQL.encode("utf-8")) != SELECTOR_QUERY_SHA256:
        return _terminal(
            mode="select",
            database=database,
            code="selector_query_hash_mismatch",
            detail="embedded selector SQL differs from the committed pre-registration",
        )
    if not database.is_file():
        return _terminal(
            mode="select",
            database=database,
            code="production_skg_database_missing",
            detail="the sole pre-registered production Academic SKG database is absent",
            extra={"structural_denominator": 0},
        )

    database_hash = _sha256_file(database)
    try:
        connection = duckdb.connect(str(database), read_only=True)
    except (duckdb.Error, OSError, ValueError) as exc:
        return _terminal(
            mode="select",
            database=database,
            code="production_skg_database_unreadable",
            detail=f"{type(exc).__name__}: {exc}",
            extra={"database_sha256": database_hash, "structural_denominator": 0},
        )

    try:
        inventory = _database_inventory(connection)
        if inventory["missing_required_tables"]:
            return _terminal(
                mode="select",
                database=database,
                code="selector_required_table_missing",
                detail="the exact committed query contract cannot execute",
                extra={
                    "database_sha256": database_hash,
                    "structural_denominator": 0,
                    "database_inventory": inventory,
                },
            )
        cursor = connection.execute(SELECTOR_SQL, [f"duckdb://{database}"])
        output_fields = tuple(str(item[0]) for item in cursor.description)
        if output_fields != SELECTOR_FIELDS:
            return _terminal(
                mode="select",
                database=database,
                code="selector_output_schema_mismatch",
                detail=f"observed fields: {output_fields!r}",
                extra={
                    "database_sha256": database_hash,
                    "structural_denominator": 0,
                    "database_inventory": inventory,
                },
            )
        raw_rows = cursor.fetchall()
        normalized = [_row_tuple(row) for row in raw_rows]
        rejected_non_string = sum(row is None for row in normalized)
        unique_rows = sorted(
            {row for row in normalized if row is not None},
            key=_encoded_fields,
        )
        population_payload = b"".join(_encoded_fields(row) for row in unique_rows)
        base = {
            "database_sha256": database_hash,
            "database_inventory": inventory,
            "raw_query_row_denominator": len(raw_rows),
            "rejected_non_string_rows": rejected_non_string,
            "duplicate_rows_collapsed": len(raw_rows) - rejected_non_string - len(unique_rows),
            "structural_denominator": len(unique_rows),
            "structural_population_sha256": _sha256_bytes(population_payload),
            "selector_output_schema": SELECTOR_FIELDS,
        }
        if not unique_rows:
            return _terminal(
                mode="select",
                database=database,
                code="structural_population_empty",
                detail="the exact committed numeric-claim-edge-work population has zero rows",
                extra=base,
            )

        ranked: list[tuple[tuple[bytes, ...], str, tuple[str, ...]]] = []
        for row in unique_rows:
            digest = _sha256_bytes(
                "|".join((SELECTION_SEED, *row[:5])).encode("utf-8")
            )
            order_key = (
                bytes.fromhex(digest),
                _encoded_fields((row[1], row[2], row[3], row[4], row[7])),
            )
            ranked.append((order_key, digest, row))
        _, selection_digest, selected_row = min(ranked, key=lambda item: item[0])
        selected = dict(zip(SELECTOR_FIELDS, selected_row, strict=True))
        stratum = {
            "operator_family": selected["edge_src"],
            "reference_region": selected["target_context_id"],
            "relation_type": "exact",
        }
        stratum_key = "|".join(stratum.values())
        candidate_digest = _sha256_bytes(
            "|".join(
                (
                    selected["skg_snapshot_ref"],
                    stratum_key,
                    selection_digest,
                    selected["numeric_id"],
                    selected["edge_id"],
                    selected["openalex_id"],
                    selected["claim_id"],
                )
            ).encode("utf-8")
        )
        return {
            "schema_version": "gy-pr1a-task0-feasibility.v1",
            "mode": "select",
            "recorded_at": _now(),
            "status": "selected",
            "database_path": str(database),
            "database_exists": True,
            "selection_lock_path": str(lock_path),
            "selection_lock_sha256": _sha256_file(lock_path),
            "script": _script_identity(),
            **base,
            "selection_seed": SELECTION_SEED,
            "selection_digest": selection_digest,
            "selected": selected,
            "provisional_raw_stratum": stratum,
            "provisional_candidate_id": f"gy-pr1a-primary:{candidate_digest}",
            "owner_binding_status": "not_yet_inspected",
        }
    except (duckdb.Error, OSError, TypeError, ValueError) as exc:
        return _terminal(
            mode="select",
            database=database,
            code="selector_execution_failed",
            detail=f"{type(exc).__name__}: {exc}",
            extra={"database_sha256": database_hash, "structural_denominator": 0},
        )
    finally:
        connection.close()


def _snapshot_root(database: Path) -> Path:
    expected_suffix = Path("academic/graph/scholar_knowledge.duckdb")
    if tuple(database.parts[-len(expected_suffix.parts) :]) != expected_suffix.parts:
        raise ValueError("database path does not have the registered Academic SKG suffix")
    return database.parents[2]


def _selection_receipt_errors(
    selection: dict[str, Any],
    database: Path,
    lock_path: Path,
) -> list[str]:
    errors: list[str] = []
    current_script = _script_identity()
    receipt_script = selection.get("script")
    if not isinstance(receipt_script, dict):
        errors.append("selection_script_identity_missing")
    else:
        for field in (
            "sha256",
            "selector_query_sha256",
            "binding_query_sha256",
            "calibration_query_sha256",
            "plan_commit",
            "plan_blob",
        ):
            if receipt_script.get(field) != current_script[field]:
                errors.append(f"selection_script_identity_mismatch:{field}")
    if selection.get("database_path") != str(database):
        errors.append("selection_database_path_mismatch")
    if selection.get("selection_lock_path") != str(lock_path):
        errors.append("selection_lock_path_mismatch")
    if selection.get("selection_lock_sha256") != _sha256_file(lock_path):
        errors.append("selection_lock_hash_mismatch")
    if selection.get("selection_seed") != SELECTION_SEED:
        errors.append("selection_seed_mismatch")
    if selection.get("selector_output_schema") != list(SELECTOR_FIELDS):
        errors.append("selection_output_schema_mismatch")
    if not isinstance(selection.get("structural_denominator"), int) or int(
        selection.get("structural_denominator") or 0
    ) < 1:
        errors.append("selection_structural_denominator_invalid")
    population_hash = selection.get("structural_population_sha256")
    if not isinstance(population_hash, str) or len(population_hash) != 64:
        errors.append("selection_population_hash_invalid")

    selected = selection.get("selected")
    if not isinstance(selected, dict) or any(
        not isinstance(selected.get(field), str) for field in SELECTOR_FIELDS
    ):
        errors.append("selection_selected_row_schema_mismatch")
        return errors
    expected_digest = _sha256_bytes(
        "|".join(
            (
                SELECTION_SEED,
                selected["skg_snapshot_ref"],
                selected["numeric_id"],
                selected["edge_id"],
                selected["openalex_id"],
                selected["claim_id"],
            )
        ).encode("utf-8")
    )
    if selection.get("selection_digest") != expected_digest:
        errors.append("selection_digest_mismatch")
    expected_stratum = {
        "operator_family": selected["edge_src"],
        "reference_region": selected["target_context_id"],
        "relation_type": "exact",
    }
    if selection.get("provisional_raw_stratum") != expected_stratum:
        errors.append("selection_provisional_stratum_mismatch")
    expected_candidate_digest = _sha256_bytes(
        "|".join(
            (
                selected["skg_snapshot_ref"],
                "|".join(expected_stratum.values()),
                expected_digest,
                selected["numeric_id"],
                selected["edge_id"],
                selected["openalex_id"],
                selected["claim_id"],
            )
        ).encode("utf-8")
    )
    if selection.get("provisional_candidate_id") != (
        f"gy-pr1a-primary:{expected_candidate_digest}"
    ):
        errors.append("selection_provisional_candidate_id_mismatch")
    if selection.get("owner_binding_status") != "not_yet_inspected":
        errors.append("selection_owner_binding_status_mismatch")
    return errors


def _git_output(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["/opt/homebrew/bin/git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _journal_selection_seal(
    repo_root: Path,
    selection_path: Path,
    lock_path: Path,
) -> dict[str, str]:
    if selection_path != SELECTION_RECEIPT_PATH:
        raise ValueError("selection receipt path is not the pre-registered custody path")
    if lock_path != SELECTION_LOCK_PATH:
        raise ValueError("selection lock path is not the pre-registered custody path")
    if JOURNAL_PATH != repo_root / "docs/superpowers/journals/2026-09-02-gy-pr1a-data-only-promotion.md":
        raise ValueError("journal path is not rooted in the supplied repository")
    top_level = Path(_git_output(repo_root, "rev-parse", "--show-toplevel"))
    branch = _git_output(repo_root, "symbolic-ref", "--short", "HEAD")
    if branch != "codex/gy-pr1a-data-only-promotion":
        raise ValueError(f"journal seal is on the wrong branch: {branch}")
    status = subprocess.run(
        [
            "/opt/homebrew/bin/git",
            "-C",
            str(top_level),
            "diff",
            "--quiet",
            "HEAD",
            "--",
            JOURNAL_GIT_PATH,
        ],
        check=False,
    )
    if status.returncode != 0:
        raise ValueError("journal selection seal has uncommitted changes")
    journal = _git_output(
        top_level,
        "show",
        f"HEAD:{JOURNAL_GIT_PATH}",
    )
    expected = {
        "selection_receipt_sha256": _sha256_file(selection_path),
        "selection_lock_sha256": _sha256_file(lock_path),
        "selection_script_sha256": _script_identity()["sha256"],
        "selection_plan_commit": PLAN_COMMIT,
        "selection_plan_blob": PLAN_BLOB,
    }
    for key, value in expected.items():
        matches = re.findall(rf"^{re.escape(key)}: ([^\n]+)$", journal, flags=re.MULTILINE)
        if matches != [value]:
            raise ValueError(f"journal selection seal mismatch: {key}")
    seal_commit = _git_output(
        top_level,
        "log",
        "-1",
        "--format=%H",
        "--",
        JOURNAL_GIT_PATH,
    )
    if not seal_commit:
        raise ValueError("journal selection seal commit missing")
    return {
        **expected,
        "journal_seal_commit": seal_commit,
        "journal_branch": branch,
    }


def _journal_binding_seal(
    repo_root: Path,
    binding_path: Path,
    binding: dict[str, Any],
) -> dict[str, str]:
    if binding_path != BINDING_RECEIPT_PATH:
        raise ValueError("binding receipt path is not the pre-registered custody path")
    if JOURNAL_PATH != repo_root / "docs/superpowers/journals/2026-09-02-gy-pr1a-data-only-promotion.md":
        raise ValueError("journal path is not rooted in the supplied repository")
    top_level = Path(_git_output(repo_root, "rev-parse", "--show-toplevel"))
    branch = _git_output(repo_root, "symbolic-ref", "--short", "HEAD")
    if branch != "codex/gy-pr1a-data-only-promotion":
        raise ValueError(f"journal seal is on the wrong branch: {branch}")
    status = subprocess.run(
        [
            "/opt/homebrew/bin/git",
            "-C",
            str(top_level),
            "diff",
            "--quiet",
            "HEAD",
            "--",
            JOURNAL_GIT_PATH,
        ],
        check=False,
    )
    if status.returncode != 0:
        raise ValueError("journal binding seal has uncommitted changes")
    journal = _git_output(top_level, "show", f"HEAD:{JOURNAL_GIT_PATH}")
    owner = binding.get("owner_binding")
    if not isinstance(owner, dict):
        raise ValueError("binding owner evidence missing")
    expected = {
        "binding_receipt_sha256": _sha256_file(binding_path),
        "binding_script_sha256": _script_identity()["sha256"],
        "binding_selection_receipt_sha256": str(binding["selection_receipt_sha256"]),
        "binding_reference_epoch": str(owner["reference_epoch"]),
        "binding_reference_hash": str(owner["reference_hash"]),
        "binding_candidate_id": str(binding["candidate_id"]),
    }
    for key, value in expected.items():
        matches = re.findall(rf"^{re.escape(key)}: ([^\n]+)$", journal, flags=re.MULTILINE)
        if matches != [value]:
            raise ValueError(f"journal binding seal mismatch: {key}")
    seal_commit = _git_output(
        top_level,
        "log",
        "-1",
        "--format=%H",
        "--",
        JOURNAL_GIT_PATH,
    )
    if not seal_commit:
        raise ValueError("journal binding seal commit missing")
    return {
        **expected,
        "journal_seal_commit": seal_commit,
        "journal_branch": branch,
    }


def bind_selected_case(
    database: Path,
    selection_path: Path,
    lock_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    try:
        lock = _verified_lock(lock_path)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        return _terminal(
            mode="bind",
            database=database,
            code="selection_invocation_lock_invalid",
            detail=f"{type(exc).__name__}: {exc}",
        )
    selection = json.loads(selection_path.read_text(encoding="utf-8"))
    if not isinstance(selection, dict) or selection.get("status") != "selected":
        return _terminal(
            mode="bind",
            database=database,
            code="immutable_selection_receipt_missing",
            detail="owner binding requires the frozen successful selection output",
        )
    selection_errors = _selection_receipt_errors(selection, database, lock_path)
    if selection_errors:
        payload = _terminal(
            mode="bind",
            database=database,
            code="selection_receipt_invalid",
            detail=";".join(selection_errors),
            extra={
                "selection_receipt_path": str(selection_path),
                "selection_receipt_sha256": _sha256_file(selection_path),
            },
        )
        payload["status"] = "not_established"
        return payload
    try:
        journal_seal = _journal_selection_seal(
            repo_root,
            selection_path,
            lock_path,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        payload = _terminal(
            mode="bind",
            database=database,
            code="selection_journal_seal_invalid",
            detail=f"{type(exc).__name__}: {exc}",
            extra={
                "selection_receipt_path": str(selection_path),
                "selection_receipt_sha256": _sha256_file(selection_path),
            },
        )
        payload["status"] = "not_established"
        return payload
    current_db_hash = _sha256_file(database) if database.is_file() else ""
    if current_db_hash != selection.get("database_sha256"):
        return _terminal(
            mode="bind",
            database=database,
            code="database_changed_after_selection",
            detail="the database bytes differ from the immutable selection receipt",
            extra={
                "selected_database_sha256": selection.get("database_sha256"),
                "current_database_sha256": current_db_hash,
            },
        )

    selected = selection["selected"]
    try:
        from polisyos.runtime.quality.credal_reference import build_credal_reference

        reference = build_credal_reference(repo_root)
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        payload = _terminal(
            mode="bind",
            database=database,
            code="owner_reference_unavailable",
            detail=f"{type(exc).__name__}: {exc}",
            extra={
                "selection_receipt_path": str(selection_path),
                "selection_receipt_sha256": _sha256_file(selection_path),
                "selection_lock_path": str(lock_path),
                "selection_lock_sha256": _sha256_file(lock_path),
            },
        )
        payload["status"] = "not_established"
        return payload

    raw_operator = str(selected["edge_src"])
    raw_target = str(selected["edge_dst"])
    operator_edge = reference.essential_edges.get(("L6_KNOB_OPERATOR", raw_operator))
    operator_resolved = bool(
        operator_edge is not None
        and operator_edge.edge_id == raw_operator
        and operator_edge.status == "confirmed"
    )
    lever_target_edge = reference.essential_edges.get(
        ("L6_KNOB_WORLD_SLOT", raw_operator)
    )
    lever_targets: set[str] = set()
    if lever_target_edge is not None and lever_target_edge.status == "confirmed":
        for completion in lever_target_edge.admissible_completions:
            value = completion.value
            if not isinstance(value, dict):
                continue
            targets = value.get("target_world_slots")
            if isinstance(targets, list | tuple):
                lever_targets.update(str(item) for item in targets)
    lever_target_resolved = raw_target in lever_targets
    world_edge = reference.essential_edges.get(("WMR_WORLD_SLOT", raw_target))
    world_slot_resolved = bool(
        world_edge is not None
        and world_edge.edge_id == raw_target
        and world_edge.status == "confirmed"
    )
    policy_map_edges = []
    for edge in reference.essential_edges.values():
        if edge.modality != "WMR_POLICY_SLOT_MAP" or edge.status != "confirmed":
            continue
        maps_target = edge.edge_id.endswith(f":{raw_target}") or edge.edge_id == raw_target
        for completion in edge.admissible_completions:
            value = completion.value
            if isinstance(value, dict) and str(
                value.get("world_slot") or value.get("slot_id") or ""
            ) == raw_target:
                maps_target = True
        if maps_target:
            policy_map_edges.append(edge)
    target_writable = (
        world_slot_resolved and bool(policy_map_edges) and lever_target_resolved
    )

    try:
        connection = duckdb.connect(str(database), read_only=True)
        try:
            numeric_binding = _binding_row(connection, selected)
        finally:
            connection.close()
    except (duckdb.Error, OSError, TypeError, ValueError) as exc:
        numeric_binding = {
            "status": "disqualified",
            "reasons": ["numeric_binding_unreadable"],
            "detail": f"{type(exc).__name__}: {exc}",
        }

    disqualifiers = list(numeric_binding.get("reasons") or [])
    if not operator_resolved:
        disqualifiers.append("exact_registered_l6_operator_missing")
    if not target_writable:
        disqualifiers.append("exact_writable_wmr_target_missing")
    stratum = {
        "operator_family": raw_operator,
        "reference_region": str(selected["target_context_id"]),
        "relation_type": "exact",
    }
    stratum_key = "|".join(stratum.values())
    candidate_digest = _sha256_bytes(
        "|".join(
            (
                str(selected["skg_snapshot_ref"]),
                stratum_key,
                str(selection["selection_digest"]),
                str(selected["numeric_id"]),
                str(selected["edge_id"]),
                str(selected["openalex_id"]),
                str(selected["claim_id"]),
            )
        ).encode("utf-8")
    )
    return {
        "schema_version": "gy-pr1a-task0-feasibility.v1",
        "mode": "bind",
        "recorded_at": _now(),
        "status": "negative_terminal" if disqualifiers else "bound",
        "terminal_code": "selected_case_disqualified" if disqualifiers else None,
        "terminal_detail": (
            "the immutable selected row failed a pre-registered owner binding"
            if disqualifiers
            else None
        ),
        "database_path": str(database),
        "database_sha256": current_db_hash,
        "selection_receipt_path": str(selection_path),
        "selection_receipt_sha256": _sha256_file(selection_path),
        "selection_lock_path": str(lock_path),
        "selection_lock_sha256": _sha256_file(lock_path),
        "selection_lock": lock,
        "journal_selection_seal": journal_seal,
        "structural_denominator": selection["structural_denominator"],
        "structural_population_sha256": selection["structural_population_sha256"],
        "selector_output_schema": selection["selector_output_schema"],
        "selection_digest": selection["selection_digest"],
        "selected": selected,
        "selected_stratum": stratum,
        "candidate_id": f"gy-pr1a-primary:{candidate_digest}",
        "candidate_binding": {
            "treatment_operator": raw_operator,
            "outcome_target": raw_target,
            "estimand": str(selected["estimate_type"]),
            "population_region": str(selected["target_context_id"]),
            "numeric_evidence": numeric_binding,
        },
        "owner_binding": {
            "reference_epoch": reference.reference_epoch,
            "reference_hash": reference.reference_hash,
            "reference_component_versions": dict(reference.component_versions),
            "operator_lookup_key": ["L6_KNOB_OPERATOR", raw_operator],
            "operator_exact_registered": operator_resolved,
            "operator_edge_content_hash": (
                operator_edge.content_hash if operator_edge is not None else None
            ),
            "operator_edge_provenance": (
                dict(operator_edge.provenance) if operator_edge is not None else None
            ),
            "lever_target_lookup_key": ["L6_KNOB_WORLD_SLOT", raw_operator],
            "lever_target_exact_confirmed": lever_target_resolved,
            "lever_target_content_hash": (
                lever_target_edge.content_hash if lever_target_edge is not None else None
            ),
            "lever_target_world_slots": sorted(lever_targets),
            "world_slot_lookup_key": ["WMR_WORLD_SLOT", raw_target],
            "world_slot_exact_confirmed": world_slot_resolved,
            "world_slot_content_hash": (
                world_edge.content_hash if world_edge is not None else None
            ),
            "policy_map_content_hashes": sorted(
                edge.content_hash for edge in policy_map_edges
            ),
            "target_writable": target_writable,
            "alias_resolution_used": False,
        },
        "disqualifiers": sorted(set(disqualifiers)),
        "script": _script_identity(),
    }


def _binding_receipt_errors(
    binding: dict[str, Any],
    lock_path: Path,
) -> list[str]:
    errors: list[str] = []
    current_script = _script_identity()
    receipt_script = binding.get("script")
    if not isinstance(receipt_script, dict):
        errors.append("binding_script_identity_missing")
    else:
        for field in (
            "sha256",
            "selector_query_sha256",
            "binding_query_sha256",
            "calibration_query_sha256",
            "plan_commit",
            "plan_blob",
        ):
            if receipt_script.get(field) != current_script[field]:
                errors.append(f"binding_script_identity_mismatch:{field}")
    if binding.get("selection_lock_path") != str(lock_path):
        errors.append("binding_selection_lock_path_mismatch")
    if binding.get("selection_lock_sha256") != _sha256_file(lock_path):
        errors.append("binding_selection_lock_hash_mismatch")

    selection_path_value = binding.get("selection_receipt_path")
    if not isinstance(selection_path_value, str) or not selection_path_value:
        errors.append("binding_selection_receipt_path_missing")
        return errors
    selection_path = Path(selection_path_value)
    try:
        selection_bytes = selection_path.read_bytes()
        selection = json.loads(selection_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"binding_selection_receipt_unreadable:{type(exc).__name__}")
        return errors
    if _sha256_bytes(selection_bytes) != binding.get("selection_receipt_sha256"):
        errors.append("binding_selection_receipt_hash_mismatch")
    if not isinstance(selection, dict) or selection.get("status") != "selected":
        errors.append("binding_selection_receipt_status_mismatch")
        return errors
    if selection.get("selection_seed") != SELECTION_SEED:
        errors.append("binding_selection_seed_mismatch")
    for field in (
        "structural_denominator",
        "structural_population_sha256",
        "selector_output_schema",
        "selection_digest",
        "selected",
    ):
        if binding.get(field) is not None and binding.get(field) != selection.get(field):
            errors.append(f"binding_selection_field_mismatch:{field}")
    if binding.get("selected") != selection.get("selected"):
        errors.append("binding_selected_row_mismatch")

    selected = selection.get("selected")
    if not isinstance(selected, dict) or any(
        not isinstance(selected.get(field), str) for field in SELECTOR_FIELDS
    ):
        errors.append("binding_selected_row_schema_mismatch")
        return errors
    expected_selection_digest = _sha256_bytes(
        "|".join(
            (
                SELECTION_SEED,
                selected["skg_snapshot_ref"],
                selected["numeric_id"],
                selected["edge_id"],
                selected["openalex_id"],
                selected["claim_id"],
            )
        ).encode("utf-8")
    )
    if selection.get("selection_digest") != expected_selection_digest:
        errors.append("binding_selection_digest_mismatch")
    expected_stratum = {
        "operator_family": selected["edge_src"],
        "reference_region": selected["target_context_id"],
        "relation_type": "exact",
    }
    if binding.get("selected_stratum") != expected_stratum:
        errors.append("binding_selected_stratum_mismatch")
    expected_candidate_digest = _sha256_bytes(
        "|".join(
            (
                selected["skg_snapshot_ref"],
                "|".join(expected_stratum.values()),
                expected_selection_digest,
                selected["numeric_id"],
                selected["edge_id"],
                selected["openalex_id"],
                selected["claim_id"],
            )
        ).encode("utf-8")
    )
    if binding.get("candidate_id") != f"gy-pr1a-primary:{expected_candidate_digest}":
        errors.append("binding_candidate_id_mismatch")
    owner = binding.get("owner_binding")
    if not isinstance(owner, dict):
        errors.append("binding_owner_evidence_missing")
    else:
        if owner.get("operator_exact_registered") is not True:
            errors.append("binding_operator_not_owner_resolved")
        if owner.get("target_writable") is not True:
            errors.append("binding_target_not_owner_resolved")
        if owner.get("alias_resolution_used") is not False:
            errors.append("binding_alias_resolution_used")
    if binding.get("disqualifiers") != []:
        errors.append("binding_disqualifiers_present")
    return errors


def measure_calibration(
    database: Path,
    binding_path: Path,
    lock_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    try:
        _verified_lock(lock_path)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        payload = _terminal(
            mode="measure",
            database=database,
            code="selection_invocation_lock_invalid",
            detail=f"{type(exc).__name__}: {exc}",
        )
        payload["status"] = "not_established"
        return payload
    binding = json.loads(binding_path.read_text(encoding="utf-8"))
    if not isinstance(binding, dict) or binding.get("status") != "bound":
        return _terminal(
            mode="measure",
            database=database,
            code="immutable_owner_binding_missing",
            detail="measurement requires the frozen successful owner-binding output",
        )
    binding_errors = _binding_receipt_errors(binding, lock_path)
    if binding_errors:
        payload = _terminal(
            mode="measure",
            database=database,
            code="owner_binding_receipt_invalid",
            detail=";".join(binding_errors),
            extra={
                "binding_receipt_path": str(binding_path),
                "binding_receipt_sha256": _sha256_file(binding_path),
                "selected_stratum_count": None,
                "qualifying_observation_denominator": None,
            },
        )
        payload["status"] = "not_established"
        return payload
    try:
        journal_binding_seal = _journal_binding_seal(
            repo_root,
            binding_path,
            binding,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        payload = _terminal(
            mode="measure",
            database=database,
            code="binding_journal_seal_invalid",
            detail=f"{type(exc).__name__}: {exc}",
            extra={
                "binding_receipt_path": str(binding_path),
                "binding_receipt_sha256": _sha256_file(binding_path),
                "selected_stratum_count": None,
                "qualifying_observation_denominator": None,
            },
        )
        payload["status"] = "not_established"
        return payload
    selection_receipt_path = Path(str(binding["selection_receipt_path"]))
    replayed_binding = bind_selected_case(
        database,
        selection_receipt_path,
        lock_path,
        repo_root,
    )
    replay_fields = (
        "database_sha256",
        "structural_denominator",
        "structural_population_sha256",
        "selector_output_schema",
        "selection_digest",
        "selected",
        "selected_stratum",
        "candidate_id",
        "candidate_binding",
        "owner_binding",
        "disqualifiers",
    )
    replay_mismatches = [
        field for field in replay_fields if replayed_binding.get(field) != binding.get(field)
    ]
    if replayed_binding.get("status") != "bound" or replay_mismatches:
        payload = _terminal(
            mode="measure",
            database=database,
            code="owner_binding_replay_mismatch",
            detail=(
                str(replayed_binding.get("terminal_code") or "")
                + ";fields="
                + ",".join(replay_mismatches)
            ),
            extra={
                "binding_receipt_path": str(binding_path),
                "binding_receipt_sha256": _sha256_file(binding_path),
                "selected_stratum_count": None,
                "qualifying_observation_denominator": None,
            },
        )
        payload["status"] = "not_established"
        return payload
    current_db_hash = _sha256_file(database) if database.is_file() else ""
    if current_db_hash != binding.get("database_sha256"):
        return _terminal(
            mode="measure",
            database=database,
            code="database_changed_after_owner_binding",
            detail="the database bytes differ from the immutable owner-binding receipt",
            extra={
                "bound_database_sha256": binding.get("database_sha256"),
                "current_database_sha256": current_db_hash,
                "selected_stratum_count": 0,
            },
        )

    selected = binding["selected"]
    selected_stratum = binding["selected_stratum"]
    snapshot_root = _snapshot_root(database)
    claim_config = ReadOnlyClaimConfig(snapshot_root)
    pointer_denominator = int(claim_config.claim_adjudication_result_ref_path.is_file())
    compatibility_denominator = int(claim_config.claim_adjudications_path.is_file())
    cas_root_denominator = int(claim_config.claim_adjudication_cas_root.is_dir())
    authority_error = ""
    batch_lineage: dict[str, Any] = {}
    verified_rows: dict[str, dict[str, Any]] = {}
    try:
        from polisyos.data_forge.domains.academic.batch.admitted_claim_adjudications import (
            load_verified_claim_adjudication_rows,
        )
        from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
            load_admitted_claim_adjudication_batch,
        )

        batch, result_ref = load_admitted_claim_adjudication_batch(claim_config)  # type: ignore[arg-type]
        verified_rows = load_verified_claim_adjudication_rows(claim_config)  # type: ignore[arg-type]
        batch_lineage = {
            "result_artifact_id": str(result_ref.artifact_id),
            "raw_input_ref": batch.raw_input_ref,
            "candidate_ref": batch.candidate_ref,
            "evaluation_ref": batch.evaluation_ref,
            "rule_version": batch.rule_version,
            "admission_predicate": batch.admission_predicate,
            "authoritative_for": list(batch.authoritative_for),
            "may_not_use_for": list(batch.may_not_use_for),
            "input_claim_denominator": len(batch.input_claim_ids),
            "result_denominator": len(batch.results),
        }
    except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
        authority_error = f"{type(exc).__name__}: {exc}"

    authority_denominators = {
        "claim_adjudication_result_ref_json": pointer_denominator,
        "claim_adjudications_jsonl": compatibility_denominator,
        "claim_adjudication_cas_directory": cas_root_denominator,
    }
    if authority_error:
        payload = _terminal(
            mode="measure",
            database=database,
            code="calibration_authority_unavailable",
            detail=authority_error,
            extra={
                "binding_receipt_path": str(binding_path),
                "binding_receipt_sha256": _sha256_file(binding_path),
                "authority_source_file_denominators": authority_denominators,
                "selected_stratum_count": None,
                "qualifying_observation_denominator": None,
            },
        )
        payload["status"] = "not_established"
        return payload
    if batch_lineage.get("authoritative_for") != ["academic_claim_edge_publishability"]:
        payload = _terminal(
            mode="measure",
            database=database,
            code="calibration_authority_purpose_mismatch",
            detail="the CAS batch lacks the exact edge-publishability authority purpose",
            extra={
                "authority_batch_lineage": batch_lineage,
                "authority_source_file_denominators": authority_denominators,
                "selected_stratum_count": None,
                "qualifying_observation_denominator": None,
            },
        )
        payload["status"] = "not_established"
        return payload

    try:
        from polisyos.runtime.quality.credal_reference import build_credal_reference

        reference = build_credal_reference(repo_root)
    except (FileNotFoundError, OSError, RuntimeError, TypeError, ValueError) as exc:
        payload = _terminal(
            mode="measure",
            database=database,
            code="owner_reference_unavailable",
            detail=f"{type(exc).__name__}: {exc}",
            extra={
                "authority_batch_lineage": batch_lineage,
                "authority_source_file_denominators": authority_denominators,
                "selected_stratum_count": None,
                "qualifying_observation_denominator": None,
            },
        )
        payload["status"] = "not_established"
        return payload
    bound_owner = binding.get("owner_binding")
    if not isinstance(bound_owner, dict) or (
        bound_owner.get("reference_epoch") != reference.reference_epoch
        or bound_owner.get("reference_hash") != reference.reference_hash
    ):
        payload = _terminal(
            mode="measure",
            database=database,
            code="owner_reference_changed_after_binding",
            detail="the live owner reference differs from the frozen binding receipt",
            extra={
                "bound_reference_epoch": (
                    bound_owner.get("reference_epoch") if isinstance(bound_owner, dict) else None
                ),
                "live_reference_epoch": reference.reference_epoch,
                "bound_reference_hash": (
                    bound_owner.get("reference_hash") if isinstance(bound_owner, dict) else None
                ),
                "live_reference_hash": reference.reference_hash,
                "selected_stratum_count": None,
                "qualifying_observation_denominator": None,
            },
        )
        payload["status"] = "not_established"
        return payload

    try:
        connection = duckdb.connect(str(database), read_only=True)
        try:
            inventory = _database_inventory(connection)
            cursor = connection.execute(CALIBRATION_SQL)
            calibration_output_fields = tuple(str(item[0]) for item in cursor.description)
            if calibration_output_fields != CALIBRATION_FIELDS:
                raise ValueError(
                    f"calibration output schema mismatch: {calibration_output_fields!r}"
                )
            raw_rows = cursor.fetchall()
        finally:
            connection.close()
    except (duckdb.Error, OSError, ValueError) as exc:
        return _terminal(
            mode="measure",
            database=database,
            code="calibration_query_failed",
            detail=f"{type(exc).__name__}: {exc}",
            extra={"selected_stratum_count": 0},
        )

    normalized_calibration_rows = [
        tuple(row)
        for row in raw_rows
        if len(row) == len(CALIBRATION_FIELDS)
        and all(isinstance(value, str) for value in row)
    ]
    exact_rows = sorted(set(normalized_calibration_rows), key=_encoded_fields)
    rejected_calibration_rows = len(raw_rows) - len(normalized_calibration_rows)
    duplicate_calibration_rows = len(normalized_calibration_rows) - len(exact_rows)
    exclusion_counts: Counter[str] = Counter()
    observations: set[tuple[str, ...]] = set()
    outcome_counts: Counter[str] = Counter()
    grouped_counts: Counter[str] = Counter()
    structural_grouped_counts: Counter[str] = Counter()
    result_artifact_id = str(batch_lineage.get("result_artifact_id") or "")
    reference_epoch = reference.reference_epoch
    for row in exact_rows:
        numeric_id, edge_id, openalex_id, claim_id, edge_src, edge_dst, region, _ = row
        stratum_key = f"{edge_src}|{region}|exact"
        structural_grouped_counts[stratum_key] += 1
        adjudication = verified_rows.get(claim_id)
        if adjudication is None:
            exclusion_counts["verified_adjudication_missing"] += 1
            continue
        if str(adjudication.get("openalex_id") or "") != openalex_id:
            exclusion_counts["adjudication_work_identity_mismatch"] += 1
            continue
        if str(adjudication.get("cause_variable") or "") != edge_src:
            exclusion_counts["adjudication_cause_identity_mismatch"] += 1
            continue
        if str(adjudication.get("effect_variable") or "") != edge_dst:
            exclusion_counts["adjudication_effect_identity_mismatch"] += 1
            continue
        if not bool(adjudication.get("publishable_edge")):
            exclusion_counts["adjudication_not_publishable"] += 1
            outcome_counts["publishable_edge_false_not_projected"] += 1
            continue
        operator_edge = reference.essential_edges.get(("L6_KNOB_OPERATOR", edge_src))
        if not (
            operator_edge is not None
            and operator_edge.edge_id == edge_src
            and operator_edge.status == "confirmed"
        ):
            exclusion_counts["exact_registered_l6_operator_missing"] += 1
            continue
        lever_target_edge = reference.essential_edges.get(
            ("L6_KNOB_WORLD_SLOT", edge_src)
        )
        lever_targets: set[str] = set()
        if lever_target_edge is not None and lever_target_edge.status == "confirmed":
            for completion in lever_target_edge.admissible_completions:
                value = completion.value
                if not isinstance(value, dict):
                    continue
                targets = value.get("target_world_slots")
                if isinstance(targets, list | tuple):
                    lever_targets.update(str(item) for item in targets)
        if edge_dst not in lever_targets:
            exclusion_counts["exact_l6_lever_target_missing"] += 1
            continue
        world_edge = reference.essential_edges.get(("WMR_WORLD_SLOT", edge_dst))
        if not (
            world_edge is not None
            and world_edge.edge_id == edge_dst
            and world_edge.status == "confirmed"
        ):
            exclusion_counts["exact_wmr_world_slot_missing"] += 1
            continue
        has_policy_map = False
        for edge in reference.essential_edges.values():
            if edge.modality != "WMR_POLICY_SLOT_MAP" or edge.status != "confirmed":
                continue
            if edge.edge_id.endswith(f":{edge_dst}") or edge.edge_id == edge_dst:
                has_policy_map = True
            for completion in edge.admissible_completions:
                value = completion.value
                if isinstance(value, dict) and str(
                    value.get("world_slot") or value.get("slot_id") or ""
                ) == edge_dst:
                    has_policy_map = True
        if not has_policy_map:
            exclusion_counts["exact_writable_wmr_policy_map_missing"] += 1
            continue
        if not result_artifact_id:
            exclusion_counts["authority_result_artifact_missing"] += 1
            continue
        observation_key = (
            result_artifact_id,
            claim_id,
            openalex_id,
            numeric_id,
            edge_id,
            region,
            reference_epoch,
        )
        if observation_key in observations:
            exclusion_counts["duplicate_observation_key"] += 1
            continue
        observations.add(observation_key)
        grouped_counts[stratum_key] += 1
        outcome_counts["publishable_edge_true_plus_exact_owner_identity"] += 1

    selected_key = "|".join(
        (
            str(selected_stratum["operator_family"]),
            str(selected_stratum["reference_region"]),
            str(selected_stratum["relation_type"]),
        )
    )
    selected_count = int(grouped_counts.get(selected_key, 0))
    complete_grouped_counts = {
        key: int(grouped_counts.get(key, 0))
        for key in sorted(structural_grouped_counts)
    }
    terminal = selected_count < 20
    return {
        "schema_version": "gy-pr1a-task0-feasibility.v1",
        "mode": "measure",
        "recorded_at": _now(),
        "status": "negative_terminal" if terminal else "feasible",
        "terminal_code": "selected_stratum_below_minimum" if terminal else None,
        "terminal_detail": (
            "the immutable selected stratum has fewer than 20 qualifying observations"
            if terminal
            else None
        ),
        "database_path": str(database),
        "database_sha256": current_db_hash,
        "binding_receipt_path": str(binding_path),
        "binding_receipt_sha256": _sha256_file(binding_path),
        "journal_binding_seal": journal_binding_seal,
        "selection_receipt_path": binding["selection_receipt_path"],
        "selection_receipt_sha256": binding["selection_receipt_sha256"],
        "selection_digest": binding["selection_digest"],
        "selected": selected,
        "selected_stratum": selected_stratum,
        "selected_stratum_key": selected_key,
        "minimum_required": 20,
        "selected_stratum_count": selected_count,
        "complete_structural_row_denominator": len(exact_rows),
        "raw_calibration_query_row_denominator": len(raw_rows),
        "rejected_calibration_rows": rejected_calibration_rows,
        "duplicate_calibration_rows_collapsed": duplicate_calibration_rows,
        "calibration_output_schema": CALIBRATION_FIELDS,
        "verified_adjudication_denominator": len(verified_rows),
        "qualifying_observation_denominator": len(observations),
        "structural_grouped_stratum_counts": dict(sorted(structural_grouped_counts.items())),
        "grouped_stratum_counts": complete_grouped_counts,
        "outcome_label_counts": dict(sorted(outcome_counts.items())),
        "exclusion_counts": dict(sorted(exclusion_counts.items())),
        "authority_resolution_error": None,
        "authority_source_file_denominators": authority_denominators,
        "authority_batch_lineage": batch_lineage,
        "runtime_projection_rule": {
            "rule_id": "cg2_production_academic_skg_adjudication_v1",
            "input_authority_used_only_for": "academic_claim_edge_publishability",
            "projected_relation_outcome": "exact",
            "projection_predicates": [
                "publishable_edge_true",
                "exact_claim_edge_work_identity_recomputed",
                "exact_registered_l6_operator_recomputed",
                "exact_writable_wmr_target_recomputed",
                "cas_lineage_verified",
            ],
            "false_publishability_rows_are_not_relation_negatives": True,
            "statistical_probability_claim": False,
            "governance_admissibility_claim": False,
        },
        "owner_reference_epoch": reference.reference_epoch,
        "owner_reference_hash": reference.reference_hash,
        "database_inventory": inventory,
        "script": _script_identity(),
        "claim_boundary": "internal_engineering_feasibility_no_probability",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("select", "bind", "measure"), required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--repo-root", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    database = args.database.resolve()
    lock_path = SELECTION_LOCK_PATH
    if args.mode == "select":
        receipt_path = SELECTION_RECEIPT_PATH
        if receipt_path.exists():
            raise SystemExit("pre-registered selection receipt path already exists")
        payload = select_case(database, lock_path)
    elif args.mode == "bind":
        if args.repo_root is None:
            raise SystemExit("--repo-root is required for --mode bind")
        receipt_path = BINDING_RECEIPT_PATH
        if receipt_path.exists():
            raise SystemExit("pre-registered binding receipt path already exists")
        payload = bind_selected_case(
            database,
            SELECTION_RECEIPT_PATH,
            lock_path,
            args.repo_root.resolve(),
        )
    else:
        if args.repo_root is None:
            raise SystemExit("--repo-root is required for --mode measure")
        receipt_path = MEASUREMENT_RECEIPT_PATH
        if receipt_path.exists():
            raise SystemExit("pre-registered measurement receipt path already exists")
        payload = measure_calibration(
            database,
            BINDING_RECEIPT_PATH,
            lock_path,
            args.repo_root.resolve(),
        )
    receipt_bytes = _persist_receipt(receipt_path, payload)
    sys.stdout.buffer.write(receipt_bytes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Initial chronology state

- first owner-data inspection: `not_started`;
- selector invocation: `not_started`;
- selected candidate/estimand binding: `not_started`;
- owner adjudication: `not_started`;
- calibration feasibility measurement: `not_started`;
- substitutions: none;
- deviations: none;
- negative terminals: none;
- public publication: `not_established`;
- correction: none;
- prohibited substitution found: `false`.

## Event 1 — first inspection and immutable negative terminal

- Appended at: `2026-09-02T12:43:40+03:00`.
- First owner-data inspection / first result-bearing run:
  `2026-09-02T09:41:00.167533+00:00`.
- Preceding custody commit: `16c1d28e7f1ff673927f0886a9741c0fbe4e5b6b`.
- Exact registered selection command: executed once.
- Process exit: `0`; the instrument represents an honest terminal in its receipt rather than as a
  process crash.
- Receipt status: `negative_terminal`.
- Terminal code: `selector_required_table_missing`.
- Capability disposition: `not_established`; no selected stratum or calibration-count predicate
  was reached.
- Structural denominator: `0`.
- Required-table denominator/present: `7 / 6`.
- Missing required table: `ac_skg_span_grounded_claims`.
- Terminal detail: `the exact committed query contract cannot execute`.
- No structural row was returned or inspected; no candidate, estimand, stratum, or calibration
  outcome was selected.
- The invoked provisioned worktree path canonicalized to
  `/Users/deniskopylov/polisyos/policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb`.
  The recorded database SHA-256 is
  `583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967`.

The plan says a missing required table is an empty structural population and a terminal, expressly
denying permission to use an ambient view or alternate join. It also says an empty structural
population is a zero result that stops the task. Phase-2 stop rule 1 therefore fires before binding,
calibration measurement, CG2 implementation, N7 source edits, or any promotion attempt. The nearby
table names visible in the catalog are not substitutes and were not queried. This terminal is not
rerun, repaired, rescored, or replaced.

### Selection custody seal

selection_receipt_sha256: 4127d689edabf279e0fc473c1f1f779448e935a644a8c355481e35f458e8ef5b
selection_lock_sha256: b982b3841bedecfe2e0ddc5e033892af8e2c8cb7a6878c3fee06ed3091479eae
selection_script_sha256: 3a7b23508d1947a1f8733a246080d1c2fb8fe2056771c29e1836c3afe8d7b627
selection_plan_commit: 7781da8e9a47f13d39a035dc3bc2f6810d9fa0e8
selection_plan_blob: b5d50b8f397733e99afa84f9634d4dfcf40c4d43

The fixed one-shot lock is `selection_invocation_consumed`; it was claimed at
`2026-09-02T09:40:58.738032+00:00`. No binding or measurement receipt exists. The seal records the
failed first attempt without converting it into evidence for a later attempt.

### Exact selection receipt

```json
{
  "database_exists": true,
  "database_inventory": {
    "missing_required_tables": [
      "ac_skg_span_grounded_claims"
    ],
    "required_table_denominator": 7,
    "required_tables_present": 6,
    "table_denominator": 27,
    "table_names": [
      "ac_article_extractions",
      "ac_boundary_conditions",
      "ac_causal_claims",
      "ac_causal_claims_raw",
      "ac_claim_adjudications",
      "ac_ingest_errors",
      "ac_parameter_estimates",
      "ac_runs",
      "ac_skg_articles",
      "ac_skg_canonization_cache",
      "ac_skg_contested_edges",
      "ac_skg_context_attributes",
      "ac_skg_context_profiles",
      "ac_skg_edge_evidence",
      "ac_skg_edges",
      "ac_skg_family_edges",
      "ac_skg_moderation_edges",
      "ac_skg_parameters",
      "ac_skg_simulation_parameters",
      "ac_skg_transport_scores",
      "ac_skg_variable_synonyms",
      "ac_skg_variables",
      "ac_skg_versions",
      "ac_topic_selections",
      "ac_topics",
      "ac_work_concepts",
      "ac_works"
    ]
  },
  "database_path": "/Users/deniskopylov/polisyos/policy-engine/production_data/policyos_academic_runtime_slim_20260411T112032Z/academic/graph/scholar_knowledge.duckdb",
  "database_sha256": "583233169ab729bbcf4c7189c60ff97ba98e3b5146aded44402c87eaccf3a967",
  "mode": "select",
  "recorded_at": "2026-09-02T09:41:00.167533+00:00",
  "schema_version": "gy-pr1a-task0-feasibility.v1",
  "script": {
    "binding_query_sha256": "d355339a2675bd74523aa9cde2ab2bbe65cf799588a252ea9127622bc06afcfd",
    "calibration_query_sha256": "37188eb2fd5af23b102146ba401b3af82831ee1db9a3b97366a7af27493b8d3c",
    "path": "/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/.superpowers/sdd/2026-09-02-gy-pr1a-data-only-promotion/task-0-feasibility.py",
    "plan_blob": "b5d50b8f397733e99afa84f9634d4dfcf40c4d43",
    "plan_commit": "7781da8e9a47f13d39a035dc3bc2f6810d9fa0e8",
    "python_executable": "/Users/deniskopylov/polisyos/.worktrees/gy-pr1a-data-only-promotion/policy-engine/.venv/bin/python",
    "python_version": "3.14.0 (main, Oct  7 2025, 09:34:52) [Clang 17.0.0 (clang-1700.0.13.3)]",
    "selector_query_sha256": "a69f142d098b4e6f3feb382f9ba0427a399415421bc918813eeb7300a2d770c6",
    "sha256": "3a7b23508d1947a1f8733a246080d1c2fb8fe2056771c29e1836c3afe8d7b627"
  },
  "status": "negative_terminal",
  "structural_denominator": 0,
  "terminal_code": "selector_required_table_missing",
  "terminal_detail": "the exact committed query contract cannot execute"
}
```

### INT-K06 custody chronology after the terminal

- prospectivity: `not_established` as a public claim; repository evidence shows the plan and
  complete instrument committed before this first inspection;
- firstness: `not_established` as a public claim; this lane records one invocation and the one-shot
  lock is consumed;
- substitutions: none;
- chronology: preregistration commit `16c1d28e7f1ff673927f0886a9741c0fbe4e5b6b` precedes the
  `2026-09-02T09:41:00.167533+00:00` terminal receipt;
- adjudication: the plan's predeclared missing-table rule applies; no discretionary adjudication;
- deviations: none; the executor followed the registered query and stopped on its registered
  terminal instead of substituting a table;
- negative terminals: one — `selector_required_table_missing`, structural denominator `0`;
- capability disposition: `not_established`; the fixed structural selector could not execute
  because its required table is absent. No candidate, selected stratum, or `>=20` calibration
  measurement exists;
- publication: `not_established`; nothing here is projected as a governed promotion or statistical
  claim;
- correction: none;
- prohibited substitution found: `false`.

### Capability finding

The data-only no-appointment ruling remains intact. The fixed structural selector could not execute
because its required table is absent, so availability of the preregistered genuine
production-owned CG2 population is `not_established`; no candidate, selected stratum, or `>=20`
calibration measurement exists. This nevertheless stops GY-PR1a under the preregistered
fixed-source terminal. It does not authorize a substitute source, synthesized population, source
edit, or weakening of the selector. Candidate eligibility and the eleven-clause acceptance
predicate are `not_established`; zero clauses are claimed satisfied because execution terminated
before a candidate existed. No truth-bearing object was constructed directly.

### Exact append-only prose for architect transcription

For `first-promotion-candidate-with-complete-evidence`:

> **BLOCKED 2026-09-02 — FIXED TASK-0 SELECTOR TERMINAL.** The committed selector could not
> execute because required table `ac_skg_span_grounded_claims` is missing (`6/7` required tables
> present); receipt status is `negative_terminal`, terminal code
> `selector_required_table_missing`, and `structural_denominator=0`. This is not an
> eligible-candidate count of zero: the candidate predicate is `not_established`, so the plan
> requires stopping before candidate construction, injection, or promotion. The row remains
> blocked on the engineering producer chain: N8 persisted bound `ValueGateReceipt` plus valid
> `value_ready`, and production N9 context wiring. No institutional appointment is required for
> PR1a.

For `gy-promotion-obligations-scope-insufficient`:

> **BLOCKED 2026-09-02 — SHARED FIELD-PILOT CLOSURE SIGNAL.** The unconditional
> `scope_insufficient` defect is repaired. The fixed Task-0 selector nevertheless terminated
> before candidate selection because `ac_skg_span_grounded_claims` is missing and
> `structural_denominator=0`; no candidate or receipt may be constructed from this run. The prior
> complete census remains authoritative: data-only production `3 full / 0 scope-only`;
> field-pilot production `4 full / 1 scope-only`, with the sole scope-only path
> `_eval_safety_obligation` at `promotion_sequence.py:5197`. Closure still requires the
> producer-issued persisted canonical field-pilot receipt for `GY-O0-NC-01`. The data-only PR1a
> path requires no appointment.

For the GY plan's `GY-PR1` / PR1a row:

> **GY-PR1 / PR1a — `not_started`; Task-0 attempt terminal.** PR1a remains the
> engineering-only data path: produce and persist the bound N8 `ValueGateReceipt`/`value_ready`,
> wire production N9's existing writer-input keys, and reach a real canonical data-only
> `consumer_promotable=True` receipt. The fixed selector receipt is negative-terminal
> (`selector_required_table_missing`; `structural_denominator=0`), so the plan's prerequisite gate
> stops before Task 1 and cannot treat zero as a successful empty candidate set. PR1b remains
> separate pilot-grade work and is the only half requiring an institutional EvalSafety
> appointment.

No existing CG2 debt row is changed by this attempt: the authorized CG2 implementation never
began. The capability finding above is the input for an architect-owned new row or a future
supersession of the first-promotion candidate row; this journal does not silently invent an active
register identifier.

## Event 2 — terminal closeout verification

- Recorded at: `2026-09-02T12:57:03+03:00`.
- `git diff --check`: exit `0`.
- Complete tracked `src/**/*.py` denominator: `2,617`; delta from the carried baseline: `0`.
- Changed tracked path denominator: one, this append-only journal; no production source, test,
  frozen receipt epoch, OpenAPI source, generated client, schema, or active-plan file changed.
- Selection lock SHA-256 remains
  `b982b3841bedecfe2e0ddc5e033892af8e2c8cb7a6878c3fee06ed3091479eae`.
- Selection receipt SHA-256 remains
  `4127d689edabf279e0fc473c1f1f779448e935a644a8c355481e35f458e8ef5b`.
- Binding receipt: absent, as the terminal requires.
- Calibration-feasibility receipt: absent, as the terminal requires.
- No test was added or run after the production terminal: stop rule 1 forbids the source/test work
  that would create a red-first group.
- `EVAL_SAFETY` was not evaluated because no candidate existed; no result from this run is described
  as satisfied, omitted, exempted, `scope_insufficient`, or `NOT_APPLICABLE_DATA_ONLY`.

`check_docs_lifecycle.py` exited `1` with exactly the six carried findings and no journal finding:
two missing `status`/`owner` fields in `docs/plans/active/LEDGER.md`, plus four stale
`frontend/runtime-dashboard` references in the Atlas adoption ledger, Atlas archive map, frontend
Atlas adjudication, and PAO-R0 audit. The bound debt checker was not invoked: the plan reserves its
single captured invocation for Task 7, and this attempt terminated at Task 0. Its closeout status in
this stopped attempt is therefore `not_established`, not inferred from terminal transport or a
carried baseline.

Pattern closeout: the stop preserves P01/P02 capability honesty, P32 resolve-bind-verify, P33's
witness/spec distinction, P35's complete denominator, P37 predicate provenance, and P38's
property/proxy distinction. In particular, `structural_denominator=0` proves the fixed selector had
no executable structural population; it does not prove that zero candidates would be eligible or
that a hypothetical selected stratum would contain fewer than 20 observations.
