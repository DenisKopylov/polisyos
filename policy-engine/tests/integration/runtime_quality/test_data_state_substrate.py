from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import jax.numpy as jnp
import numpy as np
import pytest
from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes, to_canonical_bytes
from polisyos.core.components import (
    Capability,
    ComponentId,
    ComponentKind,
    ComponentMetadata,
)
from polisyos.core.contracts import CapabilityDiscoveryRequest, CapabilityDiscoveryResponse
from polisyos.core.contracts.foundry import CompileRequest
from polisyos.foundry.compile.api import compile as compile_foundry
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.trinity import TrinityBundle
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.services import control_registry_providers
from polisyos.runtime.http.services.control_registry_providers import (
    resolve_control_registry_providers,
)
from polisyos.runtime.quality.capability_index import ScientistCapabilityOwnerTruth
from polisyos.runtime.quality.data_state_substrate import (
    DataStateSubstrateError,
    build_l5_family_binding_profile,
    build_production_data_state_world_model_record,
    l1_dcat_variable_availability,
    materialize_l4_data_state_snapshot,
)
from polisyos.runtime.quality.substrate_registry import (
    default_substrate_catalog_paths,
    load_l5_catalog_authority,
)
from polisyos.scientist.agent.tools.registry import ToolRegistry
from polisyos.scientist.agent.tools.schema import ToolDefinition
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
_CANONICAL_DATA_ROOT = (
    Path("production_data/canonical/local_data_20260501/") / "ukraine_server_support_20260410"
)
_L5_D2_DIR = _CANONICAL_DATA_ROOT / "runtime_calibration_internals/calibration/d2"
_L5_D3_DIR = _CANONICAL_DATA_ROOT / "runtime_calibration_internals/calibration/d3"
_NORMALIZED_CORPUS_DIR = _CANONICAL_DATA_ROOT / "normalized_corpus"
_L1_DCAT_DIR = Path("production_data/datasets_full_phase3full_20260327_183054")
_ACADEMIC_RUNTIME_DIR = Path("production_data/policyos_academic_runtime_slim_20260411T112032Z")


@dataclass(frozen=True)
class _DiscoveryFixtureNode:
    """Lightweight real NodeRegistry member that must never execute during discovery."""

    spec: NodeSpec

    def execute(self, ctx: Any, state: Any) -> NodeOutcome:
        del ctx, state
        raise AssertionError("capability discovery must serialize NodeSpec, never execute handlers")


def _scientist_discovery_search_body(
    *,
    request_id: str,
    query_text: str,
    match_all: bool = False,
) -> dict[str, object]:
    return {
        "search": {
            "request_id": request_id,
            "query_text": query_text,
            "construct_refs": ["fixture"],
            "intent": "capability_discovery",
            "required_layers": ["scientist_registry"],
            "authority_purpose": "review_capability_candidates",
            "allowed_modes": ["exact", "lexical"],
            "budget": {"top_k": 10, "match_all": match_all},
            "rule_version": "policyos.ds10.discovery.v1",
        },
        "resource_kinds": ["agent"],
        "audience": "REVIEWER",
    }


def _compile_smoke_plan(store: FileSystemCAS, model_spec: object, registry_bundle_ref: object):
    intervention = InterventionSpec(
        intervention_id="real_l4_tax_smoke",
        kind="income_tax",
        target=SelectorPredicate(field="id", operator=SelectorOperator.EQUALS, value="all"),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={"rate": Decimal("0.03")},
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="problem_real_l4_data_state_smoke",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id="policy_real_l4_data_state_smoke", interventions=[intervention]
        ),
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


