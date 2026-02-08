from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.observability import get_metrics


class SBOMFormat(str, Enum):
    CYCLONEDX_JSON = "cyclonedx-json"
    SPDX_JSON = "spdx-json"


class VulnerabilitySeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"
    UNKNOWN = "unknown"


class VulnerabilityRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cve_id: str
    severity: VulnerabilitySeverity = VulnerabilitySeverity.UNKNOWN
    cvss_score: float | None = None
    package_name: str = ""
    package_version: str = ""
    fixed_version: str | None = None
    source: str = ""


class SBOMMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: SBOMFormat = SBOMFormat.CYCLONEDX_JSON
    schema_version: str = "1.5"
    component_count: int = 0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generator_tool: str = ""
    source: str = ""
    sbom_hash: str = ""


class SBOMVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool
    metadata: SBOMMetadata
    total_vulnerabilities: int
    blocking_vulnerabilities: list[VulnerabilityRecord] = Field(default_factory=list)
    deny_reasons: list[str] = Field(default_factory=list)
    threshold_cvss: float = 7.0


class SBOMGenerationError(RuntimeError):
    """SBOM generation failed."""


class SBOMScannerError(RuntimeError):
    """Vulnerability scan failed."""


class SBOMGenerator:
    """Wraps cyclonedx/syft/grype CLI tools for reproducible SBOM pipeline."""

    def __init__(
        self,
        *,
        cyclonedx_bin: str = "cyclonedx-py",
        syft_bin: str = "syft",
        grype_bin: str = "grype",
    ) -> None:
        self._cyclonedx_bin = cyclonedx_bin
        self._syft_bin = syft_bin
        self._grype_bin = grype_bin

    def generate_from_lockfile(self, *, lockfile_path: Path, output_path: Path) -> SBOMMetadata:
        metrics = get_metrics()
        source = "lockfile"
        try:
            resolved = lockfile_path
            if lockfile_path.name == "uv.lock":
                requirements_path = output_path.parent / "requirements.txt"
                _run_cli(
                    [
                        "uv",
                        "export",
                        "--format",
                        "requirements-txt",
                        "--output-file",
                        str(requirements_path),
                    ],
                    timeout_seconds=120,
                )
                resolved = requirements_path

            _run_cli(
                [
                    self._cyclonedx_bin,
                    "requirements",
                    "--input-file",
                    str(resolved),
                    "--output-format",
                    "json",
                    "--output-file",
                    str(output_path),
                    "--schema-version",
                    "1.5",
                ],
                timeout_seconds=180,
            )
            metadata = _extract_sbom_metadata(
                output_path,
                source=source,
                generator=self._cyclonedx_bin,
            )
            metrics.record_sbom_generation(source=source, outcome="success")
            return metadata
        except Exception as exc:  # noqa: BLE001
            metrics.record_sbom_generation(source=source, outcome="error")
            raise SBOMGenerationError(str(exc)) from exc

    def generate_from_image(self, *, image_ref: str, output_path: Path) -> SBOMMetadata:
        metrics = get_metrics()
        source = "image"
        try:
            _run_cli(
                [
                    self._syft_bin,
                    image_ref,
                    "--output",
                    f"cyclonedx-json={output_path}",
                    "--source-name",
                    "polisyos",
                ],
                timeout_seconds=300,
            )
            metadata = _extract_sbom_metadata(
                output_path,
                source=image_ref,
                generator=self._syft_bin,
            )
            metrics.record_sbom_generation(source=source, outcome="success")
            return metadata
        except Exception as exc:  # noqa: BLE001
            metrics.record_sbom_generation(source=source, outcome="error")
            raise SBOMGenerationError(str(exc)) from exc

    def merge_cyclonedx(self, *, inputs: list[Path], output_path: Path) -> SBOMMetadata:
        if not inputs:
            raise SBOMGenerationError("at least one SBOM input is required")
        if len(inputs) == 1:
            output_path.write_bytes(inputs[0].read_bytes())
            return _extract_sbom_metadata(output_path, source="merged", generator="copy")

        payload: dict[str, Any] = {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "serialNumber": "",
            "version": 1,
            "metadata": {},
            "components": [],
            "vulnerabilities": [],
        }

        seen_components: set[str] = set()
        seen_vulns: set[str] = set()
        for path in inputs:
            data = json.loads(path.read_text(encoding="utf-8"))
            for comp in data.get("components", []):
                key = comp.get("bom-ref") or f"{comp.get('name')}@{comp.get('version')}"
                if key in seen_components:
                    continue
                seen_components.add(key)
                payload["components"].append(comp)

            for vuln in data.get("vulnerabilities", []):
                key = vuln.get("id") or json.dumps(vuln, sort_keys=True)
                if key in seen_vulns:
                    continue
                seen_vulns.add(key)
                payload["vulnerabilities"].append(vuln)

        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return _extract_sbom_metadata(output_path, source="merged", generator="python")

    def scan_with_grype(
        self,
        *,
        sbom_path: Path,
        output_path: Path,
        grype_db_path: Path | None = None,
    ) -> None:
        cmd = [
            self._grype_bin,
            f"sbom:{sbom_path}",
            "--output",
            "json",
            "--file",
            str(output_path),
        ]
        env = None
        if grype_db_path is not None:
            env = {"GRYPE_DB_CACHE_DIR": str(grype_db_path)}
        try:
            _run_cli(cmd, timeout_seconds=300, env=env)
        except Exception as exc:  # noqa: BLE001
            raise SBOMScannerError(str(exc)) from exc


