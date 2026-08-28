from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import duckdb
import pytest

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import CompileRequest
from polisyos.core.registry import build_default_registry_bundle
from polisyos.data_forge.kernel.pipeline.manifests import write_publish_manifest
from polisyos.data_forge.kernel.snapshot import finalize_snapshot
from polisyos.fabric.world import (
    WorldSnapshotFactWrite,
    WorldSnapshotNodeWrite,
    WorldSnapshotWriteRequest,
    write_world_snapshot,
)
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.ir.analytics.interventions import (
    InterventionContext,
    NodeIntervention,
    QueryTarget,
    VariableAssignment,
    identification_plan_for_intervention,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    ConstraintRegistry,
)
from polisyos.ir.linker import link_trinity
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.registry.registry_fragments import RegistryBundle
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.quality.intervention_atom_binding import (
    build_intervention_atom_binding,
    intervention_atom_target_selector_ref,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
    register_substrate_entry,
)
from polisyos.runtime.quality.world_model_record import (
    BranchMode,
    FabricWorldRef,
    SkgCausalPriorRef,
    WorldModelRecord,
    WorldModelRecordError,
    build_world_model_record,
    consume_world_model_record_for_simulation,
    resolve_intervention_atom_world_binding,
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


def _future_substrate_registration() -> SubstrateRegistration:
    return SubstrateRegistration(
        source_id="acquisition:test_future_source",
        family_id="future_observation_family",
        layer=SubstrateLayer.L4,
        coverage=SubstrateCoverage(
            coverage_score=0.42,
            coverage_kind="acquisition_receipt.coverage",
            coverage_rule_ref="receipt://acquisition/test-future-source#coverage",
        ),
        trust_tier=SubstrateTrustTier(
            tier="weak_anchor",
            trust_cap=0.25,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref="repo://l5/measurement_registry.json#/trust_tiers/weak_anchor",
        ),
        identification_mode="bounds_only",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id="ukraine_schema_v2",
            authority_ref="repo://l5/schema_regime_registry.json#/regimes/ukraine_schema_v2",
            effective_start="2022-02-01",
            boundary_buffer_periods=1,
            source_version="2.0",
        ),
        data_version="future-source-v1",
        snapshot_id=SNAPSHOT_ID,
        source_snapshot_id=SNAPSHOT_ID,
        provenance_refs=("receipt://acquisition/test-future-source",),
        authority_refs=("repo://l5/measurement_registry.json",),
    )


def _put_json(store: FileSystemCAS, payload: object, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type="application/json"),
        canon_spec=CanonSpec(forbid_floats=False),
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


