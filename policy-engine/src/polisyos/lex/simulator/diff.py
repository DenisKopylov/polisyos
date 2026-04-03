"""Rule-level NormPack diff contracts and deterministic comparison helpers."""
from __future__ import annotations

import json
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.norm_pack import NormPack, NormRule


class NormChangeType(str, Enum):
    """How one norm changed between two versions of a `NormPack`."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class FieldDelta(BaseModel):
    """Serialized value change for one ``NormRule`` field."""
    model_config = ConfigDict(extra="forbid")

    field_name: str
    old_value: str | None = None
    new_value: str | None = None


class NormChange(BaseModel):
    """One per-norm diff record produced by `diff_norm_packs()`."""

    model_config = ConfigDict(extra="forbid")

    norm_id: str
    change_type: NormChangeType
    old_rule: NormRule | None = None
    new_rule: NormRule | None = None
    field_deltas: list[FieldDelta] = Field(default_factory=list)


class NormDiff(BaseModel):
    """Structured diff between two `NormPack` snapshots."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    old_pack_id: str
    new_pack_id: str
    jurisdiction: str
    changes: list[NormChange] = Field(default_factory=list)
    added_count: int = 0
    removed_count: int = 0
    modified_count: int = 0
    unchanged_count: int = 0

    @property
    def has_changes(self) -> bool:
        return bool(self.added_count or self.removed_count or self.modified_count)

    @property
    def affected_norm_ids(self) -> list[str]:
        return [
            change.norm_id
            for change in self.changes
            if change.change_type != NormChangeType.UNCHANGED
        ]


def diff_norm_packs(old_pack: NormPack, new_pack: NormPack) -> NormDiff:
    """Compute a deterministic rule-level diff between two norm packs."""

    old_index = _index_rules(old_pack.norms, pack_id=old_pack.pack_id)
    new_index = _index_rules(new_pack.norms, pack_id=new_pack.pack_id)
    all_norm_ids = sorted(set(old_index) | set(new_index))

    changes: list[NormChange] = []
    added = removed = modified = unchanged = 0

    for norm_id in all_norm_ids:
        old_rule = old_index.get(norm_id)
        new_rule = new_index.get(norm_id)

        if old_rule is None and new_rule is not None:
            changes.append(
                NormChange(
                    norm_id=norm_id,
                    change_type=NormChangeType.ADDED,
                    new_rule=new_rule,
                )
            )
            added += 1
            continue

        if old_rule is not None and new_rule is None:
            changes.append(
                NormChange(
                    norm_id=norm_id,
                    change_type=NormChangeType.REMOVED,
                    old_rule=old_rule,
                )
            )
            removed += 1
            continue

        if old_rule is None or new_rule is None:
            continue

        old_dump = old_rule.model_dump(mode="json")
        new_dump = new_rule.model_dump(mode="json")
        if old_dump == new_dump:
            changes.append(
                NormChange(
                    norm_id=norm_id,
                    change_type=NormChangeType.UNCHANGED,
                    old_rule=old_rule,
                    new_rule=new_rule,
                )
            )
            unchanged += 1
            continue

        changes.append(
            NormChange(
                norm_id=norm_id,
                change_type=NormChangeType.MODIFIED,
                old_rule=old_rule,
                new_rule=new_rule,
                field_deltas=_compute_field_deltas(old_dump, new_dump),
            )
        )
        modified += 1

    return NormDiff(
        old_pack_id=old_pack.pack_id,
        new_pack_id=new_pack.pack_id,
        jurisdiction=old_pack.jurisdiction,
        changes=changes,
        added_count=added,
        removed_count=removed,
        modified_count=modified,
        unchanged_count=unchanged,
    )


def _index_rules(norms: list[NormRule], *, pack_id: str) -> dict[str, NormRule]:
    index: dict[str, NormRule] = {}
    for rule in norms:
        if rule.norm_id in index:
            raise ValueError(f"Duplicate norm_id '{rule.norm_id}' in pack '{pack_id}'")
        index[rule.norm_id] = rule
    return index


def _compute_field_deltas(old_dict: dict[str, Any], new_dict: dict[str, Any]) -> list[FieldDelta]:
    deltas: list[FieldDelta] = []
    all_keys = sorted(set(old_dict) | set(new_dict))
    for key in all_keys:
        old_value = old_dict.get(key)
        new_value = new_dict.get(key)
        if old_value == new_value:
            continue
        deltas.append(
            FieldDelta(
                field_name=key,
                old_value=_serialize_delta_value(old_value),
                new_value=_serialize_delta_value(new_value),
            )
        )
    return deltas


def _serialize_delta_value(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=True, sort_keys=True)
