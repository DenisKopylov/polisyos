"""Runtime-owned Policy Design Case graph compiler.

The compiler assembles graph structure from existing runtime surfaces. It does
not mint claim, projection, evidence, or closeout authority; those remain owned
by their producer and reader modules.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.core import artifacts, canon

RUNTIME_POLICY_DESIGN_CASE_SCHEMA_VERSION = "policyos.runtime.pdc.graph.v1"
RUNTIME_POLICY_DESIGN_CASE_COMPILER = "polisyos.pdc.compiler"
RUNTIME_POLICY_DESIGN_CASE_COMPILER_VERSION = "2026.05.24+w8a"
RUNTIME_POLICY_DESIGN_CASE_PROJECTION_POLICY = (
    "reads_runtime_policy_design_case_graph"
)
RUNTIME_POLICY_DESIGN_CASE_ARTIFACT_KIND = "runtime.policy_design_case_graph"

_GRAPH_AUTHORITY = ("pdc_graph_structure",)
_GRAPH_MAY_NOT_USE_FOR = (
    "projection_authority",
    "claim_authority",
)
_LLM_SOURCE_CLASSES = frozenset({"llm_candidate", "llm_critic", "llm_drafter"})
_CONTEXT_ONLY_USES = frozenset({"", "context_only", "context-only"})
_PRODUCER_BINDING_KEYS = (
    "selected_binding_refs",
    "data_refs",
    "selected_norm_refs",
    "legal_authority_record_refs",
    "method_output_refs",
    "ir_analytics_refs",
    "ir_certificate_refs",
    "proof_composability_refs",
)
_CONFLICT_KEYS = (
    "conflict_refs",
    "counter_evidence_refs",
    "counterevidence_refs",
    "legal_authority_blocker_refs",
)
_INDEPENDENCE_KEYS = ("effective_independence_refs", "independence_refs")


class RuntimePolicyDesignCaseCompilerError(ValueError):
    """Fail-closed RuntimePolicyDesignCase compiler violation."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class RuntimePdcAuthorityEnvelope(BaseModel):
    """Authority boundary for the graph as graph structure only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    authority_role: Literal["runtime_pdc_graph"] = "runtime_pdc_graph"
    provenance_kind: Literal["runtime_emitted"] = "runtime_emitted"
    producer_component: Literal["polisyos.pdc.compiler"] = RUNTIME_POLICY_DESIGN_CASE_COMPILER
    authoritative_for: tuple[str, ...] = _GRAPH_AUTHORITY
    may_not_use_for: tuple[str, ...] = _GRAPH_MAY_NOT_USE_FOR
    may_not_be_used_for: tuple[str, ...] = _GRAPH_MAY_NOT_USE_FOR
    runtime_event_ref: str = Field(min_length=1)
    graph_ref: str | None = None

    @field_validator("authoritative_for", "may_not_use_for", "may_not_be_used_for", mode="before")
    @classmethod
    def _coerce_tuple(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _enforce_graph_boundary(self) -> RuntimePdcAuthorityEnvelope:
        if self.authoritative_for != _GRAPH_AUTHORITY:
            raise ValueError("Runtime PDC graph may only be authoritative for graph structure")
        forbidden = set(self.may_not_use_for)
        if not set(_GRAPH_MAY_NOT_USE_FOR) <= forbidden:
            raise ValueError("Runtime PDC graph must forbid projection and claim authority")
        if not set(_GRAPH_MAY_NOT_USE_FOR) <= set(self.may_not_be_used_for):
            raise ValueError("Runtime PDC graph must expose may_not_be_used_for limits")
        return self


class RuntimePdcClaimNode(BaseModel):
    """One claim node plus graph-local refs gathered from existing producers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1)
    claim_type: str | None = None
    claim_family: str | None = None
    claim_use: str | None = None
    text: str | None = None
    support_status: str | None = None
    publishability: str | None = None
    readiness_level: str | None = None
    source_class: str = "deterministic_producer"
    facet_refs: tuple[str, ...] = Field(default=())
    obligation_refs: tuple[str, ...] = Field(default=())
    producer_binding_refs: tuple[str, ...] = Field(default=())
    baseline_refs: tuple[str, ...] = Field(default=())
    alternative_refs: tuple[str, ...] = Field(default=())
    warrant_refs: tuple[str, ...] = Field(default=())
    argument_refs: tuple[str, ...] = Field(default=())
    rebuttal_refs: tuple[str, ...] = Field(default=())
    conflict_refs: tuple[str, ...] = Field(default=())
    effective_independence_refs: tuple[str, ...] = Field(default=())
    accepted_deficit_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    blocker_refs: tuple[str, ...] = Field(default=())
    runtime_claim_registry_entry_ref: str | None = None

    @field_validator(
        "facet_refs",
        "obligation_refs",
        "producer_binding_refs",
        "baseline_refs",
        "alternative_refs",
        "warrant_refs",
        "argument_refs",
        "rebuttal_refs",
        "conflict_refs",
        "effective_independence_refs",
        "accepted_deficit_refs",
        "limitation_refs",
        "blocker_refs",
        mode="before",
    )
    @classmethod
    def _strip_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _prevent_llm_authority_laundering(self) -> RuntimePdcClaimNode:
        if self.source_class.casefold() in _LLM_SOURCE_CLASSES and (
            (self.claim_use or "").casefold() not in _CONTEXT_ONLY_USES
        ):
            raise ValueError(
                "runtime_pdc_graph_llm_authority_laundering: "
                "LLM-sourced claims must remain context-only in the runtime graph"
            )
        return self