class SBOMVerifier:
    def __init__(
        self,
        *,
        cvss_threshold: float = 7.0,
        allowed_cves: frozenset[str] | None = None,
    ) -> None:
        self._threshold = cvss_threshold
        self._allowed_cves = frozenset(item.upper() for item in (allowed_cves or frozenset()))

    def verify(
        self,
        *,
        sbom_path: Path,
        vulnerability_report_path: Path | None = None,
    ) -> SBOMVerificationResult:
        sbom_data = json.loads(sbom_path.read_text(encoding="utf-8"))
        metadata = _extract_sbom_metadata(sbom_path, source="verify", generator="verifier")

        vulnerabilities: list[VulnerabilityRecord] = []
        vulnerabilities.extend(_parse_cyclonedx_vulnerabilities(sbom_data))

        if vulnerability_report_path is not None and vulnerability_report_path.exists():
            grype_data = json.loads(vulnerability_report_path.read_text(encoding="utf-8"))
            vulnerabilities.extend(_parse_grype_vulnerabilities(grype_data))

        deduped = _dedupe_vulnerabilities(vulnerabilities)
        blocking = [
            item
            for item in deduped
            if (item.cvss_score is not None)
            and (item.cvss_score >= self._threshold)
            and (item.cve_id.upper() not in self._allowed_cves)
        ]

        metrics = get_metrics()
        for severity in VulnerabilitySeverity:
            count = sum(1 for item in deduped if item.severity == severity)
            if count:
                metrics.record_sbom_vulnerability_count(severity=severity.value, count=count)

        allowed = len(blocking) == 0
        metrics.record_sbom_deployment_gate(decision="allow" if allowed else "deny")

        reasons: list[str] = []
        if blocking:
            reasons.append(
                "SBOM_CVE_BLOCK: "
                f"{len(blocking)} vulnerability(ies) with CVSS >= {self._threshold:.1f}"
            )
            reasons.extend(
                f"{item.cve_id} {item.package_name}@{item.package_version} CVSS={item.cvss_score}"
                for item in blocking[:10]
            )

        return SBOMVerificationResult(
            allowed=allowed,
            metadata=metadata,
            total_vulnerabilities=len(deduped),
            blocking_vulnerabilities=blocking,
            deny_reasons=reasons,
            threshold_cvss=self._threshold,
        )


def _run_cli(
    cmd: list[str],
    *,
    timeout_seconds: int,
    env: dict[str, str] | None = None,
) -> None:
    merged_env = None
    if env:
        merged_env = os.environ.copy()
        merged_env.update(env)
    process = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        env=merged_env,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"command failed ({process.returncode}): {' '.join(cmd)}\n"
            f"stdout: {process.stdout.strip()}\n"
            f"stderr: {process.stderr.strip()}"
        )


