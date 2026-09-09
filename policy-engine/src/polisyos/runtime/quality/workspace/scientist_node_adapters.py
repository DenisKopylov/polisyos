"""Legacy Scientist node adapters for the GY Phase-2 operation waist."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts as core_artifacts
from polisyos.core import canon as core_canon
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
from polisyos.runtime.quality import adapter_contracts

SCIENTIST_NODE_ADAPTER_RULE_VERSION = "policyos.gy.phase2.adapters.v3"
_CANDIDATE_SCHEMA = "policyos.gy.phase2.legacy_node_candidate.v3"
_CANON = core_canon.CanonSpec(forbid_floats=False, exclude_none=False)


class NodeLike(Protocol):
    """Minimal Scientist node surface required by the Phase-2 adapter."""

    @property
    def spec(self) -> object:
        """Return the node spec that declares state reads/writes."""
        ...


class AdapterArtifactByteBinding(BaseModel):
    """Verified CAS bytes and canonical manifest identity at an adapter boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    artifact_ref: core_artifacts.ArtifactRef
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    manifest_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class AdapterConformanceResult(BaseModel):
    """Measured adapter admission evidence and its single candidate execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    adapter_id: str
    passed: bool
    checked: list[str]
    failures: list[str] = Field(default_factory=list)
    rule_version: str = SCIENTIST_NODE_ADAPTER_RULE_VERSION
    workspace_id: str | None = None
    invocation_id: str | None = None
    cycle_index: int | None = None
    smoke_attempted: bool = False
    smoke_status: str | None = None
    input_state_hash: str | None = None
    node_spec_hash: str | None = None
    contract_hash: str | None = None
    input_bindings: list[AdapterArtifactByteBinding] = Field(default_factory=list)
    source_output_bindings: list[AdapterArtifactByteBinding] = Field(default_factory=list)
    output_bindings: list[AdapterArtifactByteBinding] = Field(default_factory=list)
    applicability_binding: AdapterArtifactByteBinding | None = None
    preservation_failures: list[dict[str, Any]] = Field(default_factory=list)
    execution: ScientistNodeAdapterExecutionResult | None = Field(default=None, exclude=True)
    conformance_ref: core_artifacts.ArtifactRef | None = Field(default=None, exclude=True)


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
        produces = [_output_port(path, spec=spec) for path in produced]
        contract = OperationContract(
            operation_id=operation_id,
            operation_version="phase2.v3",
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


def validate_scientist_node_adapter_shape(
    adapter: ScientistNodeAdapter,
) -> AdapterConformanceResult:
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
    cycle_index: int = 0,
) -> AdapterConformanceResult:
    """Run one isolated smoke and verify its complete declared CAS boundary.

    Candidate execution is returned for reuse only after the consumer checks
    ``passed`` and the persisted conformance ref. Failed executions remain
    diagnostic evidence; they never grant an admitted operation.
    """

    shape = validate_scientist_node_adapter_shape(adapter)
    checked = [
        *shape.checked,
        "semantic_output_preservation",
        "real_input_cas_closure",
        "formal_applicability",
        "runtime_to_cas_preservation",
    ]
    failures = list(shape.failures)
    inputs: list[AdapterArtifactByteBinding] = []
    source_outputs: list[AdapterArtifactByteBinding] = []
    outputs: list[AdapterArtifactByteBinding] = []
    preservation_failures: list[dict[str, Any]] = []
    applicability_binding = None
    execution = None
    input_state_hash = None
    node_spec_hash = None
    contract_hash = None
    store = getattr(ctx, "store", None)

    def finish() -> AdapterConformanceResult:
        report = AdapterConformanceResult(
            adapter_id=adapter.adapter_id,
            passed=not failures,
            checked=checked,
            failures=list(failures),
            execution=execution,
            input_state_hash=input_state_hash,
            node_spec_hash=node_spec_hash,
            contract_hash=contract_hash,
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            cycle_index=cycle_index,
            smoke_attempted=execution is not None and execution.blocker is None,
            smoke_status=execution.invocation.status if execution is not None else None,
            input_bindings=inputs,
            source_output_bindings=source_outputs,
            output_bindings=outputs,
            applicability_binding=applicability_binding,
            preservation_failures=preservation_failures,
        )
        if store is None:
            return report
        try:
            payload = report.model_dump(mode="json")
            ref = store.put_json(
                deepcopy(payload),
                _write_options(
                    adapter,
                    "gy.adapter_conformance",
                    "policyos.gy.phase2.adapters",
                    inputs
                    + source_outputs
                    + outputs
                    + ([applicability_binding] if applicability_binding else []),
                ),
                canon_spec=_CANON,
            )
            _, actual, _ = _read_binding(store, ref, "conformance")
            if actual != core_canon.to_canonical_bytes(payload, _CANON):
                raise ValueError("conformance_readback_changed")
            return report.model_copy(update={"conformance_ref": ref})
        except Exception as exc:
            return report.model_copy(
                update={
                    "passed": False,
                    "failures": [*failures, f"conformance_persistence_failed:{type(exc).__name__}"],
                }
            )

    if not all(
        callable(getattr(store, method, None))
        for method in ("put_json", "get_bytes", "get_manifest")
    ):
        failures.append("semantic_store_missing")
        store = None
        return finish()
    try:
        smoke_state = deepcopy(_validated_node_state(state))
    except Exception as exc:
        failures.append(f"input_state_invalid:{type(exc).__name__}")
        return finish()
    try:
        node_spec_hash = _byte_hash(
            core_canon.to_canonical_bytes(_jsonish(adapter.node.spec), _CANON)
        )
        contract_hash = _byte_hash(
            core_canon.to_canonical_bytes(adapter.contract.model_dump(mode="json"), _CANON)
        )
        current = ScientistNodeAdapter.from_node(
            adapter.node,
            operation_id=adapter.contract.operation_id,
            operation_class=adapter.operation_class,
            authority_transform=adapter.contract.authority_transform,
            legacy_alias=adapter.legacy_alias,
        )
        if (
            current.contract != adapter.contract
            or current.node_id != adapter.node_id
            or current.required_inputs != adapter.required_inputs
            or current.produced_outputs != adapter.produced_outputs
        ):
            failures.append("adapter_node_contract_mismatch")
        facts = {path: _input_fact(smoke_state, path) for path in adapter.required_inputs}
        input_state_hash = _byte_hash(core_canon.to_canonical_bytes(facts, _CANON))
        for path, fact in facts.items():
            try:
                inputs.extend(_reference_closure(store, fact["value"], path))
            except Exception as exc:
                failures.append(f"input_reference_invalid:{path}:{type(exc).__name__}")
        formal = adapter.evaluate_applicability(
            workspace_id=workspace_id,
            invocation_id=invocation_id,
            state_facts={path: fact["value"] for path, fact in facts.items()},
            result_id=f"applicability-{_slug(invocation_id)}",
        )
        applicability_payload = formal.applicability.model_dump(mode="json")
        applicability_ref = store.put_json(
            deepcopy(applicability_payload),
            _write_options(
                adapter,
                "gy.adapter_applicability",
                "policyos.gy.phase2.adapter_applicability",
                inputs,
            ),
            canon_spec=_CANON,
        )
        applicability_binding, actual, _ = _read_binding(store, applicability_ref, "applicability")
        if actual != core_canon.to_canonical_bytes(applicability_payload, _CANON):
            failures.append("formal_applicability_readback_changed")
    except Exception as exc:
        failures.append(f"semantic_input_binding_failed:{type(exc).__name__}")
    if failures:
        return finish()

    frozen_input_state = deepcopy(smoke_state)
    execution = adapter.execute_candidate(
        ctx=ctx,
        state=smoke_state,
        workspace_id=workspace_id,
        invocation_id=invocation_id,
        cycle_index=cycle_index,
    )
    try:
        if (
            _byte_hash(core_canon.to_canonical_bytes(_jsonish(adapter.node.spec), _CANON))
            != node_spec_hash
        ):
            failures.append("node_spec_changed_during_smoke")
    except Exception as exc:
        failures.append(f"node_spec_changed_during_smoke:{type(exc).__name__}")
    if execution.blocker is not None:
        failures.append(f"semantic_blocked:{execution.blocker.missing_input}")
    if execution.outcome is None or getattr(execution.outcome, "status", None) != "ok":
        failures.append(f"semantic_node_status:{getattr(execution.outcome, 'status', 'missing')!s}")
    if execution.outcome is not None:
        try:
            execution = execution.model_copy(
                update={"outcome": _validated_node_outcome(execution.outcome)}
            )
        except Exception as exc:
            failures.append(f"output_state_invalid:{type(exc).__name__}")
            return finish()
    verified_envelopes: list[ArtifactEnvelope] = []
    # Freeze the complete source projection before any candidate write can mutate it.
    payloads, output_failures = _current_output_payloads(
        adapter, ctx=ctx, input_state=frozen_input_state, outcome=execution.outcome
    )
    failures.extend(output_failures)
    if output_failures:
        return finish()
    for output_key in adapter.produced_outputs:
        payload = payloads[output_key]
        try:
            bound_output = _reference_closure(store, payload, output_key)
            source_outputs.extend(bound_output)
        except Exception as exc:
            failures.append(f"output_reference_invalid:{output_key}:{type(exc).__name__}")
            continue
        payload.update(
            {"authority_disposition": "candidate_only", "schema_version": _CANDIDATE_SCHEMA}
        )
        lineage = inputs + bound_output
        opts = _write_options(
            adapter, "gy.legacy_node_candidate", "policyos.gy.phase2.legacy_node_candidate", lineage
        )
        before = _preservation_surface(
            "runtime",
            payload,
            producer=opts.producer.model_dump(mode="json"),
            schema=opts.schema.model_dump(mode="json"),
            lineage=[item.model_dump(mode="json") for item in opts.inputs],
        )
        try:
            core_ref = store.put_json(deepcopy(payload), opts, canon_spec=_CANON)
            binding, raw, manifest = _read_binding(store, core_ref, output_key)
            outputs.append(binding)
            after = _preservation_surface(
                "runtime.cas",
                core_canon.from_canonical_bytes(raw),
                producer=manifest.producer.model_dump(mode="json") if manifest.producer else None,
                schema=manifest.artifact_schema.model_dump(mode="json")
                if manifest.artifact_schema
                else None,
                lineage=[item.model_dump(mode="json") for item in manifest.inputs],
            )
            report = adapter_contracts.validate_adapter_preservation(
                adapter_path="runtime_to_cas",
                before=before,
                after=after,
            )
            if report.status != "pass" or "runtime_refs" not in report.checked_field_families:
                failures.append(f"adapter_preservation_failed:{output_key}")
                preservation_failures.extend(
                    {"output_key": output_key, **item} for item in report.to_blocking_failures()
                )
                continue
            pdc_ref = _pdc_binding_ref(binding, "LegacyNodeCandidateOutput", _CANDIDATE_SCHEMA)
            verified_envelopes.append(
                ArtifactEnvelope(
                    ref=pdc_ref,
                    payload_ref=pdc_ref.uri,
                    payload_schema_ref=_CANDIDATE_SCHEMA,
                    lifecycle_state="shadow",
                    created_by={"kind": "legacy_node_adapter", "node_id": adapter.node_id},
                    producer_operation={
                        "operation_id": adapter.contract.operation_id,
                        "operation_class": adapter.operation_class.value,
                        "legacy_alias": adapter.legacy_alias,
                    },
                    input_artifacts=[
                        _pdc_binding_ref(item, "LegacyNodeInput", item.artifact_ref.kind)
                        for item in lineage
                    ],
                    producer_roots=[],
                )
            )
        except Exception as exc:
            failures.append(f"output_cas_preservation_failed:{output_key}:{type(exc).__name__}")
    refs = [envelope.ref for envelope in verified_envelopes]
    execution = execution.model_copy(
        update={
            "artifact_envelopes": verified_envelopes,
            "invocation": execution.invocation.model_copy(
                update={
                    "output_artifacts": refs,
                    "applicability_result": f"cas://{applicability_binding.artifact_ref.artifact_id}",
                }
            ),
            "ledger_event": execution.ledger_event.model_copy(update={"output_artifacts": refs}),
        }
    )
    return finish()


def _byte_hash(raw: bytes) -> str:
    return "sha256:" + sha256(raw).hexdigest()


def _validated_node_state(state: object) -> object:
    from polisyos.scientist import ExperimentState

    if not isinstance(state, ExperimentState):
        raise TypeError("scientist_state_type_required")
    payload = state.model_dump(mode="python", round_trip=True, warnings=False)
    # Rebuild from values: validation of an existing instance skips mutated maps.
    # Base-owned fields keep their constraints even in a richer state subclass.
    ExperimentState.model_validate({key: payload[key] for key in ExperimentState.model_fields})
    return type(state).model_validate(payload)


def _validated_node_outcome(outcome: object) -> object:
    from polisyos.scientist.orchestration.engine import NodeOutcome

    if not isinstance(outcome, NodeOutcome):
        raise TypeError("scientist_outcome_type_required")
    state = _validated_node_state(outcome.state)
    payload = outcome.model_dump(mode="python", round_trip=True, exclude={"state"}, warnings=False)
    payload["state"] = state
    NodeOutcome.model_validate({key: payload[key] for key in NodeOutcome.model_fields})
    return type(outcome).model_validate(payload)


def _input_fact(state: object, path: str) -> dict[str, Any]:
    value = state
    missing = object()
    for part in path.split("."):
        value = (
            value[part]
            if isinstance(value, dict) and part in value
            else (missing if isinstance(value, dict) else getattr(value, part, missing))
        )
        if value is missing:
            return {"present": False, "value": None}
    return {"present": True, "value": _jsonish(value)}


def _read_binding(
    store: core_artifacts.ArtifactStore, ref: object, path: str
) -> tuple[AdapterArtifactByteBinding, bytes, core_artifacts.ArtifactManifest]:
    typed = core_artifacts.ArtifactRef.model_validate(ref)
    raw = store.get_bytes(typed.artifact_id)
    digest = _byte_hash(raw)
    manifest = core_artifacts.ArtifactManifest.model_validate(store.get_manifest(typed.artifact_id))
    if (
        digest != str(typed.artifact_id)
        or manifest.artifact_id != typed.artifact_id
        or manifest.kind != typed.kind
        or manifest.media_type != typed.media_type
        or manifest.integrity.sha256 != digest.removeprefix("sha256:")
    ):
        raise ValueError("artifact_byte_or_manifest_identity_mismatch")
    return (
        AdapterArtifactByteBinding(
            path=path,
            artifact_ref=typed,
            content_hash=digest,
            manifest_hash=_byte_hash(
                core_canon.to_canonical_bytes(
                    manifest.model_dump(mode="json", by_alias=True), _CANON
                )
            ),
        ),
        raw,
        manifest,
    )


def _reference_closure(
    store: core_artifacts.ArtifactStore, value: object, path: str
) -> list[AdapterArtifactByteBinding]:
    bindings: list[AdapterArtifactByteBinding] = []
    visited: set[str] = set()

    def visit(item: object, coordinate: str) -> None:
        if hasattr(item, "model_dump"):
            item = item.model_dump(mode="json")
        if isinstance(item, dict) and "artifact_id" in item:
            binding, _, manifest = _read_binding(store, item, coordinate)
            bindings.append(binding)
            identity = str(binding.artifact_ref.artifact_id)
            if identity in visited:
                return
            visited.add(identity)
            for index, parent in enumerate(manifest.inputs):
                parent_manifest = core_artifacts.ArtifactManifest.model_validate(
                    store.get_manifest(parent.artifact_id)
                )
                visit(
                    core_artifacts.ArtifactRef(
                        artifact_id=parent.artifact_id,
                        kind=parent_manifest.kind,
                        media_type=parent_manifest.media_type,
                    ),
                    f"{coordinate}.lineage[{index}]",
                )
        elif isinstance(item, dict):
            for key, child in item.items():
                visit(child, f"{coordinate}.{key}")
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                visit(child, f"{coordinate}[{index}]")

    visit(value, path)
    return bindings


def _write_options(
    adapter: ScientistNodeAdapter,
    kind: str,
    schema: str,
    bindings: list[AdapterArtifactByteBinding],
) -> core_artifacts.PutOptions:
    return core_artifacts.PutOptions(
        kind=kind,
        media_type="application/json",
        schema=core_artifacts.SchemaInfo(name=schema, version="3.0"),
        producer=core_artifacts.ProducerInfo(
            component=adapter.node_id, version=SCIENTIST_NODE_ADAPTER_RULE_VERSION
        ),
        inputs=[
            core_artifacts.InputRef(artifact_id=item.artifact_ref.artifact_id, role=item.path)
            for item in bindings
        ],
    )


def _preservation_surface(
    surface: str, payload: object, *, producer: object, schema: object, lineage: object
) -> adapter_contracts.AdapterSurfacePayload:
    return adapter_contracts.AdapterSurfacePayload(
        surface=surface,
        field_families={
            "runtime_refs": {
                "runtime_refs": deepcopy(payload),
                "provenance": deepcopy(producer),
                "schema": deepcopy(schema),
                "lineage": deepcopy(lineage),
            }
        },
    )


def _pdc_binding_ref(
    binding: AdapterArtifactByteBinding, artifact_type: str, schema_ref: str
) -> ArtifactRef:
    identity = str(binding.artifact_ref.artifact_id)
    return ArtifactRef(
        artifact_id=identity,
        artifact_type=artifact_type,
        content_hash=binding.content_hash,
        schema_ref=schema_ref,
        uri=f"cas://{identity}",
        version="phase2.v2",
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


def _output_port(path: str, *, spec: object) -> PortSpec:
    return PortSpec(
        port_id=f"port-{_slug(path)}",
        direction="produces",
        port_type="StatePath",
        claim_shape={"kind": "legacy_node_output", "state_path": path},
        multiplicity={"min": 1, "max": 1},
        constraints={
            "legacy_state_path": path,
            "admission_state": "shadow",
            "output_contract": next(
                (
                    row.model_dump(mode="json")
                    for row in getattr(spec, "output_rules", ())
                    if row.output_key == path
                ),
                {"output_key": path, "availability": "required", "verifier_rule_ref": None},
            ),
        },
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


def _direct_artifact_refs(value: object) -> dict[str, core_artifacts.ArtifactRef]:
    """Collect offered values, excluding ancestry that the CAS verifier resolves later."""
    refs: dict[str, core_artifacts.ArtifactRef] = {}

    def visit(item: object) -> None:
        if hasattr(item, "model_dump"):
            item = item.model_dump(mode="json")
        if isinstance(item, dict) and "artifact_id" in item:
            ref = core_artifacts.ArtifactRef.model_validate(item)
            refs[str(ref.artifact_id)] = ref
        elif isinstance(item, dict):
            for child in item.values():
                visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item:
                visit(child)

    visit(value)
    return refs


def _validated_current_output_payloads(
    adapter: ScientistNodeAdapter,
    *,
    ctx: object,
    input_state: object,
    outcome: object,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Bind the full declared output set to the actual attempt and owner readback."""
    from polisyos.scientist.orchestration.engine import (
        OutputAwareNodeOutcome,
        OutputAwareNodeSpec,
    )

    keys = adapter.produced_outputs
    if len(keys) != len(set(keys)):
        return {}, ["output_contract_duplicate_key"]
    current = {str(ref.artifact_id): ref for ref in getattr(outcome, "artifacts", ())}
    payloads = {key: deepcopy(_output_payload(outcome, key)) for key in keys}
    failures: list[str] = []
    aware = isinstance(adapter.node.spec, OutputAwareNodeSpec)
    verified_spec = None
    dispositions = {}
    if aware:
        verified_spec = OutputAwareNodeSpec.model_validate(
            adapter.node.spec.model_dump(mode="python", round_trip=True)
        )
        if verified_spec.produces != keys:
            return payloads, ["output_contract_population_mismatch"]
        if not isinstance(outcome, OutputAwareNodeOutcome):
            return payloads, ["output_disposition_ledger_missing"]
        dispositions = {row.output_key: row for row in outcome.output_dispositions}
        if len(dispositions) != len(outcome.output_dispositions) or set(dispositions) != set(keys):
            return payloads, ["output_disposition_population_mismatch"]
        # Never accept a caller's passed/recomputed flag. Execute the actual node
        # owner's substantive readback on the frozen pre-smoke state.
        verifier = getattr(adapter.node, "verify_output_dispositions", None)
        if not callable(verifier):
            return payloads, ["output_disposition_verifier_missing"]
        spec_before = deepcopy(verified_spec.model_dump(mode="json"))
        outcome_before = deepcopy(outcome.model_dump(mode="json"))
        input_before = deepcopy(input_state.model_dump(mode="json"))
        try:
            verifier(ctx=ctx, input_state=input_state, outcome=outcome)
        except Exception as exc:
            return payloads, [f"output_disposition_verification_failed:{exc}"]
        checked_spec = OutputAwareNodeSpec.model_validate(
            adapter.node.spec.model_dump(mode="python", round_trip=True)
        )
        if checked_spec.model_dump(mode="json") != spec_before:
            return payloads, ["output_contract_changed_during_readback"]
        if (
            outcome.model_dump(mode="json") != outcome_before
            or input_state.model_dump(mode="json") != input_before
        ):
            return payloads, ["output_evidence_changed_during_readback"]
    elif isinstance(outcome, OutputAwareNodeOutcome):
        return payloads, ["output_disposition_contract_missing"]

    for key, payload in payloads.items():
        disposition = dispositions.get(key)
        if disposition is not None and disposition.disposition == "refused":
            rule = next(row for row in verified_spec.output_rules if row.output_key == key)
            if rule.availability != "owner_verified_refusal":
                failures.append(f"required_output_refused:{key}")
                continue
            if payload["state_present"] or payload["artifacts_index_present"]:
                failures.append(f"refused_output_positive_slot_present:{key}")
                continue
            if current.get(str(disposition.artifact_ref.artifact_id)) != disposition.artifact_ref:
                failures.append(f"output_not_emitted_current_attempt:{key}")
                continue
            payload["output_disposition"] = disposition.model_dump(mode="json")
            continue
        if payload["state_value"] is None and payload["artifacts_index_value"] is None:
            failures.append(f"output_not_preserved:{key}")
            continue
        offered = _direct_artifact_refs(payload)
        if not offered or any(current.get(identity) != ref for identity, ref in offered.items()):
            failures.append(f"output_not_emitted_current_attempt:{key}")
            continue
        if disposition is not None:
            if offered.get(str(disposition.artifact_ref.artifact_id)) != disposition.artifact_ref:
                failures.append(f"output_disposition_ref_mismatch:{key}")
                continue
            payload["output_disposition"] = disposition.model_dump(mode="json")
    return payloads, failures


def _current_output_payloads(
    adapter: ScientistNodeAdapter,
    *,
    ctx: object,
    input_state: object,
    outcome: object,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Turn malformed offered contracts/refs into typed conformance failures."""
    try:
        return _validated_current_output_payloads(
            adapter, ctx=ctx, input_state=input_state, outcome=outcome
        )
    except Exception as exc:
        return {}, [f"output_contract_invalid:{type(exc).__name__}:{exc}"]


def _output_payload(outcome: object, output_key: str) -> dict[str, Any]:
    state = getattr(outcome, "state", None)
    return {
        "output_key": output_key,
        "outcome_status": str(getattr(outcome, "status", "unknown")),
        "state_present": _input_fact(state, output_key)["present"],
        "artifacts_index_present": _input_fact(state, f"artifacts_index.{output_key}")["present"],
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
    "AdapterArtifactByteBinding",
    "AdapterConformanceResult",
    "ScientistNodeAdapter",
    "ScientistNodeAdapterExecutionResult",
    "validate_adapter_semantic_preservation",
    "validate_scientist_node_adapter_shape",
]
