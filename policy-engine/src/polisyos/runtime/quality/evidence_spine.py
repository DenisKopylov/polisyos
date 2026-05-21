"""Evidence-spine carriers and propagation checks for scenario contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

EVIDENCE_SPINE_CARRIER_SCHEMA_VERSION = "policyos.evidence_spine_carrier.v1"
EVIDENCE_SPINE_GRAPH_SCHEMA_VERSION = "policyos.scenario_contract_propagation_graph.v1"


class EvidenceSpineValidationError(ValueError):
    """Raised when a scenario evidence carrier is not usable by producers."""


@dataclass(frozen=True)
class EvidenceRequirementBinding:
    """One producer's disposition for a scenario evidence requirement."""

    requirement_id: str
    status: str
    domain: str | None = None
    selected_refs: tuple[str, ...] = ()
    rejected_refs: tuple[str, ...] = ()
    blocker_code: str | None = None
    missing_facets: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()
    authority_envelope_ref: str | None = None

    def __post_init__(self) -> None:
        requirement_id = _clean_text(self.requirement_id)
        if requirement_id is None:
            raise EvidenceSpineValidationError("requirement_id is required")
        status = _clean_text(self.status)
        if status is None:
            raise EvidenceSpineValidationError("binding status is required")
        object.__setattr__(self, "requirement_id", requirement_id)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "domain", _clean_text(self.domain))
        object.__setattr__(self, "selected_refs", _text_tuple(self.selected_refs))
        object.__setattr__(self, "rejected_refs", _text_tuple(self.rejected_refs))
        object.__setattr__(self, "blocker_code", _clean_text(self.blocker_code))
        object.__setattr__(self, "missing_facets", _text_tuple(self.missing_facets))
        object.__setattr__(self, "limitation_refs", _text_tuple(self.limitation_refs))
        object.__setattr__(
            self,
            "authority_envelope_ref",
            _clean_text(self.authority_envelope_ref),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "domain": self.domain,
            "status": self.status,
            "selected_refs": list(self.selected_refs),
            "rejected_refs": list(self.rejected_refs),
            "blocker_code": self.blocker_code,
            "missing_facets": list(self.missing_facets),
            "limitation_refs": list(self.limitation_refs),
            "authority_envelope_ref": self.authority_envelope_ref,
        }


