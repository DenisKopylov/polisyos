"""SLSA attestation bundle generation and SBOM attachment."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import content_hash
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.core.run.manifest import RunManifest

from ._assembler_archive import write_json
from ._assembler_errors import AuditAssemblyError
from .models import ExportOptions

__all__ = [
    "attach_sbom",
    "build_slsa_bundle",
    "extract_sbom_metadata",
    "find_decision_packet_id",
]


def find_decision_packet_id(
    artifact_ids: list[ArtifactID],
    manifests: dict[str, ArtifactManifest],
) -> ArtifactID | None:
    """Return the first decision-packet artifact, or *None*."""
    for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
        manifest = manifests.get(artifact_id.hex)
        if manifest is not None and manifest.kind == "scientist.decision_packet":
            return artifact_id
    return None


def build_slsa_bundle(
    cas: FileSystemCAS,
    options: ExportOptions,
    *,
    pkg_dir: Path,
    run_manifest: RunManifest,
    run_id: str,
    artifact_ids: list[ArtifactID],
    decision_packet_id: ArtifactID | None,
    warnings: list[str],
) -> dict[str, Any]:
    """Build the SLSA attestation, sign it, and upload to a transparency log."""
    from polisyos.core.security.slsa import (
        FulcioClient,
        RekorClient,
        SLSAAttestationBuilder,
        SLSAConfig,
    )

    try:
        config = SLSAConfig.from_env().with_overrides(
            mode=options.slsa_mode,
            policy=options.slsa_policy,
        )
    except (TypeError, ValueError) as exc:
        warnings.append(f"SLSA disabled due to invalid config: {exc}")
        return {"enabled": False, "status": "disabled", "mode": "off"}

    if not config.enabled:
        return {"enabled": False, "status": "disabled", "mode": config.mode.value}

    if decision_packet_id is None:
        if config.require_success:
            raise AuditAssemblyError(
                "SLSA policy is required but decision_packet artifact is missing"
            )
        warnings.append("SLSA skipped: decision_packet artifact was not found")
        return {
            "enabled": True,
            "status": "skipped",
            "mode": config.mode.value,
            "reason": "decision_packet_missing",
        }

    slsa_dir = pkg_dir / "slsa"
    slsa_dir.mkdir(parents=True, exist_ok=True)
    internal_params: dict[str, Any] = {
        "export_profile": options.profile.value,
        "signing_policy": options.signing_policy.value,
        "slsa_mode": config.mode.value,
        "slsa_policy": config.policy.value,
    }

    try:
        statement = SLSAAttestationBuilder(cas).build_attestation(
            decision_packet_id=decision_packet_id,
            run_manifest=run_manifest,
            input_artifact_ids=[
                artifact_id
                for artifact_id in artifact_ids
                if artifact_id.hex != decision_packet_id.hex
            ],
            internal_parameters=internal_params,
        )
        attestation_payload = statement.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
        )
        write_json(slsa_dir / "attestation.json", attestation_payload)

        payload_bytes = json.dumps(
            attestation_payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signer = FulcioClient(config)
        signed = signer.sign(payload_bytes)
        write_json(
            slsa_dir / "signature.json",
            {
                "algorithm": signed.algorithm,
                "signature_hex": signed.signature_hex,
                "payload_sha256": signed.payload_sha256,
                "certificate_pem": signed.certificate_pem,
                "certificate_chain": signed.certificate_chain,
                "oidc_issuer": signed.oidc_issuer,
                "oidc_subject": signed.oidc_subject,
                "signed_at": signed.signed_at,
            },
        )

        transparency = RekorClient(config).upload(
            attestation_bytes=payload_bytes,
            signature_hex=signed.signature_hex,
            certificate_pem=signed.certificate_pem,
        )
        if transparency is not None:
            write_json(
                slsa_dir / "transparency_entry.json",
                {
                    "mode": transparency.mode,
                    "log_id": transparency.log_id,
                    "log_index": transparency.log_index,
                    "integrated_time": transparency.integrated_time,
                    "payload_sha256": transparency.payload_sha256,
                    "verification_url": transparency.verification_url,
                    "created_at": transparency.created_at,
                },
            )

        return {
            "enabled": True,
            "status": "PASS",
            "mode": config.mode.value,
            "policy": config.policy.value,
            "attestation_path": "slsa/attestation.json",
            "signature_path": "slsa/signature.json",
            "transparency_path": (
                "slsa/transparency_entry.json" if transparency is not None else None
            ),
            "transparency_log_index": (
                transparency.log_index if transparency is not None else None
            ),
        }
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        write_json(
            slsa_dir / "error.json",
            {
                "status": "degraded",
                "mode": config.mode.value,
                "policy": config.policy.value,
                "error": str(exc),
            },
        )
        if config.require_success:
            raise AuditAssemblyError(f"SLSA required policy failed: {exc}") from exc
        warnings.append(f"SLSA degraded: {exc}")
        return {
            "enabled": True,
            "status": "WARN",
            "mode": config.mode.value,
            "policy": config.policy.value,
            "error": str(exc),
        }


def attach_sbom(
    cas: FileSystemCAS,
    *,
    pkg_dir: Path,
    run_manifest: RunManifest,
    warnings: list[str],
) -> dict[str, Any]:
    """Attach a CycloneDX SBOM to the audit package."""
    sbom_dir = pkg_dir / "sbom"
    sbom_dir.mkdir(parents=True, exist_ok=True)

    sbom_ref = run_manifest.sbom_ref
    if sbom_ref is not None:
        try:
            sbom_data = _load_json_payload(cas, sbom_ref.artifact_id)
            target = sbom_dir / "sbom.cdx.json"
            write_json(target, sbom_data)
            metadata = extract_sbom_metadata(sbom_data)
            return {
                "enabled": True,
                "status": "attached",
                "format": "cyclonedx-json",
                "path": "sbom/sbom.cdx.json",
                "cas_ref": sbom_ref.artifact_id.hex,
                **metadata,
            }
        except (ValueError, TypeError, OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            warnings.append(f"SBOM attach from CAS failed: {exc}")

    env_path = os.getenv("POLISYOS_SBOM_PATH", "").strip()
    if env_path:
        path = Path(env_path)
        if path.exists() and path.is_file():
            try:
                shutil.copy2(path, sbom_dir / "sbom.cdx.json")
                content = json.loads(path.read_text(encoding="utf-8"))
                metadata = extract_sbom_metadata(content)
                return {
                    "enabled": True,
                    "status": "attached_from_env",
                    "format": "cyclonedx-json",
                    "path": "sbom/sbom.cdx.json",
                    "source": str(path),
                    **metadata,
                }
            except (
                json.JSONDecodeError,
                OSError,
                TypeError,
                ValueError,
                UnicodeDecodeError,
            ) as exc:
                warnings.append(f"SBOM attach from env failed: {exc}")

    warnings.append("SBOM not available for audit package")
    return {"enabled": False, "status": "unavailable"}


def extract_sbom_metadata(sbom_data: dict[str, Any]) -> dict[str, Any]:
    """Extract summary metadata from a CycloneDX SBOM dict."""
    serialized = json.dumps(sbom_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "component_count": len(sbom_data.get("components", [])),
        "vulnerability_count": len(sbom_data.get("vulnerabilities", [])),
        "spec_version": sbom_data.get("specVersion", "unknown"),
        "hash": content_hash(serialized),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_json_payload(cas: FileSystemCAS, artifact_id: ArtifactID) -> dict[str, Any]:
    blob = cas.get_bytes(artifact_id)
    try:
        payload = from_canonical_bytes(blob)
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        payload = json.loads(blob.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact payload is not an object")
    return payload
