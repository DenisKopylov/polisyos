from __future__ import annotations

import hashlib
from typing import Any, Mapping

from polisyos.ir.canon import to_canonical_bytes
from polisyos.ir.migration_report import (
    MigrationAction,
    MigrationReport,
    MigrationWarning,
)
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.policy_spec import InterventionSpec as CanonInterventionSpec
from polisyos.ir.policy_spec import PolicySpec
from polisyos.ir.problem_frame import (
    ConstraintSpec as CanonConstraintSpec,
    ConstraintType,
    ObjectiveSpec as CanonObjectiveSpec,
    ProblemDomain,
    ProblemFrame,
    StakeholderSpec,
)
from polisyos.ir.trinity import TRINITY_BUNDLE_SCHEMA_VERSION, TrinityBundle

from polisyos.ir.legacy.surface import (
    AdvisoryEntity,
    ConstraintSpec,
    InterventionSpec,
    ObjectiveSpec,
    PolicyAdvisory,
    PolicySemantic,
    PolicySurfaceIR,
)
from polisyos.ir.legacy.trinity_v0 import TrinityBundle as LegacyTrinityBundle

# Label prefix mappings (legacy conventions)
PROBLEM_FRAME_PREFIXES = frozenset(["goal:", "success:", "actor:", "kpi:"])
POLICY_SPEC_PREFIXES = frozenset(["policy:", "intervention:", "mechanism:"])
MODEL_SPEC_PREFIXES = frozenset(["model:", "data:", "assumption:", "fidelity:"])

NOTE_PREFIX_POLICY = "[policy]"
NOTE_PREFIX_MODEL = "[model]"


def _compute_source_ref_from_surface(ir: PolicySurfaceIR) -> str:
    payload = ir.semantic_fingerprint_payload()
    canonical = to_canonical_bytes(payload)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _compute_source_ref_from_bundle(bundle: LegacyTrinityBundle) -> str:
    source_ref = None
    if getattr(bundle.problem_frame, "metadata", None):
        source_ref = bundle.problem_frame.metadata.source_ir_ref
    if not source_ref:
        canonical = to_canonical_bytes(bundle.model_dump(mode="json"))
        source_ref = f"sha256:{hashlib.sha256(canonical).hexdigest()}"
    return source_ref


def _ids_from_source(source_ref: str) -> tuple[str, str, str]:
    hex_part = source_ref.split(":", 1)[-1]
    seed = hex_part[:12]
    return (f"pf_{seed}", f"ps_{seed}", f"ms_{seed}")


def _partition_labels(labels: list[str]) -> dict[str, list[str]]:
    result = {
        "problem_frame": [],
        "policy_spec": [],
        "model_spec": [],
        "unclassified": [],
    }

    for label in labels:
        classified = False
        for prefix in PROBLEM_FRAME_PREFIXES:
            if label.startswith(prefix):
                result["problem_frame"].append(label)
                classified = True
                break
        if classified:
            continue

        for prefix in POLICY_SPEC_PREFIXES:
            if label.startswith(prefix):
                result["policy_spec"].append(label)
                classified = True
                break
        if classified:
            continue

        for prefix in MODEL_SPEC_PREFIXES:
            if label.startswith(prefix):
                result["model_spec"].append(label)
                classified = True
                break

        if not classified:
            result["unclassified"].append(label)

    return result


def _partition_notes(notes: list[str]) -> dict[str, list[str]]:
    result = {"policy_spec": [], "model_spec": [], "default": []}

    for note in notes:
        if note.startswith(NOTE_PREFIX_POLICY):
            result["policy_spec"].append(note[len(NOTE_PREFIX_POLICY) :].strip())
        elif note.startswith(NOTE_PREFIX_MODEL):
            result["model_spec"].append(note[len(NOTE_PREFIX_MODEL) :].strip())
        else:
            result["default"].append(note)

    return result


def _map_objectives(objectives: list[ObjectiveSpec]) -> list[CanonObjectiveSpec]:
    return [CanonObjectiveSpec.model_validate(obj.model_dump()) for obj in objectives]


def _map_interventions(interventions: list[InterventionSpec]) -> list[CanonInterventionSpec]:
    return [CanonInterventionSpec.model_validate(item.model_dump()) for item in interventions]


