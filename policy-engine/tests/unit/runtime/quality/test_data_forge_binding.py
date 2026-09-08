from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime

import pytest

from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
from polisyos.data_forge.kernel.snapshot import finalize_snapshot
from polisyos.runtime.quality.data_forge_binding import (
    DATA_FORGE_SNAPSHOT_BINDING_SCHEMA_VERSION,
    REQUIRED_DATA_FORGE_SNAPSHOT_ROLES,
    normalize_data_forge_snapshot_binding_report,
    official_data_forge_snapshot_for_claim,
)
from polisyos.runtime.quality.scorecard import build_quality_scorecard, normalize_quality_evidence


@pytest.fixture
def recorded_panel_owner(tmp_path, monkeypatch):
    """Create a small owner cassette; this is never a canonical rate population."""
    import duckdb

    from polisyos.core import artifacts
    from polisyos.runtime.quality import data_forge_binding as owner

    bundle = tmp_path / "calibration_bundle_v1"
    bundle.mkdir()
    parquet = bundle / "observation_panel_monthly.parquet"
    with duckdb.connect() as connection:
        connection.execute(
            "CREATE TABLE observations(entity_id VARCHAR, period_start DATE, "
            "observed_value DOUBLE, family VARCHAR, metric_id VARCHAR)"
        )
        connection.executemany(
            "INSERT INTO observations VALUES (?, ?, ?, ?, ?)",
            [
                (entity, f"2018-{month:02d}-01", float(index * 10 + month),
                 "budget_flows", "amount")
                for index, entity in enumerate(("alpha", "beta", "gamma"))
                for month in range(5, 9)
            ],
        )
        connection.execute("COPY observations TO ? (FORMAT PARQUET)", [str(parquet)])
    manifest = bundle / "calibration_bundle_manifest.json"
    manifest.write_text(json.dumps({
        "artifact_name": manifest.name,
        "outputs": {parquet.name: {
            "path": f"/recorded/owner/{parquet.name}",
            "sha256": hashlib.sha256(parquet.read_bytes()).hexdigest(),
            "size_bytes": parquet.stat().st_size,
        }},
        "metrics": {"families_present": ["budget_flows"]},
        "validation": [],
    }))
    monkeypatch.setattr(owner, "_recorded_panel_bundle_dir", lambda: bundle, raising=False)
    return owner, artifacts.FileSystemCAS(tmp_path / "cas"), parquet, manifest


def _recorded_recipe(owner):
    return owner.RecordedPanelRecipe(
        entity_ids=("alpha", "beta", "gamma"),
        period_start="2018-05-01", period_end="2018-08-01", period_count=4,
        treatment=(1, 0, 0), time_treatment=2,
    )


def _produce_recorded(recorded_panel_owner):
    owner, store, _, _ = recorded_panel_owner
    return owner.produce_recorded_panel_method_input(
        store=store, method_fqn="causal.inference.synthetic_control@1.0.0",
        recipe=_recorded_recipe(owner),
    )


def test_recorded_panel_method_input_roundtrips_measured_and_assumed_fields(recorded_panel_owner):
    owner, store, parquet, manifest = recorded_panel_owner
    result = _produce_recorded(recorded_panel_owner)
    verified = owner.verify_recorded_panel_method_input(
        store=store, binding_receipt_ref=result.binding_receipt_ref,
    )
    assert verified == result
    assert result.contract_payload["outcome"] == [
        [5.0, 6.0, 7.0, 8.0], [15.0, 16.0, 17.0, 18.0], [25.0, 26.0, 27.0, 28.0],
    ]
    receipt = result.receipt
    assert receipt.source_sha256 == hashlib.sha256(parquet.read_bytes()).hexdigest()
    assert receipt.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert receipt.measured_fields == ("outcome", "unit_ids", "time_index")
    assert receipt.assumed_fields == ("treatment", "time_treatment")
    assert receipt.decision_grade == "descriptive_only"
    assert receipt.causal_identification_established is False


