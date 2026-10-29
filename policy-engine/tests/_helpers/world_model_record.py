# Shared synthetic fixtures for World Model Record consumers.

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import duckdb

from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.registry import build_default_registry_bundle
from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
from polisyos.data_forge.kernel.snapshot import finalize_snapshot
from polisyos.fabric.world import (
    WorldSnapshotFactWrite,
    WorldSnapshotNodeWrite,
    WorldSnapshotWriteRequest,
    write_world_snapshot,
)
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    FabricWorldRef,
    SkgCausalPriorRef,
    build_world_model_record,
)

SNAPSHOT_ID = "snapshot-2026-05-24"

FABRIC_PAYLOAD = {
    "agents": {
        "age": [31, 44],
        "skill_level": [1.1, 1.4],
        "income": [1200.0, 1800.0],
        "reported_income": [1000.0, 1600.0],
        "risk_aversion": [0.4, 0.6],
        "is_employed": [True, False],
        "employer_id": [0, -1],
    },
    "firms": {
        "labor_count": [12.0],
        "wage_offer": [35.0],
    },
    "government_balance": 0.0,
    "tax_rate": 0.0,
}


def _build_record(
    tmp_path: Path,
    *,
    data_snapshot_factory: Callable[[FileSystemCAS], ArtifactRef] | None = None,
):
    # Workspace artifacts must not rely on the chosen CAS creating this path.
    tmp_path.mkdir(parents=True, exist_ok=True)
    store = FileSystemCAS(tmp_path / "cas")
    _write_fabric_world_snapshot(tmp_path)
    data_snapshot_ref = (
        _data_snapshot_ref(store) if data_snapshot_factory is None else data_snapshot_factory(store)
    )
    registry_bundle = build_default_registry_bundle(store)
    model_spec = _model_spec(data_snapshot_ref, registry_bundle.bundle_ref)
    result = build_world_model_record(
        store,
        fabric_world_ref=_fabric_ref(tmp_path),
        data_forge_snapshot_binding_path=_write_data_forge_binding(tmp_path),
        data_snapshot_ref=data_snapshot_ref,
        model_spec=model_spec,
        skg_causal_prior_ref=_skg_ref(tmp_path),
        substrate_registry=_substrate_registry(),
        region_or_jurisdiction="UA-30",
        population_scope="wartime_msme",
        policy_domain="fiscal_credit",
        valid_time_scope="2026-05-24/2026-12-31",
        tx_time_scope="2026-05-24T12:00:00+00:00",
        resolution="firm_month",
        branch_mode=BranchMode.OBSERVED,
        policy_slot_ids=("agents.income", "government.balance"),
        producer_ref="test.world_model_record_builder",
        required_substrate_families=("firm_fundamentals",),
    )
    return store, result, model_spec, registry_bundle.bundle_ref