def _map_constraints(constraints: list[ConstraintSpec]) -> list[CanonConstraintSpec]:
    mapped: list[CanonConstraintSpec] = []
    for item in constraints:
        mapped.append(
            CanonConstraintSpec(
                constraint_id=item.constraint_id,
                constraint_type=ConstraintType.HARD,
                value=item.value,
                notes=list(item.notes),
            )
        )
    return mapped


def _map_stakeholders(entities: list[AdvisoryEntity]) -> list[StakeholderSpec]:
    out: list[StakeholderSpec] = []
    for entity in entities:
        attributes = dict(entity.attributes)
        if entity.parent_id and "parent_id" not in attributes:
            attributes["parent_id"] = entity.parent_id
        out.append(
            StakeholderSpec(
                stakeholder_id=entity.entity_id,
                entity_type=entity.entity_type,
                name=entity.name,
                attributes=attributes,
            )
        )
    return out


def migrate_surface_ir_to_trinity(
    legacy_ir: PolicySurfaceIR,
) -> tuple[TrinityBundle, MigrationReport]:
    semantic: PolicySemantic = legacy_ir.semantic
    advisory: PolicyAdvisory = legacy_ir.advisory or PolicyAdvisory()

    source_ref = _compute_source_ref_from_surface(legacy_ir)
    problem_id, policy_id, model_id = _ids_from_source(source_ref)

    label_groups = _partition_labels(advisory.labels)
    note_groups = _partition_notes(semantic.notes)

    warnings: list[MigrationWarning] = [
        MigrationWarning(
            code="domain_defaulted",
            message="ProblemFrame.domain defaulted to custom",
            path="$.problem_frame.domain",
        ),
    ]

    actions: list[MigrationAction] = [
        MigrationAction(
            kind="transform",
            from_path="$.semantic.objectives",
            to_path="$.problem_frame.objectives",
            note="Mapped legacy objectives to ProblemFrame.objectives",
        ),
        MigrationAction(
            kind="transform",
            from_path="$.semantic.interventions",
            to_path="$.policy_spec.interventions",
            note="Mapped legacy interventions to PolicySpec.interventions",
        ),
        MigrationAction(
            kind="transform",
            from_path="$.semantic.constraints",
            to_path="$.problem_frame.hard_constraints",
            note="Mapped legacy constraints to hard_constraints (constraint_type=HARD)",
            lossy=True,
        ),
        MigrationAction(
            kind="transform",
            from_path="$.advisory.entities",
            to_path="$.problem_frame.stakeholders",
            note="Mapped advisory entities to stakeholders",
            lossy=True,
        ),
        MigrationAction(
            kind="copy",
            from_path="$.semantic.context_snapshot_ref",
            to_path="$.model_spec.data_snapshot_ref",
        ),
        MigrationAction(
            kind="copy",
            from_path="$.semantic.registry_bundle_ref",
            to_path="$.model_spec.registry_bundle_ref",
        ),
        MigrationAction(
            kind="copy",
            from_path="$.semantic.time_semantics",
            to_path="$.model_spec.time_semantics",
        ),
        MigrationAction(
            kind="split",
            from_path="$.advisory.labels",
            to_path="$.problem_frame.labels|$.policy_spec.labels|$.model_spec.labels",
            note="Partitioned labels by legacy prefix",
        ),
        MigrationAction(
            kind="split",
            from_path="$.semantic.notes",
            to_path="$.policy_spec.notes|$.model_spec.notes",
            note="Partitioned notes by legacy prefix (defaults to policy_spec)",
        ),
    ]

    problem_frame = ProblemFrame(
        problem_id=problem_id,
        domain=ProblemDomain.CUSTOM,
        objectives=_map_objectives(semantic.objectives),
        kpis=[],
        success_criteria=[],
        hard_constraints=_map_constraints(semantic.constraints),
        soft_constraints=[],
        stakeholders=_map_stakeholders(advisory.entities),
        narrative=advisory.narrative,
        labels=label_groups["problem_frame"] + label_groups["unclassified"],
        notes=list(advisory.notes),
    )

    policy_spec = PolicySpec(
        policy_id=policy_id,
        interventions=_map_interventions(semantic.interventions),
        labels=label_groups["policy_spec"],
        notes=note_groups["policy_spec"] + note_groups["default"],
    )

    model_spec = ModelSpec(
        model_id=model_id,
        data_snapshot_ref=semantic.context_snapshot_ref,
        registry_bundle_ref=semantic.registry_bundle_ref,
        time_semantics=semantic.time_semantics,
        labels=label_groups["model_spec"],
        notes=note_groups["model_spec"],
    )

    bundle = TrinityBundle(
        schema_version=TRINITY_BUNDLE_SCHEMA_VERSION,
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )

    report = MigrationReport(
        migration_id=source_ref,
        source_format="policy_surface_ir",
        source_schema_version=legacy_ir.schema_version,
        target_format="trinity_bundle",
        target_schema_version=TRINITY_BUNDLE_SCHEMA_VERSION,
        source_ref=source_ref,
        warnings=warnings,
        actions=actions,
    )

    return bundle, report


