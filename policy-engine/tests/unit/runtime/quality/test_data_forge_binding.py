from __future__ import annotations

import copy
import json
from datetime import UTC, datetime

from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
from polisyos.data_forge.kernel.snapshot import finalize_snapshot
from polisyos.runtime.quality.data_forge_binding import (
    DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION,
    REQUIRED_DATA_FORGE_SNAPSHOT_ROLES,
    normalize_data_forge_snapshot_binding_report,
    official_data_forge_snapshot_for_claim,
)
from polisyos.runtime.quality.scorecard import build_quality_scorecard, normalize_quality_evidence


def _sha(char: str) -> str:
    return "sha256:" + char * 64


def _cas(char: str) -> str:
    return "cas://sha256/" + char * 64


def _snapshot_binding(role: str, surface: str, char: str) -> dict[str, object]:
    snapshot_ref = _sha(char)
    return {
        "role": role,
        "snapshot_id": f"{role}-snapshot-2026-05-15",
        "snapshot_ref": snapshot_ref,
        "release_id": f"release-{role}-2026-05-15",
        "release_manifest_ref": _cas(char),
        "manifest_ref": _cas(char),
        "manifest_artifact_id": snapshot_ref,
        "artifact_ids": [snapshot_ref, _sha("f")],
        "merkle_root": char * 64,
        "data_hash": snapshot_ref,
        "read_api_surface": surface,
        "read_api_module": f"polisyos.data_forge.read_api.{surface}",
        "read_api_identity": f"{surface}@{role}-snapshot-2026-05-15",
        "runtime_event_ref": f"event://data-forge/{role}/2026-05-15",
        "published_at": "2026-05-15T00:00:00+00:00",
        "freshness_ttl_seconds": 60 * 60 * 24 * 14,
        "corpus_id": f"corpus-{role}",
        "provenance_manifest_ref": _cas("e"),
        "creation_time": "2026-05-15T00:00:00+00:00",
        "lineage_refs": [_cas(char), f"event://data-forge/{role}/ingest"],
        "builder_revision": "git:policyos-w9c-test",
        "transform_lineage": [
            {
                "step_id": f"{role}.normalize",
                "operation": "normalize",
                "input_refs": [_cas(char)],
                "output_refs": [snapshot_ref],
                "code_ref": "git:policyos-w9c-test",
                "config_ref": _cas("e"),
            }
        ],
        "quality_gates": [
            {
                "name": f"{role}_publish_quality",
                "status": "pass",
                "artifact_id": _sha(char),
            }
        ],
        "prov": {
            "entity": f"data-forge:{role}:snapshot",
            "activity": f"data-forge:{role}:publish",
            "agent": "team-data-forge",
        },
        "openlineage": {
            "namespace": "polisyos.data_forge",
            "job": {"name": f"{role}.publish"},
            "run": {"runId": f"run-{role}-2026-05-15"},
            "outputs": [
                {
                    "name": f"{role}-snapshot-2026-05-15",
                    "facets": {
                        "dataHash": {"sha256": char * 64},
                        "merkleRoot": {"sha256": char * 64},
                    },
                }
            ],
        },
        "claim_requirement_bindings": [
            {
                "claim_id": f"claim-{role}",
                "requirement_id": f"req-{role}-data",
                "requirement_kind": "data_source",
                "authority_level": "closeout",
                "time_role": "publication_time",
                "supported_by": [snapshot_ref],
                "lifecycle_dependency_refs": [f"event://data-forge/{role}/2026-05-15"],
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
    assert report["capability_reality_status"] == "implemented"
    assert "official_snapshot_identity" in report["runtime_authority_envelope"]["authoritative_for"]
    assert "claim_support" in report["runtime_authority_envelope"]["may_not_use_for"]
    assert report["summary"] == {
        "required_role_count": len(REQUIRED_DATA_FORGE_SNAPSHOT_ROLES),
        "bound_role_count": 4,
        "claim_requirement_binding_count": 4,
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
    assert all(binding["release_id"] for binding in report["bindings"])
    assert all(binding["merkle_root"] for binding in report["bindings"])
    assert all(binding["builder_revision"] for binding in report["bindings"])
    assert all(binding["transform_lineage"] for binding in report["bindings"])


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


def test_data_forge_snapshot_binding_requires_closeout_grade_identity_lineage_and_claims() -> None:
    payload = _complete_report()
    binding = payload["bindings"][0]
    assert isinstance(binding, dict)
    for field in (
        "release_id",
        "release_manifest_ref",
        "merkle_root",
        "data_hash",
        "prov",
        "openlineage",
        "claim_requirement_bindings",
        "runtime_event_ref",
    ):
        binding.pop(field, None)

    report = normalize_data_forge_snapshot_binding_report(
        payload,
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert {
        "data_forge_snapshot_release_id_missing",
        "data_forge_snapshot_release_manifest_ref_missing",
        "data_forge_snapshot_merkle_root_missing",
        "data_forge_snapshot_data_hash_missing",
        "data_forge_snapshot_prov_lineage_missing",
        "data_forge_snapshot_openlineage_missing",
        "data_forge_snapshot_claim_requirement_binding_missing",
        "data_forge_snapshot_runtime_event_ref_missing",
    } <= _issue_codes(report)


def test_data_forge_snapshot_binding_requires_w9c_provenance_manifest_fields() -> None:
    payload = _complete_report()
    binding = payload["bindings"][0]
    assert isinstance(binding, dict)
    for field in (
        "corpus_id",
        "provenance_manifest_ref",
        "creation_time",
        "lineage_refs",
        "builder_revision",
        "transform_lineage",
    ):
        binding.pop(field, None)

    report = normalize_data_forge_snapshot_binding_report(
        payload,
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert {
        "data_forge_snapshot_corpus_id_missing",
        "data_forge_snapshot_provenance_manifest_ref_missing",
        "data_forge_snapshot_creation_time_missing",
        "data_forge_snapshot_lineage_refs_missing",
        "data_forge_snapshot_builder_revision_missing",
        "data_forge_snapshot_transform_lineage_missing",
    } <= _issue_codes(report)


def test_data_forge_snapshot_binding_answers_official_snapshot_for_claim() -> None:
    report = normalize_data_forge_snapshot_binding_report(
        _complete_report(),
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    answer = official_data_forge_snapshot_for_claim(
        report,
        claim_id="claim-catalog",
        requirement_id="req-catalog-data",
    )
    missing = official_data_forge_snapshot_for_claim(report, claim_id="claim-missing")

    assert answer.status == "satisfied"
    assert answer.corpus_id == "corpus-catalog"
    assert answer.snapshot_ref == _sha("2")
    assert answer.builder_revision == "git:policyos-w9c-test"
    assert answer.transform_lineage[0].operation == "normalize"
    assert missing.status == "not_found"
    assert missing.snapshot_ref is None


def test_data_forge_snapshot_binding_rejects_broad_dataset_claim_requirement() -> None:
    payload = _complete_report()
    binding = payload["bindings"][1]
    assert isinstance(binding, dict)
    binding["claim_requirement_bindings"] = [
        {
            "claim_id": "claim-broad",
            "requirement_id": "dataset-bundle",
            "requirement_kind": "broad_dataset_label",
            "authority_level": "closeout",
            "time_role": "publication_time",
            "supported_by": ["datasets"],
        }
    ]

    report = normalize_data_forge_snapshot_binding_report(
        payload,
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "fail"
    assert "data_forge_snapshot_claim_requirement_broad_label" in _issue_codes(report)


def test_data_forge_finalize_emits_official_binding_consumed_by_runtime(tmp_path) -> None:
    snapshot_root = tmp_path / "snapshot-2026-05-15"
    roles = {
        "lex": ("legal", "legal"),
        "datasets": ("catalog", "catalog"),
        "academic": ("academic", "academic"),
        "ukraine": ("domain", "ukraine"),
    }
    for pipeline, (role, _surface) in roles.items():
        artifact = snapshot_root / pipeline / f"{pipeline}.jsonl"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({"pipeline": pipeline}) + "\n", encoding="utf-8")
        write_publish_manifest(
            manifest_path=snapshot_root / pipeline / "publish" / "manifest.json",
            pipeline=pipeline,
            artifacts=(artifact,),
            published_at="2026-05-15T00:00:00+00:00",
            extra={
                "claim_requirement_bindings": [
                    {
                        "claim_id": f"claim-{role}",
                        "requirement_id": f"req-{role}",
                        "requirement_kind": "data_source",
                        "authority_level": "closeout",
                        "time_role": "publication_time",
                    }
                ]
            },
        )

    finalize_snapshot(
        snapshot_root,
        update_latest_symlink=False,
        pipelines=("lex", "datasets", "academic", "ukraine"),
    )
    binding_path = snapshot_root / "data_forge_snapshot_binding.json"

    report = normalize_data_forge_snapshot_binding_report(
        json.loads(binding_path.read_text(encoding="utf-8")),
        now=datetime(2026, 5, 17, tzinfo=UTC),
    )

    assert report["status"] == "pass"
    assert {
        binding["role"]: binding["read_api_surface"] for binding in report["bindings"]
    } == {
        "legal": "legal",
        "catalog": "catalog",
        "academic": "academic",
        "domain": "ukraine",
    }
    assert report["summary"]["claim_requirement_binding_count"] == 4


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