def _data_snapshot_ref(store: FileSystemCAS, *, snapshot_id: str = SNAPSHOT_ID):
    payload_ref = store.put_json(
        FABRIC_PAYLOAD,
        PutOptions(kind="fabric.world_payload", media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return store.put_json(
        DataSnapshot(
            data_ref=payload_ref,
            stats={"snapshot_id": snapshot_id},
            notes=[f"snapshot_id:{snapshot_id}"],
        ),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(payload_ref, role="data_ref")],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )


def _fabric_ref(
    tmp_path: Path,
    *,
    snapshot_id: str = SNAPSHOT_ID,
    as_of_valid_time: str | None = "2026-05-24T00:00:00+00:00",
    as_of_tx_time: str | None = "2026-05-24T12:00:00+00:00",
) -> FabricWorldRef:
    return FabricWorldRef(
        snapshot_root=str(tmp_path / "fabric-world"),
        snapshot_id=snapshot_id,
        branch="main",
        as_of_valid_time=as_of_valid_time,
        as_of_tx_time=as_of_tx_time,
        world_query_policy="default_allow_public",
        provenance_manifest_ref="cas://sha256/" + "a" * 64,
    )


def _model_spec(data_snapshot_ref: object, registry_bundle_ref: object) -> ModelSpec:
    return ModelSpec(
        model_id="model_ua_msme_world",
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
        registry_bundle_ref=str(registry_bundle_ref.artifact_id),
        calibrated=True,
        calibration_ref="sha256:" + "c" * 64,
        notes=["world_model_record_fixture"],
    )


def _put_json(store: FileSystemCAS, payload: object, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def _skg_ref(tmp_path: Path, *, snapshot_id: str = SNAPSHOT_ID) -> SkgCausalPriorRef:
    db_path = tmp_path / "academic-skg.duckdb"
    con = duckdb.connect(str(db_path))
    con.execute("CREATE OR REPLACE TABLE ac_skg_versions (version_id INTEGER)")
    con.execute("INSERT INTO ac_skg_versions VALUES (7)")
    con.close()
    from polisyos.data_forge.read_api.academic import SKGQuery

    query = SKGQuery(db_path=db_path, index_dir=tmp_path / "index")
    version_id = query.latest_skg_version_id()
    snapshot_ref = query.skg_snapshot_ref(version_id=version_id)
    return SkgCausalPriorRef(
        skg_snapshot_ref=snapshot_ref or "duckdb://missing#v0",
        skg_version_id=str(version_id),
        source_data_snapshot_id=snapshot_id,
        edge_prior_refs=("skg-edge://credit_access:firm_survival",),
        transport_score_refs=("skg-transport://credit_access:UA-30",),
        query_trace_refs=("g2-skg-query-trace:credit-access",),
    )


def _substrate_registry(
    *,
    source_id: str = "l5_measurement_registry",
    family_id: str = "firm_fundamentals",
    coverage_score: float = 0.8,
    trust_tier: str = "authoritative_partial_coverage",
    trust_cap: float = 0.85,
    identification_mode: str = "point_identified",
) -> SubstrateRegistry:
    registration = SubstrateRegistration(
        source_id=source_id,
        family_id=family_id,
        layer=SubstrateLayer.L5,
        coverage=SubstrateCoverage(
            coverage_score=coverage_score,
            coverage_kind="l5.measurement_registry.coverage_rules",
            coverage_rule_ref=f"repo://l5/measurement_registry.json#/coverage_rules/{family_id}",
        ),
        trust_tier=SubstrateTrustTier(
            tier=trust_tier,
            trust_cap=trust_cap,
            trust_multiplier=0.95,
            min_coverage=0.5,
            max_coverage=1.0,
            authority_ref=f"repo://l5/measurement_registry.json#/trust_tiers/{trust_tier}",
        ),
        identification_mode=identification_mode,
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id="ukraine_schema_v2",
            authority_ref="repo://l5/schema_regime_registry.json#/regimes/ukraine_schema_v2",
            effective_start="2022-02-01",
            boundary_buffer_periods=1,
            source_version="2.0",
        ),
        data_version="l5-calibration-d2",
        snapshot_id=SNAPSHOT_ID,
        source_snapshot_id=SNAPSHOT_ID,
        provenance_refs=(
            f"repo://l5/measurement_registry.json#/coverage_rules/{family_id}",
            f"repo://l5/identification_mode_registry.json#/{family_id}",
        ),
        authority_refs=(
            "repo://l5/measurement_registry.json",
            "repo://l5/identification_mode_registry.json",
            "repo://l5/schema_regime_registry.json",
        ),
    )
    return build_substrate_registry(
        (build_substrate_registry_entry(registration),),
        producer_ref="test.substrate_registry",
        source_catalog_refs=registration.authority_refs,
    )


def _write_data_forge_binding(tmp_path: Path, *, snapshot_id: str = SNAPSHOT_ID) -> Path:
    snapshot_root = tmp_path / snapshot_id
    artifact = snapshot_root / "academic" / "academic.jsonl"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"snapshot_id": snapshot_id}) + "\n", encoding="utf-8")
    write_publish_manifest(
        manifest_path=snapshot_root / "academic" / "publish" / "manifest.json",
        pipeline="academic",
        artifacts=(artifact,),
        published_at="2026-05-24T08:30:00+00:00",
        extra={
            "corpus_id": "corpus-academic",
            "builder_revision": "git:policyos-world-model-test",
            "lineage_refs": ["event://data-forge/academic/harvest"],
            "claim_requirement_bindings": [
                {
                    "claim_id": "claim-world-version",
                    "requirement_id": "req-world-data",
                    "requirement_kind": "data_source",
                    "authority_level": "closeout",
                    "time_role": "publication_time",
                }
            ],
        },
    )
    finalize_snapshot(snapshot_root, update_latest_symlink=False, pipelines=("academic",))
    return snapshot_root / "data_forge_snapshot_binding.json"