def _data_snapshot_ref(store: FileSystemCAS, *, snapshot_id: str = SNAPSHOT_ID):
    payload_ref = _put_json(store, FABRIC_PAYLOAD, kind="fabric.world_payload")
    return _put_json(
        store,
        DataSnapshot(
            data_ref=payload_ref,
            stats={"snapshot_id": snapshot_id},
            notes=[f"snapshot_id:{snapshot_id}"],
        ),
        kind="fabric.data_snapshot",
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


def _model_spec(data_snapshot_ref: object, registry_bundle_ref: object) -> ModelSpec:
    return ModelSpec(
        model_id="model_ua_msme_world",
        data_snapshot_ref=str(data_snapshot_ref.artifact_id),
        registry_bundle_ref=str(registry_bundle_ref.artifact_id),
        calibrated=True,
        calibration_ref="sha256:" + "c" * 64,
        notes=["world_model_record_fixture"],
    )


def _build_record(tmp_path: Path):
    store = FileSystemCAS(tmp_path / "cas")
    _write_fabric_world_snapshot(tmp_path)
    data_snapshot_ref = _data_snapshot_ref(store)
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


def _build_record_with_fabric_node(
    tmp_path: Path,
    *,
    node_id: str | None,
    include_as_of_facts: bool = True,
    fact_valid_time: str = "2026-05-24T00:00:00Z",
    fact_tx_time: str = "2026-05-24T12:00:00Z",
    as_of_valid_time: str | None = "2026-05-24T00:00:00+00:00",
    as_of_tx_time: str | None = "2026-05-24T12:00:00+00:00",
):
    store = FileSystemCAS(tmp_path / "cas")
    _write_fabric_world_snapshot(
        tmp_path,
        node_id=node_id,
        include_as_of_facts=include_as_of_facts,
        fact_valid_time=fact_valid_time,
        fact_tx_time=fact_tx_time,
    )
    data_snapshot_ref = _data_snapshot_ref(store)
    registry_bundle = build_default_registry_bundle(store)
    model_spec = _model_spec(data_snapshot_ref, registry_bundle.bundle_ref)
    return build_world_model_record(
        store,
        fabric_world_ref=_fabric_ref(
            tmp_path,
            as_of_valid_time=as_of_valid_time,
            as_of_tx_time=as_of_tx_time,
        ),
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


def _compile_smoke_plan(store: FileSystemCAS, model_spec: ModelSpec, registry_bundle_ref: object):
    intervention = InterventionSpec(
        intervention_id="tax_cut",
        kind="income_tax",
        target=SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all"),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"rate": Decimal("0.1")},
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_world_smoke", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(policy_id="policy_world_smoke", interventions=[intervention]),
        model_spec=model_spec,
    )
    trinity_ref = store.put_json(
        trinity,
        PutOptions(
            kind="ir.trinity_bundle",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version=trinity.schema_version),
        ),
    )
    compiled = compile_foundry(
        store,
        CompileRequest(
            input_kind="trinity",
            policy_ref=trinity_ref,
            registry_bundle_ref=registry_bundle_ref,
        ),
    )
    assert compiled.ok
    assert compiled.exec_plan_ref is not None
    return compiled.exec_plan_ref


def _atom_for_record(record: WorldModelRecord):
    intervention = InterventionSpec(
        intervention_id="credit_access_subsidy",
        kind="tax_subsidy",
        target=SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all"),
        schedule=ScheduleSpec(start_step=0, duration_steps=4),
        params={"rate": Decimal("0.20")},
        priority=1,
        target_population_type="wartime_msme",
        target_sector_ids=["manufacturing"],
        target_region_ids=["UA-30"],
    )
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="problem_ua_msme_credit", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="policy_ua_msme_credit",
            problem_frame_ref="sha256:" + "a" * 64,
            interventions=[intervention],
        ),
        model_spec=ModelSpec(model_id="model_ua_msme", data_snapshot_ref="sha256:" + "b" * 64),
    )
    linked_bundle, report = link_trinity(
        bundle,
        RegistryBundle(
            mechanisms=DEFAULT_MECHANISM_REGISTRY,
            slots=DEFAULT_SLOT_REGISTRY,
            merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
            selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
            units=DEFAULT_UNITS_REGISTRY,
            metrics=DEFAULT_METRIC_REGISTRY,
            constraints=ConstraintRegistry(constraints={}),
        ),
    )
    assert report.ok
    causal = NodeIntervention(
        assignments=(
            VariableAssignment(variable="agents.income", value_expr="income + subsidy(rate)"),
        )
    )
    return build_intervention_atom_binding(
        problem_frame_ref="sha256:" + "a" * 64,
        policy_spec_ref="sha256:" + "c" * 64,
        intervention=intervention,
        linked_intervention=linked_bundle.bindings.interventions[0],
        causal_intervention=causal,
        query_target=QueryTarget(
            outcome_variables=("firm_survival",),
            conditioning=("baseline_credit_access",),
            functional="average_treatment_effect",
        ),
        identification_plan=identification_plan_for_intervention(causal),
        causal_context=InterventionContext(
            source_domain="observed_ua_msme_panel",
            target_domain="wartime_msme",
            selection_diagram_ref=intervention_atom_target_selector_ref(intervention),
            available_data_refs=("data_snapshot:ua_msme_credit_panel",),
        ),
        world_model_record_ref=record.world_model_record_id,
        producer_ref="test.intervention_atom",
        provenance_refs=("trinity_bundle:policy_ua_msme_credit", "proof_kernel:node_do_income"),
        operator_proof_type_map={"tax_subsidy": "node"},
        estimand_metric_id="msme_survival_rate",
        estimand_unit_id="ratio",
    )


