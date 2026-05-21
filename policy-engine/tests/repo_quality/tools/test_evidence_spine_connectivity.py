from __future__ import annotations

import json
from pathlib import Path

from tools.quality.validation import check_evidence_spine_connectivity as checker


SCENARIO_CONTRACT_ID = "scenario-evidence-contract:ukraine_msme_wartime_credit_support:v1"
DATA_REQ = "scenario:ukraine_msme_wartime_credit_support:data:production_msme_panel"
LEGAL_REQ = "scenario:ukraine_msme_wartime_credit_support:legal:msme_credit"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _scenario_contract() -> dict[str, object]:
    return {
        "schema_version": "policyos.scenario_evidence_contract.v1",
        "contract_id": SCENARIO_CONTRACT_ID,
        "requirements": [
            {"requirement_id": DATA_REQ, "domain": "data"},
            {"requirement_id": LEGAL_REQ, "domain": "legal"},
        ],
    }


def _bundle_dir(tmp_path: Path, *, fabric_contract_id: str | None) -> Path:
    bundle_dir = tmp_path / "bundle"
    _write_json(
        bundle_dir / "request.sanitized.json",
        {
            "request": "Evaluate Ukraine MSME wartime credit support.",
            "context": {"scenario_evidence_contract": _scenario_contract()},
        },
    )
    _write_json(
        bundle_dir / "bundle.json",
        {
            "schema_version": "policyos.canary_evidence.v1",
            "command": {
                "scenario_evidence_contract_id": SCENARIO_CONTRACT_ID,
                "scenario_evidence_contract": _scenario_contract(),
            },
            "files": {
                "quality_evidence": {
                    "fabric_retrieval_trace": (
                        "quality_evidence/fabric_retrieval_trace.json"
                    ),
                    "normative_evidence": "quality_evidence/normative_evidence.json",
                }
            },
        },
    )
    _write_json(
        bundle_dir / "quality_evidence" / "fabric_retrieval_trace.json",
        {
            "schema_version": "polisyos.fabric.SourceSelectionTrace.v1",
            "scenario_evidence_contract_id": fabric_contract_id,
            "production_data_contract_binding_report": {
                "scenario_contract_id": SCENARIO_CONTRACT_ID,
                "scenario_binding_findings": [
                    {
                        "requirement_id": DATA_REQ,
                        "status": "blocked",
                        "expected_family": "production_msme_panel",
                    }
                ],
            },
        },
    )
    _write_json(
        bundle_dir / "quality_evidence" / "normative_evidence.json",
        {
            "schema_version": "polisyos.lex.NormativeApplicabilityReport.v1",
            "scenario_evidence_contract_id": SCENARIO_CONTRACT_ID,
            "legal_requirements": [{"requirement_id": LEGAL_REQ}],
            "query_normalization_report": {
                "legal_requirements": [{"requirement_id": LEGAL_REQ}]
            },
        },
    )
    return bundle_dir


def _failure_codes(report: dict[str, object]) -> set[str]:
    return {
        str(finding["code"])
        for finding in report["findings"]  # type: ignore[index]
        if isinstance(finding, dict) and finding.get("status") == "fail"
    }


def test_connectivity_checker_flags_dropped_contract_id(tmp_path: Path) -> None:
    bundle_dir = _bundle_dir(tmp_path, fabric_contract_id=None)

    report = checker.inspect_bundle(bundle_dir)

    assert report["status"] == "fail"
    assert _failure_codes(report) == {"evidence_spine_contract_dropped"}
    assert report["graph"]["status"] == "fail"  # type: ignore[index]
    assert report["graph"]["findings"][0]["artifact_ref"] == (  # type: ignore[index]
        "quality_evidence/fabric_retrieval_trace.json"
    )


def test_connectivity_checker_accepts_complete_synthetic_bundle(tmp_path: Path) -> None:
    bundle_dir = _bundle_dir(tmp_path, fabric_contract_id=SCENARIO_CONTRACT_ID)

    report = checker.inspect_bundle(bundle_dir)

    assert report["status"] == "pass"
    assert report["findings"] == []
    assert report["graph"]["summary"]["node_count"] == 3  # type: ignore[index]


def test_connectivity_checker_writes_json_output(tmp_path: Path) -> None:
    bundle_dir = _bundle_dir(tmp_path, fabric_contract_id=None)
    output = tmp_path / "evidence_spine_connectivity.json"

    exit_code = checker.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle_dir),
            "--json-output",
            str(output),
        ]
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["schema_version"] == "policyos.evidence_spine_connectivity_check.v1"
    assert payload["status"] == "fail"
    assert _failure_codes(payload) == {"evidence_spine_contract_dropped"}


def test_connectivity_checker_require_passing_returns_two_on_fail(tmp_path: Path) -> None:
    bundle_dir = _bundle_dir(tmp_path, fabric_contract_id=None)

    exit_code = checker.main(
        [
            "--repo-root",
            str(Path.cwd()),
            "--bundle-dir",
            str(bundle_dir),
            "--require-passing",
        ]
    )

    assert exit_code == 2
