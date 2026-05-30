"""Runtime-owned registry that binds producer evidence to final claims."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from polisyos.runtime.quality.calibration_ledger import (
    historical_prior_claim_evidence_issues,
)
from polisyos.runtime.quality.candidate_firewall import (
    candidate_firewall_issues_for_payload,
)
from polisyos.runtime.quality.ir_analytics_bridge import (
    IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY,
    ir_analytics_bridge_issues_for_claims,
    ir_analytics_claim_bindings_by_claim,
    merge_ir_analytics_binding_into_registry_entry,
    normalize_ir_analytics_claim_bridge,
)
from polisyos.runtime.quality.memory_influence import (
    memory_influence_claim_evidence_issues,
)

SCHEMA_VERSION = "policyos.runtime.claim_registry.v1"
REPORT_KIND = "runtime.claim_registry"
REPORT_REF_KEY = "runtime_claim_registry_ref"

_REQUIRED_ENTRY_REF_SPECS: tuple[tuple[str, str], ...] = (
    ("scenario_requirement_refs", "scenario_requirement"),
    ("data_refs", "data"),
    ("selected_norm_refs", "selected_norm"),
    ("method_output_refs", "method_output"),
    ("portfolio_refs", "portfolio"),
    ("argument_refs", "argument"),
    ("warrant_refs", "warrant"),
    ("rebuttal_refs", "rebuttal"),
    ("counter_evidence_refs", "counter_evidence"),
    ("limitation_refs", "limitation"),
    ("accepted_deficit_refs", "accepted_deficit"),
)

_OPTIONAL_EMPTY_REF_KEYS = frozenset(
    {
        "assumption_gate_refs",
        "legal_authority_record_refs",
        "legal_authority_blocker_refs",
        "ir_analytics_refs",
        "ir_certificate_refs",
        "negative_certificate_refs",
        "proof_composability_refs",
        "proof_statuses",
        "proof_composability_statuses",
        "baseline_refs",
        "alternative_refs",
        "comparison_refs",
        "conflict_refs",
        "claim_family",
        "claim_type",
        "claim_use",
    }
)


@dataclass(frozen=True)
class RuntimeClaimRegistryEntry:
    """Claim-bound evidence surface emitted by runtime producers."""

    claim_id: str
    scenario_requirement_refs: tuple[str, ...] = ()
    data_refs: tuple[str, ...] = ()
    selected_norm_refs: tuple[str, ...] = ()
    rejected_norm_refs: tuple[str, ...] = ()
    method_output_refs: tuple[str, ...] = ()
    portfolio_refs: tuple[str, ...] = ()
    argument_refs: tuple[str, ...] = ()
    warrant_refs: tuple[str, ...] = ()
    rebuttal_refs: tuple[str, ...] = ()
    counter_evidence_refs: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()
    accepted_deficit_refs: tuple[str, ...] = ()
    assumption_gate_refs: tuple[str, ...] = ()
    legal_authority_record_refs: tuple[str, ...] = ()
    legal_authority_blocker_refs: tuple[str, ...] = ()
    uncertainty_refs: tuple[str, ...] = ()
    baseline_refs: tuple[str, ...] = ()
    alternative_refs: tuple[str, ...] = ()
    comparison_refs: tuple[str, ...] = ()
    blocker_refs: tuple[str, ...] = ()
    extra: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "claim_id": self.claim_id,
            "scenario_requirement_refs": list(self.scenario_requirement_refs),
            "data_refs": list(self.data_refs),
            "selected_norm_refs": list(self.selected_norm_refs),
            "rejected_norm_refs": list(self.rejected_norm_refs),
            "method_output_refs": list(self.method_output_refs),
            "portfolio_refs": list(self.portfolio_refs),
            "argument_refs": list(self.argument_refs),
            "warrant_refs": list(self.warrant_refs),
            "rebuttal_refs": list(self.rebuttal_refs),
            "counter_evidence_refs": list(self.counter_evidence_refs),
            "limitation_refs": list(self.limitation_refs),
            "accepted_deficit_refs": list(self.accepted_deficit_refs),
            "assumption_gate_refs": list(self.assumption_gate_refs),
            "legal_authority_record_refs": list(self.legal_authority_record_refs),
            "legal_authority_blocker_refs": list(self.legal_authority_blocker_refs),
            "uncertainty_refs": list(self.uncertainty_refs),
            "baseline_refs": list(self.baseline_refs),
            "alternative_refs": list(self.alternative_refs),
            "comparison_refs": list(self.comparison_refs),
            "blocker_refs": list(self.blocker_refs),
        }
        payload.update(dict(self.extra))
        return payload


@dataclass(frozen=True)
class RuntimeClaimRegistry:
    """Normalized registry payload plus validation status."""

    claims: tuple[RuntimeClaimRegistryEntry, ...]
    status: str = "pass"
    issues: tuple[Mapping[str, Any], ...] = ()
    summary: Mapping[str, Any] = field(default_factory=dict)
    registry_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "claims": [entry.to_dict() for entry in self.claims],
            "summary": dict(self.summary),
            "issues": [dict(issue) for issue in self.issues],
        }
        if self.registry_ref:
            payload[REPORT_REF_KEY] = self.registry_ref
        return payload


def build_runtime_claim_registry(
    *,
    claims: Sequence[Mapping[str, Any]],
    scenario_evidence_contract: Mapping[str, Any] | None = None,
    fabric_retrieval_trace: Mapping[str, Any] | None = None,
    normative_evidence: Mapping[str, Any] | None = None,
    foundry_method_report: Mapping[str, Any] | None = None,
    ir_analytics_bridge: Mapping[str, Any] | None = None,
    run_id: str | None = None,
    registry_ref: str | None = None,
    spine_context: Mapping[str, Any] | None = None,
    hypothesis_ledger: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the runtime claim registry from final, claim-local evidence refs."""

    entries = [
        _entry_from_claim(
            dict(claim),
            index=index,
            run_id=run_id,
            scenario_evidence_contract=scenario_evidence_contract,
            registry_ref=registry_ref,
            spine_context=spine_context,
        )
        for index, claim in enumerate(claims or [])
        if isinstance(claim, Mapping)
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "registry_kind": REPORT_KIND,
        "claims": entries,
    }
    if registry_ref:
        payload[REPORT_REF_KEY] = registry_ref
    return normalize_runtime_claim_registry(
        payload,
        claims=claims,
        normative_evidence=normative_evidence,
        fabric_retrieval_trace=fabric_retrieval_trace,
        foundry_method_report=foundry_method_report,
        ir_analytics_bridge=ir_analytics_bridge,
        run_id=run_id,
        hypothesis_ledger=hypothesis_ledger,
    )


