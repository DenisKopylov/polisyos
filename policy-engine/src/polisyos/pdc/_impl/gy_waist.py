"""Layer 3 GY two-ring waist contracts for the workspace control loop."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, model_validator

from polisyos.common import serialization

from .layer2_readiness import (
    ID_PATTERN,
    AuthorityBoundary,
    CertifiedOperationEnvelope,
    DecisionGrade,
    EvidenceBasis,
    EvidenceKind,
    Layer2ReadinessModel,
)

GY_WAIST_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy_waist.v1"
GY_PROMOTION_SEQUENCE_SCHEMA_VERSION = "policyos.policy_design_case.layer3_gy.n9_promotion.v3"

GY_COMPARISON_PROJECTION_LEGACY_SCHEMA_VERSION = "policyos.gy.comparison_projection.v1"
GY_COMPARISON_PROJECTION_SCHEMA_VERSION = "policyos.gy.comparison_projection.v2"


GY_VERIFICATION_COMPARISON_LEGACY_RULE_VERSION = (
    "policyos.gy.non_authority_verification.v2"
)
GY_VERIFICATION_COMPARISON_RULE_VERSION = "policyos.gy.non_authority_verification.v3"

GY_ARTIFACT_ID_PATTERN = r"^(?:[a-z][a-z0-9_.-]*|sha256:[0-9a-f]{64})$"

GY_CONTENT_HASH_EXCLUDED_FIELDS = (
    "ms",
    "seconds",
    "secs",
    "elapsed",
    "elapsed_s",
    "elapsed_ms",
    "vector_ms",
    "text_ms",
    "duration_ms",
    "duration_s",
    "took_ms",
    "timestamp",
    "generated_at",
    "started_at",
    "finished_at",
    "created_at",
    "wall_time",
    "wall_clock",
    "now",
    "run_at",
    "executed_at",
    "runtime_metrics",
    "*_ms",
    "*_sec",
    "*_secs",
    "*_at",
    "*_ns",
    "*_us",
    "*_latency",
    "*_duration",
)
_VERIFIER_WRITERS = frozenset({"verifier", "governance", "a_side", "system_verifier"})
_DECISION_GRADE_RANK: dict[str | None, int] = {
    None: 0,
    "unsupported": 0,
    "descriptive_only": 1,
    "advisory_admissible": 2,
    "decision_admissible": 3,
}
_GY_DRIFT_MISSING = object()
_GY_CONTENT_HASH_VALUE_MISSING = object()
_GY_DIAGNOSTIC_IDENTITY_PATTERN = r"^(?:absent|sha256:[0-9a-f]{64})$"
_GY_NON_AUTHORITY_PROVENANCE = frozenset({"verification"})
_GY_COMPARISON_BLOCK_EXCLUDED = object()
type _GyComparisonPathSegment = str | int
type _GyComparisonPath = tuple[_GyComparisonPathSegment, ...]
type GyComparisonPredicateProvenance = Literal["recomputed", "independently_reconciled"]
type GyComparisonLegacyMigrator = Callable[
    [Mapping[str, object], Mapping[str, object]],
    Mapping[str, object],
]


@dataclass(frozen=True)
class GyArtifactProjectionRule:
    """One reason-bound top-level exclusion from an artifact projection."""

    top_level_fields: frozenset[str]
    applies_to: Literal["artifact_and_identity", "identity_only"]
    reason: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.top_level_fields, frozenset)
            or not self.top_level_fields
            or any(
                not isinstance(field, str) or not field.strip()
                for field in self.top_level_fields
            )
        ):
            raise ValueError("gy_artifact_projection_rule_fields_required")
        if self.applies_to not in {"artifact_and_identity", "identity_only"}:
            raise ValueError("gy_artifact_projection_rule_scope_invalid")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("gy_artifact_projection_rule_reason_required")


@dataclass(frozen=True)
class GyArtifactProjectionOwner:
    """Own JSON representation and declared exclusions for one artifact family.

    Explicit nulls are governing JSON values. Missing members stay missing, and
    unsupported values fail closed rather than being stringified. Exclusions are
    exact top-level names, grouped by a durable reason.
    """

    exclusion_rules: tuple[GyArtifactProjectionRule, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.exclusion_rules, tuple) or any(
            not isinstance(rule, GyArtifactProjectionRule)
            for rule in self.exclusion_rules
        ):
            raise ValueError("gy_artifact_projection_rules_invalid")
        seen_fields: set[str] = set()
        seen_reasons: set[str] = set()
        for rule in self.exclusion_rules:
            if seen_fields.intersection(rule.top_level_fields):
                raise ValueError("gy_artifact_projection_rule_field_duplicate")
            if rule.reason in seen_reasons:
                raise ValueError("gy_artifact_projection_rule_reason_duplicate")
            seen_fields.update(rule.top_level_fields)
            seen_reasons.add(rule.reason)

    def exclusion_rule(self, *, reason: str) -> GyArtifactProjectionRule:
        """Return the one declared exclusion rule carrying ``reason``."""

        for rule in self.exclusion_rules:
            if rule.reason == reason:
                return rule
        raise ValueError("gy_artifact_projection_rule_unknown")

    def artifact_projection(self, value: object) -> dict[str, object]:
        """Return canonical artifact JSON with governing nulls retained."""

        return self._project(value, include_identity_only=False)

    def identity_projection(self, value: object) -> dict[str, object]:
        """Return the artifact projection without its recursive self-identity."""

        return self._project(value, include_identity_only=True)

    def _project(
        self,
        value: object,
        *,
        include_identity_only: bool,
    ) -> dict[str, object]:
        payload = _gy_artifact_projection_json_mapping(value)
        excluded = {
            field
            for rule in self.exclusion_rules
            if rule.applies_to == "artifact_and_identity" or include_identity_only
            for field in rule.top_level_fields
        }
        return {key: item for key, item in payload.items() if key not in excluded}


GY_N11_CONFIDENCE_CONTRACT_PROJECTION_OWNER = GyArtifactProjectionOwner(
    exclusion_rules=(
        GyArtifactProjectionRule(
            top_level_fields=frozenset(
                {
                    "comparison_content_hash",
                    "comparison_projection_schema_version",
                    "comparison_rule_version",
                }
            ),
            applies_to="artifact_and_identity",
            reason="non_governing_verification_identity",
        ),
        GyArtifactProjectionRule(
            top_level_fields=frozenset({"artifact_content_hash"}),
            applies_to="identity_only",
            reason="recursive_self_identity",
        ),
    )
)


def _gy_artifact_projection_json_mapping(value: object) -> dict[str, object]:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=False)
    if not isinstance(value, Mapping):
        raise ValueError("gy_artifact_projection_mapping_required")
    projected = _gy_artifact_projection_json_value(value)
    if not isinstance(projected, dict):  # pragma: no cover - root checked above
        raise ValueError("gy_artifact_projection_mapping_required")
    return projected


def _gy_artifact_projection_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("gy_artifact_projection_mapping_key_invalid")
        return {
            key: _gy_artifact_projection_json_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_gy_artifact_projection_json_value(item) for item in value]
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    raise ValueError("gy_artifact_projection_value_not_json")


@dataclass(frozen=True)
class GyComparisonOwnerRule:
    """Producer-owned policy for reconstructing one comparison-plan entry.

    A persisted manifest is an integrity recipe, never an authority source.  The
    live owner registry fixes the only action and P37 predicate provenance that
    one rule may claim, so artifact bytes cannot widen ``project`` into
    ``exclude`` or upgrade the predicate's evidence class.
    """

    projector: Callable[[Mapping[str, object]], object]
    action: Literal["exclude", "project"]
    predicate_provenance: GyComparisonPredicateProvenance


@dataclass(frozen=True)
class GyComparisonAdmission:
    """One ephemeral producer-owned admission into a comparison projection.

    ``source_content_hash`` binds the admission to the exact live block that the
    producer validated.  ``projector`` is owned by that producer and is applied
    to the aligned frozen block only after the live path has been derived from
    that exact binding.  A JSON declaration or a self-computed hash cannot mint
    an admission.
    """

    owner_rule: str
    source_content_hash: str
    projector: Callable[[Mapping[str, object]], object]
    action: Literal["exclude", "project"] = "project"
    predicate_provenance: GyComparisonPredicateProvenance = "recomputed"
    legacy_migrator: GyComparisonLegacyMigrator | None = None


@dataclass(frozen=True)
class _GyComparisonPlanEntry:
    path: _GyComparisonPath
    owner_rule: str
    projector: Callable[[Mapping[str, object]], object]
    action: Literal["exclude", "project"]
    predicate_provenance: GyComparisonPredicateProvenance
    legacy_migrator: GyComparisonLegacyMigrator | None = None


@dataclass(frozen=True)
class GyComparisonProjectionPlan:
    """Path-bound comparison plan derived from live producer admissions."""

    entries: tuple[_GyComparisonPlanEntry, ...]

    def __post_init__(self) -> None:
        paths = tuple(entry.path for entry in self.entries)
        if len(paths) != len(set(paths)):
            raise ValueError("gy_comparison_admission_path_duplicate")

    @property
    def manifest(self) -> list[dict[str, str]]:
        """Return the stable, persisted description of admitted live paths."""

        return [
            {
                "action": entry.action,
                "json_pointer": _gy_comparison_json_pointer(entry.path),
                "owner_rule": entry.owner_rule,
                "predicate_provenance": entry.predicate_provenance,
            }
            for entry in self.entries
        ]

    def project(self, value: object) -> object:
        """Project an aligned full record under this producer-bound plan."""

        entries = {entry.path: entry for entry in self.entries}
        applied: set[_GyComparisonPath] = set()

        def walk(item: object, path: _GyComparisonPath) -> object:
            entry = entries.get(path)
            if entry is not None:
                if not isinstance(item, Mapping):
                    raise ValueError("gy_comparison_admitted_block_shape_mismatch")
                applied.add(path)
                if entry.action == "exclude":
                    entry.projector(item)
                    return _GY_COMPARISON_BLOCK_EXCLUDED
                projected = entry.projector(item)
                if projected is _GY_COMPARISON_BLOCK_EXCLUDED:
                    raise ValueError("gy_comparison_projector_action_mismatch")
                return strip_gy_volatile_fields(projected)
            if isinstance(item, Mapping):
                projected_mapping: dict[str, object] = {}
                for key, child in item.items():
                    normalized_key = str(key)
                    if is_gy_content_hash_excluded_field(normalized_key):
                        continue
                    projected_child = walk(child, (*path, normalized_key))
                    if projected_child is not _GY_COMPARISON_BLOCK_EXCLUDED:
                        projected_mapping[normalized_key] = projected_child
                return projected_mapping
            if isinstance(item, (list, tuple)):
                projected_items: list[object] = []
                for index, child in enumerate(item):
                    projected_child = walk(child, (*path, index))
                    if projected_child is not _GY_COMPARISON_BLOCK_EXCLUDED:
                        projected_items.append(projected_child)
                return projected_items
            return item

        projected = walk(value, ())
        if applied != set(entries):
            raise ValueError("gy_comparison_admission_path_missing")
        return projected

    def relative_to(self, prefix: _GyComparisonPath) -> GyComparisonProjectionPlan:
        """Return the portion of this plan below one already-bound container."""

        selected = tuple(
            _GyComparisonPlanEntry(
                path=entry.path[len(prefix) :],
                owner_rule=entry.owner_rule,
                projector=entry.projector,
                action=entry.action,
                predicate_provenance=entry.predicate_provenance,
                legacy_migrator=entry.legacy_migrator,
            )
            for entry in self.entries
            if entry.path[: len(prefix)] == prefix
        )
        if not selected:
            raise ValueError("gy_comparison_relative_plan_empty")
        return GyComparisonProjectionPlan(entries=selected)

    def migrate_admitted_blocks(self, previous: object, current: object) -> object:
        """Apply live-owner legacy migrations only at their admitted paths.

        A migration callback is ephemeral: it exists only on a plan built from
        live producer admissions and is never serialized in the manifest.
        Every non-admitted byte remains the previous custody value here; the
        ordinary reconciliation step decides unrelated live changes later.
        """

        migrations = {
            entry.path: entry
            for entry in self.entries
            if entry.legacy_migrator is not None
        }
        if not migrations:
            return previous
        visited: set[_GyComparisonPath] = set()

        def walk(left: object, right: object, path: _GyComparisonPath) -> object:
            entry = migrations.get(path)
            if entry is not None:
                if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                    raise ValueError("gy_comparison_admitted_block_shape_mismatch")
                migrator = entry.legacy_migrator
                if migrator is None:  # pragma: no cover - selected above.
                    raise ValueError("gy_comparison_legacy_migrator_missing")
                migrated = migrator(left, right)
                if not isinstance(migrated, Mapping):
                    raise ValueError("gy_comparison_legacy_migration_shape_invalid")
                visited.add(path)
                return {str(key): item for key, item in migrated.items()}
            if isinstance(left, Mapping) and isinstance(right, Mapping):
                return {
                    str(key): (
                        walk(child, right[key], (*path, str(key)))
                        if key in right
                        else child
                    )
                    for key, child in left.items()
                }
            if isinstance(left, list) and isinstance(right, list):
                return [
                    walk(child, right[index], (*path, index))
                    if index < len(right)
                    else child
                    for index, child in enumerate(left)
                ]
            if isinstance(left, tuple) and isinstance(right, tuple):
                return tuple(
                    walk(child, right[index], (*path, index))
                    if index < len(right)
                    else child
                    for index, child in enumerate(left)
                )
            return left

        migrated = walk(previous, current, ())
        if visited != set(migrations):
            raise ValueError("gy_comparison_admission_path_missing")
        return migrated

    def preserve_admitted_blocks(self, previous: object, current: object) -> object:
        """Retain admitted evidence while taking unrelated live reissue deltas.

        A projected admission is retained only when its complete typed semantic
        projection is equal.  An excluded admission was already validated and
        content-bound by its live producer token.  Fields outside admissions are
        taken from the live record, except ordinary operational leaves.
        """

        aligned_previous = self.migrate_admitted_blocks(previous, current)
        return self._preserve_aligned_admitted_blocks(aligned_previous, current)

    def _preserve_aligned_admitted_blocks(
        self,
        aligned_previous: object,
        current: object,
    ) -> object:
        """Preserve one already-migrated frozen value without rerunning its owner."""

        entries = {entry.path: entry for entry in self.entries}
        preserve_operational = self.project(aligned_previous) == self.project(current)
        visited: set[_GyComparisonPath] = set()

        def walk(left: object, right: object, path: _GyComparisonPath) -> object:
            entry = entries.get(path)
            if entry is not None:
                if not isinstance(left, Mapping) or not isinstance(right, Mapping):
                    raise ValueError("gy_comparison_admitted_block_shape_mismatch")
                visited.add(path)
                if entry.projector(left) != entry.projector(right):
                    raise ValueError("gy_comparison_admitted_block_semantic_mismatch")
                return left
            if isinstance(left, Mapping) and isinstance(right, Mapping):
                return {
                    str(key): (
                        left[key]
                        if (
                            preserve_operational
                            and key in left
                            and is_gy_content_hash_excluded_field(str(key))
                        )
                        else walk(left[key], child, (*path, str(key)))
                        if key in left
                        else child
                    )
                    for key, child in right.items()
                }
            if isinstance(left, list) and isinstance(right, list):
                return [
                    walk(left[index], child, (*path, index)) if index < len(left) else child
                    for index, child in enumerate(right)
                ]
            if isinstance(left, tuple) and isinstance(right, tuple):
                return tuple(
                    walk(left[index], child, (*path, index)) if index < len(left) else child
                    for index, child in enumerate(right)
                )
            return right

        reconciled = walk(aligned_previous, current, ())
        if visited != set(entries):
            raise ValueError("gy_comparison_admission_path_missing")
        return reconciled


class _GyDriftOperandIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    content_identity: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    operand_role: Literal["expected_frozen", "live_replayed"]


class _GyDriftLeafIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    content_identity: str = Field(pattern=_GY_DIAGNOSTIC_IDENTITY_PATTERN)
    presence: Literal["present", "absent"]
    value_type: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^(?:absent|[A-Za-z_][A-Za-z0-9_.]*)$",
    )

    @model_validator(mode="after")
    def _validate_absence_identity(self) -> _GyDriftLeafIdentity:
        absent_fields = (
            self.content_identity == "absent",
            self.presence == "absent",
            self.value_type == "absent",
        )
        if len(set(absent_fields)) != 1:
            raise ValueError("gy_drift_leaf_absence_identity_inconsistent")
        return self


class _GyDriftChangedLeaf(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    expected_frozen: _GyDriftLeafIdentity
    live_replayed: _GyDriftLeafIdentity
    operational: bool
    path: str = Field(min_length=1, max_length=4096, pattern=r"^/")


class _GyOperationalDriftDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    admission_arm: Literal["controlled_at_capture", "migrated", "not_applicable"]
    changed_leaves: tuple[_GyDriftChangedLeaf, ...] = Field(min_length=1)
    expected_frozen: _GyDriftOperandIdentity
    live_replayed: _GyDriftOperandIdentity
    recording_role: Literal[
        "first_vertical",
        "education",
        "unseen",
        "not_applicable",
    ]

    @model_validator(mode="after")
    def _validate_operand_roles(self) -> _GyOperationalDriftDiagnostic:
        if self.expected_frozen.operand_role != "expected_frozen":
            raise ValueError("gy_drift_expected_operand_role_invalid")
        if self.live_replayed.operand_role != "live_replayed":
            raise ValueError("gy_drift_observed_operand_role_invalid")
        return self


class GyOperationalReconciliationError(ValueError):
    """A safe, typed description of one canonical GY comparison failure."""

    def __init__(
        self,
        code: Literal[
            "gy_operational_reconciliation_semantic_projection_mismatch",
            "gy_operational_reconciliation_shape_mismatch",
            "gy_operational_reconciliation_exact_mismatch",
        ],
        diagnostic: _GyOperationalDriftDiagnostic,
    ) -> None:
        self.code = code
        self._diagnostic = diagnostic
        super().__init__(code, diagnostic)

    @property
    def safe_detail(self) -> str:
        """Return the canonical code plus identity-only diagnostic payload."""

        return (
            self.code
            + ":"
            + json.dumps(
                self._diagnostic.model_dump(mode="json"),
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            )
        )

    def __str__(self) -> str:
        return self.safe_detail


def is_gy_content_hash_excluded_field(key: str) -> bool:
    """Return whether ``key`` is an operational GY content-hash exclusion."""

    normalized = key.lower()
    return any(
        normalized.endswith(rule[1:]) if rule.startswith("*") else normalized == rule
        for rule in GY_CONTENT_HASH_EXCLUDED_FIELDS
    )


def is_gy_declared_non_authority_block(value: object) -> bool:
    """Return whether a block declares only recognized non-authority provenance.

    This function classifies the declaration only. It does not establish producer
    provenance or content integrity and therefore never changes ``gy_content_hash``.
    A comparison owner must separately admit the block through its typed producer.
    """

    if not isinstance(value, Mapping):
        return False
    declaration = value.get("authority_provenance", _GY_CONTENT_HASH_VALUE_MISSING)
    if isinstance(declaration, str):
        provenances = (declaration,)
    elif isinstance(declaration, list) and all(isinstance(item, str) for item in declaration):
        provenances = tuple(declaration)
    else:
        return False
    return bool(provenances) and all(
        provenance in _GY_NON_AUTHORITY_PROVENANCE for provenance in provenances
    )


def strip_gy_volatile_fields(value: object) -> object:
    """Return ``value`` with operational timing fields removed recursively."""

    if isinstance(value, dict):
        return {
            str(key): strip_gy_volatile_fields(item)
            for key, item in value.items()
            if not is_gy_content_hash_excluded_field(str(key))
        }
    if isinstance(value, (list, tuple)):
        return [strip_gy_volatile_fields(item) for item in value]
    return value


def gy_content_hash(value: object) -> str:
    """Return a GY evidence content hash over time-stripped canonical JSON."""

    payload = json.dumps(
        strip_gy_volatile_fields(value),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def gy_recorded_content_hash(value: object) -> str:
    """Return an exact canonical-JSON hash without comparison exclusions."""

    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def build_gy_comparison_projection_plan(
    value: object,
    *,
    admissions: tuple[GyComparisonAdmission, ...],
) -> GyComparisonProjectionPlan:
    """Bind exact live producer admissions to their derived payload paths.

    Admissions form a multiset.  Every supplied admission must match exactly one
    live mapping, and an additional byte-identical copy receives no admission.
    This prevents a caller-controlled declaration or duplicated block from
    widening the comparison projection.
    """

    remaining = list(admissions)
    entries: list[_GyComparisonPlanEntry] = []

    def walk(item: object, path: _GyComparisonPath) -> None:
        if isinstance(item, Mapping):
            source_content_hash = gy_recorded_content_hash(item)
            match_index = next(
                (
                    index
                    for index, admission in enumerate(remaining)
                    if admission.source_content_hash == source_content_hash
                ),
                None,
            )
            if match_index is not None:
                admission = remaining.pop(match_index)
                # Exercise the producer's typed projector at binding time.  A
                # coincidental hash-shaped mapping cannot create a usable plan.
                admission.projector(item)
                entries.append(
                    _GyComparisonPlanEntry(
                        path=path,
                        owner_rule=admission.owner_rule,
                        projector=admission.projector,
                        action=admission.action,
                        predicate_provenance=admission.predicate_provenance,
                        legacy_migrator=admission.legacy_migrator,
                    )
                )
                return
            for key, child in item.items():
                walk(child, (*path, str(key)))
        elif isinstance(item, (list, tuple)):
            for index, child in enumerate(item):
                walk(child, (*path, index))

    walk(value, ())
    if remaining:
        raise ValueError("gy_comparison_live_admission_unbound")
    return GyComparisonProjectionPlan(entries=tuple(entries))


def build_gy_comparison_projection_plan_from_manifest(
    value: object,
    *,
    manifest: object,
    owner_rule_registry: Mapping[str, GyComparisonOwnerRule],
) -> GyComparisonProjectionPlan:
    """Reconstruct a projection recipe for non-authoritative integrity checks.

    This function does not establish comparison admission.  Writers and exact
    rederive checks must independently rebuild a plan from live producer
    admissions and require its manifest to equal this recipe.
    """

    if not isinstance(manifest, list) or not manifest:
        raise ValueError("gy_comparison_admission_manifest_invalid")
    entries: list[_GyComparisonPlanEntry] = []
    for row in manifest:
        if not isinstance(row, Mapping):
            raise ValueError("gy_comparison_admission_manifest_invalid")
        pointer = row.get("json_pointer")
        owner_rule = row.get("owner_rule")
        action = row.get("action")
        predicate_provenance = row.get("predicate_provenance")
        if (
            not isinstance(pointer, str)
            or not isinstance(owner_rule, str)
            or owner_rule not in owner_rule_registry
        ):
            raise ValueError("gy_comparison_admission_manifest_invalid")
        registered = owner_rule_registry[owner_rule]
        if (
            action != registered.action
            or predicate_provenance != registered.predicate_provenance
        ):
            raise ValueError("gy_comparison_admission_manifest_owner_policy_mismatch")
        path = _gy_comparison_path_from_pointer(value, pointer)
        entries.append(
            _GyComparisonPlanEntry(
                path=path,
                owner_rule=owner_rule,
                projector=registered.projector,
                action=registered.action,
                predicate_provenance=registered.predicate_provenance,
                legacy_migrator=None,
            )
        )
    plan = GyComparisonProjectionPlan(entries=tuple(entries))
    if plan.manifest != manifest:
        raise ValueError("gy_comparison_admission_manifest_not_canonical")
    plan.project(value)
    return plan


def gy_comparison_content_hash(
    value: object,
    *,
    comparison_plan: GyComparisonProjectionPlan,
) -> str:
    """Hash the owner-admitted comparison projection of a full GY record."""

    projected = comparison_plan.project(value)
    payload = json.dumps(
        projected,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def gy_artifact_self_identity_projection(value: object) -> dict[str, Any]:
    """Return the GY semantic payload for an artifact or its writer draft.

    Artifact writers project the unhashed draft immediately before assigning its
    self-identity.  Verifiers project the resulting self-identifying artifact.
    Keeping both states on this owner makes those two comparisons the same call;
    models and already-hashed mappings still require exactly one identity field.
    """

    if isinstance(value, Mapping) and not {"content_hash", "record_hash"}.intersection(value):
        payload = {str(key): item for key, item in value.items()}
    else:
        payload = serialization.artifact_self_identity_projection(value)
    projected = strip_gy_volatile_fields(payload)
    if not isinstance(projected, dict):  # pragma: no cover - mapping input is normalized above
        raise ValueError("gy_artifact_identity_projection_mapping_required")
    return projected


def overlay_gy_shared_operational_leaves(previous: object, current: object) -> object:
    """Overlay shared operational leaves while preserving the current payload shape.

    This writer operation is deliberately distinct from strict comparison
    reconciliation: governing changes and current-only branches remain live,
    and a previous-only field or sequence member is never manufactured.

    Args:
        previous: Previously persisted payload supplying admitted operational values.
        current: Live writer payload supplying shape and governing content.

    Returns:
        The current-shaped payload with shared canonically operational fields overlaid.
    """

    return _overlay_gy_shared_operational_leaves(previous, current)


def reconcile_gy_operational_leaves(
    previous: object,
    current: object,
    *,
    recording_role: Literal["first_vertical", "education", "unseen"] | None = None,
    admission_arm: Literal["controlled_at_capture", "migrated"] | None = None,
    require_exact_match: bool = False,
) -> object:
    """Preserve shared operational leaves only after semantic and shape agreement.

    The procedure is fail-closed: it rejects a semantic change or a shape drift,
    and it only copies an operational leaf that both payloads already declare.
    Mismatches report recursive paths and content identities, never raw values.
    """

    projector = strip_gy_volatile_fields
    previous_semantic = projector(previous)
    current_semantic = projector(current)
    if previous_semantic != current_semantic:
        raise _gy_operational_reconciliation_error(
            "gy_operational_reconciliation_semantic_projection_mismatch",
            previous,
            current,
            recording_role=recording_role,
            admission_arm=admission_arm,
        )
    if not _gy_payload_shape_matches(previous, current):
        raise _gy_operational_reconciliation_error(
            "gy_operational_reconciliation_shape_mismatch",
            previous,
            current,
            recording_role=recording_role,
            admission_arm=admission_arm,
        )
    if require_exact_match and previous != current:
        raise _gy_operational_reconciliation_error(
            "gy_operational_reconciliation_exact_mismatch",
            previous,
            current,
            recording_role=recording_role,
            admission_arm=admission_arm,
        )
    return overlay_gy_shared_operational_leaves(previous, current)


def reconcile_gy_comparison_projection(
    previous: object,
    current: object,
    *,
    comparison_plan: GyComparisonProjectionPlan,
    recording_role: Literal["first_vertical", "education", "unseen"] | None = None,
    admission_arm: Literal["controlled_at_capture", "migrated"] | None = None,
) -> object:
    """Preserve raw admitted evidence after producer-owned semantic agreement.

    The supplied plan is ephemeral proof that its admitted live blocks were
    resolved and validated by their canonical owners. The comparison remains
    fail-closed for every field outside those exact paths. On agreement, the
    frozen admitted blocks and shared operational leaves are retained verbatim;
    the ordinary custody hash therefore continues to bind every recorded byte.
    """

    try:
        aligned_previous = comparison_plan.migrate_admitted_blocks(previous, current)
    except GyOperationalReconciliationError:
        raise
    except ValueError as exc:
        raise _gy_operational_reconciliation_error(
            "gy_operational_reconciliation_semantic_projection_mismatch",
            previous,
            current,
            recording_role=recording_role,
            admission_arm=admission_arm,
        ) from exc
    previous_semantic = comparison_plan.project(aligned_previous)
    current_semantic = comparison_plan.project(current)
    if previous_semantic != current_semantic:
        raise _gy_operational_reconciliation_error(
            "gy_operational_reconciliation_semantic_projection_mismatch",
            previous,
            current,
            recording_role=recording_role,
            admission_arm=admission_arm,
        )
    if not _gy_payload_shape_matches(aligned_previous, current):
        raise _gy_operational_reconciliation_error(
            "gy_operational_reconciliation_shape_mismatch",
            previous,
            current,
            recording_role=recording_role,
            admission_arm=admission_arm,
        )
    reconciled = comparison_plan._preserve_aligned_admitted_blocks(
        aligned_previous,
        current,
    )
    if comparison_plan.project(reconciled) != previous_semantic:  # pragma: no cover
        raise _gy_operational_reconciliation_error(
            "gy_operational_reconciliation_semantic_projection_mismatch",
            previous,
            current,
            recording_role=recording_role,
            admission_arm=admission_arm,
        )
    return reconciled


def _gy_operational_reconciliation_error(
    code: Literal[
        "gy_operational_reconciliation_semantic_projection_mismatch",
        "gy_operational_reconciliation_shape_mismatch",
        "gy_operational_reconciliation_exact_mismatch",
    ],
    expected: object,
    observed: object,
    *,
    recording_role: Literal["first_vertical", "education", "unseen"] | None,
    admission_arm: Literal["controlled_at_capture", "migrated"] | None,
) -> GyOperationalReconciliationError:
    return GyOperationalReconciliationError(
        code,
        _GyOperationalDriftDiagnostic(
            admission_arm=admission_arm or "not_applicable",
            changed_leaves=tuple(_gy_changed_leaf_reports(expected, observed)),
            expected_frozen=_GyDriftOperandIdentity(
                content_identity=_gy_diagnostic_content_identity(expected),
                operand_role="expected_frozen",
            ),
            live_replayed=_GyDriftOperandIdentity(
                content_identity=_gy_diagnostic_content_identity(observed),
                operand_role="live_replayed",
            ),
            recording_role=recording_role or "not_applicable",
        ),
    )


def _gy_changed_leaf_reports(
    expected: object,
    observed: object,
    *,
    path: str = "",
    field_name: str | None = None,
) -> list[_GyDriftChangedLeaf]:
    if expected is _GY_DRIFT_MISSING:
        return _gy_missing_branch_leaf_reports(
            observed,
            missing_expected=True,
            path=path,
            field_name=field_name,
        )
    if observed is _GY_DRIFT_MISSING:
        return _gy_missing_branch_leaf_reports(
            expected,
            missing_expected=False,
            path=path,
            field_name=field_name,
        )
    if type(expected) is not type(observed):
        return [_gy_changed_leaf_report(expected, observed, path=path, field_name=field_name)]
    if isinstance(expected, dict) and isinstance(observed, dict):
        reports: list[dict[str, Any]] = []
        keys = sorted(set(expected) | set(observed), key=lambda key: str(key))
        for key in keys:
            child_path = _gy_json_pointer(path, str(key))
            reports.extend(
                _gy_changed_leaf_reports(
                    expected.get(key, _GY_DRIFT_MISSING),
                    observed.get(key, _GY_DRIFT_MISSING),
                    path=child_path,
                    field_name=str(key),
                )
            )
        return reports
    if isinstance(expected, (list, tuple)) and isinstance(observed, (list, tuple)):
        reports = []
        shared_length = min(len(expected), len(observed))
        for index in range(shared_length):
            reports.extend(
                _gy_changed_leaf_reports(
                    expected[index],
                    observed[index],
                    path=_gy_json_pointer(path, str(index)),
                    field_name=field_name,
                )
            )
        for index in range(shared_length, max(len(expected), len(observed))):
            reports.extend(
                _gy_changed_leaf_reports(
                    expected[index] if index < len(expected) else _GY_DRIFT_MISSING,
                    observed[index] if index < len(observed) else _GY_DRIFT_MISSING,
                    path=_gy_json_pointer(path, str(index)),
                    field_name=field_name,
                )
            )
        return reports
    if expected == observed:
        return []
    return [_gy_changed_leaf_report(expected, observed, path=path, field_name=field_name)]


def _gy_missing_branch_leaf_reports(
    present: object,
    *,
    missing_expected: bool,
    path: str,
    field_name: str | None,
) -> list[_GyDriftChangedLeaf]:
    reports: list[_GyDriftChangedLeaf] = []
    if isinstance(present, dict) and present:
        for key in sorted(present, key=lambda key: str(key)):
            reports.extend(
                _gy_missing_branch_leaf_reports(
                    present[key],
                    missing_expected=missing_expected,
                    path=_gy_json_pointer(path, str(key)),
                    field_name=str(key),
                )
            )
        return reports
    if isinstance(present, (list, tuple)) and present:
        for index, item in enumerate(present):
            reports.extend(
                _gy_missing_branch_leaf_reports(
                    item,
                    missing_expected=missing_expected,
                    path=_gy_json_pointer(path, str(index)),
                    field_name=field_name,
                )
            )
        return reports
    expected = _GY_DRIFT_MISSING if missing_expected else present
    observed = present if missing_expected else _GY_DRIFT_MISSING
    return [_gy_changed_leaf_report(expected, observed, path=path, field_name=field_name)]


def _gy_changed_leaf_report(
    expected: object,
    observed: object,
    *,
    path: str,
    field_name: str | None,
) -> _GyDriftChangedLeaf:
    return _GyDriftChangedLeaf(
        expected_frozen=_gy_leaf_identity(expected),
        live_replayed=_gy_leaf_identity(observed),
        operational=bool(field_name is not None and is_gy_content_hash_excluded_field(field_name)),
        path=path or "/",
    )


def _gy_leaf_identity(value: object) -> _GyDriftLeafIdentity:
    if value is _GY_DRIFT_MISSING:
        return _GyDriftLeafIdentity(
            content_identity="absent",
            presence="absent",
            value_type="absent",
        )
    return _GyDriftLeafIdentity(
        content_identity=_gy_diagnostic_content_identity(value),
        presence="present",
        value_type=type(value).__name__,
    )


def _gy_diagnostic_content_identity(value: object) -> str:
    payload = json.dumps(
        {"type": type(value).__name__, "value": value},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _gy_json_pointer(parent: str, segment: str) -> str:
    escaped = segment.replace("~", "~0").replace("/", "~1")
    return f"{parent}/{escaped}"


def _gy_comparison_json_pointer(path: _GyComparisonPath) -> str:
    pointer = ""
    for segment in path:
        pointer = _gy_json_pointer(pointer, str(segment))
    return pointer or "/"


def _gy_comparison_path_from_pointer(value: object, pointer: str) -> _GyComparisonPath:
    if pointer == "/":
        return ()
    if not pointer.startswith("/"):
        raise ValueError("gy_comparison_admission_pointer_invalid")
    current = value
    path: list[_GyComparisonPathSegment] = []
    for encoded in pointer[1:].split("/"):
        segment = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, Mapping):
            if segment not in current:
                raise ValueError("gy_comparison_admission_path_missing")
            path.append(segment)
            current = current[segment]
        elif isinstance(current, (list, tuple)):
            try:
                index = int(segment)
            except ValueError as exc:
                raise ValueError("gy_comparison_admission_pointer_invalid") from exc
            if index < 0 or index >= len(current):
                raise ValueError("gy_comparison_admission_path_missing")
            path.append(index)
            current = current[index]
        else:
            raise ValueError("gy_comparison_admission_path_missing")
    return tuple(path)


def _gy_payload_shape_matches(
    previous: object,
    current: object,
) -> bool:
    if isinstance(previous, dict) and isinstance(current, dict):
        return set(previous) == set(current) and all(
            _gy_payload_shape_matches(previous[key], current[key]) for key in previous
        )
    if isinstance(previous, (list, tuple)) and isinstance(current, (list, tuple)):
        return (
            type(previous) is type(current)
            and len(previous) == len(current)
            and all(
                _gy_payload_shape_matches(left, right)
                for left, right in zip(previous, current, strict=True)
            )
        )
    return type(previous) is type(current)


def _overlay_gy_shared_operational_leaves(
    previous: object,
    current: object,
) -> object:
    if isinstance(previous, Mapping) and isinstance(current, Mapping):
        return {
            key: (
                previous[key]
                if is_gy_content_hash_excluded_field(str(key)) and key in previous
                else _overlay_gy_shared_operational_leaves(previous[key], value)
                if key in previous
                else value
            )
            for key, value in current.items()
        }
    if isinstance(previous, list) and isinstance(current, list):
        return [
            _overlay_gy_shared_operational_leaves(previous[index], value)
            if index < len(previous)
            else value
            for index, value in enumerate(current)
        ]
    if isinstance(previous, tuple) and isinstance(current, tuple):
        return tuple(
            _overlay_gy_shared_operational_leaves(previous[index], value)
            if index < len(previous)
            else value
            for index, value in enumerate(current)
        )
    return current


def assert_ring2_verifier_provenance(
    value: object,
    *,
    context: dict[str, Any] | None = None,
) -> None:
    """Fail closed if a Ring-2 field is consumed without verifier provenance.

    Pydantic ``model_construct`` and ``model_copy(update=...)`` deliberately skip
    validation. Authority-bearing consumers therefore call this boundary check on
    the object they are about to persist, promote, or surface-read. The check
    serializes models to plain JSON and re-validates them with the caller's
    writer context so constructed Ring-2 fields cannot be smuggled through a
    trusted in-memory instance.
    """

    writer_role = str((context or {}).get("writer_role") or "").strip()
    if isinstance(value, BaseModel):
        model_type = type(value)
        try:
            model_type.model_validate(value.model_dump(mode="json"), context=context)
        except Exception as exc:
            raise ValueError(f"Ring-2 verifier provenance rejected: {exc}") from exc
        attempted = _non_empty_ring2_fields(value)
        if attempted and writer_role not in _VERIFIER_WRITERS:
            raise ValueError(
                "Ring-2 verifier provenance rejected for "
                f"{model_type.__name__}: {', '.join(sorted(attempted))}"
            )
        for item in value.__dict__.values():
            assert_ring2_verifier_provenance(item, context=context)
        return
    if isinstance(value, dict):
        for item in value.values():
            assert_ring2_verifier_provenance(item, context=context)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            assert_ring2_verifier_provenance(item, context=context)


def _non_empty_ring2_fields(value: BaseModel) -> list[str]:
    ring2_fields = getattr(type(value), "ring2_fields", frozenset())
    attempted: list[str] = []
    for field in ring2_fields:
        item = getattr(value, field, None)
        if item not in (None, [], {}):
            attempted.append(str(field))
    return attempted


class GyWaistModel(BaseModel):
    """Strict frozen base model with field-level Ring-2 write checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    ring2_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def _reject_untrusted_ring2_writes(cls, data: object, info: ValidationInfo) -> object:
        if not isinstance(data, dict) or not cls.ring2_fields:
            return data
        writer_role = str((info.context or {}).get("writer_role") or "").strip()
        if writer_role in _VERIFIER_WRITERS:
            return data
        attempted = [
            field
            for field in cls.ring2_fields
            if field in data and data[field] not in (None, [], {})
        ]
        if attempted:
            raise ValueError(
                "verifier-only Ring-2 field write rejected for "
                f"{cls.__name__}: {', '.join(sorted(attempted))}"
            )
        return data