def migrate_trinity_bundle_v0_to_trinity(
    legacy_bundle: LegacyTrinityBundle,
) -> tuple[TrinityBundle, MigrationReport]:
    source_ref = _compute_source_ref_from_bundle(legacy_bundle)
    problem_id, policy_id, model_id = _ids_from_source(source_ref)

    warnings: list[MigrationWarning] = [
        MigrationWarning(
            code="domain_defaulted",
            message="ProblemFrame.domain defaulted to custom",
            path="$.problem_frame.domain",
        )
    ]
    if legacy_bundle.model_spec.assumptions:
        warnings.append(
            MigrationWarning(
                code="assumptions_dropped",
                message="Legacy model_spec.assumptions dropped during migration",
                path="$.model_spec.assumptions",
            )
        )
    actions: list[MigrationAction] = [
        MigrationAction(
            kind="transform",
            from_path="$.problem_frame.kpis",
            to_path="$.problem_frame.objectives",
            note="Mapped legacy kpis (objectives) to objectives",
        ),
        MigrationAction(
            kind="transform",
            from_path="$.problem_frame.constraints",
            to_path="$.problem_frame.hard_constraints",
            note="Mapped legacy constraints to hard_constraints (constraint_type=HARD)",
            lossy=True,
        ),
        MigrationAction(
            kind="transform",
            from_path="$.problem_frame.actors",
            to_path="$.problem_frame.stakeholders",
            note="Mapped legacy actors to stakeholders",
            lossy=True,
        ),
        MigrationAction(
            kind="copy",
            from_path="$.policy_spec.interventions",
            to_path="$.policy_spec.interventions",
        ),
        MigrationAction(
            kind="copy",
            from_path="$.model_spec.data_snapshot_ref",
            to_path="$.model_spec.data_snapshot_ref",
        ),
    ]

    problem_frame = ProblemFrame(
        problem_id=problem_id,
        domain=ProblemDomain.CUSTOM,
        objectives=_map_objectives(legacy_bundle.problem_frame.kpis),
        kpis=[],
        success_criteria=[],
        hard_constraints=_map_constraints(legacy_bundle.problem_frame.constraints),
        soft_constraints=[],
        stakeholders=_map_stakeholders(legacy_bundle.problem_frame.actors),
        narrative=legacy_bundle.problem_frame.problem_statement,
        labels=list(legacy_bundle.problem_frame.success_criteria_tags)
        + list(legacy_bundle.problem_frame.general_labels),
        notes=list(legacy_bundle.problem_frame.metadata.auxiliary_notes),
    )

    policy_spec = PolicySpec(
        policy_id=policy_id,
        interventions=_map_interventions(legacy_bundle.policy_spec.interventions),
        labels=list(legacy_bundle.policy_spec.policy_labels),
        notes=list(legacy_bundle.policy_spec.implementation_notes),
    )

    model_spec = ModelSpec(
        model_id=model_id,
        data_snapshot_ref=legacy_bundle.model_spec.data_snapshot_ref,
        registry_bundle_ref=legacy_bundle.model_spec.registry_bundle_ref,
        time_semantics=legacy_bundle.model_spec.time_semantics,
        labels=list(legacy_bundle.model_spec.model_labels),
        notes=list(legacy_bundle.model_spec.model_notes),
    )

    bundle = TrinityBundle(
        schema_version=TRINITY_BUNDLE_SCHEMA_VERSION,
        problem_frame=problem_frame,
        policy_spec=policy_spec,
        model_spec=model_spec,
    )

    report = MigrationReport(
        migration_id=source_ref,
        source_format="legacy_trinity_bundle_v0",
        source_schema_version=legacy_bundle.problem_frame.schema_version,
        target_format="trinity_bundle",
        target_schema_version=TRINITY_BUNDLE_SCHEMA_VERSION,
        source_ref=source_ref,
        warnings=warnings,
        actions=actions,
    )

    return bundle, report