class RuntimePdcClaimEdge(BaseModel):
    """Typed edge between graph refs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    edge_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    target_ref: str = Field(min_length=1)
    edge_type: Literal[
        "obligation_supports_claim",
        "producer_binding_supports_claim",
        "baseline_contextualizes_claim",
        "alternative_contextualizes_claim",
        "warrant_supports_claim",
        "conflict_contests_claim",
        "independence_qualifies_claim",
    ]


class RuntimePdcClaimGraph(BaseModel):
    """Graph-local claim nodes and their typed structural edges."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    claims: tuple[RuntimePdcClaimNode, ...] = Field(default=())
    edges: tuple[RuntimePdcClaimEdge, ...] = Field(default=())

    @model_validator(mode="after")
    def _validate_unique_claims(self) -> RuntimePdcClaimGraph:
        ids = [claim.claim_id for claim in self.claims]
        if len(ids) != len(set(ids)):
            raise ValueError("RuntimePolicyDesignCase claim ids must be unique")
        return self


class RuntimePdcWarrantStructure(BaseModel):
    """Per-claim warrant ref structure consumed by W8.B argument graph builders."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    structure_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    argument_refs: tuple[str, ...] = Field(default=())
    warrant_refs: tuple[str, ...] = Field(default=())
    rebuttal_refs: tuple[str, ...] = Field(default=())
    evidence_refs: tuple[str, ...] = Field(default=())
    authority_refs: tuple[str, ...] = Field(default=())
    limitation_refs: tuple[str, ...] = Field(default=())
    accepted_deficit_refs: tuple[str, ...] = Field(default=())
    status: Literal["present", "pending_argument_graph"] = "present"

    @field_validator(
        "argument_refs",
        "warrant_refs",
        "rebuttal_refs",
        "evidence_refs",
        "authority_refs",
        "limitation_refs",
        "accepted_deficit_refs",
        mode="before",
    )
    @classmethod
    def _strip_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)


class RuntimePdcCloseoutRef(BaseModel):
    """Graph-local pointer to closeout substrate evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    closeout_ref: str = Field(min_length=1)
    status: str = Field(min_length=1)
    verdict: str = Field(min_length=1)
    can_closeout: bool


