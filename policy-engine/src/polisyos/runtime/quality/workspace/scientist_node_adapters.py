"""Legacy Scientist node adapters for the GY Phase-2 operation waist."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.pdc import (
    ApplicabilityResult,
    ArtifactEnvelope,
    ArtifactRef,
    OperationClass,
    OperationContract,
    OperationInvocationRecord,
    PortSpec,
    SearchBlockerRecord,
    SearchLedgerEvent,
)

SCIENTIST_NODE_ADAPTER_RULE_VERSION = "policyos.gy.phase2.adapters.v1"


class NodeLike(Protocol):
    """Minimal Scientist node surface required by the Phase-2 adapter."""

    @property
    def spec(self) -> object:
        """Return the node spec that declares state reads/writes."""
        ...


class AdapterConformanceResult(BaseModel):
    """Result of checking that a legacy adapter preserves node contract shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_id: str
    passed: bool
    checked: list[str]
    failures: list[str] = Field(default_factory=list)


class AdapterApplicabilityEvaluation(BaseModel):
    """Formal-gate result plus the typed blocker emitted for missing ports."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    applicability: ApplicabilityResult
    blocker: SearchBlockerRecord | None = None


class ScientistNodeAdapterExecutionResult(BaseModel):
    """Ring-1 execution evidence for one legacy node adapter invocation."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    applicability: ApplicabilityResult
    invocation: OperationInvocationRecord
    ledger_event: SearchLedgerEvent
    artifact_envelopes: list[ArtifactEnvelope]
    outcome: Any | None = None
    blocker: SearchBlockerRecord | None = None


