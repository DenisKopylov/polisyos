"""Shared rule-evolution contracts for replay-safe Policy Design Cases."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from polisyos.core import canon

RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.rule_evolution_registry.v1"
)
RULE_EVOLUTION_REPLAY_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.rule_evolution_replay.v1"
)
RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION = (
    "policyos.runtime.policy_design_case.rule_evolution_public_annotation.v1"
)
RULE_EVOLUTION_REGISTRY_KIND = "runtime.rule_evolution_registry"
RULE_EVOLUTION_REGISTRY_SCHEMA = "polisyos.runtime.RuleEvolutionRegistry"
RULE_EVOLUTION_CONTRACT_ID = "policy_design_case.rule_evolution_registry.v1"
RULE_EVOLUTION_RECORD_FAMILY = "publication_trust_and_external_governance.v1"
RULE_EVOLUTION_PRODUCER_OWNER = "team-runtime-quality"
RULE_EVOLUTION_READER_OWNER = "team-runtime-quality"
RULE_EVOLUTION_PUBLIC_POLICY_ADR_BLOCKER = "ADR-TBD-rule-evolution-public-revalidation"

_SEMANTIC_CHANGE_DECISIONS = frozenset(
    {
        "semantic_rule_change",
        "semantic_tightening",
        "new_requirement",
    }
)
_C33_AUTHORITY_BOUNDARY = (
    "annotation_only_until_ADR-TBD-rule-evolution-public-revalidation_is_accepted"
)


class _JsonArtifactStore(Protocol):
    """Minimal CAS writer protocol used by rule-evolution persistence."""

    def put_json(
        self,
        payload: object,
        options: object,
        canon_spec: object | None = None,
    ) -> object:
        """Persist JSON-like payloads and return an artifact reference."""


@dataclass(frozen=True)
class _ArtifactWriteOptions:
    """Local write options shape consumed by CAS stores."""

    kind: str
    media_type: str
    schema: Mapping[str, str]
    producer: object | None = None
    env: object | None = None
    inputs: tuple[object, ...] = ()
    canon: object | None = None


def logic_hash_for_rule(rule_logic: object) -> str:
    """Return the replay-stable SHA-256 identity for rule or taxonomy logic.

    Args:
        rule_logic: JSON-like rule logic, taxonomy logic, or a stable scalar.

    Returns:
        A `sha256:<hex>` digest over PolicyOS canonical JSON bytes.
    """

    data = _stable_json_bytes(rule_logic)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build_rule_evolution_registry(
    *,
    registry_id: str,
    version: str,
    effective_at: str,
    rule_refs: Sequence[Mapping[str, Any]],
    taxonomy_refs: Sequence[Mapping[str, Any]] = (),
    alias_remaps: Sequence[Mapping[str, Any]] = (),
    previous_registry: Mapping[str, Any] | None = None,
    authority_profile_ref: str | None = None,
    evidence_ref: str | None = None,
    runtime_event_ref: str | None = None,
) -> dict[str, Any]:
    """Build a runtime rule-evolution registry with semantic-change detection.

    Lossless identifier migration is allowed only when the source and target
    logic hashes match. If the requirement id changes and the logic hash also
    changes, the registry emits a revalidation blocker instead of recording a
    silent compatible rename.
    """

    normalized_rules, rule_issues = _normalize_rule_refs(rule_refs)
    normalized_taxonomy, taxonomy_issues = _normalize_taxonomy_refs(taxonomy_refs)
    previous_rules = _rules_by_requirement(
        previous_registry.get("rule_refs") if previous_registry else ()
    )
    current_rules = _rules_by_requirement(normalized_rules)
    normalized_remaps, remap_issues = _normalize_alias_remaps(
        alias_remaps,
        previous_rules=previous_rules,
        current_rules=current_rules,
    )
    same_id_changes = _same_requirement_changes(
        previous_rules=previous_rules,
        current_rules=current_rules,
        alias_remaps=normalized_remaps,
    )

    semantic_changes = [
        row
        for row in (*normalized_remaps, *same_id_changes)
        if bool(row.get("semantic_change_detected"))
    ]
    issues = [
        *rule_issues,
        *taxonomy_issues,
        *remap_issues,
        *[
            _issue(
                "rule_logic_semantic_change_detected",
                (
                    "Requirement logic changed under the same id. Closed cases "
                    "must replay under the original logic and current cases require "
                    "revalidation."
                ),
                requirement_id=str(row["target_requirement_id"]),
                refs=[str(row["source_logic_hash"]), str(row["target_logic_hash"])],
            )
            for row in same_id_changes
        ],
    ]
    revalidation_state = _revalidation_state(
        semantic_changes=semantic_changes,
        issues=issues,
        alias_remaps=normalized_remaps,
    )
    status = (
        "blocked"
        if revalidation_state["state"]
        in {"revalidation_required", "blocked_until_revalidated"}
        else "pass"
    )
    registry_ref = (
        _text(evidence_ref)
        or _derived_ref(
            {
                "registry_id": registry_id,
                "version": version,
                "effective_at": effective_at,
                "rule_refs": normalized_rules,
                "taxonomy_refs": normalized_taxonomy,
                "alias_remaps": normalized_remaps,
            }
        )
    )
    payload: dict[str, Any] = {
        "schema_version": RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION,
        "contract_id": RULE_EVOLUTION_CONTRACT_ID,
        "registry_kind": RULE_EVOLUTION_REGISTRY_KIND,
        "record_family": RULE_EVOLUTION_RECORD_FAMILY,
        "registry_id": _required_text(registry_id, "registry_id"),
        "version": _required_text(version, "version"),
        "effective_at": _required_text(effective_at, "effective_at"),
        "status": status,
        "producer_owner": RULE_EVOLUTION_PRODUCER_OWNER,
        "reader_owner": RULE_EVOLUTION_READER_OWNER,
        "authority_profile_ref": _text(authority_profile_ref),
        "rule_registry_ref": registry_ref,
        "evidence_ref": registry_ref,
        "runtime_event_ref": _text(runtime_event_ref)
        or f"event://rule-evolution/{_required_text(registry_id, 'registry_id')}",
        "rule_refs": normalized_rules,
        "taxonomy_refs": normalized_taxonomy,
        "alias_remaps": normalized_remaps,
        "semantic_changes": semantic_changes,
        "same_requirement_id_changes": same_id_changes,
        "revalidation_state": revalidation_state,
        "old_logic_replay_behavior": _old_logic_replay_behavior(semantic_changes),
        "summary": {
            "rule_ref_count": len(normalized_rules),
            "taxonomy_ref_count": len(normalized_taxonomy),
            "alias_remap_count": len(normalized_remaps),
            "semantic_change_count": len(semantic_changes),
            "issue_count": len(issues),
        },
        "issues": issues,
        "runtime_authority_envelope": _authority_envelope(
            registry_ref=registry_ref,
            runtime_event_ref=_text(runtime_event_ref)
            or f"event://rule-evolution/{_required_text(registry_id, 'registry_id')}",
        ),
        "capability_reality": {
            "typed_contract": RULE_EVOLUTION_CONTRACT_ID,
            "producer": RULE_EVOLUTION_PRODUCER_OWNER,
            "artifact": registry_ref,
            "orchestration_bridge": "polisyos.runtime.quality.replay.build_replay_manifest",
            "consumer": "polisyos.runtime.quality.closeout_reader",
            "verification": "tests/unit/runtime/quality/test_rule_evolution.py",
            "surface": "public_rule_evolution_annotation",
            "semantic_test": "requirement id remap with changed logic hash blocks",
        },
    }
    payload["public_annotation"] = public_rule_evolution_annotation(payload)
    return payload


def build_rule_evolution_replay_context(
    *,
    case_id: str,
    closed_case_rule_registry: Mapping[str, Any],
    current_rule_registry: Mapping[str, Any],
    closure_time: str,
    replay_time: str,
) -> dict[str, Any]:
    """Build the replay context that preserves closed-case rule semantics."""

    original_hashes = _logic_hashes_by_requirement(closed_case_rule_registry)
    current_hashes = _logic_hashes_by_requirement(current_rule_registry)
    alias_map = {
        str(row["from_requirement_id"]): str(row["to_requirement_id"])
        for row in _mapping_rows(current_rule_registry.get("alias_remaps"))
        if _text(row.get("from_requirement_id")) and _text(row.get("to_requirement_id"))
    }
    mismatches = []
    for requirement_id, original_hash in original_hashes.items():
        current_requirement_id = alias_map.get(requirement_id, requirement_id)
        current_hash = current_hashes.get(current_requirement_id)
        if current_hash != original_hash:
            mismatches.append(
                {
                    "requirement_id": requirement_id,
                    "current_requirement_id": current_requirement_id,
                    "original_logic_hash": original_hash,
                    "current_logic_hash": current_hash,
                }
            )
    current_semantic_change = bool(
        current_rule_registry.get("semantic_changes") or mismatches
    )
    replay_mode = "original_logic" if current_semantic_change else "current_logic_compatible"
    annotation = public_rule_evolution_annotation(current_rule_registry)
    annotation["legacy_case_annotation"] = (
        "replayed_under_original_logic"
        if current_semantic_change
        else "current_logic_compatible_with_closure"
    )
    return {
        "schema_version": RULE_EVOLUTION_REPLAY_SCHEMA_VERSION,
        "case_id": _required_text(case_id, "case_id"),
        "replay_mode": replay_mode,
        "semantic_change_detected": current_semantic_change,
        "original_rule_registry_ref": _registry_ref(closed_case_rule_registry),
        "current_rule_registry_ref": _registry_ref(current_rule_registry),
        "original_rule_registry_version": _text(closed_case_rule_registry.get("version")),
        "current_rule_registry_version": _text(current_rule_registry.get("version")),
        "original_logic_hashes": original_hashes,
        "current_logic_hashes": current_hashes,
        "logic_hash_mismatches": mismatches,
        "taxonomy_refs": _taxonomy_ref_index(closed_case_rule_registry),
        "time_roles": {
            "closure_time": _required_text(closure_time, "closure_time"),
            "replay_time": _required_text(replay_time, "replay_time"),
            "closed_registry_effective_at": _text(
                closed_case_rule_registry.get("effective_at")
            ),
            "current_registry_effective_at": _text(current_rule_registry.get("effective_at")),
        },
        "revalidation_state": {
            "state": "legacy_replay_only" if current_semantic_change else "not_required",
            "affected_requirement_ids": [
                str(row["requirement_id"])
                for row in mismatches
                if _text(row.get("requirement_id"))
            ],
            "closed_cases_replay_under_original_logic": current_semantic_change,
        },
        "public_annotation": annotation,
        "may_not_use_for": [
            "silent_current_logic_upgrade",
            "mandatory_public_revalidation_policy",
        ],
    }


def public_rule_evolution_annotation(registry: Mapping[str, Any]) -> dict[str, Any]:
    """Return public-facing rule evolution metadata without minting policy authority."""

    remaps = _mapping_rows(registry.get("alias_remaps"))
    semantic_changes = _mapping_rows(registry.get("semantic_changes"))
    revalidation = registry.get("revalidation_state")
    revalidation_state = (
        _text(revalidation.get("state")) if isinstance(revalidation, Mapping) else None
    ) or "not_required"
    affected_requirement_ids = (
        _text_values(revalidation.get("affected_requirement_ids"))
        if isinstance(revalidation, Mapping)
        else ()
    )
    if semantic_changes or revalidation_state in {
        "revalidation_required",
        "blocked_until_revalidated",
        "legacy_replay_only",
    }:
        annotation_state = "semantic_change"
    elif remaps:
        annotation_state = "compatible_alias"
    else:
        annotation_state = "unchanged"
    return {
        "schema_version": RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION,
        "registry_id": _text(registry.get("registry_id")),
        "registry_version": _text(registry.get("version")),
        "rule_registry_ref": _registry_ref(registry),
        "public_annotation_state": annotation_state,
        "annotation_required": annotation_state != "unchanged",
        "revalidation_state": revalidation_state,
        "affected_requirement_ids": list(affected_requirement_ids),
        "alias_remap_count": len(remaps),
        "semantic_change_count": len(semantic_changes),
        "silent_upgrade_allowed": False,
        "closed_cases_replay_under_original_logic": revalidation_state
        in {"revalidation_required", "blocked_until_revalidated", "legacy_replay_only"},
        "authority_boundary": _C33_AUTHORITY_BOUNDARY,
        "decision_refs": ["ADR-0163", "ADR-0100"],
        "blocked_structural_policy_ref": RULE_EVOLUTION_PUBLIC_POLICY_ADR_BLOCKER,
        "authoritative_for": ["public_rule_evolution_annotation"],
        "may_not_use_for": [
            "mandatory_public_revalidation_policy",
            "silent_upgrade_approval",
            "claim_evidence_authority",
            "scorecard_authority",
        ],
    }


def persist_rule_evolution_registry(
    registry: Mapping[str, Any],
    *,
    store: _JsonArtifactStore,
) -> object:
    """Persist a rule-evolution registry and return its CAS ref."""

    return store.put_json(
        dict(registry),
        _ArtifactWriteOptions(
            kind=RULE_EVOLUTION_REGISTRY_KIND,
            media_type="application/json",
            schema={"name": RULE_EVOLUTION_REGISTRY_SCHEMA, "version": "1.0"},
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )


def _normalize_rule_refs(
    rule_refs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, raw in enumerate(rule_refs):
        if not isinstance(raw, Mapping):
            issues.append(
                _issue(
                    "rule_ref_invalid",
                    "Rule registry entries must be mappings.",
                    field=f"rule_refs[{index}]",
                )
            )
            continue
        requirement_id = _text(
            raw.get("requirement_id") or raw.get("rule_id") or raw.get("id")
        )
        if requirement_id is None:
            issues.append(
                _issue(
                    "rule_requirement_id_missing",
                    "Rule registry entries must declare a requirement id.",
                    field=f"rule_refs[{index}].requirement_id",
                )
            )
            continue
        logic_hash = _hash_from_row(raw)
        if logic_hash is None:
            issues.append(
                _issue(
                    "rule_logic_hash_missing",
                    "Rule registry entries must carry logic or a logic hash.",
                    requirement_id=requirement_id,
                )
            )
            logic_hash = logic_hash_for_rule({"requirement_id": requirement_id})
        row = {
            "requirement_id": requirement_id,
            "rule_id": _text(raw.get("rule_id")) or requirement_id,
            "logic_hash": logic_hash,
            "logic_hash_source": "provided" if _text(raw.get("logic_hash")) else "computed",
            "taxonomy_refs": list(_text_values(raw.get("taxonomy_refs"))),
            "authority_purpose": _text(raw.get("authority_purpose")) or "admissibility",
            "status": _text(raw.get("status")) or "active",
            "provenance_ref": _text(raw.get("provenance_ref")),
        }
        if "logic" in raw:
            row["logic"] = _json_compatible(raw["logic"])
        row.update(_optional_rule_metadata(raw))
        rows.append({key: value for key, value in row.items() if value not in (None, [], "")})
    return rows, issues


def _optional_rule_metadata(raw: Mapping[str, Any]) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for key in (
        "rule_family",
        "rule_version",
        "owner",
        "authority_level",
        "public_revalidation_effect",
        "source_class",
    ):
        value = _text(raw.get(key))
        if value is not None:
            metadata[key] = value
    evidence_basis = _text_values(raw.get("evidence_basis"))
    if evidence_basis:
        metadata["evidence_basis"] = list(evidence_basis)
    scope = raw.get("scope")
    if isinstance(scope, Mapping):
        metadata["scope"] = dict(scope)
    deprecation_policy = raw.get("deprecation_policy")
    if isinstance(deprecation_policy, Mapping):
        metadata["deprecation_policy"] = dict(deprecation_policy)
    return metadata


def _normalize_taxonomy_refs(
    taxonomy_refs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, raw in enumerate(taxonomy_refs):
        if not isinstance(raw, Mapping):
            issues.append(
                _issue(
                    "taxonomy_ref_invalid",
                    "Taxonomy registry entries must be mappings.",
                    field=f"taxonomy_refs[{index}]",
                )
            )
            continue
        taxonomy_id = _text(
            raw.get("taxonomy_id") or raw.get("id") or raw.get("taxonomy")
        )
        if taxonomy_id is None:
            issues.append(
                _issue(
                    "taxonomy_id_missing",
                    "Taxonomy registry entries must declare a taxonomy id.",
                    field=f"taxonomy_refs[{index}].taxonomy_id",
                )
            )
            continue
        row = {
            "taxonomy_id": taxonomy_id,
            "version": _text(raw.get("version")) or "unknown",
            "ref": _text(raw.get("ref") or raw.get("taxonomy_ref")),
            "logic_hash": _hash_from_row(raw)
            or logic_hash_for_rule(
                {
                    "taxonomy_id": taxonomy_id,
                    "version": _text(raw.get("version")) or "unknown",
                    "ref": _text(raw.get("ref") or raw.get("taxonomy_ref")),
                }
            ),
        }
        rows.append({key: value for key, value in row.items() if value not in (None, "", [])})
    return rows, issues


def _normalize_alias_remaps(
    alias_remaps: Sequence[Mapping[str, Any]],
    *,
    previous_rules: Mapping[str, Mapping[str, Any]],
    current_rules: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for index, raw in enumerate(alias_remaps):
        if not isinstance(raw, Mapping):
            issues.append(
                _issue(
                    "rule_alias_remap_invalid",
                    "Rule alias remap entries must be mappings.",
                    field=f"alias_remaps[{index}]",
                )
            )
            continue
        source_id = _text(
            raw.get("from_requirement_id")
            or raw.get("source_requirement_id")
            or raw.get("old_requirement_id")
        )
        target_id = _text(
            raw.get("to_requirement_id")
            or raw.get("target_requirement_id")
            or raw.get("new_requirement_id")
        )
        if source_id is None or target_id is None:
            issues.append(
                _issue(
                    "rule_alias_endpoint_missing",
                    "Rule alias remap requires source and target requirement ids.",
                    field=f"alias_remaps[{index}]",
                )
            )
            continue
        source_hash = (
            _clean_hash(raw.get("source_logic_hash"))
            or _clean_hash(raw.get("from_logic_hash"))
            or _logic_hash(previous_rules.get(source_id))
        )
        target_hash = (
            _clean_hash(raw.get("target_logic_hash"))
            or _clean_hash(raw.get("to_logic_hash"))
            or _logic_hash(current_rules.get(target_id))
        )
        if source_hash is None or target_hash is None:
            decision = "unknown_requirement_blocked"
            compatible = False
            semantic_change = True
            issues.append(
                _issue(
                    "rule_alias_logic_hash_missing",
                    (
                        "Rule alias remap cannot be treated as compatible without "
                        "source and target logic hashes."
                    ),
                    requirement_id=target_id,
                    refs=[value for value in (source_id, target_id) if value],
                )
            )
        elif source_hash == target_hash:
            decision = "lossless_alias_migration"
            compatible = True
            semantic_change = False
        else:
            decision = "semantic_rule_change"
            compatible = False
            semantic_change = True
            issues.append(
                _issue(
                    "rule_alias_semantic_change_detected",
                    (
                        "Requirement id remap changed the logic hash. Treat it as "
                        "semantic change or tightening, not as a silent compatible rename."
                    ),
                    requirement_id=target_id,
                    refs=[source_hash, target_hash],
                )
            )
        rows.append(
            {
                "from_requirement_id": source_id,
                "to_requirement_id": target_id,
                "source_requirement_id": source_id,
                "target_requirement_id": target_id,
                "source_logic_hash": source_hash,
                "target_logic_hash": target_hash,
                "decision": decision,
                "compatible_migration": compatible,
                "semantic_change_detected": semantic_change,
                "reason": _text(raw.get("reason")),
            }
        )
    return [
        {key: value for key, value in row.items() if value not in (None, "", [])}
        for row in rows
    ], issues


def _same_requirement_changes(
    *,
    previous_rules: Mapping[str, Mapping[str, Any]],
    current_rules: Mapping[str, Mapping[str, Any]],
    alias_remaps: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    remapped_sources = {
        str(row["from_requirement_id"])
        for row in alias_remaps
        if _text(row.get("from_requirement_id"))
    }
    changes: list[dict[str, Any]] = []
    for requirement_id, previous in previous_rules.items():
        if requirement_id in remapped_sources or requirement_id not in current_rules:
            continue
        previous_hash = _logic_hash(previous)
        current_hash = _logic_hash(current_rules[requirement_id])
        if previous_hash and current_hash and previous_hash != current_hash:
            changes.append(
                {
                    "from_requirement_id": requirement_id,
                    "to_requirement_id": requirement_id,
                    "source_requirement_id": requirement_id,
                    "target_requirement_id": requirement_id,
                    "source_logic_hash": previous_hash,
                    "target_logic_hash": current_hash,
                    "decision": "semantic_rule_change",
                    "compatible_migration": False,
                    "semantic_change_detected": True,
                }
            )
    return changes


def _revalidation_state(
    *,
    semantic_changes: Sequence[Mapping[str, Any]],
    issues: Sequence[Mapping[str, Any]],
    alias_remaps: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    affected = sorted(
        {
            str(row.get("to_requirement_id") or row.get("target_requirement_id"))
            for row in semantic_changes
            if _text(row.get("to_requirement_id") or row.get("target_requirement_id"))
        }
    )
    if semantic_changes:
        state = "revalidation_required"
    elif any(str(issue.get("code")) == "rule_alias_logic_hash_missing" for issue in issues):
        state = "blocked_until_revalidated"
    else:
        state = "not_required"
    return {
        "state": state,
        "affected_requirement_ids": affected,
        "alias_remap_count": len(alias_remaps),
        "semantic_change_count": len(semantic_changes),
        "closed_cases_replay_under_original_logic": bool(semantic_changes),
        "public_annotation_required": bool(alias_remaps or semantic_changes),
    }


def _old_logic_replay_behavior(semantic_changes: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "closed_cases": (
            "replay_with_original_registry"
            if semantic_changes
            else "current_registry_compatible"
        ),
        "current_cases": (
            "revalidate_before_publication"
            if semantic_changes
            else "lossless_schema_or_alias_migration_allowed"
        ),
        "silent_upgrade_allowed": False,
    }


def _authority_envelope(*, registry_ref: str, runtime_event_ref: str) -> dict[str, Any]:
    return {
        "authority_role": "runtime_reader",
        "provenance_kind": "runtime_emitted",
        "cas_ref": registry_ref,
        "runtime_event_ref": runtime_event_ref,
        "authoritative_for": ["rule_evolution_replay"],
        "may_not_use_for": [
            "claim_evidence_authority",
            "mandatory_public_revalidation_policy",
            "scorecard_authority",
            "silent_upgrade_approval",
        ],
    }


def _rules_by_requirement(value: object) -> dict[str, Mapping[str, Any]]:
    return {
        str(row["requirement_id"]): row
        for row in _mapping_rows(value)
        if _text(row.get("requirement_id"))
    }


def _logic_hashes_by_requirement(registry: Mapping[str, Any]) -> dict[str, str]:
    return {
        requirement_id: str(row["logic_hash"])
        for requirement_id, row in _rules_by_requirement(registry.get("rule_refs")).items()
        if _logic_hash(row)
    }


def _taxonomy_ref_index(registry: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in _mapping_rows(registry.get("taxonomy_refs")):
        taxonomy_id = _text(row.get("taxonomy_id"))
        ref = _text(row.get("ref") or row.get("logic_hash"))
        if taxonomy_id and ref:
            result[taxonomy_id] = ref
    return result


def _registry_ref(registry: Mapping[str, Any]) -> str | None:
    return _text(
        registry.get("rule_registry_ref")
        or registry.get("registry_ref")
        or registry.get("evidence_ref")
        or registry.get("cas_ref")
    )


def _mapping_rows(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [row for row in value if isinstance(row, Mapping)]


def _text_values(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if not isinstance(value, Sequence):
        return ()
    return tuple(
        text
        for item in value
        if (text := _text(item)) is not None
    )


def _hash_from_row(row: Mapping[str, Any]) -> str | None:
    return _clean_hash(row.get("logic_hash")) or (
        logic_hash_for_rule(row["logic"]) if "logic" in row else None
    )


def _logic_hash(row: Mapping[str, Any] | None) -> str | None:
    if row is None:
        return None
    return _clean_hash(row.get("logic_hash"))


def _clean_hash(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if text.startswith("sha256:") and len(text) == 71:
        digest = text.removeprefix("sha256:")
        if all(char in "0123456789abcdef" for char in digest.lower()):
            return "sha256:" + digest.lower()
    if len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower()):
        return "sha256:" + text.lower()
    return None


def _derived_ref(value: object) -> str:
    data = _stable_json_bytes(value)
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _stable_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        default=str,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _json_compatible(value: object) -> object:
    return json.loads(
        json.dumps(
            value,
            default=str,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


def _issue(
    code: str,
    message: str,
    *,
    field: str | None = None,
    requirement_id: str | None = None,
    refs: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "phase": "rule_evolution",
        "message": message,
        "field": field,
        "requirement_id": requirement_id,
        "refs": list(refs),
        "next_action": (
            "Record rule/taxonomy logic hashes, replay old closed cases under "
            "the original registry, and revalidate current/public cases before "
            "treating the change as publishable."
        ),
    }


def _required_text(value: object, field: str) -> str:
    text = _text(value)
    if text is None:
        raise ValueError(f"{field} is required")
    return text


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


__all__ = [
    "RULE_EVOLUTION_CONTRACT_ID",
    "RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION",
    "RULE_EVOLUTION_RECORD_FAMILY",
    "RULE_EVOLUTION_REGISTRY_KIND",
    "RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION",
    "RULE_EVOLUTION_REPLAY_SCHEMA_VERSION",
    "build_rule_evolution_registry",
    "build_rule_evolution_replay_context",
    "logic_hash_for_rule",
    "persist_rule_evolution_registry",
    "public_rule_evolution_annotation",
]