class OperationClass(StrEnum):
    """Operation verbs available to the GY workspace loop."""

    DISCOVER = "DISCOVER"
    ACQUIRE = "ACQUIRE"
    BIND = "BIND"
    TRANSFORM = "TRANSFORM"
    ESTIMATE = "ESTIMATE"
    SIMULATE = "SIMULATE"
    TRANSPORT = "TRANSPORT"
    VERIFY = "VERIFY"
    REFINE = "REFINE"
    LOWER = "LOWER"
    DECOMPOSE = "DECOMPOSE"
    COMPOSE = "COMPOSE"
    ELICIT = "ELICIT"
    ESCALATE = "ESCALATE"
    ABSTAIN = "ABSTAIN"


class SearchTerminalKind(StrEnum):
    """Typed terminal states for anytime GY workspace exits."""

    A_SPEC_GAP = "a_spec_gap"
    TOOL_FAILURE = "tool_failure"
    COMPOSITION_INVALID = "composition_invalid"
    RECURSIVE_BLOCKED = "recursive_blocked"
    SEARCH_CEILING_REPAIR_REQUIRED = "search_ceiling_repair_required"
    HUMAN_DECISION_REQUIRED = "human_decision_required"
    ACQUISITION_REQUIRED = "acquisition_required"
    BUDGET_EXHAUSTED = "budget_exhausted"
    FRONTIER_STABLE = "frontier_stable"
    GROUNDED_ADMISSIBLE = "grounded_admissible"
    GROUNDED_PARTIAL_ADMISSIBLE = "grounded_partial_admissible"
    GROUNDED_ABSTENTION = "grounded_abstention"


