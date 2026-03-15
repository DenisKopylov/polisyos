from __future__ import annotations

from dataclasses import dataclass

from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.foundry.methods import build_method_catalog_snapshot, persist_method_catalog_snapshot
from polisyos.foundry.methods.catalog import (
    ensure_all_methods_registered as ensure_causal_methods_registered,
)
from polisyos.foundry.methods.catalog.causal.capabilities import build_causal_capability_contract
from polisyos.ir.analytics.causal_capabilities import persist_causal_capability_contract
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_build_method_catalog_snapshot@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Build Method Catalog Snapshot",
    description="Capture live FoundryMethod catalog for prompting and preflight.",
    tags=["builtin", "planning", "methods"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=["run_id"],
    state_writes=[
        "params.method_catalog_snapshot_ref",
        "params.causal_capability_hash",
        f"artifacts_index.{ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF}",
    ],
    produces=[
        ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF,
        ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF,
    ],
)


@dataclass(frozen=True)
class BuildMethodCatalogSnapshotNode:
    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        ensure_causal_methods_registered()
        capability_contract = build_causal_capability_contract()
        capability_ref = persist_causal_capability_contract(ctx.store, capability_contract)
        snapshot = build_method_catalog_snapshot(
            run_id=state.run_id,
            capability_contract=capability_contract,
        )
        snapshot_ref = persist_method_catalog_snapshot(ctx.store, snapshot)
        new_state = state.model_copy(deep=True)
        new_state.params["method_catalog_snapshot_ref"] = str(snapshot_ref.artifact_id)
        new_state.params["causal_capability_hash"] = capability_contract.dependency_fingerprint
        new_state.artifacts_index[ARTIFACT_METHOD_CATALOG_SNAPSHOT_REF] = snapshot_ref
        new_state.artifacts_index[ARTIFACT_CAUSAL_CAPABILITY_CONTRACT_REF] = capability_ref
        new_state.method_catalog_snapshot_ref = snapshot_ref
        new_state.causal_capability_contract_ref = capability_ref
        return NodeOutcome(
            status="ok",
            state=new_state,
            artifacts=[snapshot_ref, capability_ref],
            events=[
                NodeEvent(
                    level="info",
                    message="Method catalog snapshot captured",
                    attrs={
                        "method_count": len(snapshot.entries),
                        "causal_capability_hash": capability_contract.dependency_fingerprint,
                    },
                )
            ],
        )


__all__ = ["BuildMethodCatalogSnapshotNode"]
