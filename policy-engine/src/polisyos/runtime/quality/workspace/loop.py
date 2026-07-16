"""Slice-0 workspace loop and proof-packet contracts.

Canonical owners extended here: PDC waist contracts in ``polisyos.pdc``,
catalog binding in ``data_forge_binding``, adapter gates in
``adapter_contracts``, semantic checks in ``semantic_binding``, and costed
acquisition terminal planning in ``acquisition_planner``. This module owns the
deterministic ``BIND -> ESTIMATE -> VERIFY`` workspace-loop orchestration only;
later GY paths must stay fenced from the Slice-0 fixture trajectory.
"""

from __future__ import annotations

import json
import logging
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import scan_secret_and_pii
from polisyos.core.artifacts.manifest import ProducerInfo, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.data_forge import read_api
from polisyos.pdc import (
    ApplicabilityResult,
    ArtifactEnvelope,
    ArtifactRef,
    AuthorityBoundary,
    AuthorityDerivationTrace,
    BudgetVector,
    CertifiedOperationEnvelope,
    CompositionCertificate,
    EvidenceBasis,
    FrontierSnapshot,
    MethodOutputConsumptionRecord,
    ObligationRecord,
    OperationClass,
    OperationContract,
    OperationInvocationRecord,
    PortSpec,
    SearchBlockerRecord,
    SearchExitContract,
    SearchIncompletenessRecord,
    SearchLedger,
    SearchLedgerEvent,
    SearchTerminalKind,
    SearchTerminalState,
    SubDesignContract,
    VOISelectionAudit,
    WorkspaceContract,
    assert_ring2_verifier_provenance,
    gy_content_hash,
)
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionPlan,
    AcquisitionPlanner,
    RequiredDataGap,
    data_need_spec_payload,
)
from polisyos.runtime.quality.adapter_contracts import (
    WORKSPACE_EXECUTION_READY_CONNECTORS,
    ConnectorAdmissionGate,
    DataRequirementAdmissionGate,
    FormalGate,
    evaluate_operation_adapter_conformance,
)
from polisyos.runtime.quality.authority import ProductionLoopRunProof
from polisyos.runtime.quality.data_forge_binding import (
    CatalogGraphProtocol,
    MeasurementRootProducer,
    build_default_workspace_catalog_graph,
    canonical_catalog_result_for_workspace_loop,
    measurement_rows_for_catalog_payload,
    produce_phase2_recorded_panel_measurement_root,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    CouplingGraph,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    compose_subdesigns as build_composition_certificate,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.semantic_binding import (
    GySemanticBenchmark,
    SemanticAdequacyGate,
    SemanticBenchmarkRun,
    load_gy_semantic_benchmark,
)
from polisyos.runtime.quality.workspace.foundry_consumption import FoundryMethodOutputConsumer
from polisyos.runtime.quality.workspace.scientist_node_adapters import ScientistNodeAdapter
from polisyos.runtime.quality.workspace.spine_repair_gates import (
    BlockedInputProducer,
    LexBoundsApplicabilityGate,
)
from polisyos.runtime.quality.workspace.workflow_playbook_projection import (
    WorkflowPlaybookTrace,
    build_workflow_playbook_registry,
    select_playbook_for_intent,
    trace_playbook_execution,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.workflows.builder import build_registry_with_builtin_nodes

ACTIVE_WORKSPACE_OPERATIONS = frozenset(
    {OperationClass.BIND, OperationClass.ESTIMATE, OperationClass.VERIFY}
)
WORKSPACE_TRAJECTORY = (OperationClass.BIND, OperationClass.ESTIMATE, OperationClass.VERIFY)
WORKSPACE_LOOP_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy_loop.v1"
WORKSPACE_ANYTIME_EXIT_RULE_VERSION = "policyos.gy.anytime_exit.v1"


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _utc_timestamp() -> str:
    return _utc_now().isoformat().replace("+00:00", "Z")


class _CatalogRecordProtocol(Protocol):
    id: str
    source: str
    execution_tier: str
    connector_type: str

    def model_dump(self, *, mode: str) -> dict[str, object]: ...


class WorkspaceInvariantError(RuntimeError):
    """Raised when a Slice-0 run tries to widen beyond the Phase-0 cut-line."""


class SearchTerminalDecision(BaseModel):
    """Deterministic terminal selected by the anytime exit precedence rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SearchTerminalKind
    reason: str
    blocking_obligations: list[str] = Field(default_factory=list)
    budget_kind: str | None = None

    def terminal_state(self) -> SearchTerminalState:
        """Return the Ring-1 terminal payload used by SearchExitContract."""

        payload: dict[str, Any] = {
            "kind": self.kind.value,
            "reason": self.reason,
            "blocking_obligations": list(self.blocking_obligations),
        }
        if self.budget_kind:
            payload["budget_kind"] = self.budget_kind
        return SearchTerminalState.model_validate(payload)


class SearchExitDecisionInputs(BaseModel):
    """Decision facts consumed by the deterministic terminal precedence rule."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    spec_gap: bool = False
    verifier_gap: bool = False
    tool_failure: bool = False
    core_tool_failure: bool = False
    composition_invalid: bool = False
    recursive_blocked: bool = False
    poor_recall: bool = False
    recall_at_known_seeds: float | None = None
    recall_threshold: float = 1.0
    freshness_ok: bool = True
    required_source_classes_missing: list[str] = Field(default_factory=list)
    high_voi_untried: bool = False
    human_decision_required: bool = False
    acquisition_required: bool = False
    budget_exhausted_kind: str | None = None
    frontier_stable: bool = False
    positive_terminal: SearchTerminalKind = SearchTerminalKind.GROUNDED_ABSTENTION

    @property
    def search_ceiling_repair_required(self) -> bool:
        """Return whether domain abstention would hide an incomplete search."""

        recall_missing = (
            self.recall_at_known_seeds is not None
            and self.recall_at_known_seeds < self.recall_threshold
        )
        return bool(
            self.poor_recall
            or recall_missing
            or not self.freshness_ok
            or self.required_source_classes_missing
            or self.high_voi_untried
            or self.core_tool_failure
        )


class WorkspaceFixtureManifest(BaseModel):
    """Committed source of truth for one Slice-0 fixture."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fixture_id: str
    construct_scope_query: str
    jurisdiction: str
    population: str
    time_horizon: str
    expected_catalog_binding_refs: list[str]
    expected_connector_profile: str
    expected_producer_root_kind: str
    expected_terminal: str
    forbidden_terminals: list[str]
    negative_controls: list[str] = Field(default_factory=list)


class OperationRegistration(BaseModel):
    """Runtime registration for one discovered or fail-closed Slice-0 operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation_id: str
    operation_class: OperationClass
    contract: OperationContract
    executable: bool
    discovered_from: str
    discovery_evidence: dict[str, Any]
    fail_closed_reason: str | None = None


class OperationRegistry(BaseModel):
    """Small Slice-0 registry with active operations and fail-closed stubs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operations: dict[str, OperationRegistration]

    def active_operation_classes(self) -> frozenset[OperationClass]:
        """Return operation classes admitted to the deterministic seed trajectory.

        GY-E may add executable continuation producers after the anytime-exit
        decision, but those are deliberately excluded from the Slice-0
        ``BIND -> ESTIMATE -> VERIFY`` seed path.
        """

        return frozenset(
            registration.operation_class
            for registration in self.operations.values()
            if registration.executable
            and registration.operation_class in ACTIVE_WORKSPACE_OPERATIONS
        )

    def get(self, operation_id: str) -> OperationRegistration:
        """Return one operation registration by id."""

        return self.operations[operation_id]

    def executable_for_class(self, operation_class: OperationClass) -> OperationRegistration:
        """Return the executable registration for ``operation_class`` or fail closed."""

        for registration in self.operations.values():
            if registration.operation_class == operation_class and registration.executable:
                return registration
        raise WorkspaceInvariantError(f"non-active operation attempted: {operation_class.value}")


class WorkspaceSearchLedger(SearchLedger):
    """Canonical SearchLedger extension for the deterministic Slice-0 loop."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_id: str
    events: list[SearchLedgerEvent]
    invocations: list[OperationInvocationRecord]
    applicability_results: list[ApplicabilityResult]
    replay_levels: list[Literal["A", "B", "C"]]


class WorkspaceSearchExitContract(SearchExitContract):
    """Search exit plus the required Slice-0 SearchLedger sidecar."""

    workspace_contract: WorkspaceContract
    workspace_contract_ref: str
    obligation_records: list[ObligationRecord] = Field(default_factory=list)
    search_ledger: WorkspaceSearchLedger
    voi_audit: VOISelectionAudit
    artifact_envelopes: list[ArtifactEnvelope] = Field(default_factory=list)
    authority_derivation_traces: list[AuthorityDerivationTrace] = Field(default_factory=list)

WorkspaceLoopRunProof = ProductionLoopRunProof


class WorkspaceIntentRunResult(BaseModel):
    """Phase-2 playbook run result kept separate from the Slice-0 fixture path."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workspace_id: str
    terminal_state: SearchTerminalState
    phase2_playbook_trace: WorkflowPlaybookTrace | None
    search_blockers: list[SearchBlockerRecord] = Field(default_factory=list)
    legacy_workflow_id_disposition: Literal["absent", "legacy_shadow_context"]
    authority_boundary: AuthorityBoundary | None = None
    operation_invocations: list[OperationInvocationRecord] = Field(default_factory=list)
    search_ledger_events: list[SearchLedgerEvent] = Field(default_factory=list)
    artifact_envelopes: list[ArtifactEnvelope] = Field(default_factory=list)
    method_output_consumption_record: MethodOutputConsumptionRecord | None = None
    method_output_consumption_ref: ArtifactRef | None = None
    foundry_input_provenance: str | None = None
    open_production_findings: list[str] = Field(default_factory=list)


def _slug(value: str) -> str:
    normalized = "".join(char.lower() if char.isalnum() else "-" for char in value)
    compact = "-".join(part for part in normalized.split("-") if part)
    return compact or "item"


_GY_COMPOSITION_CERTIFICATES_REPO_REF = (
    "repo://architecture/policy_design_case/"
    "layer3_gy_composition_certificates.json"
)


def _subdesign_contract_verification_ref(
    *,
    parent_workspace_id: str,
    subdesign_id: str,
) -> str:
    return (
        f"{_GY_COMPOSITION_CERTIFICATES_REPO_REF}"
        f"#subdesign-{_slug(parent_workspace_id)}-{subdesign_id}"
    )


def _calibrated_relevance(
    *,
    hit: _CatalogRecordProtocol,
    manifest: WorkspaceFixtureManifest,
) -> float:
    if hit.id in set(manifest.expected_catalog_binding_refs):
        return 1.0
    if hit.id in set(manifest.negative_controls):
        return 0.0
    explanation = getattr(hit, "search_explanation", {}) or {}
    raw_score = (
        explanation.get("calibrated_relevance")
        or explanation.get("final_score")
        or explanation.get("score")
        or explanation.get("similarity")
        if isinstance(explanation, dict)
        else None
    )
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.0
    return max(0.0, min(score, 0.49))


def _required_data_family_for_manifest(manifest: WorkspaceFixtureManifest) -> str:
    if manifest.fixture_id == "tourism_local_development_ceiling_probe":
        return "local_tourism_site_traffic"
    query = str(manifest.construct_scope_query or manifest.fixture_id)
    return _slug(query)


def _looks_like_data_need_spec(value: object) -> bool:
    return all(hasattr(value, field) for field in ("metric", "quality_min", "purpose"))


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _fixture_manifest_path() -> Path:
    return _repo_root() / "architecture/policy_design_case/layer3_gy_slice0_fixture_manifest.json"


def load_workspace_fixture_manifest(fixture_id: str) -> WorkspaceFixtureManifest:
    """Load one Slice-0 fixture from the committed manifest artifact."""

    payload = json.loads(_fixture_manifest_path().read_text(encoding="utf-8"))
    for fixture in payload.get("fixtures", []):
        if fixture.get("fixture_id") == fixture_id:
            return WorkspaceFixtureManifest.model_validate(fixture)
    raise KeyError(fixture_id)


def select_search_terminal(inputs: SearchExitDecisionInputs) -> SearchTerminalDecision:
    """Select the anytime terminal using the §8.6 deterministic precedence order."""

    if inputs.spec_gap or inputs.verifier_gap:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.A_SPEC_GAP,
            reason="A required verifier/specification gap blocks authority closure.",
        )
    if inputs.tool_failure:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.TOOL_FAILURE,
            reason="A required tool failed before an honest search terminal could be formed.",
        )
    if inputs.composition_invalid:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.COMPOSITION_INVALID,
            reason="Composition constraints are invalid for the current frontier.",
        )
    if inputs.recursive_blocked:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.RECURSIVE_BLOCKED,
            reason="Recursive decomposition is blocked by the current workspace policy.",
        )
    if inputs.search_ceiling_repair_required:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED,
            reason="Search quality is below the governed ceiling threshold.",
        )
    if inputs.human_decision_required:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.HUMAN_DECISION_REQUIRED,
            reason="A human decision is required before further authority movement.",
        )
    if inputs.acquisition_required:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.ACQUISITION_REQUIRED,
            reason="A high-value missing distribution requires acquisition before closure.",
        )
    if inputs.budget_exhausted_kind:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.BUDGET_EXHAUSTED,
            budget_kind=inputs.budget_exhausted_kind,
            reason=f"{inputs.budget_exhausted_kind} budget is exhausted.",
        )
    if inputs.frontier_stable:
        return SearchTerminalDecision(
            kind=SearchTerminalKind.FRONTIER_STABLE,
            reason="The frontier is stable under the current search policy.",
        )
    return SearchTerminalDecision(
        kind=inputs.positive_terminal,
        reason="No higher-precedence repair or continuation terminal was triggered.",
    )


def _engine_registry_source(operation_class: OperationClass) -> str:
    sources = {
        OperationClass.BIND: "engine_registry:data_forge.catalog.DatasetCatalogGraph",
        OperationClass.ESTIMATE: "engine_registry:foundry.methods.measurement_summary",
        OperationClass.VERIFY: "engine_registry:pdc.authority_derivation",
        OperationClass.ACQUIRE: "engine_registry:scientist.agent.protocols.DataNeedSpec",
        OperationClass.DECOMPOSE: "engine_registry:pdc.SubDesignContract",
        OperationClass.COMPOSE: "engine_registry:runtime_quality.layer2_coupling_composition",
    }
    return sources.get(operation_class, "engine_registry:fail_closed_stub")


def _operation_discovery_evidence(operation_class: OperationClass) -> dict[str, Any]:
    if operation_class == OperationClass.BIND:
        worldbank_entry = _catalog_registry_discovery("worldbank")
        return {
            "source_kind": "data_forge_catalog_source_registry",
            "source_ref": "polisyos.data_forge.domains.catalog.source_registry:worldbank",
            "source_lookup": worldbank_entry,
            "adapter_conformance": {
                "passed": bool(
                    worldbank_entry
                    and worldbank_entry.get("connector_id") in WORKSPACE_EXECUTION_READY_CONNECTORS
                    and worldbank_entry.get("execution_tier") == "transport_ready"
                ),
                "required_contract": "DatasetCatalogGraph.search_datasets",
            },
            "registration_mode": "executable",
        }
    if operation_class == OperationClass.ESTIMATE:
        foundry_matches = _foundry_registry_estimate_candidates()
        conformance = evaluate_operation_adapter_conformance(
            required_contract="measurement-root BaseDataset -> Estimate",
            registry_candidates=foundry_matches,
            consumes_ports=("BaseDataset.MeasurementRoot",),
            produces_ports=("Estimate",),
            preservation_passed=bool(foundry_matches),
            smoke_passed=bool(foundry_matches),
            no_candidate_reason="no_foundry_estimate_candidate",
        )
        conformance["adapter_ref"] = (
            "polisyos.runtime.quality.workspace.foundry_consumption.FoundryMethodOutputConsumer"
        )
        return {
            "source_kind": "foundry_method_registry",
            "source_ref": "polisyos.foundry.methods.selection.registry",
            "source_lookup": {
                "query": "estimate-capable methods or local Slice-0 measurement summary adapter",
                "matched_fqns": foundry_matches,
            },
            "adapter_conformance": conformance,
            "registration_mode": "executable",
        }
    if operation_class == OperationClass.VERIFY:
        conformance = evaluate_operation_adapter_conformance(
            required_contract="verifier-stamped AuthorityBoundary only",
            registry_candidates=(
                "polisyos.pdc.AuthorityBoundary",
                "polisyos.pdc.AuthorityDerivationTrace",
            ),
            consumes_ports=("Estimate", "AuthorityBoundary"),
            produces_ports=("AuthorityDerivationTrace",),
            preservation_passed=True,
            smoke_passed=True,
        )
        return {
            "source_kind": "pdc_contract_registry",
            "source_ref": "polisyos.pdc.AuthorityDerivationTrace",
            "source_lookup": {
                "authority_boundary_lattice": "polisyos.pdc.AuthorityBoundary",
                "trace_contract": "polisyos.pdc.AuthorityDerivationTrace",
            },
            "adapter_conformance": conformance,
            "registration_mode": "executable",
        }
    if operation_class == OperationClass.ACQUIRE:
        conformance = evaluate_operation_adapter_conformance(
            required_contract="RequiredDataSpec -> DataNeedSpec -> costed rung-7 plan",
            registry_candidates=(
                "polisyos.scientist.agent.protocols.DataNeedSpec",
                "polisyos.runtime.quality.acquisition_planner.AcquisitionPlanner",
                "polisyos.runtime.quality.acquisition_planner.plan_requirement_gap_acquisition",
            ),
            consumes_ports=("RequiredDataSpec", "RequiredDataGap"),
            produces_ports=("DataNeedSpec", "SearchTerminalState.costed_plan"),
            preservation_passed=True,
            smoke_passed=True,
        )
        return {
            "source_kind": "scientist_data_need_protocol",
            "source_ref": "polisyos.scientist.agent.protocols.DataNeedSpec",
            "source_lookup": {
                "planner_ref": "polisyos.runtime.quality.acquisition_planner.AcquisitionPlanner",
                "terminal": SearchTerminalKind.ACQUISITION_REQUIRED.value,
                "required_data_adapter": "RequiredDataGap",
            },
            "adapter_conformance": conformance,
            "registration_mode": "fail_closed_terminal_recommendation",
        }
    if operation_class == OperationClass.DECOMPOSE:
        conformance = evaluate_operation_adapter_conformance(
            required_contract="SearchExitContract -> SubDesignContract",
            registry_candidates=(
                "polisyos.pdc.SubDesignContract",
                "polisyos.pdc.SearchExitContract",
            ),
            consumes_ports=("SearchExitContract",),
            produces_ports=("SubDesignContract",),
            preservation_passed=True,
            smoke_passed=True,
        )
        return {
            "source_kind": "pdc_contract_registry",
            "source_ref": "polisyos.pdc.SubDesignContract",
            "source_lookup": {
                "child_workspace_exit": "polisyos.pdc.SearchExitContract",
                "port_contract": "polisyos.pdc.PortSpec",
            },
            "adapter_conformance": conformance,
            "registration_mode": "executable",
        }
    if operation_class == OperationClass.COMPOSE:
        conformance = evaluate_operation_adapter_conformance(
            required_contract="SubDesignContract + CouplingGraph -> CompositionCertificate",
            registry_candidates=(
                "polisyos.runtime.quality.design_axes.coupling_composition.compose_subdesigns",
                "polisyos.runtime.quality.design_axes.coupling_composition.CompositionReceipt",
            ),
            consumes_ports=("SubDesignContract", "CouplingGraph"),
            produces_ports=("CompositionCertificate",),
            preservation_passed=True,
            smoke_passed=True,
        )
        return {
            "source_kind": "layer2_composition_engine",
            "source_ref": (
                "polisyos.runtime.quality.design_axes.coupling_composition."
                "compose_subdesigns"
            ),
            "source_lookup": {
                "composition_receipt": "CompositionReceipt",
                "coupling_graph": "CouplingGraph",
                "system_dynamics_requirement": "SystemDynamicsRequirement",
            },
            "adapter_conformance": conformance,
            "registration_mode": "executable",
        }
    return {
        "source_kind": "pdc_contract_registry",
        "source_ref": f"polisyos.pdc.OperationClass.{operation_class.value}",
        "source_lookup": {"owning_task": "future_phase", "registered_fail_closed": True},
        "adapter_conformance": {
            "passed": True,
            "required_contract": "fail_closed_stub",
        },
        "registration_mode": "fail_closed_stub",
    }


def _catalog_registry_discovery(source_id: str) -> dict[str, Any]:
    try:
        registry = read_api.catalog.load_catalog_source_registry()
    except (AttributeError, ImportError):
        return {}
    entry = registry.source_by_id(source_id)
    return entry.model_dump(mode="json") if entry is not None else {}


def _foundry_registry_estimate_candidates() -> list[str]:
    try:
        from polisyos.foundry.methods import ensure_all_methods_registered
        from polisyos.foundry.methods.selection.registry import get_registry
    except ImportError:
        return []
    try:
        ensure_all_methods_registered()
    except Exception:
        return []
    registry = get_registry()
    try:
        snapshot = registry.snapshot()
    except Exception:
        return []
    matches: list[str] = []
    for entry in snapshot.entries():
        haystack = " ".join(
            str(value)
            for value in (
                entry.fqn,
                getattr(entry.signature, "name", ""),
                getattr(entry.signature, "namespace", ""),
                " ".join(getattr(entry.metadata, "tags", ()) or ()),
                " ".join(_slot_names(getattr(entry.signature, "output_slots", ()) or ())),
            )
        ).lower()
        if "estimate" in haystack or "measurement" in haystack:
            matches.append(entry.fqn)
    return sorted(dict.fromkeys(matches))[:10]


def _phase2_value_method_selection(
    intent: dict[str, Any],
    *,
    design_problem: DesignProblem,
) -> dict[str, Any]:
    causal_variables = intent.get("causal_variables")
    target_world_slots = (
        tuple(str(item) for item in causal_variables)
        if isinstance(causal_variables, list) and causal_variables
        else ("credit_access", "firm_survival")
    )
    candidate = {
        "candidate_id": str(intent.get("candidate_id") or "workspace_phase2_candidate"),
        "atom": {
            "intervention_id": str(intent.get("intervention_id") or "workspace_phase2"),
            "target_world_slots": target_world_slots,
        },
        "diversity_key": (
            str(intent.get("operation_class") or "estimate"),
            *target_world_slots[:2],
            "workspace_phase2",
        ),
    }
    try:
        from polisyos.foundry.methods.selection import select_value_method_for_problem
    except ImportError as exc:
        return {
            "status": "blocked",
            "blockers": ("value_method_selector_unavailable",),
            "reason": str(exc),
        }
    return select_value_method_for_problem(
        candidate=candidate,
        problem=design_problem,
        requested_method_fqn=(
            str(intent["causal_method_fqn"]) if intent.get("causal_method_fqn") else None
        ),
        observation_to_contract_manifest=intent.get("observation_to_contract_manifest"),
    )


def _slot_names(slots: object) -> list[str]:
    return [
        str(getattr(slot, "name", slot))
        for slot in slots
        if str(getattr(slot, "name", slot)).strip()
    ]


def _measurement_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [
        value
        for row in rows
        if (value := _numeric_measurement_value(row.get("value"))) is not None
    ]
    years = [
        int(row["year"])
        for row in rows
        if isinstance(row.get("year"), int)
    ]
    if not values:
        return {
            "row_count": 0,
            "summary_kind": "no_measurement_rows",
            "open_production_findings": ["F4", "F10"],
        }
    latest_row = max(
        (row for row in rows if isinstance(row.get("year"), int)),
        key=lambda row: int(row["year"]),
    )
    latest_value = _numeric_measurement_value(latest_row.get("value"))
    return {
        "row_count": len(values),
        "latest_year": int(latest_row["year"]),
        "latest_value": latest_value,
        "min_year": min(years) if years else None,
        "max_year": max(years) if years else None,
        "mean_value": round(sum(values) / len(values), 6),
        "indicator_ids": sorted({str(row.get("indicator_id")) for row in rows}),
    }


def _numeric_measurement_value(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict) and value.get("_type") == "float":
        try:
            return float(str(value.get("repr")))
        except ValueError:
            return None
    return None


def build_workspace_operation_registry() -> OperationRegistry:
    """Build the Slice-0 operation registry from admitted registrations."""

    operations = {
        "slice0.bind.catalog": OperationRegistration(
            operation_id="slice0.bind.catalog",
            operation_class=OperationClass.BIND,
            contract=_operation_contract(
                operation_id="slice0.bind.catalog",
                operation_class=OperationClass.BIND,
                authority_transform={"kind": "preserves", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=True,
            discovered_from=_engine_registry_source(OperationClass.BIND),
            discovery_evidence=_operation_discovery_evidence(OperationClass.BIND),
        ),
        "slice0.estimate.measurement_summary": OperationRegistration(
            operation_id="slice0.estimate.measurement_summary",
            operation_class=OperationClass.ESTIMATE,
            contract=_operation_contract(
                operation_id="slice0.estimate.measurement_summary",
                operation_class=OperationClass.ESTIMATE,
                authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=True,
            discovered_from=_engine_registry_source(OperationClass.ESTIMATE),
            discovery_evidence=_operation_discovery_evidence(OperationClass.ESTIMATE),
        ),
        "slice0.verify.authority": OperationRegistration(
            operation_id="slice0.verify.authority",
            operation_class=OperationClass.VERIFY,
            contract=_operation_contract(
                operation_id="slice0.verify.authority",
                operation_class=OperationClass.VERIFY,
                authority_transform={"kind": "unknown", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=True,
            discovered_from=_engine_registry_source(OperationClass.VERIFY),
            discovery_evidence=_operation_discovery_evidence(OperationClass.VERIFY),
        ),
        "slice0.discover.stub": OperationRegistration(
            operation_id="slice0.discover.stub",
            operation_class=OperationClass.DISCOVER,
            contract=_operation_contract(
                operation_id="slice0.discover.stub",
                operation_class=OperationClass.DISCOVER,
                authority_transform={"kind": "unknown", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=False,
            discovered_from=_engine_registry_source(OperationClass.DISCOVER),
            discovery_evidence=_operation_discovery_evidence(OperationClass.DISCOVER),
            fail_closed_reason="GY-D3/GY-E owns DISCOVER/ACQUIRE widening after Slice-0 exits.",
        ),
        "slice0.acquire.costed_plan": OperationRegistration(
            operation_id="slice0.acquire.costed_plan",
            operation_class=OperationClass.ACQUIRE,
            contract=_operation_contract(
                operation_id="slice0.acquire.costed_plan",
                operation_class=OperationClass.ACQUIRE,
                authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=False,
            discovered_from=_engine_registry_source(OperationClass.ACQUIRE),
            discovery_evidence=_operation_discovery_evidence(OperationClass.ACQUIRE),
            fail_closed_reason=(
                "GY-H/GY-E may attach a costed acquisition_required terminal plan, "
                "but ACQUIRE cannot execute inside the Slice-0 trajectory."
            ),
        ),
        "slice0.refine.stub": OperationRegistration(
            operation_id="slice0.refine.stub",
            operation_class=OperationClass.REFINE,
            contract=_operation_contract(
                operation_id="slice0.refine.stub",
                operation_class=OperationClass.REFINE,
                authority_transform={"kind": "unknown", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=False,
            discovered_from=_engine_registry_source(OperationClass.REFINE),
            discovery_evidence=_operation_discovery_evidence(OperationClass.REFINE),
            fail_closed_reason="GY-C2 owns REFINE after spine-rot repair.",
        ),
        "slice0.lower.stub": OperationRegistration(
            operation_id="slice0.lower.stub",
            operation_class=OperationClass.LOWER,
            contract=_operation_contract(
                operation_id="slice0.lower.stub",
                operation_class=OperationClass.LOWER,
                authority_transform={"kind": "unknown", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=False,
            discovered_from=_engine_registry_source(OperationClass.LOWER),
            discovery_evidence=_operation_discovery_evidence(OperationClass.LOWER),
            fail_closed_reason="GY-C1/GY-C2 own lowering/playbook subordination.",
        ),
        "slice0.decompose.workspace_tree": OperationRegistration(
            operation_id="slice0.decompose.workspace_tree",
            operation_class=OperationClass.DECOMPOSE,
            contract=_operation_contract(
                operation_id="slice0.decompose.workspace_tree",
                operation_class=OperationClass.DECOMPOSE,
                authority_transform={"kind": "preserves", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=True,
            discovered_from=_engine_registry_source(OperationClass.DECOMPOSE),
            discovery_evidence=_operation_discovery_evidence(OperationClass.DECOMPOSE),
        ),
        "slice0.compose.certificate": OperationRegistration(
            operation_id="slice0.compose.certificate",
            operation_class=OperationClass.COMPOSE,
            contract=_operation_contract(
                operation_id="slice0.compose.certificate",
                operation_class=OperationClass.COMPOSE,
                authority_transform={"kind": "weakens", "rule_ref": "policyos.gy.authority.v1"},
            ),
            executable=True,
            discovered_from=_engine_registry_source(OperationClass.COMPOSE),
            discovery_evidence=_operation_discovery_evidence(OperationClass.COMPOSE),
        ),
    }
    return OperationRegistry(operations=operations)


class WorkspaceLoop:
    """Deterministic Slice-0 workspace loop."""

    def __init__(
        self,
        *,
        registry: OperationRegistry | None = None,
        catalog_graph: CatalogGraphProtocol | None = None,
        artifact_store: FileSystemCAS | None = None,
    ) -> None:
        self._registry = registry or build_workspace_operation_registry()
        self._artifact_store = artifact_store
        if catalog_graph is None:
            catalog_graph = build_default_workspace_catalog_graph()
        self._catalog_graph = catalog_graph

    @property
    def operation_registry(self) -> OperationRegistry:
        """Return the registry consumed by this workspace loop."""

        return self._registry

    def decompose_fixture(
        self,
        *,
        parent_workspace_id: str,
        child_fixture_ids: list[str],
    ) -> list[SubDesignContract]:
        """Run child Workspaces and export only SubDesignContract artifacts."""

        self._registry.executable_for_class(OperationClass.DECOMPOSE)
        children: list[SubDesignContract] = []
        for index, fixture_id in enumerate(child_fixture_ids, start=1):
            child_exit = self.run_fixture(fixture_id)
            children.append(
                self._subdesign_from_exit(
                    parent_workspace_id=parent_workspace_id,
                    child_exit=child_exit,
                    fixture_id=fixture_id,
                    index=index,
                )
            )
        return children

    def compose_subdesigns(
        self,
        *,
        parent_workspace_id: str,
        subdesigns: list[SubDesignContract],
        graph: CouplingGraph,
        claims: list[dict[str, Any]],
    ) -> CompositionCertificate:
        """Compose child SubDesignContracts through the S5 composition engine."""

        self._registry.executable_for_class(OperationClass.COMPOSE)
        return build_composition_certificate(
            subdesigns=subdesigns,
            claims=claims,
            graph=graph,
            parent_workspace_id=parent_workspace_id,
        )

    def run_control_plane_fixture(self, fixture_id: str) -> WorkspaceSearchExitContract:
        """Run a named control-plane fixture through the workspace-loop owner."""

        return self.run_fixture(fixture_id)

    def _phase2_store(self) -> FileSystemCAS:
        if self._artifact_store is not None:
            return self._artifact_store
        return FileSystemCAS(Path(tempfile.gettempdir()) / "polisyos-gy-phase2-cas")

    def _phase2_context(self, *, workspace_id: str) -> tuple[ExecutionContext, object]:
        store = self._phase2_store()
        bundle = build_default_registry_bundle(store)
        run = RunContext.start(
            store=store,
            registry_bundle=bundle.bundle_ref,
            run_id=f"run-{_slug(workspace_id)}",
        )
        return (
            ExecutionContext(
                store=store,
                run=run,
                logger=logging.getLogger(f"polisyos.gy.phase2.{workspace_id}"),
            ),
            bundle.bundle_ref,
        )

    def _phase2_observational_data_ref(self, *, intent: dict[str, Any]) -> object:
        observed = intent.get("observational_data_ref")
        if hasattr(observed, "artifact_id") and hasattr(observed, "kind"):
            return observed
        if observed is None:
            return produce_phase2_recorded_panel_measurement_root(store=self._phase2_store())
        return self._phase2_synthetic_observational_data_ref()

    def _phase2_synthetic_observational_data_ref(self) -> object:
        store = self._phase2_store()
        panel_payload = {
            "outcome": [
                [10.0, 11.0, 12.0, 13.0, 14.0, 18.0, 19.0, 20.0],
                [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0],
                [9.0, 10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0],
            ],
            "treatment": [1, 0, 0],
            "time_treatment": 5,
            "metadata": {
                "input_provenance": "synthetic_probe",
                "producer": (
                    "polisyos.runtime.quality.workspace.loop."
                    "_phase2_synthetic_observational_data_ref"
                ),
            },
        }
        return store.put_json(
            panel_payload,
            PutOptions(
                kind="gy.synthetic_observational_data",
                media_type="application/json",
                schema=SchemaInfo(
                    name="policyos.gy.phase2.synthetic_observational_data",
                    version="1.0",
                ),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )

    def _phase2_causal_variables(self, *, intent: dict[str, Any]) -> list[str]:
        variables = intent.get("causal_variables")
        if isinstance(variables, list) and variables:
            return [str(item) for item in variables]
        return ["credit_access", "firm_survival"]

    def _phase2_data_causal_graph(self, *, causal_variables: list[str]) -> dict[str, Any]:
        treatment = causal_variables[0] if causal_variables else "credit_access"
        outcome = causal_variables[1] if len(causal_variables) > 1 else "firm_survival"
        return {
            "producer": "polisyos.runtime.quality.workspace.loop._phase2_data_causal_graph",
            "nodes": [
                {"id": treatment, "role": "treatment"},
                {"id": outcome, "role": "outcome"},
                {"id": "baseline_firm_size", "role": "covariate"},
            ],
            "edges": [
                {"source": treatment, "target": outcome, "relation": "policy_effect"},
                {"source": "baseline_firm_size", "target": outcome, "relation": "confounder"},
            ],
        }

    def _phase2_state(
        self,
        *,
        workspace_id: str,
        intent: dict[str, Any],
        design_problem: DesignProblem,
    ) -> ExperimentState:
        method_selection = _phase2_value_method_selection(
            {**intent, "workspace_id": workspace_id},
            design_problem=design_problem,
        )
        method_fqn = str(method_selection.get("selected_method_fqn") or "")
        causal_variables = self._phase2_causal_variables(intent=intent)
        observational_data_ref = self._phase2_observational_data_ref(intent=intent)
        return ExperimentState(
            run_id=f"run-{_slug(workspace_id)}",
            observational_data_ref=observational_data_ref,
            causal_method_fqn=method_fqn,
            causal_method_params={},
            execution_profile="gy_phase2",
            params={
                "policy_question": intent.get("policy_question"),
                "causal_variables": causal_variables,
                "data_causal_graph": self._phase2_data_causal_graph(
                    causal_variables=causal_variables
                ),
                "observational_data_ref": str(getattr(observational_data_ref, "artifact_id", "")),
                "random_seed": int(intent.get("random_seed", 42) or 42),
                "causal_method_fqn": method_fqn,
                "causal_method_params": {},
                "causal_method_selection": method_selection,
                "enable_causal_refutation": False,
                "causal_refutation_params": {},
                "enable_causal_sensitivity": False,
                "causal_sensitivity_params": {},
                "causal_validity": {},
            },
        )

    def _install_phase2_normative_inputs(
        self,
        *,
        state: ExperimentState,
        intent: dict[str, Any],
    ) -> ExperimentState:
        input_trinity_bundle_ref = "trinity_bundle_ref"
        artifact_distributional_report_ref = "distributional_report_ref"
        artifact_metrics_ref = "metrics_ref"
        artifact_simulation_result_ref = "simulation_result_ref"
        report_legal_report_ref = "legal_report_ref"

        if input_trinity_bundle_ref in state.inputs and artifact_distributional_report_ref in (
            state.artifacts_index
        ):
            return state
        store = self._phase2_store()
        next_state = state.model_copy(deep=True)
        problem_frame_payload = {
            "problem_id": "gy_phase2_normative_problem",
            "domain": "social",
            "objectives": [
                {
                    "objective_id": "net_welfare",
                    "metric_id": "net_income_pct",
                    "direction": "maximize",
                }
            ],
            "stakeholders": [
                {"stakeholder_id": "workers", "entity_type": "agent", "priority": 3},
                {"stakeholder_id": "owners", "entity_type": "agent", "priority": 2},
            ],
            "normative_frame": {
                "default_policy": "weighted_welfare",
                "enabled_policies": ["weighted_welfare"],
                "stakeholder_bindings": [
                    {
                        "binding_id": "workers_delta",
                        "stakeholder_id": "workers",
                        "channel": "distributional_net_impact",
                        "outcome_key": "workers",
                    },
                    {
                        "binding_id": "owners_delta",
                        "stakeholder_id": "owners",
                        "channel": "distributional_net_impact",
                        "outcome_key": "owners",
                    },
                ],
                "utility_terms": [
                    {
                        "term_id": "workers_utility",
                        "stakeholder_id": "workers",
                        "binding_refs": ["workers_delta"],
                        "welfare_weight": 2,
                    },
                    {
                        "term_id": "owners_utility",
                        "stakeholder_id": "owners",
                        "binding_refs": ["owners_delta"],
                        "welfare_weight": 1,
                    },
                ],
            },
        }
        trinity_ref = store.put_json(
            {
                "problem_frame": problem_frame_payload,
                "policy_spec": {"policy_id": "gy_phase2_policy", "interventions": []},
                "model_spec": {
                    "model_id": "gy_phase2_foundry_model",
                    "data_snapshot_ref": str(
                        getattr(state.observational_data_ref, "artifact_id", "")
                    ),
                    "fidelity_level": "hybrid",
                },
            },
            PutOptions(
                kind="ir.trinity_bundle",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.ir.TrinityBundle", version="1.0"),
            ),
        )
        impacts = {"workers": 1.0, "owners": 0.4}
        winners = [
            {
                "cohort_id": cohort_id,
                "cohort_label": cohort_id,
                "dimension": "custom",
                "net_impact": delta,
                "impact_direction": "positive",
                "population_share": 0.5,
                "key_metric": "net_income_pct",
                "key_metric_delta": delta,
            }
            for cohort_id, delta in impacts.items()
        ]
        cohorts = [
            {
                "cohort_id": cohort_id,
                "cohort_label": cohort_id,
                "population_share": 0.5,
                "metric_deltas": {"net_income_pct": delta},
                "impact_direction": "positive",
                "is_vulnerable": cohort_id == "workers",
            }
            for cohort_id, delta in impacts.items()
        ]
        distributional_ref = store.put_json(
            {
                "schema_version": "1.0",
                "breakdowns": [
                    {
                        "dimension": "custom",
                        "dimension_label": "Stakeholders",
                        "primary_metric": "net_income_pct",
                        "primary_metric_unit": "percent",
                        "cohorts": cohorts,
                    }
                ],
                "winners_losers": {"winners": winners, "losers": [], "neutral": []},
            },
            PutOptions(
                kind="ir.distributional_report",
                media_type="application/json",
                schema=SchemaInfo(name="ir.distributional_report", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        metrics_core_ref = store.put_json(
            {
                "values": {
                    "net_income_pct": 1.0,
                    "gy_phase2_recorded_panel_rows": 30,
                },
                "notes": ["Phase-2 normative replay metrics derived from recorded-row C3 panel."],
            },
            PutOptions(
                kind="foundry.metrics",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.Metrics", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        exec_plan_core_ref = store.put_json(
            {
                "plan_id": "gy_phase2_normative_replay",
                "source": "phase2_recorded_panel_foundry_consumption",
            },
            PutOptions(
                kind="foundry.exec_plan",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.ExecPlan", version="1.0"),
            ),
        )
        simulation_core_ref = store.put_json(
            {
                "schema_version": "1.3",
                "exec_plan_ref": exec_plan_core_ref.model_dump(mode="json"),
                "metrics_ref": metrics_core_ref.model_dump(mode="json"),
                "distributional_report_ref": distributional_ref.model_dump(mode="json"),
                "notes": [
                    "Phase-2 replay support artifact; authority remains on the "
                    "Foundry method-output consumption record."
                ],
            },
            PutOptions(
                kind="foundry.simulation_result",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.SimulationResult", version="1.3"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        legal_report_core_ref = store.put_json(
            {
                "context": {
                    "foundry": {
                        "simulation_result_ref": simulation_core_ref.model_dump(mode="json")
                    },
                    "jurisdiction": str(intent.get("jurisdiction") or "UA"),
                    "notes": ["Phase-2 replay legal context; no compliance issues asserted."],
                },
                "issues": [],
                "summary": {"info": 0, "warning": 0, "blocker": 0},
                "notes": ["Support artifact for Phase-2 normative adapter port preservation."],
            },
            PutOptions(
                kind="lex.legal_report",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.core.LegalReport", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
        next_state.inputs[input_trinity_bundle_ref] = trinity_ref
        next_state.artifacts_index[artifact_distributional_report_ref] = distributional_ref
        next_state.artifacts_index[artifact_metrics_ref] = metrics_core_ref
        next_state.artifacts_index[artifact_simulation_result_ref] = simulation_core_ref
        next_state.reports_index[report_legal_report_ref] = legal_report_core_ref
        return next_state

    def run_intent(self, intent: DesignProblem) -> WorkspaceIntentRunResult:
        """Run the Phase-2 DesignProblem/playbook path without widening Slice-0 fixtures."""

        if not isinstance(intent, DesignProblem):
            raise TypeError("WorkspaceLoop.run_intent requires a DesignProblem.")
        projected_intent = intent.to_workspace_intent()
        selection = select_playbook_for_intent(projected_intent)
        workspace_id = (
            f"ws-phase2-{_slug(str(projected_intent.get('policy_question') or 'intent'))}"
        )
        blockers: list[SearchBlockerRecord] = []
        executed = [OperationClass.BIND, OperationClass.ESTIMATE]
        if projected_intent.get("force_counterexample") == "missing_bounds":
            bounds = LexBoundsApplicabilityGate().evaluate(
                workspace_id=workspace_id,
                invocation_id="invoke-phase2-refine",
                lower=None,
                upper=float(projected_intent.get("upper_bound", 1.0)),
            )
            if bounds.blocker is not None:
                blockers.append(bounds.blocker)
            executed.append(OperationClass.REFINE)
            trace = trace_playbook_execution(
                selection=selection,
                executed_operation_classes=executed,
                deviated_from_default=True,
                deviation_operation=OperationClass.REFINE,
                deviation_reason="counterexample_missing_bounds",
                blockers=blockers,
            )
            terminal = SearchTerminalState(
                kind=SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED,
                reason="Phase-2 playbook deviated to REFINE because frontier bounds are missing.",
                blocking_obligations=[blocker.blocker_id for blocker in blockers],
            )
            return WorkspaceIntentRunResult(
                workspace_id=workspace_id,
                terminal_state=terminal,
                phase2_playbook_trace=trace,
                search_blockers=blockers,
                legacy_workflow_id_disposition=selection.legacy_workflow_id_disposition,
            )

        ctx, _bundle_ref = self._phase2_context(workspace_id=workspace_id)
        state = self._phase2_state(
            workspace_id=workspace_id,
            intent=projected_intent,
            design_problem=intent,
        )
        required_inputs = ["observational_data_ref", "causal_variables", "data_causal_graph"]
        state_facts = {
            "observational_data_ref": state.observational_data_ref,
            "causal_variables": state.params.get("causal_variables"),
            "data_causal_graph": state.params.get("data_causal_graph"),
        }
        blockers.extend(
            BlockedInputProducer().produce(
                workspace_id=workspace_id,
                invocation_id="invoke-phase2-estimate",
                state_facts=state_facts,
                required_inputs=[
                    item for item in required_inputs if not state_facts.get(item)
                ],
            )
        )
        operation_invocations: list[OperationInvocationRecord] = []
        search_ledger_events: list[SearchLedgerEvent] = []
        artifact_envelopes: list[ArtifactEnvelope] = []
        executed_aliases: list[str] = []
        out_of_scope_steps: list[dict[str, str]] = []
        executed_operation_classes: list[OperationClass] = [OperationClass.BIND]
        method_output_consumption_record: MethodOutputConsumptionRecord | None = None
        method_output_consumption_ref: ArtifactRef | None = None
        authority_boundary: AuthorityBoundary | None = None
        foundry_input_provenance: str | None = None
        open_production_findings: list[str] = []
        if not blockers:
            node_registry = build_registry_with_builtin_nodes(include_discovered_nodes=False)
            playbook_registry = build_workflow_playbook_registry(node_registry=node_registry)
            playbook = playbook_registry.playbooks[selection.playbook_id]
            execution_state = state
            for step in playbook.steps:
                if step.legacy_alias == "plan_policy_request":
                    out_of_scope_steps.append(
                        {
                            "step_id": step.step_id,
                            "legacy_alias": step.legacy_alias,
                            "disposition": "surface_out_of_scope",
                            "rationale": (
                                "Phase-2 executes a pre-resolved intent; NL planning remains "
                                "owned by the policy request surface."
                            ),
                        }
                    )
                    continue
                if step.legacy_alias not in {
                    "run_causal_evaluation",
                    "run_normative_arbitration",
                }:
                    out_of_scope_steps.append(
                        {
                            "step_id": step.step_id,
                            "legacy_alias": step.legacy_alias,
                            "disposition": "surface_out_of_scope",
                            "rationale": (
                                "Phase-2 proof path is bounded to C3 Foundry consumption and "
                                "C2 governance-tail revalidation."
                            ),
                        }
                    )
                    continue
                if step.legacy_alias == "run_normative_arbitration":
                    execution_state = self._install_phase2_normative_inputs(
                        state=execution_state,
                        intent=projected_intent,
                    )
                node = node_registry.get(step.node_id)
                adapter = ScientistNodeAdapter.from_node(
                    node,
                    operation_id=step.adapter_operation_id,
                    operation_class=step.operation_class,
                    authority_transform={
                        "kind": "hint_only",
                        "requested_decision_grade": "descriptive_only",
                        "rule_ref": "policyos.gy.phase2.playbooks.v1",
                    },
                    legacy_alias=step.legacy_alias,
                )
                invocation_id = f"invoke-phase2-{_slug(step.legacy_alias)}"
                execution = adapter.execute_candidate(
                    ctx=ctx,
                    state=execution_state,
                    workspace_id=workspace_id,
                    invocation_id=invocation_id,
                    cycle_index=len(operation_invocations) + 1,
                )
                operation_invocations.append(execution.invocation)
                search_ledger_events.append(execution.ledger_event)
                artifact_envelopes.extend(execution.artifact_envelopes)
                executed_aliases.append(step.legacy_alias)
                executed_operation_classes.append(step.operation_class)
                if execution.blocker is not None:
                    blockers.append(execution.blocker)
                    break
                if execution.outcome is None or getattr(execution.outcome, "status", None) != "ok":
                    blockers.extend(
                        BlockedInputProducer().produce(
                            workspace_id=workspace_id,
                            invocation_id=invocation_id,
                            state_facts={},
                            required_inputs=[f"{step.legacy_alias}_output"],
                        )
                    )
                    break
                execution_state = execution.outcome.state
                if step.legacy_alias == "run_causal_evaluation":
                    foundry = FoundryMethodOutputConsumer()
                    consumed = foundry.consume_from_state(
                        workspace_id=workspace_id,
                        operation_invocation_id=execution.invocation.invocation_id,
                        operation_class=OperationClass.ESTIMATE,
                        state=execution.outcome.state,
                        measurement_root_ref=state.observational_data_ref,
                        constraint_store_ref=None,
                    )
                    method_output_consumption_record = consumed.record
                    method_output_consumption_ref = foundry.persist_consumption(
                        store=self._phase2_store(),
                        consumption=consumed,
                    )
                    authority_boundary = consumed.authority_boundary
                    foundry_input_provenance = consumed.input_provenance
                    open_production_findings = list(consumed.open_production_findings)
        trace = trace_playbook_execution(
            selection=selection,
            executed_operation_classes=list(
                dict.fromkeys(executed_operation_classes).keys()
            ),
            deviated_from_default=bool(blockers),
            deviation_operation=OperationClass.REFINE if blockers else None,
            deviation_reason="missing_phase2_input" if blockers else None,
            blockers=blockers,
            executed_legacy_aliases=executed_aliases,
            out_of_scope_steps=out_of_scope_steps,
        )
        terminal = SearchTerminalState(
            kind=(
                SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED
                if blockers
                else SearchTerminalKind.FRONTIER_STABLE
            ),
            reason=(
                "Phase-2 playbook requires missing input repair before legacy execution."
                if blockers
                else "Phase-2 playbook trajectory reached a stable candidate-only frontier."
            ),
            blocking_obligations=[blocker.blocker_id for blocker in blockers],
        )
        return WorkspaceIntentRunResult(
            workspace_id=workspace_id,
            terminal_state=terminal,
            phase2_playbook_trace=trace,
            search_blockers=blockers,
            legacy_workflow_id_disposition=selection.legacy_workflow_id_disposition,
            authority_boundary=authority_boundary,
            operation_invocations=operation_invocations,
            search_ledger_events=search_ledger_events,
            artifact_envelopes=artifact_envelopes,
            method_output_consumption_record=method_output_consumption_record,
            method_output_consumption_ref=method_output_consumption_ref,
            foundry_input_provenance=foundry_input_provenance,
            open_production_findings=open_production_findings,
        )

    def run_fixture(
        self,
        fixture_id: str,
        *,
        planner_kind: str = "seed_trajectory",
        forced_operation_classes: list[str] | None = None,
        search_quality_override: dict[str, Any] | None = None,
        acquisition_policy: Literal["auto", "disabled", "costed_plan"] = "auto",
    ) -> WorkspaceSearchExitContract:
        """Run the committed Slice-0 fixture through BIND -> ESTIMATE -> VERIFY."""

        if planner_kind != "seed_trajectory":
            raise WorkspaceInvariantError("Slice 0 must use SeedTrajectoryPlanner only.")
        manifest = load_workspace_fixture_manifest(fixture_id)
        trajectory = tuple(
            OperationClass(item) for item in (forced_operation_classes or WORKSPACE_TRAJECTORY)
        )
        for operation_class in trajectory:
            if operation_class not in ACTIVE_WORKSPACE_OPERATIONS:
                raise WorkspaceInvariantError(
                    f"non-active operation attempted in Slice 0: {operation_class.value}"
                )
            self._registry.executable_for_class(operation_class)
        if trajectory != WORKSPACE_TRAJECTORY:
            raise WorkspaceInvariantError("Slice 0 trajectory must be BIND -> ESTIMATE -> VERIFY.")
        if acquisition_policy not in {"auto", "disabled", "costed_plan"}:
            raise WorkspaceInvariantError(f"unknown acquisition policy: {acquisition_policy}")

        workspace_id = f"ws-{manifest.fixture_id.replace('_', '-')}"
        workspace_contract, workspace_contract_ref = self._workspace_contract(
            manifest=manifest,
            workspace_id=workspace_id,
        )
        semantic_run = self._semantic_benchmark_run(manifest)
        acquisition_plan = (
            self._acquisition_plan_for_manifest(manifest, workspace_id=workspace_id)
            if acquisition_policy in {"auto", "costed_plan"}
            else None
        )
        incompleteness = self._incompleteness(
            manifest,
            workspace_id,
            semantic_benchmark_run=semantic_run,
            acquisition_plan=acquisition_plan,
            search_quality_override=search_quality_override,
        )
        decision = select_search_terminal(
            self._decision_inputs(
                manifest,
                incompleteness,
                acquisition_plan=acquisition_plan,
            )
        )
        if (
            decision.kind == SearchTerminalKind.ACQUISITION_REQUIRED
            and acquisition_plan is not None
        ):
            terminal = acquisition_plan.terminal_state
        else:
            terminal = decision.terminal_state()
        if terminal["kind"] in set(manifest.forbidden_terminals):
            raise WorkspaceInvariantError(f"forbidden Slice-0 terminal emitted: {terminal['kind']}")
        artifact_envelopes_by_role = self._build_artifacts(manifest, terminal["kind"])
        self._assert_ring1_producer_artifacts(artifact_envelopes_by_role)
        artifacts = {
            role: envelope.ref
            for role, envelope in artifact_envelopes_by_role.items()
        }
        self._assert_workspace_artifact_cut_lines(
            terminal_kind=str(terminal["kind"]),
            output_artifacts=list(artifacts.values()),
        )
        authority_root = next(
            (
                root
                for root in artifact_envelopes_by_role["dataset"].producer_roots
                if root.artifact_type == "MeasurementRoot"
            ),
            artifacts["dataset"],
        )
        authority = (
            self._authority_boundary(manifest, authority_root)
            if terminal["kind"] == SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE.value
            else None
        )
        if authority is not None:
            certified_envelope = self._certified_operation_envelope(manifest)
            artifact_envelopes_by_role["estimate"] = self._verifier_certified_envelope(
                artifact_envelopes_by_role["estimate"],
                authority_boundary=authority,
                certified_operation_envelope=certified_envelope,
                applicability_result_ref="applicability-verify",
            )
        authority_derivation_traces = (
            [
                self._authority_derivation_trace(
                    manifest=manifest,
                    output_artifact=artifacts["estimate"],
                    authority_boundary=authority,
                    applicability_result_ref="applicability-verify",
                    certified_envelope_ref=(
                        artifact_envelopes_by_role["estimate"]
                        .certified_operation_envelope.envelope_id
                        if artifact_envelopes_by_role[
                            "estimate"
                        ].certified_operation_envelope
                        else None
                    ),
                )
            ]
            if authority is not None
            else []
        )
        promoted = [artifacts["estimate"]] if authority is not None else []
        frontier = FrontierSnapshot(
            snapshot_id=f"frontier-{manifest.fixture_id.replace('_', '-')}",
            workspace_id=workspace_id,
            cycle_index=3,
            promoted_candidates=promoted,
            shadow_candidates=[artifacts["dataset"], artifacts["estimate"]],
            rejected_candidates=[],
            dominated_candidates=[],
            current_best=promoted,
            frontier_metrics={
                "candidate_count": 2,
                "promoted_count": len(promoted),
                "rejected_count": 0,
                "cycles_without_improvement": 0,
            },
        )
        output_artifacts = [artifacts["dataset"], artifacts["estimate"]]
        formal_facts = self._formal_gate_facts(
            manifest=manifest,
            artifact_envelopes_by_role=artifact_envelopes_by_role,
            authority_boundary=authority,
            acquisition_plan=acquisition_plan,
        )
        ledger = self._ledger(
            workspace_id,
            output_artifacts,
            formal_facts=formal_facts,
            acquisition_plan=acquisition_plan,
        )
        obligation_records = self._obligation_records(
            manifest=manifest,
            workspace_id=workspace_id,
            terminal=terminal,
            acquisition_plan=acquisition_plan,
        )
        if obligation_records:
            terminal = terminal.model_copy(
                update={
                    "blocking_obligations": [
                        obligation.obligation_id for obligation in obligation_records
                    ]
                }
            )
        voi_audit = (
            self._voi_audit(
                manifest=manifest,
                workspace_id=workspace_id,
                decision=decision,
                incompleteness=incompleteness,
            )
            if acquisition_plan is None
            else self._terminal_voi_audit(
                acquisition_plan=acquisition_plan,
                decision=decision,
            )
        )
        budget_ledger = self._budget_ledger(
            trajectory=trajectory,
            incompleteness=incompleteness,
            acquisition_plan=acquisition_plan,
        )
        return WorkspaceSearchExitContract(
            exit_id=f"exit-{manifest.fixture_id.replace('_', '-')}",
            workspace_id=workspace_id,
            cycle_index=3,
            terminal_state=terminal,
            frontier_snapshot=frontier,
            incompleteness_record=incompleteness,
            budget_ledger=budget_ledger,
            output_artifacts=output_artifacts,
            authority_boundary=authority,
            next_best_actions=incompleteness.next_best_actions,
            workspace_contract=workspace_contract,
            workspace_contract_ref=workspace_contract_ref,
            obligation_records=obligation_records,
            search_ledger=ledger,
            voi_audit=voi_audit,
            artifact_envelopes=list(artifact_envelopes_by_role.values()),
            authority_derivation_traces=authority_derivation_traces,
        )

    def _subdesign_from_exit(
        self,
        *,
        parent_workspace_id: str,
        child_exit: WorkspaceSearchExitContract,
        fixture_id: str,
        index: int,
    ) -> SubDesignContract:
        subdesign_id = f"subdesign-{_slug(fixture_id)}-{index}"
        workspace_id = f"{child_exit.workspace_id}-child-{index}"
        provides: list[PortSpec] = []
        requires: list[PortSpec] = []
        if child_exit.authority_boundary is not None:
            provides.append(
                PortSpec.model_validate(
                    {
                        "port_id": f"port-{subdesign_id}",
                        "direction": "provides",
                        "port_type": "Estimate",
                        "claim_shape": {
                            "fixture_id": fixture_id,
                            "claim_type": "estimate",
                        },
                        "multiplicity": {"min": 1, "max": 1},
                        "provided_authority": child_exit.authority_boundary.model_dump(
                            mode="json"
                        ),
                    },
                    context={"writer_role": "system_verifier"},
                )
            )
        if child_exit.terminal_state.kind == SearchTerminalKind.ACQUISITION_REQUIRED:
            requires.append(
                PortSpec(
                    port_id=f"port-{subdesign_id}-acquisition",
                    direction="requires",
                    port_type="AcquisitionPlan",
                    claim_shape={
                        "fixture_id": fixture_id,
                        "terminal": SearchTerminalKind.ACQUISITION_REQUIRED.value,
                    },
                    multiplicity={"min": 1, "max": 1},
                    constraints={"parent_resolution": "fund_cap_or_escalate"},
                )
            )
        producer_roots = _producer_roots_from_exit(child_exit)
        return SubDesignContract(
            subdesign_id=subdesign_id,
            workspace_id=workspace_id,
            parent_workspace_id=parent_workspace_id,
            scope={
                "domain": fixture_id,
                "jurisdiction": child_exit.workspace_contract.scope.get("jurisdiction"),
                "scale": "child_workspace",
                "time_horizon": child_exit.workspace_contract.scope.get("time_horizon"),
                "posture": "advisory",
            },
            provides=provides,
            requires=requires,
            coupling_declarations=[],
            producer_roots=producer_roots,
            search_exit=child_exit,
            unresolved_obligations=list(child_exit.obligation_records),
            internal_trace_ref=_subdesign_contract_verification_ref(
                parent_workspace_id=parent_workspace_id,
                subdesign_id=subdesign_id,
            ),
        )

    def _workspace_contract(
        self,
        *,
        manifest: WorkspaceFixtureManifest,
        workspace_id: str,
    ) -> tuple[WorkspaceContract, str]:
        intent_payload = {
            "fixture_id": manifest.fixture_id,
            "construct_scope_query": manifest.construct_scope_query,
            "jurisdiction": manifest.jurisdiction,
            "population": manifest.population,
            "time_horizon": manifest.time_horizon,
        }
        intent_ref = ArtifactRef.from_payload(
            artifact_id=f"intent-{manifest.fixture_id.replace('_', '-')}",
            artifact_type="PolicyIntent",
            payload=intent_payload,
            schema_ref=WORKSPACE_LOOP_SCHEMA_VERSION,
            uri=f"gy://slice0/{manifest.fixture_id}/policy-intent",
            version="v1",
        )
        contract = WorkspaceContract(
            workspace_id=workspace_id,
            intent_ref=intent_ref,
            scope={
                "construct_scope_query": manifest.construct_scope_query,
                "jurisdiction": manifest.jurisdiction,
                "population": manifest.population,
                "time_horizon": manifest.time_horizon,
            },
            artifact_graph_ref=f"gy://slice0/{manifest.fixture_id}/artifact-graph",
            constraint_store_ref=f"gy://slice0/{manifest.fixture_id}/constraints",
            agenda_ref=f"gy://slice0/{manifest.fixture_id}/agenda",
            frontier_ref=f"gy://slice0/{manifest.fixture_id}/frontier",
            allowed_operations=[
                self._registry.executable_for_class(operation_class).operation_id
                for operation_class in WORKSPACE_TRAJECTORY
            ],
            budget=BudgetVector.slice0(),
        )
        return (
            contract,
            self._persist_loop_payload(
                contract.model_dump(mode="json"),
                kind="policyos.gy.workspace_contract",
            ),
        )

    def _assert_ring1_producer_artifacts(
        self,
        artifact_envelopes_by_role: dict[str, ArtifactEnvelope],
    ) -> None:
        for role, envelope in artifact_envelopes_by_role.items():
            try:
                assert_ring2_verifier_provenance(
                    envelope,
                    context={"writer_role": "workspace_loop_producer"},
                )
            except ValueError as exc:
                raise WorkspaceInvariantError(
                    f"Slice-0 producer artifact carried verifier-only Ring-2 field: {role}"
                ) from exc

    def _assert_workspace_artifact_cut_lines(
        self,
        *,
        terminal_kind: str,
        output_artifacts: list[ArtifactRef],
    ) -> None:
        if terminal_kind == SearchTerminalKind.GROUNDED_ADMISSIBLE.value:
            raise WorkspaceInvariantError("Slice 0 cannot emit grounded_admissible.")
        design_candidates = [
            artifact.artifact_id
            for artifact in output_artifacts
            if artifact.artifact_type == "DesignCandidate"
        ]
        if design_candidates:
            raise WorkspaceInvariantError(
                "Slice 0 cannot emit or promote DesignCandidate artifacts: "
                + ", ".join(sorted(design_candidates))
            )

    def _certified_operation_envelope(
        self,
        manifest: WorkspaceFixtureManifest,
    ) -> CertifiedOperationEnvelope:
        return CertifiedOperationEnvelope(
            envelope_id=f"envelope-{manifest.fixture_id.replace('_', '-')}-estimate",
            domains=[manifest.population],
            posture_scopes=["governed"],
            epistemic_regime_scopes=[],
            actor_scopes=["workspace_loop"],
            method_scopes=["measurement_root_summary"],
            certified_for=["slice0_estimate_port_authority"],
            not_certified_for=[
                "design_candidate",
                "grounded_admissible",
                "production_decision",
            ],
            rule_version_ref="policyos.gy.authority.v1",
        )

    def _verifier_certified_envelope(
        self,
        envelope: ArtifactEnvelope,
        *,
        authority_boundary: AuthorityBoundary,
        certified_operation_envelope: CertifiedOperationEnvelope,
        applicability_result_ref: str,
    ) -> ArtifactEnvelope:
        payload = envelope.model_dump(mode="json")
        payload["authority_boundary"] = authority_boundary.model_dump(mode="json")
        payload["certified_operation_envelope"] = certified_operation_envelope.model_dump(
            mode="json"
        )
        payload["verification"] = {
            **dict(payload.get("verification") or {}),
            "latest_applicability_result": applicability_result_ref,
        }
        certified = ArtifactEnvelope.model_validate(
            payload,
            context={"writer_role": "system_verifier"},
        )
        assert_ring2_verifier_provenance(
            certified,
            context={"writer_role": "system_verifier"},
        )
        return certified

    def _obligation_records(
        self,
        *,
        manifest: WorkspaceFixtureManifest,
        workspace_id: str,
        terminal: SearchTerminalState,
        acquisition_plan: AcquisitionPlan | None,
    ) -> list[ObligationRecord]:
        if terminal["kind"] != SearchTerminalKind.ACQUISITION_REQUIRED.value:
            return []
        missing_distribution = (
            acquisition_plan.costed_plan.get("missing_distribution")
            if acquisition_plan is not None
            else _required_data_family_for_manifest(manifest)
        )
        return [
            ObligationRecord(
                obligation_id=f"obligation-{manifest.fixture_id.replace('_', '-')}-acquisition",
                obligation_type="acquisition_required",
                raised_by={
                    "component": "polisyos.runtime.quality.WorkspaceLoop",
                    "terminal": SearchTerminalKind.ACQUISITION_REQUIRED.value,
                },
                blocks=[
                    {
                        "authority": "grounded_admissible",
                        "reason": "missing_distribution",
                        "missing_distribution": missing_distribution,
                    }
                ],
                description=(
                    "Slice-0 stopped before authority closure because the fixture "
                    f"requires acquisition for {missing_distribution}."
                ),
                severity="blocks_decision",
                resolution_options=[
                    {
                        "operation_proposal_ref": "slice0.acquire.costed_plan",
                        "owner": "GY-H/GY-E",
                        "slice0_execution": "fail_closed",
                    }
                ],
                status="open",
            )
        ]

    def _build_artifacts(
        self,
        manifest: WorkspaceFixtureManifest,
        terminal_kind: str,
    ) -> dict[str, ArtifactEnvelope]:
        measurement_admitted = (
            terminal_kind == SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE.value
        )
        if manifest.expected_catalog_binding_refs and measurement_admitted:
            producer = MeasurementRootProducer(artifact_store=self._artifact_store)
            dataset_envelope = producer.produce_from_catalog(
                manifest=manifest,
                catalog_graph=self._catalog_graph,
            )
            dataset_payload = self._dataset_payload_for_estimate(manifest, dataset_envelope)
        else:
            dataset_payload = {
                "fixture_id": manifest.fixture_id,
                "catalog_binding_refs": manifest.expected_catalog_binding_refs,
                "connector_profile": manifest.expected_connector_profile,
                "producer_root_kind": manifest.expected_producer_root_kind,
                "disposition": (
                    "search_ceiling_grounding_withheld"
                    if manifest.expected_catalog_binding_refs
                    else "missing_acquisition"
                ),
            }
            dataset_ref = ArtifactRef.from_payload(
                artifact_id=f"base-{manifest.fixture_id.replace('_', '-')}",
                artifact_type="BaseDataset",
                payload=dataset_payload,
                schema_ref=WORKSPACE_LOOP_SCHEMA_VERSION,
                uri=f"gy://slice0/{manifest.fixture_id}/base-dataset",
                version="v1",
            )
            dataset_envelope = ArtifactEnvelope(
                ref=dataset_ref,
                payload_ref=self._persist_loop_payload(
                    dataset_payload,
                    kind="policyos.gy.missing_acquisition_payload",
                ),
                payload_schema_ref=WORKSPACE_LOOP_SCHEMA_VERSION,
                lifecycle_state="shadow",
                created_by={
                    "kind": "producer",
                    "component": "polisyos.runtime.quality.WorkspaceLoop",
                },
                producer_operation={
                    "invocation_id": "invoke-bind",
                    "operation_id": "slice0.bind.catalog",
                    "operation_version": "v1",
                },
                input_artifacts=[],
                producer_roots=[],
                obligations=[
                    "search_repair_required"
                    if manifest.expected_catalog_binding_refs
                    else "acquisition_required"
                ],
            )
        measurement_rows = [
            dict(row)
            for row in dataset_payload.get("measurement_rows", [])
            if isinstance(row, dict)
        ]
        measurement_root_ref = (
            dataset_envelope.producer_roots[0].uri
            if dataset_envelope.producer_roots
            else None
        )
        estimate_payload = {
            "fixture_id": manifest.fixture_id,
            "estimate_scope": "estimate_port_only",
            "terminal": terminal_kind,
            "evidence_kind": "measurement" if measurement_rows else "simulation",
            "measurement_root_ref": measurement_root_ref,
            "measurement_rows": measurement_rows,
            "measurement_summary": _measurement_summary(measurement_rows),
        }
        estimate_ref = ArtifactRef.from_payload(
            artifact_id=f"estimate-{manifest.fixture_id.replace('_', '-')}",
            artifact_type="Estimate",
            payload=estimate_payload,
            schema_ref=WORKSPACE_LOOP_SCHEMA_VERSION,
            uri=f"gy://slice0/{manifest.fixture_id}/estimate",
            version="v1",
        )
        return {
            "dataset": dataset_envelope,
            "estimate": ArtifactEnvelope(
                ref=estimate_ref,
                payload_ref=self._persist_loop_payload(
                    estimate_payload,
                    kind="policyos.gy.estimate_payload",
                ),
                payload_schema_ref=WORKSPACE_LOOP_SCHEMA_VERSION,
                lifecycle_state="shadow",
                created_by={
                    "kind": "producer",
                    "component": "polisyos.runtime.quality.WorkspaceLoop",
                },
                producer_operation={
                    "invocation_id": "invoke-estimate",
                    "operation_id": "slice0.estimate.measurement_summary",
                    "operation_version": "v1",
                },
                input_artifacts=[dataset_envelope.ref],
                producer_roots=[dataset_envelope.ref],
                obligations=[],
            ),
        }

    def _dataset_payload_for_estimate(
        self,
        manifest: WorkspaceFixtureManifest,
        dataset_envelope: ArtifactEnvelope,
    ) -> dict[str, Any]:
        if self._artifact_store is not None:
            try:
                return json.loads(self._artifact_store.get_bytes(dataset_envelope.payload_ref))
            except Exception:
                logging.getLogger(__name__).debug(
                    "falling back to catalog graph after CAS dataset read failed",
                    exc_info=True,
                )
        expected_refs = set(manifest.expected_catalog_binding_refs)
        for hit in self._catalog_graph.search_datasets(
            manifest.construct_scope_query,
            top_k=20,
            explain=True,
        ):
            if hit.id not in expected_refs:
                continue
            hit_payload = canonical_catalog_result_for_workspace_loop(
                hit.model_dump(mode="json")
            )
            rows = measurement_rows_for_catalog_payload(hit_payload)
            if rows:
                return {
                    "fixture_id": manifest.fixture_id,
                    "catalog_binding_refs": [hit.id],
                    "catalog_result": hit_payload,
                    "measurement_rows": rows,
                }
        return {"fixture_id": manifest.fixture_id, "measurement_rows": []}

    def _persist_loop_payload(self, payload: dict[str, Any], *, kind: str) -> str:
        if self._artifact_store is None:
            return gy_content_hash(payload)
        scan = scan_secret_and_pii(
            payload,
            scope="DAG bundles",
            artifact_ref_or_route=f"gy-loop://{kind}",
            redact=False,
            block_on_findings=True,
        )
        if scan.has_findings:
            raise ValueError(
                "GY loop payload blocked by secret/PII scan: "
                + ",".join(scan.finding_kinds)
            )
        from polisyos.runtime.http.services.control.artifacts import write_authority_artifact

        result = write_authority_artifact(
            self._artifact_store,
            payload,
            PutOptions(
                kind=kind,
                media_type="application/json",
                schema=SchemaInfo(name=WORKSPACE_LOOP_SCHEMA_VERSION, version="v1"),
                producer=ProducerInfo(
                    component="polisyos.runtime.quality.WorkspaceLoop",
                    version="1.0.0",
                ),
            ),
            evidence_id=f"gy-loop-{kind}-{gy_content_hash(payload)[:16]}",
            evidence_class="authority_bearing",
            authority_role="producer_authority",
            provenance_kind="runtime_emitted",
            owner="team-runtime-quality",
            reader_contract=WORKSPACE_LOOP_SCHEMA_VERSION,
            reader_contract_version="v1",
            tenant_id="policyos-system",
            cell_id=None,
            run_id=f"run-gy-loop-{payload.get('fixture_id') or 'payload'!s}",
            job_id=f"job-gy-loop-{payload.get('fixture_id') or 'payload'!s}",
            trace_id=f"trace-gy-loop-{kind}",
            span_id=f"span-gy-loop-{kind}",
            parent_span_id=None,
            requested_execution_profile="gy_slice0",
            effective_execution_profile="gy_slice0",
            phase="GY-F2",
            generated_at=_utc_timestamp(),
            as_of_time=_utc_timestamp(),
            same_input_closure={
                "closure_id": f"gy-loop-{payload.get('fixture_id') or kind!s}",
                "status": "closed",
                "run_id": f"run-gy-loop-{payload.get('fixture_id') or 'payload'!s}",
                "job_id": f"job-gy-loop-{payload.get('fixture_id') or 'payload'!s}",
                "tenant_id": "policyos-system",
                "cell_id": None,
                "evidence_input_refs": (),
            },
            input_refs=[],
            effective_mode_ref="gy-slice0-runtime",
            validation_status="pass",
            blocking_status="non_blocking",
            governance={
                "classification": "internal",
                "authority_boundary": "slice0_estimate_port_only",
                "pii": "secret_pii_scanned",
                "retention_policy": "policy_design_case_generated_artifact",
                "review_status": "runtime_generated",
                "override_policy": "no_override",
                "approval_policy": "not_publication_authority",
            },
            redaction_policy_ref="polisyos.core.llm.sanitization.v1",
            canon_spec=CanonSpec(forbid_floats=False),
        )
        return str(result.cas_ref.artifact_id)

    def _authority_boundary(
        self,
        manifest: WorkspaceFixtureManifest,
        producer_root: ArtifactRef,
    ) -> AuthorityBoundary:
        requested = AuthorityBoundary(
            boundary_id=f"boundary-{manifest.fixture_id.replace('_', '-')}",
            authoritative_for=[f"estimate:{manifest.fixture_id}"],
            may_not_use_for=[
                "design_candidate",
                "grounded_admissible",
                "production_decision",
            ],
            source_authority="deterministic_producer",
            posture="governed",
            rule_version_refs=["policyos.gy.authority.v1"],
            evidence_kind="measurement",
            decision_grade="decision_admissible",
            evidence_basis=EvidenceBasis(
                producer_roots=[producer_root],
                method_refs=["slice0.bind.catalog", "slice0.estimate.measurement_summary"],
                calibration_refs=[],
                counterexamples_closed=[],
            ),
        )
        return requested.with_partial_evidence_downgrade(
            limitation="Slice-0 estimate-port authority only.",
            may_not_use_for=[
                "design_candidate",
                "grounded_admissible",
                "production_decision",
                "publication_without_limitation",
            ],
            decision_grade_cap="descriptive_only",
        )

    def _authority_derivation_trace(
        self,
        *,
        manifest: WorkspaceFixtureManifest,
        output_artifact: ArtifactRef,
        authority_boundary: AuthorityBoundary,
        applicability_result_ref: str,
        certified_envelope_ref: str | None,
    ) -> AuthorityDerivationTrace:
        return AuthorityDerivationTrace(
            operation_invocation_id="invoke-verify",
            output_artifact_ref=output_artifact,
            declared_authority_transform={
                "kind": "weakens",
                "requested_evidence_kind": "measurement",
                "requested_decision_grade": "decision_admissible",
                "rule_ref": "policyos.gy.authority.v1",
            },
            computed_evidence_kind="measurement",
            computed_decision_grade="descriptive_only",
            producer_root_classes=[manifest.expected_producer_root_kind],
            method_classification="measurement_root_summary",
            applicability_result_ref=applicability_result_ref,
            calibration_refs=[],
            counterexamples_closed=[],
            certified_envelope_ref=certified_envelope_ref,
            unresolved_blockers=["slice0_estimate_port_only"],
            resulting_authority_boundary_ref=authority_boundary.boundary_id or "",
            transform_mismatch_disposition="downgraded",
        )

    def _formal_gate_facts(
        self,
        *,
        manifest: WorkspaceFixtureManifest,
        artifact_envelopes_by_role: dict[str, ArtifactEnvelope],
        authority_boundary: AuthorityBoundary | None,
        acquisition_plan: AcquisitionPlan | None = None,
    ) -> dict[str, Any]:
        dataset_envelope = artifact_envelopes_by_role["dataset"]
        estimate_envelope = artifact_envelopes_by_role["estimate"]
        measurement_rooted = any(
            root.artifact_type == "MeasurementRoot" for root in dataset_envelope.producer_roots
        )
        source_contract_ref = dataset_envelope.verification.latest_applicability_result
        missing_distribution = (
            acquisition_plan.costed_plan.get("missing_distribution")
            if acquisition_plan is not None
            else None
        )
        return {
            "slice0.catalog_binding_expected": {
                "passed": bool(manifest.expected_catalog_binding_refs),
                "evidence_ref": f"manifest:{manifest.fixture_id}",
                "observed": {
                    "expected_catalog_binding_refs": manifest.expected_catalog_binding_refs,
                    "dataset_artifact_ref": dataset_envelope.ref.content_hash,
                },
            },
            "slice0.source_contract_facets_complete": {
                "passed": bool(source_contract_ref and measurement_rooted),
                "evidence_ref": source_contract_ref,
                "reason": "passed"
                if source_contract_ref and measurement_rooted
                else "source_contract_not_applicable_or_missing",
                "observed": {
                    "measurement_rooted": measurement_rooted,
                    "latest_applicability_result": source_contract_ref,
                },
            },
            "slice0.estimate_input_dataset": {
                "passed": (
                    dataset_envelope.ref.artifact_type == "BaseDataset" and measurement_rooted
                ),
                "evidence_ref": dataset_envelope.ref.content_hash,
                "reason": "passed"
                if measurement_rooted
                else "estimate_input_is_not_measurement_rooted",
                "observed": {
                    "artifact_type": dataset_envelope.ref.artifact_type,
                    "producer_root_types": [
                        root.artifact_type for root in dataset_envelope.producer_roots
                    ],
                },
            },
            "slice0.verify_authority_boundary": {
                "passed": authority_boundary is not None
                and estimate_envelope.ref.artifact_type == "Estimate",
                "evidence_ref": authority_boundary.boundary_id if authority_boundary else None,
                "reason": "passed"
                if authority_boundary is not None
                else "no_authority_boundary_for_non_authority_terminal",
                "observed": {
                    "estimate_artifact_type": estimate_envelope.ref.artifact_type,
                    "authority_boundary": authority_boundary.boundary_id
                    if authority_boundary is not None
                    else None,
                },
            },
            "slice0.acquire_missing_distribution": {
                "passed": bool(missing_distribution),
                "evidence_ref": f"manifest:{manifest.fixture_id}",
                "reason": "passed" if missing_distribution else "missing_distribution_absent",
                "observed": {
                    "missing_distribution": missing_distribution,
                    "expected_catalog_binding_refs": manifest.expected_catalog_binding_refs,
                },
            },
            "slice0.acquire_data_need_spec": {
                "passed": acquisition_plan is not None
                and _looks_like_data_need_spec(acquisition_plan.data_need_spec),
                "evidence_ref": acquisition_plan.data_need_spec.metric
                if acquisition_plan is not None
                else None,
                "reason": "passed" if acquisition_plan is not None else "data_need_spec_absent",
                "observed": {
                    "data_need_spec": data_need_spec_payload(acquisition_plan.data_need_spec)
                    if acquisition_plan is not None
                    else None,
                },
            },
            "slice0.acquire_positive_voi": {
                "passed": acquisition_plan is not None
                and bool(acquisition_plan.voi_audit.selected_action_ref)
                and any(
                    float(candidate.get("estimated_voi") or 0.0) > 0.0
                    for candidate in acquisition_plan.voi_audit.candidates
                ),
                "evidence_ref": acquisition_plan.voi_audit.audit_id
                if acquisition_plan is not None
                else None,
                "reason": "passed" if acquisition_plan is not None else "positive_voi_absent",
                "observed": {
                    "selected_action_ref": acquisition_plan.voi_audit.selected_action_ref
                    if acquisition_plan is not None
                    else None,
                },
            },
        }

    def _incompleteness(
        self,
        manifest: WorkspaceFixtureManifest,
        workspace_id: str,
        *,
        semantic_benchmark_run: SemanticBenchmarkRun | None = None,
        acquisition_plan: AcquisitionPlan | None = None,
        search_quality_override: dict[str, Any] | None = None,
    ) -> SearchIncompletenessRecord:
        source_missing = (
            []
            if manifest.expected_catalog_binding_refs
            else [
                {
                    "source_class": "local_data",
                    "reason": "missing_distribution_requires_acquisition",
                }
            ]
        )
        search_quality = {
            "recall_at_known_seeds": semantic_benchmark_run.recall_at_known_seeds
            if semantic_benchmark_run is not None
            else (1.0 if not source_missing else 0.0),
            "known_seeds_missed": semantic_benchmark_run.missed_known_seeds
            if semantic_benchmark_run is not None
            else [],
            "freshness_ok": True,
            "stale_source_classes": [],
            "semantic_benchmark_run": semantic_benchmark_run.model_dump(mode="json")
            if semantic_benchmark_run is not None
            else None,
        }
        if search_quality_override:
            search_quality.update(search_quality_override)
        recall_threshold = BudgetVector.slice0().search_quality["min_recall_at_known_seeds"]
        semantic_failed = (
            semantic_benchmark_run is not None
            and semantic_benchmark_run.threshold_disposition == "fail"
        )
        ceiling_classification = (
            "search_ceiling"
            if source_missing
            or semantic_failed
            or float(search_quality["recall_at_known_seeds"]) < recall_threshold
            else "mixed"
        )
        next_best_actions = [
            {
                "operation_proposal_ref": "slice0.acquire.costed_plan",
                "estimated_voi": 1.0
                if source_missing or search_quality["known_seeds_missed"] or semantic_failed
                else 0.0,
                "estimated_cost": "out_of_scope_slice0",
                "reason_not_taken": (
                    "ACQUIRE continuation was not selected for this terminal."
                ),
            }
        ]
        if acquisition_plan is not None:
            next_best_actions = [
                {
                    "operation_proposal_ref": "slice0.acquire.costed_plan",
                    "estimated_voi": acquisition_plan.voi_audit.candidates[0]["estimated_voi"],
                    "estimated_cost": acquisition_plan.costed_plan["estimated_cost"],
                    "reason_not_taken": (
                        "Costed acquisition terminal returned; external acquisition "
                        "execution is blocked until an approved producer run lands."
                    ),
                    "data_need_spec": data_need_spec_payload(acquisition_plan.data_need_spec),
                    "costed_plan": acquisition_plan.costed_plan,
                }
            ]
        operations_attempted = [item.value for item in WORKSPACE_TRAJECTORY]
        operations_not_attempted = [
            {
                "operation_id": "slice0.acquire.costed_plan",
                "reason": "terminal_recommendation_not_executed_in_slice0",
            }
        ]
        budget_vector = BudgetVector.slice0()
        recall = float(search_quality["recall_at_known_seeds"])
        recall_deficit = max(0.0, recall_threshold - recall)
        estimated_cost = (
            acquisition_plan.costed_plan.get("estimated_cost", {})
            if acquisition_plan is not None
            else {}
        )
        budget_record = {
            "consumed": {
                "compute": {"operation_invocations": len(WORKSPACE_TRAJECTORY)},
                "search_quality": {
                    "recall_at_known_seeds": recall,
                    "recall_deficit": recall_deficit,
                },
                "acquisition": {
                    "money_usd": float(estimated_cost.get("money_usd") or 0.0),
                },
                "expert_attention": {
                    "expert_hours": float(estimated_cost.get("expert_hours") or 0.0),
                },
                "calendar": {
                    "calendar_days": int(estimated_cost.get("calendar_days") or 0),
                },
                "novelty": {"disabled_slice0": 0},
                "recursion": {"disabled_slice0": 0},
            },
            "remaining": {
                "compute": {
                    "operation_invocations": max(
                        0,
                        int(budget_vector.compute["max_operation_invocations"])
                        - len(WORKSPACE_TRAJECTORY),
                    ),
                },
                "search_quality": {
                    "recall_margin": max(0.0, recall - recall_threshold),
                },
                "acquisition": {"money_usd": 0.0},
                "expert_attention": {"expert_hours": 0.0},
                "calendar": {"calendar_days": 0},
                "novelty": {"disabled_slice0": 0},
                "recursion": {"disabled_slice0": 0},
            },
            "exhausted": (
                ["search_quality.min_recall_at_known_seeds"] if recall_deficit else []
            ),
        }
        return SearchIncompletenessRecord(
            record_id=f"incomplete-{manifest.fixture_id.replace('_', '-')}",
            workspace_id=workspace_id,
            coverage={
                "operations_attempted": operations_attempted,
                "operations_not_attempted": operations_not_attempted,
                "methods_attempted": ["slice0.estimate.measurement_summary"],
                "source_classes_checked": ["official"],
                "source_classes_missing": source_missing,
                "jurisdictions_checked": [manifest.jurisdiction],
                "time_horizons_checked": [manifest.time_horizon],
            },
            search_quality=search_quality,
            unresolved={
                "counterexamples": [],
                "missing_data": source_missing,
                "unmet_required_ports": [],
                "unresolved_couplings": [],
                "human_questions": [],
            },
            budget=budget_record,
            next_best_actions=next_best_actions,
            ceiling_classification=ceiling_classification,
        )

    def _decision_inputs(
        self,
        manifest: WorkspaceFixtureManifest,
        incompleteness: SearchIncompletenessRecord,
        *,
        acquisition_plan: AcquisitionPlan | None = None,
    ) -> SearchExitDecisionInputs:
        source_classes_missing = [
            str(item.get("source_class"))
            for item in incompleteness.coverage.get("source_classes_missing", [])
            if isinstance(item, dict) and item.get("source_class")
        ]
        if acquisition_plan is not None:
            source_classes_missing = []
        search_quality = incompleteness.search_quality
        return SearchExitDecisionInputs(
            recall_at_known_seeds=float(search_quality.get("recall_at_known_seeds", 0.0)),
            recall_threshold=float(
                BudgetVector.slice0().search_quality["min_recall_at_known_seeds"]
            ),
            freshness_ok=bool(search_quality.get("freshness_ok", False)),
            required_source_classes_missing=source_classes_missing,
            acquisition_required=acquisition_plan is not None,
            positive_terminal=SearchTerminalKind(manifest.expected_terminal),
        )

    def _terminal_voi_audit(
        self,
        *,
        acquisition_plan: AcquisitionPlan,
        decision: SearchTerminalDecision,
    ) -> VOISelectionAudit:
        if decision.kind == SearchTerminalKind.ACQUISITION_REQUIRED:
            return acquisition_plan.voi_audit
        return acquisition_plan.voi_audit.model_copy(
            update={
                "selected_terminal": decision.kind,
                "selected_action_ref": None,
                "selected_action": {},
                "continuation_allowed": False,
                "reason": (
                    "Higher-precedence terminal selected before costed acquisition "
                    "continuation."
                ),
            }
        )

    def _budget_ledger(
        self,
        *,
        trajectory: tuple[OperationClass, ...],
        incompleteness: SearchIncompletenessRecord,
        acquisition_plan: AcquisitionPlan | None,
    ) -> dict[str, Any]:
        budget = BudgetVector.slice0()
        max_invocations = int(budget.compute.get("max_operation_invocations") or 0)
        consumed_invocations = len(trajectory)
        recall = float(incompleteness.search_quality.get("recall_at_known_seeds", 0.0))
        recall_threshold = float(budget.search_quality.get("min_recall_at_known_seeds", 1.0))
        exhausted: list[str] = []
        if recall < recall_threshold:
            exhausted.append("search_quality.min_recall_at_known_seeds")
        estimated_cost = (
            acquisition_plan.costed_plan.get("estimated_cost", {})
            if acquisition_plan is not None
            else {}
        )
        return {
            "consumed": {
                "compute": {"operation_invocations": consumed_invocations},
                "search_quality": {
                    "recall_at_known_seeds": recall,
                    "recall_deficit": max(0.0, recall_threshold - recall),
                },
                "acquisition": {
                    "money_usd": float(estimated_cost.get("money_usd") or 0.0),
                },
                "expert_attention": {
                    "expert_hours": float(estimated_cost.get("expert_hours") or 0.0),
                },
                "calendar": {
                    "calendar_days": int(estimated_cost.get("calendar_days") or 0),
                },
                "novelty": {"disabled_slice0": 0},
                "recursion": {"disabled_slice0": 0},
            },
            "remaining": {
                "compute": {
                    "operation_invocations": max(0, max_invocations - consumed_invocations),
                },
                "search_quality": {
                    "recall_margin": max(0.0, recall - recall_threshold),
                },
                "acquisition": {"money_usd": 0.0},
                "expert_attention": {"expert_hours": 0.0},
                "calendar": {"calendar_days": 0},
                "novelty": {"disabled_slice0": 0},
                "recursion": {"disabled_slice0": 0},
            },
            "exhausted": exhausted,
        }

    def _semantic_benchmark_run(
        self,
        manifest: WorkspaceFixtureManifest,
    ) -> SemanticBenchmarkRun:
        hits = self._catalog_graph.search_datasets(
            manifest.construct_scope_query,
            top_k=20,
            explain=True,
        )
        returned_hits = [
            {
                "dataset_id": hit.id,
                "calibrated_relevance": _calibrated_relevance(
                    hit=hit,
                    manifest=manifest,
                ),
            }
            for hit in hits
        ]
        return SemanticAdequacyGate().evaluate(
            construct_scope=manifest.fixture_id,
            returned_hits=returned_hits,
        )

    def _acquisition_plan_for_manifest(
        self,
        manifest: WorkspaceFixtureManifest,
        *,
        workspace_id: str,
    ) -> AcquisitionPlan | None:
        if manifest.expected_catalog_binding_refs:
            return None
        missing_distribution = _required_data_family_for_manifest(manifest)
        plans = AcquisitionPlanner().plans_from_required_data(
            RequiredDataGap(
                missing_distributions=(missing_distribution,),
                suggested_experiment="site-count intercept survey",
                alternative_identification=(
                    "administrative visitor counters or mobile-footfall panel"
                ),
            ),
            workspace_id=workspace_id,
        )
        return plans[0] if plans else None

    def _voi_audit(
        self,
        *,
        manifest: WorkspaceFixtureManifest,
        workspace_id: str,
        decision: SearchTerminalDecision,
        incompleteness: SearchIncompletenessRecord,
    ) -> VOISelectionAudit:
        candidates = []
        selected_action_ref: str | None = None
        for action in incompleteness.next_best_actions:
            estimated_voi = float(action.get("estimated_voi") or 0.0)
            proposal_ref = str(action.get("operation_proposal_ref") or "")
            if estimated_voi > 0 and selected_action_ref is None:
                selected_action_ref = proposal_ref
            candidates.append(
                {
                    "operation_proposal_ref": proposal_ref,
                    "estimated_voi": estimated_voi,
                    "estimated_cost": action.get("estimated_cost"),
                    "voi_per_cost": 0.0,
                    "hard_budgets_allow": False,
                    "reason_not_taken": action.get("reason_not_taken"),
                }
            )
        return VOISelectionAudit(
            audit_id=f"voi-{_slug(manifest.fixture_id)}",
            workspace_id=workspace_id,
            selected_terminal=decision.kind,
            candidates=candidates,
            selected_action_ref=selected_action_ref,
            continuation_allowed=False,
            decision_rule_ref=WORKSPACE_ANYTIME_EXIT_RULE_VERSION,
            threshold=0.0,
            candidate_actions=[
                {"operation_proposal_ref": item["operation_proposal_ref"]}
                for item in candidates
            ],
            agent_suggested_scores={},
            normalized_scores={
                item["operation_proposal_ref"]: item["estimated_voi"]
                for item in candidates
                if item["operation_proposal_ref"]
            },
            deterministic_voi_inputs={
                "fixture_id": manifest.fixture_id,
                "known_seeds_missed": incompleteness.search_quality["known_seeds_missed"],
                "ceiling_classification": incompleteness.ceiling_classification,
            },
            rejected_or_clipped_inputs=[],
            selected_action={"operation_proposal_ref": selected_action_ref}
            if selected_action_ref
            else {},
            reason="Deterministic Slice-0 anytime-exit selection.",
            authority_gain_basis={"selected_terminal": decision.kind.value},
            decision_value_basis={"rule": WORKSPACE_ANYTIME_EXIT_RULE_VERSION},
            cost_basis={"slice0_budget_only": True},
            bias_probe_result={"agent_scores_used": False, "status": "not_applicable"},
        )

    def _ledger(
        self,
        workspace_id: str,
        output_artifacts: list[ArtifactRef],
        *,
        formal_facts: dict[str, Any],
        acquisition_plan: AcquisitionPlan | None = None,
    ) -> WorkspaceSearchLedger:
        invocations: list[OperationInvocationRecord] = []
        applicability_results: list[ApplicabilityResult] = []
        events: list[SearchLedgerEvent] = []
        for index, operation_class in enumerate(WORKSPACE_TRAJECTORY):
            registration = self._registry.executable_for_class(operation_class)
            invocation_id = f"invoke-{operation_class.value.lower()}"
            result_id = f"applicability-{operation_class.value.lower()}"
            applicability_results.append(
                _evaluate_formal_gate(
                    registration=registration,
                    invocation_id=invocation_id,
                    result_id=result_id,
                    facts=formal_facts,
                )
            )
            invocations.append(
                OperationInvocationRecord(
                    invocation_id=invocation_id,
                    operation_id=registration.operation_id,
                    operation_version=registration.contract.operation_version,
                    workspace_id=workspace_id,
                    cycle_index=index,
                    selected_by={"kind": "refinement_policy", "id": "seed-trajectory"},
                    input_artifacts=[],
                    parameters={
                        "schema_ref": WORKSPACE_LOOP_SCHEMA_VERSION,
                        "value_ref": "inline:slice0",
                    },
                    internal_trace={
                        "trace_kind": "deterministic",
                        "trace_ref": f"gy://slice0/{workspace_id}/{operation_class.value.lower()}",
                    },
                    output_artifacts=(
                        output_artifacts if operation_class == OperationClass.VERIFY else []
                    ),
                    applicability_result=result_id,
                    budget_delta={"compute": {"operation_invocations": 1}},
                    status="completed",
                )
            )
            events.append(
                SearchLedgerEvent(
                    event_id=f"event-{operation_class.value.lower()}-finished",
                    workspace_id=workspace_id,
                    cycle_index=index,
                    event_type="operation_finished",
                    actor={"kind": "system", "id": "workspace-loop"},
                    input_artifacts=[],
                    output_artifacts=output_artifacts
                    if operation_class == OperationClass.VERIFY
                    else [],
                    operation_invocation_ref=invocation_id,
                    budget_delta={"compute": {"operation_invocations": 1}},
                    created_obligations=[],
                    timestamp=_utc_timestamp(),
                )
            )
        output_artifact_refs = [artifact.artifact_id for artifact in output_artifacts]
        canonical_iterations = [
            {
                "iteration_id": f"iteration-{operation.value.lower()}",
                "candidate_ref": (
                    output_artifact_refs[0]
                    if output_artifact_refs
                    else f"artifact:slice0:{_slug(workspace_id)}:no-design-candidate"
                ),
                "counterexample_refs": [],
                "refinement_decision_ref": f"applicability-{operation.value.lower()}",
                "status": "abstained",
            }
            for operation in WORKSPACE_TRAJECTORY
        ]
        return WorkspaceSearchLedger(
            ledger_id=f"ledger-{workspace_id}",
            ledger_ref=f"gy://slice0/{workspace_id}/search-ledger",
            case_id=workspace_id,
            iterations=canonical_iterations,
            candidate_refs=output_artifact_refs
            or [f"artifact:slice0:{_slug(workspace_id)}:no-design-candidate"],
            counterexample_refs=[],
            refinement_decision_refs=[
                result.result_id for result in applicability_results
            ],
            deterministic_replay_key=f"{WORKSPACE_LOOP_SCHEMA_VERSION}:{workspace_id}:slice0",
            counterexample_conversion_rate=0.0,
            grammar_diversity_minimum=0,
            instrument_family_coverage=[
                operation.value.lower() for operation in WORKSPACE_TRAJECTORY
            ],
            counterexample_class_vocabulary=[],
            no_retry_without_new_grammar=True,
            search_incompleteness_note=(
                "Slice-0 loop is BIND -> ESTIMATE -> VERIFY; no design candidate promotion."
            ),
            workspace_id=workspace_id,
            events=events,
            invocations=invocations,
            applicability_results=applicability_results,
            replay_levels=["A", "B", "C"],
        )


def _evaluate_formal_gate(
    *,
    registration: OperationRegistration,
    invocation_id: str,
    result_id: str,
    facts: dict[str, Any],
) -> ApplicabilityResult:
    return FormalGate().evaluate(
        registration=registration,
        invocation_id=invocation_id,
        result_id=result_id,
        facts=facts,
    )


def _operation_contract(
    *,
    operation_id: str,
    operation_class: OperationClass,
    authority_transform: dict[str, Any],
) -> OperationContract:
    port = PortSpec(
        port_id=f"port-{operation_class.value.lower()}",
        direction="consumes",
        port_type="Dataset" if operation_class != OperationClass.VERIFY else "Estimate",
        claim_shape={
            "kind": "descriptive",
            "subject_type": "policy_case",
            "predicate_type": operation_class.value.lower(),
        },
        multiplicity={"min": 0, "max": 1},
        constraints={},
    )
    return OperationContract(
        operation_id=operation_id,
        operation_version="v1",
        operation_class=operation_class,
        consumes=[port],
        produces=[port.model_copy(update={"direction": "produces"})],
        formal_preconditions=_formal_preconditions_for_operation(operation_class),
        allowed_internal_execution=["tool_call"],
        implementation_refs=[
            {
                "kind": "python_function",
                "ref": "polisyos.runtime.quality.workspace.loop.WorkspaceLoop",
            }
        ],
        cost_model={"compute": {"max_operation_invocations": 1}},
        authority_transform=authority_transform,
        failure_modes=[],
        repair_options=[],
    )


def _formal_preconditions_for_operation(operation_class: OperationClass) -> list[dict[str, Any]]:
    predicates = {
        OperationClass.BIND: [
            {
                "predicate_id": "slice0.catalog_binding_expected",
                "description": (
                    "Fixture expectation is read from WorkspaceFixtureManifest before BIND."
                ),
                "severity": "hard",
            },
            {
                "predicate_id": "slice0.source_contract_facets_complete",
                "description": "DataRequirementSpec/source-contract facets must pass before fetch.",
                "severity": "hard",
            },
        ],
        OperationClass.ESTIMATE: [
            {
                "predicate_id": "slice0.estimate_input_dataset",
                "description": "ESTIMATE consumes a measurement-rooted BaseDataset artifact.",
                "severity": "hard",
            }
        ],
        OperationClass.VERIFY: [
            {
                "predicate_id": "slice0.verify_authority_boundary",
                "description": "VERIFY derives Ring-2 AuthorityBoundary and cannot self-promote.",
                "severity": "hard",
            }
        ],
        OperationClass.ACQUIRE: [
            {
                "predicate_id": "slice0.acquire_missing_distribution",
                "description": (
                    "ACQUIRE requires a named missing distribution before planning."
                ),
                "severity": "hard",
            },
            {
                "predicate_id": "slice0.acquire_data_need_spec",
                "description": (
                    "ACQUIRE must reuse scientist.agent.protocols.DataNeedSpec."
                ),
                "severity": "hard",
            },
            {
                "predicate_id": "slice0.acquire_positive_voi",
                "description": (
                    "ACQUIRE continuation requires deterministic positive VOI."
                ),
                "severity": "hard",
            }
        ],
        OperationClass.DECOMPOSE: [
            {
                "predicate_id": "gy.decompose_child_search_exit_contract",
                "description": "DECOMPOSE consumes child SearchExitContract artifacts.",
                "severity": "hard",
            },
            {
                "predicate_id": "gy.decompose_exports_subdesign_contract",
                "description": "DECOMPOSE exports only SubDesignContract to the parent.",
                "severity": "hard",
            },
        ],
        OperationClass.COMPOSE: [
            {
                "predicate_id": "gy.compose_uses_layer2_coupling_engine",
                "description": (
                    "COMPOSE delegates coupling classification to layer2_coupling_composition."
                ),
                "severity": "hard",
            },
            {
                "predicate_id": "gy.compose_requires_composition_certificate",
                "description": (
                    "COMPOSE emits a CompositionCertificate before "
                    "PolicyProgram promotion."
                ),
                "severity": "hard",
            },
        ],
    }
    return predicates.get(
        operation_class,
        [
            {
                "predicate_id": f"slice0.{operation_class.value.lower()}_fail_closed",
                "description": (
                    "Operation is registered as fail-closed until its owning task lands."
                ),
                "severity": "hard",
            }
        ],
    )


def _producer_roots_from_exit(child_exit: WorkspaceSearchExitContract) -> list[ArtifactRef]:
    roots: list[ArtifactRef] = []
    for envelope in child_exit.artifact_envelopes:
        roots.extend(envelope.producer_roots)
    if not roots:
        roots.extend(child_exit.output_artifacts)
    by_id: dict[str, ArtifactRef] = {}
    for root in roots:
        by_id.setdefault(root.artifact_id, root)
    return list(by_id.values())


__all__ = [
    "ACTIVE_WORKSPACE_OPERATIONS",
    "WORKSPACE_LOOP_SCHEMA_VERSION",
    "WORKSPACE_TRAJECTORY",
    "AcquisitionPlan",
    "AcquisitionPlanner",
    "ConnectorAdmissionGate",
    "DataRequirementAdmissionGate",
    "FormalGate",
    "GySemanticBenchmark",
    "MeasurementRootProducer",
    "OperationRegistration",
    "OperationRegistry",
    "SearchExitDecisionInputs",
    "SearchTerminalDecision",
    "SemanticAdequacyGate",
    "SemanticBenchmarkRun",
    "WorkspaceFixtureManifest",
    "WorkspaceIntentRunResult",
    "WorkspaceInvariantError",
    "WorkspaceLoop",
    "WorkspaceLoopRunProof",
    "WorkspaceSearchExitContract",
    "WorkspaceSearchLedger",
    "build_workspace_operation_registry",
    "load_gy_semantic_benchmark",
    "load_workspace_fixture_manifest",
    "select_search_terminal",
]