class PromotionObligationClass(StrEnum):
    """Declared N9 obligation-class denominator at this promotion rule version."""

    SYNTAX = "syntax"
    TYPE = "type"
    SLOT = "slot"
    PARAM = "param"
    COUPLING = "coupling"
    EFFECT = "effect"
    IDENTIFICATION = "identification"
    CALIBRATION = "calibration"
    MEASUREMENT = "measurement"
    DATA = "data"
    IMPLEMENTATION = "implementation"
    EQUILIBRIUM = "equilibrium"
    NORMATIVE = "normative"
    EVAL_SAFETY = "eval_safety"
    VALUE = "value"


class PromotionFailClosedReason(StrEnum):
    """Typed N9 fail-closed reasons."""

    SINGLE_OBLIGATION_FAIL = "single_obligation_fail"
    JOINT_OBLIGATION_INCONSISTENCY = "joint_obligation_inconsistency"
    PROOF_TIMEOUT = "proof_timeout"
    SCOPE_INSUFFICIENT = "scope_insufficient"
    UNKNOWN = "unknown"


class PromotionObligationStatus(StrEnum):
    """Status lattice for one compiled N9 obligation."""

    SATISFIED = "satisfied"
    FAILED = "failed"
    UNKNOWN = "unknown"
    SCOPE_INSUFFICIENT = "scope_insufficient"
    NOT_APPLICABLE_DATA_ONLY = "not_applicable_data_only"