@dataclass(frozen=True)
class EvidenceSpineCarrier:
    """Runtime carrier that keeps scenario obligations attached to evidence."""

    scenario_evidence_contract_id: str
    requirement_ids: tuple[str, ...]
    producer_component: str
    producer_report_schema: str
    reader_contract: str
    authority_profile: str
    schema_version: str = EVIDENCE_SPINE_CARRIER_SCHEMA_VERSION
    spine_id: str | None = None
    trace_id: str | None = None
    parent_spine_ref: str | None = None
    scenario_contract_version: str | None = None
    code_revision: str | None = None
    carrier_classification: str = "internal_ref"
    redaction_policy: str = "refs_only_no_raw_payloads"
    input_refs: tuple[str, ...] = ()
    output_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        contract_id = _clean_text(self.scenario_evidence_contract_id)
        if contract_id is None:
            raise EvidenceSpineValidationError("scenario_evidence_contract_id is required")
        requirement_ids = _text_tuple(self.requirement_ids)
        if not requirement_ids:
            raise EvidenceSpineValidationError("requirement_ids are required")
        producer_component = _clean_text(self.producer_component)
        if producer_component is None:
            raise EvidenceSpineValidationError("producer_component is required")
        producer_report_schema = _clean_text(self.producer_report_schema)
        if producer_report_schema is None:
            raise EvidenceSpineValidationError("producer_report_schema is required")
        reader_contract = _clean_text(self.reader_contract)
        if reader_contract is None:
            raise EvidenceSpineValidationError("reader_contract is required")
        authority_profile = _clean_text(self.authority_profile)
        if authority_profile is None:
            raise EvidenceSpineValidationError("authority_profile is required")

        normalized = {
            "scenario_evidence_contract_id": contract_id,
            "requirement_ids": list(requirement_ids),
            "producer_component": producer_component,
            "producer_report_schema": producer_report_schema,
            "reader_contract": reader_contract,
            "authority_profile": authority_profile,
            "parent_spine_ref": _clean_text(self.parent_spine_ref),
            "code_revision": _clean_text(self.code_revision),
        }
        object.__setattr__(self, "scenario_evidence_contract_id", contract_id)
        object.__setattr__(self, "requirement_ids", requirement_ids)
        object.__setattr__(self, "producer_component", producer_component)
        object.__setattr__(self, "producer_report_schema", producer_report_schema)
        object.__setattr__(self, "reader_contract", reader_contract)
        object.__setattr__(self, "authority_profile", authority_profile)
        object.__setattr__(self, "spine_id", _clean_text(self.spine_id) or _stable_id(normalized))
        object.__setattr__(self, "trace_id", _clean_text(self.trace_id) or self.spine_id)
        object.__setattr__(self, "parent_spine_ref", _clean_text(self.parent_spine_ref))
        object.__setattr__(
            self,
            "scenario_contract_version",
            _clean_text(self.scenario_contract_version),
        )
        object.__setattr__(self, "code_revision", _clean_text(self.code_revision))
        object.__setattr__(
            self,
            "carrier_classification",
            _clean_text(self.carrier_classification) or "internal_ref",
        )
        object.__setattr__(
            self,
            "redaction_policy",
            _clean_text(self.redaction_policy) or "refs_only_no_raw_payloads",
        )
        object.__setattr__(self, "input_refs", _text_tuple(self.input_refs))
        object.__setattr__(self, "output_refs", _text_tuple(self.output_refs))

    @classmethod
    def from_scenario_contract(
        cls,
        scenario_contract: Mapping[str, Any],
        *,
        producer_component: str,
        producer_report_schema: str,
        reader_contract: str,
        authority_profile: str,
        code_revision: str | None = None,
        parent_spine_ref: str | None = None,
        input_refs: Sequence[Any] = (),
        output_refs: Sequence[Any] = (),
        trace_id: str | None = None,
        spine_id: str | None = None,
    ) -> EvidenceSpineCarrier:
        contract_id = _clean_text(
            scenario_contract.get("scenario_evidence_contract_id")
            or scenario_contract.get("contract_id")
            or scenario_contract.get("id")
        )
        requirement_ids = _requirement_ids_from_contract(scenario_contract)
        return cls(
            scenario_evidence_contract_id=contract_id or "",
            requirement_ids=requirement_ids,
            producer_component=producer_component,
            producer_report_schema=producer_report_schema,
            reader_contract=reader_contract,
            authority_profile=authority_profile,
            spine_id=spine_id,
            trace_id=trace_id,
            parent_spine_ref=parent_spine_ref,
            scenario_contract_version=_clean_text(
                scenario_contract.get("schema_version") or scenario_contract.get("version")
            ),
            code_revision=code_revision,
            input_refs=_text_tuple(input_refs),
            output_refs=_text_tuple(output_refs),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "spine_id": self.spine_id,
            "trace_id": self.trace_id,
            "parent_spine_ref": self.parent_spine_ref,
            "scenario_evidence_contract_id": self.scenario_evidence_contract_id,
            "scenario_contract_version": self.scenario_contract_version,
            "requirement_ids": list(self.requirement_ids),
            "producer_component": self.producer_component,
            "producer_report_schema": self.producer_report_schema,
            "reader_contract": self.reader_contract,
            "authority_profile": self.authority_profile,
            "code_revision": self.code_revision,
            "carrier_classification": self.carrier_classification,
            "redaction_policy": self.redaction_policy,
            "input_refs": list(self.input_refs),
            "output_refs": list(self.output_refs),
        }


