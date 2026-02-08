from __future__ import annotations

import hashlib
import json
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.x509 import load_pem_x509_certificate

from polisyos.core.artifacts.manifest import ArtifactManifest
from polisyos.core.canon.canon_json import to_canonical_bytes
from polisyos.core.artifacts.signing import (
    DetachedSignature,
    SignatureStatement,
    canonical_statement_bytes,
    compute_key_id,
)

from .models import StepResult, StepStatus, VerificationReport
from .safe_tar import UnsafeArchiveError, safe_extract_tar


class AuditPackageVerifier:
    """Offline verifier for portable audit package."""

    def __init__(
        self,
        *,
        trusted_keys: list[Path] | None = None,
        trusted_keys_dir: Path | None = None,
        allow_package_keys: bool = False,
        fail_unsigned: bool = False,
        require_slsa: bool = False,
    ) -> None:
        self._trusted_keys = trusted_keys or []
        self._trusted_keys_dir = trusted_keys_dir
        self._allow_package_keys = allow_package_keys
        self._fail_unsigned = fail_unsigned
        self._require_slsa = require_slsa

    def verify(self, package_path: Path) -> VerificationReport:
        report = VerificationReport(package_path=str(package_path))
        with ExitStack() as stack:
            if package_path.is_dir():
                pkg_dir = package_path
            else:
                tmp = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="polisyos-audit-verify-")))
                try:
                    safe_extract_tar(package_path, tmp)
                except UnsafeArchiveError as exc:
                    report.add_failure("UNSAFE_ARCHIVE", str(exc))
                    report.finalize()
                    return report
                pkg_dir = tmp

            index = self._load_index(pkg_dir, report)
            if index is None:
                report.finalize()
                return report

            report.run_id = str(index.get("run_id") or "unknown")
            export_profile = self._resolve_profile(pkg_dir, index)
            report.metadata["export_profile"] = export_profile

            report.package_integrity = self._verify_package_integrity(pkg_dir, index, report)
            report.cas_integrity, artifact_index = self._verify_cas_integrity(
                pkg_dir,
                report,
                export_profile=export_profile,
            )
            report.signature_verification = self._verify_signatures(
                pkg_dir,
                report,
                artifact_index=artifact_index,
                export_profile=export_profile,
            )
            report.provenance_validation = self._verify_provenance(pkg_dir, report, artifact_index)
            report.dependency_completeness = self._verify_completeness(pkg_dir, report)
            report.slsa_verification = self._verify_slsa(pkg_dir, report, artifact_index)
            report.environment = self._load_environment(pkg_dir)
            report.finalize()
            return report

    def _load_index(self, pkg_dir: Path, report: VerificationReport) -> dict[str, Any] | None:
        index_path = pkg_dir / "index.json"
        if not index_path.exists():
            report.add_failure("MISSING_INDEX", "Missing index.json", path="index.json")
            return None
        try:
            index = json.loads(index_path.read_text("utf-8"))
        except Exception as exc:
            report.add_failure("INVALID_INDEX", f"index.json is invalid: {exc}", path="index.json")
            return None
        if index.get("package_format") != "polisyos-audit-v1":
            report.add_failure(
                "PACKAGE_FORMAT",
                f"Unsupported package format: {index.get('package_format')}",
                path="index.json",
            )
            return None
        return index

    def _resolve_profile(self, pkg_dir: Path, index: dict[str, Any]) -> str:
        opts_path = pkg_dir / "metadata" / "export_opts.json"
        if opts_path.exists():
            try:
                payload = json.loads(opts_path.read_text("utf-8"))
                profile = str(payload.get("profile") or "").strip()
                if profile in {"full", "manifests_only"}:
                    return profile
            except Exception:
                pass
        profile = str(index.get("export_profile") or "").strip()
        if profile in {"full", "manifests_only"}:
            return profile
        return "full"

    def _verify_package_integrity(
        self,
        pkg_dir: Path,
        index: dict[str, Any],
        report: VerificationReport,
    ) -> StepResult:
        step = StepResult(step_name="Package Integrity")
        started = time.perf_counter()
        checksums_path = pkg_dir / "verification" / "checksums.sha256"
        if not checksums_path.exists():
            step.status = StepStatus.FAIL
            step.checks_failed += 1
            report.add_failure("MISSING_CHECKSUMS", "Missing checksums.sha256", path="verification/checksums.sha256")
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step

        checksums = _parse_checksums(checksums_path)
        for rel_path, expected_hash in checksums.items():
            path = pkg_dir / rel_path
            if not path.exists():
                step.checks_failed += 1
                report.add_failure("MISSING_FILE", f"Missing file {rel_path}", path=rel_path)
                continue
            actual_hash = _sha256_path(path)
            if actual_hash != expected_hash:
                step.checks_failed += 1
                report.add_failure(
                    "CHECKSUM_MISMATCH",
                    f"Checksum mismatch for {rel_path}",
                    path=rel_path,
                    expected=expected_hash,
                    actual=actual_hash,
                )
            else:
                step.checks_passed += 1

        for file_entry in index.get("files", []):
            rel = file_entry.get("path")
            expected = file_entry.get("sha256")
            if not isinstance(rel, str) or not isinstance(expected, str):
                continue
            path = pkg_dir / rel
            if not path.exists():
                step.checks_failed += 1
                report.add_failure("INDEX_FILE_MISSING", f"index file missing: {rel}", path=rel)
                continue
            actual = _sha256_path(path)
            if actual != expected:
                step.checks_failed += 1
                report.add_failure(
                    "INDEX_HASH_MISMATCH",
                    f"index hash mismatch: {rel}",
                    path=rel,
                    expected=expected,
                    actual=actual,
                )
            else:
                step.checks_passed += 1

        step = self._verify_checksum_signature(pkg_dir, report, step)
        if step.checks_failed > 0:
            step.status = StepStatus.FAIL
        elif step.checks_passed > 0 and step.checks_skipped == 0:
            step.status = StepStatus.PASS
        else:
            step.status = StepStatus.WARN
        step.duration_ms = (time.perf_counter() - started) * 1000
        return step

    def _verify_checksum_signature(
        self,
        pkg_dir: Path,
        report: VerificationReport,
        step: StepResult,
    ) -> StepResult:
        sig_path = pkg_dir / "verification" / "checksums.sha256.sig"
        if not sig_path.exists():
            step.checks_skipped += 1
            report.add_warning(
                "CHECKSUM_SIGNATURE_MISSING",
                "Package checksum signature not found",
                path="verification/checksums.sha256.sig",
            )
            return step
        try:
            sig_payload = json.loads(sig_path.read_text("utf-8"))
        except Exception as exc:
            step.checks_failed += 1
            report.add_failure("INVALID_CHECKSUM_SIGNATURE", str(exc), path=str(sig_path))
            return step
        signature_hex = sig_payload.get("signature_hex")
        key_id = sig_payload.get("key_id")
        if not isinstance(signature_hex, str) or not isinstance(key_id, str):
            step.checks_failed += 1
            report.add_failure("INVALID_CHECKSUM_SIGNATURE", "signature payload missing key_id/signature_hex")
            return step

        trusted, _ = self._load_trusted_keys(pkg_dir)
        public_key = trusted.get(key_id)
        if public_key is None:
            step.checks_failed += 1
            report.add_failure("UNTRUSTED_PACKAGE_KEY", f"Key not trusted: {key_id}")
            return step

        payload = (pkg_dir / "verification" / "checksums.sha256").read_bytes()
        try:
            public_key.verify(bytes.fromhex(signature_hex), payload)
        except InvalidSignature:
            step.checks_failed += 1
            report.add_failure("INVALID_CHECKSUM_SIGNATURE", "checksum signature verification failed")
            return step
        except Exception as exc:
            step.checks_failed += 1
            report.add_failure("INVALID_CHECKSUM_SIGNATURE", f"verification error: {exc}")
            return step

        step.checks_passed += 1
        return step

    def _verify_cas_integrity(
        self,
        pkg_dir: Path,
        report: VerificationReport,
        *,
        export_profile: str,
    ) -> tuple[StepResult, dict[str, dict[str, Path | ArtifactManifest]]]:
        step = StepResult(step_name="CAS Integrity")
        started = time.perf_counter()
        artifact_index: dict[str, dict[str, Path | ArtifactManifest]] = {}
        manifests = sorted((pkg_dir / "artifacts" / "sha256").rglob("*.manifest.json"))
        for manifest_path in manifests:
            report.artifacts_total += 1
            try:
                manifest = ArtifactManifest.model_validate_json(manifest_path.read_text("utf-8"))
            except Exception as exc:
                step.checks_failed += 1
                report.add_failure(
                    "INVALID_ARTIFACT_MANIFEST",
                    f"manifest parse error: {exc}",
                    path=str(manifest_path.relative_to(pkg_dir)),
                )
                continue
            hex_id = manifest.artifact_id.hex
            blob_path = manifest_path.with_name(f"{hex_id}.blob")
            artifact_index[hex_id] = {"manifest": manifest, "manifest_path": manifest_path, "blob_path": blob_path}

            if blob_path.exists():
                actual_sha = _sha256_path(blob_path)
                if actual_sha != hex_id:
                    step.checks_failed += 1
                    report.add_failure(
                        "CAS_INTEGRITY",
                        f"blob sha mismatch for {hex_id}",
                        path=str(blob_path.relative_to(pkg_dir)),
                        expected=hex_id,
                        actual=actual_sha,
                    )
                elif blob_path.stat().st_size != manifest.byte_size:
                    step.checks_failed += 1
                    report.add_failure(
                        "SIZE_MISMATCH",
                        f"blob size mismatch for {hex_id}",
                        path=str(blob_path.relative_to(pkg_dir)),
                    )
                elif manifest.integrity.sha256 != hex_id:
                    step.checks_failed += 1
                    report.add_failure(
                        "MANIFEST_INTEGRITY",
                        f"manifest integrity mismatch for {hex_id}",
                        path=str(manifest_path.relative_to(pkg_dir)),
                    )
                else:
                    step.checks_passed += 1
                    report.artifacts_checked += 1
            else:
                if export_profile == "manifests_only":
                    step.checks_skipped += 1
                else:
                    step.checks_failed += 1
                    report.add_failure(
                        "MISSING_BLOB",
                        f"blob missing for {hex_id}",
                        path=str(blob_path.relative_to(pkg_dir)),
                    )
        step.status = _status_from_counts(step)
        step.duration_ms = (time.perf_counter() - started) * 1000
        return step, artifact_index

    def _verify_signatures(
        self,
        pkg_dir: Path,
        report: VerificationReport,
        *,
        artifact_index: dict[str, dict[str, Path | ArtifactManifest]],
        export_profile: str,
    ) -> StepResult:
        step = StepResult(step_name="Signature Verification")
        started = time.perf_counter()
        trusted_keys, identities = self._load_trusted_keys(pkg_dir)

        sig_files = sorted((pkg_dir / "signatures" / "sha256").rglob("*.sig"))
        signed_ids: set[str] = set()
        for sig_path in sig_files:
            report.signatures_total += 1
            try:
                signature = DetachedSignature.model_validate_json(sig_path.read_text("utf-8"))
            except Exception as exc:
                step.checks_failed += 1
                report.add_failure("INVALID_SIGNATURE_FILE", str(exc), path=str(sig_path.relative_to(pkg_dir)))
                continue
            hex_id = signature.statement.artifact_id.removeprefix("sha256:")
            signed_ids.add(hex_id)
            entry = artifact_index.get(hex_id)
            if entry is None:
                step.checks_failed += 1
                report.add_failure("SIGNATURE_ORPHAN", f"signature references unknown artifact {hex_id}")
                continue
            key = trusted_keys.get(signature.key_id)
            if key is None:
                step.checks_failed += 1
                report.add_failure(
                    "UNTRUSTED_KEY",
                    f"Untrusted signing key: {signature.key_id}",
                    path=str(sig_path.relative_to(pkg_dir)),
                )
                continue
            statement = signature.statement
            manifest = entry["manifest"]
            assert isinstance(manifest, ArtifactManifest)
            manifest_path = entry["manifest_path"]
            blob_path = entry["blob_path"]
            assert isinstance(manifest_path, Path)
            assert isinstance(blob_path, Path)

            manifest_sha = _sha256_path(manifest_path)
            if statement.manifest_sha256 != manifest_sha:
                step.checks_failed += 1
                report.add_failure("SIG_MANIFEST_MISMATCH", f"manifest hash mismatch for {hex_id}")
                continue

            if blob_path.exists():
                blob_sha = _sha256_path(blob_path)
                if statement.blob_sha256 != blob_sha:
                    step.checks_failed += 1
                    report.add_failure("SIG_BLOB_MISMATCH", f"blob hash mismatch for {hex_id}")
                    continue
            else:
                if export_profile == "manifests_only":
                    if statement.blob_sha256 != manifest.integrity.sha256:
                        step.checks_failed += 1
                        report.add_failure(
                            "INDIRECT_BLOB_HASH_MISMATCH",
                            f"indirect blob hash mismatch for {hex_id}",
                        )
                        continue
                    step.checks_skipped += 1
                    report.add_warning(
                        "INDIRECT_SIGNATURE_VERIFICATION",
                        f"Blob absent for {hex_id}; verified statement via manifest hash only",
                    )
                else:
                    step.checks_failed += 1
                    report.add_failure("MISSING_BLOB_FOR_SIGNATURE", f"blob missing for {hex_id}")
                    continue

            if identities:
                expected_identity = identities.get(signature.key_id)
                if (
                    expected_identity
                    and signature.signer_identity
                    and expected_identity != signature.signer_identity
                ):
                    report.add_warning(
                        "SIGNER_IDENTITY_MISMATCH",
                        f"expected {expected_identity}, got {signature.signer_identity}",
                    )

            payload = canonical_statement_bytes(
                SignatureStatement.model_validate(statement.model_dump(mode="python"))
            )
            try:
                key.verify(bytes.fromhex(signature.signature_hex), payload)
            except InvalidSignature:
                step.checks_failed += 1
                report.add_failure("INVALID_SIGNATURE", f"Ed25519 verification failed for {hex_id}")
                continue
            except Exception as exc:
                step.checks_failed += 1
                report.add_failure("INVALID_SIGNATURE", f"verification error for {hex_id}: {exc}")
                continue

            step.checks_passed += 1
            report.signatures_valid += 1

        unsigned = sorted(set(artifact_index) - signed_ids)
        if unsigned:
            if self._fail_unsigned:
                step.checks_failed += len(unsigned)
                report.add_failure("UNSIGNED_ARTIFACTS", f"Unsigned artifacts: {', '.join(unsigned[:8])}")
            else:
                report.add_warning("UNSIGNED_ARTIFACTS", f"Unsigned artifacts: {', '.join(unsigned[:8])}")
                step.checks_skipped += len(unsigned)

        step.status = _status_from_counts(step)
        step.duration_ms = (time.perf_counter() - started) * 1000
        return step

    def _load_trusted_keys(self, pkg_dir: Path) -> tuple[dict[str, Any], dict[str, str]]:
        trusted: dict[str, Any] = {}
        identities: dict[str, str] = {}

        if self._trusted_keys_dir and self._trusted_keys_dir.exists():
            for item in sorted(self._trusted_keys_dir.glob("*")):
                if not item.is_file():
                    continue
                try:
                    key = load_pem_public_key(item.read_bytes())
                    trusted[compute_key_id(key)] = key
                except Exception:
                    continue
        for path in self._trusted_keys:
            if not path.exists() or not path.is_file():
                continue
            try:
                key = load_pem_public_key(path.read_bytes())
                trusted[compute_key_id(key)] = key
            except Exception:
                continue

        if self._allow_package_keys:
            package_key_dir = pkg_dir / "signatures" / "public_keys"
            if package_key_dir.exists():
                for item in sorted(package_key_dir.glob("*.pem")):
                    if not item.is_file():
                        continue
                    try:
                        key = load_pem_public_key(item.read_bytes())
                        trusted[compute_key_id(key)] = key
                    except Exception:
                        continue
            identities_path = package_key_dir / "identities.json"
            if identities_path.exists():
                try:
                    payload = json.loads(identities_path.read_text("utf-8"))
                except Exception:
                    payload = {}
                if isinstance(payload, dict):
                    for key_id, value in payload.items():
                        if isinstance(key_id, str) and isinstance(value, str):
                            identities[key_id] = value
        return trusted, identities

    def _verify_provenance(
        self,
        pkg_dir: Path,
        report: VerificationReport,
        artifact_index: dict[str, dict[str, Path | ArtifactManifest]],
    ) -> StepResult:
        step = StepResult(step_name="Provenance Validation")
        started = time.perf_counter()
        path = pkg_dir / "provenance" / "prov.json"
        if not path.exists():
            report.add_failure("MISSING_PROVENANCE", "Missing provenance/prov.json")
            step.checks_failed += 1
            step.status = StepStatus.FAIL
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step
        try:
            prov_json = json.loads(path.read_text("utf-8"))
        except Exception as exc:
            report.add_failure("INVALID_PROVENANCE", f"prov.json parse error: {exc}")
            step.checks_failed += 1
            step.status = StepStatus.FAIL
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step

        entities = prov_json.get("entity", {})
        activities = prov_json.get("activity", {})
        agents = prov_json.get("agent", {})
        if not isinstance(entities, dict) or not isinstance(activities, dict) or not isinstance(agents, dict):
            report.add_failure("INVALID_PROVENANCE", "entity/activity/agent sections must be objects")
            step.checks_failed += 1
            step.status = StepStatus.FAIL
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step

        report.prov_entities = len(entities)
        report.prov_activities = len(activities)
        report.prov_agents = len(agents)

        for entity_id in entities:
            if entity_id.startswith("posart:"):
                hex_id = entity_id.split(":", 1)[1]
                if hex_id not in artifact_index:
                    step.checks_failed += 1
                    report.add_failure(
                        "PROV_DANGLING_ENTITY",
                        f"Entity references missing artifact: {entity_id}",
                    )
                else:
                    step.checks_passed += 1

        derivations = prov_json.get("wasDerivedFrom", {})
        edges: list[tuple[str, str]] = []
        if isinstance(derivations, dict):
            for item in derivations.values():
                if not isinstance(item, dict):
                    continue
                src = item.get("prov:generatedEntity")
                tgt = item.get("prov:usedEntity")
                if isinstance(src, str) and isinstance(tgt, str):
                    edges.append((src, tgt))
        if _has_cycle(edges):
            step.checks_failed += 1
            report.add_failure("PROV_CYCLE_DETECTED", "Cycle detected in wasDerivedFrom graph")
        else:
            step.checks_passed += 1

        used_rel = prov_json.get("used", {})
        gen_rel = prov_json.get("wasGeneratedBy", {})
        used_by_activity = {
            item.get("prov:activity")
            for item in used_rel.values()
            if isinstance(item, dict) and isinstance(item.get("prov:activity"), str)
        } if isinstance(used_rel, dict) else set()
        gen_by_activity = {
            item.get("prov:activity")
            for item in gen_rel.values()
            if isinstance(item, dict) and isinstance(item.get("prov:activity"), str)
        } if isinstance(gen_rel, dict) else set()
        for activity_id in activities:
            if activity_id not in used_by_activity and activity_id not in gen_by_activity:
                report.add_warning("ORPHAN_ACTIVITY", f"Activity has no I/O links: {activity_id}")
                step.checks_skipped += 1
            else:
                step.checks_passed += 1

        step.status = _status_from_counts(step)
        step.duration_ms = (time.perf_counter() - started) * 1000
        return step

    def _verify_completeness(self, pkg_dir: Path, report: VerificationReport) -> StepResult:
        step = StepResult(step_name="Dependency Completeness")
        started = time.perf_counter()
        path = pkg_dir / "provenance" / "prov.json"
        if not path.exists():
            step.status = StepStatus.SKIP
            step.checks_skipped = 1
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step
        try:
            prov_json = json.loads(path.read_text("utf-8"))
        except Exception:
            step.status = StepStatus.FAIL
            step.checks_failed = 1
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step
        entity_ids = set(prov_json.get("entity", {}).keys()) if isinstance(prov_json.get("entity"), dict) else set()
        deriv = prov_json.get("wasDerivedFrom", {})
        if isinstance(deriv, dict):
            for edge in deriv.values():
                if not isinstance(edge, dict):
                    continue
                used = edge.get("prov:usedEntity")
                gen = edge.get("prov:generatedEntity")
                if isinstance(used, str) and used not in entity_ids:
                    step.checks_failed += 1
                    report.add_failure("INCOMPLETE_CLOSURE", f"Missing usedEntity in closure: {used}")
                else:
                    step.checks_passed += 1
                if isinstance(gen, str) and gen not in entity_ids:
                    step.checks_failed += 1
                    report.add_failure("INCOMPLETE_CLOSURE", f"Missing generatedEntity in closure: {gen}")
                else:
                    step.checks_passed += 1
        step.status = _status_from_counts(step)
        step.duration_ms = (time.perf_counter() - started) * 1000
        return step

    def _verify_slsa(
        self,
        pkg_dir: Path,
        report: VerificationReport,
        artifact_index: dict[str, dict[str, Path | ArtifactManifest]],
    ) -> StepResult:
        step = StepResult(step_name="SLSA Verification")
        started = time.perf_counter()

        slsa_dir = pkg_dir / "slsa"
        if not slsa_dir.exists():
            step.checks_skipped += 1
            if self._require_slsa:
                step.checks_failed += 1
                report.add_failure(
                    "SLSA_MISSING",
                    "SLSA evidence is required but package has no slsa/ directory",
                    path="slsa",
                )
            else:
                report.add_warning(
                    "SLSA_MISSING",
                    "Package has no SLSA evidence (legacy package or SLSA disabled)",
                    path="slsa",
                )
            step.status = _status_from_counts(step)
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step

        attestation_path = slsa_dir / "attestation.json"
        if not attestation_path.exists():
            step.checks_failed += 1
            report.add_failure(
                "SLSA_ATTESTATION_MISSING",
                "Missing slsa/attestation.json",
                path="slsa/attestation.json",
            )
            step.status = _status_from_counts(step)
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step

        try:
            payload = json.loads(attestation_path.read_text("utf-8"))
        except Exception as exc:
            step.checks_failed += 1
            report.add_failure(
                "SLSA_ATTESTATION_INVALID_JSON",
                f"Invalid attestation JSON: {exc}",
                path="slsa/attestation.json",
            )
            step.status = _status_from_counts(step)
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step

        try:
            from polisyos.core.security.slsa.models import InTotoStatement

            statement = InTotoStatement.model_validate(payload)
        except Exception as exc:
            step.checks_failed += 1
            report.add_failure(
                "SLSA_ATTESTATION_INVALID_STRUCTURE",
                f"Attestation structure validation failed: {exc}",
                path="slsa/attestation.json",
            )
            step.status = _status_from_counts(step)
            step.duration_ms = (time.perf_counter() - started) * 1000
            return step

        step.checks_passed += 1

        root_hex = ""
        try:
            index_data = json.loads((pkg_dir / "index.json").read_text("utf-8"))
            root_ref = index_data.get("artifacts", {}).get("root_artifact_id")
            if isinstance(root_ref, str):
                root_hex = root_ref.removeprefix("sha256:")
        except Exception:
            root_hex = ""

        if not statement.subject:
            step.checks_failed += 1
            report.add_failure(
                "SLSA_SUBJECT_MISSING",
                "Attestation subject list is empty",
                path="slsa/attestation.json",
            )
        else:
            digest = statement.subject[0].digest.sha256
            if root_hex and digest != root_hex:
                step.checks_failed += 1
                report.add_failure(
                    "SLSA_SUBJECT_ROOT_MISMATCH",
                    "Subject digest does not match root_artifact_id",
                    path="slsa/attestation.json",
                    expected=root_hex,
                    actual=digest,
                )
            else:
                step.checks_passed += 1

        for dep in statement.predicate.build_definition.resolved_dependencies:
            dep_hash = dep.digest.sha256
            if dep_hash not in artifact_index:
                step.checks_failed += 1
                report.add_failure(
                    "SLSA_DEPENDENCY_MISSING",
                    f"Resolved dependency is missing from package: {dep_hash}",
                    path="slsa/attestation.json",
                )
            else:
                step.checks_passed += 1

        canonical_payload = to_canonical_bytes(
            statement.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
        canonical_sha = hashlib.sha256(canonical_payload).hexdigest()

        signature_path = slsa_dir / "signature.json"
        if not signature_path.exists():
            step.checks_skipped += 1
            if self._require_slsa:
                step.checks_failed += 1
                report.add_failure(
                    "SLSA_SIGNATURE_MISSING",
                    "SLSA signature is required but slsa/signature.json is absent",
                    path="slsa/signature.json",
                )
            else:
                report.add_warning(
                    "SLSA_SIGNATURE_MISSING",
                    "SLSA signature is absent",
                    path="slsa/signature.json",
                )
        else:
            try:
                sig_payload = json.loads(signature_path.read_text("utf-8"))
            except Exception as exc:
                step.checks_failed += 1
                report.add_failure(
                    "SLSA_SIGNATURE_INVALID_JSON",
                    f"Invalid signature payload: {exc}",
                    path="slsa/signature.json",
                )
            else:
                signature_hex = sig_payload.get("signature_hex")
                certificate_pem = sig_payload.get("certificate_pem")
                payload_sha = sig_payload.get("payload_sha256")
                if not isinstance(signature_hex, str) or not signature_hex:
                    step.checks_failed += 1
                    report.add_failure(
                        "SLSA_SIGNATURE_MISSING_FIELD",
                        "signature_hex missing in slsa/signature.json",
                        path="slsa/signature.json",
                    )
                elif isinstance(payload_sha, str) and payload_sha != canonical_sha:
                    step.checks_failed += 1
                    report.add_failure(
                        "SLSA_SIGNATURE_PAYLOAD_HASH_MISMATCH",
                        "signature payload hash mismatch",
                        path="slsa/signature.json",
                        expected=canonical_sha,
                        actual=payload_sha,
                    )
                elif not isinstance(certificate_pem, str) or not certificate_pem.strip():
                    step.checks_failed += 1
                    report.add_failure(
                        "SLSA_SIGNATURE_CERT_MISSING",
                        "certificate_pem missing in slsa/signature.json",
                        path="slsa/signature.json",
                    )
                else:
                    try:
                        certificate = load_pem_x509_certificate(certificate_pem.encode("utf-8"))
                        public_key = certificate.public_key()
                        public_key.verify(
                            bytes.fromhex(signature_hex),
                            canonical_payload,
                            ec.ECDSA(hashes.SHA256()),
                        )
                        step.checks_passed += 1
                    except InvalidSignature:
                        step.checks_failed += 1
                        report.add_failure(
                            "SLSA_SIGNATURE_INVALID",
                            "SLSA signature verification failed",
                            path="slsa/signature.json",
                        )
                    except Exception as exc:
                        step.checks_failed += 1
                        report.add_failure(
                            "SLSA_SIGNATURE_VERIFY_ERROR",
                            f"Error while verifying signature: {exc}",
                            path="slsa/signature.json",
                        )

        transparency_path = slsa_dir / "transparency_entry.json"
        if transparency_path.exists():
            try:
                transparency = json.loads(transparency_path.read_text("utf-8"))
            except Exception as exc:
                step.checks_failed += 1
                report.add_failure(
                    "SLSA_TRANSPARENCY_INVALID_JSON",
                    f"Invalid transparency entry JSON: {exc}",
                    path="slsa/transparency_entry.json",
                )
            else:
                entry_hash = transparency.get("payload_sha256")
                if isinstance(entry_hash, str) and entry_hash == canonical_sha:
                    step.checks_passed += 1
                else:
                    step.checks_failed += 1
                    report.add_failure(
                        "SLSA_TRANSPARENCY_HASH_MISMATCH",
                        "Transparency entry payload hash does not match attestation hash",
                        path="slsa/transparency_entry.json",
                        expected=canonical_sha,
                        actual=str(entry_hash),
                    )
        elif self._require_slsa:
            step.checks_failed += 1
            report.add_failure(
                "SLSA_TRANSPARENCY_MISSING",
                "Transparency entry required but slsa/transparency_entry.json is absent",
                path="slsa/transparency_entry.json",
            )
        else:
            step.checks_skipped += 1
            report.add_warning(
                "SLSA_TRANSPARENCY_MISSING",
                "Transparency entry is absent",
                path="slsa/transparency_entry.json",
            )

        step.status = _status_from_counts(step)
        step.duration_ms = (time.perf_counter() - started) * 1000
        return step

    def _load_environment(self, pkg_dir: Path) -> dict[str, Any]:
        path = pkg_dir / "metadata" / "environment.json"
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text("utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}
        simplified: dict[str, Any] = {}
        for key in ("python", "platform", "fingerprint", "jax_version"):
            if key in payload:
                simplified[key] = payload[key]
        if "python" in payload and isinstance(payload["python"], dict):
            simplified["python"] = payload["python"].get("version")
        if "os" in payload and isinstance(payload["os"], dict):
            simplified["platform"] = payload["os"].get("system")
        return simplified


def _parse_checksums(path: Path) -> dict[str, str]:
    checksums: dict[str, str] = {}
    for line in path.read_text("utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        if "  " not in text:
            continue
        sha, rel = text.split("  ", 1)
        checksums[rel] = sha
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


def _status_from_counts(step: StepResult) -> StepStatus:
    if step.checks_failed > 0:
        return StepStatus.FAIL
    if step.checks_passed > 0 and step.checks_skipped == 0:
        return StepStatus.PASS
    if step.checks_passed > 0 and step.checks_skipped > 0:
        return StepStatus.WARN
    if step.checks_skipped > 0:
        return StepStatus.SKIP
    return StepStatus.SKIP


def _has_cycle(edges: list[tuple[str, str]]) -> bool:
    graph: dict[str, list[str]] = {}
    for src, tgt in edges:
        graph.setdefault(src, []).append(tgt)
    visited: set[str] = set()
    stack: set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        stack.add(node)
        for nxt in graph.get(node, []):
            if nxt not in visited:
                if dfs(nxt):
                    return True
            elif nxt in stack:
                return True
        stack.remove(node)
        return False

    for node in graph:
        if node not in visited and dfs(node):
            return True
    return False
