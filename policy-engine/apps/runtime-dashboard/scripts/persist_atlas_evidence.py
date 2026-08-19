"""Persist one Atlas verification payload and its content-bound receipt in Core CAS."""

from __future__ import annotations

import base64
import binascii
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.core.artifacts import (
        ArtifactID,
        ArtifactManifest,
        ArtifactStore,
        ProducerInfo,
        VerificationReport,
    )
    from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo
    from polisyos.core.canon import CanonSpec


OPERATION = "persist_atlas_evidence"
HEALTH_OPERATION = "persist_atlas_health_metrics"
READINESS_OPERATION = "persist_atlas_surface_readiness_claims"
RAW_REPORT_KIND = "atlas_evidence_raw_runner_report"
RAW_REPORT_INPUT_ROLE = "runner_report"
PAYLOAD_KIND = "atlas_evidence_verification_payload"
PAYLOAD_SCHEMA = {
    "id": "polisyos.atlas.evidence-verification-payload",
    "version": "1.0.0",
}
RECEIPT_KIND = "atlas_evidence_receipt"
RECEIPT_SCHEMA = {
    "id": "polisyos.atlas.evidence-receipt",
    "version": "1.0.0",
}
RECEIPT_INPUT_ROLE = "verification_payload"
PRODUCER_COMPONENT = "polisyos.atlas.evidence_persistence@1.0.0"
PRODUCER_VERSION = "1.0.0"
IMPLEMENTATION_PATHS = (
    "apps/runtime-dashboard/src/test/evidence/atlasEvidenceArtifact.ts",
    "apps/runtime-dashboard/src/test/evidence/atlasAutomatedEvidenceCapture.ts",
    "apps/runtime-dashboard/src/test/evidence/captureAtlasEvidence.ts",
    "apps/runtime-dashboard/scripts/capture_atlas_evidence.mjs",
    "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
)
HEALTH_REPORT_KIND = "atlas_health_metric_report"
HEALTH_REPORT_SCHEMA = {
    "id": "polisyos.atlas.health-metric-report",
    "version": "1.0.0",
}
HEALTH_SNAPSHOT_KIND = "atlas_health_metric_snapshot"
HEALTH_SNAPSHOT_SCHEMA = {
    "id": "polisyos.atlas.health-metric-snapshot",
    "version": "1.0.0",
}
HEALTH_REPORT_INPUT_ROLE = "measurement_report"
HEALTH_PRODUCER_SCRIPT = "apps/runtime-dashboard/scripts/measure_atlas_health.mjs"
HEALTH_SOURCE_VALIDATOR = (
    "apps/runtime-dashboard/scripts/validate_atlas_health_sources.py"
)
HEALTH_INSTRUMENT_COMPONENT = "polisyos.atlas.health_metric_instrument@1.0.0"
HEALTH_ADMISSION_COMPONENT = "polisyos.atlas.health_metric_admission@1.0.0"
HEALTH_IMPLEMENTATION_PATHS = (
    "apps/runtime-dashboard/src/test/evidence/atlasHealthMetrics.ts",
    HEALTH_PRODUCER_SCRIPT,
    HEALTH_SOURCE_VALIDATOR,
    "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
    "pyproject.toml",
    "uv.lock",
)
HEALTH_INSTRUMENT_PATHS = HEALTH_IMPLEMENTATION_PATHS[:3]
READINESS_REPORT_KIND = "atlas_surface_readiness_claim_report"
READINESS_REPORT_SCHEMA = {
    "id": "polisyos.atlas.surface-readiness-claim-report",
    "version": "2.0.0",
}
READINESS_PROJECTION_KIND = "atlas_surface_readiness_claim_projection"
READINESS_PROJECTION_SCHEMA = {
    "id": "polisyos.atlas.surface-readiness-claim-projection",
    "version": "2.0.0",
}
READINESS_REPORT_INPUT_ROLE = "claim_report"
READINESS_PRODUCER_SCRIPT = (
    "apps/runtime-dashboard/scripts/reconcile_atlas_surface_readiness.mjs"
)
READINESS_RECONCILER_SOURCE = (
    "apps/runtime-dashboard/src/test/evidence/"
    "atlasSurfaceReadinessReconciliation.ts"
)
READINESS_TEST_PATH = (
    "apps/runtime-dashboard/src/test/evidence/"
    "atlasSurfaceReadinessReconciliation.test.ts"
)
READINESS_LEDGER_PATH = (
    "architecture/atlas_surfaces/live-application-readiness-ledger.json"
)
READINESS_SCHEMA_PATH = (
    "architecture/atlas_surfaces/surface-readiness-ledger.schema.json"
)
READINESS_ROUTE_SOURCE = "apps/runtime-dashboard/src/app/routes/routes.tsx"
READINESS_ROUTE_TEST = "apps/runtime-dashboard/src/app/routes/routes.test.tsx"
READINESS_RECONCILER_COMPONENT = (
    "polisyos.atlas.surface_readiness_reconciler@2.0.0"
)
READINESS_ADMISSION_COMPONENT = (
    "polisyos.atlas.surface_readiness_admission@2.0.0"
)
READINESS_OBSERVED_ATTESTATION_SCOPE = (
    "observed_by_reconciler attests intake closure: this process produced the row through "
    "a closed path by running each available applicable canonical check itself and recording "
    "any unavailable claim check as unavailable; no report, exit code, status, or basis was "
    "supplied by a caller, and runner code being unmodified on disk is not attested."
)
READINESS_IMPLEMENTATION_PATHS = (
    READINESS_RECONCILER_SOURCE,
    READINESS_TEST_PATH,
    READINESS_PRODUCER_SCRIPT,
    "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
    HEALTH_SOURCE_VALIDATOR,
    READINESS_LEDGER_PATH,
    READINESS_SCHEMA_PATH,
    READINESS_ROUTE_SOURCE,
    READINESS_ROUTE_TEST,
)
HEALTH_METRIC_IDS = (
    "primitive_adoption",
    "fail_closed_fidelity",
    "audience_enforcement",
    "surface_missing_closure",
    "evidence_coverage",
    "machine_twin_parity",
    "honesty_comprehension",
)
DENIED_USES = [
    "component_maturity",
    "design_authority",
    "policy_authority",
    "promotion",
    "publication",
    "runtime_authority",
    "stable",
]
HEALTH_CANDIDATE_DENIED_USES = ["descriptive_atlas_health_measurement", *DENIED_USES]
HEALTH_CHILD_ENV = {
    "HOME": "/var/empty",
    "LANG": "C",
    "LC_ALL": "C",
    "PATH": "/usr/bin:/bin",
    "TZ": "UTC",
}
HEALTH_DENIED_ENV_PREFIXES = ("NODE_", "PYTHON", "VITE_", "npm_", "NPM_", "PNPM_")
TRUSTED_NODE_LOCATORS = (
    Path("/opt/homebrew/bin/node"),
    Path("/usr/local/bin/node"),
    Path("/usr/bin/node"),
)
BOUND_FIELDS = ("evidence_kind", "subject", "rule", "provenance", "times", "result")


class AtlasEvidencePersistenceError(ValueError):
    """Report a fail-closed Atlas evidence persistence contract violation."""


