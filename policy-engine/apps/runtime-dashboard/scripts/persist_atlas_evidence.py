"""Persist one Atlas verification payload and its content-bound receipt in Core CAS."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import subprocess
import sys
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
DENIED_USES = [
    "component_maturity",
    "design_authority",
    "policy_authority",
    "promotion",
    "publication",
    "runtime_authority",
    "stable",
]
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
    return request


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


def _capture_implementation_provenance() -> dict[str, Any]:
    files: list[dict[str, str]] = []
    aggregate = hashlib.sha256()
    for relative_path in IMPLEMENTATION_PATHS:
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


def _producer(implementation_provenance: Mapping[str, object]) -> ProducerInfo:
    from polisyos.core.artifacts import GitInfo, ProducerInfo

    return ProducerInfo(
        component=PRODUCER_COMPONENT,
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


def _fail(exc: Exception) -> NoReturn:
    _emit(
        {
            "ok": False,
            "operation": OPERATION,
            "error": {
                "code": "atlas_evidence_persistence_failed",
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
    )
    raise SystemExit(1)


def main() -> None:
    """Read one strict JSON request and emit one strict JSON result."""
    try:
        request = _read_request()
        raw_report = _decode_raw_report(request["raw_report_base64"])
        result = persist_atlas_evidence(raw_report, request["payload"], request["receipt"])
    except Exception as exc:  # The process boundary must always return structured JSON.
        _fail(exc)
    _emit(result)


if __name__ == "__main__":
    main()
