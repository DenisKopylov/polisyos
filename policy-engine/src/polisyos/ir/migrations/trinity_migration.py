from __future__ import annotations

import hashlib
from typing import Tuple

from polisyos.core.canon.canon_json import to_canonical_bytes
from polisyos.ir.surface import PolicyAdvisory, PolicySemantic, PolicySurfaceIR
from polisyos.ir.trinity import (
    ModelSpec,
    PolicySpec,
    ProblemFrame,
    SharedMetadata,
    TRINITY_SCHEMA_VERSION,
    TrinityBundle,
)

# Label prefix mappings
PROBLEM_FRAME_PREFIXES = frozenset(["goal:", "success:", "actor:", "kpi:"])
POLICY_SPEC_PREFIXES = frozenset(["policy:", "intervention:", "mechanism:"])
MODEL_SPEC_PREFIXES = frozenset(["model:", "data:", "assumption:", "fidelity:"])

# Note prefix mappings
NOTE_PREFIX_POLICY = "[policy]"
NOTE_PREFIX_MODEL = "[model]"


def _compute_source_ref(ir: PolicySurfaceIR) -> str:
    """Compute a deterministic reference hash for the source IR."""
    payload = ir.semantic_fingerprint_payload()
    canonical = to_canonical_bytes(payload)
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _partition_labels(labels: list[str]) -> dict[str, list[str]]:
    """Partition labels by their prefix into Trinity categories."""
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
    """Partition notes by their prefix into Trinity categories."""
    result = {
        "policy_spec": [],
        "model_spec": [],
        "default": [],  # Goes to PolicySpec by default
    }

    for note in notes:
        if note.startswith(NOTE_PREFIX_POLICY):
            result["policy_spec"].append(note[len(NOTE_PREFIX_POLICY) :].strip())
        elif note.startswith(NOTE_PREFIX_MODEL):
            result["model_spec"].append(note[len(NOTE_PREFIX_MODEL) :].strip())
        else:
            result["default"].append(note)

    return result


def split_surface_ir(
    legacy_ir: PolicySurfaceIR,
) -> Tuple[ProblemFrame, PolicySpec, ModelSpec]:
    """
    Split a PolicySurfaceIR into the Trinity format.

    This is the core migration function that decomposes the monolithic IR
    into three independent, versioned artifacts.

    Args:
        legacy_ir: The source PolicySurfaceIR (schema_version 2.x)

    Returns:
        Tuple of (ProblemFrame, PolicySpec, ModelSpec)

    Raises:
        ValueError: If the IR is malformed or missing required fields
    """
    semantic = legacy_ir.semantic
    advisory = legacy_ir.advisory or PolicyAdvisory()

    # Compute source reference for traceability
    source_ref = _compute_source_ref(legacy_ir)

    # Partition labels
    label_groups = _partition_labels(advisory.labels)

    # Partition notes
    note_groups = _partition_notes(semantic.notes)

    # Build shared metadata template
    def make_metadata(auxiliary: list[str] | None = None) -> SharedMetadata:
        return SharedMetadata(
            source_ir_ref=source_ref,
            auxiliary_notes=auxiliary or list(advisory.notes),
            migration_version="1.0",
        )

    # === ProblemFrame ===
    problem_frame = ProblemFrame(
        schema_version=TRINITY_SCHEMA_VERSION,
        kpis=list(semantic.objectives),
        constraints=list(semantic.constraints),
        actors=list(advisory.entities),
        problem_statement=advisory.narrative,
        success_criteria_tags=label_groups["problem_frame"],
        general_labels=label_groups["unclassified"],
        metadata=make_metadata(),
    )

    # === PolicySpec ===
    policy_spec = PolicySpec(
        schema_version=TRINITY_SCHEMA_VERSION,
        interventions=list(semantic.interventions),
        implementation_notes=note_groups["policy_spec"] + note_groups["default"],
        policy_labels=label_groups["policy_spec"],
        metadata=make_metadata(),
    )

    # === ModelSpec ===
    model_spec = ModelSpec(
        schema_version=TRINITY_SCHEMA_VERSION,
        data_snapshot_ref=semantic.context_snapshot_ref,
        registry_bundle_ref=semantic.registry_bundle_ref,
        time_semantics=semantic.time_semantics,
        model_notes=note_groups["model_spec"],
        model_labels=label_groups["model_spec"],
        assumptions={},
        metadata=make_metadata(),
    )

    return problem_frame, policy_spec, model_spec


def merge_to_surface_ir(
    problem_frame: ProblemFrame,
    policy_spec: PolicySpec,
    model_spec: ModelSpec,
    *,
    target_schema_version: str = "2.0",
) -> PolicySurfaceIR:
    """
    Merge Trinity artifacts back into a PolicySurfaceIR.

    This function provides backward compatibility, allowing Trinity
    artifacts to be used with systems that expect the legacy format.

    Args:
        problem_frame: The ProblemFrame artifact
        policy_spec: The PolicySpec artifact
        model_spec: The ModelSpec artifact
        target_schema_version: Target PolicySurfaceIR version (default "2.0")

    Returns:
        A reconstructed PolicySurfaceIR

    Note:
        Some data loss is possible for fields that were added in Trinity
        but do not exist in legacy format (for example, assumptions).
    """
    # Reconstruct labels with prefixes preserved
    merged_labels = (
        list(problem_frame.success_criteria_tags)
        + list(problem_frame.general_labels)
        + list(policy_spec.policy_labels)
        + list(model_spec.model_labels)
    )

    # Reconstruct notes with prefixes for round-trip preservation
    merged_notes: list[str] = []
    for note in policy_spec.implementation_notes:
        # Do not double-prefix notes that already have it
        if not note.startswith(NOTE_PREFIX_POLICY):
            merged_notes.append(f"{NOTE_PREFIX_POLICY} {note}")
        else:
            merged_notes.append(note)
    for note in model_spec.model_notes:
        if not note.startswith(NOTE_PREFIX_MODEL):
            merged_notes.append(f"{NOTE_PREFIX_MODEL} {note}")
        else:
            merged_notes.append(note)

    # Build semantic
    semantic = PolicySemantic(
        context_snapshot_ref=model_spec.data_snapshot_ref,
        registry_bundle_ref=model_spec.registry_bundle_ref,
        time_semantics=model_spec.time_semantics,
        objectives=list(problem_frame.kpis),
        interventions=list(policy_spec.interventions),
        constraints=list(problem_frame.constraints),
        notes=merged_notes,
    )

    # Build advisory
    advisory = PolicyAdvisory(
        entities=list(problem_frame.actors),
        narrative=problem_frame.problem_statement,
        labels=merged_labels,
        notes=list(problem_frame.metadata.auxiliary_notes),
    )

    return PolicySurfaceIR(
        schema_version=target_schema_version,
        semantic=semantic,
        advisory=advisory,
    )


def split_to_bundle(legacy_ir: PolicySurfaceIR) -> TrinityBundle:
    """Convenience function to split IR into a TrinityBundle."""
    pf, ps, ms = split_surface_ir(legacy_ir)
    return TrinityBundle(
        problem_frame=pf,
        policy_spec=ps,
        model_spec=ms,
        source_schema_version=legacy_ir.schema_version,
    )


def is_trinity_migrated(data: dict) -> bool:
    """Check if data is already in Trinity format."""
    return "problem_frame" in data and "policy_spec" in data and "model_spec" in data