class RuntimePolicyDesignCase(BaseModel):
    """Typed runtime-owned Policy Design Case graph.

    The object is the source of truth for graph structure only. Projection,
    claim authority, producer evidence, and closeout authority remain separate
    consumers/producers with their own authority envelopes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.runtime.pdc.graph.v1"] = (
        RUNTIME_POLICY_DESIGN_CASE_SCHEMA_VERSION
    )
    graph_id: str = Field(min_length=1)
    graph_ref: str = Field(min_length=1)
    runtime_event_ref: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    job_id: str | None = None
    tenant_id: str | None = None
    generated_at: datetime
    producer_component: Literal["polisyos.pdc.compiler"] = RUNTIME_POLICY_DESIGN_CASE_COMPILER
    compiler_version: str = RUNTIME_POLICY_DESIGN_CASE_COMPILER_VERSION
    authority_envelope: RuntimePdcAuthorityEnvelope
    policy_design_case_profile: dict[str, Any] | None = None
    claim_graph: RuntimePdcClaimGraph
    warrant_structures: tuple[RuntimePdcWarrantStructure, ...] = Field(default=())
    obligation_refs: tuple[str, ...] = Field(default=())
    producer_binding_refs: tuple[str, ...] = Field(default=())
    baseline_refs: tuple[str, ...] = Field(default=())
    alternative_refs: tuple[str, ...] = Field(default=())
    conflict_refs: tuple[str, ...] = Field(default=())
    effective_independence_refs: tuple[str, ...] = Field(default=())
    closeout_refs: tuple[RuntimePdcCloseoutRef, ...] = Field(default=())
    closeout_verdict: dict[str, Any] | None = None
    contested_record_refs: tuple[str, ...] = Field(default=())
    contested_records: tuple[dict[str, Any], ...] = Field(default=())
    deficit_register_refs: tuple[str, ...] = Field(default=())
    deficit_register: tuple[dict[str, Any], ...] = Field(default=())
    claim_registry_ref: str | None = None
    semantic_binding_refs: tuple[str, ...] = Field(default=())
    producer_pipeline_ref: str | None = None
    claim_decomposition_refs: tuple[str, ...] = Field(default=())
    projection_source_policy: Literal["reads_runtime_policy_design_case_graph"] = (
        RUNTIME_POLICY_DESIGN_CASE_PROJECTION_POLICY
    )
    capability_reality_label: Literal["implemented"] = "implemented"

    @field_validator(
        "obligation_refs",
        "producer_binding_refs",
        "baseline_refs",
        "alternative_refs",
        "conflict_refs",
        "effective_independence_refs",
        "contested_record_refs",
        "deficit_register_refs",
        "semantic_binding_refs",
        "claim_decomposition_refs",
        mode="before",
    )
    @classmethod
    def _strip_refs(cls, value: object) -> tuple[str, ...]:
        return _text_tuple(value)

    @model_validator(mode="after")
    def _validate_authority_ref(self) -> RuntimePolicyDesignCase:
        if self.authority_envelope.graph_ref not in {None, self.graph_ref}:
            raise ValueError("RuntimePolicyDesignCase authority graph_ref must match graph_ref")
        return self


def compile_runtime_policy_design_case(
    *,
    run_id: str,
    claims: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    job_id: str | None = None,
    tenant_id: str | None = None,
    policy_design_case: Mapping[str, Any] | None = None,
    claim_registry: Mapping[str, Any] | None = None,
    semantic_binding: Mapping[str, Any] | None = None,
    closeout_verdict: Mapping[str, Any] | None = None,
    producer_pipeline_report: Mapping[str, Any] | None = None,
    obligation_graph: Mapping[str, Any] | None = None,
    claim_decomposition: Mapping[str, Any] | None = None,
    contested_records: Sequence[Mapping[str, Any]] = (),
    deficit_register: Sequence[Mapping[str, Any]] = (),
    generated_at: datetime | None = None,
) -> RuntimePolicyDesignCase:
    """Compile a runtime-owned graph from existing PDC runtime surfaces.

    Args:
        run_id: Runtime run id for the graph.
        claims: Claim rows or a claim-ledger-like mapping.
        job_id: Optional control-plane job id.
        tenant_id: Optional tenant id.
        policy_design_case: Existing assurance-case profile used by projection.
        claim_registry: Runtime claim registry or W7 provisional registry.
        semantic_binding: Semantic binding ledger or semantic closure bridge.
        closeout_verdict: Closeout reader verdict.
        producer_pipeline_report: Optional W7.F report for producer binding refs.
        obligation_graph: Optional W6.C obligation graph payload.
        claim_decomposition: Optional W6.D claim decomposition payload.
        contested_records: Optional W4/W5 contested records.
        deficit_register: Optional deficit register rows.
        generated_at: Deterministic timestamp for tests and replay.

    Returns:
        A strict `RuntimePolicyDesignCase` graph object.
    """

    generated = _utc(generated_at)
    run_id_text = _required_text(run_id, "runtime_pdc_graph_run_id_missing")
    claim_rows = _claim_rows(claims)
    registry = _mapping(claim_registry)
    registry_rows = claim_registry_rows_by_id(registry)
    semantic = _mapping(semantic_binding)
    closeout = _mapping(closeout_verdict)
    pipeline = _mapping(producer_pipeline_report)
    pipeline_binding_refs = _producer_binding_refs_from_pipeline(pipeline)
    graph_claims = [
        _claim_node(
            claim,
            index=index,
            registry_entry=registry_rows.get(_claim_id(claim, index)),
            pipeline_binding_refs=pipeline_binding_refs,
        )
        for index, claim in enumerate(claim_rows)
    ]
    try:
        claim_graph = RuntimePdcClaimGraph(
            claims=tuple(graph_claims),
            edges=tuple(_claim_edges(graph_claims)),
        )
    except ValueError as exc:
        _raise_compiler_error(exc)
    warrant_structures = tuple(
        _warrant_structure(claim)
        for claim in graph_claims
        if claim.argument_refs
        or claim.warrant_refs
        or claim.rebuttal_refs
        or claim.limitation_refs
        or claim.accepted_deficit_refs
    )
    closeout_refs = tuple(_closeout_refs(closeout, run_id=run_id_text))
    contested_rows = tuple(dict(row) for row in contested_records if isinstance(row, Mapping))
    deficit_rows = tuple(dict(row) for row in deficit_register if isinstance(row, Mapping))
    policy_design_case_payload = _policy_design_case_payload(policy_design_case)
    base_payload: dict[str, Any] = {
        "schema_version": RUNTIME_POLICY_DESIGN_CASE_SCHEMA_VERSION,
        "graph_id": f"runtime-pdc-graph:{run_id_text}",
        "graph_ref": "pending",
        "runtime_event_ref": f"event://runtime-pdc-graph/{run_id_text}",
        "run_id": run_id_text,
        "job_id": _optional_text(job_id),
        "tenant_id": _optional_text(tenant_id),
        "generated_at": generated,
        "producer_component": RUNTIME_POLICY_DESIGN_CASE_COMPILER,
        "compiler_version": RUNTIME_POLICY_DESIGN_CASE_COMPILER_VERSION,
        "authority_envelope": {
            "runtime_event_ref": f"event://runtime-pdc-graph/{run_id_text}",
        },
        "policy_design_case_profile": policy_design_case_payload,
        "claim_graph": claim_graph.model_dump(mode="python"),
        "warrant_structures": [row.model_dump(mode="python") for row in warrant_structures],
        "obligation_refs": _all_refs(
            *(claim.obligation_refs for claim in graph_claims),
            _refs_for(obligation_graph, "graph_ref", "graph_id"),
        ),
        "producer_binding_refs": _all_refs(
            *(claim.producer_binding_refs for claim in graph_claims),
            pipeline_binding_refs,
        ),
        "baseline_refs": _all_refs(*(claim.baseline_refs for claim in graph_claims)),
        "alternative_refs": _all_refs(*(claim.alternative_refs for claim in graph_claims)),
        "conflict_refs": _all_refs(*(claim.conflict_refs for claim in graph_claims)),
        "effective_independence_refs": _all_refs(
            *(claim.effective_independence_refs for claim in graph_claims)
        ),
        "closeout_refs": [row.model_dump(mode="python") for row in closeout_refs],
        "closeout_verdict": closeout or None,
        "contested_record_refs": _all_refs(
            _refs_for(contested_rows, "contested_record_id", "id")
        ),
        "contested_records": contested_rows,
        "deficit_register_refs": _all_refs(_refs_for(deficit_rows, "deficit_id", "id")),
        "deficit_register": deficit_rows,
        "claim_registry_ref": _claim_registry_ref(registry),
        "semantic_binding_refs": _semantic_binding_refs(semantic),
        "producer_pipeline_ref": _optional_text(pipeline.get("producer_pipeline_ref")),
        "claim_decomposition_refs": _payload_ref(claim_decomposition),
        "projection_source_policy": RUNTIME_POLICY_DESIGN_CASE_PROJECTION_POLICY,
        "capability_reality_label": "implemented",
    }
    graph_ref = _stable_ref("runtime-pdc-graph", base_payload)
    base_payload["graph_ref"] = graph_ref
    base_payload["authority_envelope"] = {
        **base_payload["authority_envelope"],
        "graph_ref": graph_ref,
    }
    try:
        return RuntimePolicyDesignCase.model_validate(base_payload)
    except ValueError as exc:
        _raise_compiler_error(exc)


def runtime_policy_design_case_projection_source(
    runtime_pdc_graph: RuntimePolicyDesignCase | Mapping[str, Any],
) -> dict[str, Any]:
    """Return a projection-safe source payload derived only from the graph."""

    graph = _deserialize_graph(runtime_pdc_graph)
    authority = graph.authority_envelope.model_dump(mode="json")
    return {
        "schema_version": "policyos.runtime.pdc.graph_projection_source.v1",
        "authority_role": "projection_only",
        "projection_policy": RUNTIME_POLICY_DESIGN_CASE_PROJECTION_POLICY,
        "runtime_pdc_graph_ref": graph.graph_ref,
        "source_ref": graph.graph_ref,
        "audit_refs": _all_refs(
            (graph.graph_ref,),
            graph.semantic_binding_refs,
            graph.closeout_refs[0].closeout_ref if graph.closeout_refs else (),
        ),
        "source_authority_boundary": authority,
        "source_authority_refs": {
            "runtime_pdc_graph_ref": graph.graph_ref,
            "runtime_event_ref": graph.runtime_event_ref,
        },
        "closeout_verdict": graph.closeout_verdict or {},
        "contested_records": [dict(row) for row in graph.contested_records],
        "deficit_register": [dict(row) for row in graph.deficit_register],
        "invariant_summary": {
            "status": "pass" if not graph.conflict_refs else "warn",
            "passing_count": len(graph.claim_graph.claims),
            "failing_count": 0,
            "blocker_codes": [],
            "evidence_refs": _all_refs(
                graph.graph_ref,
                graph.claim_registry_ref,
                graph.semantic_binding_refs,
            ),
            "details": {
                "claim_count": len(graph.claim_graph.claims),
                "edge_count": len(graph.claim_graph.edges),
                "warrant_structure_count": len(graph.warrant_structures),
            },
        },
        "claim_graph_summary": {
            "claim_count": len(graph.claim_graph.claims),
            "edge_count": len(graph.claim_graph.edges),
            "obligation_ref_count": len(graph.obligation_refs),
            "producer_binding_ref_count": len(graph.producer_binding_refs),
            "baseline_ref_count": len(graph.baseline_refs),
            "alternative_ref_count": len(graph.alternative_refs),
            "conflict_ref_count": len(graph.conflict_refs),
            "effective_independence_ref_count": len(graph.effective_independence_refs),
        },
        "contract_verification_status": "not_verified",
        "contract_verification_refs": [],
    }


def persist_runtime_policy_design_case_graph(
    runtime_pdc_graph: RuntimePolicyDesignCase | Mapping[str, Any],
    *,
    store: object,
    inputs: Iterable[object] | None = None,
) -> object:
    """Persist a W8.A RuntimePolicyDesignCase graph as a replayable JSON artifact."""

    graph = _deserialize_graph(runtime_pdc_graph)
    return store.put_json(
        graph.model_dump(mode="json", exclude_none=True),
        artifacts.PutOptions(
            kind=RUNTIME_POLICY_DESIGN_CASE_ARTIFACT_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=RUNTIME_POLICY_DESIGN_CASE_SCHEMA_VERSION,
                version="1.0.0",
            ),
            inputs=list(inputs or ()),
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )


def _deserialize_graph(
    value: RuntimePolicyDesignCase | Mapping[str, Any],
) -> RuntimePolicyDesignCase:
    if isinstance(value, RuntimePolicyDesignCase):
        return value
    return RuntimePolicyDesignCase.model_validate(dict(value))


def _policy_design_case_payload(
    policy_design_case: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if policy_design_case is None:
        return None
    return dict(policy_design_case)


def claim_registry_rows_by_id(
    claim_registry: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return claim registry rows keyed by claim id without claiming authority."""

    rows: dict[str, dict[str, Any]] = {}
    if not isinstance(claim_registry, Mapping):
        return rows
    for index, row in enumerate(_sequence(claim_registry.get("claims"))):
        if not isinstance(row, Mapping):
            continue
        normalized = dict(row)
        claim_id = _claim_id(normalized, index)
        rows[claim_id] = normalized
    return rows