def _symlink_dir(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(src, dst, target_is_directory=True)


def _repo_with_household_identification_mode(
    tmp_path: Path,
    *,
    selected_mode: str,
) -> Path:
    temp_root = tmp_path / f"repo-l5-household-{selected_mode}"
    production_root = temp_root / "production_data"
    canonical_root = temp_root / _CANONICAL_DATA_ROOT
    calibration_root = canonical_root / "runtime_calibration_internals/calibration"
    production_root.mkdir(parents=True, exist_ok=True)

    manifest_src = REPO_ROOT / "production_data/manifest.json"
    if manifest_src.exists():
        os.symlink(manifest_src, production_root / "manifest.json")
    _symlink_dir(REPO_ROOT / _L1_DCAT_DIR, temp_root / _L1_DCAT_DIR)
    _symlink_dir(REPO_ROOT / _ACADEMIC_RUNTIME_DIR, temp_root / _ACADEMIC_RUNTIME_DIR)
    _symlink_dir(REPO_ROOT / _NORMALIZED_CORPUS_DIR, temp_root / _NORMALIZED_CORPUS_DIR)
    _symlink_dir(REPO_ROOT / _L5_D3_DIR, temp_root / _L5_D3_DIR)
    for registry_name in (
        "layer3_gy_l5_schema_regime_registry.json",
        "layer3_gy_l5_schema_regime_scope_registry.json",
    ):
        registry_src = REPO_ROOT / "architecture/policy_design_case" / registry_name
        registry_dst = temp_root / "architecture/policy_design_case" / registry_name
        registry_dst.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(registry_src, registry_dst)

    d2_dst = temp_root / _L5_D2_DIR
    shutil.copytree(REPO_ROOT / _L5_D2_DIR, d2_dst)
    identification_path = d2_dst / "identification_mode_registry.json"
    # The appointed production-data tree is read-only.  ``copytree`` preserves
    # that mode, so make only this isolated test copy writable before mutation.
    identification_path.chmod(0o600)
    identification = json.loads(identification_path.read_text(encoding="utf-8"))
    household = dict(identification["household_distribution"])
    household["selected_mode"] = selected_mode
    household["primary_mode"] = selected_mode
    household["fallback_triggered"] = False
    household["reason"] = "s1_behavioral_toggle_probe"
    identification["household_distribution"] = household
    identification_path.write_text(
        json.dumps(identification, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    calibration_root.mkdir(parents=True, exist_ok=True)
    return temp_root


def test_agent_registry_has_typed_discovery_surface(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Default agent discovery must persist real Scientist registry projections lazily."""
    factory_calls = {"nodes": 0, "tools": 0}

    def _node_registry_factory() -> NodeRegistry:
        factory_calls["nodes"] += 1
        registry = NodeRegistry()
        metadata = ComponentMetadata(
            component_id=ComponentId.parse("scientist.fixture_policy_designer@1.0.0"),
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            domains=["policy_design"],
            jurisdictions=[],
            tags=["fixture", "policy"],
            capabilities=Capability.SCIENTIST_NODE,
            deps=[],
            display_name="Fixture policy designer",
            description="Fixture policy designer node",
            provides=["fixture_policy_design"],
        )
        registry.register(
            _DiscoveryFixtureNode(
                NodeSpec(
                    metadata=metadata,
                    state_reads=["fixture_input"],
                    state_writes=["fixture_output"],
                    produces=["fixture_design"],
                )
            )
        )
        return registry

    def _tool_registry_factory() -> ToolRegistry:
        factory_calls["tools"] += 1
        registry = ToolRegistry()
        registry.register(
            ToolDefinition(
                name="fixture_policy_search",
                description="Fixture policy search tool",
                parameters={
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
                domain="policy_design",
            ),
            lambda *, query: {"query": query},
        )
        return registry

    monkeypatch.setattr(
        control_registry_providers,
        "_default_scientist_node_registry",
        _node_registry_factory,
        raising=False,
    )
    monkeypatch.setattr(
        control_registry_providers,
        "_default_scientist_tool_registry",
        _tool_registry_factory,
        raising=False,
    )
    empty = SimpleNamespace(
        query_entries=lambda *args, **kwargs: (),
        get=lambda *args, **kwargs: None,
        list_all=lambda: [],
        list_by_family=lambda *args, **kwargs: [],
    )
    providers = resolve_control_registry_providers(
        connectors=empty,
        source_profiles=empty,
        binding_profiles=empty,
        model_profiles=empty,
        gy_catalog_graph=SimpleNamespace(),
    )
    agent_provider = next(
        provider
        for provider in providers.capability_discovery_providers
        if provider.resource_kind == "agent"
    )
    assert factory_calls == {"nodes": 0, "tools": 0}

    env = build_runtime_api_env(
        tmp_path,
        include_test_client=True,
        app_kwargs={
            "container_overrides": RuntimeContainerOverrides(
                control_registry_providers=providers
            )
        },
    )
    try:
        client = env["client"]
        assert client is not None
        with client:
            assert factory_calls == {"nodes": 0, "tools": 0}
            body = _scientist_discovery_search_body(
                request_id="search:scientist-registries",
                query_text="fixture policy",
            )
            response = client.post("/api/v1/control/capabilities/search", json=body)
            assert response.status_code == 200
            packet = CapabilityDiscoveryResponse.model_validate(response.json())
            assert factory_calls == {"nodes": 1, "tools": 1}
            assert {item.capability_ref for item in packet.results} == {
                "scientist-node:scientist.fixture_policy_designer@1.0.0",
                "scientist-tool:fixture_policy_search",
            }
            assert {item.resource_kind for item in packet.results} == {"agent"}
            assert {item.discovery_result.state for item in packet.results} == {
                "recall_unmeasured"
            }
            assert packet.frontier.completeness_status == "recall_unmeasured"
            assert packet.frontier.incompleteness_reasons == (
                "scientist_registry_recall_unmeasured",
            )
            assert all(
                item.execution_result.state != "executable"
                and item.authority_result.state != "admitted_authority"
                for item in packet.results
            )

            request = CapabilityDiscoveryRequest.model_validate(body)
            owner_result = agent_provider.search(request)
            receipt = owner_result.owner_receipt
            assert receipt.resource_kind == "agent"
            assert owner_result.completeness_status == "recall_unmeasured"
            assert receipt.node_registry_snapshot_ref != receipt.tool_registry_snapshot_ref
            assert factory_calls == {"nodes": 1, "tools": 1}
            assert {
                type(row.owner_truth) for row in owner_result.rows
            } == {ScientistCapabilityOwnerTruth}
            assert all(
                set(row.provenance_refs) <= set(receipt.provenance_refs)
                and set(row.owner_truth.provenance_refs) <= set(receipt.provenance_refs)
                for row in owner_result.rows
                if row.owner_truth is not None
            )

            control = env["app"].state._control_service
            store = control._artifact_store
            node_id = ArtifactID.model_validate(receipt.node_registry_snapshot_ref)
            tool_id = ArtifactID.model_validate(receipt.tool_registry_snapshot_ref)
            node_bytes = store.get_bytes(node_id)
            tool_bytes = store.get_bytes(tool_id)
            assert "sha256:" + hashlib.sha256(node_bytes).hexdigest() == (
                receipt.node_registry_snapshot_digest
            )
            assert "sha256:" + hashlib.sha256(tool_bytes).hexdigest() == (
                receipt.tool_registry_snapshot_digest
            )
            node_snapshot = from_canonical_bytes(node_bytes)
            tool_snapshot = from_canonical_bytes(tool_bytes)
            assert node_snapshot["schema_version"] == "scientist.node_registry.v1"
            assert tool_snapshot["schema_version"] == "scientist.tool_registry.v1"
            assert [entry["capability_ref"] for entry in node_snapshot["entries"]] == sorted(
                entry["capability_ref"] for entry in node_snapshot["entries"]
            )
            assert [entry["capability_ref"] for entry in tool_snapshot["entries"]] == sorted(
                entry["capability_ref"] for entry in tool_snapshot["entries"]
            )
            assert "handler" not in json.dumps(tool_snapshot, sort_keys=True)
            receipt_id = ArtifactID.model_validate(
                "sha256:"
                + hashlib.sha256(
                    to_canonical_bytes(receipt.model_dump(mode="json"))
                ).hexdigest()
            )
            assert store.get_manifest(receipt_id).kind == "scientist.registry_owner_receipt"
            assert from_canonical_bytes(store.get_bytes(receipt_id)) == receipt.model_dump(
                mode="json"
            )

            negative_body = _scientist_discovery_search_body(
                request_id="search:l4-is-not-scientist-registry",
                query_text="agent_registry_full L4 world-model entity data lookup",
                match_all=True,
            )
            negative_response = client.post(
                "/api/v1/control/capabilities/search",
                json=negative_body,
            )
            assert negative_response.status_code == 200
            negative_packet = CapabilityDiscoveryResponse.model_validate(
                negative_response.json()
            )
            assert {item.capability_ref for item in negative_packet.results} == {
                item.capability_ref for item in packet.results
            }
            assert all(
                item.discovery_result.snapshot_ref == receipt.search_snapshot_ref
                and item.execution_result.state != "executable"
                and item.authority_result.state != "admitted_authority"
                and all("agent_registry_full" not in ref for ref in item.provenance_refs)
                for item in negative_packet.results
            )
            assert factory_calls == {"nodes": 1, "tools": 1}
    finally:
        close_runtime_api_env(env)


def test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")

    built = build_production_data_state_world_model_record(
        store,
        repo_root=REPO_ROOT,
        workspace_dir=tmp_path / "s1-world",
        agent_limit=128,
        required_l1_variables=("avg_income", "employment_rate", "tax_revenue"),
        required_substrate_families=(
            "budget_flows",
            "firm_fundamentals",
            "household_distribution",
            "distress_enforcement",
        ),
    )
    exec_plan_ref = _compile_smoke_plan(
        store,
        built.model_spec,
        built.registry_bundle_ref,
    )
    exec_result = execute_foundry(
        store,
        built.simulation_input.to_execute_request(exec_plan_ref=exec_plan_ref),
    )

    assert built.data_snapshot_stats["l4_total_rows"]["agent_registry_full"] > 8_000_000
    assert built.data_snapshot_stats["bound_agent_count"] == 128
    assert built.data_snapshot_stats["source_mode"] == "real_l4_representative_slice"
    assert built.world_model.record.data_forge_binding_ref.role == "domain"
    assert built.world_model.record.data_forge_binding_ref.read_api_identity.startswith("ukraine@")
    assert built.world_model.record.substrate_registry_ref.substrate_version_id.startswith(
        "substrate_version_"
    )
    assert built.world_model.record.foundry_binding_ref.input_bindings_ref == str(
        built.world_model.input_bindings_ref.artifact_id
    )
    assert built.world_model.bound_global_state.__class__.__name__ == "GlobalState"
    assert int(built.world_model.bound_global_state.agents.active.shape[0]) == 128
    assert float(jnp.sum(built.world_model.bound_global_state.agents.income)) > 0.0
    assert exec_result.ok is True
    assert exec_result.simulation_result_ref is not None


def test_real_l4_same_slice_is_content_address_stable_and_different_slice_changes(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")

    first = build_production_data_state_world_model_record(
        store,
        repo_root=REPO_ROOT,
        workspace_dir=tmp_path / "world-a",
        agent_limit=128,
    )
    second = build_production_data_state_world_model_record(
        store,
        repo_root=REPO_ROOT,
        workspace_dir=tmp_path / "world-b",
        agent_limit=128,
    )
    different = materialize_l4_data_state_snapshot(
        store,
        repo_root=REPO_ROOT,
        workspace_dir=tmp_path / "world-c",
        agent_limit=64,
    )

    assert first.materialization.payload_content_hash == second.materialization.payload_content_hash
    assert (
        first.world_model.record.world_model_record_id
        == second.world_model.record.world_model_record_id
    )
    assert (
        first.data_snapshot_stats["bound_cell_count"]
        == second.data_snapshot_stats["bound_cell_count"]
    )
    assert first.materialization.payload_content_hash != different.payload_content_hash
    assert first.data_snapshot_stats["sample_strategy"] == "deterministic_region_stratified_hash"
    assert first.data_snapshot_stats["agent_registry_resolution_strategy"] == (
        "canonical_latest_record_then_ambiguous_region_sector_for_conflicts"
    )


def test_l5_family_profile_keeps_point_proxy_and_changepoint_honest() -> None:
    profile = build_l5_family_binding_profile(
        REPO_ROOT,
        families=("budget_flows", "household_distribution"),
        period_start="2021-12",
        period_end="2022-03",
    )

    point = profile.family_authority("budget_flows")
    proxy = profile.family_authority("household_distribution")
    l5 = load_l5_catalog_authority(default_substrate_catalog_paths(REPO_ROOT))
    expected_proxy_tier = l5.expected_trust_tier("household_distribution")

    assert point.identification_mode == "point_identified"
    assert point.trust_tier == "authoritative_high_coverage"
    assert point.trust_cap == 1.0
    assert point.value_authority == "point"
    assert proxy.identification_mode == "proxy_identified"
    assert proxy.trust_tier == expected_proxy_tier.tier
    assert proxy.trust_cap == expected_proxy_tier.trust_cap
    assert proxy.value_authority == "proxy_bounds"
    assert profile.schema_regime_status == "spans_changepoint_flagged"
    assert profile.boundary_buffer_periods == 1
    assert profile.regime_ids == ("ukraine_schema_v1", "ukraine_schema_v2")


def test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    proxy = build_production_data_state_world_model_record(
        store,
        repo_root=REPO_ROOT,
        workspace_dir=tmp_path / "proxy-world",
        agent_limit=16,
    )
    point_repo = _repo_with_household_identification_mode(
        tmp_path,
        selected_mode="point_identified",
    )
    point = build_production_data_state_world_model_record(
        store,
        repo_root=point_repo,
        workspace_dir=tmp_path / "point-world",
        agent_limit=16,
    )

    proxy_households = proxy.world_model.bound_global_state.household_cells
    point_households = point.world_model.bound_global_state.household_cells
    assert proxy_households is not None
    assert point_households is not None

    proxy_set = proxy_households.value_outer_set
    point_set = point_households.value_outer_set
    assert proxy_set is not None
    assert point_set is not None

    proxy_width = np.asarray(proxy_set.width)
    point_width = np.asarray(point_set.width)
    assert proxy_set.identification_status == "proxy"
    assert np.any(proxy_width > 0.0)
    assert point_set.identification_status == "point"
    assert np.allclose(point_width, 0.0)
    assert proxy_set != point_set
    assert proxy.materialization.payload_content_hash != point.materialization.payload_content_hash


def test_representative_slice_is_stratified_and_scales_against_full_corpus(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas")

    materialized = materialize_l4_data_state_snapshot(
        store,
        repo_root=REPO_ROOT,
        workspace_dir=tmp_path / "representative",
        agent_limit=128,
    )
    stats = materialized.data_snapshot_stats

    assert stats["sample_strategy"] == "deterministic_region_stratified_hash"
    assert stats["sample_stratification"] == "region_code"
    assert stats["bound_agent_count"] == 128
    assert stats["bound_region_count"] > 1
    assert stats["bound_sector_count"] > 1
    assert stats["l4_total_rows"]["agent_registry_full"] > 8_000_000
    assert stats["l4_total_rows"]["firm_fundamentals_annual"] > stats["bound_agent_count"]


def test_l1_uncovered_variable_and_empty_slice_fail_closed(tmp_path: Path) -> None:
    unavailable = l1_dcat_variable_availability(
        REPO_ROOT,
        "not_a_real_policyos_metric_for_s1",
    )

    assert unavailable.status == "unavailable"
    assert unavailable.metric_binding_count == 0
    assert unavailable.observation_count == 0

    store = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(DataStateSubstrateError) as unavailable_exc:
        materialize_l4_data_state_snapshot(
            store,
            repo_root=REPO_ROOT,
            workspace_dir=tmp_path / "unavailable",
            agent_limit=16,
            required_l1_variables=("not_a_real_policyos_metric_for_s1",),
        )
    assert unavailable_exc.value.code == "l1_variable_unavailable"

    with pytest.raises(DataStateSubstrateError) as empty_exc:
        materialize_l4_data_state_snapshot(
            store,
            repo_root=REPO_ROOT,
            workspace_dir=tmp_path / "empty",
            agent_limit=0,
            required_l1_variables=("avg_income",),
        )
    assert empty_exc.value.code == "production_data_state_empty"


def test_unregistered_substrate_variant_is_caught_by_n3(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")

    with pytest.raises(DataStateSubstrateError) as exc:
        build_production_data_state_world_model_record(
            store,
            repo_root=REPO_ROOT,
            workspace_dir=tmp_path / "unregistered",
            agent_limit=16,
            required_l1_variables=("avg_income",),
            required_substrate_families=("family_not_registered_in_s0",),
        )

    assert exc.value.code == "substrate_entry_unresolved"
