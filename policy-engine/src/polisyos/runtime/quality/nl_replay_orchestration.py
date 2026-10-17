"""NL/replay orchestration continuity records for Policy Design Case runtime paths."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from polisyos.runtime.quality.public_export import PUBLIC_EXPORT_SCHEMA_VERSION

NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION = "policyos.runtime.nl_replay_orchestration_continuity.v1"
NL_REPLAY_ORCHESTRATION_FILE_REF = "quality_evidence/runtime_orchestration_continuity.json"
NL_REPLAY_ORCHESTRATION_RECORD_KEY = "runtime_orchestration_continuity"

_DEFAULT_REQUIRED_SURFACES = (
    "request_context",
    "workflow_state",
    "job_progress",
    "replay_manifest",
    "bundle",
    "inspection",
    "readiness",
    "export",
)
_REQUIRED_REF_FAMILIES = (
    "carrier_ref",
    "concept_spine_ref",
    "jurisdiction_spine_ref",
    "runtime_claim_registry_ref",
    "producer_binding_refs",
)
_SOURCE_SURFACE_NAMES = (
    "request_context",
    "workflow_state",
    "job_progress",
    "quality_evidence",
)
_OBSERVATION_SURFACE_NAMES = (
    "replay_manifest",
    "bundle",
    "inspection",
    "readiness",
    "export",
)
_OBSERVED_REF_FAMILIES = (
    "carrier_refs",
    "concept_spine_refs",
    "jurisdiction_spine_refs",
    "producer_handshake_ledger_refs",
    "runtime_claim_registry_refs",
    "producer_binding_refs",
)
_SINGLETON_REF_FAMILIES = (
    "carrier_ref",
    "concept_spine_ref",
    "jurisdiction_spine_ref",
    "producer_handshake_ledger_ref",
    "runtime_claim_registry_ref",
)
_REFERENCE_VALUE_KEYS = (
    "ref",
    "id",
    "artifact_ref",
    "cas_ref",
    "claim_ref",
    "runtime_event_ref",
    "binding_id",
    "handshake_id",
    "handoff_id",
    "producer_handshake_ledger_ref",
)


def build_nl_replay_orchestration_continuity(
    *,
    request_context: Mapping[str, Any] | None = None,
    workflow_state: Mapping[str, Any] | None = None,
    job_progress: Mapping[str, Any] | None = None,
    replay_manifest: Mapping[str, Any] | None = None,
    bundle_payload: Mapping[str, Any] | None = None,
    quality_evidence: Mapping[str, Any] | None = None,
    inspection_report: Mapping[str, Any] | None = None,
    readiness_payload: Mapping[str, Any] | None = None,
    export_payload: Mapping[str, Any] | None = None,
    required_surfaces: Sequence[str] = _DEFAULT_REQUIRED_SURFACES,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the W4.A continuity record shared by live, replay, and export paths.

    The record is a diagnostic bridge artifact. Its selected caller/loaded input
    surfaces (request context, workflow state, job progress, and quality evidence)
    provide a ``consumer_asserted`` candidate ref basis; they are not admitted as
    authority. Replay manifest, bundle, inspection, readiness, and export surfaces
    are observations. Their refs remain visible in ``surface_coverage`` and are
    compared with the source candidates, but cannot seed required refs or the
    record's summarized refs. Valid embedded continuity records expose summary refs
    only as observations; they never supply a later source basis or producer provenance.
    Typed public-export bundles and projection-only objects on source surfaces are
    refused. Neither record nor export is producer-domain evidence or can satisfy
    authority, scorecard, approval, or public-projection gates by itself.
    """

    surfaces = {
        "request_context": request_context,
        "workflow_state": workflow_state,
        "job_progress": job_progress,
        "replay_manifest": replay_manifest,
        "bundle": bundle_payload,
        "quality_evidence": quality_evidence,
        "inspection": inspection_report,
        "readiness": readiness_payload,
        "export": export_payload,
    }
    input_findings: list[dict[str, Any]] = []
    collected_by_surface = {
        name: _collect_surface_refs(name, payload, findings=input_findings)
        for name, payload in surfaces.items()
        if isinstance(payload, Mapping) and payload
    }
    source_refs = _combine_refs(
        refs for name, refs in collected_by_surface.items() if name in _SOURCE_SURFACE_NAMES
    )
    observation_refs = {
        name: collected_by_surface.get(name, _empty_collected_refs())
        for name in _OBSERVATION_SURFACE_NAMES
    }
    findings = [
        *_surface_findings(surfaces, collected_by_surface, required_surfaces),
        *input_findings,
        *_required_ref_findings(source_refs),
        *_singleton_mismatch_findings(source_refs),
        *_observation_ref_findings(source_refs, observation_refs),
    ]
    combined = source_refs
    status = "fail" if findings else "pass"
    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)

    payload = {
        "schema_version": NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION,
        "record_family": "nl_replay_orchestration_continuity.v1",
        "status": status,
        "generated_at": timestamp.astimezone(UTC).replace(microsecond=0).isoformat(),
        "carrier_ref": _first(combined["carrier_refs"]),
        "parent_spine_ref": _first(combined["parent_spine_refs"]),
        "concept_spine_ref": _first(combined["concept_spine_refs"]),
        "jurisdiction_spine_ref": _first(combined["jurisdiction_spine_refs"]),
        "producer_spine_context_ref": _first(combined["producer_spine_context_refs"]),
        "producer_handshake_ledger_ref": _first(combined["producer_handshake_ledger_refs"]),
        "runtime_claim_registry_ref": _first(combined["runtime_claim_registry_refs"]),
        "scenario_contract_refs": list(combined["scenario_contract_refs"]),
        "handoff_refs": list(combined["handoff_refs"]),
        "producer_handshake_refs": list(combined["producer_handshake_refs"]),
        "producer_binding_refs": list(combined["producer_binding_refs"]),
        "claim_refs": list(combined["claim_refs"]),
        "bridge_authority_refs": list(combined["bridge_authority_refs"]),
        "continuity_ref": NL_REPLAY_ORCHESTRATION_FILE_REF,
        "authority_boundary": {
            "authority_role": "diagnostic_only",
            "provenance_kind": "runtime_emitted",
            "authoritative_for": ["boundary_continuity"],
            "may_not_use_for": [
                "producer_domain_truth",
                "scorecard_authority",
                "approval_authority",
                "runtime_closeout_authority",
                "public_projection_authority",
                "evidence_strength",
            ],
        },
        "surface_coverage": _surface_coverage(collected_by_surface),
        "summary": {
            "surface_count": len(collected_by_surface),
            "required_surface_count": len(tuple(required_surfaces)),
            "finding_count": len(findings),
            "handoff_ref_count": len(combined["handoff_refs"]),
            "producer_handshake_ref_count": len(combined["producer_handshake_refs"]),
            "producer_binding_ref_count": len(combined["producer_binding_refs"]),
            "claim_ref_count": len(combined["claim_refs"]),
        },
        "findings": findings,
    }
    payload["continuity_fingerprint"] = _stable_ref(
        {key: value for key, value in payload.items() if key != "continuity_fingerprint"}
    )
    return payload


