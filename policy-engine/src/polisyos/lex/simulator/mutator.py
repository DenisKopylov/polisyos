"""Deterministic NormPack mutation helpers for what-if legal scenario analysis.

``NormPackMutator`` applies add/replace/modify/remove operations, derives a stable mutated
``pack_id`` from the operation log and ``MutationIntent``, and records mutation provenance in the
resulting ``NormPack.metadata`` block.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.norm_pack import NormPack, NormRule
from polisyos.ir.world.ids import stable_world_id_from_canon


class MutationIntent(BaseModel):
    """Why and for which scenario the mutated pack was created."""

    model_config = ConfigDict(extra="forbid")

    scenario_label: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    requested_by: str = "unknown"
    ticket_ref: str | None = None


class NormPackMutator:
    """Fluent helper for deterministic NormPack mutations."""

    def __init__(self, base_pack: NormPack) -> None:
        self._base = base_pack
        self._norms: dict[str, NormRule] = {
            rule.norm_id: rule.model_copy(deep=True) for rule in base_pack.norms
        }
        self._effective_date: str | None = base_pack.effective_date
        self._metadata_overrides: dict[str, object] = {}
        self._operations: list[dict[str, object]] = []

    def replace_norm(self, norm_id: str, new_rule: NormRule) -> NormPackMutator:
        """Replace one existing norm while preserving the target ``norm_id``.

        Raises:
            KeyError: If ``norm_id`` is absent from the base pack.
            ValueError: If ``new_rule.norm_id`` does not match ``norm_id``.
        """
        if norm_id not in self._norms:
            raise KeyError(f"Norm '{norm_id}' not found in base pack '{self._base.pack_id}'")
        if new_rule.norm_id != norm_id:
            raise ValueError(
                f"Replacement norm_id mismatch: expected '{norm_id}', got '{new_rule.norm_id}'"
            )
        self._norms[norm_id] = new_rule.model_copy(deep=True)
        self._operations.append({"op": "replace_norm", "norm_id": norm_id})
        return self

    def modify_norm(self, norm_id: str, **field_overrides: object) -> NormPackMutator:
        """Patch one existing norm by validating a merged ``NormRule`` payload."""
        if norm_id not in self._norms:
            raise KeyError(f"Norm '{norm_id}' not found in base pack '{self._base.pack_id}'")
        current = self._norms[norm_id]
        updated_payload = current.model_dump(mode="python")
        updated_payload.update(field_overrides)
        self._norms[norm_id] = NormRule.model_validate(updated_payload)
        self._operations.append(
            {
                "op": "modify_norm",
                "norm_id": norm_id,
                "fields": sorted(field_overrides.keys()),
            }
        )
        return self

    def remove_norm(self, norm_id: str) -> NormPackMutator:
        """Remove one norm from the mutable working copy."""
        if norm_id not in self._norms:
            raise KeyError(f"Norm '{norm_id}' not found in base pack '{self._base.pack_id}'")
        del self._norms[norm_id]
        self._operations.append({"op": "remove_norm", "norm_id": norm_id})
        return self

    def add_norm(self, rule: NormRule) -> NormPackMutator:
        """Add a new norm and reject duplicates already present in the working copy."""
        if rule.norm_id in self._norms:
            raise ValueError(f"Norm '{rule.norm_id}' already exists; use replace_norm()")
        self._norms[rule.norm_id] = rule.model_copy(deep=True)
        self._operations.append({"op": "add_norm", "norm_id": rule.norm_id})
        return self

    def set_effective_date(self, effective_date: str | None) -> NormPackMutator:
        """Override the effective date on the mutated pack under construction."""
        self._effective_date = effective_date
        self._operations.append({"op": "set_effective_date", "effective_date": effective_date})
        return self

    def with_metadata(self, **overrides: object) -> NormPackMutator:
        """Merge additional metadata into the mutated pack before ``build()``."""
        self._metadata_overrides.update(overrides)
        if overrides:
            self._operations.append({"op": "set_metadata", "keys": sorted(overrides.keys())})
        return self

    def build(self, intent: MutationIntent) -> NormPack:
        """Materialize the mutated NormPack with deterministic ids and mutation provenance."""
        norms = sorted(self._norms.values(), key=lambda item: item.norm_id)
        pack_id = stable_world_id_from_canon(
            prefix="normpack.mutated",
            payload={
                "base_pack_id": self._base.pack_id,
                "jurisdiction": self._base.jurisdiction,
                "effective_date": self._effective_date,
                "intent": intent.model_dump(mode="json", exclude_none=True),
                "operations": self._operations,
                "resulting_norm_signatures": [_rule_signature(rule) for rule in norms],
            },
        )

        metadata = dict(self._base.metadata)
        metadata.update(self._metadata_overrides)
        metadata["_mutation_base_pack_id"] = self._base.pack_id
        metadata["_mutation_intent"] = intent.model_dump(mode="json", exclude_none=True)
        metadata["_mutation_operations"] = list(self._operations)

        return NormPack(
            schema_version=self._base.schema_version,
            pack_id=pack_id,
            jurisdiction=self._base.jurisdiction,
            effective_date=self._effective_date,
            norms=norms,
            metadata=metadata,
        )


def _rule_signature(rule: NormRule) -> dict[str, object]:
    payload = rule.model_dump(mode="json")
    return {
        "norm_id": rule.norm_id,
        "digest_payload": payload,
    }
