"""Build CAS integrity proof records from verified artifact store reads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ._integrity_ops import ArtifactIntegrityError
from .ids import ArtifactID
from .manifest import ArtifactManifest


class CASIntegrityReport(BaseModel):
    """GY-F2 proof record for one CAS artifact's integrity and authority state."""

    model_config = ConfigDict(extra="forbid")

    artifact_ref: str
    payload_digest: str
    canonicalization_rule_ref: str
    blob_uri: str
    manifest_ref: str
    authority_manifest_ref: str | None
    duplicate_group_id: str
    referrers: list[str] = Field(default_factory=list)
    report_index_refs: list[str] = Field(default_factory=list)
    lineage_refs: list[str] = Field(default_factory=list)
    tamper_probe_result: str
    mutation_probe_result: str
    gc_retain_reason: str
    gc_dry_run_result: str


def build_cas_integrity_report(
    store: Any,
    artifact_id: ArtifactID | str,
    *,
    referrers: list[str] | tuple[str, ...] = (),
    report_index_refs: list[str] | tuple[str, ...] = (),
    lineage_refs: list[str] | tuple[str, ...] = (),
    retain_roots: dict[str, Any] | None = None,
    tamper_probe_result: str = "verify_passed",
    mutation_probe_result: str = "not_probed",
) -> CASIntegrityReport:
    """Return a proof record using the store's manifest and verify primitives."""

    artifact = (
        ArtifactID.model_validate(artifact_id)
        if isinstance(artifact_id, str)
        else artifact_id
    )
    verification = store.verify(artifact)
    if not verification.ok:
        raise ArtifactIntegrityError(
            f"CAS integrity report requires a verified artifact: {verification.error}"
        )
    manifest = store.get_manifest(artifact)
    payload_digest = verification.actual_sha256_hex or manifest.integrity.sha256
    authority_ref = (
        manifest.authority.authority_envelope_ref if manifest.authority is not None else None
    )
    normalized_referrers = sorted({str(item) for item in referrers})
    normalized_report_refs = sorted({str(item) for item in report_index_refs})
    normalized_lineage_refs = sorted({str(item) for item in lineage_refs})
    gc_retain_reason, gc_dry_run_result = _gc_dry_run(
        artifact_ref=str(artifact),
        manifest=manifest,
        referrers=normalized_referrers,
        report_index_refs=normalized_report_refs,
        lineage_refs=normalized_lineage_refs,
        retain_roots=retain_roots or {},
    )
    return CASIntegrityReport(
        artifact_ref=str(artifact),
        payload_digest=payload_digest,
        canonicalization_rule_ref=_canonicalization_rule_ref(manifest),
        blob_uri=_blob_uri(store, artifact),
        manifest_ref=f"cas-manifest://{artifact}",
        authority_manifest_ref=authority_ref,
        duplicate_group_id=f"sha256:{payload_digest}",
        referrers=normalized_referrers,
        report_index_refs=normalized_report_refs,
        lineage_refs=normalized_lineage_refs,
        tamper_probe_result=tamper_probe_result,
        mutation_probe_result=mutation_probe_result,
        gc_retain_reason=gc_retain_reason,
        gc_dry_run_result=gc_dry_run_result,
    )


def _canonicalization_rule_ref(manifest: ArtifactManifest) -> str:
    canon = manifest.canon
    if canon is None:
        return "raw-bytes"
    return f"{canon.name}@{canon.version}"


def _blob_uri(store: Any, artifact_id: ArtifactID) -> str:
    del store
    return f"cas-blob://{artifact_id}"


def _gc_dry_run(
    *,
    artifact_ref: str,
    manifest: ArtifactManifest,
    referrers: list[str],
    report_index_refs: list[str],
    lineage_refs: list[str],
    retain_roots: dict[str, Any],
) -> tuple[str, str]:
    if manifest.authority is None:
        return "not_authority_bearing", "eligible"
    retaining_sources: list[str] = []
    report_root_refs = _reachable_artifact_refs(retain_roots.get("report_index"))
    lineage_root_refs = _reachable_artifact_refs(retain_roots.get("lineage"))
    workspace_root_refs = _reachable_artifact_refs(retain_roots.get("workspace"))
    if artifact_ref in report_root_refs:
        retaining_sources.append("report_index")
    if artifact_ref in lineage_root_refs:
        retaining_sources.append("lineage")
    if artifact_ref in workspace_root_refs:
        retaining_sources.append("workspace")
    if retaining_sources:
        return "authority_referenced_by:" + ",".join(retaining_sources), "retain"
    if report_index_refs or lineage_refs or referrers:
        return "authority_referrer_declared_but_unreachable", "blocked"
    return "authority_missing_referrer", "blocked"


def _reachable_artifact_refs(root: Any) -> set[str]:
    refs: set[str] = set()
    _collect_reachable_artifact_refs(root, refs)
    return refs


def _collect_reachable_artifact_refs(value: Any, refs: set[str]) -> None:
    if isinstance(value, str):
        if value.startswith("sha256:"):
            refs.add(value)
        return
    if isinstance(value, bytes):
        return
    if isinstance(value, dict):
        for item in value.values():
            _collect_reachable_artifact_refs(item, refs)
        return
    if isinstance(value, list | tuple | set):
        for item in value:
            _collect_reachable_artifact_refs(item, refs)


__all__ = ["CASIntegrityReport", "build_cas_integrity_report"]