type PromotionObligationRole = Literal["class_gate", "decisive_predicate"]
type PromotionObligationIdentityProvenance = Literal["recomputed"]

PROMOTION_OBLIGATION_IDENTITY_RULE_VERSION = (
    "polisyos.policy_design_case.layer3_gy.n9_obligation_instance_identity.v1"
)


class PromotionGateId(StrEnum):
    """Real gate owners consumed by the canonical N9 sequence."""

    GY_WAIST = "gy_waist"
    RING2_WAIST = "ring2_waist"
    CGF_GROUNDING = "cgf_grounding"
    CG2_BIND_PROMOTABILITY = "cg2_bind_promotability"
    GYK_ENTAILMENT = "gyk_entailment"
    N5_COUPLING = "n5_coupling"
    N8_VALUE = "n8_value"
    N8_CALIBRATION = "n8_calibration"
    N8_TRANSPORT = "n8_transport"
    S6_BLIND_SPOT = "s6_blind_spot"
    S7_MANDATE_DELEGATION = "s7_mandate_delegation"
    S8_VALUE_POSTURE = "s8_value_posture"
    G4_GOVERNED_PROMOTION = "g4_governed_promotion"
    GY_O0_EVAL_SAFETY = "gy_o0_eval_safety"


PROMOTION_RISK_CONDITIONALITY_CAVEAT = (
    "P(false promotion | maintained assumptions) <= delta is conditional on obligation "
    "completeness + validator soundness (the spec's A4 = our open P29). Exact rational "
    "spend in the bound N11 confidence-ledger projection is authoritative; these floats "
    "are display-only."
)
_PROMOTION_ROLE_POLARITY = {
    "promotion": "false_accept",
    "refusal": "confident_wrong_refusal",
    "acquisition": "confident_wrong_refusal",
    "admission": "confident_wrong_admission",
    "promotion_conformance": "conformance_only",
}