@dataclass(frozen=True)
class EvidenceSpineNode:
    """One producer artifact in the scenario-contract propagation graph."""

    node_id: str
    producer_component: str
    artifact_ref: str
    consumed_carrier: EvidenceSpineCarrier
    emitted_scenario_evidence_contract_id: str | None
    consumed_requirement_ids: tuple[str, ...] = ()
    emitted_requirement_ids: tuple[str, ...] = ()
    bindings: tuple[EvidenceRequirementBinding, ...] = ()
    status: str = "pass"
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        node_id = _clean_text(self.node_id)
        if node_id is None:
            raise EvidenceSpineValidationError("node_id is required")
        producer_component = _clean_text(self.producer_component)
        if producer_component is None:
            raise EvidenceSpineValidationError("producer_component is required")
        artifact_ref = _clean_text(self.artifact_ref)
        if artifact_ref is None:
            raise EvidenceSpineValidationError("artifact_ref is required")
        object.__setattr__(self, "node_id", node_id)
        object.__setattr__(self, "producer_component", producer_component)
        object.__setattr__(self, "artifact_ref", artifact_ref)
        object.__setattr__(
            self,
            "emitted_scenario_evidence_contract_id",
            _clean_text(self.emitted_scenario_evidence_contract_id),
        )
        object.__setattr__(
            self,
            "consumed_requirement_ids",
            _text_tuple(self.consumed_requirement_ids) or self.consumed_carrier.requirement_ids,
        )
        object.__setattr__(self, "emitted_requirement_ids", _text_tuple(self.emitted_requirement_ids))
        object.__setattr__(self, "bindings", tuple(self.bindings))
        object.__setattr__(self, "status", _clean_text(self.status) or "pass")
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "producer_component": self.producer_component,
            "artifact_ref": self.artifact_ref,
            "status": self.status,
            "consumed_scenario_evidence_contract_id": (
                self.consumed_carrier.scenario_evidence_contract_id
            ),
            "emitted_scenario_evidence_contract_id": self.emitted_scenario_evidence_contract_id,
            "consumed_requirement_ids": list(self.consumed_requirement_ids),
            "emitted_requirement_ids": list(self.emitted_requirement_ids),
            "binding_count": len(self.bindings),
            "bindings": [binding.to_dict() for binding in self.bindings],
            "carrier": self.consumed_carrier.to_dict(),
            "metadata": dict(self.metadata),
        }


