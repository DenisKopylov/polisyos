"""Single verification chokepoint for claim-publishability consumers."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from weakref import WeakKeyDictionary

from polisyos.core import artifacts, canon
from polisyos.data_forge.domains.academic.batch.claim_adjudicator import (
    load_admitted_claim_adjudication_batch,
)
from polisyos.ir.analytics import ClaimAdjudicationInputBatch, ClaimAdjudicationInputItem

if TYPE_CHECKING:
    from collections.abc import Mapping

    from polisyos.data_forge.domains.academic.batch.claim_adjudication_verifier import (
        ClaimAdjudicationVerifier,
    )
    from polisyos.data_forge.domains.academic.batch.config import AcademicBatchConfig


def _compatibility_rows(config: AcademicBatchConfig) -> list[dict[str, Any]]:
    if not config.claim_adjudications_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        config.claim_adjudications_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(
                f"claim adjudication compatibility row {line_number} must be an object"
            )
        rows.append(payload)
    return rows


@dataclass(frozen=True)
class _RowsState:
    config: AcademicBatchConfig
    verifier: ClaimAdjudicationVerifier | None
    store: artifacts.FileSystemCAS | None
    result_ref: artifacts.ArtifactRef | None
    raw_input_ref: str | None


_ROW_STATES: WeakKeyDictionary[VerifiedClaimAdjudicationRows, _RowsState] = WeakKeyDictionary()


class VerifiedClaimAdjudicationRows:
    """Fieldless, owner-minted access to currently verified adjudication rows.

    Every authority read re-resolves the signed evidence and champion. Copying
    its values produces candidate dictionaries, never another admitted capability.
    """

    __slots__ = ("__weakref__",)
    __hash__ = object.__hash__
    __eq__ = object.__eq__

    def __new__(cls) -> VerifiedClaimAdjudicationRows:
        raise TypeError("claim adjudication rows must be minted by their verification owner")

    def _read(self) -> dict[str, dict[str, Any]]:
        state = _ROW_STATES.get(self)
        if state is None:
            raise ValueError("claim_adjudication_unminted_rows_capability")
        if state.result_ref is None:
            if state.config.claim_adjudication_result_ref_path.exists() or _compatibility_rows(
                state.config
            ):
                raise ValueError("claim_adjudication_empty_rows_changed")
            return {}
        batch, result_ref = load_admitted_claim_adjudication_batch(
            state.config,
            result_ref=state.result_ref,
            store=state.store,
            verifier=state.verifier,
        )
        rows = [
            {
                **result.model_dump(mode="json"),
                "adjudication_receipt_id": str(result_ref.artifact_id),
                "authority_rule_version": batch.rule_version,
            }
            for result in batch.results
        ]
        projected = _compatibility_rows(state.config)
        if projected and projected != rows:
            raise ValueError("claim adjudication compatibility projection differs from receipt")
        return {str(row["claim_id"]): row for row in rows}

    def for_current_subject(self, subject: Mapping[str, object]) -> dict[str, Any] | None:
        """Resolve an exact, complete current input occurrence; never join by ID alone."""
        rows = self._read()
        claim_id = subject.get("claim_id")
        if claim_id not in rows:
            return None
        # Schema defaults are not observed current context. Require every field.
        fields = set(ClaimAdjudicationInputItem.model_fields)
        if set(subject) != fields:
            raise ValueError("claim_adjudication_current_subject_transport_incomplete")
        current = ClaimAdjudicationInputItem.model_validate(subject)
        state = _ROW_STATES[self]
        if state.raw_input_ref is None:
            raise ValueError("claim_adjudication_raw_input_binding_missing")
        store = state.store or artifacts.FileSystemCAS(state.config.claim_adjudication_cas_root)
        raw = ClaimAdjudicationInputBatch.model_validate(
            canon.from_canonical_bytes(store.get_bytes(artifacts.ArtifactID(state.raw_input_ref)))
        )
        expected = next(item for item in raw.items if item.claim_id == claim_id)
        if current.model_dump(mode="json") != expected.model_dump(mode="json"):
            raise ValueError("claim_adjudication_current_subject_binding_mismatch")
        return rows[current.claim_id]


def resolve_current_claim_adjudication(
    rows: VerifiedClaimAdjudicationRows | None,
    *,
    claim: Mapping[str, object],
    work: Mapping[str, object] | None = None,
) -> dict[str, Any] | None:
    """Bind every canonical input field from the actual consuming transport.

    Aliases adapt field names only. Values are never filled from the admitted
    original, and conflicting aliases are rejected. Legacy partial transports
    remain candidates until they carry the complete canonical occurrence.
    """
    if rows is None:
        return None
    capability = require_verified_claim_adjudication_rows(rows)
    aliases = {
        "openalex_id": ("openalex_id", "work_id", "id"),
        "cause_variable": ("cause_variable", "cause", "cause_text"),
        "effect_variable": ("effect_variable", "effect", "effect_text"),
        "claim_type_hint": ("claim_type_hint", "claim_type"),
        "extraction_confidence": ("extraction_confidence", "claim_extraction_confidence"),
    }
    work = work or {}
    subject: dict[str, object] = {}
    for field in ClaimAdjudicationInputItem.model_fields:
        values = [
            claim[name]
            for name in aliases.get(field, (field,))
            if name in claim and not (name == "claim_extraction_confidence" and claim[name] is None)
        ]
        if values:
            if any(value != values[0] for value in values[1:]):
                raise ValueError("claim_adjudication_current_subject_alias_conflict:" + field)
            subject[field] = values[0]
    # WorkRecord's identity and title are the enclosing consumer subject.
    # Its confidence and metadata spans instead describe the whole paper.
    for field, names in (("openalex_id", ("id", "openalex_id", "work_id")), ("title", ("title",))):
        for name in names:
            if name in work and work[name] != subject.get(field):
                raise ValueError("claim_adjudication_current_subject_work_mismatch:" + field)
    return capability.for_current_subject(subject)


def require_verified_claim_adjudication_rows(value: object) -> VerifiedClaimAdjudicationRows:
    """Reject raw mappings and unminted markers at every publication consumer."""
    if type(value) is not VerifiedClaimAdjudicationRows:
        raise ValueError("claim_adjudication_verified_rows_capability_required")
    value._read()
    return value


def load_verified_claim_adjudication_rows(
    config: AcademicBatchConfig,
    *,
    verifier: ClaimAdjudicationVerifier | None = None,
    store: artifacts.FileSystemCAS | None = None,
) -> VerifiedClaimAdjudicationRows:
    """Mint a capability bound to an exact result, reverified on every row read."""
    result_ref = None
    raw_input_ref = None
    if config.claim_adjudication_result_ref_path.exists():
        batch, result_ref = load_admitted_claim_adjudication_batch(
            config, store=store, verifier=verifier
        )
        raw_input_ref = batch.raw_input_ref
    elif _compatibility_rows(config):
        raise ValueError("unreceipted claim adjudication compatibility rows")
    capability = object.__new__(VerifiedClaimAdjudicationRows)
    _ROW_STATES[capability] = _RowsState(
        deepcopy(config), verifier, store, result_ref, raw_input_ref
    )
    capability._read()
    return capability


__all__ = [
    "VerifiedClaimAdjudicationRows",
    "load_verified_claim_adjudication_rows",
    "require_verified_claim_adjudication_rows",
    "resolve_current_claim_adjudication",
]