class PromotionRiskSpendRecord(GyWaistModel):
    """Display projection of an owner-recomputed N11 ledger check."""

    obligation_class: PromotionObligationClass
    certificate_ref: str = Field(..., min_length=1, max_length=300)
    instrument: str = Field(..., min_length=1, max_length=120)
    certificate_role: Literal[
        "promotion",
        "refusal",
        "acquisition",
        "admission",
        "promotion_conformance",
    ]
    claim_polarity: Literal[
        "false_accept",
        "confident_wrong_refusal",
        "confident_wrong_admission",
        "conformance_only",
    ]
    declared_delta_spend: float = Field(ge=0.0)
    deterministic_proof: bool = False
    n11_confidence_ledger_ref: str = Field(
        ...,
        max_length=300,
        pattern=r"^confidence-check:sha256:[0-9a-f]{64}$",
    )

    @model_validator(mode="after")
    def _role_matches_error_polarity(self) -> PromotionRiskSpendRecord:
        if self.claim_polarity != _PROMOTION_ROLE_POLARITY[self.certificate_role]:
            raise ValueError("certificate_role_claim_polarity_mismatch")
        return self


class PromotionRiskSpendSummary(GyWaistModel):
    """Display-only decimal projection of exact N11 rational accounting."""

    total_declared_delta: float = Field(ge=0.0)
    budget_delta: float = Field(ge=0.0)
    within_budget: bool
    spend_records: list[PromotionRiskSpendRecord] = Field(default_factory=list, max_length=80)
    caveat: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _require_exact_conditionality_caveat(self) -> PromotionRiskSpendSummary:
        if self.caveat != PROMOTION_RISK_CONDITIONALITY_CAVEAT:
            raise ValueError("promotion_risk_conditionality_caveat_mismatch")
        return self


class PromotionObligationDraft(GyWaistModel):
    """One owner-produced N9 class result before run-scoped identity finalization."""

    obligation_class: PromotionObligationClass
    gate_id: PromotionGateId
    status: PromotionObligationStatus
    reason: PromotionFailClosedReason | None = None
    owner_ref: str = Field(..., min_length=1, max_length=300)
    detail: str = Field(..., min_length=1, max_length=1000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=40)
    risk_spend: PromotionRiskSpendRecord | None = None
    semantic_scope: Literal["real_semantics", "scope_insufficient", "data_only_not_required"] = (
        "real_semantics"
    )

    @model_validator(mode="after")
    def _fail_closed_reason_matches_status(self) -> PromotionObligationDraft:
        if (
            self.status
            in {
                PromotionObligationStatus.FAILED,
                PromotionObligationStatus.UNKNOWN,
                PromotionObligationStatus.SCOPE_INSUFFICIENT,
            }
            and self.reason is None
        ):
            raise ValueError("unsatisfied_promotion_obligation_requires_reason")
        if (
            self.status == PromotionObligationStatus.SATISFIED
            and self.semantic_scope == "scope_insufficient"
        ):
            raise ValueError("obligation_class_vacuously_passed")
        return self


def promotion_obligation_instance_id(
    *,
    obligation_role: PromotionObligationRole,
    obligation_class: PromotionObligationClass,
    gate_id: PromotionGateId,
    source_obligation_ref: str,
    source_obligation_content_hash: str,
    instance_scope_content_hash: str,
) -> str:
    """Derive one obligation identity from its governed source and run scope."""

    return gy_content_hash(
        {
            "rule_version": PROMOTION_OBLIGATION_IDENTITY_RULE_VERSION,
            "obligation_role": obligation_role,
            "obligation_class": obligation_class.value,
            "gate_id": gate_id.value,
            "source_obligation_ref": source_obligation_ref,
            "source_obligation_content_hash": source_obligation_content_hash,
            "instance_scope_content_hash": instance_scope_content_hash,
        }
    )


class PromotionObligationRecord(PromotionObligationDraft):
    """Canonical N9 row with deterministic identity over governed source content."""

    obligation_role: PromotionObligationRole
    source_obligation_ref: str = Field(..., min_length=1, max_length=500)
    source_obligation_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    instance_scope_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    identity_provenance: PromotionObligationIdentityProvenance
    obligation_instance_id: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @classmethod
    def from_draft(
        cls,
        draft: PromotionObligationDraft,
        *,
        obligation_role: PromotionObligationRole,
        source_obligation_ref: str,
        source_obligation_content_hash: str,
        instance_scope_content_hash: str,
    ) -> PromotionObligationRecord:
        """Finalize an owner outcome after all class-level mutations are complete."""

        identity = promotion_obligation_instance_id(
            obligation_role=obligation_role,
            obligation_class=draft.obligation_class,
            gate_id=draft.gate_id,
            source_obligation_ref=source_obligation_ref,
            source_obligation_content_hash=source_obligation_content_hash,
            instance_scope_content_hash=instance_scope_content_hash,
        )
        return cls(
            **draft.model_dump(mode="python"),
            obligation_role=obligation_role,
            source_obligation_ref=source_obligation_ref,
            source_obligation_content_hash=source_obligation_content_hash,
            instance_scope_content_hash=instance_scope_content_hash,
            identity_provenance="recomputed",
            obligation_instance_id=identity,
        )

    @model_validator(mode="after")
    def _identity_is_recomputed_from_governing_content(self) -> PromotionObligationRecord:
        expected = promotion_obligation_instance_id(
            obligation_role=self.obligation_role,
            obligation_class=self.obligation_class,
            gate_id=self.gate_id,
            source_obligation_ref=self.source_obligation_ref,
            source_obligation_content_hash=self.source_obligation_content_hash,
            instance_scope_content_hash=self.instance_scope_content_hash,
        )
        if self.obligation_instance_id != expected:
            raise ValueError("promotion_obligation_instance_identity_mismatch")
        return self