def _label_with_prefix(label: str, *, prefix: str, known_prefixes: set[str]) -> str:
    if any(label.startswith(pfx) for pfx in known_prefixes):
        return label
    return f"{prefix}{label}"


def _compute_source_ref_from_trinity(bundle: TrinityBundle) -> str:
    canonical = to_canonical_bytes(bundle.model_dump(mode="json"))
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def migrate_trinity_to_surface_ir(
    bundle: TrinityBundle,
    *,
    target_schema_version: str = "2.0",
) -> tuple[PolicySurfaceIR, MigrationReport]:
    pf = bundle.problem_frame
    ps = bundle.policy_spec
    ms = bundle.model_spec

    merged_labels: list[str] = []
    merged_labels.extend(
        _label_with_prefix(label, prefix="goal:", known_prefixes=set(PROBLEM_FRAME_PREFIXES))
        for label in pf.labels
    )
    merged_labels.extend(
        _label_with_prefix(label, prefix="policy:", known_prefixes=set(POLICY_SPEC_PREFIXES))
        for label in ps.labels
    )
    merged_labels.extend(
        _label_with_prefix(label, prefix="model:", known_prefixes=set(MODEL_SPEC_PREFIXES))
        for label in ms.labels
    )

    merged_notes: list[str] = []
    merged_notes.extend([f"{NOTE_PREFIX_POLICY} {note}" for note in ps.notes])
    merged_notes.extend([f"{NOTE_PREFIX_MODEL} {note}" for note in ms.notes])

    semantic = PolicySemantic(
        context_snapshot_ref=ms.data_snapshot_ref,
        registry_bundle_ref=ms.registry_bundle_ref,
        time_semantics=ms.time_semantics,
        objectives=[
            ObjectiveSpec.model_validate(obj.model_dump(exclude={"kpi_refs"}))
            for obj in pf.objectives
        ],
        interventions=[
            InterventionSpec.model_validate(obj.model_dump(exclude={"enabled"}))
            for obj in ps.interventions
        ],
        constraints=[
            ConstraintSpec(
                constraint_id=constraint.constraint_id,
                value=constraint.value,
                notes=list(constraint.notes),
            )
            for constraint in (pf.hard_constraints + pf.soft_constraints)
        ],
        notes=merged_notes,
    )

    advisory = PolicyAdvisory(
        entities=[
            AdvisoryEntity(
                entity_id=stakeholder.stakeholder_id,
                entity_type=stakeholder.entity_type,
                name=stakeholder.name,
                attributes=dict(stakeholder.attributes),
            )
            for stakeholder in pf.stakeholders
        ],
        narrative=pf.narrative,
        labels=merged_labels,
        notes=pf.notes,
    )

    surface = PolicySurfaceIR(
        schema_version=target_schema_version,
        semantic=semantic,
        advisory=advisory,
    )

    actions = [
        MigrationAction(
            kind="merge",
            from_path="$.problem_frame|$.policy_spec|$.model_spec",
            to_path="$.policy_surface_ir",
            note="Merged canonical Trinity bundle into legacy surface IR",
            lossy=True,
        )
    ]

    source_ref = _compute_source_ref_from_trinity(bundle)
    report = MigrationReport(
        migration_id=source_ref,
        source_format="trinity_bundle",
        source_schema_version=bundle.schema_version,
        target_format="policy_surface_ir",
        target_schema_version=target_schema_version,
        source_ref=source_ref,
        warnings=[],
        actions=actions,
    )

    return surface, report


def is_trinity_bundle_payload(payload: Mapping[str, Any]) -> bool:
    return (
        "problem_frame" in payload
        and "policy_spec" in payload
        and "model_spec" in payload
    )


def is_legacy_trinity_bundle_payload(payload: Mapping[str, Any]) -> bool:
    return (
        "problem_frame" in payload
        and "policy_spec" in payload
        and "model_spec" in payload
        and "source_schema_version" in payload
    )


__all__ = [
    "migrate_surface_ir_to_trinity",
    "migrate_trinity_to_surface_ir",
    "migrate_trinity_bundle_v0_to_trinity",
    "is_trinity_bundle_payload",
    "is_legacy_trinity_bundle_payload",
]
