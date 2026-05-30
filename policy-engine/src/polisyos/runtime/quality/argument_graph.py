"""Argument and warrant graph builder for runtime Policy Design Cases.

The graph is a runtime-quality explanation artifact. It preserves the path from
claim to readiness, but it does not mint claim, evidence, projection, or
readiness authority.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from polisyos.runtime.quality.assurance_case import (
    POLICY_DESIGN_CASE_NODE_MAPPING,
    POLICY_DESIGN_CASE_PROFILE_METADATA,
)
from polisyos.runtime.quality.claim_argument import CLAIM_ARGUMENT_NODE_MAPPING
from polisyos.runtime.quality.explanation_reliability import (
    warrant_berl_reliability_refs,
    warrant_requires_berl_reliability,
)
from polisyos.runtime.quality.prompt_tool_ledger import (
    persist_runtime_quality_json_artifact,
)

ARGUMENT_GRAPH_SCHEMA_VERSION = "policyos.runtime.policy_design_case.argument_graph.v1"
ARGUMENT_GRAPH_INSPECTION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.argument_graph.inspection.v1"
)
ARGUMENT_GRAPH_EXPORT_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.argument_graph.export.v1"
)
ARGUMENT_GRAPH_CONTRACT_ID = "policy_design_case.argument_warrant_graph.v1"
ARGUMENT_GRAPH_KIND = "runtime_quality.policy_design_case.argument_graph"
ARGUMENT_GRAPH_NEXT_DIAGNOSTIC_COMMAND = (
    "uv run pytest tests/unit/runtime/quality/test_argument_graph.py "
    "tests/unit/runtime/quality/test_claim_argument.py -q"
)

ArgumentGraphExportProfile = Literal["all", "sacm", "cae", "gsn"]

_VALID_AUTHORITY_ROLES = frozenset({"producer_authority", "runtime_blocker"})
_VALID_AUTHORITY_PROVENANCE = frozenset({"runtime_emitted", "runtime_blocker"})
_PASSING_READINESS_STATUSES = frozenset(
    {"pass", "passed", "ok", "ready", "publishable", "accepted"}
)

_CLAIM_KEYS = (
    "final_major_claims",
    "major_claims",
    "claims",
    "claim_records",
)
_ARGUMENT_KEYS = ("arguments", "argument_records", "claim_arguments")
_WARRANT_KEYS = ("warrants", "warrant_records", "claim_warrants")
_EVIDENCE_KEYS = (
    "evidence_records",
    "producer_evidence",
    "producer_evidence_records",
    "evidence",
    "evidence_nodes",
)
_AUTHORITY_KEYS = (
    "authority_records",
    "authorities",
    "runtime_authorities",
    "authority_nodes",
)
_READINESS_KEYS = (
    "readiness_records",
    "readiness",
    "readiness_nodes",
    "claim_readiness",
    "closeout_readiness",
)
_NODE_ID_KEYS = (
    "node_id",
    "assurance_node_id",
    "assurance_node_ref",
    "record_id",
    "id",
    "cas_ref",
    "evidence_ref",
)
_CLAIM_ID_KEYS = ("claim_id", "id", "record_id")
_CLAIM_REF_KEYS = (
    "claim_ref",
    "assurance_node_id",
    "assurance_node_ref",
    "cas_ref",
    "evidence_ref",
    "record_id",
    "id",
)
_SURFACE_ID_KEYS = {
    "argument": ("argument_id", *_NODE_ID_KEYS),
    "warrant": ("warrant_id", *_NODE_ID_KEYS),
    "evidence": ("evidence_id", "producer_evidence_id", *_NODE_ID_KEYS),
    "authority": ("authority_id", *_NODE_ID_KEYS),
    "readiness": ("readiness_id", *_NODE_ID_KEYS),
}


class ArgumentGraphError(ValueError):
    """Fail-closed argument graph construction error."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class ArgumentGraphIssue(BaseModel):
    """One machine-readable graph issue."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    claim_id: str | None = None
    node_id: str | None = None
    node_type: str | None = None
    field: str | None = None
    severity: str = "error"

    @field_validator("code", "message", "severity")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _required_text(value, "required_text")

    @field_validator("claim_id", "node_id", "node_type", "field")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)


class WarrantAssumption(BaseModel):
    """Typed assumption used by a warrant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assumption_id: str | None = None
    statement: str = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(default=())

    @field_validator("assumption_id")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("statement")
    @classmethod
    def _strip_statement(cls, value: str) -> str:
        return _required_text(value, "statement")

    @field_validator("source_refs", mode="before")
    @classmethod
    def _strip_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class ApplicabilityPredicate(BaseModel):
    """Machine-readable applicability predicate for a warrant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    predicate_id: str | None = None
    expression: str = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(default=())

    @field_validator("predicate_id")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("expression")
    @classmethod
    def _strip_expression(cls, value: str) -> str:
        return _required_text(value, "expression")

    @field_validator("source_refs", mode="before")
    @classmethod
    def _strip_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class WarrantLimit(BaseModel):
    """Typed boundary or limitation carried by a warrant."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    limit_id: str | None = None
    statement: str = Field(min_length=1)
    severity: str | None = None
    source_refs: tuple[str, ...] = Field(default=())

    @field_validator("limit_id", "severity")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator("statement")
    @classmethod
    def _strip_statement(cls, value: str) -> str:
        return _required_text(value, "statement")

    @field_validator("source_refs", mode="before")
    @classmethod
    def _strip_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class WarrantSemantics(BaseModel):
    """Typed warrant semantics required for machine inspection."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    assumptions: tuple[WarrantAssumption, ...] = Field(default=())
    applicability_predicates: tuple[ApplicabilityPredicate, ...] = Field(default=())
    confidence_refs: tuple[str, ...] = Field(default=())
    reliability_refs: tuple[str, ...] = Field(default=())
    berl_refs: tuple[str, ...] = Field(default=())
    limits: tuple[WarrantLimit, ...] = Field(default=())

    @field_validator("confidence_refs", "reliability_refs", "berl_refs", mode="before")
    @classmethod
    def _strip_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible warrant semantics payload."""

        return self.model_dump(mode="json", exclude_none=True)


