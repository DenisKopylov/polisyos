from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from polisyos.core.artifacts.manifest import InputRef
from polisyos.core.compiler.report import put_link_report
from polisyos.core.registry import load_registry_bundle_content
from polisyos.ir.linker import link_trinity
from polisyos.ir.registry_fragments import RegistryBundle
from polisyos.ir.trinity import TrinityBundle
from polisyos.core.components import Capability, ComponentId, ComponentMetadata
from polisyos.core.canon import from_canonical_bytes

from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.protocol import NodeError, NodeEvent, NodeOutcome, NodeSpec
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins import errors as node_errors
from polisyos.scientist.nodes.builtins.state_keys import (
    INPUT_REGISTRY_BUNDLE_REF,
    INPUT_TRINITY_BUNDLE_REF,
    REPORT_LINK_REPORT_REF,
)

_METADATA = ComponentMetadata(
    component_id=ComponentId.parse("scientist.node_link_trinity@1.0.0"),
    display_name="Link Trinity",
    description="Validate Trinity bundle against registries and emit LinkReport.",
    tags=["builtin", "compile"],
    capabilities=Capability.SCIENTIST_NODE,
)

_SPEC = NodeSpec(
    metadata=_METADATA,
    state_reads=[
        f"inputs.{INPUT_TRINITY_BUNDLE_REF}",
        f"inputs.{INPUT_REGISTRY_BUNDLE_REF}",
    ],
    state_writes=[f"reports_index.{REPORT_LINK_REPORT_REF}"],
    produces=[REPORT_LINK_REPORT_REF],
)


@dataclass(frozen=True)
class LinkTrinityNode:
    allow_extra_params: bool = False
    strict: bool = True

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def bind(self, params: dict[str, Any]) -> "LinkTrinityNode":
        if not params:
            return self
        allow_extra = params.get("allow_extra_params", self.allow_extra_params)
        strict = params.get("strict", self.strict)
        return replace(self, allow_extra_params=bool(allow_extra), strict=bool(strict))

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        trinity_ref = state.inputs.get(INPUT_TRINITY_BUNDLE_REF)
        registry_ref = state.inputs.get(INPUT_REGISTRY_BUNDLE_REF)
        if trinity_ref is None or registry_ref is None:
            error = NodeError(
                code=node_errors.ERROR_MISSING_INPUT,
                message="Missing Trinity bundle or registry bundle",
                details={
                    "trinity_bundle_ref": bool(trinity_ref),
                    "registry_bundle_ref": bool(registry_ref),
                },
            )
            return NodeOutcome(status="fail", state=state, error=error)

        payload = from_canonical_bytes(ctx.store.get_bytes(trinity_ref.artifact_id))
        bundle = TrinityBundle.model_validate(payload)

        registry_content = load_registry_bundle_content(ctx.store, registry_ref)
        registries = RegistryBundle(
            mechanisms=registry_content.mechanism_registry,
            slots=registry_content.slot_registry,
            merge_rules=registry_content.merge_registry,
            constraints=registry_content.constraint_registry,
            selector_fields=registry_content.selector_field_registry,
            units=registry_content.units_registry,
            metrics=registry_content.metric_registry,
        )

        link_inputs = [
            InputRef(artifact_id=trinity_ref.artifact_id, role="trinity_bundle"),
            InputRef(artifact_id=registry_ref.artifact_id, role="registry_bundle"),
        ]
        _, link_report = link_trinity(
            bundle,
            registries,
            allow_extra_params=self.allow_extra_params,
            strict=self.strict,
        )
        link_report_ref = put_link_report(ctx.store, link_report, inputs=link_inputs)

        new_state = state.model_copy(deep=True)
        new_state.reports_index[REPORT_LINK_REPORT_REF] = link_report_ref

        if self.strict and not link_report.ok:
            error = NodeError(
                code=node_errors.ERROR_TRINITY_LINK_FAILED,
                message="Trinity link failed",
                details={"link_report_ref": link_report_ref.model_dump()},
            )
            event = NodeEvent(level="warn", message="Trinity link reported errors")
            return NodeOutcome(
                status="fail",
                state=new_state,
                artifacts=[link_report_ref],
                events=[event],
                error=error,
            )

        return NodeOutcome(status="ok", state=new_state, artifacts=[link_report_ref])