def _jsonish(value: object) -> object:
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


class _DictAccessModel(GyWaistModel):
    """Small adapter for legacy dict-style reads during typed-contract migration."""

    def __getitem__(self, key: str) -> object:
        return _jsonish(getattr(self, key))

    def get(self, key: str, default: object | None = None) -> object | None:
        if not hasattr(self, key):
            return default
        return _jsonish(getattr(self, key))


class SearchTerminalState(_DictAccessModel):
    """Typed terminal state selected by deterministic anytime-exit precedence."""

    kind: SearchTerminalKind
    reason: str = Field(..., min_length=1, max_length=800)
    blocking_obligations: list[str] = Field(default_factory=list)
    budget_kind: str | None = None
    costed_plan: dict[str, Any] | None = None
    data_need_spec: dict[str, Any] | None = None


class ArtifactRef(GyWaistModel):
    """Content-addressed reference for one immutable GY artifact."""

    artifact_id: str = Field(..., pattern=GY_ARTIFACT_ID_PATTERN)
    artifact_type: str = Field(..., min_length=1, max_length=80)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    schema_ref: str = Field(..., min_length=1, max_length=200)
    uri: str = Field(..., min_length=1, max_length=300)
    version: str = Field(..., min_length=1, max_length=80)

    @classmethod
    def from_payload(
        cls,
        *,
        artifact_id: str,
        artifact_type: str,
        payload: object,
        schema_ref: str,
        uri: str,
        version: str,
    ) -> ArtifactRef:
        """Build an artifact ref whose hash uses GY canonical evidence semantics."""

        return cls(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_hash=gy_content_hash(payload),
            schema_ref=schema_ref,
            uri=uri,
            version=version,
        )


class ArtifactEnvelopeVerification(GyWaistModel):
    """Verification refs attached to an artifact envelope."""

    ring2_fields: ClassVar[frozenset[str]] = frozenset({"latest_promotion_result"})

    latest_applicability_result: str | None = None
    latest_promotion_result: str | None = None


class ArtifactEnvelope(GyWaistModel):
    """Ring-1 artifact carrier with verifier-only Ring-2 authority fields."""

    ring2_fields: ClassVar[frozenset[str]] = frozenset(
        {"authority_boundary", "certified_operation_envelope"}
    )

    ref: ArtifactRef
    payload_ref: str
    payload_schema_ref: str
    lifecycle_state: Literal["shadow", "verified", "promoted", "rejected", "superseded", "archived"]
    created_by: dict[str, str]
    producer_operation: dict[str, str]
    input_artifacts: list[ArtifactRef] = Field(default_factory=list)
    producer_roots: list[ArtifactRef] = Field(default_factory=list)
    certified_operation_envelope: CertifiedOperationEnvelope | None = None
    authority_boundary: AuthorityBoundary | None = None
    obligations: list[str] = Field(default_factory=list)
    verification: ArtifactEnvelopeVerification = Field(default_factory=ArtifactEnvelopeVerification)


class PortSpec(GyWaistModel):
    """Typed operation port; provided authority is verifier-only."""

    ring2_fields: ClassVar[frozenset[str]] = frozenset({"provided_authority"})

    port_id: str = Field(..., pattern=ID_PATTERN)
    direction: Literal["consumes", "produces", "requires", "provides"]
    port_type: str = Field(..., min_length=1, max_length=80)
    claim_shape: dict[str, Any]
    multiplicity: dict[str, int]
    constraints: dict[str, Any] = Field(default_factory=dict)
    required_authority: dict[str, Any] | None = None
    provided_authority: AuthorityBoundary | None = None


class OperationContract(GyWaistModel):
    """Coarse operation contract discovered from engine registries."""

    operation_id: str = Field(..., pattern=ID_PATTERN)
    operation_version: str = Field(..., min_length=1, max_length=80)
    operation_class: OperationClass
    consumes: list[PortSpec]
    produces: list[PortSpec]
    formal_preconditions: list[dict[str, Any]] = Field(default_factory=list)
    allowed_internal_execution: list[
        Literal[
            "foundry_method",
            "foundry_method_chain",
            "llm_agent_plan",
            "tool_call",
            "human_request",
        ]
    ]
    implementation_refs: list[dict[str, str]]
    cost_model: dict[str, Any]
    authority_transform: dict[str, Any]
    failure_modes: list[str] = Field(default_factory=list)
    repair_options: list[OperationClass] = Field(default_factory=list)


class OperationInvocationRecord(GyWaistModel):
    """Replay-visible execution record for one operation invocation."""

    invocation_id: str = Field(..., pattern=ID_PATTERN)
    operation_id: str
    operation_version: str
    workspace_id: str
    cycle_index: int = Field(ge=0)
    selected_by: dict[str, str]
    selection_rationale_ref: str | None = None
    input_artifacts: list[ArtifactRef]
    parameters: dict[str, Any]
    internal_trace: dict[str, Any]
    tool_calls: list[str] = Field(default_factory=list)
    human_requests: list[str] = Field(default_factory=list)
    output_artifacts: list[ArtifactRef]
    applicability_result: str
    budget_delta: dict[str, Any]
    status: Literal["started", "completed", "failed", "repair_required", "cancelled"]


class ApplicabilityResult(GyWaistModel):
    """Deterministic formal-gate verdict for an operation."""

    result_id: str = Field(..., pattern=ID_PATTERN)
    invocation_id: str
    status: Literal["applicable", "not_applicable", "applicable_with_warnings", "repair_required"]
    checked_preconditions: list[dict[str, Any]]
    failed_preconditions: list[dict[str, Any]]
    type_errors: list[dict[str, Any]]
    repair_options: list[dict[str, Any]]


class BudgetVector(GyWaistModel):
    """Vector budget used by the GY loop."""

    compute: dict[str, Any] = Field(default_factory=dict)
    acquisition: dict[str, Any] = Field(default_factory=dict)
    expert_attention: dict[str, Any] = Field(default_factory=dict)
    calendar: dict[str, Any] = Field(default_factory=dict)
    novelty: dict[str, Any] = Field(default_factory=dict)
    recursion: dict[str, Any] = Field(default_factory=dict)
    search_quality: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def slice0(cls) -> BudgetVector:
        """Return the minimal Slice-0 budget vector allowed by the GY plan."""

        return cls(
            compute={
                "max_operation_invocations": 3,
                "max_wall_seconds": 30,
                "hard": True,
            },
            search_quality={
                "min_recall_at_known_seeds": 1.0,
                "required_source_classes": ["official"],
            },
        )


class WorkspaceContract(GyWaistModel):
    """Blackboard workspace contract for one GY loop run."""

    workspace_id: str = Field(..., pattern=ID_PATTERN)
    parent_workspace_id: str | None = None
    intent_ref: ArtifactRef
    scope: dict[str, Any]
    artifact_graph_ref: str
    constraint_store_ref: str
    agenda_ref: str
    frontier_ref: str
    allowed_operations: list[str]
    budget: BudgetVector
    recursion_policy: dict[str, Any] = Field(
        default_factory=lambda: {
            "max_depth": 0,
            "max_child_workspaces": 0,
            "decompose_allowed": False,
        }
    )
    exit_requirements: dict[str, bool] = Field(
        default_factory=lambda: {
            "require_search_exit_contract": True,
            "require_incompleteness_record": True,
            "require_authority_boundaries_for_promotion": True,
        }
    )


class SearchLedgerEvent(GyWaistModel):
    """W3C-PROV-shaped event in the GY search ledger."""

    ring2_fields: ClassVar[frozenset[str]] = frozenset({"authority_delta"})

    event_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    cycle_index: int = Field(ge=0)
    event_type: str
    actor: dict[str, str]
    input_artifacts: list[ArtifactRef]
    output_artifacts: list[ArtifactRef]
    operation_invocation_ref: str | None = None
    decision_record_ref: str | None = None
    budget_delta: dict[str, Any] | None = None
    authority_delta: dict[str, Any] | None = None
    created_obligations: list[str]
    timestamp: str