def _claim_rows(claims: Sequence[Mapping[str, Any]] | Mapping[str, Any]) -> list[dict[str, Any]]:
    if isinstance(claims, Mapping):
        raw = claims.get("claims")
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes, bytearray)):
            return [dict(row) for row in raw if isinstance(row, Mapping)]
        return []
    return [dict(row) for row in claims if isinstance(row, Mapping)]


def _claim_node(
    claim: Mapping[str, Any],
    *,
    index: int,
    registry_entry: Mapping[str, Any] | None,
    pipeline_binding_refs: Sequence[str],
) -> RuntimePdcClaimNode:
    entry = dict(registry_entry or {})
    claim_id = _claim_id(claim, index)
    source_class = (
        _optional_text(claim.get("decomposition_source_class"))
        or _optional_text(claim.get("source_class"))
        or _optional_text(entry.get("source_class"))
        or "deterministic_producer"
    )
    producer_binding_refs = _all_refs(
        *(_refs_for(entry, key) for key in _PRODUCER_BINDING_KEYS),
        _claim_bound_pipeline_refs(pipeline_binding_refs, claim_id),
    )
    conflict_refs = _all_refs(*(_refs_for(entry, key) for key in _CONFLICT_KEYS))
    effective_independence_refs = _all_refs(
        *(_refs_for(entry, key) for key in _INDEPENDENCE_KEYS),
        *(_refs_for(claim, key) for key in _INDEPENDENCE_KEYS),
    )
    try:
        return RuntimePdcClaimNode(
            claim_id=claim_id,
            claim_type=_optional_text(claim.get("claim_type")),
            claim_family=_optional_text(claim.get("claim_family")),
            claim_use=_optional_text(claim.get("claim_use")),
            text=_optional_text(claim.get("text") or claim.get("claim_text")),
            support_status=_optional_text(claim.get("support_status")),
            publishability=_optional_text(claim.get("publishability")),
            readiness_level=_optional_text(claim.get("readiness_level")),
            source_class=source_class,
            facet_refs=_all_refs(_refs_for(claim, "facet_refs"), _refs_for(entry, "facet_refs")),
            obligation_refs=_all_refs(
                _refs_for(claim, "obligation_refs"),
                _refs_for(entry, "obligation_refs"),
                _refs_for(entry, "scenario_requirement_refs"),
            ),
            producer_binding_refs=producer_binding_refs,
            baseline_refs=_all_refs(
                _refs_for(claim, "baseline_refs"), _refs_for(entry, "baseline_refs")
            ),
            alternative_refs=_all_refs(
                _refs_for(claim, "alternative_refs"), _refs_for(entry, "alternative_refs")
            ),
            warrant_refs=_all_refs(
                _refs_for(claim, "warrant_refs"),
                _refs_for(entry, "warrant_refs"),
            ),
            argument_refs=_all_refs(
                _refs_for(claim, "argument_refs"), _refs_for(entry, "argument_refs")
            ),
            rebuttal_refs=_all_refs(
                _refs_for(claim, "rebuttal_refs"), _refs_for(entry, "rebuttal_refs")
            ),
            conflict_refs=conflict_refs,
            effective_independence_refs=effective_independence_refs,
            accepted_deficit_refs=_all_refs(
                _refs_for(claim, "accepted_deficit_refs"),
                _refs_for(entry, "accepted_deficit_refs"),
            ),
            limitation_refs=_all_refs(
                _refs_for(claim, "limitation_refs"), _refs_for(entry, "limitation_refs")
            ),
            blocker_refs=_all_refs(
                _refs_for(claim, "blocker_refs"),
                _refs_for(entry, "blocker_refs"),
            ),
            runtime_claim_registry_entry_ref=_stable_ref(
                "runtime-pdc-claim-registry-entry",
                entry,
            )
            if entry
            else None,
        )
    except ValueError as exc:
        _raise_compiler_error(exc)


