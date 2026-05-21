"""Tenant ownership index for shared immutable CAS artifacts."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.core.canon.canon_json import CanonSpec, to_canonical_bytes

from ._atomic_write import AtomicFileWriter
from .ids import ArtifactID

OWNERSHIP_INDEX_SCHEMA_VERSION = "policyos.artifact_ownership_index.v1"
OWNERSHIP_SIGNATURE_SCHEMA_VERSION = "policyos.artifact_ownership_index_signature.v1"
OWNERSHIP_MODE_SHARED_CAS = "shared_immutable_cas"


class ArtifactOwnershipError(PermissionError):
    """Raised when a tenant attempts to access an artifact it does not own."""


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _normal_tenant_id(value: str | None) -> str:
    tenant_id = str(value or "").strip()
    if not tenant_id:
        raise ArtifactOwnershipError("Tenant-scoped artifact access requires a tenant_id")
    return tenant_id


def _normal_cell_id(value: str | None) -> str | None:
    cell_id = str(value or "").strip()
    return cell_id or None


def _record_matches_owner(
    record: dict[str, Any],
    *,
    tenant_id: str,
    cell_id: str | None,
) -> bool:
    if record.get("tenant_id") != tenant_id:
        return False
    recorded_cell = _normal_cell_id(record.get("cell_id"))
    return recorded_cell == cell_id


class ArtifactOwnershipIndex:
    """Persist tenant ownership claims next to a shared immutable filesystem CAS.

    The index is intentionally separate from blob/manifests so artifact IDs stay
    canonical content hashes across tenants. A write claims ownership for the
    current tenant; reads require a matching claim when the CAS is tenant-scoped.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.directory = self.root / "artifacts" / "ownership"
        self.path = self.directory / "index.json"
        self.signature_path = self.directory / "index.signature.json"
        self._lock = threading.Lock()

    def record_owner(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
        writer: str | None = None,
    ) -> None:
        """Upsert one tenant ownership claim for an immutable CAS artifact."""
        aid = _coerce_artifact_id(artifact_id)
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        with self._lock:
            payload = self._load_payload()
            artifacts = _artifacts_mapping(payload)
            records = list(artifacts.get(str(aid), []))
            if any(
                _record_matches_owner(
                    record,
                    tenant_id=normalized_tenant,
                    cell_id=normalized_cell,
                )
                for record in records
            ):
                if not self.signature_path.exists():
                    self._write_payload(payload)
                return
            record: dict[str, Any] = {
                "tenant_id": normalized_tenant,
                "claimed_at": _utc_now(),
            }
            if normalized_cell is not None:
                record["cell_id"] = normalized_cell
            if writer:
                record["writer"] = str(writer)
            records.append(record)
            artifacts[str(aid)] = sorted(
                records,
                key=lambda item: (
                    str(item.get("tenant_id") or ""),
                    str(item.get("cell_id") or ""),
                    str(item.get("claimed_at") or ""),
                ),
            )
            payload["artifacts"] = dict(sorted(artifacts.items()))
            self._write_payload(payload)

    def owners_for(self, artifact_id: ArtifactID | str) -> list[dict[str, Any]]:
        """Return ownership records for one artifact, newest index view first."""
        aid = _coerce_artifact_id(artifact_id)
        payload = self._load_payload()
        records = _artifacts_mapping(payload).get(str(aid), [])
        return [dict(record) for record in records]

    def is_owned_by(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
    ) -> bool:
        """Return whether the artifact has a matching tenant ownership claim."""
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        return any(
            _record_matches_owner(
                record,
                tenant_id=normalized_tenant,
                cell_id=normalized_cell,
            )
            for record in self.owners_for(artifact_id)
        )

    def require_owner(
        self,
        artifact_id: ArtifactID | str,
        *,
        tenant_id: str,
        cell_id: str | None = None,
        operation: str = "read",
    ) -> None:
        """Fail closed unless the tenant owns the artifact."""
        aid = _coerce_artifact_id(artifact_id)
        normalized_tenant = _normal_tenant_id(tenant_id)
        normalized_cell = _normal_cell_id(cell_id)
        if self.is_owned_by(aid, tenant_id=normalized_tenant, cell_id=normalized_cell):
            return
        owners = self.owners_for(aid)
        owner_labels = [
            _owner_label(record.get("tenant_id"), record.get("cell_id")) for record in owners
        ]
        owner_text = ", ".join(owner_labels) if owner_labels else "unowned"
        raise ArtifactOwnershipError(
            f"Artifact {aid} is not owned by tenant "
            f"{_owner_label(normalized_tenant, normalized_cell)} for {operation}; "
            f"current owners: {owner_text}"
        )

    def evidence(self, *, tenant_id: str | None = None, cell_id: str | None = None) -> dict[str, Any]:
        """Return evidence metadata suitable for canary/debug bundles."""
        with self._lock:
            payload = self._load_payload()
            if not self.path.exists():
                self._write_payload(payload)
            artifacts = _artifacts_mapping(payload)
            digest = _digest_payload(payload)
            signature = self._signature_payload(payload, digest=digest)
            if not self.signature_path.exists() or _load_json_file(self.signature_path) != signature:
                AtomicFileWriter.write_atomic(
                    self.signature_path,
                    _json_bytes(signature),
                )
        evidence: dict[str, Any] = {
            "mode": OWNERSHIP_MODE_SHARED_CAS,
            "schema_version": OWNERSHIP_INDEX_SCHEMA_VERSION,
            "ownership_index_path": str(self.path),
            "ownership_index_digest": digest,
            "ownership_index_signature_path": str(self.signature_path),
            "ownership_index_signature_digest": _digest_payload(signature),
            "artifact_count": len(artifacts),
        }
        if tenant_id:
            normalized_tenant = _normal_tenant_id(tenant_id)
            normalized_cell = _normal_cell_id(cell_id)
            evidence["tenant_id"] = normalized_tenant
            if normalized_cell is not None:
                evidence["cell_id"] = normalized_cell
            evidence["tenant_artifact_count"] = sum(
                1
                for records in artifacts.values()
                if any(
                    _record_matches_owner(
                        record,
                        tenant_id=normalized_tenant,
                        cell_id=normalized_cell,
                    )
                    for record in records
                )
            )
        return evidence

    def _load_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {
                "schema_version": OWNERSHIP_INDEX_SCHEMA_VERSION,
                "mode": OWNERSHIP_MODE_SHARED_CAS,
                "artifacts": {},
            }
        raw = _load_json_file(self.path)
        if not isinstance(raw, dict):
            return {
                "schema_version": OWNERSHIP_INDEX_SCHEMA_VERSION,
                "mode": OWNERSHIP_MODE_SHARED_CAS,
                "artifacts": {},
            }
        raw.setdefault("schema_version", OWNERSHIP_INDEX_SCHEMA_VERSION)
        raw.setdefault("mode", OWNERSHIP_MODE_SHARED_CAS)
        raw.setdefault("artifacts", {})
        return raw

    def _write_payload(self, payload: dict[str, Any]) -> None:
        payload["schema_version"] = OWNERSHIP_INDEX_SCHEMA_VERSION
        payload["mode"] = OWNERSHIP_MODE_SHARED_CAS
        AtomicFileWriter.write_atomic(self.path, _json_bytes(payload))
        digest = _digest_payload(payload)
        AtomicFileWriter.write_atomic(
            self.signature_path,
            _json_bytes(self._signature_payload(payload, digest=digest)),
        )

    def _signature_payload(self, payload: dict[str, Any], *, digest: str) -> dict[str, Any]:
        signed_statement = {
            "schema_version": OWNERSHIP_SIGNATURE_SCHEMA_VERSION,
            "mode": OWNERSHIP_MODE_SHARED_CAS,
            "index_sha256": digest,
            "index_schema_version": str(
                payload.get("schema_version") or OWNERSHIP_INDEX_SCHEMA_VERSION
            ),
            "algorithm": "sha256-local-integrity",
            "key_id": "local-cas-ownership-index",
        }
        signature = _digest_payload(signed_statement)
        return {**signed_statement, "signature": signature}


def _coerce_artifact_id(value: ArtifactID | str) -> ArtifactID:
    if isinstance(value, ArtifactID):
        return value
    return ArtifactID.model_validate(value)


def _artifacts_mapping(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    raw = payload.get("artifacts")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for key, value in raw.items():
        try:
            artifact_id = str(_coerce_artifact_id(str(key)))
        except (TypeError, ValueError):
            continue
        if not isinstance(value, list):
            continue
        records = [dict(item) for item in value if isinstance(item, dict)]
        result[artifact_id] = records
    return result


def _owner_label(tenant_id: object, cell_id: object | None = None) -> str:
    tenant = str(tenant_id or "").strip() or "<missing>"
    cell = _normal_cell_id(str(cell_id)) if cell_id is not None else None
    return f"{tenant}/{cell}" if cell else tenant


def _digest_payload(payload: Any) -> str:
    data = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _load_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None


__all__ = [
    "ArtifactOwnershipError",
    "ArtifactOwnershipIndex",
    "OWNERSHIP_INDEX_SCHEMA_VERSION",
    "OWNERSHIP_MODE_SHARED_CAS",
    "OWNERSHIP_SIGNATURE_SCHEMA_VERSION",
]