class ScientistNodeAdapter(BaseModel):
    """Ring-1 adapter that exposes one legacy node as a GY operation."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    adapter_id: str
    node_id: str
    legacy_alias: str
    operation_class: OperationClass
    contract: OperationContract
    required_inputs: list[str]
    produced_outputs: list[str]
    node: Any = Field(exclude=True, repr=False)

    @classmethod
    def from_node(
        cls,
        node: NodeLike,
        *,
        operation_id: str,
        operation_class: OperationClass,
        authority_transform: dict[str, Any],
        legacy_alias: str | None = None,
    ) -> ScientistNodeAdapter:
        """Build an adapter from a real Scientist ``NodeSpec`` surface."""

        spec = node.spec
        metadata = getattr(spec, "metadata", None)
        component_id = getattr(metadata, "component_id", None)
        node_id = str(component_id) if component_id is not None else node.__class__.__name__
        alias = legacy_alias or _legacy_alias_from_node(node)
        state_reads = [str(item) for item in getattr(spec, "state_reads", [])]
        produced = [str(item) for item in getattr(spec, "produces", [])]
        if not produced:
            produced = [str(item) for item in getattr(spec, "state_writes", [])]
        consumes = [_input_port(path) for path in state_reads]
        produces = [_output_port(path) for path in produced]
        contract = OperationContract(
            operation_id=operation_id,
            operation_version="phase2.v1",
            operation_class=operation_class,
            consumes=consumes,
            produces=produces,
            formal_preconditions=[
                {
                    "predicate_id": f"phase2.required_input.{_slug(path)}",
                    "input_path": path,
                    "severity": "hard",
                    "rule_version": SCIENTIST_NODE_ADAPTER_RULE_VERSION,
                }
                for path in state_reads
            ],
            allowed_internal_execution=["tool_call"],
            implementation_refs=[
                {
                    "kind": "scientist_node",
                    "node_id": node_id,
                    "legacy_alias": alias,
                }
            ],
            cost_model={"kind": "legacy_node_adapter", "budget_axis": "compute"},
            authority_transform=authority_transform,
            failure_modes=["missing_input", "legacy_node_failure", "candidate_only_output"],
            repair_options=[OperationClass.REFINE, OperationClass.ACQUIRE],
        )
        return cls(
            adapter_id=f"adapter-{_slug(operation_id)}",
            node_id=node_id,
            legacy_alias=alias,
            operation_class=operation_class,
            contract=contract,
            required_inputs=state_reads,
            produced_outputs=produced,
            node=node,
        )

    def evaluate_applicability(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
        state_facts: dict[str, Any],
        result_id: str,
    ) -> AdapterApplicabilityEvaluation:
        """Fail closed when a legacy node input port is not present."""

        checked: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for input_path in self.required_inputs:
            value = state_facts.get(input_path)
            passed = not _missing(value)
            predicate_id = f"phase2.required_input.{_slug(input_path)}"
            checked.append(
                {
                    "predicate_id": predicate_id,
                    "input_path": input_path,
                    "status": "passed" if passed else "failed",
                    "rule_version": SCIENTIST_NODE_ADAPTER_RULE_VERSION,
                }
            )
            if not passed:
                failed.append(
                    {
                        "predicate_id": predicate_id,
                        "input_path": input_path,
                        "reason": "missing_legacy_node_input",
                        "severity": "hard",
                    }
                )
        applicability = ApplicabilityResult(
            result_id=result_id,
            invocation_id=invocation_id,
            status="repair_required" if failed else "applicable",
            checked_preconditions=checked,
            failed_preconditions=failed,
            type_errors=[],
            repair_options=[
                {
                    "operation_class": OperationClass.REFINE.value,
                    "reason": "Provide missing legacy node input before execution.",
                }
            ]
            if failed
            else [],
        )
        blocker = None
        if failed:
            missing_input = str(failed[0]["input_path"])
            blocker = SearchBlockerRecord(
                blocker_id=f"blocker-{_slug(missing_input)}",
                workspace_id=workspace_id,
                operation_class=self.operation_class,
                blocked_port=missing_input,
                missing_input=missing_input,
                reason="Legacy node input port is missing; adapter cannot execute.",
                applicability_result_ref=result_id,
                repair_options=applicability.repair_options,
                producer_missing_label="producer_missing",
            )
        return AdapterApplicabilityEvaluation(applicability=applicability, blocker=blocker)

    def execute_candidate(
        self,
        *,
        ctx: object | None,
        state: object,
        workspace_id: str,
        invocation_id: str,
        cycle_index: int,
    ) -> ScientistNodeAdapterExecutionResult:
        """Execute the wrapped node and record candidate-only Ring-1 evidence."""

        state_facts = {
            input_path: _resolve_state_path(state, input_path)
            for input_path in self.required_inputs
        }
        applicability = self.evaluate_applicability(
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            state_facts=state_facts,
            result_id=f"applicability-{_slug(invocation_id)}",
        )
        if applicability.blocker is not None:
            invocation = self._invocation_record(
                workspace_id=workspace_id,
                invocation_id=invocation_id,
                cycle_index=cycle_index,
                status="repair_required",
                output_artifacts=[],
                applicability_result=applicability.applicability.result_id,
                internal_trace={
                    "adapter_id": self.adapter_id,
                    "node_id": self.node_id,
                    "legacy_alias": self.legacy_alias,
                    "candidate_only": True,
                    "blocked": True,
                },
            )
            ledger_event = self._ledger_event(
                workspace_id=workspace_id,
                invocation_id=invocation_id,
                cycle_index=cycle_index,
                output_artifacts=[],
                event_type="legacy_adapter_blocked",
            )
            return ScientistNodeAdapterExecutionResult(
                applicability=applicability.applicability,
                invocation=invocation,
                ledger_event=ledger_event,
                artifact_envelopes=[],
                blocker=applicability.blocker,
            )

        try:
            outcome = self.node.execute(ctx, state)
        except Exception as exc:  # pragma: no cover - defensive engine bridge
            invocation = self._invocation_record(
                workspace_id=workspace_id,
                invocation_id=invocation_id,
                cycle_index=cycle_index,
                status="failed",
                output_artifacts=[],
                applicability_result=applicability.applicability.result_id,
                internal_trace={
                    "adapter_id": self.adapter_id,
                    "node_id": self.node_id,
                    "legacy_alias": self.legacy_alias,
                    "candidate_only": True,
                    "exception_type": exc.__class__.__name__,
                },
            )
            ledger_event = self._ledger_event(
                workspace_id=workspace_id,
                invocation_id=invocation_id,
                cycle_index=cycle_index,
                output_artifacts=[],
                event_type="legacy_adapter_failed",
            )
            return ScientistNodeAdapterExecutionResult(
                applicability=applicability.applicability,
                invocation=invocation,
                ledger_event=ledger_event,
                artifact_envelopes=[],
                outcome=None,
            )

        envelopes = [
            _candidate_envelope(
                workspace_id=workspace_id,
                invocation_id=invocation_id,
                operation_id=self.contract.operation_id,
                operation_class=self.operation_class,
                node_id=self.node_id,
                legacy_alias=self.legacy_alias,
                output_key=output_key,
                payload=_output_payload(outcome, output_key),
            )
            for output_key in self.produced_outputs
        ]
        output_refs = [envelope.ref for envelope in envelopes]
        outcome_status = str(getattr(outcome, "status", "unknown"))
        invocation_status = (
            "completed"
            if outcome_status == "ok"
            else "repair_required"
            if outcome_status == "skip"
            else "failed"
        )
        invocation = self._invocation_record(
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            cycle_index=cycle_index,
            status=invocation_status,
            output_artifacts=output_refs,
            applicability_result=applicability.applicability.result_id,
            internal_trace={
                "adapter_id": self.adapter_id,
                "node_id": self.node_id,
                "legacy_alias": self.legacy_alias,
                "outcome_status": outcome_status,
                "candidate_only": True,
            },
        )
        ledger_event = self._ledger_event(
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            cycle_index=cycle_index,
            output_artifacts=output_refs,
            event_type="legacy_adapter_executed",
        )
        return ScientistNodeAdapterExecutionResult(
            applicability=applicability.applicability,
            invocation=invocation,
            ledger_event=ledger_event,
            artifact_envelopes=envelopes,
            outcome=outcome,
            blocker=applicability.blocker,
        )

    def _invocation_record(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
        cycle_index: int,
        status: str,
        output_artifacts: list[ArtifactRef],
        applicability_result: str,
        internal_trace: dict[str, Any],
    ) -> OperationInvocationRecord:
        return OperationInvocationRecord(
            invocation_id=invocation_id,
            operation_id=self.contract.operation_id,
            operation_version=self.contract.operation_version,
            workspace_id=workspace_id,
            cycle_index=cycle_index,
            selected_by={
                "kind": "phase2_playbook_adapter",
                "rule_version": SCIENTIST_NODE_ADAPTER_RULE_VERSION,
            },
            input_artifacts=[],
            parameters={"legacy_alias": self.legacy_alias},
            internal_trace=internal_trace,
            tool_calls=[],
            output_artifacts=output_artifacts,
            applicability_result=applicability_result,
            budget_delta={"legacy_node_invocations": 1},
            status=status,  # type: ignore[arg-type]
        )

    def _ledger_event(
        self,
        *,
        workspace_id: str,
        invocation_id: str,
        cycle_index: int,
        output_artifacts: list[ArtifactRef],
        event_type: str,
    ) -> SearchLedgerEvent:
        return SearchLedgerEvent(
            event_id=f"ledger-{_slug(invocation_id)}",
            workspace_id=workspace_id,
            cycle_index=cycle_index,
            event_type=event_type,
            actor={"kind": "legacy_node_adapter", "legacy_alias": self.legacy_alias},
            input_artifacts=[],
            output_artifacts=output_artifacts,
            operation_invocation_ref=invocation_id,
            budget_delta={"legacy_node_invocations": 1},
            created_obligations=[],
            timestamp=datetime.now(UTC).replace(microsecond=0).isoformat(),
        )


def validate_scientist_node_adapter_shape(adapter: ScientistNodeAdapter) -> AdapterConformanceResult:
    """Check that an adapter preserves ports and stays a Ring-1 authority hint."""

    failures: list[str] = []
    checked = [
        "consumes_ports",
        "produces_ports",
        "formal_preconditions",
        "authority_transform_hint",
        "candidate_only_execution",
    ]
    if not adapter.contract.consumes:
        failures.append("adapter_missing_consumes_ports")
    if not adapter.contract.produces:
        failures.append("adapter_missing_produces_ports")
    if not adapter.contract.formal_preconditions:
        failures.append("adapter_missing_formal_preconditions")
    if not adapter.contract.authority_transform:
        failures.append("adapter_missing_authority_transform_hint")
    if "tool_call" not in adapter.contract.allowed_internal_execution:
        failures.append("adapter_not_candidate_tool_execution")
    return AdapterConformanceResult(
        adapter_id=adapter.adapter_id,
        passed=not failures,
        checked=checked,
        failures=failures,
    )


def validate_adapter_semantic_preservation(
    adapter: ScientistNodeAdapter,
    *,
    ctx: object | None,
    state: object,
    workspace_id: str,
    invocation_id: str,
) -> AdapterConformanceResult:
    """Run the wrapped node and prove declared outputs are actually preserved."""

    shape = validate_scientist_node_adapter_shape(adapter)
    checked = [*shape.checked, "semantic_output_preservation"]
    failures = list(shape.failures)
    execution = adapter.execute_candidate(
        ctx=ctx,
        state=state,
        workspace_id=workspace_id,
        invocation_id=invocation_id,
        cycle_index=0,
    )
    if execution.blocker is not None:
        failures.append(f"semantic_blocked:{execution.blocker.missing_input}")
    if execution.outcome is None or getattr(execution.outcome, "status", None) != "ok":
        failures.append(
            f"semantic_node_status:{str(getattr(execution.outcome, 'status', 'missing'))}"
        )
    envelope_output_keys = {
        str(envelope.ref.uri).rsplit("/", maxsplit=1)[-1]
        for envelope in execution.artifact_envelopes
    }
    for output_key in adapter.produced_outputs:
        if output_key not in envelope_output_keys:
            failures.append(f"output_envelope_missing:{output_key}")
            continue
        payload = _output_payload(execution.outcome, output_key)
        if payload.get("state_value") is None and payload.get("artifacts_index_value") is None:
            failures.append(f"output_not_preserved:{output_key}")
    return AdapterConformanceResult(
        adapter_id=adapter.adapter_id,
        passed=not failures,
        checked=checked,
        failures=failures,
    )


def _legacy_alias_from_node(node: object) -> str:
    name = node.__class__.__name__
    if name.endswith("Node"):
        name = name[:-4]
    return _snake(name)


def _input_port(path: str) -> PortSpec:
    return PortSpec(
        port_id=f"port-{_slug(path)}",
        direction="consumes",
        port_type="StatePath",
        claim_shape={"kind": "legacy_node_state_read", "state_path": path},
        multiplicity={"min": 1, "max": 1},
        constraints={"legacy_state_path": path},
    )


def _output_port(path: str) -> PortSpec:
    return PortSpec(
        port_id=f"port-{_slug(path)}",
        direction="produces",
        port_type="StatePath",
        claim_shape={"kind": "legacy_node_output", "state_path": path},
        multiplicity={"min": 1, "max": 1},
        constraints={"legacy_state_path": path, "admission_state": "shadow"},
    )


def _missing(value: object) -> bool:
    return value is None or value == "" or value == []


def _resolve_state_path(state: object, path: str) -> object:
    value: object = state
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else getattr(value, part, None)
        if value is None:
            return None
    return value


def _candidate_envelope(
    *,
    workspace_id: str,
    invocation_id: str,
    operation_id: str,
    operation_class: OperationClass,
    node_id: str,
    legacy_alias: str,
    output_key: str,
    payload: object,
) -> ArtifactEnvelope:
    artifact_id = f"phase2.{_slug(workspace_id)}.{_slug(invocation_id)}.{_slug(output_key)}"
    ref = ArtifactRef.from_payload(
        artifact_id=artifact_id,
        artifact_type="LegacyNodeCandidateOutput",
        payload=payload,
        schema_ref="policyos.gy.phase2.legacy_node_candidate.v1",
        uri=f"gy://phase2/{workspace_id}/{invocation_id}/{output_key}",
        version="phase2.v1",
    )
    return ArtifactEnvelope(
        ref=ref,
        payload_ref=ref.uri,
        payload_schema_ref=ref.schema_ref,
        lifecycle_state="shadow",
        created_by={"kind": "legacy_node_adapter", "node_id": node_id},
        producer_operation={
            "operation_id": operation_id,
            "operation_class": operation_class.value,
            "legacy_alias": legacy_alias,
        },
        input_artifacts=[],
        producer_roots=[],
    )


def _output_payload(outcome: object, output_key: str) -> dict[str, Any]:
    state = getattr(outcome, "state", None)
    return {
        "output_key": output_key,
        "outcome_status": str(getattr(outcome, "status", "unknown")),
        "state_value": _jsonish(_resolve_state_path(state, output_key)),
        "artifacts_index_value": _jsonish(
            _resolve_state_path(state, f"artifacts_index.{output_key}")
        ),
    }


def _jsonish(value: object) -> object:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _jsonish(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonish(item) for item in value]
    return value


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


def _snake(value: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index > 0:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


__all__ = [
    "AdapterApplicabilityEvaluation",
    "AdapterConformanceResult",
    "ScientistNodeAdapterExecutionResult",
    "ScientistNodeAdapter",
    "validate_adapter_semantic_preservation",
    "validate_scientist_node_adapter_shape",
]