def _claim_edges(claims: Sequence[RuntimePdcClaimNode]) -> list[RuntimePdcClaimEdge]:
    edges: list[RuntimePdcClaimEdge] = []
    for claim in claims:
        edge_specs: tuple[tuple[str, str, Iterable[str]], ...] = (
            ("obligation_supports_claim", "obligation", claim.obligation_refs),
            ("producer_binding_supports_claim", "producer-binding", claim.producer_binding_refs),
            ("baseline_contextualizes_claim", "baseline", claim.baseline_refs),
            ("alternative_contextualizes_claim", "alternative", claim.alternative_refs),
            ("warrant_supports_claim", "warrant", (*claim.argument_refs, *claim.warrant_refs)),
            ("conflict_contests_claim", "conflict", claim.conflict_refs),
            ("independence_qualifies_claim", "independence", claim.effective_independence_refs),
        )
        for edge_type, prefix, refs in edge_specs:
            for ref in refs:
                edges.append(
                    RuntimePdcClaimEdge(
                        edge_id=_stable_ref(
                            "runtime-pdc-edge",
                            {
                                "source_ref": ref,
                                "target_ref": claim.claim_id,
                                "edge_type": edge_type,
                            },
                        ),
                        source_ref=f"{prefix}:{ref}" if ":" not in ref else ref,
                        target_ref=f"claim:{claim.claim_id}",
                        edge_type=edge_type,
                    )
                )
    return edges


