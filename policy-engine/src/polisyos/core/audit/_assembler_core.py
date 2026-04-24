"""Core AuditPackageAssembler class — orchestrates audit package creation."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.graph import resolve_dependency_graph
from polisyos.core.artifacts.signing import (
    DetachedSignature,
    SigningConfig,
    load_signer_from_config,
)
from polisyos.core.canon.canon_json import from_canonical_bytes
from polisyos.core.run.context import recover_pending_run_finalize
from polisyos.core.run.manifest import RunManifest
from polisyos.core.trace.record import TraceRecord

from ._assembler_archive import (
    build_index,
    compute_file_checksums,
    create_deterministic_tarball,
    write_checksums,
    write_json,
)
from ._assembler_errors import (
    AuditAssemblyError,
    IncompleteAuditError,
    IncompleteRunError,
    RunNotFoundError,
    UnsignedArtifactError,
)
from ._assembler_provenance import (
    build_merged_provenance,
    collect_public_keys,
    collect_signatures,
)
from ._assembler_slsa import (
    attach_sbom,
    build_slsa_bundle,
    find_decision_packet_id,
)
from .models import AuditExportResult, ExportOptions, ExportProfile, SigningPolicy
from .prov_json import ProvJsonConverter, prov_json_to_dot

if TYPE_CHECKING:
    from polisyos.core.artifacts.ids import ArtifactID
    from polisyos.core.artifacts.manifest import ArtifactManifest
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.core.contracts.provenance import ProvenanceCoreGraph

__all__ = [
    "AuditPackageAssembler",
]

logger = get_logger(__name__)


@dataclass(frozen=True)
class _RunData:
    run_id: str
    run_dir: Path
    manifest: RunManifest
    roots: list[ArtifactID]


class AuditPackageAssembler:
    """Build portable audit package from CAS and run metadata."""

    def __init__(
        self,
        cas: FileSystemCAS,
        runs_dir: Path,
        options: ExportOptions | None = None,
    ) -> None:
        self._cas = cas
        self._runs_dir = runs_dir
        self._options = options or ExportOptions()

    def export(self, run_id: str, output_path: Path | None = None) -> AuditExportResult:
        started = time.perf_counter()
        run_data = self._load_run_data(run_id)
        artifact_ids, manifests, warnings = self._resolve_transitive_closure(run_data.roots)
        registry_id = run_data.manifest.registry_bundle.artifact_id
        if not any(item.hex == registry_id.hex for item in artifact_ids):
            artifact_ids.append(registry_id)
        manifests[registry_id.hex] = self._cas.get_manifest(registry_id)
        signatures, unsigned = collect_signatures(self._cas, artifact_ids)
        if unsigned and self._options.signing_policy == SigningPolicy.STRICT:
            raise UnsignedArtifactError(
                f"Unsigned artifacts under strict policy: {', '.join(unsigned[:10])}"
            )
        public_keys, identities, key_warnings = collect_public_keys(signatures)
        warnings.extend(key_warnings)

        merged_graph = build_merged_provenance(
            self._cas,
            run_data.run_id,
            run_data.run_dir,
            artifact_ids,
            manifests,
        )
        prov_json = ProvJsonConverter(
            run_id=run_data.run_id,
            include_bundle=True,
        ).convert(merged_graph)

        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive_path = output_path or Path(
            f"audit_{run_data.run_id}_{timestamp}.polisyos-audit.tar.gz"
        )

        with tempfile.TemporaryDirectory(prefix="polisyos-audit-export-") as tmp:
            pkg_dir = Path(tmp)
            self._assemble_tree(
                pkg_dir=pkg_dir,
                run_data=run_data,
                artifact_ids=artifact_ids,
                manifests=manifests,
                signatures=signatures,
                public_keys=public_keys,
                identities=identities,
                prov_json=prov_json,
                merged_graph=merged_graph,
                warnings=warnings,
            )
            final_archive = create_deterministic_tarball(pkg_dir, archive_path)

        elapsed = time.perf_counter() - started
        return AuditExportResult(
            archive_path=final_archive,
            run_id=run_data.run_id,
            artifacts_exported=len(artifact_ids),
            total_bytes=final_archive.stat().st_size if final_archive.exists() else 0,
            signatures_included=len(signatures),
            unsigned_artifacts=unsigned,
            prov_entities=len(prov_json.get("entity", {})),
            prov_activities=len(prov_json.get("activity", {})),
            prov_agents=len(prov_json.get("agent", {})),
            warnings=warnings,
            duration_seconds=elapsed,
        )

    # ------------------------------------------------------------------
    # Run loading
    # ------------------------------------------------------------------

    def _load_run_data(self, run_id: str) -> _RunData:
        run_dir = self._runs_dir / run_id
        manifest_path = run_dir / "manifest.json"
        manifest: RunManifest
        if manifest_path.exists():
            raw = manifest_path.read_text("utf-8")
            try:
                manifest = RunManifest.model_validate_json(raw)
            except (TypeError, ValueError) as exc:
                raise AuditAssemblyError(f"Unsupported run manifest format: {exc}") from exc
        else:
            manifest = self._load_manifest_from_trace(run_dir, run_id)

        if manifest.status == "running" or manifest.finished_at is None:
            raise IncompleteRunError(f"Run {run_id} is not finalized")

        roots = self._resolve_root_artifacts(manifest, run_dir)
        if not roots:
            raise AuditAssemblyError(f"No root artifacts resolved for run {run_id}")
        return _RunData(run_id=run_id, run_dir=run_dir, manifest=manifest, roots=roots)

    def _load_manifest_from_trace(self, run_dir: Path, run_id: str) -> RunManifest:
        recover_pending_run_finalize(self._cas, run_dir)
        trace_path = run_dir / "trace.jsonl"
        if not trace_path.exists():
            raise RunNotFoundError(
                f"Run manifest not found at {run_dir / 'manifest.json'} and trace missing"
            )
        manifest_ref: ArtifactID | None = None
        for line in trace_path.read_text("utf-8").splitlines():
            try:
                record = TraceRecord.model_validate_json(line)
            except (TypeError, ValueError):
                continue
            if record.event == "RUN_FINALIZED":
                for ref in record.refs.outputs:
                    if ref.kind == "core.run_manifest":
                        manifest_ref = ref.artifact_id
        if manifest_ref is None:
            raise RunNotFoundError(f"Could not resolve core.run_manifest for run {run_id}")
        payload = self._cas.get_bytes(manifest_ref)
        return RunManifest.model_validate(from_canonical_bytes(payload))

    # ------------------------------------------------------------------
    # Artifact resolution
    # ------------------------------------------------------------------

    def _resolve_root_artifacts(self, manifest: RunManifest, run_dir: Path) -> list[ArtifactID]:
        roots: list[ArtifactID] = []
        decision = [ref for ref in manifest.outputs if ref.kind == "scientist.decision_packet"]
        candidates = decision if decision else list(manifest.outputs)
        for ref in candidates:
            roots.append(ref.artifact_id)
        if not roots and manifest.trace_ref is not None:
            roots.append(manifest.trace_ref.artifact_id)

        # Fallback for runs where outputs were not captured in manifest.
        if not roots:
            trace_path = run_dir / "trace.jsonl"
            if trace_path.exists():
                for line in trace_path.read_text("utf-8").splitlines():
                    try:
                        rec = TraceRecord.model_validate_json(line)
                    except (TypeError, ValueError):
                        continue
                    if rec.event in {"NODE_OK", "RUN_FINALIZED", "RUN_OUTPUT_ADDED"}:
                        for ref in rec.refs.outputs:
                            roots.append(ref.artifact_id)
        dedup: dict[str, ArtifactID] = {item.hex: item for item in roots}
        return [dedup[key] for key in sorted(dedup)]

    def _resolve_transitive_closure(
        self,
        roots: list[ArtifactID],
    ) -> tuple[list[ArtifactID], dict[str, ArtifactManifest], list[str]]:
        all_ids: dict[str, ArtifactID] = {}
        manifests: dict[str, ArtifactManifest] = {}
        warnings: list[str] = []
        for root in roots:
            graph = resolve_dependency_graph(
                self._cas,
                root,
                max_depth=self._options.max_depth,
                max_nodes=self._options.max_nodes,
                verify_integrity=True,
            )
            if not graph.is_complete:
                missing = ", ".join(node.artifact_id.hex for node in graph.missing_nodes[:10])
                raise IncompleteAuditError(f"Missing/corrupted artifacts in closure: {missing}")
            for item in graph.all_artifact_ids():
                all_ids[item.hex] = item

        filtered: dict[str, ArtifactID] = {}
        for hex_id, artifact_id in all_ids.items():
            manifest = self._cas.get_manifest(artifact_id)
            manifests[hex_id] = manifest
            if manifest.kind in self._options.exclude_kinds and artifact_id not in roots:
                warnings.append(f"Excluded artifact by kind: {artifact_id} ({manifest.kind})")
                continue
            filtered[hex_id] = artifact_id
        return [filtered[key] for key in sorted(filtered)], manifests, warnings

    # ------------------------------------------------------------------
    # Tree assembly
    # ------------------------------------------------------------------

    def _assemble_tree(
        self,
        *,
        pkg_dir: Path,
        run_data: _RunData,
        artifact_ids: list[ArtifactID],
        manifests: dict[str, ArtifactManifest],
        signatures: dict[str, DetachedSignature],
        public_keys: dict[str, bytes],
        identities: dict[str, str],
        prov_json: dict[str, Any],
        merged_graph: ProvenanceCoreGraph,
        warnings: list[str],
    ) -> None:
        for sub in (
            "provenance",
            "metadata",
            "artifacts/sha256",
            "signatures/sha256",
            "signatures/public_keys",
            "verification",
            "visualization",
        ):
            (pkg_dir / sub).mkdir(parents=True, exist_ok=True)

        write_json(pkg_dir / "provenance" / "prov.json", prov_json)
        write_json(pkg_dir / "provenance" / "prov-core.json", merged_graph.to_dict())

        write_json(
            pkg_dir / "metadata" / "run_manifest.json",
            run_data.manifest.model_dump(mode="python"),
        )
        write_json(
            pkg_dir / "metadata" / "export_opts.json",
            {
                "profile": self._options.profile.value,
                "manifests_only": self._options.profile == ExportProfile.MANIFESTS_ONLY,
                "exclude_kinds": sorted(self._options.exclude_kinds),
                "signing_policy": self._options.signing_policy.value,
                "slsa_mode": self._options.slsa_mode,
                "slsa_policy": self._options.slsa_policy,
            },
        )
        if run_data.manifest.env is not None:
            write_json(
                pkg_dir / "metadata" / "environment.json",
                run_data.manifest.env.model_dump(),
            )
        if run_data.manifest.environment_manifest_ref is not None:
            env_id = run_data.manifest.environment_manifest_ref.artifact_id
            try:
                write_json(
                    pkg_dir / "metadata" / "environment.json",
                    _load_json_payload(self._cas, env_id),
                )
            except (ValueError, TypeError, OSError, UnicodeDecodeError) as exc:
                logger.debug("Ignored exception: %s", exc)

        decision_packet_id = find_decision_packet_id(artifact_ids, manifests)
        if decision_packet_id is not None:
            try:
                write_json(
                    pkg_dir / "metadata" / "decision_packet.json",
                    _load_json_payload(self._cas, decision_packet_id),
                )
            except (ValueError, TypeError, OSError, UnicodeDecodeError) as exc:
                logger.debug("Ignored exception: %s", exc)

        slsa_info = build_slsa_bundle(
            self._cas,
            self._options,
            pkg_dir=pkg_dir,
            run_manifest=run_data.manifest,
            run_id=run_data.run_id,
            artifact_ids=artifact_ids,
            decision_packet_id=decision_packet_id,
            warnings=warnings,
        )
        sbom_info = attach_sbom(
            self._cas,
            pkg_dir=pkg_dir,
            run_manifest=run_data.manifest,
            warnings=warnings,
        )

        trace_path = run_data.run_dir / "trace.jsonl"
        if trace_path.exists():
            shutil.copy2(trace_path, pkg_dir / "metadata" / "trace.jsonl")
        audit_path = run_data.run_dir / "audit.jsonl"
        if audit_path.exists():
            shutil.copy2(audit_path, pkg_dir / "metadata" / "audit.jsonl")

        for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
            blob_path, manifest_path = self._cas.get_paths(artifact_id)
            rel_dir = Path(artifact_id.hex[:2]) / artifact_id.hex[2:4]
            dst_dir = pkg_dir / "artifacts" / "sha256" / rel_dir
            dst_dir.mkdir(parents=True, exist_ok=True)
            if self._options.profile == ExportProfile.FULL:
                shutil.copy2(blob_path, dst_dir / f"{artifact_id.hex}.blob")
            shutil.copy2(manifest_path, dst_dir / f"{artifact_id.hex}.manifest.json")

            signature = signatures.get(artifact_id.hex)
            if signature is None:
                continue
            sig_dir = pkg_dir / "signatures" / "sha256" / rel_dir
            sig_dir.mkdir(parents=True, exist_ok=True)
            write_json(sig_dir / f"{artifact_id.hex}.sig", signature.model_dump(mode="python"))

        for key_id, pem in sorted(public_keys.items(), key=lambda item: item[0]):
            safe_id = key_id.replace(":", "_")
            (pkg_dir / "signatures" / "public_keys" / f"key_{safe_id}.pem").write_bytes(pem)
        write_json(pkg_dir / "signatures" / "public_keys" / "identities.json", identities)

        requirements = "cryptography>=42.0.0\n"
        (pkg_dir / "verification" / "requirements.txt").write_text(requirements, encoding="utf-8")
        (pkg_dir / "verification" / "instructions.md").write_text(
            (Path(__file__).with_name("instructions_template.md")).read_text("utf-8"),
            encoding="utf-8",
        )
        (pkg_dir / "verification" / "verify.py").write_text(
            (Path(__file__).with_name("standalone_verifier_template.py")).read_text("utf-8"),
            encoding="utf-8",
        )

        dot_content = prov_json_to_dot(prov_json)
        (pkg_dir / "visualization" / "provenance_graph.dot").write_text(
            dot_content,
            encoding="utf-8",
        )
        dot_binary = shutil.which("dot")
        if self._options.include_visualization and dot_binary:
            try:
                subprocess.run(
                    [
                        dot_binary,
                        "-Tsvg",
                        str(pkg_dir / "visualization" / "provenance_graph.dot"),
                        "-o",
                        str(pkg_dir / "visualization" / "provenance_graph.svg"),
                    ],
                    check=True,
                    capture_output=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError, OSError):
                warnings.append("Graphviz not available; skipped SVG rendering")

        checksums = compute_file_checksums(
            pkg_dir,
            exclude={"verification/checksums.sha256", "verification/checksums.sha256.sig"},
        )
        write_checksums(pkg_dir / "verification" / "checksums.sha256", checksums)

        pkg_sig = self._maybe_sign_checksums(
            pkg_dir / "verification" / "checksums.sha256",
            pkg_dir / "verification" / "checksums.sha256.sig",
            pkg_dir / "signatures" / "public_keys",
            warnings,
        )

        index = build_index(
            self._options,
            run_id=run_data.run_id,
            run_status=run_data.manifest.status,
            artifact_ids=artifact_ids,
            signatures=signatures,
            prov_json=prov_json,
            checksums=checksums,
            pkg_sig=pkg_sig,
            manifests=manifests,
            warnings=warnings,
            slsa=slsa_info,
            sbom=sbom_info,
        )
        write_json(pkg_dir / "index.json", index)

    # ------------------------------------------------------------------
    # Package signing
    # ------------------------------------------------------------------

    def _maybe_sign_checksums(
        self,
        checksums_path: Path,
        signature_path: Path,
        public_keys_dir: Path,
        warnings: list[str],
    ) -> dict[str, Any] | None:
        try:
            signer = load_signer_from_config(SigningConfig.from_env())
        except (RuntimeError, OSError, ValueError, TypeError):
            warnings.append("Package checksum signature skipped: no signing key configured")
            return None

        private_key = getattr(signer, "_private_key", None)
        public_key = getattr(signer, "_public_key", None)
        if private_key is None or public_key is None:
            warnings.append("Package checksum signature skipped: signer internals unavailable")
            return None
        payload = checksums_path.read_bytes()
        signature_hex = private_key.sign(payload).hex()
        data = {
            "algorithm": "Ed25519",
            "key_id": signer.key_id,
            "signature_hex": signature_hex,
            "signed_at": datetime.now(UTC).isoformat(),
            "target": "verification/checksums.sha256",
        }
        write_json(signature_path, data)
        safe_key_id = signer.key_id.replace(":", "_")
        pem = public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )
        key_path = public_keys_dir / f"key_{safe_key_id}.pem"
        if not key_path.exists():
            key_path.write_bytes(pem)
        return data


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_json_payload(cas: FileSystemCAS, artifact_id: ArtifactID) -> dict[str, Any]:
    blob = cas.get_bytes(artifact_id)
    try:
        payload = from_canonical_bytes(blob)
    except (TypeError, ValueError):
        payload = json.loads(blob.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact payload is not an object")
    return payload
