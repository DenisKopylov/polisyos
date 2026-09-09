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
        store=store, method_fqn="causal.inference.synthetic_control@2.0.0",
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


def test_recorded_measurement_root_does_not_alias_its_materialized_method_dto(recorded_panel_owner):
    """One payload cannot stand for both the root and a separately governed DTO."""
    from polisyos.core import artifacts, canon

    owner, store, _, _ = recorded_panel_owner
    bound = _produce_recorded(recorded_panel_owner)
    method_ref = store.put_json(bound.contract_payload, artifacts.PutOptions(
        kind="foundry.ukraine_method_input", media_type="application/json",
        schema=artifacts.SchemaInfo(name=bound.contract_target["contract_id"], version="1.0"),
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    assert bound.observational_data_ref.artifact_id != method_ref.artifact_id
    assert store.get_manifest(method_ref.artifact_id).kind == method_ref.kind
    assert store.get_manifest(bound.observational_data_ref.artifact_id).kind == (
        bound.observational_data_ref.kind
    )
    assert owner.verify_recorded_panel_method_input(
        store=store, binding_receipt_ref=bound.binding_receipt_ref,
    ) == bound


def test_causal_reader_materializes_actual_recorded_root(recorded_panel_owner):
    from types import SimpleNamespace

    from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
        _load_observational_data,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    _, store, _, _ = recorded_panel_owner
    bound = _produce_recorded(recorded_panel_owner)
    data = _load_observational_data(
        SimpleNamespace(store=store),
        ExperimentState(run_id="recorded-root-reader", observational_data_ref=bound.observational_data_ref),
        bound.receipt.method_fqn,
    )
    assert data.model_dump(mode="json") == bound.contract_payload


def test_causal_reader_cannot_treat_a_stripped_envelope_as_a_bare_dto(recorded_panel_owner):
    """Keep the envelope kind while removing its full target/payload wrapper."""
    from types import SimpleNamespace

    from polisyos.core import artifacts, canon
    from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
        _load_observational_data,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    owner, original_store, _, _ = recorded_panel_owner
    bound = _produce_recorded(recorded_panel_owner)
    store = artifacts.FileSystemCAS(original_store.root.parent / "stripped-envelope-cas")
    stripped = store.put_json(bound.contract_payload, artifacts.PutOptions(
        kind="ir.observation_method_input", media_type="application/json",
        schema=artifacts.SchemaInfo(name=owner.WORKSPACE_RECORDED_PANEL_SCHEMA_VERSION, version="3.0"),
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    with pytest.raises(ValueError):
        _load_observational_data(
            SimpleNamespace(store=store),
            ExperimentState(run_id="stripped-envelope-reader", observational_data_ref=stripped),
            bound.receipt.method_fqn,
        )


@pytest.mark.parametrize("discriminator", [
    "policyos.ir.observation.method_input_envelope.v1",
    "policyos.ir.observation.method_input_envelope.v999",
])
def test_causal_reader_recognizes_discriminator_without_other_envelope_fields(
    recorded_panel_owner, tmp_path, discriminator,
):
    from types import SimpleNamespace

    from polisyos.core import artifacts, canon
    from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
        _load_observational_data,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    bound = _produce_recorded(recorded_panel_owner)
    payload = {**bound.contract_payload, "schema_version": discriminator}
    store = artifacts.FileSystemCAS(tmp_path / "discriminator-only-envelope")
    stripped = store.put_json(payload, artifacts.PutOptions(
        kind="ir.observational_data", media_type="application/json",
        schema=artifacts.SchemaInfo(name="polisyos.ir.ObservationalData", version="1.0"),
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    with pytest.raises(ValueError):
        _load_observational_data(
            SimpleNamespace(store=store),
            ExperimentState(run_id="discriminator-only-reader", observational_data_ref=stripped),
            bound.receipt.method_fqn,
        )


@pytest.mark.parametrize("mutation", [
    "target_fqn", "target_id", "schema_version", "payload_null", "payload_empty",
    "payload_absent", "target_absent", "unexpected_authority", "ref_kind", "manifest_kind",
])
def test_recorded_envelope_content_is_consumed_by_reader_and_measurement_gate(
    recorded_panel_owner, tmp_path, mutation,
):
    """Malformed envelope content cannot stand for the complete selected DTO."""
    from types import SimpleNamespace

    from polisyos.core import artifacts, canon
    from polisyos.scientist.nodes.builtins.simulate.run_causal_evaluation import (
        _load_observational_data,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState

    owner, original_store, _, _ = recorded_panel_owner
    bound = _produce_recorded(recorded_panel_owner)
    payload = canon.from_canonical_bytes(
        original_store.get_bytes(bound.observational_data_ref.artifact_id)
    )
    if mutation == "target_fqn":
        payload["contract_target"]["contract_fqn"] = "unrelated.model"
    elif mutation == "target_id":
        payload["contract_target"]["contract_id"] = "unknown.contract.v1"
    elif mutation == "schema_version":
        payload["schema_version"] = "unrelated.envelope.v1"
    elif mutation == "payload_null":
        payload["contract_payload"] = None
    elif mutation == "payload_empty":
        payload["contract_payload"] = {}
    elif mutation == "payload_absent":
        del payload["contract_payload"]
    elif mutation == "target_absent":
        del payload["contract_target"]
    elif mutation == "unexpected_authority":
        payload["measurement_verified"] = True
    store = artifacts.FileSystemCAS(tmp_path / "mutant-envelope")
    original_manifest = original_store.get_manifest(bound.observational_data_ref.artifact_id)
    altered = store.put_json(payload, artifacts.PutOptions(
        kind=("ir.observational_data" if mutation == "manifest_kind"
              else bound.observational_data_ref.kind),
        media_type=bound.observational_data_ref.media_type,
        schema=original_manifest.artifact_schema, producer=original_manifest.producer,
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    if mutation == "ref_kind":
        altered = altered.model_copy(update={"kind": "ir.observational_data"})
    state = ExperimentState(run_id="envelope-content-refusal", observational_data_ref=altered)
    with pytest.raises(ValueError):
        _load_observational_data(SimpleNamespace(store=store), state, bound.receipt.method_fqn)
    receipt = bound.receipt.model_dump(mode="json")
    receipt["observational_data_ref"] = altered.model_dump(mode="json")
    receipt_manifest = original_store.get_manifest(bound.binding_receipt_ref.artifact_id)
    receipt_ref = store.put_json(receipt, artifacts.PutOptions(
        kind=bound.binding_receipt_ref.kind, media_type=bound.binding_receipt_ref.media_type,
        schema=receipt_manifest.artifact_schema, producer=receipt_manifest.producer,
        inputs=[artifacts.InputRef(artifact_id=altered.artifact_id, role="observational_data")],
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    with pytest.raises(owner.MeasurementRootBindingError):
        owner.verify_recorded_panel_method_input(store=store, binding_receipt_ref=receipt_ref)


def test_current_recorded_binding_refuses_prior_naked_root_epoch(recorded_panel_owner, tmp_path):
    from polisyos.core import artifacts, canon

    owner, _, _, _ = recorded_panel_owner
    bound = _produce_recorded(recorded_panel_owner)
    store = artifacts.FileSystemCAS(tmp_path / "prior-recorded-epoch")
    old_root = store.put_json(bound.contract_payload, artifacts.PutOptions(
        kind="ir.observational_data", media_type="application/json",
        schema=artifacts.SchemaInfo(
            name="policyos.gy.phase2.recorded_panel_measurement_root.v2", version="2.0",
        ),
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    old_receipt = bound.receipt.model_dump(mode="json")
    old_receipt["schema_version"] = "policyos.gy.phase2.recorded_panel_method_binding.v1"
    old_receipt["observational_data_ref"] = old_root.model_dump(mode="json")
    old_ref = store.put_json(old_receipt, artifacts.PutOptions(
        kind=bound.binding_receipt_ref.kind, media_type="application/json",
        schema=artifacts.SchemaInfo(name=old_receipt["schema_version"], version="1.0"),
        inputs=[artifacts.InputRef(artifact_id=old_root.artifact_id, role="observational_data")],
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    with pytest.raises(owner.MeasurementRootBindingError, match="artifact_identity_mismatch"):
        owner.verify_recorded_panel_method_input(store=store, binding_receipt_ref=old_ref)


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

    owner, original_store, _, _ = recorded_panel_owner
    result = _produce_recorded(recorded_panel_owner)
    alternate_store = artifacts.FileSystemCAS(tmp_path / "wrong-schema-cas")
    alternate_store.put_json(canon.from_canonical_bytes(
        original_store.get_bytes(result.observational_data_ref.artifact_id)
    ), artifacts.PutOptions(
        kind=result.observational_data_ref.kind, media_type="application/json",
        schema=artifacts.SchemaInfo(
            name=("unrelated.schema.v1" if wrong_schema_artifact == "root"
                  else owner.WORKSPACE_RECORDED_PANEL_SCHEMA_VERSION), version="3.0",
        ),
    ), canon_spec=canon.CanonSpec(forbid_floats=False))
    receipt_ref = alternate_store.put_json(result.receipt.model_dump(mode="json"),
        artifacts.PutOptions(
            kind=result.binding_receipt_ref.kind, media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=("unrelated.schema.v1" if wrong_schema_artifact == "receipt"
                      else owner.RECORDED_PANEL_BINDING_SCHEMA_VERSION), version="2.0",
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
    fabricated = canon.from_canonical_bytes(
        store.get_bytes(original.observational_data_ref.artifact_id)
    )
    fabricated["contract_payload"]["outcome"][0][0] = 987654.0
    root_manifest = store.get_manifest(original.observational_data_ref.artifact_id)
    fake_ref = store.put_json(fabricated, artifacts.PutOptions(
        kind=original.observational_data_ref.kind, media_type="application/json",
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
            store=store, method_fqn="causal.inference.synthetic_control@2.0.0", recipe=recipe,
        )
    counterfeit = tmp_path / "counterfeit"
    counterfeit.mkdir()
    (counterfeit / parquet.name).write_bytes(parquet.read_bytes())
    (counterfeit / manifest.name).write_bytes(manifest.read_bytes())
    with pytest.raises(owner.MeasurementRootBindingError, match="unrecognized_recorded_source_owner"):
        owner.produce_recorded_panel_method_input(
            store=store, method_fqn="causal.inference.synthetic_control@2.0.0",
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


def test_recorded_extraction_preserves_exact_sum_across_all_row_permutations(
    recorded_panel_owner,
):
    """The actual owner must retain values lost by order-sensitive SQL SUM."""
    import itertools
    import math
    from fractions import Fraction

    import duckdb

    owner, _, parquet, _ = recorded_panel_owner
    recipe = _recorded_recipe(owner)
    # Every permutation of the actual three source values is part of the test.
    # This is transport-only engineered cancellation, never a canonical population.
    values = (float(2**53), 1.0, -float(2**53))
    permutations = tuple(itertools.permutations(values))
    assert len(set(permutations)) == math.factorial(len(values))
    expected_value = float(round(sum(map(Fraction.from_float, values)), 6))
    expected = tuple(
        (entity, f"2018-{month:02d}-01", expected_value)
        for month in range(5, 9)
        for entity in sorted(recipe.entity_ids)
    )
    observations = []
    for ordered in permutations:
        with duckdb.connect(database=":memory:") as connection:
            connection.execute(
                "CREATE TABLE observations(entity_id VARCHAR, period_start DATE, "
                "observed_value DOUBLE, family VARCHAR, metric_id VARCHAR)"
            )
            connection.executemany(
                "INSERT INTO observations VALUES (?, ?, ?, ?, ?)",
                [
                    (entity, f"2018-{month:02d}-01", value, recipe.family, recipe.metric_id)
                    for month in range(5, 9)
                    for entity in recipe.entity_ids
                    for value in ordered
                ],
            )
            connection.execute("COPY observations TO ? (FORMAT PARQUET)", [str(parquet)])
        source_hash = hashlib.sha256(parquet.read_bytes()).hexdigest()
        actual = owner._extract_recorded_panel_rows.__wrapped__(
            str(parquet), source_hash, "controlled-direct-extraction", recipe.model_dump_json(),
        )
        observations.append((ordered, actual))
    assert len(observations) == math.factorial(len(values))
    assert all(actual == expected for _, actual in observations), observations


def test_recorded_aggregation_rounds_once_and_refuses_nonfinite_values():
    """Independent Fraction arithmetic specifies the entire finite input basis."""
    import itertools
    from fractions import Fraction

    from polisyos.runtime.quality import data_forge_binding as owner

    groups = (
        (1e308, 1e-320, -1e308),
        (float(2**53), 1.0, -float(2**53)),
        (16900852668.63, 0.0000009, -0.0000001),
        (0.0000005, 0.000001, -0.0000005),
        (-0.0000005, -0.000001, 0.0000005),
    )
    for values in groups:
        expected = float(round(sum(map(Fraction.from_float, values)), 6))
        permutations = tuple(itertools.permutations(values))
        for permutation in permutations:
            assert owner._sum_recorded_values(permutation) == expected
    for values in ((), (float("nan"),), (float("inf"),), (-float("inf"),), (1e308, 1e308)):
        with pytest.raises(owner.MeasurementRootBindingError, match=r"nonfinite|not_finite"):
            owner._sum_recorded_values(values)
