"""Claim-bound bridge for proof-carrying IR analytics artifacts."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from polisyos.method_requirement import (
    MethodIdentificationClass,
    MethodValidityRequirementSpec,
    normalize_method_requirements,
)

IR_ANALYTICS_CLAIM_BRIDGE_SCHEMA_VERSION = "policyos.runtime.ir_analytics_claim_bridge.v1"
IR_ANALYTICS_CLAIM_BRIDGE_KIND = "runtime.ir_analytics_claim_bridge"
IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY = "ir_analytics_bridge_ref"

_BLOCKING_PROOF_STATUSES = frozenset(
    {
        "blocked",
        "negative",
        "not_identified",
        "non_identified",
        "refuted",
        "failed",
    }
)
_LIMITING_PROOF_STATUSES = frozenset(
    {
        "bounded",
        "partial",
        "partially_identified",
        "limited",
        "contested",
        "uncertain",
    }
)
_BLOCKING_COMPOSABILITY_STATUSES = frozenset({"rederive"})
_LIMITING_COMPOSABILITY_STATUSES = frozenset({"revalidate", "unknown"})


@dataclass(frozen=True)
class IRAnalyticsClaimBinding:
    """One IR analytics proof bundle bound to a runtime claim id."""

    claim_id: str
    ir_analytics_refs: tuple[str, ...] = ()
    method_output_refs: tuple[str, ...] = ()
    ir_certificate_refs: tuple[str, ...] = ()
    negative_certificate_refs: tuple[str, ...] = ()
    proof_statuses: tuple[str, ...] = ()
    proof_composability_refs: tuple[str, ...] = ()
    proof_composability_statuses: tuple[str, ...] = ()
    uncertainty_refs: tuple[str, ...] = ()
    baseline_refs: tuple[str, ...] = ()
    conflict_refs: tuple[str, ...] = ()
    independence_refs: tuple[str, ...] = ()
    counter_evidence_refs: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()
    blocker_refs: tuple[str, ...] = ()
    diagnostic_refs: tuple[str, ...] = ()
    method_requirement_refs: tuple[str, ...] = ()
    runtime_event_ref: str = ""
    bridge_ref: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable bridge binding."""

        payload = {
            "claim_id": self.claim_id,
            "ir_analytics_refs": list(self.ir_analytics_refs),
            "method_output_refs": list(self.method_output_refs),
            "ir_certificate_refs": list(self.ir_certificate_refs),
            "negative_certificate_refs": list(self.negative_certificate_refs),
            "proof_statuses": list(self.proof_statuses),
            "proof_composability_refs": list(self.proof_composability_refs),
            "proof_composability_statuses": list(self.proof_composability_statuses),
            "uncertainty_refs": list(self.uncertainty_refs),
            "baseline_refs": list(self.baseline_refs),
            "conflict_refs": list(self.conflict_refs),
            "independence_refs": list(self.independence_refs),
            "counter_evidence_refs": list(self.counter_evidence_refs),
            "limitation_refs": list(self.limitation_refs),
            "blocker_refs": list(self.blocker_refs),
            "diagnostic_refs": list(self.diagnostic_refs),
            "method_requirement_refs": list(self.method_requirement_refs),
            "runtime_event_ref": self.runtime_event_ref,
            IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY: self.bridge_ref,
            "metadata": dict(self.metadata),
        }
        return {key: value for key, value in payload.items() if value not in ("", [], {})}