def test_world_model_record_builds_bound_global_state_and_executes_smoke(tmp_path: Path) -> None:
    store, built, model_spec, registry_bundle_ref = _build_record(tmp_path)
    exec_plan_ref = _compile_smoke_plan(store, model_spec, registry_bundle_ref)

    simulation_input = consume_world_model_record_for_simulation(built.record)
    exec_result = execute_foundry(
        store,
        simulation_input.to_execute_request(exec_plan_ref=exec_plan_ref),
    )

    assert built.record.schema_version == "policyos.runtime.world_model_record.v1"
    assert built.record.world_model_record_id.startswith("world_model_record_")
    assert built.record.content_hash.startswith("sha256:")
    assert built.record.branch_mode is BranchMode.OBSERVED
    assert built.record.substrate_registry_ref.substrate_version_id.startswith(
        "substrate_version_"
    )
    assert built.record.substrate_registry_ref.resolved_entries[0].family_id == (
        "firm_fundamentals"
    )
    assert built.record.substrate_registry_ref.resolved_entries[0].trust_tier == (
        "authoritative_partial_coverage"
    )
    assert built.bound_global_state.__class__.__name__ == "GlobalState"
    assert built.record.foundry_binding_ref.input_bindings_ref == str(
        built.input_bindings_ref.artifact_id
    )
    assert exec_result.ok is True
    assert exec_result.simulation_result_ref is not None