def test_recorded_panel_source_mutation_invalidates_cached_extraction(recorded_panel_owner):
    owner, _, parquet, _ = recorded_panel_owner
    _produce_recorded(recorded_panel_owner)
    parquet.write_bytes(parquet.read_bytes() + b"source mutation")
    with pytest.raises(owner.MeasurementRootBindingError, match="source_hash_mismatch"):
        _produce_recorded(recorded_panel_owner)


def test_recorded_panel_manifest_mutation_invalidates_existing_receipt(recorded_panel_owner):
    owner, store, _, manifest = recorded_panel_owner
    original = _produce_recorded(recorded_panel_owner)
    payload = json.loads(manifest.read_text())
    payload["metrics"]["custody_epoch"] = "changed"
    manifest.write_text(json.dumps(payload))
    with pytest.raises(owner.MeasurementRootBindingError, match="manifest_hash_mismatch"):
        owner.verify_recorded_panel_method_input(
            store=store, binding_receipt_ref=original.binding_receipt_ref,
        )
    refreshed = _produce_recorded(recorded_panel_owner)
    assert refreshed.receipt.manifest_sha256 != original.receipt.manifest_sha256
    assert refreshed.binding_receipt_ref != original.binding_receipt_ref


def test_recorded_panel_data_only_recipe_growth_uses_real_source_values(recorded_panel_owner):
    owner, store, _, _ = recorded_panel_owner
    original = _produce_recorded(recorded_panel_owner)
    recipe = _recorded_recipe(owner).model_copy(update={
        "entity_ids": ("gamma", "alpha"), "treatment": (0, 1),
    })
    changed = owner.produce_recorded_panel_method_input(
        store=store, method_fqn=original.receipt.method_fqn, recipe=recipe,
    )
    assert changed.contract_payload["outcome"] == [
        original.contract_payload["outcome"][2], original.contract_payload["outcome"][0],
    ]
    assert changed.receipt.source_sha256 == original.receipt.source_sha256
    assert changed.receipt.selected_rows_sha256 != original.receipt.selected_rows_sha256
    assert owner.verify_recorded_panel_method_input(
        store=store, binding_receipt_ref=changed.binding_receipt_ref,
    ) == changed


def test_recorded_panel_binding_ref_kind_is_consumed(recorded_panel_owner):
    owner, store, _, _ = recorded_panel_owner
    result = _produce_recorded(recorded_panel_owner)
    wrong_ref = result.binding_receipt_ref.model_copy(update={"kind": "unrelated.document"})
    with pytest.raises(owner.MeasurementRootBindingError, match="artifact_identity_mismatch"):
        owner.verify_recorded_panel_method_input(store=store, binding_receipt_ref=wrong_ref)


def test_recorded_panel_registered_method_does_not_repeat_discovery(recorded_panel_owner, monkeypatch):
    from polisyos.foundry import methods

    owner, store, _, _ = recorded_panel_owner
    _produce_recorded(recorded_panel_owner)
    bootstrap_calls = []
    monkeypatch.setattr(methods, "ensure_all_methods_registered", lambda: bootstrap_calls.append(True))
    result = _produce_recorded(recorded_panel_owner)
    assert owner.verify_recorded_panel_method_input(
        store=store, binding_receipt_ref=result.binding_receipt_ref,
    ) == result
    assert bootstrap_calls == []


def test_recorded_panel_receipt_manifest_has_observation_ancestry(recorded_panel_owner):
    _, store, _, _ = recorded_panel_owner
    result = _produce_recorded(recorded_panel_owner)
    manifest = store.get_manifest(result.binding_receipt_ref.artifact_id)
    assert [(str(item.artifact_id), item.role) for item in manifest.inputs] == [
        (str(result.observational_data_ref.artifact_id), "observational_data"),
    ]