def build_argument_graph(
    policy_design_case: Mapping[str, Any],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a runtime-emitted argument/warrant graph over PDC claim surfaces.

    Args:
        policy_design_case: A runtime Policy Design Case graph or compatible
            claim-argument surface.
        generated_at: Optional timestamp for deterministic tests.

    Returns:
        JSON-compatible argument graph with claim, argument, warrant, evidence,
        authority, readiness nodes, typed warrant semantics, edges, and issues.
    """

    if not isinstance(policy_design_case, Mapping):
        raise ArgumentGraphError(
            "argument_graph_case_invalid",
            "Argument graph input must be a mapping.",
        )

    policy_design_case = _runtime_pdc_graph_argument_surface(policy_design_case)
    generated = _utc(generated_at)
    claims = _claim_rows(policy_design_case)
    argument_rows = _surface_rows(policy_design_case, _ARGUMENT_KEYS)
    warrant_rows = _surface_rows(policy_design_case, _WARRANT_KEYS)
    evidence_rows = _surface_rows(policy_design_case, _EVIDENCE_KEYS)
    authority_rows = _surface_rows(policy_design_case, _AUTHORITY_KEYS)
    readiness_rows = _surface_rows(policy_design_case, _READINESS_KEYS)

    issues: list[ArgumentGraphIssue] = []
    claim_nodes: list[dict[str, Any]] = []
    argument_nodes: list[dict[str, Any]] = []
    warrant_nodes: list[dict[str, Any]] = []
    evidence_nodes: list[dict[str, Any]] = []
    authority_nodes: list[dict[str, Any]] = []
    readiness_nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    seen_arguments: set[str] = set()
    seen_warrants: set[str] = set()
    seen_evidence: set[str] = set()
    seen_authority: set[str] = set()
    seen_readiness: set[str] = set()

    if not claims:
        issues.append(
            ArgumentGraphIssue(
                code="argument_graph_claims_missing",
                message="Argument graph requires at least one major claim.",
                field="final_major_claims",
            )
        )

    for claim in claims:
        claim_id = _required_text(
            _first_text(*(claim.get(key) for key in _CLAIM_ID_KEYS)),
            "unknown_claim",
        )
        claim_node_id = _first_text(
            claim.get("assurance_node_id"),
            claim.get("assurance_node_ref"),
            claim.get("node_id"),
            claim.get("claim_ref"),
            claim.get("cas_ref"),
            claim_id,
        )
        claim_node = {
            "node_id": claim_node_id,
            "node_type": "claim",
            "claim_id": claim_id,
            "claim_ref": _first_text(*(claim.get(key) for key in _CLAIM_REF_KEYS)),
            "text": _first_text(
                claim.get("claim_text"),
                claim.get("text"),
                claim.get("statement"),
                claim.get("summary"),
            ),
            "status": _first_text(claim.get("status"), claim.get("claim_status")),
            "major": bool(claim.get("major", True)),
        }
        claim_nodes.append(_drop_none(claim_node))

        matched_arguments = _matched_rows(
            claim,
            argument_rows,
            surface="argument",
            ref_keys=("argument_refs", "argument_ref", "argument_node_refs"),
            claim_id=claim_id,
        )
        matched_warrants = _matched_rows(
            claim,
            warrant_rows,
            surface="warrant",
            ref_keys=("warrant_refs", "warrant_ref", "warrant_node_refs"),
            claim_id=claim_id,
        )
        matched_evidence = _matched_rows(
            claim,
            evidence_rows,
            surface="evidence",
            ref_keys=(
                "evidence_refs",
                "evidence_ref",
                "producer_evidence_refs",
                "producer_evidence_ref",
            ),
            claim_id=claim_id,
        )
        matched_readiness = _matched_rows(
            claim,
            readiness_rows,
            surface="readiness",
            ref_keys=("readiness_refs", "readiness_ref", "closeout_refs"),
            claim_id=claim_id,
        )

        if not matched_arguments:
            issues.append(
                _issue(
                    "argument_graph_argument_missing",
                    "Every major claim must cite at least one argument node.",
                    claim_id=claim_id,
                    node_id=claim_node_id,
                    node_type="claim",
                    field="argument_refs",
                )
            )
        if not matched_warrants:
            issues.append(
                _issue(
                    "argument_graph_warrant_missing",
                    "Every major claim must cite at least one warrant node.",
                    claim_id=claim_id,
                    node_id=claim_node_id,
                    node_type="claim",
                    field="warrant_refs",
                )
            )
        if not matched_evidence:
            issues.append(
                _issue(
                    "argument_graph_evidence_missing",
                    "Every major claim must connect warrants to runtime evidence.",
                    claim_id=claim_id,
                    node_id=claim_node_id,
                    node_type="claim",
                    field="evidence_refs",
                )
            )
        if not matched_readiness:
            issues.append(
                _issue(
                    "argument_graph_readiness_missing",
                    "Every major claim must connect authority to a readiness node.",
                    claim_id=claim_id,
                    node_id=claim_node_id,
                    node_type="claim",
                    field="readiness_refs",
                )
            )

        for argument in matched_arguments:
            argument_node = _argument_node(argument, claim_id=claim_id)
            if argument_node["node_id"] not in seen_arguments:
                argument_nodes.append(argument_node)
                seen_arguments.add(argument_node["node_id"])
            edges.append(
                _edge(
                    "claim_supported_by_argument",
                    claim_node_id,
                    argument_node["node_id"],
                    claim_id=claim_id,
                )
            )

        for argument in matched_arguments or ():
            argument_id = _identity(argument, "argument")
            argument_warrants = _matched_rows(
                argument,
                matched_warrants,
                surface="warrant",
                ref_keys=("warrant_refs", "warrant_ref", "warrant_node_refs"),
                claim_id=claim_id,
            ) or matched_warrants
            for warrant in argument_warrants:
                warrant_node, warrant_issues = _warrant_node(warrant, claim_id=claim_id)
                issues.extend(warrant_issues)
                if warrant_node["node_id"] not in seen_warrants:
                    warrant_nodes.append(warrant_node)
                    seen_warrants.add(warrant_node["node_id"])
                edges.append(
                    _edge(
                        "argument_justified_by_warrant",
                        argument_id,
                        warrant_node["node_id"],
                        claim_id=claim_id,
                    )
                )

        for warrant in matched_warrants:
            warrant_id = _identity(warrant, "warrant")
            warrant_evidence = _matched_rows(
                warrant,
                matched_evidence,
                surface="evidence",
                ref_keys=(
                    "evidence_refs",
                    "evidence_ref",
                    "producer_evidence_refs",
                    "producer_evidence_ref",
                ),
                claim_id=claim_id,
            ) or matched_evidence
            for evidence in warrant_evidence:
                evidence_node = _evidence_node(evidence, claim_id=claim_id)
                if evidence_node["node_id"] not in seen_evidence:
                    evidence_nodes.append(evidence_node)
                    seen_evidence.add(evidence_node["node_id"])
                edges.append(
                    _edge(
                        "warrant_grounded_in_evidence",
                        warrant_id,
                        evidence_node["node_id"],
                        claim_id=claim_id,
                    )
                )

                authority_node, authority_issues = _authority_node_for_evidence(
                    evidence,
                    authority_rows=authority_rows,
                    claim_id=claim_id,
                )
                issues.extend(authority_issues)
                if authority_node is None:
                    continue
                if authority_node["node_id"] not in seen_authority:
                    authority_nodes.append(authority_node)
                    seen_authority.add(authority_node["node_id"])
                edges.append(
                    _edge(
                        "evidence_bounded_by_authority",
                        evidence_node["node_id"],
                        authority_node["node_id"],
                        claim_id=claim_id,
                    )
                )

                for readiness in matched_readiness:
                    readiness_node = _readiness_node(readiness, claim_id=claim_id)
                    if readiness_node["node_id"] not in seen_readiness:
                        readiness_nodes.append(readiness_node)
                        seen_readiness.add(readiness_node["node_id"])
                    if readiness_node["status"] not in _PASSING_READINESS_STATUSES:
                        issues.append(
                            _issue(
                                "argument_graph_readiness_not_passing",
                                "Readiness node does not report a passing status.",
                                claim_id=claim_id,
                                node_id=readiness_node["node_id"],
                                node_type="readiness",
                                field="status",
                            )
                        )
                    edges.append(
                        _edge(
                            "authority_feeds_readiness",
                            authority_node["node_id"],
                            readiness_node["node_id"],
                            claim_id=claim_id,
                        )
                    )

    issue_dicts = [issue.model_dump(mode="json", exclude_none=True) for issue in issues]
    status = "blocked" if any(issue.severity == "error" for issue in issues) else "pass"
    graph = {
        "schema_version": ARGUMENT_GRAPH_SCHEMA_VERSION,
        "contract_id": ARGUMENT_GRAPH_CONTRACT_ID,
        "generated_at": generated.isoformat(),
        "status": status,
        "capability_reality_label": "implemented",
        "argument_graph_ref": _stable_ref(
            "argument-graph",
            {
                "case_id": _text(policy_design_case.get("case_id")),
                "run_id": _text(policy_design_case.get("run_id")),
                "claim_ids": [claim.get("claim_id") for claim in claim_nodes],
                "generated_at": generated.isoformat(),
            },
        ),
        "case_id": _text(policy_design_case.get("case_id")),
        "run_id": _text(policy_design_case.get("run_id")),
        "job_id": _text(policy_design_case.get("job_id")),
        "tenant_id": _text(policy_design_case.get("tenant_id")),
        "effective_execution_profile": _text(
            policy_design_case.get("effective_execution_profile")
        ),
        "authority_boundary": _authority_boundary(),
        "profile_metadata": {
            "extends": "polisyos.runtime.quality.assurance_case",
            "assurance_case_profile": dict(POLICY_DESIGN_CASE_PROFILE_METADATA),
            "node_mapping": dict(POLICY_DESIGN_CASE_NODE_MAPPING),
        },
        "claims": claim_nodes,
        "arguments": argument_nodes,
        "warrants": warrant_nodes,
        "evidence": evidence_nodes,
        "authority": authority_nodes,
        "readiness": readiness_nodes,
        "edges": _dedupe_edges(edges),
        "issues": issue_dicts,
        "inspection": {
            "inspection_schema_version": ARGUMENT_GRAPH_INSPECTION_SCHEMA_VERSION,
            "status": status,
            "surface": "argument_graph",
            "machine_readable": True,
        },
        "next_diagnostic_command": ARGUMENT_GRAPH_NEXT_DIAGNOSTIC_COMMAND,
    }
    graph["summary"] = {
        "claim_count": len(claim_nodes),
        "argument_count": len(argument_nodes),
        "warrant_count": len(warrant_nodes),
        "evidence_count": len(evidence_nodes),
        "authority_count": len(authority_nodes),
        "readiness_count": len(readiness_nodes),
        "edge_count": len(graph["edges"]),
        "issue_count": len(issue_dicts),
    }
    return graph


def inspect_argument_graph(argument_graph: Mapping[str, Any]) -> dict[str, Any]:
    """Return the machine-readable warrant inspection surface for a graph."""

    graph = _graph(argument_graph)
    issues = _issue_rows(graph)
    issues_by_claim: dict[str, list[Mapping[str, Any]]] = {}
    issues_by_node: dict[str, list[Mapping[str, Any]]] = {}
    for issue in issues:
        if claim_id := _text(issue.get("claim_id")):
            issues_by_claim.setdefault(claim_id, []).append(issue)
        if node_id := _text(issue.get("node_id")):
            issues_by_node.setdefault(node_id, []).append(issue)

    claim_paths = [
        _claim_path(
            claim,
            graph,
            issues=tuple(issues_by_claim.get(_text(claim.get("claim_id")) or "", ())),
        )
        for claim in _mapping_list(graph.get("claims"))
    ]
    warrant_inspection = [
        _warrant_inspection(
            row,
            issues=tuple(issues_by_node.get(_text(row.get("node_id")) or "", ())),
        )
        for row in _mapping_list(graph.get("warrants"))
    ]
    complete_count = sum(1 for path in claim_paths if path["complete"])
    machine_count = sum(1 for row in warrant_inspection if row["machine_inspectable"])
    status = (
        "pass"
        if graph.get("status") == "pass" and complete_count == len(claim_paths)
        else "blocked"
    )
    return {
        "schema_version": ARGUMENT_GRAPH_INSPECTION_SCHEMA_VERSION,
        "contract_id": ARGUMENT_GRAPH_CONTRACT_ID,
        "status": status,
        "argument_graph_ref": graph.get("argument_graph_ref"),
        "authority_boundary": graph.get("authority_boundary"),
        "summary": {
            "claim_path_count": len(claim_paths),
            "complete_claim_path_count": complete_count,
            "warrant_count": len(warrant_inspection),
            "machine_inspectable_warrant_count": machine_count,
            "issue_count": len(issues),
        },
        "claim_paths": claim_paths,
        "warrant_inspection": warrant_inspection,
        "issues": [dict(issue) for issue in issues],
        "next_diagnostic_command": ARGUMENT_GRAPH_NEXT_DIAGNOSTIC_COMMAND,
    }


def export_argument_graph(
    argument_graph: Mapping[str, Any],
    *,
    profile: ArgumentGraphExportProfile = "all",
) -> dict[str, Any]:
    """Export the argument graph to SACM, CAE, and GSN profile projections."""

    graph = _graph(argument_graph)
    selected_profiles = _export_profiles(profile)
    claims: list[dict[str, Any]] = []
    for claim in _mapping_list(graph.get("claims")):
        claim_id = _text(claim.get("claim_id"))
        claim_node = _text(claim.get("node_id"))
        argument_refs = _edge_targets(graph, claim_node, "claim_supported_by_argument")
        warrant_refs = _edge_targets_for_claim(graph, claim_id, "argument_justified_by_warrant")
        evidence_refs = _edge_targets_for_claim(graph, claim_id, "warrant_grounded_in_evidence")
        authority_refs = _edge_targets_for_claim(graph, claim_id, "evidence_bounded_by_authority")
        readiness_refs = _edge_targets_for_claim(graph, claim_id, "authority_feeds_readiness")
        row: dict[str, Any] = {
            "claim_id": claim_id,
            "claim_ref": claim.get("claim_ref"),
            "profiles": selected_profiles,
        }
        if "SACM" in selected_profiles:
            row["sacm"] = {
                "claim": claim_node,
                "argument_reasoning": argument_refs,
                "asserted_inference": warrant_refs,
                "artifact_reference": evidence_refs,
                "context": [*authority_refs, *readiness_refs],
            }
        if "CAE" in selected_profiles:
            row["cae"] = {
                "claim": claim_node,
                "argument": argument_refs,
                "warrant": warrant_refs,
                "evidence": evidence_refs,
                "authority": authority_refs,
                "readiness": readiness_refs,
            }
        if "GSN" in selected_profiles:
            row["gsn"] = {
                "goal": claim_node,
                "strategy": argument_refs,
                "justification": warrant_refs,
                "solution": evidence_refs,
                "context": authority_refs,
                "undeveloped": readiness_refs
                if graph.get("status") != "pass"
                else [],
            }
        claims.append(row)

    return {
        "schema_version": ARGUMENT_GRAPH_EXPORT_SCHEMA_VERSION,
        "contract_id": ARGUMENT_GRAPH_CONTRACT_ID,
        "argument_graph_ref": graph.get("argument_graph_ref"),
        "standards": selected_profiles,
        "mapping_source": {
            "assurance_case": dict(POLICY_DESIGN_CASE_NODE_MAPPING),
            "claim_argument": dict(CLAIM_ARGUMENT_NODE_MAPPING),
        },
        "authority_boundary": graph.get("authority_boundary"),
        "claims": claims,
        "edges": list(graph.get("edges") or []),
        "issues": list(graph.get("issues") or []),
    }


def build_argument_graph_quality_evidence_surfaces(
    argument_graph: Mapping[str, Any],
) -> dict[str, Any]:
    """Project W8.B graph outputs into runtime quality evidence surfaces."""

    graph = _graph(argument_graph)
    return {
        "argument_graph": dict(graph),
        "argument_graph_inspection": inspect_argument_graph(graph),
        "argument_graph_export": export_argument_graph(graph),
    }


def merge_argument_graph_quality_evidence_surfaces(
    quality_evidence: Mapping[str, Any],
    argument_graph: Mapping[str, Any],
) -> dict[str, Any]:
    """Return `quality_evidence` with W8.B argument graph surfaces added."""

    merged = dict(quality_evidence)
    merged.update(build_argument_graph_quality_evidence_surfaces(argument_graph))
    return merged


def persist_argument_graph(
    argument_graph: Mapping[str, Any],
    *,
    store: object,
    inputs: Iterable[object] | None = None,
) -> object:
    """Persist a W8.B argument graph as a runtime-quality JSON artifact."""

    graph = _graph(argument_graph)
    return persist_runtime_quality_json_artifact(
        payload=graph,
        store=store,
        kind=ARGUMENT_GRAPH_KIND,
        schema_name=ARGUMENT_GRAPH_CONTRACT_ID,
        schema_version="1.0.0",
        inputs=inputs,
    )


def _claim_rows(case: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = _surface_rows(case, _CLAIM_KEYS)
    if rows:
        return [row for row in rows if row.get("major", True) is not False]
    return [
        row
        for row in _mapping_list(case.get("nodes"))
        if _text(row.get("node_type")) == "claim" and row.get("major", True) is not False
    ]


def _runtime_pdc_graph_argument_surface(case: Mapping[str, Any]) -> Mapping[str, Any]:
    """Project W8.A RuntimePolicyDesignCase graph structure into W8.B inputs."""

    if _text(case.get("schema_version")) != "policyos.runtime.pdc.graph.v1":
        return case
    claim_graph = case.get("claim_graph")
    if not isinstance(claim_graph, Mapping):
        return case
    closeout_refs = _mapping_list(case.get("closeout_refs"))
    closeout_status = _runtime_pdc_closeout_status(closeout_refs)
    claim_rows: list[dict[str, Any]] = []
    argument_rows: list[dict[str, Any]] = []
    warrant_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    readiness_rows: list[dict[str, Any]] = []

    for raw_claim in _mapping_list(claim_graph.get("claims")):
        claim_id = _text(raw_claim.get("claim_id"))
        if not claim_id:
            continue
        argument_refs = _text_values(raw_claim.get("argument_refs")) or [
            f"argument:{claim_id}:runtime"
        ]
        warrant_refs = _text_values(raw_claim.get("warrant_refs")) or [
            f"warrant:{claim_id}:runtime"
        ]
        producer_refs = _text_values(raw_claim.get("producer_binding_refs"))
        limitation_refs = _text_values(raw_claim.get("limitation_refs")) or [
            f"limit:{claim_id}:runtime-boundary"
        ]
        readiness_ref = f"readiness:{claim_id}:closeout"
        claim_rows.append(
            {
                "claim_id": claim_id,
                "claim_text": _text(raw_claim.get("text")),
                "claim_ref": f"claim:{claim_id}",
                "major": True,
                "argument_refs": argument_refs,
                "warrant_refs": warrant_refs,
                "evidence_refs": producer_refs,
                "readiness_refs": [readiness_ref],
            }
        )
        for argument_ref in argument_refs:
            argument_rows.append(
                {
                    "argument_id": argument_ref,
                    "claim_id": claim_id,
                    "strategy": "runtime_policy_design_case_graph",
                    "text": "Runtime PDC graph links the claim to warrant and producer evidence.",
                    "evidence_refs": producer_refs,
                    "warrant_refs": warrant_refs,
                }
            )
        for warrant_ref in warrant_refs:
            warrant_rows.append(
                {
                    "warrant_id": warrant_ref,
                    "claim_id": claim_id,
                    "warrant_text": (
                        "Producer-bound evidence, graph limitations, and closeout "
                        "readiness jointly bound this claim."
                    ),
                    "argument_refs": argument_refs,
                    "evidence_refs": producer_refs,
                    "assumptions": [
                        {
                            "assumption_id": f"assumption:{claim_id}:producer-binding",
                            "statement": (
                                "Producer binding refs remain valid for the graph's "
                                "declared policy design case scope."
                            ),
                            "source_refs": producer_refs,
                        }
                    ],
                    "applicability_predicates": [
                        {
                            "predicate_id": f"applicability:{claim_id}:runtime-graph",
                            "expression": (
                                "claim_id is present in RuntimePolicyDesignCase.claim_graph "
                                "and producer refs are graph-bound"
                            ),
                            "source_refs": [f"claim:{claim_id}"],
                        }
                    ],
                    "confidence_refs": producer_refs,
                    "reliability_refs": _text_values(
                        raw_claim.get("effective_independence_refs")
                    )
                    or producer_refs,
                    "limits": [
                        {
                            "limit_id": ref,
                            "statement": (
                                "Runtime graph warrants are structural and do not mint "
                                "claim authority."
                            ),
                            "severity": "authority_boundary",
                            "source_refs": [ref],
                        }
                        for ref in limitation_refs
                    ],
                }
            )
        for producer_ref in producer_refs:
            evidence_rows.append(
                {
                    "evidence_id": producer_ref,
                    "evidence_ref": producer_ref,
                    "claim_id": claim_id,
                    "producer_component": "runtime_pdc_graph",
                    "runtime_event_ref": _text(case.get("runtime_event_ref")),
                    "runtime_authority_envelope": {
                        "authority_role": "producer_authority",
                        "provenance_kind": "runtime_emitted",
                        "authoritative_for": ["producer_binding_ref"],
                        "may_not_use_for": ["claim_authority", "projection_authority"],
                        "cas_ref": producer_ref,
                    },
                }
            )
        readiness_rows.append(
            {
                "readiness_id": readiness_ref,
                "claim_id": claim_id,
                "status": closeout_status,
                "readiness_check": "runtime_pdc_graph_closeout_ref",
                "authority_refs": [ref.get("closeout_ref") for ref in closeout_refs],
                "blocker_refs": _text_values(raw_claim.get("blocker_refs")),
            }
        )
    return {
        **dict(case),
        "case_id": _text(case.get("graph_id")),
        "final_major_claims": claim_rows,
        "arguments": argument_rows,
        "warrants": warrant_rows,
        "evidence_records": evidence_rows,
        "readiness_records": readiness_rows,
    }


def _runtime_pdc_closeout_status(closeout_refs: Sequence[Mapping[str, Any]]) -> str:
    if not closeout_refs:
        return "pass"
    return "pass" if all(bool(row.get("can_closeout")) for row in closeout_refs) else "blocked"


def _argument_node(row: Mapping[str, Any], *, claim_id: str) -> dict[str, Any]:
    return _drop_none(
        {
            "node_id": _identity(row, "argument"),
            "node_type": "argument",
            "claim_id": claim_id,
            "strategy": _first_text(
                row.get("strategy"),
                row.get("argument_strategy"),
                row.get("argument_type"),
            ),
            "text": _first_text(row.get("argument_text"), row.get("text"), row.get("rationale")),
            "evidence_refs": _text_values(row.get("evidence_refs") or row.get("evidence_ref")),
            "warrant_refs": _text_values(row.get("warrant_refs") or row.get("warrant_ref")),
        }
    )


def _warrant_node(
    row: Mapping[str, Any],
    *,
    claim_id: str,
) -> tuple[dict[str, Any], list[ArgumentGraphIssue]]:
    node_id = _identity(row, "warrant")
    semantics = _warrant_semantics(row)
    issues = _warrant_semantic_issues(
        semantics,
        warrant=row,
        claim_id=claim_id,
        node_id=node_id,
    )
    return (
        _drop_none(
            {
                "node_id": node_id,
                "node_type": "warrant",
                "claim_id": claim_id,
                "text": _first_text(
                    row.get("warrant_text"),
                    row.get("rationale"),
                    row.get("text"),
                ),
                "argument_refs": _text_values(
                    row.get("argument_refs") or row.get("argument_ref")
                ),
                "evidence_refs": _text_values(
                    row.get("evidence_refs") or row.get("evidence_ref")
                ),
                "requires_berl_reliability": warrant_requires_berl_reliability(row),
                "semantics": semantics.as_dict(),
                "machine_inspectable": not issues,
            }
        ),
        issues,
    )


def _evidence_node(row: Mapping[str, Any], *, claim_id: str) -> dict[str, Any]:
    node_id = _identity(row, "evidence")
    return _drop_none(
        {
            "node_id": node_id,
            "node_type": "evidence",
            "claim_id": claim_id,
            "evidence_ref": _first_text(
                row.get("evidence_ref"),
                row.get("cas_ref"),
                row.get("artifact_ref"),
                node_id,
            ),
            "producer_component": _first_text(
                row.get("producer_component"),
                row.get("producer"),
                row.get("source_component"),
            ),
            "runtime_event_ref": _text(row.get("runtime_event_ref")),
        }
    )


def _authority_node_for_evidence(
    evidence: Mapping[str, Any],
    *,
    authority_rows: Iterable[Mapping[str, Any]],
    claim_id: str,
) -> tuple[dict[str, Any] | None, list[ArgumentGraphIssue]]:
    evidence_id = _identity(evidence, "evidence")
    authority = _authority_mapping(evidence)
    if authority is None:
        authority = _matched_authority(evidence, authority_rows, claim_id=claim_id)
    if authority is None:
        return (
            None,
            [
                _issue(
                    "argument_graph_evidence_authority_missing",
                    "Evidence nodes must carry runtime-emitted authority metadata.",
                    claim_id=claim_id,
                    node_id=evidence_id,
                    node_type="evidence",
                    field="runtime_authority_envelope",
                )
            ],
        )

    authority_id = _first_text(
        authority.get("authority_id"),
        authority.get("node_id"),
        authority.get("record_id"),
        authority.get("id"),
        f"authority-{evidence_id}",
    )
    role = _text(authority.get("authority_role"))
    provenance = _text(authority.get("provenance_kind"))
    issues: list[ArgumentGraphIssue] = []
    if role not in _VALID_AUTHORITY_ROLES or provenance not in _VALID_AUTHORITY_PROVENANCE:
        issues.append(
            _issue(
                "argument_graph_evidence_authority_boundary_invalid",
                (
                    "Argument graph evidence authority must be runtime-emitted "
                    "producer authority or runtime blocker authority."
                ),
                claim_id=claim_id,
                node_id=authority_id,
                node_type="authority",
                field="authority_role",
            )
        )
    return (
        _drop_none(
            {
                "node_id": authority_id,
                "node_type": "authority",
                "claim_id": claim_id,
                "evidence_node_id": evidence_id,
                "authority_role": role,
                "provenance_kind": provenance,
                "cas_ref": _first_text(
                    authority.get("cas_ref"),
                    authority.get("artifact_ref"),
                    evidence.get("evidence_ref"),
                    evidence.get("cas_ref"),
                ),
                "runtime_event_ref": _first_text(
                    authority.get("runtime_event_ref"),
                    evidence.get("runtime_event_ref"),
                ),
                "authoritative_for": _text_values(authority.get("authoritative_for")),
                "may_not_use_for": _text_values(authority.get("may_not_use_for")),
            }
        ),
        issues,
    )


def _readiness_node(row: Mapping[str, Any], *, claim_id: str) -> dict[str, Any]:
    return _drop_none(
        {
            "node_id": _identity(row, "readiness"),
            "node_type": "readiness",
            "claim_id": claim_id,
            "status": _text(row.get("status") or row.get("readiness_status")) or "unknown",
            "readiness_check": _text(row.get("readiness_check")),
            "authority_refs": _text_values(row.get("authority_refs") or row.get("authority_ref")),
            "blocker_refs": _text_values(row.get("blocker_refs") or row.get("blocker_ref")),
        }
    )


def _warrant_semantics(warrant: Mapping[str, Any]) -> WarrantSemantics:
    assumptions = tuple(
        _assumption(item, index=index)
        for index, item in enumerate(_raw_list(warrant.get("assumptions")), start=1)
    )
    predicates = tuple(
        _applicability_predicate(item, index=index)
        for index, item in enumerate(
            _raw_list(
                warrant.get("applicability_predicates")
                or warrant.get("applicability")
                or warrant.get("applicability_conditions")
            ),
            start=1,
        )
    )
    limits = tuple(
        _warrant_limit(item, index=index)
        for index, item in enumerate(
            _raw_list(
                warrant.get("limits")
                or warrant.get("applicability_limits")
                or warrant.get("confidence_limits")
            ),
            start=1,
        )
    )
    return WarrantSemantics(
        assumptions=assumptions,
        applicability_predicates=predicates,
        confidence_refs=_text_values(
            warrant.get("confidence_refs")
            or warrant.get("confidence_ref")
            or warrant.get("confidence_bound_refs")
            or warrant.get("confidence_limit_refs")
        ),
        reliability_refs=_text_values(
            warrant.get("reliability_refs")
            or warrant.get("reliability_ref")
            or warrant.get("warrant_reliability_refs")
        ),
        berl_refs=warrant_berl_reliability_refs(warrant),
        limits=limits,
    )


def _warrant_semantic_issues(
    semantics: WarrantSemantics,
    *,
    warrant: Mapping[str, Any],
    claim_id: str,
    node_id: str,
) -> list[ArgumentGraphIssue]:
    issues: list[ArgumentGraphIssue] = []
    if not semantics.assumptions:
        issues.append(
            _issue(
                "argument_graph_warrant_assumptions_missing",
                "Warrants must expose typed assumptions.",
                claim_id=claim_id,
                node_id=node_id,
                node_type="warrant",
                field="warrants.assumptions",
            )
        )
    if not semantics.applicability_predicates:
        issues.append(
            _issue(
                "argument_graph_warrant_applicability_predicates_missing",
                "Warrants must expose machine-readable applicability predicates.",
                claim_id=claim_id,
                node_id=node_id,
                node_type="warrant",
                field="warrants.applicability_predicates",
            )
        )
    if not (
        semantics.confidence_refs
        or semantics.reliability_refs
        or semantics.berl_refs
    ):
        issues.append(
            _issue(
                "argument_graph_warrant_confidence_or_reliability_refs_missing",
                "Warrants must cite confidence, reliability, or BERL refs.",
                claim_id=claim_id,
                node_id=node_id,
                node_type="warrant",
                field="warrants.confidence_refs",
            )
        )
    if warrant_requires_berl_reliability(warrant) and not semantics.berl_refs:
        issues.append(
            _issue(
                "argument_graph_warrant_berl_refs_missing",
                "Warrants requiring explanation reliability must cite BERL refs.",
                claim_id=claim_id,
                node_id=node_id,
                node_type="warrant",
                field="warrants.berl_reliability_refs",
            )
        )
    if not semantics.limits:
        issues.append(
            _issue(
                "argument_graph_warrant_limits_missing",
                "Warrants must expose applicability or confidence limits.",
                claim_id=claim_id,
                node_id=node_id,
                node_type="warrant",
                field="warrants.limits",
            )
        )
    return issues


def _assumption(item: object, *, index: int) -> WarrantAssumption:
    if isinstance(item, Mapping):
        return WarrantAssumption(
            assumption_id=_first_text(
                item.get("assumption_id"),
                item.get("id"),
                item.get("record_id"),
            ),
            statement=_required_text(
                _first_text(item.get("statement"), item.get("text"), item.get("description")),
                f"assumption.{index}",
            ),
            source_refs=_text_values(item.get("source_refs") or item.get("evidence_refs")),
        )
    return WarrantAssumption(statement=_required_text(_text(item), f"assumption.{index}"))


def _applicability_predicate(item: object, *, index: int) -> ApplicabilityPredicate:
    if isinstance(item, Mapping):
        return ApplicabilityPredicate(
            predicate_id=_first_text(
                item.get("predicate_id"),
                item.get("id"),
                item.get("record_id"),
            ),
            expression=_required_text(
                _first_text(
                    item.get("expression"),
                    item.get("predicate"),
                    item.get("condition"),
                    item.get("statement"),
                ),
                f"applicability.{index}",
            ),
            source_refs=_text_values(item.get("source_refs") or item.get("evidence_refs")),
        )
    return ApplicabilityPredicate(
        expression=_required_text(_text(item), f"applicability.{index}")
    )


def _warrant_limit(item: object, *, index: int) -> WarrantLimit:
    if isinstance(item, Mapping):
        return WarrantLimit(
            limit_id=_first_text(item.get("limit_id"), item.get("id"), item.get("record_id")),
            statement=_required_text(
                _first_text(item.get("statement"), item.get("text"), item.get("description")),
                f"limit.{index}",
            ),
            severity=_text(item.get("severity")),
            source_refs=_text_values(item.get("source_refs") or item.get("evidence_refs")),
        )
    return WarrantLimit(statement=_required_text(_text(item), f"limit.{index}"))


def _surface_rows(case: Mapping[str, Any], keys: Iterable[str]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in keys:
        rows.extend(_mapping_list(case.get(key)))
    return rows


def _matched_rows(
    source: Mapping[str, Any],
    rows: Iterable[Mapping[str, Any]],
    *,
    surface: str,
    ref_keys: Iterable[str],
    claim_id: str,
) -> list[Mapping[str, Any]]:
    explicit_refs = set()
    for key in ref_keys:
        explicit_refs.update(_text_values(source.get(key)))
    matched: list[Mapping[str, Any]] = []
    for row in rows:
        row_ids = _row_id_values(row, surface)
        if explicit_refs and not explicit_refs.isdisjoint(row_ids):
            matched.append(row)
            continue
        if _row_matches_claim(row, claim_id=claim_id):
            matched.append(row)
    return matched


def _matched_authority(
    evidence: Mapping[str, Any],
    authority_rows: Iterable[Mapping[str, Any]],
    *,
    claim_id: str,
) -> Mapping[str, Any] | None:
    evidence_ids = _row_id_values(evidence, "evidence")
    for row in authority_rows:
        row_refs = set(
            _text_values(row.get("evidence_refs"))
            + _text_values(row.get("evidence_ref"))
            + _text_values(row.get("source_refs"))
            + _text_values(row.get("source_ref"))
        )
        if row_refs and not row_refs.isdisjoint(evidence_ids):
            return row
        if _row_matches_claim(row, claim_id=claim_id):
            return row
    return None


def _authority_mapping(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    for key in ("runtime_authority_envelope", "authority_envelope", "authority"):
        value = row.get(key)
        if isinstance(value, Mapping):
            return value
    if _text(row.get("authority_role")) or _text(row.get("provenance_kind")):
        return row
    return None


def _row_matches_claim(row: Mapping[str, Any], *, claim_id: str) -> bool:
    return claim_id in set(
        _text_values(row.get("claim_id"))
        + _text_values(row.get("claim_ids"))
        + _text_values(row.get("claim_ref"))
        + _text_values(row.get("major_claim_id"))
    )


def _row_id_values(row: Mapping[str, Any], surface: str) -> set[str]:
    values = set()
    for key in _SURFACE_ID_KEYS.get(surface, _NODE_ID_KEYS):
        values.update(_text_values(row.get(key)))
    return values


def _identity(row: Mapping[str, Any], surface: str) -> str:
    for key in _SURFACE_ID_KEYS.get(surface, _NODE_ID_KEYS):
        value = _text(row.get(key))
        if value is not None:
            return value
    return _stable_ref(surface, row)


def _edge(
    edge_kind: str,
    source_node_id: str,
    target_node_id: str,
    *,
    claim_id: str,
) -> dict[str, str]:
    return {
        "edge_kind": edge_kind,
        "source_node_id": source_node_id,
        "target_node_id": target_node_id,
        "claim_id": claim_id,
    }


def _dedupe_edges(edges: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for edge in edges:
        key = (
            _text(edge.get("edge_kind")) or "",
            _text(edge.get("source_node_id")) or "",
            _text(edge.get("target_node_id")) or "",
            _text(edge.get("claim_id")) or "",
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(edge))
    return deduped


def _claim_path(
    claim: Mapping[str, Any],
    graph: Mapping[str, Any],
    *,
    issues: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    claim_id = _text(claim.get("claim_id"))
    claim_node = _text(claim.get("node_id"))
    edge_counts = {
        kind: len(_edge_targets_for_claim(graph, claim_id, kind))
        for kind in (
            "claim_supported_by_argument",
            "argument_justified_by_warrant",
            "warrant_grounded_in_evidence",
            "evidence_bounded_by_authority",
            "authority_feeds_readiness",
        )
    }
    complete = all(count > 0 for count in edge_counts.values()) and not issues
    return {
        "claim_id": claim_id,
        "claim_node_id": claim_node,
        "complete": complete,
        "edge_counts": edge_counts,
        "issue_codes": [issue["code"] for issue in issues],
    }


def _warrant_inspection(
    warrant: Mapping[str, Any],
    *,
    issues: tuple[Mapping[str, Any], ...],
) -> dict[str, Any]:
    semantics = warrant.get("semantics") if isinstance(warrant.get("semantics"), Mapping) else {}
    assumption_count = len(_mapping_list(semantics.get("assumptions")))
    predicate_count = len(_mapping_list(semantics.get("applicability_predicates")))
    confidence_refs = _text_values(semantics.get("confidence_refs"))
    reliability_refs = _text_values(semantics.get("reliability_refs"))
    berl_refs = _text_values(semantics.get("berl_refs"))
    limit_count = len(_mapping_list(semantics.get("limits")))
    machine_inspectable = (
        assumption_count > 0
        and predicate_count > 0
        and bool(confidence_refs or reliability_refs or berl_refs)
        and limit_count > 0
        and not issues
    )
    return {
        "warrant_id": _text(warrant.get("node_id")),
        "claim_id": _text(warrant.get("claim_id")),
        "machine_inspectable": machine_inspectable,
        "assumption_count": assumption_count,
        "applicability_predicate_count": predicate_count,
        "confidence_refs": confidence_refs,
        "reliability_refs": reliability_refs,
        "berl_refs": berl_refs,
        "limit_count": limit_count,
        "issue_codes": [issue["code"] for issue in issues],
    }


def _edge_targets(
    graph: Mapping[str, Any],
    source_node_id: str | None,
    edge_kind: str,
) -> list[str]:
    if source_node_id is None:
        return []
    return [
        str(edge["target_node_id"])
        for edge in _mapping_list(graph.get("edges"))
        if _text(edge.get("edge_kind")) == edge_kind
        and _text(edge.get("source_node_id")) == source_node_id
        and _text(edge.get("target_node_id")) is not None
    ]


def _edge_targets_for_claim(
    graph: Mapping[str, Any],
    claim_id: str | None,
    edge_kind: str,
) -> list[str]:
    return [
        str(edge["target_node_id"])
        for edge in _mapping_list(graph.get("edges"))
        if _text(edge.get("edge_kind")) == edge_kind
        and _text(edge.get("claim_id")) == claim_id
        and _text(edge.get("target_node_id")) is not None
    ]


def _export_profiles(profile: ArgumentGraphExportProfile) -> list[str]:
    if profile == "all":
        return ["SACM", "CAE", "GSN"]
    if profile == "sacm":
        return ["SACM"]
    if profile == "cae":
        return ["CAE"]
    if profile == "gsn":
        return ["GSN"]
    raise ArgumentGraphError(
        "argument_graph_export_profile_invalid",
        "Export profile must be all, sacm, cae, or gsn.",
    )


def _authority_boundary() -> dict[str, Any]:
    return {
        "authority_role": "diagnostic_only",
        "provenance_kind": "runtime_projection",
        "authoritative_for": [
            "argument_graph_structure",
            "warrant_inspection",
        ],
        "may_not_use_for": [
            "claim_authority",
            "evidence_authority",
            "projection_authority",
            "readiness_authority",
            "runtime_closeout_authority",
        ],
        "policy": (
            "Argument graph surfaces explain runtime-owned argument structure; "
            "they cannot upgrade claim, evidence, readiness, or projection authority."
        ),
    }


def _issue(
    code: str,
    message: str,
    *,
    claim_id: str | None = None,
    node_id: str | None = None,
    node_type: str | None = None,
    field: str | None = None,
) -> ArgumentGraphIssue:
    return ArgumentGraphIssue(
        code=code,
        message=message,
        claim_id=claim_id,
        node_id=node_id,
        node_type=node_type,
        field=field,
    )


def _graph(argument_graph: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(argument_graph, Mapping):
        raise ArgumentGraphError(
            "argument_graph_invalid",
            "Argument graph must be a mapping.",
        )
    if _text(argument_graph.get("schema_version")) != ARGUMENT_GRAPH_SCHEMA_VERSION:
        raise ArgumentGraphError(
            "argument_graph_schema_version_invalid",
            "Argument graph uses an unsupported schema version.",
        )
    return dict(argument_graph)


def _issue_rows(graph: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(_mapping_list(graph.get("issues")))


def _mapping_list(value: object) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, list | tuple):
        return [item for item in value if isinstance(item, Mapping)]
    return []


def _raw_list(value: object) -> list[object]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


def _text_tuple(value: object) -> tuple[str, ...]:
    return tuple(_text_values(value))


def _text_values(value: object) -> list[str]:
    values: list[str] = []
    if value is None:
        return values
    if isinstance(value, str):
        text = _text(value)
        return [text] if text is not None else []
    if isinstance(value, Mapping):
        for key in ("ref", "id", "value", "evidence_ref", "cas_ref", "artifact_ref"):
            text = _text(value.get(key))
            if text is not None:
                values.append(text)
        return list(dict.fromkeys(values))
    if isinstance(value, Iterable):
        for item in value:
            values.extend(_text_values(item))
        return list(dict.fromkeys(values))
    text = _text(value)
    return [text] if text is not None else []


def _first_text(*values: object) -> str | None:
    for value in values:
        text = _text(value)
        if text is not None:
            return text
    return None


def _required_text(value: object, fallback: str) -> str:
    text = _text(value)
    if text is None:
        return fallback
    return text


def _optional_text(value: str | None) -> str | None:
    return _text(value)


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _drop_none(value: Mapping[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if item is not None}


def _stable_ref(prefix: str, payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return f"{prefix}:sha256:{hashlib.sha256(encoded).hexdigest()}"


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(tz=UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


__all__ = [
    "ARGUMENT_GRAPH_CONTRACT_ID",
    "ARGUMENT_GRAPH_EXPORT_SCHEMA_VERSION",
    "ARGUMENT_GRAPH_INSPECTION_SCHEMA_VERSION",
    "ARGUMENT_GRAPH_KIND",
    "ARGUMENT_GRAPH_SCHEMA_VERSION",
    "ArgumentGraphError",
    "build_argument_graph",
    "build_argument_graph_quality_evidence_surfaces",
    "export_argument_graph",
    "inspect_argument_graph",
    "merge_argument_graph_quality_evidence_surfaces",
    "persist_argument_graph",
]