class AuthorityDerivationTrace(Layer2ReadinessModel):
    """Trace proving verifier authority is derived, not copied from operation hints."""

    operation_invocation_id: str = Field(..., pattern=ID_PATTERN)
    output_artifact_ref: ArtifactRef
    declared_authority_transform: dict[str, Any]
    computed_evidence_kind: EvidenceKind
    computed_decision_grade: DecisionGrade
    producer_root_classes: list[str]
    method_classification: str
    applicability_result_ref: str
    calibration_refs: list[str] = Field(default_factory=list)
    counterexamples_closed: list[str] = Field(default_factory=list)
    certified_envelope_ref: str | None = None
    unresolved_blockers: list[str] = Field(default_factory=list)
    resulting_authority_boundary_ref: str
    transform_mismatch_disposition: Literal["matched", "downgraded", "rejected", "upgraded"]
    promotion_sequence_ref: str | None = Field(default=None, max_length=300)
    gate_outcome_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    confidence_ledger_scope_ref: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
    )
    confidence_ledger_head_id: str | None = Field(
        default=None,
        pattern=(
            r"^(?:confidence-event|confidence-ledger-root|confidence-run-root|confidence-slot):"
            r"sha256:[0-9a-f]{64}$"
        ),
    )
    confidence_ledger_receipt_id: str | None = Field(
        default=None,
        pattern=r"^confidence-ledger:sha256:[0-9a-f]{64}$",
    )
    confidence_ledger_projection_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    risk_spend_total: float = Field(default=0.0, ge=0.0)
    risk_budget_delta: float | None = Field(default=None, ge=0.0)
    trace_content_hash: str | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _reject_self_promotion(self) -> AuthorityDerivationTrace:
        if self.promotion_sequence_ref is not None:
            required_values = {
                "confidence_ledger_scope_ref": self.confidence_ledger_scope_ref,
                "confidence_ledger_head_id": self.confidence_ledger_head_id,
                "confidence_ledger_receipt_id": self.confidence_ledger_receipt_id,
                "confidence_ledger_projection_hash": self.confidence_ledger_projection_hash,
                "risk_budget_delta": self.risk_budget_delta,
            }
            missing = [name for name, value in required_values.items() if value is None]
            if "risk_spend_total" not in self.model_fields_set:
                missing.append("risk_spend_total")
            if missing:
                raise ValueError(
                    "promotion_trace_confidence_ledger_binding_missing:" + ",".join(sorted(missing))
                )
            if (
                self.risk_budget_delta is not None
                and self.risk_spend_total > self.risk_budget_delta
            ):
                raise ValueError("promotion_trace_risk_spend_exceeds_budget")
        requested_kind = self.declared_authority_transform.get("requested_evidence_kind")
        requested_grade = self.declared_authority_transform.get("requested_decision_grade")
        if self.transform_mismatch_disposition not in {"matched", "downgraded", "rejected"}:
            raise ValueError("authority_transform hints cannot self-promote")
        kind_self_promotes = isinstance(
            requested_kind, str
        ) and not _computed_evidence_covers_request(
            computed=self.computed_evidence_kind,
            requested=requested_kind,
        )
        grade_self_promotes = isinstance(requested_grade, str) and _DECISION_GRADE_RANK.get(
            requested_grade, 0
        ) > _DECISION_GRADE_RANK.get(self.computed_decision_grade, 0)
        if self.transform_mismatch_disposition == "matched" and (
            kind_self_promotes or grade_self_promotes
        ):
            raise ValueError("authority_transform hints cannot self-promote")
        if (
            requested_grade == "decision_admissible"
            and self.computed_decision_grade == "decision_admissible"
            and self.unresolved_blockers
        ):
            raise ValueError("authority_transform hints cannot self-promote past blockers")
        return self


class FrontierSnapshot(GyWaistModel):
    """Anytime snapshot of promoted, shadow, and rejected frontier artifacts."""

    snapshot_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    cycle_index: int = Field(ge=0)
    promoted_candidates: list[ArtifactRef] = Field(default_factory=list)
    shadow_candidates: list[ArtifactRef] = Field(default_factory=list)
    rejected_candidates: list[dict[str, Any]] = Field(default_factory=list)
    dominated_candidates: list[dict[str, Any]] = Field(default_factory=list)
    current_best: list[ArtifactRef] = Field(default_factory=list)
    frontier_metrics: dict[str, Any] = Field(default_factory=dict)


class SearchCoverageRecord(_DictAccessModel):
    """What the Slice/search process did and did not cover."""

    operations_attempted: list[str] = Field(default_factory=list)
    operations_not_attempted: list[dict[str, Any]] = Field(default_factory=list)
    methods_attempted: list[str] = Field(default_factory=list)
    source_classes_checked: list[str] = Field(default_factory=list)
    source_classes_missing: list[dict[str, Any]] = Field(default_factory=list)
    jurisdictions_checked: list[str] = Field(default_factory=list)
    time_horizons_checked: list[str] = Field(default_factory=list)


class SearchQualityRecord(_DictAccessModel):
    """Search-quality facts that separate domain limits from search failure."""

    recall_at_known_seeds: float = Field(ge=0, le=1)
    known_seeds_missed: list[str] = Field(default_factory=list)
    freshness_ok: bool
    stale_source_classes: list[str] = Field(default_factory=list)
    semantic_benchmark_run: dict[str, Any] | None = None


class SearchUnresolvedRecord(_DictAccessModel):
    """Outstanding blockers exposed by an anytime exit."""

    counterexamples: list[dict[str, Any]] = Field(default_factory=list)
    missing_data: list[dict[str, Any]] = Field(default_factory=list)
    unmet_required_ports: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_couplings: list[dict[str, Any]] = Field(default_factory=list)
    human_questions: list[dict[str, Any]] = Field(default_factory=list)


class SearchBudgetRecord(_DictAccessModel):
    """Budget ledger slice attached to SearchIncompletenessRecord."""

    consumed: dict[str, Any]
    remaining: dict[str, Any]
    exhausted: list[str] = Field(default_factory=list)


class SearchNextBestAction(_DictAccessModel):
    """Typed next action candidate used by VOI and acquisition terminals."""

    operation_proposal_ref: str
    estimated_voi: float = Field(ge=0)
    estimated_cost: Any
    reason_not_taken: str
    data_need_spec: dict[str, Any] | None = None
    costed_plan: dict[str, Any] | None = None


class SearchIncompletenessRecord(GyWaistModel):
    """Honesty artifact explaining what search did and did not cover."""

    record_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    coverage: SearchCoverageRecord
    search_quality: SearchQualityRecord
    unresolved: SearchUnresolvedRecord
    budget: SearchBudgetRecord
    next_best_actions: list[SearchNextBestAction]
    ceiling_classification: Literal["domain_ceiling", "search_ceiling", "mixed", "unknown"]


class VOISelectionAudit(GyWaistModel):
    """Auditable value-of-information selection for anytime continuation or exit."""

    audit_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    selected_terminal: SearchTerminalKind
    candidates: list[dict[str, Any]]
    selected_action_ref: str | None = None
    continuation_allowed: bool
    decision_rule_ref: str
    threshold: float | None = Field(default=None, ge=0)
    notes: list[str] = Field(default_factory=list)
    candidate_actions: list[dict[str, Any]] = Field(default_factory=list)
    agent_suggested_scores: dict[str, Any] = Field(default_factory=dict)
    normalized_scores: dict[str, Any] = Field(default_factory=dict)
    deterministic_voi_inputs: dict[str, Any] = Field(default_factory=dict)
    rejected_or_clipped_inputs: list[dict[str, Any]] = Field(default_factory=list)
    selected_action: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    authority_gain_basis: dict[str, Any] = Field(default_factory=dict)
    decision_value_basis: dict[str, Any] = Field(default_factory=dict)
    cost_basis: dict[str, Any] = Field(default_factory=dict)
    bias_probe_result: dict[str, Any] = Field(default_factory=dict)


class SearchBlockerRecord(GyWaistModel):
    """Typed REFINE/search blocker with replayable frontier and repair context."""

    blocker_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    operation_class: OperationClass
    blocked_port: str = Field(..., min_length=1, max_length=200)
    missing_input: str = Field(..., min_length=1, max_length=200)
    reason: str = Field(..., min_length=1, max_length=800)
    frontier_snapshot_ref: str | None = None
    applicability_result_ref: str | None = None
    repair_options: list[dict[str, Any]] = Field(default_factory=list)
    producer_missing_label: (
        Literal[
            "producer_missing",
            "bridge_missing",
            "artifact_missing",
            "verification_missing",
            "semantic_test_missing",
        ]
        | None
    ) = None
    severity: Literal["repair_required", "blocks_authority", "blocks_execution"] = "repair_required"


