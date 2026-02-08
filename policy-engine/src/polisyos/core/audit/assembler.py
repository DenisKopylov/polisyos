from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_public_key

from polisyos.core.artifacts.graph import resolve_dependency_graph
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactManifest
from polisyos.core.artifacts.signing import (
    DEFAULT_IDENTITIES_PATH,
    DEFAULT_TRUST_DIR,
    DetachedSignature,
    SigningConfig,
    compute_key_id,
    load_signer_from_config,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon.canon_json import from_canonical_bytes, to_canonical_bytes
from polisyos.core.run.manifest import RunManifest
from polisyos.core.trace.record import TraceRecord
from polisyos.fabric.provenance.core import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEntity,
)
from polisyos.runtime.manifest import RunManifest as LegacyRunManifest

from .models import AuditExportResult, ExportOptions, ExportProfile, SigningPolicy
from .prov_json import ProvJsonConverter, prov_json_to_dot


class AuditAssemblyError(RuntimeError):
    """Base export error."""


class RunNotFoundError(AuditAssemblyError):
    """Run manifest not found."""


class IncompleteRunError(AuditAssemblyError):
    """Run not finalized."""


class IncompleteAuditError(AuditAssemblyError):
    """Dependency closure is incomplete."""


class UnsignedArtifactError(AuditAssemblyError):
    """Strict signing policy failure."""


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
        signatures, unsigned = self._collect_signatures(artifact_ids)
        if unsigned and self._options.signing_policy == SigningPolicy.STRICT:
            raise UnsignedArtifactError(
                f"Unsigned artifacts under strict policy: {', '.join(unsigned[:10])}"
            )
        public_keys, identities, key_warnings = self._collect_public_keys(signatures)
        warnings.extend(key_warnings)

        merged_graph = self._build_merged_provenance(
            run_data.run_id,
            run_data.run_dir,
            artifact_ids,
            manifests,
        )
        prov_json = ProvJsonConverter(
            run_id=run_data.run_id,
            include_bundle=True,
        ).convert(merged_graph)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
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
            final_archive = self._create_deterministic_tarball(pkg_dir, archive_path)

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

    def _load_run_data(self, run_id: str) -> _RunData:
        run_dir = self._runs_dir / run_id
        manifest_path = run_dir / "manifest.json"
        manifest: RunManifest
        if manifest_path.exists():
            raw = manifest_path.read_text("utf-8")
            try:
                manifest = RunManifest.model_validate_json(raw)
            except Exception as exc:
                try:
                    LegacyRunManifest.model_validate_json(raw)
                except Exception:
                    raise AuditAssemblyError(f"Unsupported run manifest format: {exc}") from exc
                raise AuditAssemblyError(
                    "Legacy runtime RunManifest is not supported for audit export; "
                    "use CAS-native runs."
                ) from exc
        else:
            manifest = self._load_manifest_from_trace(run_dir, run_id)

        if manifest.status == "running" or manifest.finished_at is None:
            raise IncompleteRunError(f"Run {run_id} is not finalized")

        roots = self._resolve_root_artifacts(manifest, run_dir)
        if not roots:
            raise AuditAssemblyError(f"No root artifacts resolved for run {run_id}")
        return _RunData(run_id=run_id, run_dir=run_dir, manifest=manifest, roots=roots)

    def _load_manifest_from_trace(self, run_dir: Path, run_id: str) -> RunManifest:
        trace_path = run_dir / "trace.jsonl"
        if not trace_path.exists():
            raise RunNotFoundError(
                f"Run manifest not found at {run_dir / 'manifest.json'} and trace missing"
            )
        manifest_ref: ArtifactID | None = None
        for line in trace_path.read_text("utf-8").splitlines():
            try:
                record = TraceRecord.model_validate_json(line)
            except Exception:
                continue
            if record.event == "RUN_FINALIZED":
                for ref in record.refs.outputs:
                    if ref.kind == "core.run_manifest":
                        manifest_ref = ref.artifact_id
        if manifest_ref is None:
            raise RunNotFoundError(f"Could not resolve core.run_manifest for run {run_id}")
        payload = self._cas.get_bytes(manifest_ref)
        return RunManifest.model_validate(from_canonical_bytes(payload))

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
                    except Exception:
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
            if (
                manifest.kind in self._options.exclude_kinds
                and artifact_id not in roots
            ):
                warnings.append(f"Excluded artifact by kind: {artifact_id} ({manifest.kind})")
                continue
            filtered[hex_id] = artifact_id
        return [filtered[key] for key in sorted(filtered)], manifests, warnings

    def _collect_signatures(
        self,
        artifact_ids: list[ArtifactID],
    ) -> tuple[dict[str, DetachedSignature], list[str]]:
        signatures: dict[str, DetachedSignature] = {}
        unsigned: list[str] = []
        for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
            signature = self._cas.get_signature(artifact_id)
            if signature is None:
                unsigned.append(str(artifact_id))
                continue
            signatures[artifact_id.hex] = signature
        return signatures, unsigned

    def _collect_public_keys(
        self,
        signatures: dict[str, DetachedSignature],
    ) -> tuple[dict[str, bytes], dict[str, str], list[str]]:
        key_ids = {sig.key_id for sig in signatures.values()}
        found: dict[str, bytes] = {}
        warnings: list[str] = []
        if not key_ids:
            return found, {}, warnings

        candidates = [
            DEFAULT_TRUST_DIR,
            Path(".polisyos/keys/trusted"),
            Path.home() / ".polisyos/keys/trusted",
        ]
        for directory in candidates:
            if not directory.exists() or not directory.is_dir():
                continue
            for key_file in sorted(directory.glob("*")):
                if not key_file.is_file():
                    continue
                try:
                    pem = key_file.read_bytes()
                    public_key = load_pem_public_key(pem)
                    key_id = compute_key_id(public_key)
                except Exception:
                    continue
                if key_id in key_ids:
                    found[key_id] = pem

        missing = sorted(key_ids - set(found))
        for key_id in missing:
            warnings.append(f"Public key not found for key_id={key_id}")

        identities: dict[str, str] = {}
        for path in (
            DEFAULT_IDENTITIES_PATH,
            Path(".polisyos/keys/identities.json"),
            Path.home() / ".polisyos/keys/identities.json",
        ):
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text("utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            for key_id, value in payload.items():
                if key_id in key_ids and isinstance(value, str):
                    identities[key_id] = value
        return found, identities, warnings

    def _build_merged_provenance(
        self,
        run_id: str,
        run_dir: Path,
        artifact_ids: list[ArtifactID],
        manifests: dict[str, ArtifactManifest],
    ) -> ProvenanceCoreGraph:
        graph = ProvenanceCoreGraph(graph_id=f"audit_{run_id}")
        graph.add_agent(
            ProvenanceAgent(
                agent_id="agent/system",
                agent_type=AgentType.SYSTEM,
                label="Policy OS",
            )
        )

        for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
            manifest = manifests[artifact_id.hex]
            entity = ProvenanceEntity(
                entity_id=str(artifact_id),
                entity_type=EntityType.DATASET,
                label=f"{manifest.kind}:{artifact_id.hex[:12]}",
                created_at=manifest.created_at,
                attributes={
                    "artifact_id": str(artifact_id),
                    "kind": manifest.kind,
                    "media_type": manifest.media_type,
                    "byte_size": int(manifest.byte_size),
                    "sha256": manifest.integrity.sha256,
                },
            )
            graph.add_entity(entity)
            for input_ref in manifest.inputs:
                graph.add_derivation(str(artifact_id), str(input_ref.artifact_id))
            if manifest.producer is not None:
                component = str(manifest.producer.component).replace("@", "_")
                agent_id = f"agent/{component}"
                graph.add_agent(
                    ProvenanceAgent(
                        agent_id=agent_id,
                        agent_type=AgentType.SYSTEM,
                        label=str(manifest.producer.component),
                        metadata={"version": manifest.producer.version},
                    )
                )
                graph.add_attribution(str(artifact_id), agent_id)

        trace_path = run_dir / "trace.jsonl"
        if trace_path.exists():
            for idx, line in enumerate(trace_path.read_text("utf-8").splitlines()):
                try:
                    record = TraceRecord.model_validate_json(line)
                except Exception:
                    continue
                activity_id = f"{run_id}/{idx:05d}/{record.phase}/{record.event}"
                activity = ProvenanceActivity(
                    activity_id=activity_id,
                    activity_type=_map_trace_activity(record.phase, record.event),
                    label=f"{record.phase}:{record.event}",
                    started_at=record.ts,
                    ended_at=record.ts,
                    parameters={
                        "phase": record.phase,
                        "event": record.event,
                    },
                )
                graph.add_activity(activity)
                graph.add_association(activity_id, "agent/system")
                for ref in record.refs.inputs:
                    graph.add_usage(activity_id, str(ref.artifact_id))
                for ref in record.refs.outputs:
                    graph.add_generation(str(ref.artifact_id), activity_id)

        for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
            try:
                payload = self._load_json_payload(artifact_id)
            except Exception:
                continue
            prov_ref = payload.get("provenance_ref")
            prov_artifact_id = _extract_provenance_artifact_id(prov_ref)
            if prov_artifact_id is None:
                continue
            try:
                prov_payload = self._load_json_payload(prov_artifact_id)
                sub_graph = ProvenanceCoreGraph.from_dict(prov_payload)
            except Exception:
                continue
            for item in sub_graph.entities.values():
                graph.add_entity(item)
            for item in sub_graph.activities.values():
                graph.add_activity(item)
            for item in sub_graph.agents.values():
                graph.add_agent(item)
            for edge in sub_graph.edges:
                graph.edges.append(edge)

        return graph

    def _load_json_payload(self, artifact_id: ArtifactID) -> dict[str, Any]:
        blob = self._cas.get_bytes(artifact_id)
        try:
            payload = from_canonical_bytes(blob)
        except Exception:
            payload = json.loads(blob.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("artifact payload is not an object")
        return payload

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

        _write_json(pkg_dir / "provenance" / "prov.json", prov_json)
        _write_json(pkg_dir / "provenance" / "prov-core.json", merged_graph.to_dict())

        _write_json(
            pkg_dir / "metadata" / "run_manifest.json",
            run_data.manifest.model_dump(mode="python"),
        )
        _write_json(
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
            _write_json(
                pkg_dir / "metadata" / "environment.json",
                run_data.manifest.env.model_dump(),
            )
        if run_data.manifest.environment_manifest_ref is not None:
            env_id = run_data.manifest.environment_manifest_ref.artifact_id
            try:
                _write_json(
                    pkg_dir / "metadata" / "environment.json",
                    self._load_json_payload(env_id),
                )
            except Exception:
                pass

        decision_packet_id = _find_decision_packet_id(artifact_ids, manifests)
        if decision_packet_id is not None:
            try:
                _write_json(
                    pkg_dir / "metadata" / "decision_packet.json",
                    self._load_json_payload(decision_packet_id),
                )
            except Exception:
                pass

        slsa_info = self._build_slsa_bundle(
            pkg_dir=pkg_dir,
            run_data=run_data,
            artifact_ids=artifact_ids,
            decision_packet_id=decision_packet_id,
            warnings=warnings,
        )
        sbom_info = self._attach_sbom(
            pkg_dir=pkg_dir,
            run_data=run_data,
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
            _write_json(sig_dir / f"{artifact_id.hex}.sig", signature.model_dump(mode="python"))

        for key_id, pem in sorted(public_keys.items(), key=lambda item: item[0]):
            safe_id = key_id.replace(":", "_")
            (pkg_dir / "signatures" / "public_keys" / f"key_{safe_id}.pem").write_bytes(pem)
        _write_json(pkg_dir / "signatures" / "public_keys" / "identities.json", identities)

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
        if self._options.include_visualization and shutil.which("dot"):
            try:
                subprocess.run(
                    [
                        "dot",
                        "-Tsvg",
                        str(pkg_dir / "visualization" / "provenance_graph.dot"),
                        "-o",
                        str(pkg_dir / "visualization" / "provenance_graph.svg"),
                    ],
                    check=True,
                    capture_output=True,
                )
            except Exception:
                warnings.append("Graphviz not available; skipped SVG rendering")

        checksums = _compute_file_checksums(
            pkg_dir,
            exclude={"verification/checksums.sha256", "verification/checksums.sha256.sig"},
        )
        _write_checksums(pkg_dir / "verification" / "checksums.sha256", checksums)

        pkg_sig = self._maybe_sign_checksums(
            pkg_dir / "verification" / "checksums.sha256",
            pkg_dir / "verification" / "checksums.sha256.sig",
            pkg_dir / "signatures" / "public_keys",
            warnings,
        )

        index = self._build_index(
            run_data=run_data,
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
        _write_json(pkg_dir / "index.json", index)

    def _attach_sbom(
        self,
        *,
        pkg_dir: Path,
        run_data: _RunData,
        warnings: list[str],
    ) -> dict[str, Any]:
        sbom_dir = pkg_dir / "sbom"
        sbom_dir.mkdir(parents=True, exist_ok=True)

        sbom_ref = run_data.manifest.sbom_ref
        if sbom_ref is not None:
            try:
                sbom_data = self._load_json_payload(sbom_ref.artifact_id)
                target = sbom_dir / "sbom.cdx.json"
                _write_json(target, sbom_data)
                metadata = self._extract_sbom_metadata(sbom_data)
                return {
                    "enabled": True,
                    "status": "attached",
                    "format": "cyclonedx-json",
                    "path": "sbom/sbom.cdx.json",
                    "cas_ref": sbom_ref.artifact_id.hex,
                    **metadata,
                }
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"SBOM attach from CAS failed: {exc}")

        env_path = os.getenv("POLISYOS_SBOM_PATH", "").strip()
        if env_path:
            path = Path(env_path)
            if path.exists() and path.is_file():
                try:
                    shutil.copy2(path, sbom_dir / "sbom.cdx.json")
                    content = json.loads(path.read_text(encoding="utf-8"))
                    metadata = self._extract_sbom_metadata(content)
                    return {
                        "enabled": True,
                        "status": "attached_from_env",
                        "format": "cyclonedx-json",
                        "path": "sbom/sbom.cdx.json",
                        "source": str(path),
                        **metadata,
                    }
                except Exception as exc:  # noqa: BLE001
                    warnings.append(f"SBOM attach from env failed: {exc}")

        warnings.append("SBOM not available for audit package")
        return {"enabled": False, "status": "unavailable"}

    def _extract_sbom_metadata(self, sbom_data: dict[str, Any]) -> dict[str, Any]:
        serialized = json.dumps(sbom_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {
            "component_count": len(sbom_data.get("components", [])),
            "vulnerability_count": len(sbom_data.get("vulnerabilities", [])),
            "spec_version": sbom_data.get("specVersion", "unknown"),
            "hash": hashlib.sha256(serialized).hexdigest(),
        }

    def _build_slsa_bundle(
        self,
        *,
        pkg_dir: Path,
        run_data: _RunData,
        artifact_ids: list[ArtifactID],
        decision_packet_id: ArtifactID | None,
        warnings: list[str],
    ) -> dict[str, Any]:
        from polisyos.core.security.slsa import (
            FulcioClient,
            RekorClient,
            SLSAAttestationBuilder,
            SLSAConfig,
        )

        try:
            config = SLSAConfig.from_env().with_overrides(
                mode=self._options.slsa_mode,
                policy=self._options.slsa_policy,
            )
        except Exception as exc:
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
            "export_profile": self._options.profile.value,
            "signing_policy": self._options.signing_policy.value,
            "slsa_mode": config.mode.value,
            "slsa_policy": config.policy.value,
        }

        try:
            statement = SLSAAttestationBuilder(self._cas).build_attestation(
                decision_packet_id=decision_packet_id,
                run_manifest=run_data.manifest,
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
            _write_json(slsa_dir / "attestation.json", attestation_payload)

            payload_bytes = to_canonical_bytes(attestation_payload)
            signer = FulcioClient(config)
            signed = signer.sign(payload_bytes)
            _write_json(
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
                _write_json(
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
        except Exception as exc:
            _write_json(
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

    def _maybe_sign_checksums(
        self,
        checksums_path: Path,
        signature_path: Path,
        public_keys_dir: Path,
        warnings: list[str],
    ) -> dict[str, Any] | None:
        try:
            signer = load_signer_from_config(SigningConfig.from_env())
        except Exception:
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
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "target": "verification/checksums.sha256",
        }
        _write_json(signature_path, data)
        safe_key_id = signer.key_id.replace(":", "_")
        pem = public_key.public_bytes(
            encoding=Encoding.PEM,
            format=PublicFormat.SubjectPublicKeyInfo,
        )
        key_path = public_keys_dir / f"key_{safe_key_id}.pem"
        if not key_path.exists():
            key_path.write_bytes(pem)
        return data

    def _build_index(
        self,
        *,
        run_data: _RunData,
        artifact_ids: list[ArtifactID],
        signatures: dict[str, DetachedSignature],
        prov_json: dict[str, Any],
        checksums: dict[str, str],
        pkg_sig: dict[str, Any] | None,
        manifests: dict[str, ArtifactManifest],
        warnings: list[str],
        slsa: dict[str, Any],
        sbom: dict[str, Any],
    ) -> dict[str, Any]:
        created_at = (
            datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )
        root = _find_decision_packet_id(artifact_ids, manifests)
        files = [{"path": path, "sha256": sha} for path, sha in sorted(checksums.items())]
        return {
            "schema_version": "1.0.0",
            "package_format": "polisyos-audit-v1",
            "created_at": created_at,
            "created_by": {
                "tool": "polisyos",
                "command": f"audit export {run_data.run_id}",
            },
            "run_id": run_data.run_id,
            "run_status": run_data.manifest.status,
            "export_profile": self._options.profile.value,
            "provenance": {
                "format": "W3C-PROV-JSON",
                "path": "provenance/prov.json",
                "entity_count": len(prov_json.get("entity", {})),
                "activity_count": len(prov_json.get("activity", {})),
                "agent_count": len(prov_json.get("agent", {})),
            },
            "artifacts": {
                "total_count": len(artifact_ids),
                "signed_count": len(signatures),
                "unsigned_count": max(0, len(artifact_ids) - len(signatures)),
                "root_artifact_id": str(root) if root is not None else None,
            },
            "signatures": {
                "algorithm": "Ed25519",
                "package_checksum_signature": pkg_sig is not None,
            },
            "slsa": slsa,
            "sbom": sbom,
            "integrity": {
                "package_checksum_file": "verification/checksums.sha256",
                "package_checksum_signature": (
                    "verification/checksums.sha256.sig" if pkg_sig is not None else None
                ),
                "algorithm": "SHA-256",
            },
            "warnings": sorted(set(warnings)),
            "files": files,
        }

    def _create_deterministic_tarball(self, src_dir: Path, output_path: Path) -> Path:
        archive_path = _normalize_archive_path(output_path)
        archive_path.parent.mkdir(parents=True, exist_ok=True)

        with archive_path.open("wb") as raw:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                fileobj=raw,
                mtime=0,
            ) as gz:
                with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as tar:
                    for path in sorted(src_dir.rglob("*")):
                        rel = path.relative_to(src_dir).as_posix()
                        if path.is_symlink():
                            continue
                        info = tar.gettarinfo(str(path), arcname=rel)
                        info.uid = 0
                        info.gid = 0
                        info.uname = ""
                        info.gname = ""
                        info.mtime = 0
                        if path.is_dir():
                            info.mode = 0o755
                            tar.addfile(info)
                            continue
                        if path.is_file():
                            info.mode = 0o644
                            with path.open("rb") as handle:
                                tar.addfile(info, handle)
        return archive_path


def _extract_provenance_artifact_id(value: Any) -> ArtifactID | None:
    if isinstance(value, dict):
        inner = value.get("artifact_id")
        if isinstance(inner, str):
            try:
                return ArtifactID.model_validate(inner)
            except Exception:
                return None
    if isinstance(value, str):
        try:
            return ArtifactID.model_validate(value)
        except Exception:
            return None
    return None


def _map_trace_activity(phase: str, event: str) -> ActivityType:
    key = f"{phase.lower()}:{event.lower()}"
    if "ingest" in key:
        return ActivityType.INGEST
    if "query" in key:
        return ActivityType.QUERY
    if "merge" in key:
        return ActivityType.MERGE
    if "sim" in key:
        return ActivityType.SIMULATION_STEP
    if "validate" in key:
        return ActivityType.VALIDATION
    if "etl" in key:
        return ActivityType.ETL
    if "aggregate" in key:
        return ActivityType.AGGREGATION
    return ActivityType.VALIDATION


def _find_decision_packet_id(
    artifact_ids: list[ArtifactID],
    manifests: dict[str, ArtifactManifest],
) -> ArtifactID | None:
    for artifact_id in sorted(artifact_ids, key=lambda item: item.hex):
        manifest = manifests.get(artifact_id.hex)
        if manifest is not None and manifest.kind == "scientist.decision_packet":
            return artifact_id
    return None


def _normalize_archive_path(path: Path) -> Path:
    suffixes = path.suffixes
    if len(suffixes) >= 3 and suffixes[-3:] == [".polisyos-audit", ".tar", ".gz"]:
        return path
    if len(suffixes) >= 2 and suffixes[-2:] == [".tar", ".gz"]:
        return path.with_name(path.name.replace(".tar.gz", ".polisyos-audit.tar.gz"))
    if path.suffix == ".tar":
        return path.with_suffix(".polisyos-audit.tar.gz")
    if path.suffix == ".gz":
        return path.with_name(path.name.replace(".gz", ".polisyos-audit.tar.gz"))
    return Path(f"{path}.polisyos-audit.tar.gz")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, default=_json_default),
        encoding="utf-8",
    )


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return str(value)


def _compute_file_checksums(
    root: Path,
    *,
    exclude: set[str],
) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if rel in exclude:
            continue
        checksums[rel] = _sha256_path(path)
    return checksums


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksums(path: Path, checksums: dict[str, str]) -> None:
    lines = [f"{sha}  {rel}" for rel, sha in sorted(checksums.items(), key=lambda item: item[0])]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