def build_evidence_spine_graph(
    nodes: Sequence[EvidenceSpineNode],
    *,
    bundle_ref: str | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Evaluate whether scenario contract IDs and requirements survive producers."""

    normalized_nodes = list(nodes)
    findings: list[dict[str, Any]] = []
    for node in normalized_nodes:
        expected_contract_id = node.consumed_carrier.scenario_evidence_contract_id
        observed_contract_id = node.emitted_scenario_evidence_contract_id
        if observed_contract_id is None:
            findings.append(
                _finding(
                    code="evidence_spine_contract_dropped",
                    message=(
                        "Producer consumed a scenario evidence contract but emitted no "
                        "scenario_evidence_contract_id."
                    ),
                    node=node,
                    expected_contract_id=expected_contract_id,
                    observed_contract_id=None,
                    missing_requirement_ids=(),
                )
            )
        elif observed_contract_id != expected_contract_id:
            findings.append(
                _finding(
                    code="evidence_spine_contract_mismatch",
                    message=(
                        "Producer emitted a different scenario_evidence_contract_id than "
                        "the contract it consumed."
                    ),
                    node=node,
                    expected_contract_id=expected_contract_id,
                    observed_contract_id=observed_contract_id,
                    missing_requirement_ids=(),
                )
            )

        consumed_requirement_ids = set(node.consumed_requirement_ids)
        emitted_requirement_ids = set(node.emitted_requirement_ids)
        missing_requirement_ids = tuple(
            sorted(consumed_requirement_ids.difference(emitted_requirement_ids))
        )
        if consumed_requirement_ids and not emitted_requirement_ids:
            findings.append(
                _finding(
                    code="evidence_spine_requirement_ids_dropped",
                    message=(
                        "Producer consumed scenario requirement ids but emitted no "
                        "requirement id bindings."
                    ),
                    node=node,
                    expected_contract_id=expected_contract_id,
                    observed_contract_id=observed_contract_id,
                    missing_requirement_ids=missing_requirement_ids,
                )
            )
        elif missing_requirement_ids:
            findings.append(
                _finding(
                    code="evidence_spine_requirement_ids_partially_dropped",
                    message=(
                        "Producer emitted only a subset of consumed scenario requirement ids."
                    ),
                    node=node,
                    expected_contract_id=expected_contract_id,
                    observed_contract_id=observed_contract_id,
                    missing_requirement_ids=missing_requirement_ids,
                )
            )

    status = "fail" if any(item["status"] == "fail" for item in findings) else "pass"
    consumed_requirement_count = len(
        {
            requirement_id
            for node in normalized_nodes
            for requirement_id in node.consumed_requirement_ids
        }
    )
    emitted_requirement_count = len(
        {
            requirement_id
            for node in normalized_nodes
            for requirement_id in node.emitted_requirement_ids
        }
    )
    return {
        "schema_version": EVIDENCE_SPINE_GRAPH_SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "bundle_ref": bundle_ref,
        "status": status,
        "summary": {
            "node_count": len(normalized_nodes),
            "finding_count": len(findings),
            "consumed_requirement_count": consumed_requirement_count,
            "emitted_requirement_count": emitted_requirement_count,
        },
        "nodes": [node.to_dict() for node in normalized_nodes],
        "findings": findings,
    }


def build_scenario_contract_propagation_graph(
    *,
    request_payload: Mapping[str, Any] | None,
    bundle_payload: Mapping[str, Any] | None = None,
    quality_evidence_payload: Mapping[str, Any] | None = None,
    bundle_ref: str | None = None,
    authority_profile: str | None = None,
    code_revision: str | None = None,
) -> dict[str, Any]:
    """Build a graph from known bundle surfaces without exposing raw secrets."""

    scenario_contract = find_scenario_evidence_contract(
        request_payload=request_payload,
        bundle_payload=bundle_payload,
        quality_evidence_payload=quality_evidence_payload,
    )
    if scenario_contract is None:
        return _invalid_graph(
            code="evidence_spine_contract_missing",
            message="No scenario_evidence_contract was found in request, bundle, or reports.",
            bundle_ref=bundle_ref,
        )

    try:
        carrier = EvidenceSpineCarrier.from_scenario_contract(
            scenario_contract,
            producer_component="runtime.nl_pipeline",
            producer_report_schema="policyos.runtime.request_context.v1",
            reader_contract="runtime_quality.scenario_contract_propagation_graph",
            authority_profile=authority_profile or "unknown",
            code_revision=code_revision,
            output_refs=("request.sanitized.json",),
        )
    except EvidenceSpineValidationError as exc:
        return _invalid_graph(
            code="evidence_spine_contract_invalid",
            message=str(exc),
            bundle_ref=bundle_ref,
        )

    quality_evidence = dict(quality_evidence_payload or {})
    nodes: list[EvidenceSpineNode] = [
        EvidenceSpineNode(
            node_id="runtime.request_context",
            producer_component="runtime.nl_pipeline",
            artifact_ref="request.sanitized.json",
            consumed_carrier=carrier,
            emitted_scenario_evidence_contract_id=carrier.scenario_evidence_contract_id,
            consumed_requirement_ids=carrier.requirement_ids,
            emitted_requirement_ids=carrier.requirement_ids,
            metadata={"surface": "request"},
        )
    ]
    nodes.extend(_nodes_from_quality_evidence(carrier, quality_evidence))
    return build_evidence_spine_graph(nodes, bundle_ref=bundle_ref)


def find_scenario_evidence_contract(
    *,
    request_payload: Mapping[str, Any] | None,
    bundle_payload: Mapping[str, Any] | None = None,
    quality_evidence_payload: Mapping[str, Any] | None = None,
) -> Mapping[str, Any] | None:
    """Find the scenario evidence contract on the bundle surfaces that carry it."""

    candidates = [
        _nested_mapping(request_payload, ("context", "scenario_evidence_contract")),
        _nested_mapping(request_payload, ("scenario_evidence_contract",)),
        _nested_mapping(bundle_payload, ("command", "scenario_evidence_contract")),
        _nested_mapping(bundle_payload, ("scenario_evidence_contract",)),
        _nested_mapping(quality_evidence_payload, ("golden_scenario_contract",)),
        _nested_mapping(quality_evidence_payload, ("golden_scenario_contract", "contract")),
        _nested_mapping(
            quality_evidence_payload,
            ("golden_scenario_contract", "scenario_evidence_contract"),
        ),
    ]
    for candidate in candidates:
        if candidate is not None:
            if "contract_id" in candidate or "scenario_evidence_contract_id" in candidate:
                return candidate
    return None


def _nodes_from_quality_evidence(
    carrier: EvidenceSpineCarrier,
    quality_evidence: Mapping[str, Any],
) -> list[EvidenceSpineNode]:
    nodes: list[EvidenceSpineNode] = []
    fabric = _mapping(quality_evidence.get("fabric_retrieval_trace"))
    if fabric is not None:
        fabric_consumed, fabric_emitted = _fabric_requirement_ids(fabric, carrier)
        if _producer_consumes_contract(fabric, fabric_consumed):
            nodes.append(
                EvidenceSpineNode(
                    node_id="fabric.retrieval_trace",
                    producer_component="fabric",
                    artifact_ref="quality_evidence/fabric_retrieval_trace.json",
                    consumed_carrier=carrier,
                    emitted_scenario_evidence_contract_id=_clean_text(
                        fabric.get("scenario_evidence_contract_id")
                    ),
                    consumed_requirement_ids=fabric_consumed,
                    emitted_requirement_ids=fabric_emitted,
                    bindings=_bindings_from_findings(
                        _nested_list(
                            fabric,
                            (
                                "production_data_contract_binding_report",
                                "scenario_binding_findings",
                            ),
                        )
                    ),
                )
            )

    normative = _mapping(quality_evidence.get("normative_evidence"))
    if normative is not None:
        lex_consumed, lex_emitted = _lex_requirement_ids(normative, carrier)
        if _producer_consumes_contract(normative, lex_consumed):
            nodes.append(
                EvidenceSpineNode(
                    node_id="lex.normative_evidence",
                    producer_component="lex",
                    artifact_ref="quality_evidence/normative_evidence.json",
                    consumed_carrier=carrier,
                    emitted_scenario_evidence_contract_id=_clean_text(
                        normative.get("scenario_evidence_contract_id")
                    ),
                    consumed_requirement_ids=lex_consumed,
                    emitted_requirement_ids=lex_emitted,
                    bindings=_bindings_from_findings(_nested_list(normative, ("legal_requirements",))),
                )
            )

    for report_key, component, filename in (
        (
            "foundry_method_report",
            "foundry",
            "quality_evidence/foundry_method_report.json",
        ),
        (
            "policy_grounding_matrix",
            "scientist.policy_grounding",
            "quality_evidence/policy_grounding_matrix.json",
        ),
        (
            "semantic_binding_ledger",
            "runtime.semantic_binding",
            "quality_evidence/semantic_binding_ledger.json",
        ),
        (
            "policy_design_case",
            "runtime.policy_design_case",
            "quality_evidence/policy_design_case.json",
        ),
    ):
        report = _mapping(quality_evidence.get(report_key))
        if report is None:
            continue
        consumed = _report_requirement_ids(report)
        if not _producer_consumes_contract(report, consumed):
            continue
        emitted = _report_requirement_ids(
            report,
            keys=(
                "emitted_requirement_ids",
                "requirement_ids",
                "scenario_requirement_refs",
            ),
        )
        nodes.append(
            EvidenceSpineNode(
                node_id=report_key.replace("_", "."),
                producer_component=component,
                artifact_ref=filename,
                consumed_carrier=carrier,
                emitted_scenario_evidence_contract_id=_clean_text(
                    report.get("scenario_evidence_contract_id")
                ),
                consumed_requirement_ids=consumed,
                emitted_requirement_ids=emitted,
            )
        )

    return nodes


def _producer_consumes_contract(
    report: Mapping[str, Any],
    consumed_requirement_ids: tuple[str, ...],
) -> bool:
    if consumed_requirement_ids:
        return True
    for key in (
        "scenario_contract_id",
        "scenario_evidence_contract_id",
        "scenario_evidence_contract",
        "contract_id",
    ):
        if _clean_text(report.get(key)) is not None:
            return True
    for key in ("production_data_contract_binding_report", "query_normalization_report"):
        nested = _mapping(report.get(key))
        if nested is not None and (
            _clean_text(nested.get("scenario_contract_id"))
            or _clean_text(nested.get("scenario_evidence_contract_id"))
            or _nested_list(nested, ("legal_requirements",))
            or _nested_list(nested, ("scenario_binding_findings",))
        ):
            return True
    return False


def _fabric_requirement_ids(
    report: Mapping[str, Any],
    carrier: EvidenceSpineCarrier,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    binding_report = _mapping(report.get("production_data_contract_binding_report")) or {}
    findings = _nested_list(binding_report, ("scenario_binding_findings",))
    emitted = _requirement_ids_from_items(findings)
    consumed = emitted or _domain_requirement_ids(carrier, "data")
    return consumed, emitted


def _lex_requirement_ids(
    report: Mapping[str, Any],
    carrier: EvidenceSpineCarrier,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    emitted = _requirement_ids_from_items(_nested_list(report, ("legal_requirements",)))
    query_requirements = _requirement_ids_from_items(
        _nested_list(report, ("query_normalization_report", "legal_requirements"))
    )
    consumed = query_requirements or emitted or _domain_requirement_ids(carrier, "legal")
    return consumed, emitted


def _report_requirement_ids(
    report: Mapping[str, Any],
    *,
    keys: Sequence[str] = (
        "consumed_requirement_ids",
        "requirement_ids",
        "scenario_requirement_refs",
        "scenario_requirement_ids",
    ),
) -> tuple[str, ...]:
    ids: list[str] = []
    for key in keys:
        value = report.get(key)
        if isinstance(value, str):
            ids.append(value)
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            ids.extend(str(item) for item in value)
    return _text_tuple(ids)


def _domain_requirement_ids(
    carrier: EvidenceSpineCarrier,
    domain: str,
) -> tuple[str, ...]:
    marker = f":{domain}:"
    return tuple(item for item in carrier.requirement_ids if marker in item)


def _bindings_from_findings(items: Sequence[Any]) -> tuple[EvidenceRequirementBinding, ...]:
    bindings: list[EvidenceRequirementBinding] = []
    for item in items:
        mapping = _mapping(item)
        if mapping is None:
            continue
        requirement_id = _clean_text(mapping.get("requirement_id"))
        if requirement_id is None:
            continue
        bindings.append(
            EvidenceRequirementBinding(
                requirement_id=requirement_id,
                domain=_clean_text(mapping.get("domain")),
                status=_clean_text(mapping.get("status")) or "unknown",
                selected_refs=_text_tuple(
                    mapping.get("selected_refs") or mapping.get("selected_norm_refs") or ()
                ),
                rejected_refs=_text_tuple(
                    mapping.get("rejected_refs") or mapping.get("rejected_norm_refs") or ()
                ),
                blocker_code=_clean_text(mapping.get("blocker_code") or mapping.get("reason_code")),
                missing_facets=_text_tuple(mapping.get("missing_facets") or ()),
                limitation_refs=_text_tuple(mapping.get("limitation_refs") or ()),
                authority_envelope_ref=_clean_text(mapping.get("authority_envelope_ref")),
            )
        )
    return tuple(bindings)


def _invalid_graph(*, code: str, message: str, bundle_ref: str | None) -> dict[str, Any]:
    return {
        "schema_version": EVIDENCE_SPINE_GRAPH_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "bundle_ref": bundle_ref,
        "status": "fail",
        "summary": {
            "node_count": 0,
            "finding_count": 1,
            "consumed_requirement_count": 0,
            "emitted_requirement_count": 0,
        },
        "nodes": [],
        "findings": [
            {
                "status": "fail",
                "severity": "error",
                "code": code,
                "message": message,
                "producer_component": "runtime.nl_pipeline",
                "artifact_ref": "request.sanitized.json",
                "expected_contract_id": None,
                "observed_contract_id": None,
                "missing_requirement_ids": [],
                "root_cause_class": "evidence_spine_connectivity",
                "next_action": (
                    "Carry a normalized scenario_evidence_contract with requirement ids "
                    "through the runtime request context before producer execution."
                ),
            }
        ],
    }


def _finding(
    *,
    code: str,
    message: str,
    node: EvidenceSpineNode,
    expected_contract_id: str,
    observed_contract_id: str | None,
    missing_requirement_ids: Sequence[str],
) -> dict[str, Any]:
    return {
        "status": "fail",
        "severity": "error",
        "code": code,
        "message": message,
        "producer_component": node.producer_component,
        "node_id": node.node_id,
        "artifact_ref": node.artifact_ref,
        "expected_contract_id": expected_contract_id,
        "observed_contract_id": observed_contract_id,
        "consumed_requirement_ids": list(node.consumed_requirement_ids),
        "emitted_requirement_ids": list(node.emitted_requirement_ids),
        "missing_requirement_ids": list(missing_requirement_ids),
        "root_cause_class": "evidence_spine_connectivity",
        "next_action": (
            "Emit scenario_evidence_contract_id and the exact consumed requirement ids "
            "on the producer artifact before reader gates evaluate closure."
        ),
    }


def _requirement_ids_from_contract(contract: Mapping[str, Any]) -> tuple[str, ...]:
    ids = _report_requirement_ids(contract, keys=("requirement_ids",))
    if ids:
        return ids
    return _requirement_ids_from_items(contract.get("requirements"))


def _requirement_ids_from_items(items: Any) -> tuple[str, ...]:
    if isinstance(items, Mapping):
        items = [items]
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        return ()
    ids: list[str] = []
    for item in items:
        if isinstance(item, str):
            ids.append(item)
            continue
        mapping = _mapping(item)
        if mapping is None:
            continue
        requirement_id = _clean_text(
            mapping.get("requirement_id")
            or mapping.get("scenario_requirement_id")
            or mapping.get("id")
        )
        if requirement_id is not None:
            ids.append(requirement_id)
    return _text_tuple(ids)


def _nested_mapping(
    payload: Mapping[str, Any] | None,
    path: Sequence[str],
) -> Mapping[str, Any] | None:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current if isinstance(current, Mapping) else None


def _nested_list(payload: Mapping[str, Any], path: Sequence[str]) -> list[Any]:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return []
        current = current.get(key)
    return list(current) if isinstance(current, list) else []


def _mapping(value: Any) -> Mapping[str, Any] | None:
    return value if isinstance(value, Mapping) else None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _text_tuple(values: Any) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, Sequence) or isinstance(values, (bytes, bytearray)):
        return ()
    result: list[str] = []
    for value in values:
        text = _clean_text(value)
        if text is not None and text not in result:
            result.append(text)
    return tuple(result)


def _stable_id(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "evidence-spine:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:24]
