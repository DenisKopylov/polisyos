from __future__ import annotations

import json
from typing import TYPE_CHECKING

from polisyos.core.security.sbom import SBOMFormat, SBOMGenerator, SBOMMetadata, SBOMVerifier

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class _MetricsStub:
    def __init__(self) -> None:
        self.generations: list[tuple[str, str]] = []
        self.vulnerability_counts: list[tuple[str, int]] = []
        self.deployment_gates: list[str] = []

    def record_sbom_generation(self, *, source: str, outcome: str) -> None:
        self.generations.append((source, outcome))

    def record_sbom_vulnerability_count(self, *, severity: str, count: int) -> None:
        self.vulnerability_counts.append((severity, count))

    def record_sbom_deployment_gate(self, *, decision: str) -> None:
        self.deployment_gates.append(decision)


def test_sbom_verifier_allows_clean_sbom(tmp_path: Path) -> None:
    sbom_path = tmp_path / "sbom.json"
    _write_json(
        sbom_path,
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "components": [{"name": "foo", "version": "1.0.0"}],
            "vulnerabilities": [],
        },
    )

    verifier = SBOMVerifier(cvss_threshold=7.0)
    result = verifier.verify(sbom_path=sbom_path)
    assert result.allowed is True
    assert result.total_vulnerabilities == 0


def test_sbom_verifier_blocks_high_cvss(tmp_path: Path) -> None:
    sbom_path = tmp_path / "sbom.json"
    _write_json(
        sbom_path,
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "components": [{"name": "foo", "version": "1.0.0", "bom-ref": "pkg:pypi/foo@1.0.0"}],
            "vulnerabilities": [
                {
                    "id": "CVE-2024-9999",
                    "ratings": [{"severity": "critical", "score": 9.8}],
                    "affects": [{"ref": "pkg:pypi/foo@1.0.0"}],
                }
            ],
        },
    )

    verifier = SBOMVerifier(cvss_threshold=7.0)
    result = verifier.verify(sbom_path=sbom_path)
    assert result.allowed is False
    assert len(result.blocking_vulnerabilities) == 1


def test_sbom_verifier_allows_exception(tmp_path: Path) -> None:
    sbom_path = tmp_path / "sbom.json"
    _write_json(
        sbom_path,
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "components": [{"name": "foo", "version": "1.0.0", "bom-ref": "pkg:pypi/foo@1.0.0"}],
            "vulnerabilities": [
                {
                    "id": "CVE-2024-9999",
                    "ratings": [{"severity": "critical", "score": 9.8}],
                    "affects": [{"ref": "pkg:pypi/foo@1.0.0"}],
                }
            ],
        },
    )

    verifier = SBOMVerifier(cvss_threshold=7.0, allowed_cves=frozenset({"CVE-2024-9999"}))
    result = verifier.verify(sbom_path=sbom_path)
    assert result.allowed is True


def test_sbom_generator_uses_injected_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _MetricsStub()
    generator = SBOMGenerator(metrics=metrics)
    output_path = tmp_path / "sbom.json"

    monkeypatch.setattr(
        "polisyos.core.security.sbom.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )
    monkeypatch.setattr("polisyos.core.security.sbom._run_cli", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "polisyos.core.security.sbom._extract_sbom_metadata",
        lambda path, *, source, generator: SBOMMetadata(
            format=SBOMFormat.CYCLONEDX_JSON,
            schema_version="1.5",
            component_count=1,
            generator_tool=generator,
            source=source,
            sbom_hash="abc123",
        ),
    )

    metadata = generator.generate_from_lockfile(
        lockfile_path=tmp_path / "requirements.txt",
        output_path=output_path,
    )

    assert metadata.generator_tool == "cyclonedx-py"
    assert metrics.generations == [("lockfile", "success")]


def test_sbom_verifier_uses_injected_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metrics = _MetricsStub()
    sbom_path = tmp_path / "sbom.json"
    _write_json(
        sbom_path,
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.5",
            "components": [{"name": "foo", "version": "1.0.0", "bom-ref": "pkg:pypi/foo@1.0.0"}],
            "vulnerabilities": [
                {
                    "id": "CVE-2024-9999",
                    "ratings": [{"severity": "critical", "score": 9.8}],
                    "affects": [{"ref": "pkg:pypi/foo@1.0.0"}],
                }
            ],
        },
    )

    monkeypatch.setattr(
        "polisyos.core.security.sbom.get_metrics",
        lambda: (_ for _ in ()).throw(AssertionError("global metrics should not be used")),
    )

    verifier = SBOMVerifier(cvss_threshold=7.0, metrics=metrics)
    result = verifier.verify(sbom_path=sbom_path)

    assert result.allowed is False
    assert metrics.vulnerability_counts == [("critical", 1)]
    assert metrics.deployment_gates == ["deny"]
