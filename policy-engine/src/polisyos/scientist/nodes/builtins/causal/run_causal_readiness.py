"""Public causal run causal readiness module API."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.ir.analytics.causal_graph import load_causal_graph_model
from polisyos.ir.artifacts import InputRef
from polisyos.ir.observation.bundles import (
    CounterfactualCheckBundle,
    InterferenceLossSpecBundle,
    ProxyIdentificationBundle,
    StrategicResponseSpecsBundle,
    TransportabilityCheckBundle,
)
from polisyos.ir.observation.causal_readiness import (
    CausalReadinessBundle,
    persist_causal_readiness_bundle,
)
from polisyos.ir.observation.measurement import (
    RegimeCalendar,
    SchemaRegimeRegistry,
    ShockCalendar,
)
from polisyos.ir.refs import ArtifactRefModel, CausalGraphModelRef
from polisyos.scientist.causal.readiness import (
    CounterfactualQueryRunner,
    ProxyIdentificationRunner,
    StrategicResponseRunner,
    TransportabilityChecker,
    build_interference_readiness_entries,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CAUSAL_READINESS_BUNDLE_REF,
    ARTIFACT_CAUSAL_REPORT_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
    ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ARTIFACT_TRANSPORTABILITY_RESULT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_run_causal_readiness@1.0.0"),
    kind=ComponentKind.SCIENTIST_NODE,
    abi_targets={"world_abi": "1.x"},
    display_name="Run Causal Readiness",
    description=(
        "Batch proxy identification, transportability, strategic-response, "
        "counterfactual and interference readiness checks over observation-plane inputs."
    ),
    tags=["builtin", "causal", "readiness", "wave2"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        "params.proxy_identification_bundle",
        "params.transportability_check_bundle",
        "params.strategic_response_specs_bundle",
        "params.counterfactual_check_bundle",
        "params.interference_loss_spec_bundle",
        "params.measurement_model_by_family",
        "params.strategic_channel_inputs",
        "params.regime_calendar",
        "params.schema_regime_registry",
        "params.shock_calendar",
        f"artifacts_index.{ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF}",
        f"artifacts_index.{ARTIFACT_CAUSAL_REPORT_REF}",
    ],
    state_writes=[
        f"artifacts_index.{ARTIFACT_CAUSAL_READINESS_BUNDLE_REF}",
        f"artifacts_index.{ARTIFACT_TRANSPORTABILITY_RESULT_REF}",
        f"artifacts_index.{ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF}",
    ],
    produces=[
        ARTIFACT_CAUSAL_READINESS_BUNDLE_REF,
        ARTIFACT_TRANSPORTABILITY_RESULT_REF,
        ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF,
    ],
)


def _coerce_bundle(model: type[Any], payload: Any) -> Any | None:
    if payload is None:
        return None
    if isinstance(payload, model):
        return payload
    return model.model_validate(payload)


class RunCausalReadinessNode:
    """Run proxy, transport, strategic, and counterfactual readiness checks.

    Reads observation-plane bundles from ``state.params`` together with the
    reconciled graph, persists a combined ``CausalReadinessBundle``, and
    forwards primary transportability or strategic-response artifacts into the
    workflow artifact index.
    """

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        bundle_payloads = {
            "proxy": state.params.get("proxy_identification_bundle"),
            "transport": state.params.get("transportability_check_bundle"),
            "strategic": state.params.get("strategic_response_specs_bundle"),
            "counterfactual": state.params.get("counterfactual_check_bundle"),
            "interference": state.params.get("interference_loss_spec_bundle"),
        }
        if not any(value is not None for value in bundle_payloads.values()) and not state.params.get(
            "strategic_channel_inputs"
        ):
            return NodeOutcome(
                status="skip",
                state=state,
                events=[
                    NodeEvent(
                        level="info",
                        message="No C4a bundle inputs found; skip causal readiness execution.",
                    )
                ],
            )

        graph_ref_payload = state.artifacts_index.get(ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF)
        if graph_ref_payload is None:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_MISSING_INPUT,
                    message="Missing reconciled causal graph for causal readiness execution.",
                ),
            )
        try:
            graph_ref = CausalGraphModelRef.model_validate(graph_ref_payload.model_dump(mode="json"))
            graph = load_causal_graph_model(ctx.store, graph_ref)
            proxy_bundle = _coerce_bundle(ProxyIdentificationBundle, bundle_payloads["proxy"])
            transport_bundle = _coerce_bundle(TransportabilityCheckBundle, bundle_payloads["transport"])
            strategic_bundle = _coerce_bundle(
                StrategicResponseSpecsBundle,
                bundle_payloads["strategic"],
            )
            counterfactual_bundle = _coerce_bundle(
                CounterfactualCheckBundle,
                bundle_payloads["counterfactual"],
            )
            interference_bundle = _coerce_bundle(
                InterferenceLossSpecBundle,
                bundle_payloads["interference"],
            )
            regime_calendar = _coerce_bundle(RegimeCalendar, state.params.get("regime_calendar"))
            schema_regime_registry = _coerce_bundle(
                SchemaRegimeRegistry,
                state.params.get("schema_regime_registry"),
            )
            shock_calendar = _coerce_bundle(ShockCalendar, state.params.get("shock_calendar"))
        except Exception as exc:
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message=f"Invalid causal readiness payload: {exc}",
                ),
            )

        graph_input = ArtifactRefModel.model_validate(graph_ref.model_dump(mode="json"))
        causal_component_payload = state.artifacts_index.get(ARTIFACT_CAUSAL_REPORT_REF)
        causal_component_ref = (
            graph_input
            if causal_component_payload is None
            else ArtifactRefModel.model_validate(causal_component_payload.model_dump(mode="json"))
        )
        strategic_inputs = state.params.get("strategic_channel_inputs")
        if strategic_inputs is not None and not isinstance(strategic_inputs, Mapping):
            return NodeOutcome(
                status="fail",
                state=state,
                error=NodeError(
                    code=node_errors.ERROR_INVALID_STATE,
                    message="params.strategic_channel_inputs must be a mapping when provided.",
                ),
            )

        graph_inputs = [InputRef(artifact_id=graph_ref.artifact_id, role="reconciled_causal_graph")]
        proxy_runner = ProxyIdentificationRunner(graph=graph)
        transport_runner = TransportabilityChecker(
            graph=graph,
            store=ctx.store,
            base_inputs=graph_inputs,
        )
        strategic_runner = StrategicResponseRunner(
            store=ctx.store,
            causal_component_ref=causal_component_ref,
            base_inputs=graph_inputs,
            run_metadata={"run_id": state.run_id},
        )
        counterfactual_runner = CounterfactualQueryRunner(graph=graph)

        proxy_results = proxy_runner.run(
            proxy_bundle,
            measurement_models=state.params.get("measurement_model_by_family"),
        )
        transport_results = transport_runner.run(
            transport_bundle,
            regime_calendar=regime_calendar,
            schema_regime_registry=schema_regime_registry,
            shock_calendar=shock_calendar,
        )
        strategic_results = strategic_runner.run(
            strategic_bundle,
            channel_payloads=strategic_inputs,
        )
        counterfactual_results = counterfactual_runner.run(counterfactual_bundle)
        interference_results = build_interference_readiness_entries(interference_bundle)

        readiness_bundle = CausalReadinessBundle(
            proxy_results=proxy_results,
            transport_results=transport_results,
            strategic_results=strategic_results,
            counterfactual_results=counterfactual_results,
            interference_specs=interference_results,
            metadata={"run_id": state.run_id},
        )
        readiness_ref = persist_causal_readiness_bundle(
            ctx.store,
            readiness_bundle,
            inputs=graph_inputs,
        )

        next_state = state.model_copy(deep=True)
        next_state.artifacts_index[ARTIFACT_CAUSAL_READINESS_BUNDLE_REF] = ArtifactRef.model_validate(
            readiness_ref.model_dump(mode="json")
        )
        for item in transport_results:
            if item.result_ref is not None:
                next_state.artifacts_index[ARTIFACT_TRANSPORTABILITY_RESULT_REF] = ArtifactRef.model_validate(
                    item.result_ref.model_dump(mode="json")
                )
                break
        for item in strategic_results:
            if item.strategic_response_bundle_ref is not None:
                next_state.artifacts_index[ARTIFACT_STRATEGIC_RESPONSE_BUNDLE_REF] = ArtifactRef.model_validate(
                    item.strategic_response_bundle_ref.model_dump(mode="json")
                )
                break

        return NodeOutcome(
            status="ok",
            state=next_state,
            artifacts=[
                ArtifactRef.model_validate(readiness_ref.model_dump(mode="json")),
            ],
            events=[
                NodeEvent(
                    level="info",
                    message="Causal readiness checks completed.",
                    attrs={
                        "proxy": len(proxy_results),
                        "transport": len(transport_results),
                        "strategic": len(strategic_results),
                        "counterfactual": len(counterfactual_results),
                    },
                )
            ],
        )


__all__ = ["RunCausalReadinessNode"]