def _policy_engine_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ensure_worktree_import_root() -> None:
    source_root = str(_policy_engine_root() / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AtlasEvidencePersistenceError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_non_json_constant(value: str) -> NoReturn:
    raise AtlasEvidencePersistenceError(f"non-JSON numeric constant: {value}")


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise AtlasEvidencePersistenceError("stdin must contain one JSON request")
    try:
        request = json.loads(
            raw,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except json.JSONDecodeError as exc:
        raise AtlasEvidencePersistenceError(f"stdin is not valid JSON: {exc.msg}") from exc
    if not isinstance(request, dict):
        raise AtlasEvidencePersistenceError("request must be a JSON object")
    return request


def _validate_request(request: dict[str, Any]) -> None:
    operation = request.get("operation")
    if operation in {HEALTH_OPERATION, READINESS_OPERATION}:
        if set(request) != {"operation"}:
            label = (
                "health-metric"
                if operation == HEALTH_OPERATION
                else "surface-readiness"
            )
            raise AtlasEvidencePersistenceError(
                f"{label} request keys must be exactly ['operation']; "
                f"got {sorted(request)}"
            )
        return

    expected = {"operation", "payload", "raw_report_base64", "receipt"}
    actual = set(request)
    if actual != expected:
        raise AtlasEvidencePersistenceError(
            f"request keys must be exactly {sorted(expected)}; got {sorted(actual)}"
        )
    if request["operation"] != OPERATION:
        raise AtlasEvidencePersistenceError(f"operation must equal {OPERATION!r}")
    if not isinstance(request["raw_report_base64"], str) or not request["raw_report_base64"]:
        raise AtlasEvidencePersistenceError("raw_report_base64 must be a non-empty string")
    if not isinstance(request["payload"], dict):
        raise AtlasEvidencePersistenceError("payload must be a JSON object")
    if not isinstance(request["receipt"], dict):
        raise AtlasEvidencePersistenceError("receipt must be a JSON object")


def _decode_raw_report(value: str) -> bytes:
    try:
        raw_report = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AtlasEvidencePersistenceError("raw_report_base64 is not canonical base64") from exc
    if not raw_report:
        raise AtlasEvidencePersistenceError("raw runner report must not be empty")
    try:
        json.loads(
            raw_report.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AtlasEvidencePersistenceError("raw runner report must be valid UTF-8 JSON") from exc
    return raw_report


def _require_exact_mapping(value: object, expected: Mapping[str, object], *, field: str) -> None:
    if value != dict(expected):
        raise AtlasEvidencePersistenceError(f"{field} must equal the C07 contract")


def _run_git(*args: str) -> str:
    result = subprocess.run(  # noqa: S603 - fixed executable; arguments are module-owned.
        ["/usr/bin/git", *args],
        cwd=_policy_engine_root(),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise AtlasEvidencePersistenceError(
            f"capture implementation git provenance failed ({result.returncode}): "
            f"{result.stderr.strip()}"
        )
    return result.stdout


def _capture_paths_provenance(paths: tuple[str, ...]) -> dict[str, Any]:
    files: list[dict[str, str]] = []
    aggregate = hashlib.sha256()
    for relative_path in paths:
        file_sha256 = hashlib.sha256(
            (_policy_engine_root() / relative_path).read_bytes()
        ).hexdigest()
        files.append({"path": relative_path, "sha256": file_sha256})
        aggregate.update(f"{relative_path}\0{file_sha256}\n".encode())
    repository_revision = _run_git("rev-parse", "HEAD").strip()
    dirty = bool(_run_git("status", "--porcelain=v1").strip())
    return {
        "implementation_sha256": aggregate.hexdigest(),
        "files": files,
        "repository_revision": repository_revision,
        "dirty": dirty,
    }


def _capture_implementation_provenance() -> dict[str, Any]:
    return _capture_paths_provenance(IMPLEMENTATION_PATHS)


def _capture_health_implementation_provenance() -> dict[str, Any]:
    return _capture_paths_provenance(HEALTH_IMPLEMENTATION_PATHS)


def _validate_transport_contract(
    payload: dict[str, Any],
    receipt: dict[str, Any],
    *,
    implementation_provenance: Mapping[str, object],
) -> None:
    expected_payload_keys = {
        "payload_schema",
        "evidence_kind",
        "subject",
        "rule",
        "provenance",
        "times",
        "result",
        "details",
    }
    if set(payload) != expected_payload_keys:
        raise AtlasEvidencePersistenceError(
            "payload keys must equal the C07 verification-payload envelope"
        )
    expected_receipt_keys = {
        "receipt_schema",
        "authority",
        "evidence_kind",
        "subject",
        "rule",
        "provenance",
        "audiences",
        "times",
        "result",
        "retention",
    }
    if set(receipt) != expected_receipt_keys:
        raise AtlasEvidencePersistenceError(
            "receipt transport keys must equal the C07 receipt without evidence_payload_ref"
        )
    _require_exact_mapping(payload.get("payload_schema"), PAYLOAD_SCHEMA, field="payload_schema")
    _require_exact_mapping(receipt.get("receipt_schema"), RECEIPT_SCHEMA, field="receipt_schema")
    if payload.get("evidence_kind") not in {
        "automated_browser",
        "automated_keyboard",
        "manual_at",
    }:
        raise AtlasEvidencePersistenceError("payload evidence_kind is outside the C07 closed set")
    if receipt.get("evidence_kind") != payload.get("evidence_kind"):
        raise AtlasEvidencePersistenceError("receipt evidence_kind does not bind the payload")
    if not isinstance(payload.get("details"), dict) or not payload["details"]:
        raise AtlasEvidencePersistenceError("payload details must be a non-empty JSON object")
    raw_report_sha256 = payload["details"].get("raw_report_sha256")
    if (
        not isinstance(raw_report_sha256, str)
        or len(raw_report_sha256) != 64
        or any(character not in "0123456789abcdef" for character in raw_report_sha256)
    ):
        raise AtlasEvidencePersistenceError("payload raw_report_sha256 must be lowercase SHA-256")
    if payload["details"].get("capture_implementation") != dict(implementation_provenance):
        raise AtlasEvidencePersistenceError("capture implementation provenance mismatch")

    _require_exact_mapping(
        receipt.get("authority"),
        {
            "authoritative_for": ["atlas_evidence_capture"],
            "may_not_use_for": DENIED_USES,
        },
        field="receipt authority",
    )
    retention = receipt.get("retention")
    if not isinstance(retention, dict):
        raise AtlasEvidencePersistenceError("receipt retention must be a JSON object")
    if retention.get("retention_class") != "content_addressed_runtime_artifacts":
        raise AtlasEvidencePersistenceError("receipt retention_class does not match C07")
    if retention.get("retention_days") != 365:
        raise AtlasEvidencePersistenceError("receipt retention_days does not match C07")
    if retention.get("cleanup_policy") != "manual_approval_only":
        raise AtlasEvidencePersistenceError("receipt cleanup_policy does not match C07")

    for field in BOUND_FIELDS:
        if field not in payload or field not in receipt:
            raise AtlasEvidencePersistenceError(f"missing semantic binding field: {field}")
        if payload[field] != receipt[field]:
            raise AtlasEvidencePersistenceError(
                f"receipt does not bind verification payload field: {field}"
            )


def _canon_spec() -> CanonSpec:
    from polisyos.core.canon import CanonSpec

    return CanonSpec(
        name="polisyos.canon.json",
        version="0.2.0",
        forbid_floats=False,
        forbid_nan_inf=True,
        exclude_none=True,
        max_depth=128,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _governance() -> ArtifactGovernanceInfo:
    from polisyos.core.artifacts.manifest import (
        ArtifactEncryptionPolicyInfo,
        ArtifactGovernanceInfo,
        ArtifactRetentionPolicyInfo,
    )

    return ArtifactGovernanceInfo(
        classification="internal",
        retention=ArtifactRetentionPolicyInfo(
            scope="cas",
            retention_days=365,
            delete_on_expiry=False,
        ),
        encryption=ArtifactEncryptionPolicyInfo(
            mode="none",
            enforced=False,
            verified=False,
        ),
    )


def _producer(
    implementation_provenance: Mapping[str, object],
    *,
    component: str = PRODUCER_COMPONENT,
) -> ProducerInfo:
    from polisyos.core.artifacts import GitInfo, ProducerInfo

    return ProducerInfo(
        component=component,
        version=PRODUCER_VERSION,
        git=GitInfo(
            commit=str(implementation_provenance["repository_revision"]),
            dirty=bool(implementation_provenance["dirty"]),
        ),
    )


def _build_store() -> ArtifactStore:
    from polisyos.core.artifacts.backends.config import (
        ArtifactStoreConfig,
        build_artifact_store,
    )

    return build_artifact_store(ArtifactStoreConfig.from_env())


def _assert_verification(report: VerificationReport, *, label: str) -> None:
    if not report.ok:
        detail = report.error or "unknown integrity error"
        raise AtlasEvidencePersistenceError(f"{label} CAS integrity verification failed: {detail}")


def _assert_manifest(
    manifest: ArtifactManifest,
    *,
    kind: str,
    schema_name: str | None,
    schema_version: str | None,
    expected_inputs: list[tuple[str, str]],
    expected_producer: ProducerInfo,
    expect_canon: bool = True,
) -> None:
    if manifest.kind != kind:
        raise AtlasEvidencePersistenceError(f"{kind} manifest kind mismatch")
    if manifest.media_type != "application/json":
        raise AtlasEvidencePersistenceError(f"{kind} manifest media_type mismatch")

    schema = manifest.artifact_schema
    if schema_name is None:
        if schema is not None:
            raise AtlasEvidencePersistenceError(f"{kind} manifest must not invent a schema")
    elif schema is None or schema.name != schema_name or schema.version != schema_version:
        raise AtlasEvidencePersistenceError(f"{kind} manifest schema identity mismatch")

    from polisyos.core.artifacts import CanonInfo

    canon = manifest.canon
    if expect_canon:
        if canon != CanonInfo.from_spec(_canon_spec()):
            raise AtlasEvidencePersistenceError(f"{kind} manifest canon metadata mismatch")
    elif canon is not None:
        raise AtlasEvidencePersistenceError(f"{kind} raw bytes must not claim JSON canon metadata")

    producer = manifest.producer
    if producer != expected_producer:
        raise AtlasEvidencePersistenceError(f"{kind} manifest producer mismatch")
    if manifest.governance != _governance():
        raise AtlasEvidencePersistenceError(f"{kind} manifest governance mismatch")

    actual_inputs = [(str(input_ref.artifact_id), input_ref.role) for input_ref in manifest.inputs]
    if actual_inputs != expected_inputs:
        raise AtlasEvidencePersistenceError(
            f"{kind} manifest inputs mismatch: expected {expected_inputs!r}, got {actual_inputs!r}"
        )


def _resolve_json(store: ArtifactStore, artifact_id: ArtifactID, *, label: str) -> object:
    from polisyos.core.canon import from_canonical_bytes

    value = from_canonical_bytes(store.get_bytes(artifact_id))
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise AtlasEvidencePersistenceError(
            f"{label} canonical payload did not decode to plain finite JSON"
        ) from exc
    return value


def persist_atlas_evidence(
    raw_report: bytes,
    payload: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Persist, verify, resolve, and lineage-check one C07 evidence pair.

    Args:
        raw_report: Exact UTF-8 JSON bytes emitted by the declared runner.
        payload: Strict C07 verification payload already validated by the TypeScript owner.
        receipt: Strict C07 receipt fields except the circular ``evidence_payload_ref``.

    Returns:
        A JSON-serializable result containing both CAS refs, verification reports,
        resolved objects, and the receipt's verified payload-lineage edge.

    Raises:
        AtlasEvidencePersistenceError: If storage, integrity, lineage, or binding
            does not satisfy the C07 contract.
    """
    implementation_provenance = _capture_implementation_provenance()
    _validate_transport_contract(
        payload,
        receipt,
        implementation_provenance=implementation_provenance,
    )
    _ensure_worktree_import_root()

    from polisyos.core.artifacts import InputRef, PutOptions, SchemaInfo

    store = _build_store()
    canon_spec = _canon_spec()
    producer = _producer(implementation_provenance)
    raw_report_digest = hashlib.sha256(raw_report).hexdigest()
    if raw_report_digest != payload["details"]["raw_report_sha256"]:
        raise AtlasEvidencePersistenceError("raw runner report does not bind payload digest")
    raw_report_ref = store.put_bytes(
        raw_report,
        PutOptions(
            kind=RAW_REPORT_KIND,
            media_type="application/json",
            producer=producer,
            inputs=[],
            governance=_governance(),
        ),
    )
    raw_report_verification = store.verify(raw_report_ref.artifact_id)
    _assert_verification(raw_report_verification, label="raw runner report")
    raw_report_manifest = store.get_manifest(raw_report_ref.artifact_id)
    _assert_manifest(
        raw_report_manifest,
        kind=RAW_REPORT_KIND,
        schema_name=None,
        schema_version=None,
        expected_inputs=[],
        expected_producer=producer,
        expect_canon=False,
    )
    if store.get_bytes(raw_report_ref.artifact_id) != raw_report:
        raise AtlasEvidencePersistenceError("resolved raw runner report differs from input")

    payload_ref = store.put_json(
        payload,
        PutOptions(
            kind=PAYLOAD_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=PAYLOAD_SCHEMA["id"], version=PAYLOAD_SCHEMA["version"]),
            producer=producer,
            inputs=[
                InputRef(
                    artifact_id=raw_report_ref.artifact_id,
                    role=RAW_REPORT_INPUT_ROLE,
                )
            ],
            governance=_governance(),
        ),
        canon_spec=canon_spec,
    )
    payload_report = store.verify(payload_ref.artifact_id)
    _assert_verification(payload_report, label="verification payload")
    payload_manifest = store.get_manifest(payload_ref.artifact_id)
    _assert_manifest(
        payload_manifest,
        kind=PAYLOAD_KIND,
        schema_name=PAYLOAD_SCHEMA["id"],
        schema_version=PAYLOAD_SCHEMA["version"],
        expected_inputs=[(str(raw_report_ref.artifact_id), RAW_REPORT_INPUT_ROLE)],
        expected_producer=producer,
    )
    resolved_payload = _resolve_json(
        store,
        payload_ref.artifact_id,
        label="verification payload",
    )
    if resolved_payload != payload:
        raise AtlasEvidencePersistenceError("resolved verification payload differs from input")
    if not isinstance(resolved_payload, dict):
        raise AtlasEvidencePersistenceError("resolved verification payload must be a JSON object")

    stored_receipt = dict(receipt)
    stored_receipt["evidence_payload_ref"] = {
        "artifact_id": str(payload_ref.artifact_id),
        "kind": PAYLOAD_KIND,
        "media_type": "application/json",
        "schema_id": PAYLOAD_SCHEMA["id"],
        "schema_version": PAYLOAD_SCHEMA["version"],
    }
    receipt_ref = store.put_json(
        stored_receipt,
        PutOptions(
            kind=RECEIPT_KIND,
            media_type="application/json",
            schema=SchemaInfo(name=RECEIPT_SCHEMA["id"], version=RECEIPT_SCHEMA["version"]),
            producer=producer,
            inputs=[
                InputRef(
                    artifact_id=payload_ref.artifact_id,
                    role=RECEIPT_INPUT_ROLE,
                )
            ],
            governance=_governance(),
        ),
        canon_spec=canon_spec,
    )
    receipt_report = store.verify(receipt_ref.artifact_id)
    _assert_verification(receipt_report, label="evidence receipt")
    receipt_manifest = store.get_manifest(receipt_ref.artifact_id)
    expected_lineage = [(str(payload_ref.artifact_id), RECEIPT_INPUT_ROLE)]
    _assert_manifest(
        receipt_manifest,
        kind=RECEIPT_KIND,
        schema_name=RECEIPT_SCHEMA["id"],
        schema_version=RECEIPT_SCHEMA["version"],
        expected_inputs=expected_lineage,
        expected_producer=producer,
    )
    resolved_receipt = _resolve_json(store, receipt_ref.artifact_id, label="evidence receipt")
    if resolved_receipt != stored_receipt:
        raise AtlasEvidencePersistenceError("resolved evidence receipt differs from stored input")
    if not isinstance(resolved_receipt, dict):
        raise AtlasEvidencePersistenceError("resolved evidence receipt must be a JSON object")
    _validate_transport_contract(
        resolved_payload,
        {key: value for key, value in resolved_receipt.items() if key != "evidence_payload_ref"},
        implementation_provenance=implementation_provenance,
    )
    resolved_payload_ref = resolved_receipt.get("evidence_payload_ref")
    expected_payload_ref = stored_receipt["evidence_payload_ref"]
    if resolved_payload_ref != expected_payload_ref:
        raise AtlasEvidencePersistenceError("resolved receipt payload reference mismatch")

    return {
        "ok": True,
        "operation": OPERATION,
        "raw_report_ref": raw_report_ref.model_dump(mode="json"),
        "payload_ref": payload_ref.model_dump(mode="json"),
        "receipt_ref": receipt_ref.model_dump(mode="json"),
        "raw_report_verification": raw_report_verification.model_dump(mode="json"),
        "payload_verification": payload_report.model_dump(mode="json"),
        "receipt_verification": receipt_report.model_dump(mode="json"),
        "payload_manifest_input": {
            "artifact_id": str(raw_report_ref.artifact_id),
            "role": RAW_REPORT_INPUT_ROLE,
        },
        "receipt_manifest_input": {
            "artifact_id": expected_lineage[0][0],
            "role": expected_lineage[0][1],
        },
        "resolved_payload": {
            "artifact_id": str(payload_ref.artifact_id),
            "payload": resolved_payload,
        },
        "resolved_receipt": {
            "artifact_id": str(receipt_ref.artifact_id),
            "receipt": resolved_receipt,
        },
    }


def _health_source_projection() -> tuple[dict[str, Any], dict[str, Any]]:
    validator_path = _policy_engine_root() / HEALTH_SOURCE_VALIDATOR
    python_locator = _policy_engine_root() / ".venv/bin/python"
    if not python_locator.is_file() or not os.access(python_locator, os.X_OK):
        raise AtlasEvidencePersistenceError(
            "health admission requires the repository-managed Python environment"
        )
    python_executable = python_locator.resolve(strict=True)
    result = subprocess.run(  # noqa: S603 - fixed interpreter and validator paths.
        [str(python_locator), "-I", str(validator_path)],
        cwd=_policy_engine_root(),
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=HEALTH_CHILD_ENV,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise AtlasEvidencePersistenceError(
            f"fixed health source validator failed ({result.returncode}): {stderr}"
        )
    try:
        projection = json.loads(
            result.stdout.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AtlasEvidencePersistenceError(
            "fixed health source validator emitted invalid UTF-8 JSON"
        ) from exc
    if not isinstance(projection, dict):
        raise AtlasEvidencePersistenceError(
            "fixed health source validator must emit one JSON object"
        )
    expected_producer = {
        "producer_id": "polisyos.atlas.health_source_validator",
        "producer_version": "1.0.0",
        "python_executable": str(python_executable),
        "python_version": platform.python_version(),
        "jsonschema_version": importlib.metadata.version("jsonschema"),
        "schema_dialect": "https://json-schema.org/draft/2020-12/schema",
        "implementation_ref": _health_source_ref(
            HEALTH_SOURCE_VALIDATOR,
            "canonical_source_validator",
        ),
    }
    if projection.get("producer") != expected_producer:
        raise AtlasEvidencePersistenceError(
            "fixed health source validator provenance mismatch"
        )
    observation = {
        "executable": str(python_executable),
        "allowed_locator": str(python_locator),
        "executable_sha256": hashlib.sha256(python_executable.read_bytes()).hexdigest(),
        "executable_version": expected_producer["python_version"],
        "validator": HEALTH_SOURCE_VALIDATOR,
        "validator_sha256": hashlib.sha256(validator_path.read_bytes()).hexdigest(),
        "process_exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
        "environment": {
            "mode": "fixed_minimal_allowlist",
            "inherited_names": [],
            "fixed": HEALTH_CHILD_ENV,
            "isolated_python": True,
        },
    }
    return projection, observation


def _health_source_ref(path: str, role: str) -> dict[str, str]:
    return {
        "path": path,
        "sha256": hashlib.sha256((_policy_engine_root() / path).read_bytes()).hexdigest(),
        "role": role,
    }


def _health_basis(
    source_refs: list[dict[str, str]],
    limitation: str | None,
    predicate_provenance: str,
) -> dict[str, Any]:
    return {
        "kind": "observed_by_instrument",
        "producer_id": "polisyos.atlas.health_metric_instrument",
        "producer_version": "1.0.0",
        "predicate_provenance": predicate_provenance,
        "source_refs": source_refs,
        "limitation": limitation,
    }


def _health_ratio(numerator: int, denominator: int) -> dict[str, Any]:
    if denominator <= 0:
        raise AtlasEvidencePersistenceError("health ratio denominator must be positive")
    if numerator == 0:
        return {
            "kind": "zero",
            "reason_code": "observed_zero",
            "numerator": 0,
            "denominator": denominator,
            "ratio": 0,
            "ranking": None,
        }
    return {
        "kind": "measured",
        "reason_code": "observed_ratio",
        "numerator": numerator,
        "denominator": denominator,
        "ratio": numerator / denominator,
        "ranking": None,
    }


def _expected_health_rows(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    readiness = source["readiness"]
    audience = source["audience"]
    cluster = source["cluster"]
    adoption = source["adoption"]
    readiness_count = readiness["entry_count"]
    stable_count = adoption["stable_component_count"]
    stable_covered = adoption["stable_with_browser_and_at_count"]
    closure_count = (
        cluster["surface_missing_count"]
        + cluster["implemented_but_not_orchestrated_count"]
    )
    coverage_measurement = (
        {
            "kind": "incomparable",
            "reason_code": "zero_denominator",
            "numerator": stable_covered,
            "denominator": 0,
            "ratio": None,
            "ranking": None,
            "scope_refs": ["stable-components", "browser-plus-at-manual-evidence"],
        }
        if stable_count == 0
        else _health_ratio(stable_covered, stable_count)
    )
    thresholds = [
        {
            "metric_id": metric_id,
            "status": "not_established",
            "comparator": None,
            "value": None,
            "unit": None,
            "source_ref": None,
        }
        for metric_id in (
            "false_action",
            "false_pass",
            "missed_blocker",
            "unsafe_override",
            "time_to_correct",
            "confidence_vs_correctness",
        )
    ]
    return [
        {
            "metric_id": "primitive_adoption",
            "instrumentation_status": "instrumented",
            "definition": "Share of decision-bearing renders flowing through DS4 primitives.",
            "honest_direction": "Rising; 100% for authority slots.",
            "scope": {
                "scope_id": "ds1-live-readiness-rows",
                "description": f"All {readiness_count} DS1 readiness rows at {readiness['as_of']}.",
            },
            "basis": _health_basis(
                readiness["source_refs"],
                "The owner has no exhaustive decision-bearing-render to DS4-primitive relation.",
                "not_established",
            ),
            "measurement": {
                "kind": "unknown",
                "reason_code": "primitive_relation_not_established",
                "predicate_provenance": "not_established",
            },
            "known_facts": {"readiness_entry_count": readiness_count},
            "thresholds": [],
        },
        {
            "metric_id": "fail_closed_fidelity",
            "instrumentation_status": "instrumented",
            "definition": (
                "Share of blocker, abstention, out-of-envelope, and stale-cached "
                "states rendered as typed states."
            ),
            "honest_direction": "Rising to 100%.",
            "scope": {
                "scope_id": "ds1-live-readiness-rows",
                "description": f"All {readiness_count} DS1 readiness rows at {readiness['as_of']}.",
            },
            "basis": _health_basis(
                readiness["source_refs"],
                "The owner has no exhaustive semantic-state to rendered-state classifier.",
                "not_established",
            ),
            "measurement": {
                "kind": "unknown",
                "reason_code": "render_state_denominator_not_established",
                "predicate_provenance": "not_established",
            },
            "known_facts": {"readiness_entry_count": readiness_count},
            "thresholds": [],
        },
        {
            "metric_id": "audience_enforcement",
            "instrumentation_status": "instrumented",
            "definition": "Share of audience-scoped endpoints with passing server-side deny tests.",
            "honest_direction": "100% before DS12.",
            "scope": {
                "scope_id": "server-audience-denial-proxies",
                "description": (
                    "The current source-level DS20 denial proxies; DS5 final audience "
                    "mapping is absent."
                ),
            },
            "basis": _health_basis(
                audience["source_refs"],
                "Six source proxies are neither a complete endpoint denominator nor a "
                "test-run receipt.",
                "not_established",
            ),
            "measurement": {
                "kind": "unknown",
                "reason_code": "audience_endpoint_denominator_not_established",
                "predicate_provenance": "not_established",
            },
            "known_facts": {"proxy_test_count": audience["proxy_test_count"]},
            "thresholds": [],
        },
        {
            "metric_id": "surface_missing_closure",
            "instrumentation_status": "instrumented",
            "definition": (
                "Open surface_missing or implemented_but_not_orchestrated links in "
                "the cluster map."
            ),
            "honest_direction": "Falling.",
            "scope": {
                "scope_id": "policy-design-case-cluster-map-cells",
                "description": f"All {cluster['cell_count']} canonical cluster-map cells.",
            },
            "basis": _health_basis(
                cluster["source_refs"],
                "The canonical validator is a subordinate recomputation in this closed "
                "instrument, not an independent reconciliation.",
                "recomputed",
            ),
            "measurement": _health_ratio(closure_count, cluster["cell_count"]),
            "known_facts": {
                "cell_count": cluster["cell_count"],
                "implemented_cell_count": cluster["implemented_cell_count"],
                "surface_missing_count": cluster["surface_missing_count"],
                "implemented_but_not_orchestrated_count": cluster[
                    "implemented_but_not_orchestrated_count"
                ],
                "open_or_incomplete_count": cluster["open_or_incomplete_count"],
                "open_cell_count": cluster["open_cell_count"],
                "closure_contract_count": cluster["closure_contract_count"],
            },
            "thresholds": [],
        },
        {
            "metric_id": "evidence_coverage",
            "instrumentation_status": "instrumented",
            "definition": "Share of stable components carrying browser and manual AT evidence.",
            "honest_direction": "100% for stable.",
            "scope": {
                "scope_id": "ds2-adoption-ledger-stable-components",
                "description": (
                    f"All {adoption['entry_count']} DS2 adoption rows at "
                    f"{adoption['as_of']}."
                ),
            },
            "basis": _health_basis(
                adoption["source_refs"],
                "No stable row exists, so the ratio and any ranking are undefined.",
                "recomputed",
            ),
            "measurement": coverage_measurement,
            "known_facts": {
                "adoption_entry_count": adoption["entry_count"],
                "stable_component_count": stable_count,
                "stable_with_browser_and_at_count": stable_covered,
            },
            "thresholds": [],
        },
        {
            "metric_id": "machine_twin_parity",
            "instrumentation_status": "instrumented",
            "definition": "Share of shipped surfaces with a passing machine-twin parity test.",
            "honest_direction": "100%; twins ship in-slice.",
            "scope": {
                "scope_id": "ds1-live-readiness-rows",
                "description": f"All {readiness_count} DS1 readiness rows at {readiness['as_of']}.",
            },
            "basis": _health_basis(
                readiness["source_refs"],
                "MACHINE audience and implemented state do not establish a "
                "shipped-surface/twin relation or parity receipt.",
                "not_established",
            ),
            "measurement": {
                "kind": "missing",
                "reason_code": "machine_twin_relation_missing",
                "expected_owner_ref": "atlas.surface-machine-twin-relation@not_present",
                "ranking": None,
            },
            "known_facts": {
                "readiness_entry_count": readiness_count,
                "machine_audience_count": readiness["machine_audience_count"],
                "implemented_entry_count": readiness["implemented_entry_count"],
            },
            "thresholds": [],
        },
        {
            "metric_id": "honesty_comprehension",
            "instrumentation_status": "protocol_seam_only",
            "definition": "Reviewer-task success locating the weakest link and active blockers.",
            "honest_direction": "Measured and reported; no benchmark exists yet.",
            "scope": {
                "scope_id": "ds6-honesty-comprehension-seed",
                "description": "C12 seed tasks and the future INT-R3 behavioral battery.",
            },
            "basis": _health_basis(
                [
                    _health_source_ref(
                        "apps/runtime-dashboard/src/test/evidence/atlasHonestyComprehensionProtocol.ts",
                        "c12_instrument_and_int_r3_seam",
                    )
                ],
                "INT-R3 content, observation artifact, and thresholds are not established.",
                "not_established",
            ),
            "measurement": {
                "kind": "missing",
                "reason_code": "honesty_observation_missing",
                "expected_owner_ref": "INT-R3/research-observation@not_established",
                "ranking": None,
            },
            "known_facts": {
                "task_count": 2,
                "metric_count": 6,
                "research_input_status": "not_established",
                "benchmark_status": "not_established",
            },
            "thresholds": thresholds,
        },
    ]


def _require_health_report(
    value: object,
    source_projection: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AtlasEvidencePersistenceError("health-metric producer must emit one JSON object")
    expected_keys = {
        "report_schema",
        "producer",
        "measured_at",
        "measurements",
        "interpretation",
        "authority",
    }
    if set(value) != expected_keys:
        raise AtlasEvidencePersistenceError("health-metric report top-level contract mismatch")
    _require_exact_mapping(
        value.get("report_schema"),
        HEALTH_REPORT_SCHEMA,
        field="health report schema",
    )

    instrument_provenance = _capture_paths_provenance(HEALTH_INSTRUMENT_PATHS)
    roles = (
        "typed_metric_producer",
        "fixed_process_launcher",
        "canonical_source_validator",
    )
    expected_refs = [
        {**file_ref, "role": role}
        for file_ref, role in zip(instrument_provenance["files"], roles, strict=True)
    ]
    expected_producer = {
        "producer_id": "polisyos.atlas.health_metric_instrument",
        "producer_version": "1.0.0",
        "fixed_script": HEALTH_PRODUCER_SCRIPT,
        "repository_revision": instrument_provenance["repository_revision"],
        "repository_dirty": instrument_provenance["dirty"],
        "implementation_refs": expected_refs,
    }
    if value.get("producer") != expected_producer:
        raise AtlasEvidencePersistenceError("health-metric producer provenance mismatch")

    measured_at = value.get("measured_at")
    if not isinstance(measured_at, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", measured_at
    ):
        raise AtlasEvidencePersistenceError("health-metric observation time is invalid")
    try:
        datetime.fromisoformat(measured_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AtlasEvidencePersistenceError("health-metric observation time is invalid") from exc

    expected_rows = _expected_health_rows(source_projection)
    if value.get("measurements") != expected_rows:
        raise AtlasEvidencePersistenceError(
            "health-metric rows do not bind the recomputed canonical-source projection"
        )
    if value.get("interpretation") != {
        "posture": "candidate_only",
        "aggregate_status": None,
        "aggregate_ranking": None,
        "grants_stable": False,
        "blocking_permitted": False,
    }:
        raise AtlasEvidencePersistenceError("health-metric candidate interpretation widened")
    if value.get("authority") != {
        "classification": "candidate_only",
        "authoritative_for": [],
        "may_not_use_for": HEALTH_CANDIDATE_DENIED_USES,
    }:
        raise AtlasEvidencePersistenceError("health-metric candidate authority widened")
    return value


def _trusted_node() -> tuple[Path, Path, str]:
    for locator in TRUSTED_NODE_LOCATORS:
        if not locator.is_file() or not os.access(locator, os.X_OK):
            continue
        resolved = locator.resolve(strict=True)
        result = subprocess.run(  # noqa: S603 - module-owned allowlist and realpath.
            [str(resolved), "--version"],
            cwd=_policy_engine_root(),
            check=False,
            capture_output=True,
            text=True,
            env=HEALTH_CHILD_ENV,
        )
        version = result.stdout.strip()
        if result.returncode == 0 and re.fullmatch(r"v22\.\d+\.\d+", version):
            return locator, resolved, version
    raise AtlasEvidencePersistenceError(
        "fixed health-metric producer requires an allowlisted Node.js 22 executable"
    )


def _run_health_metric_producer(
) -> tuple[bytes, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    dashboard_root = _policy_engine_root() / "apps/runtime-dashboard"
    producer_script = _policy_engine_root() / HEALTH_PRODUCER_SCRIPT
    node_locator, node_executable, node_version = _trusted_node()
    result = subprocess.run(  # noqa: S603 - allowlisted realpath and fixed script.
        [str(node_executable), str(producer_script)],
        cwd=dashboard_root,
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=HEALTH_CHILD_ENV,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise AtlasEvidencePersistenceError(
            f"fixed health-metric producer failed ({result.returncode}): {stderr}"
        )
    raw_report = result.stdout
    if not raw_report:
        raise AtlasEvidencePersistenceError("fixed health-metric producer emitted no report")
    try:
        decoded = json.loads(
            raw_report.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AtlasEvidencePersistenceError(
            "fixed health-metric producer emitted invalid UTF-8 JSON"
        ) from exc
    source_projection, source_validator_observation = _health_source_projection()
    report = _require_health_report(decoded, source_projection)
    observation = {
        "executable": str(node_executable),
        "allowed_locator": str(node_locator),
        "executable_sha256": hashlib.sha256(node_executable.read_bytes()).hexdigest(),
        "executable_version": node_version,
        "script": HEALTH_PRODUCER_SCRIPT,
        "script_sha256": hashlib.sha256(producer_script.read_bytes()).hexdigest(),
        "process_exit_code": result.returncode,
        "stdout_sha256": hashlib.sha256(raw_report).hexdigest(),
        "environment": {
            "mode": "fixed_minimal_allowlist",
            "inherited_names": [],
            "fixed": HEALTH_CHILD_ENV,
            "denied_prefixes": list(HEALTH_DENIED_ENV_PREFIXES),
        },
    }
    return (
        raw_report,
        report,
        observation,
        source_projection,
        source_validator_observation,
    )


def _require_keys(value: Mapping[str, Any], expected: set[str], *, field: str) -> None:
    if set(value) != expected:
        raise AtlasEvidencePersistenceError(
            f"{field} keys must be exactly {sorted(expected)}; got {sorted(value)}"
        )


def _require_lower_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise AtlasEvidencePersistenceError(f"{field} must be lowercase SHA-256")
    return value


def _readiness_source_ref(path: str, role: str) -> dict[str, str]:
    return {
        "path": path,
        "sha256": hashlib.sha256(
            (_policy_engine_root() / path).read_bytes()
        ).hexdigest(),
        "role": role,
    }


def _validated_readiness_source_ref(
    source_projection: Mapping[str, Any],
    path: str,
    role: str,
) -> dict[str, str]:
    readiness = source_projection.get("readiness")
    if not isinstance(readiness, dict) or not isinstance(readiness.get("source_refs"), list):
        raise AtlasEvidencePersistenceError(
            "validated readiness projection has no source references"
        )
    matches = [
        reference
        for reference in readiness["source_refs"]
        if isinstance(reference, dict) and reference.get("path") == path
    ]
    if len(matches) != 1:
        raise AtlasEvidencePersistenceError(
            f"validated readiness projection does not bind exactly one {path}"
        )
    reference = matches[0]
    digest = _require_lower_sha256(
        reference.get("sha256"),
        field=f"validated readiness source {path}",
    )
    if hashlib.sha256((_policy_engine_root() / path).read_bytes()).hexdigest() != digest:
        raise AtlasEvidencePersistenceError(
            f"validated readiness source bytes changed after validation: {path}"
        )
    return {"path": path, "sha256": digest, "role": role}


def _expected_readiness_claims(
    source_projection: Mapping[str, Any],
) -> list[dict[str, str]]:
    ledger_ref = _validated_readiness_source_ref(
        source_projection,
        READINESS_LEDGER_PATH,
        "complete_readiness_owner",
    )
    _validated_readiness_source_ref(
        source_projection,
        READINESS_SCHEMA_PATH,
        "readiness_owner_schema",
    )
    ledger_bytes = (_policy_engine_root() / READINESS_LEDGER_PATH).read_bytes()
    if hashlib.sha256(ledger_bytes).hexdigest() != ledger_ref["sha256"]:
        raise AtlasEvidencePersistenceError(
            "validated readiness owner bytes changed before enumeration"
        )
    ledger = json.loads(
        ledger_bytes.decode("utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_json_constant,
    )
    if not isinstance(ledger, dict) or not isinstance(ledger.get("entries"), list):
        raise AtlasEvidencePersistenceError(
            "validated readiness owner must contain an entries array"
        )
    entries = ledger["entries"]
    readiness_projection = source_projection.get("readiness")
    if (
        not isinstance(readiness_projection, dict)
        or readiness_projection.get("entry_count") != len(entries)
    ):
        raise AtlasEvidencePersistenceError(
            "validated readiness population changed before admission"
        )

    claims: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise AtlasEvidencePersistenceError(
                "validated readiness owner contains a non-object entry"
            )
        surface_id = entry["surface_id"]
        title = entry["title"]
        if entry["maturity"] == "stable":
            claims.append(
                {
                    "claim_id": f"{surface_id}:maturity:stable",
                    "surface_id": surface_id,
                    "title": title,
                    "dimension": "maturity",
                    "declared_value": "stable",
                }
            )
        if entry["readiness_state"] == "implemented":
            claims.append(
                {
                    "claim_id": f"{surface_id}:readiness_state:implemented",
                    "surface_id": surface_id,
                    "title": title,
                    "dimension": "readiness_state",
                    "declared_value": "implemented",
                }
            )
    return claims


def _expected_route_assertion(claim: Mapping[str, str]) -> str | None:
    if claim["dimension"] != "readiness_state":
        return None
    prefix = "route-redirect-"
    surface_id = claim["surface_id"]
    if not surface_id.startswith(prefix):
        return None
    legacy_path = f"/{surface_id.removeprefix(prefix)}"
    if re.fullmatch(r"/[a-z0-9/-]+ to /[a-z0-9/-]+", claim["title"]) is None:
        return None
    if not claim["title"].startswith(f"{legacy_path} to "):
        return None
    return (
        "APP_ROUTES wraps app routes with the shell and follows legacy redirect "
        f"from '{legacy_path}'"
    )


def _expected_route_declaration(
    claim: Mapping[str, str],
) -> tuple[str, str] | None:
    expected_assertion = _expected_route_assertion(claim)
    if expected_assertion is None:
        return None
    match = re.fullmatch(
        r"(?P<source>/[a-z0-9/-]+) to (?P<target>/[a-z0-9/-]+)",
        claim["title"],
    )
    if match is None:
        return None
    return match.group("source"), match.group("target")


def _expected_vitest_runner() -> dict[str, str]:
    dashboard_root = _policy_engine_root() / "apps/runtime-dashboard"
    entry = (dashboard_root / "node_modules/vitest/vitest.mjs").resolve(strict=True)
    package = json.loads(
        (entry.parent / "package.json").read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_json_constant,
    )
    if not isinstance(package, dict) or not isinstance(package.get("version"), str):
        raise AtlasEvidencePersistenceError("resolved Vitest package has no version")
    return {
        "path": str(entry),
        "sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
        "version": package["version"],
    }


def _expected_vite_loader() -> dict[str, str]:
    dashboard_root = _policy_engine_root() / "apps/runtime-dashboard"
    package_root = dashboard_root / "node_modules/vite"
    entry = (package_root / "dist/node/index.js").resolve(strict=True)
    package = json.loads(
        (package_root / "package.json").read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_non_json_constant,
    )
    if not isinstance(package, dict) or not isinstance(package.get("version"), str):
        raise AtlasEvidencePersistenceError("resolved Vite package has no version")
    return {
        "path": str(entry),
        "sha256": hashlib.sha256(entry.read_bytes()).hexdigest(),
        "version": package["version"],
    }


def _require_readiness_source_ref(
    value: object,
    *,
    expected: Mapping[str, str],
    field: str,
) -> None:
    if value != dict(expected):
        raise AtlasEvidencePersistenceError(f"{field} source reference mismatch")


def _require_observed_readiness_basis(
    claim: Mapping[str, Any],
    expected_claim: Mapping[str, str],
    *,
    source_projection: Mapping[str, Any],
    source_validator_observation: Mapping[str, Any],
    node_executable: Path,
    node_version: str,
) -> None:
    basis = claim.get("basis")
    if not isinstance(basis, dict):
        raise AtlasEvidencePersistenceError("readiness claim basis must be an object")
    _require_keys(
        basis,
        {
            "kind",
            "attestation_scope",
            "observation",
            "owner_validation",
            "canonical_check",
            "source_refs",
        },
        field="observed readiness basis",
    )
    if basis["kind"] != "observed_by_reconciler":
        raise AtlasEvidencePersistenceError(
            "closed readiness producer may emit only observed_by_reconciler rows"
        )
    if basis["attestation_scope"] != READINESS_OBSERVED_ATTESTATION_SCOPE:
        raise AtlasEvidencePersistenceError(
            "observed readiness basis attestation scope mismatch"
        )

    observation = basis["observation"]
    if not isinstance(observation, dict):
        raise AtlasEvidencePersistenceError("claim observation must be an object")
    _require_keys(observation, {"status", "reason"}, field="claim observation")
    observation_status = observation["status"]
    if observation_status not in {
        "observed",
        "not_observed",
        "observation_unavailable",
    }:
        raise AtlasEvidencePersistenceError("claim observation status is outside the contract")
    if observation_status == "observed" and observation["reason"] is not None:
        raise AtlasEvidencePersistenceError("positive observation must not carry a reason")
    if observation_status != "observed" and (
        not isinstance(observation["reason"], str) or not observation["reason"]
    ):
        raise AtlasEvidencePersistenceError(
            "negative or unavailable observation must carry a reason"
        )
    expected_provenance = (
        "not_established"
        if observation_status == "observation_unavailable"
        else "recomputed"
    )
    if claim.get("predicate_provenance") != expected_provenance:
        raise AtlasEvidencePersistenceError(
            "claim predicate provenance does not match observation availability"
        )

    owner_validation = basis["owner_validation"]
    if not isinstance(owner_validation, dict):
        raise AtlasEvidencePersistenceError("owner validation must be an object")
    expected_owner_validation = {
        "predicate_provenance": "recomputed",
        "report_sha256": source_validator_observation["stdout_sha256"],
        "validator_ref": _readiness_source_ref(
            HEALTH_SOURCE_VALIDATOR,
            "canonical_owner_validator",
        ),
    }
    if owner_validation != expected_owner_validation:
        raise AtlasEvidencePersistenceError(
            "claim owner validation does not bind the fixed canonical validator"
        )

    canonical_check = basis["canonical_check"]
    if not isinstance(canonical_check, dict):
        raise AtlasEvidencePersistenceError("canonical check must be an object")
    _require_keys(
        canonical_check,
        {
            "check_id",
            "executable",
            "runner",
            "report_sha256",
            "assertion_name",
            "assertion_status",
            "runtime_route",
            "test_ref",
        },
        field="canonical check",
    )
    is_stable = expected_claim["dimension"] == "maturity"
    expected_check_id = (
        "surface-readiness.stable.maturity-prerequisite"
        if is_stable
        else "runtime-dashboard.route-redirect.behavior"
    )
    if canonical_check["check_id"] != expected_check_id:
        raise AtlasEvidencePersistenceError("canonical check identity mismatch")
    expected_executable = {
        "path": str(node_executable),
        "sha256": hashlib.sha256(node_executable.read_bytes()).hexdigest(),
        "version": node_version,
    }
    if canonical_check["executable"] != expected_executable:
        raise AtlasEvidencePersistenceError(
            "canonical check executable provenance mismatch"
        )
    runner = canonical_check["runner"]
    if runner is not None and runner != _expected_vitest_runner():
        raise AtlasEvidencePersistenceError(
            "canonical check Vitest runner provenance mismatch"
        )
    report_sha256 = canonical_check["report_sha256"]
    if report_sha256 is not None:
        _require_lower_sha256(report_sha256, field="canonical check report_sha256")
        if runner is None:
            raise AtlasEvidencePersistenceError(
                "canonical report digest has no bound Vitest runner"
            )
    expected_test_ref = (
        _readiness_source_ref(
            READINESS_RECONCILER_SOURCE,
            "unavailable_stable_observer_declaration",
        )
        if is_stable
        else _readiness_source_ref(
            READINESS_ROUTE_TEST,
            "canonical_behavior_check",
        )
    )
    _require_readiness_source_ref(
        canonical_check["test_ref"],
        expected=expected_test_ref,
        field="canonical check",
    )

    assertion_name = canonical_check["assertion_name"]
    assertion_status = canonical_check["assertion_status"]
    if assertion_status not in {None, "passed", "failed", "skipped"}:
        raise AtlasEvidencePersistenceError("canonical assertion status is outside the contract")
    if assertion_status is not None and (runner is None or report_sha256 is None):
        raise AtlasEvidencePersistenceError(
            "canonical assertion fact has no bound runner and report"
        )
    runtime_route = canonical_check["runtime_route"]
    expected_assertion = _expected_route_assertion(expected_claim)
    expected_declaration = _expected_route_declaration(expected_claim)
    if is_stable:
        if (
            observation_status != "observation_unavailable"
            or observation["reason"] != "canonical_stable_observer_not_registered"
            or runner is not None
            or report_sha256 is not None
            or assertion_name is not None
            or assertion_status is not None
            or runtime_route is not None
        ):
            raise AtlasEvidencePersistenceError(
                "stable claim must fail closed while its canonical observer is absent"
            )
    elif expected_assertion is None:
        if (
            observation_status != "observation_unavailable"
            or observation["reason"] != "canonical_check_not_registered"
            or assertion_name is not None
            or assertion_status is not None
            or runtime_route is not None
        ):
            raise AtlasEvidencePersistenceError(
                "unregistered implemented claim must be observation_unavailable"
            )
    else:
        if expected_declaration is None:
            raise AtlasEvidencePersistenceError("canonical route declaration could not be derived")
        if assertion_name != expected_assertion:
            raise AtlasEvidencePersistenceError(
                "canonical assertion does not bind the gated readiness claim"
            )
        if not isinstance(runtime_route, dict):
            raise AtlasEvidencePersistenceError("canonical runtime route fact must be an object")
        _require_keys(
            runtime_route,
            {
                "status",
                "reason",
                "declared_from",
                "declared_to",
                "observed_to",
                "replace",
            },
            field="canonical runtime route fact",
        )
        source_path, target_path = expected_declaration
        if (
            runtime_route["declared_from"] != source_path
            or runtime_route["declared_to"] != target_path
        ):
            raise AtlasEvidencePersistenceError(
                "canonical runtime route fact does not bind both declared endpoints"
            )
        runtime_status = runtime_route["status"]
        if runtime_status not in {"matched", "mismatched", "unavailable"}:
            raise AtlasEvidencePersistenceError(
                "canonical runtime route status is outside the contract"
            )
        if runtime_status == "matched" and runtime_route != {
            "status": "matched",
            "reason": None,
            "declared_from": source_path,
            "declared_to": target_path,
            "observed_to": target_path,
            "replace": True,
        }:
            raise AtlasEvidencePersistenceError(
                "matched runtime route does not bind target and replace semantics"
            )
        if runtime_status != "matched" and (
            not isinstance(runtime_route["reason"], str) or not runtime_route["reason"]
        ):
            raise AtlasEvidencePersistenceError("non-matching runtime route must carry a reason")
        if runtime_status == "unavailable" and (
            runtime_route["observed_to"] is not None or runtime_route["replace"] is not None
        ):
            raise AtlasEvidencePersistenceError(
                "unavailable runtime route cannot invent observed facts"
            )
        if runtime_status == "mismatched" and (
            (
                runtime_route["observed_to"] is not None
                and not isinstance(runtime_route["observed_to"], str)
            )
            or (
                runtime_route["replace"] is not None
                and not isinstance(runtime_route["replace"], bool)
            )
        ):
            raise AtlasEvidencePersistenceError(
                "mismatched runtime route carries malformed observed facts"
            )

        if observation_status != "observation_unavailable" and (
            runner is None or report_sha256 is None
        ):
            raise AtlasEvidencePersistenceError(
                "completed observation must bind runner and report digest"
            )
        if observation_status == "observed" and not (
            assertion_status == "passed" and runtime_status == "matched"
        ):
            raise AtlasEvidencePersistenceError("observed claim lacks positive canonical facts")
        if observation_status == "not_observed" and not (
            assertion_status == "failed" or runtime_status == "mismatched"
        ):
            raise AtlasEvidencePersistenceError(
                "negative observation lacks a completed negative fact"
            )
        if observation_status == "observation_unavailable" and assertion_status in {
            "passed",
            "failed",
        }:
            raise AtlasEvidencePersistenceError(
                "unavailable observation cannot coexist with a completed assertion"
            )

        observation_reason = observation["reason"]
        if observation_status == "not_observed":
            expected_reason = (
                runtime_route["reason"]
                if runtime_status == "mismatched"
                else "canonical_assertion_failed"
            )
            if observation_reason != expected_reason:
                raise AtlasEvidencePersistenceError(
                    "negative observation reason does not match its canonical fact"
                )
        elif observation_status == "observation_unavailable":
            if runtime_status == "unavailable":
                if observation_reason != runtime_route["reason"]:
                    raise AtlasEvidencePersistenceError(
                        "unavailable observation reason does not match runtime fact"
                    )
            else:
                allowed_unavailable_reasons = {
                    "canonical_assertion_ambiguous",
                    "canonical_assertion_missing",
                    "canonical_assertion_skipped",
                    "canonical_route_harness_failed",
                    "canonical_route_report_invalid",
                    "canonical_route_report_missing",
                    "canonical_route_runner_changed",
                    "canonical_route_sources_changed",
                }
                if observation_reason not in allowed_unavailable_reasons:
                    raise AtlasEvidencePersistenceError(
                        "unavailable observation reason is not produced by the fixed route run"
                    )
                if (observation_reason == "canonical_assertion_skipped") != (
                    assertion_status == "skipped"
                ):
                    raise AtlasEvidencePersistenceError(
                        "skipped assertion and unavailable reason disagree"
                    )
                if observation_reason in {
                    "canonical_assertion_ambiguous",
                    "canonical_assertion_missing",
                    "canonical_route_report_invalid",
                } and (runner is None or report_sha256 is None):
                    raise AtlasEvidencePersistenceError(
                        "report-derived unavailability has no bound runner and report"
                    )
                if observation_reason in {
                    "canonical_route_report_missing",
                    "canonical_route_runner_changed",
                    "canonical_route_sources_changed",
                } and (runner is None or report_sha256 is not None):
                    raise AtlasEvidencePersistenceError(
                        "pre-report unavailability contradicts runner/report provenance"
                    )

    expected_source_refs = [
        _validated_readiness_source_ref(
            source_projection,
            READINESS_LEDGER_PATH,
            "complete_readiness_owner",
        ),
        _validated_readiness_source_ref(
            source_projection,
            READINESS_SCHEMA_PATH,
            "readiness_owner_schema",
        ),
    ]
    if is_stable:
        expected_source_refs.extend(
            [
                expected_test_ref,
                _readiness_source_ref(
                    READINESS_PRODUCER_SCRIPT,
                    "closed_reconciler_launcher",
                ),
            ]
        )
    else:
        expected_source_refs.extend(
            [
                _readiness_source_ref(
                    READINESS_ROUTE_SOURCE,
                    "runtime_route_owner",
                ),
                expected_test_ref,
                _readiness_source_ref(
                    READINESS_RECONCILER_SOURCE,
                    "closed_claim_reconciler",
                ),
                _readiness_source_ref(
                    READINESS_PRODUCER_SCRIPT,
                    "closed_reconciler_launcher",
                ),
            ]
        )
    if basis["source_refs"] != expected_source_refs:
        raise AtlasEvidencePersistenceError(
            "claim basis does not bind the complete canonical source set"
        )


def _require_readiness_report(
    value: object,
    source_projection: Mapping[str, Any],
    source_validator_observation: Mapping[str, Any],
    *,
    node_executable: Path,
    node_version: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AtlasEvidencePersistenceError(
            "fixed readiness reconciler must emit one JSON object"
        )
    _require_keys(value, {"report_schema", "producer", "claims"}, field="claim report")
    if value["report_schema"] != READINESS_REPORT_SCHEMA:
        raise AtlasEvidencePersistenceError("claim report schema mismatch")

    producer = value["producer"]
    if not isinstance(producer, dict):
        raise AtlasEvidencePersistenceError("claim report producer must be an object")
    expected_producer = {
        "producer_id": "polisyos.atlas.surface_readiness_reconciler",
        "producer_version": "2.0.0",
        "implementation_ref": _readiness_source_ref(
            READINESS_RECONCILER_SOURCE,
            "closed_claim_reconciler",
        ),
        "vite_loader": _expected_vite_loader(),
    }
    if producer != expected_producer:
        raise AtlasEvidencePersistenceError("claim report producer provenance mismatch")

    claims = value["claims"]
    if not isinstance(claims, list):
        raise AtlasEvidencePersistenceError("claim report claims must be an array")
    expected_claims = _expected_readiness_claims(source_projection)
    if len(claims) != len(expected_claims):
        raise AtlasEvidencePersistenceError(
            "claim report does not enumerate the complete gated owner set"
        )
    seen: set[str] = set()
    for index, (claim, expected_claim) in enumerate(
        zip(claims, expected_claims, strict=True)
    ):
        if not isinstance(claim, dict):
            raise AtlasEvidencePersistenceError(f"readiness claim {index} is not an object")
        _require_keys(
            claim,
            {
                "claim_id",
                "surface_id",
                "title",
                "dimension",
                "declared_value",
                "predicate_provenance",
                "basis",
            },
            field=f"readiness claim {index}",
        )
        for field, expected_value in expected_claim.items():
            if claim[field] != expected_value:
                raise AtlasEvidencePersistenceError(
                    f"readiness claim {index} does not bind owner field {field}"
                )
        claim_id = claim["claim_id"]
        if claim_id in seen:
            raise AtlasEvidencePersistenceError(f"duplicate readiness claim: {claim_id}")
        seen.add(claim_id)
        _require_observed_readiness_basis(
            claim,
            expected_claim,
            source_projection=source_projection,
            source_validator_observation=source_validator_observation,
            node_executable=node_executable,
            node_version=node_version,
        )
    return value


def _run_readiness_reconciler(
) -> tuple[
    bytes,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    dashboard_root = _policy_engine_root() / "apps/runtime-dashboard"
    producer_script = _policy_engine_root() / READINESS_PRODUCER_SCRIPT
    node_locator, node_executable, node_version = _trusted_node()
    node_sha256 = hashlib.sha256(node_executable.read_bytes()).hexdigest()
    vite_loader = _expected_vite_loader()
    source_projection, source_validator_observation = _health_source_projection()
    result = subprocess.run(  # noqa: S603 - allowlisted realpath and fixed script.
        [str(node_executable), str(producer_script)],
        cwd=dashboard_root,
        check=False,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        env=HEALTH_CHILD_ENV,
    )
    if hashlib.sha256(node_executable.read_bytes()).hexdigest() != node_sha256:
        raise AtlasEvidencePersistenceError(
            "allowlisted Node executable changed during readiness reconciliation"
        )
    if _expected_vite_loader() != vite_loader:
        raise AtlasEvidencePersistenceError(
            "Vite module loader changed during readiness reconciliation"
        )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise AtlasEvidencePersistenceError(
            f"fixed surface-readiness reconciler failed ({result.returncode}): {stderr}"
        )
    raw_report = result.stdout
    if not raw_report:
        raise AtlasEvidencePersistenceError(
            "fixed surface-readiness reconciler emitted no claim report"
        )
    try:
        decoded = json.loads(
            raw_report.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AtlasEvidencePersistenceError(
            "fixed surface-readiness reconciler emitted invalid UTF-8 JSON"
        ) from exc
    report = _require_readiness_report(
        decoded,
        source_projection,
        source_validator_observation,
        node_executable=node_executable,
        node_version=node_version,
    )
    observation = {
        "executable": str(node_executable),
        "allowed_locator": str(node_locator),
        "executable_sha256": node_sha256,
        "executable_version": node_version,
        "script": READINESS_PRODUCER_SCRIPT,
        "script_sha256": hashlib.sha256(producer_script.read_bytes()).hexdigest(),
        "stdout_sha256": hashlib.sha256(raw_report).hexdigest(),
        "environment": {
            "mode": "fixed_minimal_allowlist",
            "inherited_names": [],
            "fixed": HEALTH_CHILD_ENV,
            "denied_prefixes": list(HEALTH_DENIED_ENV_PREFIXES),
        },
    }
    return (
        raw_report,
        report,
        observation,
        source_projection,
        source_validator_observation,
    )


def _revision_byte_status(revision: str, paths: set[str]) -> dict[str, Any]:
    """Compare product-relative current bytes with their recorded Git revision."""

    product_root = _policy_engine_root()
    worktree_prefix = _run_git("rev-parse", "--show-prefix").strip()
    revision_prefix = f"{worktree_prefix.rstrip('/')}/" if worktree_prefix else ""
    non_revision_paths: list[str] = []
    for relative_path in sorted(paths):
        current_path = product_root / relative_path
        if not current_path.is_file():
            non_revision_paths.append(relative_path)
            continue
        result = subprocess.run(  # noqa: S603 - fixed git and content-bound path set.
            ["/usr/bin/git", "show", f"{revision}:{revision_prefix}{relative_path}"],
            cwd=product_root,
            check=False,
            capture_output=True,
            env=HEALTH_CHILD_ENV,
        )
        if result.returncode != 0 or result.stdout != current_path.read_bytes():
            non_revision_paths.append(relative_path)
    return {
        "status": (
            "revision_resolvable" if not non_revision_paths else "source_hash_bound_only"
        ),
        "checked_path_count": len(paths),
        "non_revision_paths": non_revision_paths,
    }


def _health_replay_status(
    revision: str,
    report: Mapping[str, Any],
) -> dict[str, Any]:
    paths = set(HEALTH_IMPLEMENTATION_PATHS)
    for row in report["measurements"]:
        for source_ref in row["basis"]["source_refs"]:
            paths.add(source_ref["path"])
    return _revision_byte_status(revision, paths)


def persist_atlas_health_metrics() -> dict[str, Any]:
    """Run the fixed C11 producer and persist its raw report and bound snapshot.

    The operation accepts no report, root, script, exit-code, or basis input. The
    adapter observes its own child process and stores both artifacts through the
    existing Core ArtifactStore convention.
    """
    (
        raw_report,
        report,
        observation,
        source_projection,
        source_validator_observation,
    ) = _run_health_metric_producer()
    instrument_provenance = _capture_paths_provenance(HEALTH_INSTRUMENT_PATHS)
    implementation_provenance = _capture_health_implementation_provenance()
    _ensure_worktree_import_root()

    from polisyos.core.artifacts import InputRef, PutOptions, SchemaInfo

    store = _build_store()
    instrument_producer = _producer(
        instrument_provenance,
        component=HEALTH_INSTRUMENT_COMPONENT,
    )
    admission_producer = _producer(
        implementation_provenance,
        component=HEALTH_ADMISSION_COMPONENT,
    )
    report_digest = hashlib.sha256(raw_report).hexdigest()
    report_ref = store.put_bytes(
        raw_report,
        PutOptions(
            kind=HEALTH_REPORT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=HEALTH_REPORT_SCHEMA["id"],
                version=HEALTH_REPORT_SCHEMA["version"],
            ),
            producer=instrument_producer,
            inputs=[],
            governance=_governance(),
        ),
    )
    report_verification = store.verify(report_ref.artifact_id)
    _assert_verification(report_verification, label="health-metric report")
    report_manifest = store.get_manifest(report_ref.artifact_id)
    _assert_manifest(
        report_manifest,
        kind=HEALTH_REPORT_KIND,
        schema_name=HEALTH_REPORT_SCHEMA["id"],
        schema_version=HEALTH_REPORT_SCHEMA["version"],
        expected_inputs=[],
        expected_producer=instrument_producer,
        expect_canon=False,
    )
    resolved_report_bytes = store.get_bytes(report_ref.artifact_id)
    if resolved_report_bytes != raw_report:
        raise AtlasEvidencePersistenceError("resolved health report differs from producer stdout")
    resolved_report = _require_health_report(
        json.loads(
            resolved_report_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        ),
        source_projection,
    )
    if resolved_report != report:
        raise AtlasEvidencePersistenceError("resolved health report changed after admission")

    source_projection_sha256 = hashlib.sha256(
        json.dumps(
            source_projection,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    replay = _health_replay_status(
        resolved_report["producer"]["repository_revision"],
        resolved_report,
    )

    stored_snapshot = {
        "snapshot_schema": HEALTH_SNAPSHOT_SCHEMA,
        "report_ref": {
            "artifact_id": str(report_ref.artifact_id),
            "kind": HEALTH_REPORT_KIND,
            "media_type": "application/json",
            "schema_id": HEALTH_REPORT_SCHEMA["id"],
            "schema_version": HEALTH_REPORT_SCHEMA["version"],
        },
        "report_sha256": report_digest,
        "measured_at": resolved_report["measured_at"],
        "repository_revision": resolved_report["producer"]["repository_revision"],
        "producer_observation": observation,
        "persistence_implementation": implementation_provenance,
        "measurements": resolved_report["measurements"],
        "admission": {
            "verifier_id": "polisyos.atlas.health_metric_admission",
            "verifier_version": "1.0.0",
            "predicate_provenance": "recomputed",
            "source_projection_sha256": source_projection_sha256,
            "source_validator": source_projection["producer"],
            "source_validator_observation": source_validator_observation,
            "verifier_ref": _health_source_ref(
                "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
                "single_limited_descriptive_admission",
            ),
        },
        "replay": replay,
        "authority": {
            "classification": "limited_descriptive_admission",
            "authoritative_for": ["descriptive_atlas_health_measurement"],
            "may_not_use_for": DENIED_USES,
        },
        "interpretation": {
            "posture": "limited_descriptive_admission",
            "aggregate_status": None,
            "aggregate_ranking": None,
            "grants_stable": False,
            "blocking_permitted": False,
        },
        "capability": {
            "label": "implemented_but_not_orchestrated",
            "missing": ["consumer_missing", "surface_missing"],
        },
    }
    snapshot_ref = store.put_json(
        stored_snapshot,
        PutOptions(
            kind=HEALTH_SNAPSHOT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=HEALTH_SNAPSHOT_SCHEMA["id"],
                version=HEALTH_SNAPSHOT_SCHEMA["version"],
            ),
            producer=admission_producer,
            inputs=[
                InputRef(
                    artifact_id=report_ref.artifact_id,
                    role=HEALTH_REPORT_INPUT_ROLE,
                )
            ],
            governance=_governance(),
        ),
        canon_spec=_canon_spec(),
    )
    snapshot_verification = store.verify(snapshot_ref.artifact_id)
    _assert_verification(snapshot_verification, label="health-metric snapshot")
    expected_lineage = [(str(report_ref.artifact_id), HEALTH_REPORT_INPUT_ROLE)]
    snapshot_manifest = store.get_manifest(snapshot_ref.artifact_id)
    _assert_manifest(
        snapshot_manifest,
        kind=HEALTH_SNAPSHOT_KIND,
        schema_name=HEALTH_SNAPSHOT_SCHEMA["id"],
        schema_version=HEALTH_SNAPSHOT_SCHEMA["version"],
        expected_inputs=expected_lineage,
        expected_producer=admission_producer,
    )
    resolved_snapshot = _resolve_json(
        store,
        snapshot_ref.artifact_id,
        label="health-metric snapshot",
    )
    if resolved_snapshot != stored_snapshot:
        raise AtlasEvidencePersistenceError("resolved health snapshot differs from stored input")

    return {
        "ok": True,
        "operation": HEALTH_OPERATION,
        "report_ref": report_ref.model_dump(mode="json"),
        "snapshot_ref": snapshot_ref.model_dump(mode="json"),
        "report_verification": report_verification.model_dump(mode="json"),
        "snapshot_verification": snapshot_verification.model_dump(mode="json"),
        "report_manifest_input": None,
        "snapshot_manifest_input": {
            "artifact_id": expected_lineage[0][0],
            "role": expected_lineage[0][1],
        },
        "resolved_report": {
            "artifact_id": str(report_ref.artifact_id),
            "report": resolved_report,
        },
        "resolved_snapshot": {
            "artifact_id": str(snapshot_ref.artifact_id),
            "snapshot": resolved_snapshot,
        },
    }


def persist_atlas_surface_readiness_claims() -> dict[str, Any]:
    """Run the closed per-claim reconciler and persist its audit projection.

    The caller selects only this operation. Report bytes, process status, basis,
    roots, and executables are all fixed and observed inside this operation.
    No aggregate readiness result is constructed or persisted.
    """

    (
        raw_report,
        report,
        producer_observation,
        source_projection,
        source_validator_observation,
    ) = _run_readiness_reconciler()
    implementation_provenance = _capture_paths_provenance(
        READINESS_IMPLEMENTATION_PATHS
    )
    _ensure_worktree_import_root()

    from polisyos.core.artifacts import InputRef, PutOptions, SchemaInfo

    store = _build_store()
    report_producer = _producer(
        implementation_provenance,
        component=READINESS_RECONCILER_COMPONENT,
    )
    projection_producer = _producer(
        implementation_provenance,
        component=READINESS_ADMISSION_COMPONENT,
    )
    report_digest = hashlib.sha256(raw_report).hexdigest()
    report_ref = store.put_bytes(
        raw_report,
        PutOptions(
            kind=READINESS_REPORT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=READINESS_REPORT_SCHEMA["id"],
                version=READINESS_REPORT_SCHEMA["version"],
            ),
            producer=report_producer,
            inputs=[],
            governance=_governance(),
        ),
    )
    report_verification = store.verify(report_ref.artifact_id)
    _assert_verification(report_verification, label="surface-readiness claim report")
    report_manifest = store.get_manifest(report_ref.artifact_id)
    _assert_manifest(
        report_manifest,
        kind=READINESS_REPORT_KIND,
        schema_name=READINESS_REPORT_SCHEMA["id"],
        schema_version=READINESS_REPORT_SCHEMA["version"],
        expected_inputs=[],
        expected_producer=report_producer,
        expect_canon=False,
    )
    resolved_report_bytes = store.get_bytes(report_ref.artifact_id)
    if resolved_report_bytes != raw_report:
        raise AtlasEvidencePersistenceError(
            "resolved readiness claim report differs from reconciler stdout"
        )
    resolved_report = _require_readiness_report(
        json.loads(
            resolved_report_bytes.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_json_constant,
        ),
        source_projection,
        source_validator_observation,
        node_executable=Path(producer_observation["executable"]),
        node_version=producer_observation["executable_version"],
    )
    if resolved_report != report:
        raise AtlasEvidencePersistenceError(
            "resolved readiness claim report changed after admission"
        )

    stored_projection = {
        "projection_schema": READINESS_PROJECTION_SCHEMA,
        "claim_report_ref": {
            "artifact_id": str(report_ref.artifact_id),
            "kind": READINESS_REPORT_KIND,
            "media_type": "application/json",
            "schema_id": READINESS_REPORT_SCHEMA["id"],
            "schema_version": READINESS_REPORT_SCHEMA["version"],
        },
        "claim_report_sha256": report_digest,
        "claims": resolved_report["claims"],
        "verifier": {
            "verifier_id": "polisyos.atlas.surface_readiness_admission",
            "verifier_version": "2.0.0",
            "predicate_provenance": "recomputed",
            "implementation_ref": _readiness_source_ref(
                "apps/runtime-dashboard/scripts/persist_atlas_evidence.py",
                "closed_claim_admission",
            ),
        },
        "authority": {
            "classification": "governed_audit_projection",
            "authoritative_for": ["surface_readiness_claim_basis_audit"],
            "may_not_use_for": [
                "aggregate_reconciliation",
                "component_maturity",
                "design_authority",
                "policy_authority",
                "promotion",
                "publication",
                "runtime_authority",
                "stable",
            ],
        },
    }
    projection_ref = store.put_json(
        stored_projection,
        PutOptions(
            kind=READINESS_PROJECTION_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=READINESS_PROJECTION_SCHEMA["id"],
                version=READINESS_PROJECTION_SCHEMA["version"],
            ),
            producer=projection_producer,
            inputs=[
                InputRef(
                    artifact_id=report_ref.artifact_id,
                    role=READINESS_REPORT_INPUT_ROLE,
                )
            ],
            governance=_governance(),
        ),
        canon_spec=_canon_spec(),
    )
    projection_verification = store.verify(projection_ref.artifact_id)
    _assert_verification(
        projection_verification,
        label="surface-readiness claim projection",
    )
    expected_lineage = [
        (str(report_ref.artifact_id), READINESS_REPORT_INPUT_ROLE)
    ]
    projection_manifest = store.get_manifest(projection_ref.artifact_id)
    _assert_manifest(
        projection_manifest,
        kind=READINESS_PROJECTION_KIND,
        schema_name=READINESS_PROJECTION_SCHEMA["id"],
        schema_version=READINESS_PROJECTION_SCHEMA["version"],
        expected_inputs=expected_lineage,
        expected_producer=projection_producer,
    )
    resolved_projection = _resolve_json(
        store,
        projection_ref.artifact_id,
        label="surface-readiness claim projection",
    )
    if resolved_projection != stored_projection:
        raise AtlasEvidencePersistenceError(
            "resolved readiness claim projection differs from stored input"
        )

    return {
        "operation": READINESS_OPERATION,
        "claim_report_ref": report_ref.model_dump(mode="json"),
        "projection_ref": projection_ref.model_dump(mode="json"),
        "claim_report_manifest_input": None,
        "projection_manifest_input": {
            "artifact_id": expected_lineage[0][0],
            "role": expected_lineage[0][1],
        },
        "resolved_claim_report": {
            "artifact_id": str(report_ref.artifact_id),
            "report": resolved_report,
        },
        "resolved_projection": {
            "artifact_id": str(projection_ref.artifact_id),
            "projection": resolved_projection,
        },
    }


def _emit(value: object) -> None:
    sys.stdout.write(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    )


def _fail(exc: Exception, *, operation: str) -> NoReturn:
    error = {
        "operation": operation,
        "error": {
            "code": "atlas_evidence_persistence_failed",
            "type": type(exc).__name__,
            "message": str(exc),
        },
    }
    if operation != READINESS_OPERATION:
        error["ok"] = False
    _emit(error)
    raise SystemExit(1)


def main() -> None:
    """Read one strict JSON request and emit one strict JSON result."""
    operation = OPERATION
    try:
        request = _read_request()
        requested_operation = request.get("operation")
        if requested_operation in {HEALTH_OPERATION, READINESS_OPERATION}:
            operation = requested_operation
        _validate_request(request)
        if operation == HEALTH_OPERATION:
            result = persist_atlas_health_metrics()
        elif operation == READINESS_OPERATION:
            result = persist_atlas_surface_readiness_claims()
        else:
            raw_report = _decode_raw_report(request["raw_report_base64"])
            result = persist_atlas_evidence(raw_report, request["payload"], request["receipt"])
    except Exception as exc:  # The process boundary must always return structured JSON.
        _fail(exc, operation=operation)
    _emit(result)


if __name__ == "__main__":
    main()