def build_ir_analytics_claim_bridge(
    *,
    claim_bindings: Sequence[Mapping[str, Any]],
    method_requirements: Sequence[MethodValidityRequirementSpec | Mapping[str, Any]] | None = None,
    run_id: str | None = None,
    bridge_ref: str | None = None,
) -> dict[str, Any]:
    """Build a claim-addressable bridge report from IR analytics proof outputs."""

    requirements = normalize_method_requirements(method_requirements)
    bindings = [
        _normalize_binding(dict(binding), index=index, run_id=run_id, bridge_ref=bridge_ref)
        for index, binding in enumerate(claim_bindings or ())
        if isinstance(binding, Mapping)
    ]
    resolved_bridge_ref = bridge_ref or _stable_bridge_ref(
        [binding.to_dict() for binding in bindings],
        run_id=run_id,
    )
    rows = [
        _normalize_binding(
            {**binding.to_dict(), IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY: resolved_bridge_ref},
            index=index,
            run_id=run_id,
            bridge_ref=resolved_bridge_ref,
        ).to_dict()
            for index, binding in enumerate(bindings)
    ]
    rows, requirement_issues, rejected_methods = _apply_method_requirements_to_rows(
        rows,
        requirements=requirements,
    )
    issues = [
        issue
        for row in rows
        for issue in _binding_issues(row)
    ]
    issues.extend(requirement_issues)
    return {
        "schema_version": IR_ANALYTICS_CLAIM_BRIDGE_SCHEMA_VERSION,
        "bridge_kind": IR_ANALYTICS_CLAIM_BRIDGE_KIND,
        "capability_reality_status": "implemented",
        "runtime_authority_envelope": _authority_envelope(),
        IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY: resolved_bridge_ref,
        "status": _status_from_issues(issues),
        "method_requirements": [
            requirement.model_dump(mode="json") for requirement in requirements
        ],
        "claim_bindings": rows,
        "rejected_methods": rejected_methods,
        "issues": issues,
        "summary": _summary(rows, issues),
    }


