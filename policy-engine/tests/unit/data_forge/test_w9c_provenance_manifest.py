# ruff: noqa: S101

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
from polisyos.data_forge.kernel.snapshot import finalize_snapshot
from polisyos.data_forge import (
    DATA_FORGE_PROVENANCE_MANIFEST_FILE,
    load_snapshot_provenance_manifest,
)


def _cas(char: str) -> str:
    return "cas://sha256/" + char * 64


def test_finalize_writes_provenance_manifest_and_answers_claim_snapshot(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "snapshot-2026-05-24"
    roles = {
        "lex": ("legal", "1"),
        "datasets": ("catalog", "2"),
        "academic": ("academic", "3"),
        "ukraine": ("domain", "4"),
    }
    for pipeline, (role, char) in roles.items():
        artifact = snapshot_root / pipeline / f"{pipeline}.jsonl"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(json.dumps({"pipeline": pipeline}) + "\n", encoding="utf-8")
        write_publish_manifest(
            manifest_path=snapshot_root / pipeline / "publish" / "manifest.json",
            pipeline=pipeline,
            artifacts=(artifact,),
            published_at="2026-05-24T08:30:00+00:00",
            extra={
                "corpus_id": f"corpus-{role}",
                "builder_revision": "git:policyos-w9c-test",
                "lineage_refs": [_cas(char), f"event://source/{role}/harvest"],
                "transform_lineage": [
                    {
                        "step_id": f"{pipeline}.normalize",
                        "operation": "normalize",
                        "input_refs": [_cas(char)],
                        "output_refs": [f"artifact://data-forge/{role}/normalized"],
                        "code_ref": "git:policyos-w9c-test",
                        "config_ref": _cas("9"),
                    }
                ],
                "claim_requirement_bindings": [
                    {
                        "claim_id": f"claim-{role}",
                        "requirement_id": f"req-{role}",
                        "requirement_kind": "data_source",
                        "authority_level": "closeout",
                        "time_role": "publication_time",
                    }
                ],
            },
        )

    finalize_snapshot(
        snapshot_root,
        update_latest_symlink=False,
        pipelines=("lex", "datasets", "academic", "ukraine"),
    )

    manifest_path = snapshot_root / DATA_FORGE_PROVENANCE_MANIFEST_FILE
    manifest = load_snapshot_provenance_manifest(manifest_path)
    answer = manifest.official_snapshot_for_claim(
        claim_id="claim-catalog",
        requirement_id="req-catalog",
    )

    assert manifest_path.is_file()
    assert answer.status == "satisfied"
    assert answer.corpus_id == "corpus-catalog"
    assert answer.data_hash.startswith("sha256:")
    assert answer.creation_time == "2026-05-24T08:30:00+00:00"
    assert answer.builder_revision == "git:policyos-w9c-test"
    assert answer.transform_lineage[0].operation == "normalize"

    binding = json.loads(
        (snapshot_root / "data_forge_snapshot_binding.json").read_text(encoding="utf-8")
    )
    assert all(
        row["provenance_manifest_ref"].startswith("cas://sha256/")
        for row in binding["bindings"]
    )
    assert {row["corpus_id"] for row in binding["bindings"]} == {
        "corpus-legal",
        "corpus-catalog",
        "corpus-academic",
        "corpus-domain",
    }


def test_provenance_manifest_missing_claim_returns_typed_not_found(
    tmp_path: Path,
) -> None:
    snapshot_root = tmp_path / "snapshot-2026-05-24"
    artifact = snapshot_root / "datasets" / "datasets.jsonl"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"pipeline": "datasets"}) + "\n", encoding="utf-8")
    write_publish_manifest(
        manifest_path=snapshot_root / "datasets" / "publish" / "manifest.json",
        pipeline="datasets",
        artifacts=(artifact,),
        published_at="2026-05-24T08:30:00+00:00",
        extra={
            "corpus_id": "corpus-catalog",
            "builder_revision": "git:policyos-w9c-test",
            "lineage_refs": [_cas("2")],
            "transform_lineage": [
                {
                    "step_id": "datasets.publish",
                    "operation": "publish",
                    "output_refs": ["artifact://data-forge/catalog/published"],
                }
            ],
            "claim_requirement_bindings": [
                {
                    "claim_id": "claim-catalog",
                    "requirement_id": "req-catalog",
                    "requirement_kind": "data_source",
                    "authority_level": "closeout",
                    "time_role": "publication_time",
                }
            ],
        },
    )
    finalize_snapshot(
        snapshot_root,
        update_latest_symlink=False,
        pipelines=("datasets",),
    )

    manifest = load_snapshot_provenance_manifest(
        snapshot_root / DATA_FORGE_PROVENANCE_MANIFEST_FILE
    )
    answer = manifest.official_snapshot_for_claim(claim_id="claim-missing")

    assert answer.status == "not_found"
    assert answer.claim_id == "claim-missing"
    assert answer.snapshot_ref is None