@pytest.mark.parametrize("wrong_schema_artifact", ["root", "receipt"])
def test_recorded_panel_actual_manifest_schema_is_consumed(
    recorded_panel_owner, tmp_path, wrong_schema_artifact,
):
    from polisyos.core import artifacts, canon

    owner, _, _, _ = recorded_panel_owner
    result = _produce_recorded(recorded_panel_owner)
    alternate_store = artifacts.FileSystemCAS(tmp_path / "wrong-schema-cas")
    alternate_store.put_json(result.contract_payload, artifacts.PutOptions(
        kind=result.observational_data_ref.kind, media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=("unrelated.schema.v1" if wrong_schema_artifact == "root"
                  else owner.WORKSPACE_RECORDED_PANEL_SCHEMA_VERSION), version="2.0",
        ),
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    receipt_ref = alternate_store.put_json(result.receipt.model_dump(mode="json"),
        artifacts.PutOptions(
            kind=result.binding_receipt_ref.kind, media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=("unrelated.schema.v1" if wrong_schema_artifact == "receipt"
                      else owner.RECORDED_PANEL_BINDING_SCHEMA_VERSION), version="1.0",
            ),
            inputs=[artifacts.InputRef(
                artifact_id=result.observational_data_ref.artifact_id, role="observational_data",
            )],
        ), canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    with pytest.raises(owner.MeasurementRootBindingError, match="artifact_identity_mismatch"):
        owner.verify_recorded_panel_method_input(
            store=alternate_store, binding_receipt_ref=receipt_ref,
        )


def test_recorded_panel_fabricated_values_are_refused_with_all_markers(recorded_panel_owner):
    from polisyos.core import artifacts, canon

    owner, store, _, _ = recorded_panel_owner
    original = _produce_recorded(recorded_panel_owner)
    fabricated = copy.deepcopy(original.contract_payload)
    fabricated["outcome"][0][0] = 987654.0
    root_manifest = store.get_manifest(original.observational_data_ref.artifact_id)
    fake_ref = store.put_json(fabricated, artifacts.PutOptions(
        kind="ir.observational_data", media_type="application/json",
        schema=root_manifest.artifact_schema, producer=root_manifest.producer,
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    receipt = original.receipt.model_dump(mode="json")
    receipt["observational_data_ref"] = fake_ref.model_dump(mode="json")
    receipt_manifest = store.get_manifest(original.binding_receipt_ref.artifact_id)
    fake_receipt_ref = store.put_json(receipt, artifacts.PutOptions(
        kind=original.binding_receipt_ref.kind, media_type="application/json",
        schema=receipt_manifest.artifact_schema, producer=receipt_manifest.producer,
        inputs=[artifacts.InputRef(artifact_id=fake_ref.artifact_id, role="observational_data")],
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    with pytest.raises(owner.MeasurementRootBindingError, match="extraction_mismatch"):
        owner.verify_recorded_panel_method_input(store=store, binding_receipt_ref=fake_receipt_ref)


def test_recorded_panel_novel_entities_and_unknown_owner_fail_closed(recorded_panel_owner, tmp_path):
    owner, store, parquet, manifest = recorded_panel_owner
    recipe = _recorded_recipe(owner).model_copy(update={"entity_ids": ("absent", "beta", "gamma")})
    with pytest.raises(owner.MeasurementRootBindingError, match="incomplete_recorded_panel"):
        owner.produce_recorded_panel_method_input(
            store=store, method_fqn="causal.inference.synthetic_control@1.0.0", recipe=recipe,
        )
    counterfeit = tmp_path / "counterfeit"
    counterfeit.mkdir()
    (counterfeit / parquet.name).write_bytes(parquet.read_bytes())
    (counterfeit / manifest.name).write_bytes(manifest.read_bytes())
    with pytest.raises(owner.MeasurementRootBindingError, match="unrecognized_recorded_source_owner"):
        owner.produce_recorded_panel_method_input(
            store=store, method_fqn="causal.inference.synthetic_control@1.0.0",
            source=owner.RecordedPanelSource(
                parquet_path=counterfeit / parquet.name,
                manifest_path=counterfeit / manifest.name,
            ), recipe=_recorded_recipe(owner),
        )


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