class AgentDecisionRecord(GyWaistModel):
    """Ring-1 agent event; agents propose candidates and never write authority."""

    decision_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    invocation_id: str
    role: Literal["pi", "drafter", "critic", "tool_loop"]
    observed_refs: list[ArtifactRef] = Field(default_factory=list)
    candidate_operations: list[OperationClass] = Field(default_factory=list)
    selected_proposal_ref: str | None = None
    tool_calls: list[str] = Field(default_factory=list)
    candidate_only: bool = True
    status: Literal["completed", "repair_required", "blocked", "failed"]
    rationale: str = Field(..., min_length=1, max_length=1200)
    model_ref: str | None = None
    input_context_refs: list[str] = Field(default_factory=list)
    produced_candidate_refs: list[ArtifactRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def _enforce_candidate_firewall(self) -> AgentDecisionRecord:
        if self.candidate_only is not True:
            raise ValueError("AgentDecisionRecord is candidate-only; agents cannot write authority")
        return self


class MethodPlan(GyWaistModel):
    """Ring-1 method proposal assembled by an agent or adapter trajectory."""

    plan_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    proposed_by_ref: str
    operation_classes: list[OperationClass]
    method_refs: list[str] = Field(default_factory=list)
    consumes: list[dict[str, Any]] = Field(default_factory=list)
    produces: list[dict[str, Any]] = Field(default_factory=list)
    authority_transform: dict[str, Any]
    admission_state: Literal["candidate_only", "shadow", "rejected"] = "candidate_only"


class MethodOutputConsumptionRecord(GyWaistModel):
    """Proof that ESTIMATE/SIMULATE consumed real Foundry method outputs."""

    consumption_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    operation_invocation_id: str
    operation_class: OperationClass
    consumed_method_output_refs: list[ArtifactRef] = Field(default_factory=list)
    consumed_method_evidence_refs: list[ArtifactRef] = Field(default_factory=list)
    dag_consumed_method_outputs_count: int = Field(ge=0)
    measurement_root_refs: list[ArtifactRef] = Field(default_factory=list)
    constraint_store_ref: str | None = None

    @model_validator(mode="after")
    def _require_consumed_outputs(self) -> MethodOutputConsumptionRecord:
        if (
            self.dag_consumed_method_outputs_count < 1
            or not self.consumed_method_output_refs
            or not self.consumed_method_evidence_refs
        ):
            raise ValueError(
                "MethodOutputConsumptionRecord requires at least one consumed method output"
            )
        if self.dag_consumed_method_outputs_count != len(self.consumed_method_output_refs):
            raise ValueError("dag_consumed_method_outputs_count must match consumed outputs")
        return self


class SearchExitContract(GyWaistModel):
    """Typed terminal contract for every GY workspace run."""

    exit_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str
    cycle_index: int = Field(ge=0)
    terminal_state: SearchTerminalState
    frontier_snapshot: FrontierSnapshot
    incompleteness_record: SearchIncompletenessRecord
    budget_ledger: dict[str, Any]
    output_artifacts: list[ArtifactRef]
    authority_boundary: AuthorityBoundary | None = None
    next_best_actions: list[SearchNextBestAction] = Field(default_factory=list)
    evidence_kind: EvidenceKind | None = None
    decision_grade: DecisionGrade = "unsupported"
    evidence_ladder_rung: EvidenceKind | Literal["none"] = "none"

    @model_validator(mode="before")
    @classmethod
    def _derive_outcome_authority_projection(cls, value: object) -> object:
        """Derive the outcome authority axes from the verifier-written boundary."""

        if not isinstance(value, dict):
            return value
        payload = dict(value)
        boundary = payload.get("authority_boundary")
        if isinstance(boundary, AuthorityBoundary):
            evidence_kind = boundary.evidence_kind
            decision_grade = boundary.decision_grade or "unsupported"
        elif isinstance(boundary, dict):
            evidence_kind = boundary.get("evidence_kind")
            decision_grade = boundary.get("decision_grade") or "unsupported"
        else:
            evidence_kind = None
            decision_grade = "unsupported"
        derived = {
            "evidence_kind": evidence_kind,
            "decision_grade": decision_grade,
            "evidence_ladder_rung": evidence_kind or "none",
        }
        for field, expected in derived.items():
            if field in payload and payload[field] != expected:
                raise ValueError(
                    f"{field} must be derived from authority_boundary; expected {expected!r}"
                )
            payload[field] = expected
        return payload


class ObligationRecord(GyWaistModel):
    """Open obligation raised by verifier, search, or composition."""

    obligation_id: str = Field(..., pattern=ID_PATTERN)
    obligation_type: str
    raised_by: dict[str, Any]
    blocks: list[dict[str, Any]]
    description: str
    severity: Literal[
        "informational",
        "blocks_promotion",
        "blocks_composition",
        "blocks_decision",
    ]
    resolution_options: list[dict[str, Any]]
    status: Literal["open", "resolved", "escalated", "accepted_as_limit"]


class CouplingDeclaration(_DictAccessModel):
    """Child-declared coupling hypothesis; the graph classifier remains authoritative."""

    from_port: str = Field(..., min_length=1, max_length=200)
    to_port: str = Field(..., min_length=1, max_length=200)
    coupling_kind: Literal[
        "independent",
        "sequential",
        "shared_resource",
        "feedback",
        "mutually_exclusive",
        "unknown",
    ]
    rationale_ref: str = Field(..., min_length=1, max_length=300)


class SubDesignContract(GyWaistModel):
    """Assume-guarantee export from a child Workspace to its parent.

    Authority is carried only by ``PortSpec.provided_authority`` on provided
    ports. Parent workspaces may audit ``internal_trace_ref`` but cannot use it
    as an authority shortcut.
    """

    subdesign_id: str = Field(..., pattern=ID_PATTERN)
    workspace_id: str = Field(..., min_length=1, max_length=120)
    parent_workspace_id: str | None = Field(default=None, max_length=120)
    scope: dict[str, Any]
    provides: list[PortSpec] = Field(default_factory=list)
    requires: list[PortSpec] = Field(default_factory=list)
    coupling_declarations: list[CouplingDeclaration] = Field(default_factory=list)
    producer_roots: list[ArtifactRef] = Field(default_factory=list)
    search_exit: SearchExitContract
    unresolved_obligations: list[ObligationRecord] = Field(default_factory=list)
    internal_trace_ref: str = Field(..., min_length=1, max_length=300)

    @model_validator(mode="after")
    def _authority_lives_on_ports(self) -> SubDesignContract:
        if self.search_exit.authority_boundary is not None and any(
            port.provided_authority is not None for port in self.provides
        ):
            return self
        if self.search_exit.authority_boundary is not None and not any(
            port.provided_authority is not None for port in self.provides
        ):
            raise ValueError("SubDesignContract authority must be exported on ports")
        return self


class CompositionGateResult(_DictAccessModel):
    """Stage-1 coupling-gate result bridged from the S5 composition owner."""

    verdict: Literal[
        "valid",
        "requires_joint_workspace",
        "requires_capacity_aggregation",
        "requires_system_dynamics",
        "invalid",
    ]
    blocking_edges: list[str] = Field(default_factory=list)
    invalid_reason: str | None = None
    coupling_classification_ref: str | None = None
    decomposition_ref: str | None = None
    composition_receipt_ref: str | None = None
    system_dynamics_requirement_ref: str | None = None


class AuthorityFlowResult(_DictAccessModel):
    """Stage-2 per-port authority-flow result."""

    from_port: str = Field(..., min_length=1, max_length=200)
    to_port: str = Field(..., min_length=1, max_length=200)
    resulting_authority: AuthorityBoundary
    rationale_ref: str = Field(..., min_length=1, max_length=300)
    coupling_kind: str = Field(..., min_length=1, max_length=80)


class EmergentClaimGroundingResult(_DictAccessModel):
    """Stage-3 grounding result for a program-level claim."""

    claim_ref: str = Field(..., min_length=1, max_length=300)
    grounding_status: Literal["grounded", "simulation_only", "missing", "invalid", "unresolved"]
    required_grounding: list[
        Literal[
            "capacity_aggregation",
            "sequencing_consistency",
            "system_dynamics",
            "equilibrium_check",
            "cross_chapter_counterexample_search",
        ]
    ] = Field(default_factory=list)
    resulting_authority: AuthorityBoundary | None = None
    grounding_refs: list[str] = Field(default_factory=list)
    raw_evidence_line_count: int | None = Field(default=None, ge=0)
    effective_independent_evidence_count: int | None = Field(default=None, ge=0)
    limiting_deficits: list[str] = Field(default_factory=list)


class CompositionCertificate(GyWaistModel):
    """Loop-facing certificate produced by the S5 composition engine bridge."""

    certificate_id: str = Field(..., pattern=ID_PATTERN)
    parent_workspace_id: str = Field(..., min_length=1, max_length=120)
    input_subdesigns: list[str] = Field(default_factory=list)
    target_policy_program_ref: str | None = Field(default=None, max_length=300)
    candidate_ref: str | None = Field(default=None, max_length=300)
    claim_refs: list[str] = Field(default_factory=list, max_length=80)
    coupling_gate: CompositionGateResult
    authority_flow: list[AuthorityFlowResult] = Field(default_factory=list)
    emergent_claims: list[EmergentClaimGroundingResult] = Field(default_factory=list)
    unresolved_obligations: list[ObligationRecord] = Field(default_factory=list)
    verdict: Literal["composable", "composable_with_limits", "not_composable"]
    composition_receipt_ref: str | None = None
    composition_law_check_ref: str | None = None
    rule_version_ref: str = Field(..., min_length=1, max_length=300)
    schema_version: str = GY_WAIST_SCHEMA_VERSION

    @model_validator(mode="after")
    def _require_receipt_for_composable_verdict(self) -> CompositionCertificate:
        if self.verdict != "not_composable" and not self.composition_receipt_ref:
            raise ValueError("composable CompositionCertificate requires CompositionReceipt bridge")
        return self


__all__ = [
    "GY_ARTIFACT_ID_PATTERN",
    "GY_CONTENT_HASH_EXCLUDED_FIELDS",
    "GY_N11_CONFIDENCE_CONTRACT_PROJECTION_OWNER",
    "GY_WAIST_SCHEMA_VERSION",
    "PROMOTION_RISK_CONDITIONALITY_CAVEAT",
    "AgentDecisionRecord",
    "ApplicabilityResult",
    "ArtifactEnvelope",
    "ArtifactRef",
    "AuthorityDerivationTrace",
    "AuthorityFlowResult",
    "BudgetVector",
    "CompositionCertificate",
    "CompositionGateResult",
    "CouplingDeclaration",
    "DecisionGrade",
    "EmergentClaimGroundingResult",
    "EvidenceBasis",
    "EvidenceKind",
    "FrontierSnapshot",
    "GyArtifactProjectionOwner",
    "GyArtifactProjectionRule",
    "MethodOutputConsumptionRecord",
    "MethodPlan",
    "ObligationRecord",
    "OperationClass",
    "OperationContract",
    "OperationInvocationRecord",
    "PortSpec",
    "SearchBlockerRecord",
    "SearchBudgetRecord",
    "SearchCoverageRecord",
    "SearchExitContract",
    "SearchIncompletenessRecord",
    "SearchLedgerEvent",
    "SearchNextBestAction",
    "SearchQualityRecord",
    "SearchTerminalKind",
    "SearchTerminalState",
    "SearchUnresolvedRecord",
    "SubDesignContract",
    "VOISelectionAudit",
    "WorkspaceContract",
    "assert_ring2_verifier_provenance",
    "gy_content_hash",
    "is_gy_content_hash_excluded_field",
    "strip_gy_volatile_fields",
]


def _computed_evidence_covers_request(*, computed: str, requested: str) -> bool:
    if computed == requested:
        return True
    if requested == "elicitation":
        return computed != "incomparable_meet"
    if computed == "measurement":
        return requested in {
            "derivation",
            "proxy",
            "transport",
            "bounds",
            "simulation",
            "elicitation",
        }
    if computed == "derivation":
        return requested in {"proxy", "transport", "bounds", "simulation", "elicitation"}
    return False