def _warrant_structure(claim: RuntimePdcClaimNode) -> RuntimePdcWarrantStructure:
    return RuntimePdcWarrantStructure(
        structure_id=f"warrant-structure:{claim.claim_id}",
        claim_id=claim.claim_id,
        argument_refs=claim.argument_refs,
        warrant_refs=claim.warrant_refs,
        rebuttal_refs=claim.rebuttal_refs,
        evidence_refs=claim.producer_binding_refs,
        authority_refs=tuple(
            ref
            for ref in claim.producer_binding_refs
            if ref.startswith(("legal", "norm", "authority"))
        ),
        limitation_refs=claim.limitation_refs,
        accepted_deficit_refs=claim.accepted_deficit_refs,
        status="present"
        if claim.argument_refs or claim.warrant_refs
        else "pending_argument_graph",
    )


def _closeout_refs(closeout: Mapping[str, Any], *, run_id: str) -> list[RuntimePdcCloseoutRef]:
    if not closeout:
        return []
    status = _optional_text(closeout.get("status")) or "not_provided"
    verdict = _optional_text(closeout.get("verdict")) or "cannot_closeout"
    can_closeout = bool(closeout.get("can_closeout"))
    return [
        RuntimePdcCloseoutRef(
            closeout_ref=_stable_ref("runtime-pdc-closeout", closeout or {"run_id": run_id}),
            status=status,
            verdict=verdict,
            can_closeout=can_closeout,
        )
    ]