def _write_fabric_world_snapshot(
    tmp_path: Path,
    *,
    snapshot_id: str = SNAPSHOT_ID,
    branch: str = "main",
    node_id: str | None = "world.audit.fixture",
    include_as_of_facts: bool = True,
    fact_valid_time: str = "2026-05-24T00:00:00Z",
    fact_tx_time: str = "2026-05-24T12:00:00Z",
) -> Path:
    snapshot_root = tmp_path / "fabric-world"
    db_path = tmp_path / "fabric-world.duckdb"
    if node_id is None:
        # Emit through the owner, then corrupt only the retained file for the hostile consumer test.
        fixture_node_id = "world.audit.empty-fixture"
        record = write_world_snapshot(
            db_path,
            WorldSnapshotWriteRequest(
                snapshot_root=snapshot_root,
                snapshot_id=snapshot_id,
                branch_name=branch,
                as_of_valid_time="2026-05-24T00:00:00+00:00",
                as_of_tx_time="2026-05-24T12:00:00+00:00",
                provenance={"source": "world_model_record_fixture"},
                nodes=(
                    WorldSnapshotNodeWrite(
                        node_id=fixture_node_id,
                        kind="claim",
                        label=None,
                        artifact_id=None,
                        props_ref=None,
                    ),
                ),
                facts=(
                    WorldSnapshotFactWrite(
                        fact_id=f"fact:{snapshot_id}:empty-fixture",
                        schema_version="1.0",
                        subject_id=fixture_node_id,
                        predicate_id="world.kind",
                        object_value="claim",
                        target_id=None,
                        valid_time="2026-05-24T00:00:00Z",
                        tx_time="2026-05-24T12:00:00Z",
                        provenance_json={},
                        trust_json=None,
                        legal_json=None,
                        segment_id=f"seg:{snapshot_id}:empty-fixture",
                    ),
                ),
            ),
        )
        snapshot_db = duckdb.connect(record.snapshot_path)
        try:
            snapshot_db.execute("DELETE FROM world.world_facts")
            snapshot_db.execute("DELETE FROM world.world_nodes")
        finally:
            snapshot_db.close()
        return snapshot_root

    visible_valid_time = fact_valid_time if include_as_of_facts else "2026-05-25T00:00:00Z"
    visible_tx_time = fact_tx_time if include_as_of_facts else "2026-05-25T12:00:00Z"
    world_node = WorldSnapshotNodeWrite(
        node_id=node_id,
        kind="claim",
        label=None,
        artifact_id=None,
        props_ref=None,
    )
    facts = (
        WorldSnapshotFactWrite(
            fact_id=f"fact:{snapshot_id}:{node_id}:kind",
            schema_version="1.0",
            subject_id=node_id,
            predicate_id="world.kind",
            object_value="claim",
            target_id=None,
            valid_time=visible_valid_time,
            tx_time=visible_tx_time,
            provenance_json={},
            trust_json=None,
            legal_json=None,
            segment_id=f"seg:{snapshot_id}:kind",
        ),
        WorldSnapshotFactWrite(
            fact_id=f"fact:{snapshot_id}:{node_id}:label",
            schema_version="1.0",
            subject_id=node_id,
            predicate_id="world.label",
            object_value=f"Fixture {node_id}",
            target_id=None,
            valid_time=visible_valid_time,
            tx_time=visible_tx_time,
            provenance_json={},
            trust_json=None,
            legal_json=None,
            segment_id=f"seg:{snapshot_id}:label",
        ),
    )
    write_world_snapshot(
        db_path,
        WorldSnapshotWriteRequest(
            snapshot_root=snapshot_root,
            snapshot_id=snapshot_id,
            branch_name=branch,
            as_of_valid_time="2026-05-24T00:00:00+00:00",
            as_of_tx_time="2026-05-24T12:00:00+00:00",
            provenance={"source": "world_model_record_fixture"},
            nodes=(world_node,),
            facts=facts,
        ),
    )
    return snapshot_root
