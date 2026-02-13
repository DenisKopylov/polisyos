"""Binding resolver — converts BindingProfile rules to CAS-persistable artifacts.

Pure data transformations, NO jax/numpy imports.
"""

from __future__ import annotations

import json
from typing import Any

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec

from .models import BindingProfile, BindingRuleSpec


def resolve_binding_rules(profile: BindingProfile) -> list[dict[str, Any]]:
    """Convert BindingRuleSpec list → FoundryInputBindingRule-compatible dicts.

    Returns a list of dicts that can be consumed by Foundry's
    ``build_input_bindings()`` when the execution layer is ready.
    """
    rules: list[dict[str, Any]] = []
    for rule in profile.rules:
        entry: dict[str, Any] = {
            "binding_id": rule.binding_id,
            "source_path": rule.source_path,
            "target_slot_id": rule.target_slot_id,
            "required": rule.required,
        }
        if rule.default_value is not None:
            entry["default_value"] = rule.default_value
        if rule.transforms:
            entry["transforms"] = [
                {"op": t.op, "params": t.params} for t in rule.transforms
            ]
        if rule.notes:
            entry["notes"] = rule.notes
        rules.append(entry)
    return rules


def persist_binding_rules_artifact(
    store: FileSystemCAS,
    profile: BindingProfile,
    data_snapshot_ref: str | None = None,
) -> ArtifactRef:
    """Persist resolved binding rules as a CAS artifact.

    Returns an ArtifactRef that can be passed to Foundry or stored
    in IngestResponse.input_bindings_ref.
    """
    rules = resolve_binding_rules(profile)
    payload: dict[str, Any] = {
        "profile_id": profile.profile_id,
        "schema_family": profile.schema_family,
        "strategy": profile.strategy,
        "rules": rules,
        "expected_columns": profile.expected_columns,
    }
    if data_snapshot_ref:
        payload["data_snapshot_ref"] = data_snapshot_ref

    return store.put_json(
        payload,
        PutOptions(
            kind="fabric.binding_rules",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.fabric.BindingRules", version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


__all__ = [
    "persist_binding_rules_artifact",
    "resolve_binding_rules",
]