def _producer_binding_refs_from_pipeline(pipeline: Mapping[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for key in (
        "selected_binding_refs",
        "rejected_binding_refs",
        "blocked_binding_refs",
        "context_only_label_refs",
    ):
        refs.extend(_refs_for(pipeline.get("semantic_closure"), key))
    for record in _sequence(pipeline.get("producer_handshake_records")):
        refs.extend(_refs_for(record, "selected_binding_refs"))
        refs.extend(_refs_for(record, "emitted_binding_refs"))
        refs.extend(_refs_for(record, "blocked_binding_refs"))
    return _text_tuple(refs)


def _claim_bound_pipeline_refs(refs: Sequence[str], claim_id: str) -> tuple[str, ...]:
    claim_tokens = {claim_id, claim_id.replace("_", "-"), claim_id.replace("-", "_")}
    matched = [ref for ref in refs if any(token in ref for token in claim_tokens)]
    return _text_tuple(matched)


def _claim_registry_ref(registry: Mapping[str, Any]) -> str | None:
    return _optional_text(
        registry.get("runtime_claim_registry_ref")
        or registry.get("claim_registry_ref")
        or registry.get("registry_ref")
        or registry.get("provisional_claim_registry_ref")
    )


def _semantic_binding_refs(semantic: Mapping[str, Any]) -> tuple[str, ...]:
    return _all_refs(
        _refs_for(
            semantic,
            "semantic_binding_ref",
            "semantic_closure_ref",
            "producer_handshake_ledger_ref",
        )
    )


def _payload_ref(payload: Mapping[str, Any] | None) -> tuple[str, ...]:
    if not isinstance(payload, Mapping):
        return ()
    return _refs_for(payload, "ref", "graph_ref", "graph_id", "case_id", "report_fingerprint")


def _refs_for(value: object, *keys: str) -> tuple[str, ...]:
    refs: list[str] = []
    if isinstance(value, Mapping):
        for key in keys:
            refs.extend(_text_tuple(value.get(key)))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            refs.extend(_refs_for(item, *keys))
    else:
        refs.extend(_text_tuple(value))
    return _text_tuple(refs)


def _all_refs(*values: object) -> tuple[str, ...]:
    refs: list[str] = []
    for value in values:
        refs.extend(_text_tuple(value))
    return _text_tuple(refs)


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    return (
        _optional_text(claim.get("claim_id") or claim.get("id") or claim.get("claim_ref"))
        or f"claim-{index + 1}"
    )


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[object]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return value
    return ()


def _text_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values: Iterable[object] = (value,)
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        values = value
    else:
        values = (value,)
    result: list[str] = []
    for item in values:
        text = _optional_text(item)
        if text and text not in result:
            result.append(text)
    return tuple(result)


def _required_text(value: object, code: str) -> str:
    text = _optional_text(value)
    if not text:
        raise RuntimePolicyDesignCaseCompilerError(code, code)
    return text


def _optional_text(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return None


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC, microsecond=0)
    return value.astimezone(UTC).replace(microsecond=0)


def _stable_ref(prefix: str, payload: object) -> str:
    serialized = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(f"{prefix}:{serialized}".encode()).hexdigest()


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json", exclude_none=True)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(item) for item in value]
    return value


def _raise_compiler_error(exc: ValueError) -> None:
    message = str(exc)
    if "runtime_pdc_graph_llm_authority_laundering" in message:
        raise RuntimePolicyDesignCaseCompilerError(
            "runtime_pdc_graph_llm_authority_laundering",
            "LLM-sourced claims cannot enter non-context graph authority slots.",
        ) from exc
    raise RuntimePolicyDesignCaseCompilerError("runtime_pdc_graph_invalid", message) from exc


__all__ = [
    "RUNTIME_POLICY_DESIGN_CASE_SCHEMA_VERSION",
    "RuntimePdcAuthorityEnvelope",
    "RuntimePdcClaimEdge",
    "RuntimePdcClaimGraph",
    "RuntimePdcClaimNode",
    "RuntimePdcCloseoutRef",
    "RuntimePdcWarrantStructure",
    "RuntimePolicyDesignCase",
    "RuntimePolicyDesignCaseCompilerError",
    "compile_runtime_policy_design_case",
    "persist_runtime_policy_design_case_graph",
    "runtime_policy_design_case_projection_source",
]