def test_world_model_record_content_binds_same_snapshot_and_rejects_mismatch(
    tmp_path: Path,
) -> None:
    store, built, model_spec, _registry_bundle_ref = _build_record(tmp_path)
    repeat = build_world_model_record(
        store,
        fabric_world_ref=_fabric_ref(tmp_path),
        data_forge_snapshot_binding_path=_write_data_forge_binding(tmp_path),
        data_snapshot_ref=built.data_snapshot_ref,
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

    assert repeat.record.content_hash == built.record.content_hash
    assert repeat.record.world_model_record_id == built.record.world_model_record_id

    changed_substrate = build_world_model_record(
        store,
        fabric_world_ref=_fabric_ref(tmp_path),
        data_forge_snapshot_binding_path=_write_data_forge_binding(tmp_path),
        data_snapshot_ref=built.data_snapshot_ref,
        model_spec=model_spec,
        skg_causal_prior_ref=_skg_ref(tmp_path),
        substrate_registry=_substrate_registry(coverage_score=0.7),
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

    assert changed_substrate.record.substrate_registry_ref.substrate_version_id != (
        built.record.substrate_registry_ref.substrate_version_id
    )
    assert changed_substrate.record.content_hash != built.record.content_hash

    _write_fabric_world_snapshot(tmp_path, snapshot_id="snapshot-other")
    with pytest.raises(WorldModelRecordError, match="world_substrate_version_mismatch"):
        build_world_model_record(
            store,
            fabric_world_ref=_fabric_ref(tmp_path, snapshot_id="snapshot-other"),
            data_forge_snapshot_binding_path=_write_data_forge_binding(tmp_path),
            data_snapshot_ref=built.data_snapshot_ref,
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
            policy_slot_ids=("agents.income",),
            producer_ref="test.world_model_record_builder",
            required_substrate_families=("firm_fundamentals",),
        )


def test_world_model_record_rejects_unregistered_required_substrate(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    _write_fabric_world_snapshot(tmp_path)
    data_snapshot_ref = _data_snapshot_ref(store)
    registry_bundle = build_default_registry_bundle(store)
    model_spec = _model_spec(data_snapshot_ref, registry_bundle.bundle_ref)

    with pytest.raises(WorldModelRecordError, match="substrate_entry_unresolved"):
        build_world_model_record(
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
            policy_slot_ids=("agents.income",),
            producer_ref="test.world_model_record_builder",
            required_substrate_families=("unregistered_future_family",),
        )


def test_world_model_record_consumes_free_grow_registered_substrate(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    _write_fabric_world_snapshot(tmp_path)
    data_snapshot_ref = _data_snapshot_ref(store)
    registry_bundle = build_default_registry_bundle(store)
    model_spec = _model_spec(data_snapshot_ref, registry_bundle.bundle_ref)
    base_registry = _substrate_registry()
    updated_registry = register_substrate_entry(
        base_registry,
        _future_substrate_registration(),
    )

    built = build_world_model_record(
        store,
        fabric_world_ref=_fabric_ref(tmp_path),
        data_forge_snapshot_binding_path=_write_data_forge_binding(tmp_path),
        data_snapshot_ref=data_snapshot_ref,
        model_spec=model_spec,
        skg_causal_prior_ref=_skg_ref(tmp_path),
        substrate_registry=updated_registry,
        region_or_jurisdiction="UA-30",
        population_scope="wartime_msme",
        policy_domain="fiscal_credit",
        valid_time_scope="2026-05-24/2026-12-31",
        tx_time_scope="2026-05-24T12:00:00+00:00",
        resolution="firm_month",
        branch_mode=BranchMode.OBSERVED,
        policy_slot_ids=("agents.income",),
        producer_ref="test.world_model_record_builder",
        required_substrate_families=("future_observation_family",),
    )

    assert built.record.substrate_registry_ref.substrate_version_id == (
        updated_registry.substrate_version_id
    )
    assert built.record.substrate_registry_ref.resolved_entries[0].source_id == (
        "acquisition:test_future_source"
    )
    assert built.record.substrate_registry_ref.resolved_entries[0].trust_tier == (
        "weak_anchor"
    )


def test_world_model_record_rejects_unresolved_fabric_world_snapshot(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    data_snapshot_ref = _data_snapshot_ref(store)
    registry_bundle = build_default_registry_bundle(store)
    model_spec = _model_spec(data_snapshot_ref, registry_bundle.bundle_ref)

    with pytest.raises(WorldModelRecordError, match="fabric_world_snapshot_unresolved"):
        build_world_model_record(
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
            policy_slot_ids=("agents.income",),
            producer_ref="test.world_model_record_builder",
            required_substrate_families=("firm_fundamentals",),
        )


def test_world_model_record_rejects_empty_fabric_world_snapshot(tmp_path: Path) -> None:
    with pytest.raises(WorldModelRecordError, match="fabric_world_empty"):
        _build_record_with_fabric_node(tmp_path, node_id=None)


def test_world_model_record_rejects_empty_fabric_branch_as_of_view(
    tmp_path: Path,
) -> None:
    with pytest.raises(WorldModelRecordError, match=r"fabric_world_(branch|as_of)_empty"):
        _build_record_with_fabric_node(
            tmp_path,
            node_id="world.audit.fixture",
            include_as_of_facts=False,
        )


def test_world_model_record_rejects_fabric_as_of_view_with_no_visible_rows(
    tmp_path: Path,
) -> None:
    with pytest.raises(WorldModelRecordError, match=r"fabric_world_(branch|as_of)_empty"):
        _build_record_with_fabric_node(
            tmp_path,
            node_id="world.audit.fixture",
            fact_tx_time="2026-05-25T12:00:00Z",
        )


def test_world_model_record_binds_when_all_fabric_query_modes_are_populated(
    tmp_path: Path,
) -> None:
    built = _build_record_with_fabric_node(tmp_path, node_id="world.audit.fixture")

    assert built.record.fabric_world_ref.content_query_digest is not None
    assert built.record.fabric_world_ref.content_query_row_count == 1


def test_world_model_record_hash_binds_fabric_query_content(tmp_path: Path) -> None:
    same_a = _build_record_with_fabric_node(
        tmp_path / "same-a",
        node_id="world.audit.fixture",
    )
    same_b = _build_record_with_fabric_node(
        tmp_path / "same-b",
        node_id="world.audit.fixture",
    )
    different = _build_record_with_fabric_node(
        tmp_path / "different",
        node_id="world.audit.different_fixture",
    )

    assert same_a.record.fabric_world_ref.snapshot_root != (
        same_b.record.fabric_world_ref.snapshot_root
    )
    assert same_a.record.content_hash == same_b.record.content_hash
    assert same_a.record.world_model_record_id == same_b.record.world_model_record_id
    assert same_a.record.content_hash != different.record.content_hash
    assert same_a.record.fabric_world_ref.content_query_digest != (
        different.record.fabric_world_ref.content_query_digest
    )
    assert same_a.record.fabric_world_ref.content_query_row_count == 1
    assert different.record.fabric_world_ref.content_query_row_count == 1


def test_world_model_record_rejects_unresolved_skg_prior_ref(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    _write_fabric_world_snapshot(tmp_path)
    data_snapshot_ref = _data_snapshot_ref(store)
    registry_bundle = build_default_registry_bundle(store)
    model_spec = _model_spec(data_snapshot_ref, registry_bundle.bundle_ref)
    bogus_skg_ref = SkgCausalPriorRef(
        skg_snapshot_ref="duckdb://not-the-built-skg#v999999",
        skg_version_id="999999",
        source_data_snapshot_id=SNAPSHOT_ID,
        edge_prior_refs=("skg-edge://bogus",),
        transport_score_refs=("skg-transport://bogus",),
        query_trace_refs=("g2-skg-query-trace:bogus",),
    )

    with pytest.raises(WorldModelRecordError, match="skg_prior_ref_unresolved"):
        build_world_model_record(
            store,
            fabric_world_ref=_fabric_ref(tmp_path),
            data_forge_snapshot_binding_path=_write_data_forge_binding(tmp_path),
            data_snapshot_ref=data_snapshot_ref,
            model_spec=model_spec,
            skg_causal_prior_ref=bogus_skg_ref,
            substrate_registry=_substrate_registry(),
            region_or_jurisdiction="UA-30",
            population_scope="wartime_msme",
            policy_domain="fiscal_credit",
            valid_time_scope="2026-05-24/2026-12-31",
            tx_time_scope="2026-05-24T12:00:00+00:00",
            resolution="firm_month",
            branch_mode=BranchMode.OBSERVED,
            policy_slot_ids=("agents.income",),
            producer_ref="test.world_model_record_builder",
            required_substrate_families=("firm_fundamentals",),
        )


def test_world_model_record_hash_is_location_invariant_for_local_skg_ref(
    tmp_path: Path,
) -> None:
    _store_a, built_a, _model_spec_a, _registry_a = _build_record(tmp_path / "root-a")
    _store_b, built_b, _model_spec_b, _registry_b = _build_record(tmp_path / "root-b")

    assert built_a.record.skg_causal_prior_ref.skg_snapshot_ref != (
        built_b.record.skg_causal_prior_ref.skg_snapshot_ref
    )
    assert built_a.record.content_hash == built_b.record.content_hash
    assert built_a.record.world_model_record_id == built_b.record.world_model_record_id


def test_world_model_record_resolves_n2_atom_ref_and_binds_target_slots(
    tmp_path: Path,
) -> None:
    _store, built, _built_model_spec, _registry_bundle_ref = _build_record(tmp_path)
    atom = _atom_for_record(built.record)

    resolved = resolve_intervention_atom_world_binding(atom, built.record)

    assert resolved.world_model_record_id == built.record.world_model_record_id
    assert resolved.world_model_record_content_hash == built.record.content_hash
    assert {slot.slot_id: slot.state_path for slot in resolved.target_slot_bindings} == {
        "agents.income": "agents.income",
        "government.balance": "government_balance",
    }

    one_slot_store = FileSystemCAS(tmp_path / "one-slot-cas")
    one_slot_data_snapshot_ref = _data_snapshot_ref(one_slot_store)
    one_slot_registry_bundle = build_default_registry_bundle(one_slot_store)
    one_slot = build_world_model_record(
        one_slot_store,
        fabric_world_ref=_fabric_ref(tmp_path),
        data_forge_snapshot_binding_path=_write_data_forge_binding(tmp_path),
        data_snapshot_ref=one_slot_data_snapshot_ref,
        model_spec=_model_spec(one_slot_data_snapshot_ref, one_slot_registry_bundle.bundle_ref),
        skg_causal_prior_ref=_skg_ref(tmp_path),
        substrate_registry=_substrate_registry(),
        region_or_jurisdiction="UA-30",
        population_scope="wartime_msme",
        policy_domain="fiscal_credit",
        valid_time_scope="2026-05-24/2026-12-31",
        tx_time_scope="2026-05-24T12:00:00+00:00",
        resolution="firm_month",
        branch_mode=BranchMode.OBSERVED,
        policy_slot_ids=("agents.income",),
        producer_ref="test.world_model_record_builder",
        required_substrate_families=("firm_fundamentals",),
    )
    broken_atom = _atom_for_record(one_slot.record)
    with pytest.raises(WorldModelRecordError, match="world_slot_state_path_missing"):
        resolve_intervention_atom_world_binding(broken_atom, one_slot.record)


def test_world_model_record_missing_required_binding_fails_closed(tmp_path: Path) -> None:
    _store, built, _model_spec, _registry_bundle_ref = _build_record(tmp_path)
    payload = built.record.model_dump(mode="json")
    payload.pop("fabric_world_ref")

    with pytest.raises(ValueError):
        WorldModelRecord.model_validate(payload)


def test_world_model_record_source_does_not_create_parallel_world_store() -> None:
    module_path = (
        Path(__file__).resolve().parents[4]
        / "src"
        / "polisyos"
        / "runtime"
        / "quality"
        / "world_model_record.py"
    )
    source = module_path.read_text(encoding="utf-8")
    src_root = Path(__file__).resolve().parents[4] / "src" / "polisyos"

    assert "SyntheticWorld" not in source
    assert "class WorldStore" not in source
    assert "class WorldStateEngine" not in source
    assert not list(src_root.rglob("gy_n3_*.py"))