def normalize_runtime_claim_registry(
    claim_registry: Mapping[str, Any] | None,
    *,
    claims: Sequence[Mapping[str, Any]] | None = None,
    normative_evidence: Mapping[str, Any] | None = None,
    fabric_retrieval_trace: Mapping[str, Any] | None = None,
    foundry_method_report: Mapping[str, Any] | None = None,
    ir_analytics_bridge: Mapping[str, Any] | None = None,
    run_id: str | None = None,
    hypothesis_ledger: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Normalize and validate a stored runtime claim registry payload."""

    payload = dict(claim_registry or {})
    bridge_payload = (
        ir_analytics_bridge
        if ir_analytics_bridge is not None
        else payload.get("ir_analytics_bridge")
        if isinstance(payload.get("ir_analytics_bridge"), Mapping)
        else None
    )
    normalized_ir_analytics_bridge = normalize_ir_analytics_claim_bridge(
        bridge_payload,
        run_id=run_id,
    )
    ir_bindings_by_claim = ir_analytics_claim_bindings_by_claim(
        normalized_ir_analytics_bridge,
    )
    rows = [
        merge_ir_analytics_binding_into_registry_entry(
            _normalize_entry_row(dict(row), index=index, run_id=run_id),
            ir_bindings_by_claim.get(_claim_id(row, index)),
        )
        for index, row in enumerate(_claim_rows(payload))
    ]
    issues: list[dict[str, Any]] = []
    major_claim_ids = [
        _claim_id(dict(claim), index)
        for index, claim in enumerate(claims or [])
        if isinstance(claim, Mapping) and _is_major_claim(claim)
    ]
    rows_by_id = {
        str(row.get("claim_id")): row
        for row in rows
        if _text(row.get("claim_id"))
    }
    global_norm_refs = _global_norm_refs(normative_evidence)
    global_method_refs = _global_method_refs(foundry_method_report)
    generic_global_method_refs = [
        ref for ref in global_method_refs if _is_generic_method_ref(ref)
    ]

    for claim_id in major_claim_ids:
        if claim_id in rows_by_id:
            continue
        issues.append(
            _issue(
                code="runtime_claim_registry_entry_missing",
                claim_id=claim_id,
                missing_evidence_type="claim_registry_entry",
                message=(
                    f"Major claim {claim_id} has no runtime claim registry entry. "
                    "Global evidence pools are not claim-bound authority."
                ),
                next_action=(
                    "Create a RuntimeClaimRegistry row that binds this claim to "
                    "Fabric, Lex, Foundry, argument, warrant, counter-evidence, "
                    "limitations, and accepted deficits."
                ),
                global_norm_refs=global_norm_refs,
                global_method_refs=global_method_refs,
            )
        )

    for row in rows:
        issues.extend(_entry_issues(row))
        issues.extend(_candidate_firewall_issues(row, hypothesis_ledger=hypothesis_ledger))
    issues.extend(
        ir_analytics_bridge_issues_for_claims(
            claims=claims,
            bridge=normalized_ir_analytics_bridge,
            registry_rows=rows,
        )
    )

    status = _status_from_issues(issues)
    registry_ref = _text(payload.get(REPORT_REF_KEY) or payload.get("registry_ref"))
    summary = {
        "claim_count": len(rows),
        "major_claim_count": len(major_claim_ids),
        "entry_count": len(rows),
        "issue_count": len(issues),
        "global_norm_ref_count": len(global_norm_refs),
        "global_method_ref_count": len(global_method_refs),
        "generic_global_method_ref_count": len(generic_global_method_refs),
        "selected_data_ref_count": len(_global_data_refs(fabric_retrieval_trace)),
    }
    if normalized_ir_analytics_bridge is not None:
        summary.update(
            {
                "ir_analytics_binding_count": int(
                    normalized_ir_analytics_bridge.get("summary", {}).get("binding_count", 0)
                ),
                "ir_analytics_blocked_claim_count": int(
                    normalized_ir_analytics_bridge.get("summary", {}).get(
                        "blocked_claim_count",
                        0,
                    )
                ),
                "ir_analytics_bridge_status": normalized_ir_analytics_bridge.get("status"),
            }
        )
    result = {
        **payload,
        "schema_version": SCHEMA_VERSION,
        "registry_kind": REPORT_KIND,
        "status": status,
        "claims": rows,
        "summary": summary,
        "issues": issues,
    }
    if normalized_ir_analytics_bridge is not None:
        result["ir_analytics_bridge"] = normalized_ir_analytics_bridge
    if registry_ref:
        result[REPORT_REF_KEY] = registry_ref
    return result


def claim_registry_rows_by_id(
    claim_registry: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return normalized registry rows keyed by claim id."""

    if not isinstance(claim_registry, Mapping):
        return {}
    rows = {}
    for index, row in enumerate(_claim_rows(claim_registry)):
        normalized = _normalize_entry_row(dict(row), index=index, run_id=None)
        claim_id = _text(normalized.get("claim_id"))
        if claim_id:
            rows[claim_id] = normalized
    return rows


def apply_runtime_claim_registry_to_claim(
    claim: Mapping[str, Any],
    registry_entry: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project a registry entry onto a claim for downstream validators."""

    merged = dict(claim)
    if not isinstance(registry_entry, Mapping):
        return merged
    entry = _normalize_entry_row(dict(registry_entry), index=0, run_id=None)
    ref_mapping = {
        "scenario_requirement_refs": "scenario_requirement_refs",
        "data_refs": "data_refs",
        "selected_norm_refs": "selected_norm_refs",
        "rejected_norm_refs": "rejected_norm_refs",
        "legal_authority_record_refs": "legal_authority_record_refs",
        "legal_authority_blocker_refs": "legal_authority_blocker_refs",
        "method_output_refs": "method_output_refs",
        "portfolio_refs": "portfolio_refs",
        "argument_refs": "argument_refs",
        "warrant_refs": "warrant_refs",
        "rebuttal_refs": "rebuttal_refs",
        "counter_evidence_refs": "counter_evidence_refs",
        "limitation_refs": "limitation_refs",
        "accepted_deficit_refs": "accepted_deficit_refs",
        "blocker_refs": "blocker_refs",
        "independence_refs": "independence_refs",
        "synthesis_refs": "synthesis_refs",
        "ir_analytics_refs": "ir_analytics_refs",
        "ir_certificate_refs": "ir_certificate_refs",
        "negative_certificate_refs": "negative_certificate_refs",
        "proof_composability_refs": "proof_composability_refs",
        "uncertainty_refs": "uncertainty_refs",
        "baseline_refs": "baseline_refs",
        "alternative_refs": "alternative_refs",
        "comparison_refs": "comparison_refs",
        "conflict_refs": "conflict_refs",
    }
    for source_key, target_key in ref_mapping.items():
        refs = _as_refs(entry.get(source_key))
        if refs:
            merged[target_key] = refs
    if entry.get("selected_norm_refs"):
        merged["norm_refs"] = _as_refs(entry.get("selected_norm_refs"))
    if entry.get("method_output_refs"):
        merged["method_refs"] = _as_refs(entry.get("method_output_refs"))

    evidence_graph = (
        dict(merged.get("evidence_graph"))
        if isinstance(merged.get("evidence_graph"), Mapping)
        else {}
    )
    for key in (
        "portfolio_refs",
        "independence_refs",
        "synthesis_refs",
        "argument_refs",
        "warrant_refs",
        "rebuttal_refs",
        "counter_evidence_refs",
        "limitation_refs",
        "accepted_deficit_refs",
        "legal_authority_record_refs",
        "legal_authority_blocker_refs",
        "ir_analytics_refs",
        "ir_certificate_refs",
        "negative_certificate_refs",
        "proof_composability_refs",
        "uncertainty_refs",
        "baseline_refs",
        "alternative_refs",
        "comparison_refs",
        "conflict_refs",
    ):
        refs = _as_refs(entry.get(key))
        if refs:
            evidence_graph[key] = refs
    if evidence_graph:
        merged["evidence_graph"] = evidence_graph
    merged["runtime_claim_registry_entry"] = {
        key: value
        for key, value in entry.items()
        if key
        in {
            "claim_id",
            "claim_ref",
            "runtime_event_ref",
            "scenario_requirement_refs",
            "data_refs",
            "selected_norm_refs",
            "rejected_norm_refs",
            "legal_authority_record_refs",
            "legal_authority_blocker_refs",
            "method_output_refs",
            "portfolio_refs",
            "argument_refs",
            "warrant_refs",
            "rebuttal_refs",
            "counter_evidence_refs",
            "limitation_refs",
            "accepted_deficit_refs",
            "blocker_refs",
            "concept_spine_ref",
            "producer_handshake_ledger_ref",
            "producer_handshake_refs",
            IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY,
            "ir_analytics_runtime_event_ref",
            "ir_analytics_refs",
            "ir_certificate_refs",
            "negative_certificate_refs",
            "proof_statuses",
            "proof_composability_refs",
            "proof_composability_statuses",
            "uncertainty_refs",
            "baseline_refs",
            "alternative_refs",
            "comparison_refs",
            "conflict_refs",
        }
    }
    return merged


def runtime_claim_registry_issues_for_claims(
    *,
    claims: Sequence[Mapping[str, Any]],
    claim_registry: Mapping[str, Any] | None,
    normative_evidence: Mapping[str, Any] | None = None,
    fabric_retrieval_trace: Mapping[str, Any] | None = None,
    foundry_method_report: Mapping[str, Any] | None = None,
    ir_analytics_bridge: Mapping[str, Any] | None = None,
    hypothesis_ledger: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    normalized = normalize_runtime_claim_registry(
        claim_registry,
        claims=claims,
        normative_evidence=normative_evidence,
        fabric_retrieval_trace=fabric_retrieval_trace,
        foundry_method_report=foundry_method_report,
        ir_analytics_bridge=ir_analytics_bridge,
        hypothesis_ledger=hypothesis_ledger,
    )
    return [dict(issue) for issue in normalized.get("issues") or []]


def _entry_from_claim(
    claim: Mapping[str, Any],
    *,
    index: int,
    run_id: str | None,
    scenario_evidence_contract: Mapping[str, Any] | None,
    registry_ref: str | None,
    spine_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    claim_id = _claim_id(claim, index)
    selected_norm_refs = _refs_for_aliases(
        claim,
        (
            "selected_norm_refs",
            "legal_norm_refs",
            "norm_refs",
            "normative_refs",
            "norm_ids",
            "legal_refs",
        ),
    )
    method_output_refs = _refs_for_aliases(
        claim,
        (
            "method_output_refs",
            "method_output_ref",
            "method_refs",
            "foundry_method_refs",
            "analysis_refs",
            "result_refs",
        ),
    )
    data_refs = _refs_for_aliases(
        claim,
        (
            "data_refs",
            "source_data_refs",
            "data_source_refs",
            "source_refs",
            "dataset_refs",
            "fabric_refs",
            "data_snapshot_refs",
        ),
    )
    rebuttal_refs = _refs_for_aliases(
        claim,
        (
            "rebuttal_refs",
            "claim_rebuttal_refs",
            "rebuttal_evidence_refs",
        ),
    )
    counter_evidence_refs = _refs_for_aliases(
        claim,
        (
            "counter_evidence_refs",
            "counterevidence_refs",
            "disconfirming_refs",
            "disconfirming_evidence_refs",
            "disconfirming_ledger_refs",
        ),
    )
    limitation_refs = _refs_for_aliases(
        claim,
        (
            "limitation_refs",
            "accepted_limitation_refs",
            "claim_limitation_refs",
            "data_quality_limitation_refs",
            "degrade_reason_refs",
        ),
    )
    accepted_deficit_refs = _refs_for_aliases(
        claim,
        (
            "accepted_deficit_refs",
            "accepted_deficits",
            "accepted_literature_deficit_refs",
        ),
    )
    rejected_method_refs = [ref for ref in method_output_refs if _is_generic_method_ref(ref)]
    if rejected_method_refs:
        method_output_refs = [ref for ref in method_output_refs if ref not in rejected_method_refs]
    scenario_requirement_refs = _refs_for_aliases(
        claim,
        (
            "scenario_requirement_refs",
            "requirement_refs",
            "scenario_evidence_requirement_refs",
        ),
    )
    if not scenario_requirement_refs and isinstance(scenario_evidence_contract, Mapping):
        scenario_requirement_refs = _claim_specific_requirement_refs(
            claim_id=claim_id,
            scenario_evidence_contract=scenario_evidence_contract,
        )

    entry: dict[str, Any] = {
        "claim_id": claim_id,
        "claim_ref": _safe_ref(claim.get("claim_ref") or claim.get("cas_ref"))
        or _stable_claim_ref(claim),
        "runtime_event_ref": _runtime_event_ref(claim, claim_id=claim_id, run_id=run_id),
        "claim_family": _text(claim.get("claim_family") or claim.get("family")),
        "claim_type": _text(claim.get("claim_type") or claim.get("type")),
        "claim_use": _text(claim.get("claim_use") or claim.get("use")),
        "authority_role": _text(claim.get("authority_role")) or "producer_authority",
        "provenance_kind": _text(claim.get("provenance_kind")) or "runtime_emitted",
        "assurance_node_id": _text(
            claim.get("assurance_node_id")
            or claim.get("claim_node_id")
            or f"claim-node-{_slug(claim_id)}"
        ),
        "scenario_requirement_refs": scenario_requirement_refs,
        "data_refs": data_refs,
        "selected_norm_refs": selected_norm_refs,
        "rejected_norm_refs": _refs_for_aliases(
            claim,
            ("rejected_norm_refs", "rejected_legal_norm_refs", "rejected_norm_ids"),
        ),
        "method_output_refs": method_output_refs,
        "portfolio_refs": _refs_for_aliases(
            claim,
            ("portfolio_refs", "portfolio_design_refs", "evidence_portfolio_refs"),
        ),
        "argument_refs": _refs_for_aliases(
            claim,
            ("argument_refs", "claim_argument_refs", "argument_evidence_refs"),
        ),
        "warrant_refs": _refs_for_aliases(
            claim,
            (
                "warrant_refs",
                "claim_warrant_refs",
                "warrant_evidence_refs",
                "berl_warrant_refs",
                "berl_reliability_refs",
            ),
        ),
        "rebuttal_refs": rebuttal_refs,
        "counter_evidence_refs": counter_evidence_refs,
        "limitation_refs": limitation_refs,
        "accepted_deficit_refs": accepted_deficit_refs,
        "blocker_refs": _refs_for_aliases(
            claim,
            ("blocker_refs", "typed_blocker_refs", "blocking_issue_refs"),
        ),
        "rejected_method_refs": rejected_method_refs,
        "concept_refs": _refs_for_aliases(claim, ("concept_refs", "policy_concept_refs")),
        "independence_refs": _refs_for_aliases(
            claim,
            ("independence_refs", "independence_map_refs"),
        ),
        "synthesis_refs": _refs_for_aliases(
            claim,
            ("synthesis_refs", "synthesis_report_refs", "evidence_synthesis_refs"),
        ),
        "specification_curve_refs": _refs_for_aliases(
            claim,
            (
                "specification_curve_refs",
                "multiverse_specification_curve_refs",
                "multiverse_curve_refs",
            ),
        ),
        "assumption_gate_refs": _refs_for_aliases(
            claim,
            ("assumption_gate_refs", "assumption_refs", "runtime_assumption_gate_refs"),
        ),
        "legal_authority_record_refs": _refs_for_aliases(
            claim,
            (
                "legal_authority_record_refs",
                "legal_authority_refs",
                "lex_legal_authority_record_refs",
                "legal_competence_record_refs",
            ),
        ),
        "legal_authority_blocker_refs": _refs_for_aliases(
            claim,
            (
                "legal_authority_blocker_refs",
                "legal_blocker_refs",
                "lex_legal_authority_blocker_refs",
                "legal_competence_blocker_refs",
            ),
        ),
        "objective_tradeoff_refs": _refs_for_aliases(
            claim,
            ("objective_tradeoff_refs", "objective_refs", "tradeoff_refs"),
        ),
        "uncertainty_refs": _refs_for_aliases(
            claim,
            ("uncertainty_refs", "residual_uncertainty_refs", "foundry_uncertainty_refs"),
        ),
        "ir_analytics_refs": _refs_for_aliases(
            claim,
            ("ir_analytics_refs", "analytics_refs", "ir_result_refs"),
        ),
        "ir_certificate_refs": _refs_for_aliases(
            claim,
            ("ir_certificate_refs", "certificate_refs", "dual_certificate_refs"),
        ),
        "negative_certificate_refs": _refs_for_aliases(
            claim,
            ("negative_certificate_refs", "non_identification_refs"),
        ),
        "proof_composability_refs": _refs_for_aliases(
            claim,
            ("proof_composability_refs", "composability_certificate_refs"),
        ),
        "proof_statuses": _refs_for_aliases(claim, ("proof_statuses", "proof_status")),
        "proof_composability_statuses": _refs_for_aliases(
            claim,
            ("proof_composability_statuses", "proof_composability_status"),
        ),
        "baseline_refs": _refs_for_aliases(
            claim,
            ("baseline_refs", "comparison_baseline_refs"),
        ),
        "alternative_refs": _refs_for_aliases(
            claim,
            ("alternative_refs", "comparison_alternative_refs", "named_alternative_refs"),
        ),
        "comparison_refs": _refs_for_aliases(
            claim,
            (
                "comparison_refs",
                "baseline_comparison_refs",
                "baseline_alternative_comparison_refs",
            ),
        ),
        "conflict_refs": _refs_for_aliases(claim, ("conflict_refs", "conflict_ref")),
        "numerical_semantics_refs": _refs_for_aliases(
            claim,
            ("numerical_semantics_refs", "number_semantics_refs", "unit_semantics_refs"),
        ),
        "monitoring_refs": _refs_for_aliases(
            claim,
            ("monitoring_refs", "monitoring_plan_refs", "implementation_monitoring_refs"),
        ),
        "scholar_refs": _refs_for_aliases(
            claim,
            (
                "scholar_refs",
                "literature_refs",
                "scholar_literature_refs",
                "academic_evidence_refs",
            ),
        ),
        "scholar_deficit_refs": _refs_for_aliases(
            claim,
            (
                "scholar_deficit_refs",
                "literature_deficit_refs",
                "accepted_literature_deficit_refs",
            ),
        ),
    }
    if registry_ref:
        entry["runtime_claim_registry_ref"] = registry_ref
    if isinstance(spine_context, Mapping):
        for key in (
            "spine_ref",
            "concept_spine_ref",
            "evidence_spine_ref",
            "scenario_evidence_contract_id",
            "producer_handshake_ledger_ref",
        ):
            value = _text(spine_context.get(key))
            if value:
                entry[key] = value
        handshake_refs = _as_refs(spine_context.get("producer_handshake_refs"))
        if handshake_refs:
            entry["producer_handshake_refs"] = handshake_refs
    _add_compatibility_fields(entry)
    _drop_optional_empty_refs(entry)
    return entry


def _normalize_entry_row(
    row: Mapping[str, Any],
    *,
    index: int,
    run_id: str | None,
) -> dict[str, Any]:
    claim_id = _text(row.get("claim_id") or row.get("id") or f"claim_{index + 1}")
    normalized = _entry_from_claim(
        {**dict(row), "claim_id": claim_id},
        index=index,
        run_id=run_id,
        scenario_evidence_contract=None,
        registry_ref=_text(row.get("runtime_claim_registry_ref") or row.get(REPORT_REF_KEY))
        or None,
        spine_context=None,
    )
    for key, value in row.items():
        if key not in normalized or not normalized.get(key):
            normalized[key] = value
    for key in (
        "scenario_requirement_refs",
        "data_refs",
        "selected_norm_refs",
        "rejected_norm_refs",
        "method_output_refs",
        "portfolio_refs",
        "argument_refs",
        "warrant_refs",
        "rebuttal_refs",
        "counter_evidence_refs",
        "limitation_refs",
        "accepted_deficit_refs",
        "blocker_refs",
        "ir_analytics_refs",
        "ir_certificate_refs",
        "negative_certificate_refs",
        "proof_composability_refs",
        "proof_statuses",
        "proof_composability_statuses",
        "uncertainty_refs",
        "assumption_gate_refs",
        "legal_authority_record_refs",
        "legal_authority_blocker_refs",
        "baseline_refs",
        "alternative_refs",
        "comparison_refs",
        "conflict_refs",
    ):
        if key in row:
            normalized[key] = _as_refs(row.get(key))
    _add_compatibility_fields(normalized)
    _drop_optional_empty_refs(normalized)
    return normalized


def _entry_issues(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    claim_id = _text(row.get("claim_id"))
    issues: list[dict[str, Any]] = []
    for key, label in _REQUIRED_ENTRY_REF_SPECS:
        if _as_refs(row.get(key)):
            continue
        issues.append(
            _issue(
                code=f"runtime_claim_registry_{key}_missing",
                claim_id=claim_id,
                missing_evidence_type=label,
                message=f"Runtime claim registry entry {claim_id} has no {label} refs.",
                next_action=(
                    "Bind the claim to the missing runtime evidence axis before "
                    "policy grounding or publication can pass."
                ),
            )
    )
    method_output_refs = _as_refs(row.get("method_output_refs"))
    if any(_requires_method_runtime_evidence(ref) for ref in method_output_refs):
        if not _as_refs(row.get("assumption_gate_refs")) and not (
            _as_refs(row.get("ir_certificate_refs"))
            or _as_refs(row.get("proof_composability_refs"))
            or _as_refs(row.get("ir_analytics_refs"))
        ):
            issues.append(
                _issue(
                    code="runtime_claim_registry_assumption_gate_refs_missing",
                    claim_id=claim_id,
                    missing_evidence_type="assumption_gate",
                    message=(
                        f"Runtime claim registry entry {claim_id} has method output refs "
                        "but no runtime assumption-gate refs."
                    ),
                    next_action=(
                        "Bind the selected method output to assumption validation or "
                        "proof-carrying IR certificate refs before claim closure."
                    ),
                )
            )
        if not _as_refs(row.get("uncertainty_refs")):
            issues.append(
                _issue(
                    code="runtime_claim_registry_uncertainty_refs_missing",
                    claim_id=claim_id,
                    missing_evidence_type="uncertainty",
                    message=(
                        f"Runtime claim registry entry {claim_id} has method output refs "
                        "but no uncertainty refs."
                    ),
                    next_action=(
                        "Bind uncertainty envelopes, residual uncertainty, or certified "
                        "bounds refs before treating the method output as claim support."
                    ),
                )
            )
    rejected_methods = _as_refs(row.get("rejected_method_refs"))
    generic_selected = [
        ref for ref in _as_refs(row.get("method_output_refs")) if _is_generic_method_ref(ref)
    ]
    if rejected_methods or generic_selected:
        issues.append(
            _issue(
                code="runtime_claim_registry_generic_method_not_admissible",
                claim_id=claim_id,
                missing_evidence_type="method_output",
                message=(
                    "Generic method refs such as foundry.execute cannot satisfy "
                    "claim-bound method output obligations."
                ),
                next_action="Select named Foundry analytical method output refs.",
                rejected_method_refs=_dedupe([*rejected_methods, *generic_selected]),
            )
        )
    claim_use = _text(row.get("claim_use") or row.get("use"))
    if claim_use == "superiority" and (
        not _as_refs(row.get("baseline_refs")) or not _as_refs(row.get("alternative_refs"))
    ):
        issues.append(
            _issue(
                code="runtime_claim_registry_superiority_comparator_refs_missing",
                claim_id=claim_id,
                missing_evidence_type="baseline_or_alternative",
                message=(
                    "Superiority claims require both baseline_refs and named "
                    "alternative_refs before admission to the runtime claim registry."
                ),
                next_action=(
                    "Bind no-action/status-quo/business-as-usual baselines and at "
                    "least one named alternative record from claim decomposition."
                ),
            )
        )
    if claim_use == "superiority" and not _as_refs(row.get("comparison_refs")):
        issues.append(
            _issue(
                code="runtime_claim_registry_superiority_comparison_refs_missing",
                claim_id=claim_id,
                missing_evidence_type="baseline_alternative_comparison",
                message=(
                    "Superiority claims require W8.C baseline/alternative comparison "
                    "records before they can pass semantic binding."
                ),
                next_action=(
                    "Run polisyos.scientist.policy_design.baseline_compiler and bind "
                    "the emitted comparison_refs to the runtime claim registry entry."
                ),
            )
        )
    issues.extend(historical_prior_claim_evidence_issues(row, claim_id=claim_id))
    issues.extend(memory_influence_claim_evidence_issues(row, claim_id=claim_id))
    return issues


def _candidate_firewall_issues(
    row: Mapping[str, Any],
    *,
    hypothesis_ledger: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    if hypothesis_ledger is None:
        embedded = row.get("hypothesis_ledger")
        hypothesis_ledger = embedded if isinstance(embedded, Mapping) else None
    claim_id = _text(row.get("claim_id"))
    issues: list[dict[str, Any]] = []
    slot_payloads = (
        ("legal_authority", {"selected_norm_refs": _as_refs(row.get("selected_norm_refs"))}),
        ("data_authority", {"data_refs": _as_refs(row.get("data_refs"))}),
        ("method_authority", {"method_output_refs": _as_refs(row.get("method_output_refs"))}),
        ("claim_authority", {"claim_refs": _as_refs(row.get("claim_refs"))}),
        ("closeout_authority", {"blocker_refs": _as_refs(row.get("blocker_refs"))}),
    )
    for authority_slot, payload in slot_payloads:
        for issue in candidate_firewall_issues_for_payload(
            payload,
            hypothesis_ledger=hypothesis_ledger,
            authority_slots=(authority_slot,),
            surface="claim_registry",
        ):
            issue["claim_id"] = claim_id
            issue["missing_evidence_type"] = authority_slot
            issues.append(issue)
    return issues


def _add_compatibility_fields(row: dict[str, Any]) -> None:
    row["source_data_refs"] = _as_refs(row.get("source_data_refs")) or _as_refs(
        row.get("data_refs")
    )
    row["legal_norm_refs"] = _as_refs(row.get("legal_norm_refs")) or _as_refs(
        row.get("selected_norm_refs")
    )
    row["method_refs"] = _as_refs(row.get("method_refs")) or _as_refs(
        row.get("method_output_refs")
    )
    disconfirming = _dedupe(
        [
            *_as_refs(row.get("disconfirming_refs")),
            *_as_refs(row.get("rebuttal_refs")),
            *_as_refs(row.get("counter_evidence_refs")),
        ]
    )
    if disconfirming:
        row["disconfirming_refs"] = disconfirming
    if not _as_refs(row.get("scholar_refs")) and _as_refs(row.get("accepted_deficit_refs")):
        row["scholar_deficit_refs"] = _as_refs(row.get("scholar_deficit_refs")) or _as_refs(
            row.get("accepted_deficit_refs")
        )
    selected = dict(row.get("selected_producer_refs") or {})
    _set_selected(selected, "lex", _as_refs(row.get("legal_norm_refs")))
    _set_selected(
        selected,
        "lex_legal_authority",
        _as_refs(row.get("legal_authority_record_refs")),
    )
    _set_selected(selected, "fabric", _as_refs(row.get("source_data_refs")))
    _set_selected(selected, "data_forge", _as_refs(row.get("source_data_refs")))
    if _as_refs(row.get("scholar_refs")):
        _set_selected(selected, "scholar", _as_refs(row.get("scholar_refs")))
    _set_selected(
        selected,
        "foundry",
        _dedupe(
            [
                *_as_refs(row.get("method_refs")),
                *_as_refs(row.get("assumption_gate_refs")),
                *_as_refs(row.get("uncertainty_refs")),
            ]
        ),
    )
    if (
        _as_refs(row.get("ir_analytics_refs"))
        or _as_refs(row.get("ir_certificate_refs"))
        or _as_refs(row.get("negative_certificate_refs"))
    ):
        _set_selected(
            selected,
            "ir_analytics",
            _dedupe(
                [
                    *_as_refs(row.get("ir_analytics_refs")),
                    *_as_refs(row.get("method_output_refs")),
                    *_as_refs(row.get("ir_certificate_refs")),
                    *_as_refs(row.get("uncertainty_refs")),
                    *_as_refs(row.get("proof_composability_refs")),
                ]
            ),
        )
    _set_selected(selected, "options_objectives", _as_refs(row.get("objective_tradeoff_refs")))
    if selected:
        row["selected_producer_refs"] = selected


def _drop_optional_empty_refs(row: dict[str, Any]) -> None:
    for key in _OPTIONAL_EMPTY_REF_KEYS:
        if key in row and not _as_refs(row.get(key)):
            row.pop(key, None)


def _set_selected(
    selected: dict[str, Any],
    key: str,
    refs: Sequence[str],
) -> None:
    if refs and not _as_refs(selected.get(key)):
        selected[key] = list(refs)


def _claim_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in ("claims", "major_claims", "claim_registry_rows"):
        raw = payload.get(key)
        if isinstance(raw, Mapping):
            for claim_id, row in raw.items():
                if isinstance(row, Mapping):
                    merged = dict(row)
                    merged.setdefault("claim_id", str(claim_id))
                    rows.append(merged)
        elif isinstance(raw, Sequence) and not isinstance(raw, str | bytes | bytearray):
            rows.extend(item for item in raw if isinstance(item, Mapping))
    return rows


def _claim_specific_requirement_refs(
    *,
    claim_id: str,
    scenario_evidence_contract: Mapping[str, Any],
) -> list[str]:
    refs: list[str] = []
    for raw in scenario_evidence_contract.get("requirements") or []:
        if not isinstance(raw, Mapping):
            continue
        claim_ids = set(_as_refs(raw.get("claim_ids") or raw.get("claim_refs")))
        if claim_ids and claim_id not in claim_ids:
            continue
        if not claim_ids:
            continue
        refs.extend(
            _as_refs(
                raw.get("requirement_id")
                or raw.get("id")
                or raw.get("requirement_ref")
                or raw.get("ref")
            )
        )
    return _dedupe(refs)


def _refs_for_aliases(payload: Mapping[str, Any], aliases: tuple[str, ...]) -> list[str]:
    refs: list[str] = []
    for key in aliases:
        refs.extend(_as_refs(payload.get(key)))
    graph = payload.get("evidence_graph")
    if isinstance(graph, Mapping):
        for key in aliases:
            refs.extend(_as_refs(graph.get(key)))
    return _dedupe(refs)


def _as_refs(value: object) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    if isinstance(value, Mapping):
        refs: list[str] = []
        for key in (
            "evidence_ref",
            "artifact_ref",
            "cas_ref",
            "ref",
            "id",
            "claim_ref",
            "norm_id",
            "method_id",
            "method_ref",
            "method_output_ref",
            "method_result_ref",
            "result_ref",
            "assumption_gate_ref",
            "gate_ref",
            "uncertainty_envelope_ref",
            "limitation_ref",
            "source_id",
            "candidate_ref",
            "requirement_id",
        ):
            refs.extend(_as_refs(value.get(key)))
        if not refs:
            for item in value.values():
                refs.extend(_as_refs(item))
        return _dedupe(refs)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs: list[str] = []
        for item in value:
            refs.extend(_as_refs(item))
        return _dedupe(refs)
    return []


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")


def _is_major_claim(claim: Mapping[str, Any]) -> bool:
    value = claim.get("major")
    if value is None:
        return True
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() not in {"false", "0", "minor", "no"}
    return bool(value)


def _global_norm_refs(normative_evidence: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(normative_evidence, Mapping):
        return []
    refs: list[str] = []
    for key in ("applied_norms", "candidate_norms", "selected_norms"):
        raw_items = normative_evidence.get(key)
        if not isinstance(raw_items, Sequence) or isinstance(
            raw_items,
            str | bytes | bytearray,
        ):
            continue
        for item in raw_items:
            if not isinstance(item, Mapping):
                continue
            refs.extend(
                _as_refs(item.get("norm_id") or item.get("id") or item.get("artifact_id"))
            )
    return _dedupe(refs)


def _global_method_refs(foundry_method_report: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(foundry_method_report, Mapping):
        return []
    refs: list[str] = []
    for key in ("selected_methods", "rejected_methods", "candidate_methods"):
        raw_items = foundry_method_report.get(key)
        if not isinstance(raw_items, Sequence) or isinstance(
            raw_items,
            str | bytes | bytearray,
        ):
            continue
        for item in raw_items:
            if not isinstance(item, Mapping):
                continue
            refs.extend(
                _refs_for_aliases(
                    item,
                    (
                        "method_id",
                        "id",
                        "method_fqn",
                        "artifact_id",
                        "output_ref",
                        "method_output_ref",
                        "result_ref",
                    ),
                )
            )
    return _dedupe(refs)


def _global_data_refs(fabric_retrieval_trace: Mapping[str, Any] | None) -> list[str]:
    if not isinstance(fabric_retrieval_trace, Mapping):
        return []
    refs: list[str] = []
    for item in fabric_retrieval_trace.get("selected_sources") or []:
        if isinstance(item, Mapping):
            refs.extend(
                _refs_for_aliases(
                    item,
                    (
                        "source_id",
                        "id",
                        "binding_id",
                        "source_family",
                        "artifact_id",
                        "data_snapshot_ref",
                    ),
                )
            )
    return _dedupe(refs)


def _is_generic_method_ref(ref: str) -> bool:
    lowered = _text(ref).casefold()
    return lowered in {"foundry.execute", "execute", "method.execute"} or lowered.endswith(
        ".execute"
    )


def _requires_method_runtime_evidence(ref: str) -> bool:
    lowered = _text(ref).casefold()
    return lowered.startswith(("method-output:", "foundry.", "ir.method."))


def _runtime_event_ref(
    claim: Mapping[str, Any],
    *,
    claim_id: str,
    run_id: str | None,
) -> str:
    explicit = _text(claim.get("runtime_event_ref") or claim.get("diagnostic_event_ref"))
    if explicit:
        return explicit
    run = _slug(run_id or "runtime")
    return f"event://runtime_claim_registry/{run}/{_slug(claim_id)}"


def _stable_claim_ref(claim: Mapping[str, Any]) -> str:
    seed = json.dumps(
        {
            key: value
            for key, value in dict(claim).items()
            if key not in {"claim_ref", "cas_ref", "runtime_event_ref"}
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _safe_ref(value: object) -> str:
    return _text(value)


def _dedupe(values: Sequence[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        deduped.append(text)
    return deduped


def _issue(
    *,
    code: str,
    claim_id: str,
    missing_evidence_type: str,
    message: str,
    next_action: str,
    severity: str = "fail",
    **extra: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "runtime_quality",
        "phase": "runtime_claim_registry",
        "claim_id": claim_id,
        "missing_evidence_type": missing_evidence_type,
        "message": message,
        "next_action": next_action,
        **extra,
    }


def _status_from_issues(issues: Sequence[Mapping[str, Any]]) -> str:
    if any(issue.get("severity") == "fail" for issue in issues):
        return "fail"
    if any(issue.get("severity") == "warn" for issue in issues):
        return "warn"
    return "pass"


def _slug(value: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9._:-]+", "-", _text(value)).strip("-")
    return text or "claim"


def _text(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "REPORT_KIND",
    "REPORT_REF_KEY",
    "SCHEMA_VERSION",
    "RuntimeClaimRegistry",
    "RuntimeClaimRegistryEntry",
    "apply_runtime_claim_registry_to_claim",
    "build_runtime_claim_registry",
    "claim_registry_rows_by_id",
    "normalize_runtime_claim_registry",
    "runtime_claim_registry_issues_for_claims",
]
