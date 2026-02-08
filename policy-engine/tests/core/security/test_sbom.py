from __future__ import annotations

import json
from pathlib import Path

from polisyos.core.security.sbom import SBOMVerifier


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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