def _extract_sbom_metadata(path: Path, *, source: str, generator: str) -> SBOMMetadata:
    content = path.read_bytes()
    payload = json.loads(content)
    return SBOMMetadata(
        format=SBOMFormat.CYCLONEDX_JSON,
        schema_version=str(payload.get("specVersion", "1.5")),
        component_count=len(payload.get("components", [])),
        generator_tool=generator,
        source=source,
        sbom_hash=hashlib.sha256(content).hexdigest(),
    )


def _dedupe_vulnerabilities(values: list[VulnerabilityRecord]) -> list[VulnerabilityRecord]:
    unique: dict[tuple[str, str, str], VulnerabilityRecord] = {}
    for value in values:
        key = (value.cve_id.upper(), value.package_name, value.package_version)
        if key not in unique:
            unique[key] = value
            continue
        current = unique[key]
        if current.cvss_score is None and value.cvss_score is not None:
            unique[key] = value
    return list(unique.values())


def _parse_cyclonedx_vulnerabilities(payload: dict[str, Any]) -> list[VulnerabilityRecord]:
    records: list[VulnerabilityRecord] = []
    for vuln in payload.get("vulnerabilities", []):
        vuln_id = str(vuln.get("id", "")).strip()
        if not vuln_id:
            continue

        cvss_score = None
        severity = VulnerabilitySeverity.UNKNOWN
        for rating in vuln.get("ratings", []):
            score = rating.get("score")
            if score is not None:
                try:
                    cvss_score = float(score)
                except (TypeError, ValueError):
                    cvss_score = None
            raw = str(rating.get("severity", "")).strip().lower()
            severity = _coerce_severity(raw)

        package_name = ""
        package_version = ""
        affects = vuln.get("affects", [])
        if affects:
            ref = str(affects[0].get("ref", ""))
            if "@" in ref:
                left, package_version = ref.rsplit("@", 1)
                package_name = left.split("/")[-1]

        records.append(
            VulnerabilityRecord(
                cve_id=vuln_id,
                severity=severity,
                cvss_score=cvss_score,
                package_name=package_name,
                package_version=package_version,
                source="cyclonedx",
            )
        )
    return records


def _parse_grype_vulnerabilities(payload: dict[str, Any]) -> list[VulnerabilityRecord]:
    records: list[VulnerabilityRecord] = []
    for match in payload.get("matches", []):
        vuln = match.get("vulnerability", {})
        artifact = match.get("artifact", {})

        vuln_id = str(vuln.get("id", "")).strip()
        if not vuln_id:
            continue

        cvss_score = None
        for cvss in vuln.get("cvss", []):
            metrics = cvss.get("metrics", {})
            score = metrics.get("baseScore")
            if score is None:
                continue
            try:
                cvss_score = float(score)
                break
            except (TypeError, ValueError):
                continue

        fixed_version = None
        fix = vuln.get("fix", {})
        versions = fix.get("versions", [])
        if versions:
            fixed_version = str(versions[0])

        records.append(
            VulnerabilityRecord(
                cve_id=vuln_id,
                severity=_coerce_severity(str(vuln.get("severity", "unknown")).lower()),
                cvss_score=cvss_score,
                package_name=str(artifact.get("name", "")),
                package_version=str(artifact.get("version", "")),
                fixed_version=fixed_version,
                source="grype",
            )
        )

    return records


def _coerce_severity(value: str) -> VulnerabilitySeverity:
    normalized = value.strip().lower()
    for item in VulnerabilitySeverity:
        if item.value == normalized:
            return item
    if normalized == "info":
        return VulnerabilitySeverity.NEGLIGIBLE
    return VulnerabilitySeverity.UNKNOWN


__all__ = [
    "SBOMFormat",
    "SBOMGenerationError",
    "SBOMGenerator",
    "SBOMMetadata",
    "SBOMScannerError",
    "SBOMVerificationResult",
    "SBOMVerifier",
    "VulnerabilityRecord",
    "VulnerabilitySeverity",
]
