from __future__ import annotations

# ruff: noqa: S101
from polisyos.data_forge import build_snapshot_provenance_manifest
from polisyos.runtime.quality.data_forge_binding import (
    official_data_forge_snapshot_for_claim,
)


def test_snapshot_provenance_manifest_answers_closeout_claim_binding() -> None:
    manifest = build_snapshot_provenance_manifest(
        snapshot_id="snapshot-2026-05-24",
        release_id="data-forge-release-snapshot-2026-05-24",
        generated_at="2026-05-24T12:00:00+00:00",
        bindings=[
            {
                "role": "catalog",
                "corpus_id": "corpus-msme-credit",
                "snapshot_id": "snapshot-2026-05-24",
                "snapshot_ref": "cas://sha256/" + "a" * 64,
                "release_id": "data-forge-release-snapshot-2026-05-24",
                "release_manifest_ref": "cas://sha256/" + "b" * 64,
                "manifest_ref": "cas://sha256/" + "c" * 64,
                "artifact_ids": ["cas://sha256/" + "a" * 64],
                "data_hash": "sha256:" + "d" * 64,
                "merkle_root": "sha256:" + "e" * 64,
                "creation_time": "2026-05-24T11:30:00+00:00",
                "lineage_refs": ["event://data-forge/source-harvest"],
                "quality_gates": [
                    {
                        "name": "catalog_publish_quality",
                        "status": "pass",
                        "artifact_id": "cas://sha256/" + "f" * 64,
                    }
                ],
                "builder_revision": "git:policyos-w9c",
                "transform_lineage": [
                    {
                        "step_id": "catalog.normalize",
                        "operation": "normalize",
                        "input_refs": ["event://data-forge/source-harvest"],
                        "output_refs": ["artifact://data-forge/catalog/normalized"],
                    }
                ],
                "claim_requirement_bindings": [
                    {
                        "claim_id": "claim-data",
                        "requirement_id": "req-data",
                        "requirement_kind": "data_source",
                        "authority_level": "closeout",
                        "time_role": "publication_time",
                        "supported_by": ["cas://sha256/" + "a" * 64],
                    }
                ],
            }
        ],
    )

    answer = manifest.official_snapshot_for_claim(
        claim_id="claim-data",
        requirement_id="req-data",
    )

    assert answer.status == "satisfied"
    assert answer.corpus_id == "corpus-msme-credit"
    assert answer.data_hash == "sha256:" + "d" * 64
    assert answer.builder_revision == "git:policyos-w9c"
    assert answer.transform_lineage[0].operation == "normalize"


def test_snapshot_without_provenance_manifest_ref_cannot_satisfy_closeout_authority() -> None:
    report = {
        "schema_version": "policyos.runtime.data_forge_snapshot_binding.v1",
        "snapshot_id": "snapshot-2026-05-24",
        "release_id": "data-forge-release-snapshot-2026-05-24",
        "release_manifest_ref": "cas://sha256/" + "b" * 64,
        "generated_at": "2026-05-24T12:00:00+00:00",
        "bindings": [
            {
                "role": "catalog",
                "corpus_id": "corpus-msme-credit",
                "snapshot_id": "snapshot-2026-05-24",
                "snapshot_ref": "cas://sha256/" + "a" * 64,
                "release_id": "data-forge-release-snapshot-2026-05-24",
                "release_manifest_ref": "cas://sha256/" + "b" * 64,
                "manifest_ref": "cas://sha256/" + "c" * 64,
                "artifact_ids": ["cas://sha256/" + "a" * 64],
                "data_hash": "sha256:" + "d" * 64,
                "merkle_root": "sha256:" + "e" * 64,
                "creation_time": "2026-05-24T11:30:00+00:00",
                "lineage_refs": ["event://data-forge/source-harvest"],
                "quality_gates": [
                    {
                        "name": "catalog_publish_quality",
                        "status": "pass",
                        "artifact_id": "cas://sha256/" + "f" * 64,
                    }
                ],
                "builder_revision": "git:policyos-w9c",
                "transform_lineage": [
                    {
                        "step_id": "catalog.normalize",
                        "operation": "normalize",
                        "output_refs": ["artifact://data-forge/catalog/normalized"],
                    }
                ],
                "read_api_surface": "catalog",
                "read_api_identity": "catalog@snapshot-2026-05-24",
                "runtime_event_ref": "event://data-forge/snapshot-2026-05-24/catalog/release",
                "freshness_ttl_seconds": 7776000,
                "published_at": "2026-05-24T12:00:00+00:00",
                "claim_requirement_bindings": [
                    {
                        "claim_id": "claim-data",
                        "requirement_id": "req-data",
                        "requirement_kind": "data_source",
                        "authority_level": "closeout",
                        "time_role": "publication_time",
                    }
                ],
            }
        ],
    }

    answer = official_data_forge_snapshot_for_claim(
        report,
        claim_id="claim-data",
        requirement_id="req-data",
    )

    assert answer.status == "blocked"
    assert answer.reason == "data_forge_snapshot_provenance_manifest_ref_missing"