def normalize_ir_analytics_claim_bridge(
    bridge: Mapping[str, Any] | None,
    *,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    """Normalize a stored IR analytics bridge report."""

    if not isinstance(bridge, Mapping):
        return None
    bridge_ref = _text(bridge.get(IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY) or bridge.get("bridge_ref"))
    rows = [
        _normalize_binding(row, index=index, run_id=run_id, bridge_ref=bridge_ref or None).to_dict()
        for index, row in enumerate(_binding_rows(bridge))
    ]
    if not bridge_ref:
        bridge_ref = _stable_bridge_ref(rows, run_id=run_id)
        rows = [
            _normalize_binding(
                {**row, IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY: bridge_ref},
                index=index,
                run_id=run_id,
                bridge_ref=bridge_ref,
            ).to_dict()
            for index, row in enumerate(rows)
        ]
    issues = [
        issue
        for row in rows
        for issue in _binding_issues(row)
    ]
    return {
        **dict(bridge),
        "schema_version": IR_ANALYTICS_CLAIM_BRIDGE_SCHEMA_VERSION,
        "bridge_kind": IR_ANALYTICS_CLAIM_BRIDGE_KIND,
        "capability_reality_status": "implemented",
        "runtime_authority_envelope": _authority_envelope(),
        IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY: bridge_ref,
        "status": _status_from_issues(issues),
        "claim_bindings": rows,
        "issues": issues,
        "summary": _summary(rows, issues),
    }


def ir_analytics_claim_bindings_by_claim(
    bridge: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return normalized IR analytics bindings keyed by claim id."""

    normalized = normalize_ir_analytics_claim_bridge(bridge)
    if not isinstance(normalized, Mapping):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in normalized.get("claim_bindings") or ():
        if not isinstance(row, Mapping):
            continue
        claim_id = _text(row.get("claim_id"))
        if claim_id:
            result[claim_id] = dict(row)
    return result


def merge_ir_analytics_binding_into_registry_entry(
    registry_entry: Mapping[str, Any],
    binding: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Project one IR analytics binding onto a runtime claim-registry row."""

    row = dict(registry_entry)
    if not isinstance(binding, Mapping):
        return row

    proof_blocks = _binding_blocks_claim(binding)
    _append_refs(row, "ir_analytics_refs", _as_refs(binding.get("ir_analytics_refs")))
    _append_refs(row, "ir_certificate_refs", _as_refs(binding.get("ir_certificate_refs")))
    _append_refs(
        row,
        "negative_certificate_refs",
        _as_refs(binding.get("negative_certificate_refs")),
    )
    if proof_blocks:
        _append_refs(row, "rejected_method_refs", _as_refs(binding.get("method_output_refs")))
    else:
        _append_refs(row, "method_output_refs", _as_refs(binding.get("method_output_refs")))
    for key in (
        "proof_composability_refs",
        "uncertainty_refs",
        "baseline_refs",
        "conflict_refs",
        "independence_refs",
        "counter_evidence_refs",
        "limitation_refs",
        "blocker_refs",
        "diagnostic_refs",
    ):
        _append_refs(row, key, _as_refs(binding.get(key)))

    negative_refs = _as_refs(binding.get("negative_certificate_refs"))
    if negative_refs:
        _append_refs(row, "counter_evidence_refs", negative_refs)
        _append_refs(row, "blocker_refs", negative_refs)
    if _binding_composability_blocks_claim(binding):
        _append_refs(row, "blocker_refs", _as_refs(binding.get("proof_composability_refs")))
    if _binding_limits_claim(binding):
        _append_refs(
            row,
            "limitation_refs",
            _dedupe(
                [
                    *_as_refs(binding.get("limitation_refs")),
                    *_as_refs(binding.get("proof_composability_refs")),
                    *_as_refs(binding.get("uncertainty_refs")),
                ]
            ),
        )
    if _as_refs(binding.get("conflict_refs")):
        _append_refs(row, "counter_evidence_refs", _as_refs(binding.get("conflict_refs")))

    _append_texts(row, "proof_statuses", _as_texts(binding.get("proof_statuses")))
    _append_texts(
        row,
        "proof_composability_statuses",
        _as_texts(binding.get("proof_composability_statuses")),
    )
    bridge_ref = _text(
        binding.get(IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY) or binding.get("bridge_ref")
    )
    if bridge_ref:
        row[IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY] = bridge_ref
    runtime_event_ref = _text(binding.get("runtime_event_ref"))
    if runtime_event_ref:
        row["ir_analytics_runtime_event_ref"] = runtime_event_ref

    selected = dict(row.get("selected_producer_refs") or {})
    ir_selected = _dedupe(
        [
            *_as_refs(row.get("ir_analytics_refs")),
            *_as_refs(row.get("method_output_refs")),
            *_as_refs(row.get("ir_certificate_refs")),
            *_as_refs(row.get("uncertainty_refs")),
            *_as_refs(row.get("proof_composability_refs")),
        ]
    )
    if ir_selected:
        selected["ir_analytics"] = ir_selected
        row["selected_producer_refs"] = selected
    return row


def ir_analytics_bridge_issues_for_claims(
    *,
    claims: Sequence[Mapping[str, Any]] | None,
    bridge: Mapping[str, Any] | None,
    registry_rows: Sequence[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Return fail-closed issues for IR-required claims missing bridge bindings."""

    normalized_bridge = normalize_ir_analytics_claim_bridge(bridge)
    bindings_by_claim = ir_analytics_claim_bindings_by_claim(normalized_bridge)
    rows_by_claim = {
        _text(row.get("claim_id")): row
        for row in registry_rows
        if isinstance(row, Mapping) and _text(row.get("claim_id"))
    }
    issues = [
        dict(issue)
        for issue in (normalized_bridge or {}).get("issues", ())
        if isinstance(issue, Mapping)
    ]
    for index, claim in enumerate(claims or ()):
        if not isinstance(claim, Mapping) or not _requires_ir_analytics(claim):
            continue
        claim_id = _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")
        if claim_id in bindings_by_claim or _row_has_ir_analytics_bridge(
            rows_by_claim.get(claim_id),
        ):
            continue
        issues.append(
            _issue(
                code="runtime_claim_registry_ir_analytics_bridge_missing",
                severity="fail",
                claim_id=claim_id,
                missing_evidence_type="ir_analytics_bridge",
                message=(
                    f"Claim {claim_id} requires proof-carrying IR analytics, but no "
                    "claim-bound IR analytics bridge binding is present."
                ),
                next_action=(
                    "Bind IR certificates, proof status, uncertainty, conflicts, "
                    "negative certificates, and proof-composability refs to this "
                    "RuntimeClaimRegistry entry."
                ),
            )
        )
    return issues


def _normalize_binding(
    row: Mapping[str, Any],
    *,
    index: int,
    run_id: str | None,
    bridge_ref: str | None,
) -> IRAnalyticsClaimBinding:
    claim_id = _text(row.get("claim_id") or row.get("id") or f"claim_{index + 1}")
    proof_composability_statuses = _dedupe_texts(
        [
            *_as_texts(row.get("proof_composability_statuses")),
            *_as_texts(row.get("proof_composability_status")),
            *_status_from_nested(row.get("proof_composability")),
            *_status_from_nested(row.get("proof_composability_certificate")),
        ]
    )
    proof_statuses = _dedupe_texts(
        [
            *_as_texts(row.get("proof_statuses")),
            *_as_texts(row.get("proof_status")),
            *_as_texts(row.get("status") if row.get("status") != "pass" else None),
            *_status_from_nested(row.get("certificate")),
            *_status_from_nested(row.get("analytics_result")),
        ]
    )
    analytics_refs = _refs_for_aliases(
        row,
        (
            "ir_analytics_refs",
            "analytics_refs",
            "analytics_ref",
            "ir_result_refs",
            "ir_result_ref",
            "profile_refs",
            "profile_ref",
        ),
    )
    certificate_refs = _refs_for_aliases(
        row,
        (
            "ir_certificate_refs",
            "certificate_refs",
            "certificate_ref",
            "dual_certificate_refs",
            "recoverability_certificate_refs",
            "transportability_result_refs",
            "path_specific_certificate_refs",
            "certified_tightening_refs",
        ),
    )
    negative_refs = _refs_for_aliases(
        row,
        (
            "negative_certificate_refs",
            "negative_certificate_ref",
            "non_identification_refs",
            "blocked_certificate_refs",
        ),
    )
    runtime_event_ref = _text(row.get("runtime_event_ref") or row.get("diagnostic_event_ref"))
    if not runtime_event_ref:
        runtime_event_ref = (
            f"event://ir_analytics_claim_bridge/{_slug(run_id or 'runtime')}/{_slug(claim_id)}"
        )
    return IRAnalyticsClaimBinding(
        claim_id=claim_id,
        ir_analytics_refs=tuple(analytics_refs),
        method_output_refs=tuple(
            _refs_for_aliases(
                row,
                (
                    "method_output_refs",
                    "method_output_ref",
                    "analysis_output_refs",
                    "result_refs",
                    "result_ref",
                    "method_refs",
                ),
            )
        ),
        ir_certificate_refs=tuple(certificate_refs),
        negative_certificate_refs=tuple(negative_refs),
        proof_statuses=tuple(proof_statuses),
        proof_composability_refs=tuple(
            _refs_for_aliases(
                row,
                (
                    "proof_composability_refs",
                    "proof_composability_ref",
                    "composability_certificate_refs",
                    "composability_certificate_ref",
                ),
            )
        ),
        proof_composability_statuses=tuple(proof_composability_statuses),
        uncertainty_refs=tuple(
            _refs_for_aliases(
                row,
                (
                    "uncertainty_refs",
                    "uncertainty_ref",
                    "uncertainty_envelope_refs",
                    "uncertainty_envelope_ref",
                    "residual_uncertainty_refs",
                ),
            )
        ),
        baseline_refs=tuple(
            _refs_for_aliases(
                row,
                ("baseline_refs", "baseline_ref", "alternative_refs", "comparison_refs"),
            )
        ),
        conflict_refs=tuple(
            _refs_for_aliases(
                row,
                ("conflict_refs", "conflict_ref", "counter_conflict_refs"),
            )
        ),
        independence_refs=tuple(
            _refs_for_aliases(
                row,
                ("independence_refs", "independence_ref", "independence_map_refs"),
            )
        ),
        counter_evidence_refs=tuple(
            _refs_for_aliases(
                row,
                (
                    "counter_evidence_refs",
                    "counterevidence_refs",
                    "disconfirming_refs",
                    "rebuttal_refs",
                ),
            )
        ),
        limitation_refs=tuple(
            _refs_for_aliases(
                row,
                ("limitation_refs", "accepted_limitation_refs", "deficit_refs"),
            )
        ),
        blocker_refs=tuple(
            _refs_for_aliases(
                row,
                ("blocker_refs", "typed_blocker_refs", "blocking_refs"),
            )
        ),
        diagnostic_refs=tuple(
            _refs_for_aliases(
                row,
                ("diagnostic_refs", "diagnostic_ref", "source_status_refs"),
            )
        ),
        method_requirement_refs=tuple(
            _refs_for_aliases(
                row,
                (
                    "method_requirement_refs",
                    "method_requirement_ref",
                    "method_validity_requirement_refs",
                ),
            )
        ),
        runtime_event_ref=runtime_event_ref,
        bridge_ref=_text(row.get(IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY) or bridge_ref),
        metadata=_metadata(row),
    )


def _binding_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in ("claim_bindings", "bindings", "claims", "claim_registry_bindings"):
        raw = payload.get(key)
        if isinstance(raw, Mapping):
            for claim_id, value in raw.items():
                if isinstance(value, Mapping):
                    rows.append({"claim_id": str(claim_id), **dict(value)})
        elif isinstance(raw, Sequence) and not isinstance(raw, str | bytes | bytearray):
            rows.extend(item for item in raw if isinstance(item, Mapping))
    return rows


def _binding_issues(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    claim_id = _text(row.get("claim_id"))
    issues: list[dict[str, Any]] = []
    if not claim_id:
        issues.append(
            _issue(
                code="runtime_claim_registry_ir_analytics_claim_id_missing",
                severity="fail",
                claim_id="",
                missing_evidence_type="claim_id",
                message="IR analytics claim bridge binding has no claim_id.",
                next_action="Bind each IR analytics artifact to a concrete ClaimRecord id.",
            )
        )
    if not any(
        _as_refs(row.get(key))
        for key in (
            "ir_analytics_refs",
            "method_output_refs",
            "ir_certificate_refs",
            "negative_certificate_refs",
            "proof_composability_refs",
            "uncertainty_refs",
        )
    ):
        issues.append(
            _issue(
                code="runtime_claim_registry_ir_analytics_proof_refs_missing",
                severity="fail",
                claim_id=claim_id,
                missing_evidence_type="ir_analytics_proof_ref",
                message=(
                    f"IR analytics bridge binding {claim_id} carries no proof, "
                    "certificate, method output, or uncertainty refs."
                ),
                next_action=(
                    "Attach the IR analytics artifact refs instead of using the "
                    "bridge as an empty marker."
                ),
            )
        )
    if _binding_blocks_claim(row):
        issues.append(
            _issue(
                code="runtime_claim_registry_ir_analytics_blocked",
                severity="fail",
                claim_id=claim_id,
                missing_evidence_type="ir_analytics_blocker",
                message=(
                    f"IR analytics binding for claim {claim_id} carries a blocking "
                    "proof status or negative certificate."
                ),
                next_action=(
                    "Keep the claim blocked, narrow the claim, collect new evidence, "
                    "or rerun the appropriate IR proof kernel."
                ),
                blocker_refs=_dedupe(
                    [
                        *_as_refs(row.get("blocker_refs")),
                        *_as_refs(row.get("negative_certificate_refs")),
                        *(
                            _as_refs(row.get("proof_composability_refs"))
                            if _binding_composability_blocks_claim(row)
                            else []
                        ),
                    ]
                ),
            )
        )
    elif _binding_limits_claim(row):
        issues.append(
            _issue(
                code="runtime_claim_registry_ir_analytics_limited",
                severity="warn",
                claim_id=claim_id,
                missing_evidence_type="ir_analytics_limitation",
                message=(
                    f"IR analytics binding for claim {claim_id} is limited, contested, "
                    "or requires proof revalidation."
                ),
                next_action=(
                    "Carry the limitation into claim readiness, public projection, "
                    "and closeout review."
                ),
                limitation_refs=_dedupe(
                    [
                        *_as_refs(row.get("limitation_refs")),
                        *_as_refs(row.get("proof_composability_refs")),
                        *_as_refs(row.get("uncertainty_refs")),
                    ]
                ),
            )
        )
    return issues


def _binding_blocks_claim(row: Mapping[str, Any]) -> bool:
    return bool(
        _as_refs(row.get("negative_certificate_refs"))
        or _blocking_status(_as_texts(row.get("proof_statuses")))
        or _binding_composability_blocks_claim(row)
    )


def _binding_composability_blocks_claim(row: Mapping[str, Any]) -> bool:
    return _blocking_status(
        _as_texts(row.get("proof_composability_statuses")),
        blocking_statuses=_BLOCKING_COMPOSABILITY_STATUSES,
    )


def _binding_limits_claim(row: Mapping[str, Any]) -> bool:
    return bool(
        _blocking_status(
            _as_texts(row.get("proof_statuses")),
            blocking_statuses=_LIMITING_PROOF_STATUSES,
        )
        or _blocking_status(
            _as_texts(row.get("proof_composability_statuses")),
            blocking_statuses=_LIMITING_COMPOSABILITY_STATUSES,
        )
    )


def _blocking_status(
    statuses: Sequence[str],
    *,
    blocking_statuses: frozenset[str] = _BLOCKING_PROOF_STATUSES,
) -> bool:
    return any(_status_token(status) in blocking_statuses for status in statuses)


def _requires_ir_analytics(claim: Mapping[str, Any]) -> bool:
    if _truthy(
        claim.get("requires_ir_analytics")
        or claim.get("ir_analytics_required")
        or claim.get("requires_proof_carrying_ir")
    ):
        return True
    for key in (
        "method_authority_source",
        "producer",
        "required_producer",
        "required_method_authority",
    ):
        if "ir_analytics" in _text(claim.get(key)).casefold():
            return True
    return any(
        ref.casefold() == "ir_analytics"
        for ref in _as_refs(claim.get("required_producer_refs"))
    )


def _row_has_ir_analytics_bridge(row: Mapping[str, Any] | None) -> bool:
    if not isinstance(row, Mapping):
        return False
    return bool(
        _as_refs(row.get("ir_analytics_refs"))
        or _as_refs(row.get("ir_certificate_refs"))
        or _as_refs(row.get("negative_certificate_refs"))
        or _text(row.get(IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY))
    )


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
            "artifact_ref",
            "evidence_ref",
            "cas_ref",
            "ref",
            "id",
            "artifact_id",
            "certificate_ref",
            "certificate_id",
            "result_ref",
            "method_output_ref",
            "analytics_ref",
        ):
            refs.extend(_as_refs(value.get(key)))
        return _dedupe(refs)
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs: list[str] = []
        for item in value:
            refs.extend(_as_refs(item))
        return _dedupe(refs)
    return []


def _as_texts(value: object) -> list[str]:
    if isinstance(value, str):
        text = _status_token(value)
        return [text] if text else []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return _dedupe_texts(_status_token(item) for item in value)
    return []


def _status_from_nested(value: object) -> list[str]:
    if not isinstance(value, Mapping):
        if hasattr(value, "model_dump"):
            dumped = value.model_dump(mode="json")
            return _status_from_nested(dumped)
        return []
    return _as_texts(
        value.get("status")
        or value.get("proof_status")
        or value.get("composability_status")
        or value.get("identification_status")
    )


def _metadata(row: Mapping[str, Any]) -> dict[str, Any]:
    metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), Mapping) else {}
    for key in ("analytics_kind", "method_family", "identification_strategy", "checked_query"):
        value = _text(row.get(key))
        if value:
            metadata[key] = value
    return metadata


def _append_refs(row: dict[str, Any], key: str, refs: Sequence[str]) -> None:
    merged = _dedupe([*_as_refs(row.get(key)), *refs])
    if merged:
        row[key] = merged


def _append_texts(row: dict[str, Any], key: str, values: Sequence[str]) -> None:
    merged = _dedupe_texts([*_as_texts(row.get(key)), *values])
    if merged:
        row[key] = merged


def _apply_method_requirements_to_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    requirements: Sequence[MethodValidityRequirementSpec],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not requirements:
        return [dict(row) for row in rows], [], []
    rows_by_claim = {_text(row.get("claim_id")): dict(row) for row in rows}
    issues: list[dict[str, Any]] = []
    rejected_methods: list[dict[str, Any]] = []

    for requirement in requirements:
        row = rows_by_claim.get(requirement.claim_id)
        if row is None:
            issues.append(
                _issue(
                    code="ir_analytics_method_requirement_binding_missing",
                    severity="fail",
                    claim_id=requirement.claim_id,
                    missing_evidence_type="method_requirement_binding",
                    message=(
                        f"Method requirement {requirement.requirement_id} has no "
                        f"IR analytics binding for claim {requirement.claim_id}."
                    ),
                    next_action=(
                        "Bind the MethodValidityRequirementSpec to IR certificates, "
                        "method outputs, uncertainty refs, or a negative certificate."
                    ),
                    method_requirement_ref=requirement.requirement_id,
                )
            )
            continue
        _append_refs(row, "method_requirement_refs", [requirement.requirement_id])
        requirement_issues, requirement_rejections = _method_requirement_issues(
            row,
            requirement,
        )
        issues.extend(requirement_issues)
        rejected_methods.extend(requirement_rejections)
        rows_by_claim[requirement.claim_id] = row

    ordered = []
    for row in rows:
        claim_id = _text(row.get("claim_id"))
        ordered.append(rows_by_claim.get(claim_id, dict(row)))
    return ordered, issues, rejected_methods


def _method_requirement_issues(
    row: Mapping[str, Any],
    requirement: MethodValidityRequirementSpec,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    rejected_methods: list[dict[str, Any]] = []
    claim_id = requirement.claim_id
    method_output_refs = _as_refs(row.get("method_output_refs"))

    if requirement.requires_negative_certificate:
        if not _as_refs(row.get("negative_certificate_refs")):
            issues.append(
                _issue(
                    code="ir_analytics_method_requirement_negative_certificate_missing",
                    severity="fail",
                    claim_id=claim_id,
                    missing_evidence_type="negative_certificate_ref",
                    message=(
                        f"Method requirement {requirement.requirement_id} requires a "
                        f"negative certificate for claim {claim_id}."
                    ),
                    next_action=(
                        "Emit or bind the IR negative certificate instead of using "
                        "positive method output."
                    ),
                    method_requirement_ref=requirement.requirement_id,
                )
            )
        return issues, rejected_methods

    if requirement.requires_method_output and not method_output_refs:
        issues.append(
            _issue(
                code="ir_analytics_method_requirement_method_output_missing",
                severity="fail",
                claim_id=claim_id,
                missing_evidence_type="method_output_ref",
                message=(
                    f"Method requirement {requirement.requirement_id} requires method "
                    f"output refs for claim {claim_id}."
                ),
                next_action="Bind executed method output refs before claim registry consumption.",
                method_requirement_ref=requirement.requirement_id,
            )
        )
    if (
        requirement.identification_class is MethodIdentificationClass.POINT
        and not _as_refs(row.get("ir_certificate_refs"))
    ):
        issues.append(
            _issue(
                code="ir_analytics_method_requirement_certificate_missing",
                severity="fail",
                claim_id=claim_id,
                missing_evidence_type="ir_certificate_ref",
                message=(
                    f"Method requirement {requirement.requirement_id} requires an IR "
                    f"certificate for point identification on claim {claim_id}."
                ),
                next_action="Attach identification or proof certificate refs.",
                method_requirement_ref=requirement.requirement_id,
            )
        )
    if requirement.requires_uncertainty_envelope and not _as_refs(row.get("uncertainty_refs")):
        issues.append(
            _issue(
                code="ir_analytics_method_requirement_uncertainty_missing",
                severity="fail",
                claim_id=claim_id,
                missing_evidence_type="uncertainty_ref",
                message=(
                    f"Method requirement {requirement.requirement_id} requires "
                    f"uncertainty or bounds refs for claim {claim_id}."
                ),
                next_action="Attach uncertainty envelope, bounds, or residual uncertainty refs.",
                method_requirement_ref=requirement.requirement_id,
            )
        )
        rejected_methods.append(
            {
                "claim_id": claim_id,
                "method_output_refs": method_output_refs,
                "method_requirement_ref": requirement.requirement_id,
                "reason_code": "ir_requirement_uncertainty_missing",
                "reason": (
                    f"Method requirement {requirement.requirement_id} requires "
                    f"uncertainty or bounds refs for claim {claim_id}."
                ),
            }
        )
    if requirement.requires_limitation_refs and not _as_refs(row.get("limitation_refs")):
        issues.append(
            _issue(
                code="ir_analytics_method_requirement_limitation_missing",
                severity="fail",
                claim_id=claim_id,
                missing_evidence_type="limitation_ref",
                message=(
                    f"Method requirement {requirement.requirement_id} requires "
                    f"method limitations for claim {claim_id}."
                ),
                next_action="Attach transportability, scope, or proof limitation refs.",
                method_requirement_ref=requirement.requirement_id,
            )
        )
    return issues, rejected_methods


def _summary(
    rows: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    return {
        "binding_count": len(rows),
        "claim_count": len(
            {_text(row.get("claim_id")) for row in rows if _text(row.get("claim_id"))},
        ),
        "blocked_claim_count": sum(1 for row in rows if _binding_blocks_claim(row)),
        "limited_claim_count": sum(
            1 for row in rows if _binding_limits_claim(row) and not _binding_blocks_claim(row)
        ),
        "issue_count": len(issues),
        "certificate_ref_count": sum(len(_as_refs(row.get("ir_certificate_refs"))) for row in rows),
        "negative_certificate_ref_count": sum(
            len(_as_refs(row.get("negative_certificate_refs"))) for row in rows
        ),
        "proof_composability_ref_count": sum(
            len(_as_refs(row.get("proof_composability_refs"))) for row in rows
        ),
        "uncertainty_ref_count": sum(len(_as_refs(row.get("uncertainty_refs"))) for row in rows),
        "method_requirement_binding_count": sum(
            len(_as_refs(row.get("method_requirement_refs"))) for row in rows
        ),
    }


def _issue(
    *,
    code: str,
    severity: str,
    claim_id: str,
    missing_evidence_type: str,
    message: str,
    next_action: str,
    **extra: object,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "layer": "runtime_quality",
        "phase": "ir_analytics_claim_bridge",
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


def _stable_bridge_ref(rows: Sequence[Mapping[str, Any]], *, run_id: str | None) -> str:
    seed = json.dumps(
        {"run_id": run_id or "", "claim_bindings": list(rows)},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "sha256:" + hashlib.sha256(seed.encode("utf-8")).hexdigest()


def _authority_envelope() -> dict[str, tuple[str, ...] | str]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "authoritative_for": (
            "claim_bound_ir_proof_status",
            "ir_certificate_binding",
            "negative_certificate_blockers",
            "proof_composability_refs",
            "uncertainty_envelope_refs",
        ),
        "may_not_use_for": (
            "legal_authority",
            "source_family_satisfaction",
            "method_validity",
            "participation_representativeness",
            "claim_support_without_claim_registry_bridge",
            "closeout_pass_without_claim_registry_bridge",
        ),
    }


def _truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() not in {"", "0", "false", "no", "off"}
    return bool(value)


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _text(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _dedupe_texts(values: Sequence[object]) -> list[str]:
    return _dedupe([_status_token(value) for value in values])


def _status_token(value: object) -> str:
    return _text(value).casefold().replace("-", "_").replace(" ", "_")


def _slug(value: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9._:-]+", "-", _text(value)).strip("-")
    return text or "claim"


def _text(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "IR_ANALYTICS_CLAIM_BRIDGE_KIND",
    "IR_ANALYTICS_CLAIM_BRIDGE_REF_KEY",
    "IR_ANALYTICS_CLAIM_BRIDGE_SCHEMA_VERSION",
    "IRAnalyticsClaimBinding",
    "build_ir_analytics_claim_bridge",
    "ir_analytics_bridge_issues_for_claims",
    "ir_analytics_claim_bindings_by_claim",
    "merge_ir_analytics_binding_into_registry_entry",
    "normalize_ir_analytics_claim_bridge",
]