def validate_nl_replay_orchestration_continuity(
    payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a normalized continuity record and preserve existing findings."""

    record = dict(payload)
    if record.get("schema_version") != NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION:
        record.setdefault("findings", [])
        record["findings"] = [
            *[item for item in record.get("findings", []) if isinstance(item, Mapping)],
            _finding(
                "nl_replay_orchestration_schema_version_invalid",
                "Runtime orchestration continuity schema_version is invalid.",
                field="schema_version",
            ),
        ]
        record["status"] = "fail"
        record["schema_version"] = NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION
    if record.get("status") not in {"pass", "fail"}:
        record["status"] = "fail"
        record.setdefault("findings", [])
        record["findings"] = [
            *[item for item in record.get("findings", []) if isinstance(item, Mapping)],
            _finding(
                "nl_replay_orchestration_status_invalid",
                "Runtime orchestration continuity status must be pass or fail.",
                field="status",
            ),
        ]
    return record


def extract_nl_replay_orchestration_continuity(
    quality_evidence: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return a stored W4.A continuity record from a quality-evidence payload."""

    if not isinstance(quality_evidence, Mapping):
        return None
    value = quality_evidence.get(NL_REPLAY_ORCHESTRATION_RECORD_KEY)
    if isinstance(value, Mapping):
        return validate_nl_replay_orchestration_continuity(value)
    return None


@dataclass(frozen=True)
class _FilteredRefTree:
    """Record accepted subtree shape before applying the canonical ref grammar."""

    accepted: bool
    included: bool
    value: object
    claim_registry_fallback_candidates: tuple[Mapping[str, Any], ...]


def _collect_surface_refs(
    surface_name: str,
    payload: Mapping[str, Any],
    *,
    findings: list[dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    outcome = _filter_ref_tree(
        payload,
        path=f"$.{surface_name}",
        surface_name=surface_name,
        findings=findings,
    )
    collected = _empty_collected_refs()
    if surface_name in _SOURCE_SURFACE_NAMES and not outcome.accepted:
        # A source surface is atomic: a rejected descendant invalidates every ref.
        return dict.fromkeys(collected, ())
    if outcome.included:
        _collect_accepted_refs(
            outcome.value,
            collected,
            path=f"$.{surface_name}",
            surface_name=surface_name,
        )
    for candidate in outcome.claim_registry_fallback_candidates:
        _collect_claim_registry_fallback(candidate, collected)
    return {key: tuple(sorted(values)) for key, values in collected.items()}


def _empty_collected_refs() -> dict[str, set[str]]:
    return {
        "carrier_refs": set(),
        "parent_spine_refs": set(),
        "concept_spine_refs": set(),
        "jurisdiction_spine_refs": set(),
        "producer_spine_context_refs": set(),
        "producer_handshake_ledger_refs": set(),
        "runtime_claim_registry_refs": set(),
        "scenario_contract_refs": set(),
        "handoff_refs": set(),
        "producer_handshake_refs": set(),
        "producer_binding_refs": set(),
        "claim_refs": set(),
        "bridge_authority_refs": set(),
    }


def _filter_ref_tree(
    value: object,
    *,
    path: str,
    surface_name: str,
    findings: list[dict[str, Any]],
) -> _FilteredRefTree:
    """Validate the entire tree before refs are extracted from accepted portions."""

    if isinstance(value, Mapping):
        is_continuity_record = _looks_like_continuity_record(value)
        if is_continuity_record:
            if surface_name in _SOURCE_SURFACE_NAMES:
                if value.get("authority_role") == "projection_only":
                    findings.append(
                        _finding(
                            "nl_replay_orchestration_projection_on_source_surface",
                            "A projection-only continuity object appeared on a source surface.",
                            surface=surface_name,
                            field="runtime_orchestration_continuity",
                        )
                    )
                    return _FilteredRefTree(False, False, None, ())
                issue = _continuity_record_issue(value)
            else:
                issue = (
                    None
                    if _is_public_continuity_projection(value)
                    else _continuity_record_issue(value)
                )
            if issue is not None:
                findings.append(
                    _finding(
                        "nl_replay_orchestration_embedded_record_invalid",
                        issue,
                        surface=surface_name,
                        field="runtime_orchestration_continuity",
                    )
                )
                return _FilteredRefTree(False, False, None, ())
        if surface_name in _SOURCE_SURFACE_NAMES and _is_projection_only_payload(value):
            findings.append(
                _finding(
                    "nl_replay_orchestration_projection_on_source_surface",
                    "A projection-only payload appeared on a source surface.",
                    surface=surface_name,
                    field="candidate_projection",
                )
            )
            return _FilteredRefTree(False, False, None, ())

        if is_continuity_record:
            if surface_name in _SOURCE_SURFACE_NAMES:
                # The canonical source walker treats a validated record as one
                # diagnostic boundary and does not mine its descendants.
                return _FilteredRefTree(True, True, dict(value), ())
            filtered_record = dict(value)
            accepted = True
            for field in _CONTINUITY_SUMMARY_REF_FAMILIES:
                if field not in value:
                    continue
                child = _filter_ref_tree(
                    value[field],
                    path=f"{path}.{field}",
                    surface_name=surface_name,
                    findings=findings,
                )
                if child.included:
                    filtered_record[field] = child.value
                else:
                    filtered_record.pop(field, None)
                if not child.accepted:
                    accepted = False
            # The canonical record collector stops here, so no nested registry
            # is eligible for fallback through a continuity envelope.
            return _FilteredRefTree(accepted, True, filtered_record, ())

        filtered: dict[object, object] = {}
        accepted = True
        child_candidates: list[Mapping[str, Any]] = []
        for raw_key, item in value.items():
            key = str(raw_key)
            child = _filter_ref_tree(
                item,
                path=f"{path}.{key}",
                surface_name=surface_name,
                findings=findings,
            )
            if child.included:
                filtered[raw_key] = child.value
            if not child.accepted:
                accepted = False
            child_candidates.extend(child.claim_registry_fallback_candidates)

        candidates: list[Mapping[str, Any]] = []
        # A continuity record is an extraction boundary in the canonical walker;
        # registries hidden inside it were never fallback sources.
        if (
            not is_continuity_record
            and accepted
            and "claim_registry" in str(value.get("schema_version") or "")
        ):
            candidates.append(filtered)
        if not is_continuity_record:
            candidates.extend(child_candidates)
        return _FilteredRefTree(accepted, True, filtered, tuple(candidates))

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        filtered_items: list[object] = []
        accepted = True
        child_candidates = []
        for index, item in enumerate(value):
            child = _filter_ref_tree(
                item,
                path=f"{path}[{index}]",
                surface_name=surface_name,
                findings=findings,
            )
            if child.included:
                filtered_items.append(child.value)
            if not child.accepted:
                accepted = False
            child_candidates.extend(child.claim_registry_fallback_candidates)
        filtered_value: object = (
            tuple(filtered_items) if isinstance(value, tuple) else filtered_items
        )
        return _FilteredRefTree(accepted, True, filtered_value, tuple(child_candidates))

    return _FilteredRefTree(True, True, value, ())


def _collect_accepted_refs(
    value: object,
    collected: dict[str, set[str]],
    *,
    path: str,
    surface_name: str,
) -> None:
    """Apply the established ref-family routing to an already filtered tree."""

    if isinstance(value, Mapping):
        if _looks_like_continuity_record(value):
            if surface_name in _SOURCE_SURFACE_NAMES:
                # The fixed file ref is diagnostic lineage only.
                collected["handoff_refs"].update(_refs_from_value(value.get("continuity_ref")))
            else:
                # Observer summary refs remain visible but cannot seed source refs.
                collected["handoff_refs"].update(_refs_from_value(value.get("continuity_ref")))
                _collect_continuity_summary_refs(value, collected)
            return
        schema_version = _text(value.get("schema_version"))
        component_id = value.get("component_id")
        if component_id == NL_REPLAY_ORCHESTRATION_RECORD_KEY:
            collected["handoff_refs"].update(_refs_from_value(value.get("evidence_refs")))
        for raw_key, item in value.items():
            key = str(raw_key)
            key_fold = key.casefold()
            if key_fold in {
                NL_REPLAY_ORCHESTRATION_RECORD_KEY,
                "orchestration_continuity",
            } and isinstance(item, Mapping):
                _collect_accepted_refs(
                    item,
                    collected,
                    path=f"{path}.{key}",
                    surface_name=surface_name,
                )
                continue
            refs = _refs_from_value(item)
            if key_fold in {"carrier_ref", "evidence_spine_carrier_ref"} or (
                key_fold == "spine_id" and any(ref.startswith("evidence-spine:") for ref in refs)
            ):
                collected["carrier_refs"].update(refs)
            elif key_fold in {"parent_spine_ref", "evidence_spine_parent_ref"}:
                collected["parent_spine_refs"].update(refs)
            elif key_fold in {
                "concept_spine_ref",
                "consumed_concept_spine_ref",
            } and _is_orchestration_spine_path(path):
                collected["concept_spine_refs"].update(refs)
            elif key_fold in {
                "jurisdiction_spine_ref",
                "consumed_jurisdiction_spine_ref",
            } and _is_orchestration_spine_path(path):
                collected["jurisdiction_spine_refs"].update(refs)
            elif (
                key_fold == "context_id" and schema_version == "policyos.producer_spine_context.v1"
            ):
                collected["producer_spine_context_refs"].update(refs)
            elif key_fold == "producer_handshake_ledger_ref":
                collected["producer_handshake_ledger_refs"].update(refs)
            elif key_fold in {"runtime_claim_registry_ref", "claim_registry_ref"}:
                collected["runtime_claim_registry_refs"].update(refs)
            elif key_fold in {
                "scenario_evidence_contract_id",
                "scenario_contract_id",
            } or (key_fold == "contract_id" and "scenario" in path.casefold()):
                collected["scenario_contract_refs"].update(refs)
            elif key_fold in {
                "handoff_id",
                "continuity_ref",
                "orchestration_continuity_ref",
                NL_REPLAY_ORCHESTRATION_RECORD_KEY,
            }:
                collected["handoff_refs"].update(refs)
            elif key_fold in {"producer_handshake_refs", "handshake_id"}:
                collected["producer_handshake_refs"].update(refs)
            elif key_fold in {
                "candidate_spine_binding_refs",
                "selected_binding_refs",
                "emitted_binding_refs",
                "rejected_binding_refs",
                "blocked_binding_refs",
                "context_only_label_refs",
                "fabric_binding_refs",
                "lex_binding_refs",
                "foundry_binding_refs",
                "scholar_binding_refs",
                "selected_producer_refs",
            }:
                collected["producer_binding_refs"].update(refs)
            elif key_fold in {"claim_ref", "runtime_event_ref"} and (
                "claim" in path.casefold() or "claim" in key_fold
            ):
                collected["claim_refs"].update(refs)
            elif key_fold in {"bridge_authority_ref", "bridge_ref"}:
                collected["bridge_authority_refs"].update(refs)
            _collect_accepted_refs(
                item,
                collected,
                path=f"{path}.{key}",
                surface_name=surface_name,
            )
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, item in enumerate(value):
            _collect_accepted_refs(
                item,
                collected,
                path=f"{path}[{index}]",
                surface_name=surface_name,
            )


def _collect_claim_registry_fallback(
    payload: Mapping[str, Any],
    collected: dict[str, set[str]],
) -> None:
    if "claim_registry" not in str(payload.get("schema_version") or ""):
        return
    if collected["runtime_claim_registry_refs"]:
        return
    authority = payload.get("runtime_authority")
    if isinstance(authority, Mapping):
        collected["runtime_claim_registry_refs"].update(
            _refs_from_value(authority.get("cas_ref") or authority.get("artifact_ref"))
        )


def _is_orchestration_spine_path(path: str) -> bool:
    lowered = path.casefold()
    markers = (
        "spine_context",
        "producer_spine_context",
        "runtime_quality_refs",
        "evidence_spine_handoff",
        "orchestration_continuity",
        "replay_manifest",
        "request_context",
        "workflow_state",
        "job_progress",
        "semantic_binding_ledger",
    )
    return any(marker in lowered for marker in markers)


_CONTINUITY_SUMMARY_REF_FAMILIES = {
    "carrier_ref": "carrier_refs",
    "parent_spine_ref": "parent_spine_refs",
    "concept_spine_ref": "concept_spine_refs",
    "jurisdiction_spine_ref": "jurisdiction_spine_refs",
    "producer_spine_context_ref": "producer_spine_context_refs",
    "producer_handshake_ledger_ref": "producer_handshake_ledger_refs",
    "runtime_claim_registry_ref": "runtime_claim_registry_refs",
    "scenario_contract_refs": "scenario_contract_refs",
    "handoff_refs": "handoff_refs",
    "producer_handshake_refs": "producer_handshake_refs",
    "producer_binding_refs": "producer_binding_refs",
    "claim_refs": "claim_refs",
    "bridge_authority_refs": "bridge_authority_refs",
}


def _collect_continuity_summary_refs(
    value: Mapping[str, Any],
    collected: dict[str, set[str]],
) -> None:
    """Retain summary refs on an observer plane without treating them as source."""

    for field, target in _CONTINUITY_SUMMARY_REF_FAMILIES.items():
        collected[target].update(_refs_from_value(value.get(field)))


def _is_public_continuity_projection(value: Mapping[str, Any]) -> bool:
    """Check the emitted endpoint projection shape, without assigning authority."""

    required_denials = {
        "producer_domain_truth",
        "runtime_closeout_authority",
        "scorecard_authority",
        "approval_authority",
    }
    denied = value.get("may_not_use_for")
    return (
        value.get("schema_version") == NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION
        and value.get("authority_role") == "projection_only"
        and value.get("status") in {"pass", "fail"}
        and isinstance(value.get("handoff_ref_count"), int)
        and not isinstance(value.get("handoff_ref_count"), bool)
        and isinstance(value.get("producer_binding_ref_count"), int)
        and not isinstance(value.get("producer_binding_ref_count"), bool)
        and isinstance(denied, list)
        and required_denials <= {item for item in denied if isinstance(item, str)}
    )


def _is_projection_only_payload(value: Mapping[str, Any]) -> bool:
    """Identify projection-shaped source input only to deny it source status."""

    return (
        value.get("schema_version") == PUBLIC_EXPORT_SCHEMA_VERSION
        or value.get("authority_role") == "projection_only"
    )


def _looks_like_continuity_record(value: Mapping[str, Any]) -> bool:
    return (
        value.get("schema_version") == NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION
        or value.get("record_family") == "nl_replay_orchestration_continuity.v1"
    )


def _continuity_record_issue(value: Mapping[str, Any]) -> str | None:
    """Return a typed input-shape problem without trusting record self-labels."""

    required_fields = {
        "authority_boundary",
        "continuity_fingerprint",
        "continuity_ref",
        "findings",
        "record_family",
        "schema_version",
        "status",
        "summary",
        "surface_coverage",
    }
    if not required_fields <= set(value):
        return "Embedded continuity record is missing required diagnostic fields."
    if (
        value.get("schema_version") != NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION
        or value.get("record_family") != "nl_replay_orchestration_continuity.v1"
        or value.get("status") not in {"pass", "fail"}
        or value.get("continuity_ref") != NL_REPLAY_ORCHESTRATION_FILE_REF
        or not isinstance(value.get("findings"), list)
        or not isinstance(value.get("surface_coverage"), list)
        or not isinstance(value.get("summary"), Mapping)
    ):
        return "Embedded continuity record does not match its diagnostic schema."
    boundary = value.get("authority_boundary")
    if not isinstance(boundary, Mapping) or boundary.get("authority_role") != "diagnostic_only":
        return "Embedded continuity record does not preserve its diagnostic-only boundary."
    required_denials = {
        "producer_domain_truth",
        "scorecard_authority",
        "approval_authority",
        "runtime_closeout_authority",
        "public_projection_authority",
        "evidence_strength",
    }
    denied = boundary.get("may_not_use_for")
    denial_names = (
        {item for item in denied if isinstance(item, str)} if isinstance(denied, list) else set()
    )
    if not required_denials <= denial_names:
        return "Embedded continuity record has an incomplete diagnostic-only boundary."
    fingerprint = value.get("continuity_fingerprint")
    try:
        expected = _stable_ref(
            {key: item for key, item in value.items() if key != "continuity_fingerprint"}
        )
    except (TypeError, ValueError):
        return "Embedded continuity record is not stable JSON."
    if fingerprint != expected:
        return "Embedded continuity record fingerprint does not match its content."
    return None


def _observation_ref_findings(
    source_refs: Mapping[str, tuple[str, ...]],
    observation_refs: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> list[dict[str, Any]]:
    """Report observed ref families absent from selected source candidates."""

    findings: list[dict[str, Any]] = []
    for surface_name in _OBSERVATION_SURFACE_NAMES:
        surface_refs = observation_refs.get(surface_name, {})
        for family in _OBSERVED_REF_FAMILIES:
            unbound = tuple(
                sorted(set(surface_refs.get(family, ())) - set(source_refs.get(family, ())))
            )
            if not unbound:
                continue
            is_export = surface_name == "export"
            findings.append(
                _finding(
                    (
                        "nl_replay_orchestration_export_ref_unbound"
                        if is_export
                        else "nl_replay_orchestration_observation_ref_unbound"
                    ),
                    (
                        "The export endpoint contains a continuity ref absent from selected "
                        "caller/loaded source surfaces."
                        if is_export
                        else "An observation surface contains a continuity ref absent from "
                        "selected caller/loaded source surfaces."
                    ),
                    surface=surface_name,
                    field=family,
                    refs=unbound,
                )
            )
    return findings


def _combine_refs(
    surfaces: Sequence[Mapping[str, tuple[str, ...]]],
) -> dict[str, tuple[str, ...]]:
    combined: dict[str, set[str]] = _empty_collected_refs()
    for surface in surfaces:
        for key, values in surface.items():
            combined.setdefault(key, set()).update(values)
    return {key: tuple(sorted(values)) for key, values in combined.items()}


def _surface_findings(
    surfaces: Mapping[str, Mapping[str, Any] | None],
    collected_by_surface: Mapping[str, Mapping[str, tuple[str, ...]]],
    required_surfaces: Sequence[str],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name in dict.fromkeys(required_surfaces):
        if not isinstance(surfaces.get(name), Mapping) or not surfaces.get(name):
            findings.append(
                _finding(
                    "nl_replay_orchestration_surface_missing",
                    f"Runtime orchestration continuity is missing surface {name}.",
                    surface=name,
                )
            )
            continue
        collected = collected_by_surface.get(name, {})
        if not any(collected.get(key) for key in collected):
            findings.append(
                _finding(
                    "nl_replay_orchestration_surface_refs_missing",
                    f"Runtime orchestration surface {name} carries no continuity refs.",
                    surface=name,
                )
            )
    return findings


def _required_ref_findings(
    combined: Mapping[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    lookup = {
        "carrier_ref": "carrier_refs",
        "concept_spine_ref": "concept_spine_refs",
        "jurisdiction_spine_ref": "jurisdiction_spine_refs",
        "runtime_claim_registry_ref": "runtime_claim_registry_refs",
        "producer_binding_refs": "producer_binding_refs",
    }
    findings = []
    for family in _REQUIRED_REF_FAMILIES:
        if combined.get(lookup[family]):
            continue
        findings.append(
            _finding(
                f"nl_replay_orchestration_{family}_missing",
                f"Runtime orchestration continuity is missing {family}.",
                field=family,
            )
        )
    return findings


def _singleton_mismatch_findings(
    combined: Mapping[str, tuple[str, ...]],
) -> list[dict[str, Any]]:
    lookup = {
        "carrier_ref": "carrier_refs",
        "concept_spine_ref": "concept_spine_refs",
        "jurisdiction_spine_ref": "jurisdiction_spine_refs",
        "producer_handshake_ledger_ref": "producer_handshake_ledger_refs",
        "runtime_claim_registry_ref": "runtime_claim_registry_refs",
    }
    findings = []
    for family in _SINGLETON_REF_FAMILIES:
        values = combined.get(lookup[family], ())
        if len(values) <= 1:
            continue
        findings.append(
            _finding(
                f"nl_replay_orchestration_{family}_mismatch",
                f"Runtime orchestration continuity has mismatched {family} values.",
                field=family,
                refs=values,
            )
        )
    return findings


def _surface_coverage(
    collected_by_surface: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, refs in sorted(collected_by_surface.items()):
        rows.append(
            {
                "surface": name,
                "carrier_refs": list(refs.get("carrier_refs", ())),
                "concept_spine_refs": list(refs.get("concept_spine_refs", ())),
                "jurisdiction_spine_refs": list(refs.get("jurisdiction_spine_refs", ())),
                "runtime_claim_registry_refs": list(refs.get("runtime_claim_registry_refs", ())),
                "handoff_ref_count": len(refs.get("handoff_refs", ())),
                "producer_handshake_ref_count": len(refs.get("producer_handshake_refs", ())),
                "producer_binding_ref_count": len(refs.get("producer_binding_refs", ())),
                "claim_ref_count": len(refs.get("claim_refs", ())),
            }
        )
    return rows


def _finding(
    code: str,
    message: str,
    *,
    surface: str | None = None,
    field: str | None = None,
    refs: Sequence[str] = (),
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "fail",
        "severity": "error",
        "code": code,
        "message": message,
        "root_cause_class": "nl_replay_orchestration_continuity",
        "next_action": (
            "Keep required refs on selected caller/loaded source surfaces and "
            "reconcile replay, bundle, inspection, readiness, and export observations "
            "against those candidates."
        ),
    }
    if surface is not None:
        payload["surface"] = surface
    if field is not None:
        payload["field"] = field
    if refs:
        payload["refs"] = list(refs)
    return payload


def _refs_from_value(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = _text(value)
        return (text,) if text else ()
    if isinstance(value, Mapping):
        if value.get("redacted") is True:
            return ()
        refs: list[str] = []
        for key in _REFERENCE_VALUE_KEYS:
            refs.extend(_refs_from_value(value.get(key)))
        if not refs:
            for item in value.values():
                refs.extend(_refs_from_value(item))
        return tuple(dict.fromkeys(refs))
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        refs: list[str] = []
        for item in value:
            refs.extend(_refs_from_value(item))
        return tuple(dict.fromkeys(refs))
    return ()


def _first(values: Sequence[str]) -> str | None:
    return values[0] if values else None


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_ref(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return "sha256:" + hashlib.sha256(rendered.encode("utf-8")).hexdigest()


__all__ = [
    "NL_REPLAY_ORCHESTRATION_FILE_REF",
    "NL_REPLAY_ORCHESTRATION_RECORD_KEY",
    "NL_REPLAY_ORCHESTRATION_SCHEMA_VERSION",
    "build_nl_replay_orchestration_continuity",
    "extract_nl_replay_orchestration_continuity",
    "validate_nl_replay_orchestration_continuity",
]
