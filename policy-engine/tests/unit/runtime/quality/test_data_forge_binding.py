from __future__ import annotations

import copy
from datetime import UTC, datetime

from polisyos.runtime.quality.data_forge_binding import (
    DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION,
    REQUIRED_DATA_FORGE_SNAPSHOT_ROLES,
    normalize_data_forge_snapshot_binding_report,
)
from polisyos.runtime.quality.scorecard import build_quality_scorecard, normalize_quality_evidence


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _cas(char: str) -> str:
    return "cas://sha256/" + char * 64


def _snapshot_binding(role: str, surface: str, char: str) -> dict[str, object]:
    return {
        "role": role,
        "snapshot_id": f"{role}-snapshot-2026-05-15",
        "snapshot_ref": _sha(char),
        "manifest_ref": _cas(char),
        "manifest_artifact_id": _sha(char),
        "artifact_ids": [_sha(char), _sha("f")],
        "read_api_surface": surface,
        "read_api_module": f"polisyos.data_forge.read_api.{surface}",
        "published_at": "2026-05-15T00:00:00+00:00",
        "freshness_ttl_seconds": 60 * 60 * 24 * 14,
        "quality_gates": [
            {
                "name": f"{role}_publish_quality",
                "status": "pass",
                "artifact_id": _sha(char),
            }
        ],
    }


def _complete_report() -> dict[str, object]:
    return {
        "schema_version": DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION,
        "run_id": "R_quality",
        "job_id": "job-quality",
        "bindings": [
            _snapshot_binding("legal", "legal", "1"),
            _snapshot_binding("catalog", "catalog", "2"),
            _snapshot_binding("academic", "academic", "3"),
            _snapshot_binding("domain", "ukraine", "4"),
        ],
    }


def test_data_forge_snapshot_binding_covers_required_read_api_surfaces() -> None:
    report = normalize_data_forge_snapshot_binding_report(
        _complete_report(),
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "pass"
    assert report["summary"] == {
        "required_role_count": len(REQUIRED_DATA_FORGE_SNAPSHOT_ROLES),
        "bound_role_count": 4,
        "issue_count": 0,
    }
    surfaces = {
        binding["role"]: binding["read_api_surface"] for binding in report["bindings"]
    }
    assert surfaces == {
        "legal": "legal",
        "catalog": "catalog",
        "academic": "academic",
        "domain": "ukraine",
    }
    assert all(
        binding["manifest_artifact_id"].startswith("sha256:")
        for binding in report["bindings"]
    )


def test_data_forge_snapshot_binding_rejects_local_path_substitution() -> None:
    payload = _complete_report()
    binding = payload["bindings"][0]
    assert isinstance(binding, dict)
    binding["manifest_ref"] = "/opt/policyos/snapshot_manifest.json"

    report = normalize_data_forge_snapshot_binding_report(
        payload,
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert "data_forge_snapshot_manifest_local_path_substitution" in _issue_codes(report)


def test_data_forge_snapshot_binding_rejects_missing_snapshot_id() -> None:
    payload = _complete_report()
    binding = payload["bindings"][1]
    assert isinstance(binding, dict)
    binding.pop("snapshot_id")

    report = normalize_data_forge_snapshot_binding_report(
        payload,
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert "data_forge_snapshot_id_missing" in _issue_codes(report)


def test_data_forge_snapshot_binding_rejects_stale_snapshot() -> None:
    payload = _complete_report()
    binding = payload["bindings"][2]
    assert isinstance(binding, dict)
    binding["published_at"] = "2026-01-01T00:00:00+00:00"
    binding["freshness_ttl_seconds"] = 60 * 60 * 24

    report = normalize_data_forge_snapshot_binding_report(
        payload,
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert "data_forge_snapshot_stale" in _issue_codes(report)


def test_data_forge_snapshot_binding_rejects_missing_quality_gate() -> None:
    payload = _complete_report()
    binding = payload["bindings"][3]
    assert isinstance(binding, dict)
    binding["quality_gates"] = []

    report = normalize_data_forge_snapshot_binding_report(
        payload,
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert "data_forge_snapshot_quality_gate_missing" in _issue_codes(report)


def test_data_forge_snapshot_binding_preserves_runtime_blocker() -> None:
    payload = {
        "schema_version": DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION,
        "status": "blocked",
        "blockers": [
            {
                "code": "data_forge_snapshot_store_unavailable",
                "message": "Domain snapshot store is temporarily unavailable.",
                "provenance_kind": "runtime_blocker",
                "evidence_ref": _sha("a"),
                "runtime_event_ref": _sha("b"),
            }
        ],
    }

    report = normalize_data_forge_snapshot_binding_report(
        payload,
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "blocked"
    assert report["issues"] == []
    assert report["blockers"][0]["code"] == "data_forge_snapshot_store_unavailable"


def test_serious_scorecard_blocks_missing_data_forge_snapshot_binding() -> None:
    quality_evidence = normalize_quality_evidence(
        {},
        canary_kind="production",
    )

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload={"progress": {"details": {"runtime_quality_refs": {}}}},
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=quality_evidence,
    )

    assert "data_forge_snapshot_binding_missing" in _blocking_codes(scorecard)


def test_serious_scorecard_uses_data_forge_snapshot_binding_gate() -> None:
    raw_evidence = {"data_forge_snapshot_binding": _complete_report()}
    quality_evidence = normalize_quality_evidence(raw_evidence, canary_kind="production")
    mutated = copy.deepcopy(quality_evidence)
    binding_report = mutated["data_forge_snapshot_binding"]
    assert isinstance(binding_report, dict)
    first_binding = binding_report["bindings"][0]
    assert isinstance(first_binding, dict)
    first_binding["manifest_ref"] = "file:///opt/policyos/snapshot_manifest.json"

    scorecard = build_quality_scorecard(
        canary_kind="production",
        job_id="job-quality",
        run_id="R_quality",
        execution_status="completed",
        job_payload={"progress": {"details": {"runtime_quality_refs": {}}}},
        run_payload=None,
        provider_preflight={"status": "passed"},
        quality_evidence=mutated,
    )

    assert "data_forge_snapshot_manifest_local_path_substitution" in _blocking_codes(scorecard)


def _issue_codes(report: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in report.get("issues", [])
        if isinstance(issue, dict)
    }


def _blocking_codes(scorecard: dict[str, object]) -> set[str]:
    failures = scorecard.get("blocking_quality_failures")
    assert isinstance(failures, list)
    return {
        str(failure.get("code") or failure.get("gate"))
        for failure in failures
        if isinstance(failure, dict)
    }
