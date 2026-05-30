"""Neutral producer-spine binding contracts shared across producers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION = "policyos.producer_spine_context.v1"
PRODUCER_SPINE_CONSUMER_COMPONENTS = (
    "lex",
    "fabric",
    "scholar",
    "foundry",
    "scientist",
    "final_compiler",
)


class ProducerSpineReadContext(BaseModel):
    """Read interface exposing shared spine refs to producer code."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["policyos.producer_spine_context.v1"]
    context_id: str = Field(min_length=1)
    concept_spine_ref: str = Field(min_length=1)
    jurisdiction_spine_ref: str = Field(min_length=1)
    canonical_concept_refs: tuple[str, ...] = Field(default=())
    jurisdiction_refs: tuple[str, ...] = Field(default=())
    unit_refs: tuple[str, ...] = Field(default=())
    period_refs: tuple[str, ...] = Field(default=())
    geography_refs: tuple[str, ...] = Field(default=())
    consumer_components: tuple[str, ...] = Field(default=PRODUCER_SPINE_CONSUMER_COMPONENTS)

    @field_validator("context_id", "concept_spine_ref", "jurisdiction_spine_ref")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _non_empty(value)

    @field_validator(
        "canonical_concept_refs",
        "jurisdiction_refs",
        "unit_refs",
        "period_refs",
        "geography_refs",
        "consumer_components",
        mode="before",
    )
    @classmethod
    def _strip_tuple(cls, values: object) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)

    @model_validator(mode="after")
    def _validate_consumers(self) -> ProducerSpineReadContext:
        unsupported = sorted(
            set(self.consumer_components) - set(PRODUCER_SPINE_CONSUMER_COMPONENTS)
        )
        if unsupported:
            raise ValueError(
                "consumer_components contains unsupported producer spine consumers: "
                + ", ".join(unsupported)
            )
        missing = sorted(set(PRODUCER_SPINE_CONSUMER_COMPONENTS) - set(self.consumer_components))
        if missing:
            raise ValueError(
                "consumer_components must expose every producer spine consumer: "
                + ", ".join(missing)
            )
        return self


class ProducerSpineBindingFields(BaseModel):
    """Common spine-consumer fields shared by producer binding records."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    consumed_concept_spine_ref: str | None = None
    consumed_jurisdiction_spine_ref: str | None = None
    canonical_concept_refs: tuple[str, ...] = Field(default=())
    jurisdiction_refs: tuple[str, ...] = Field(default=())
    unit_refs: tuple[str, ...] = Field(default=())
    period_refs: tuple[str, ...] = Field(default=())
    geography_refs: tuple[str, ...] = Field(default=())
    candidate_spine_binding_refs: tuple[str, ...] = Field(default=())
    spine_blocker_refs: tuple[str, ...] = Field(default=())
    local_labels: tuple[str, ...] = Field(default=())

    @field_validator("consumed_concept_spine_ref", "consumed_jurisdiction_spine_ref")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @field_validator(
        "canonical_concept_refs",
        "jurisdiction_refs",
        "unit_refs",
        "period_refs",
        "geography_refs",
        "candidate_spine_binding_refs",
        "spine_blocker_refs",
        "local_labels",
        mode="before",
    )
    @classmethod
    def _strip_tuple(cls, values: object) -> tuple[str, ...]:
        return _coerce_ref_tuple(values)


def build_producer_spine_binding_fields(
    *,
    component: str,
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
    candidate_refs: Sequence[Any] | None = None,
    blocker_refs: Sequence[Any] | None = None,
    local_labels: Sequence[Any] | None = None,
) -> dict[str, Any]:
    """Build required spine-consumer fields for a producer report."""

    return _spine_fields_from_report(
        {"local_labels": tuple(_refs_from_value(local_labels))},
        spine_context,
        component=component,
        candidate_refs=tuple(_refs_from_value(candidate_refs)),
        blocker_refs=tuple(_refs_from_value(blocker_refs)),
    )


def _spine_fields_from_report(
    report: Mapping[str, Any],
    spine_context: Mapping[str, Any] | ProducerSpineReadContext | None,
    *,
    component: str | None = None,
    candidate_refs: Sequence[Any] | None = None,
    blocker_refs: Sequence[Any] | None = None,
) -> dict[str, Any]:
    context = (
        spine_context.model_dump(mode="json")
        if isinstance(spine_context, ProducerSpineReadContext)
        else dict(spine_context or {})
    )
    concept_ref = _first_text(
        report.get("consumed_concept_spine_ref"),
        report.get("concept_spine_ref"),
        context.get("concept_spine_ref"),
    )
    jurisdiction_ref = _first_text(
        report.get("consumed_jurisdiction_spine_ref"),
        report.get("jurisdiction_spine_ref"),
        context.get("jurisdiction_spine_ref"),
    )
    canonical_concepts = _refs_from(
        report,
        "canonical_concept_refs",
        "concept_refs",
        "consumed_concept_refs",
    ) or _refs_from_value(context.get("canonical_concept_refs"))
    jurisdictions = _refs_from(
        report,
        "jurisdiction_refs",
        "jurisdictions",
        "consumed_jurisdiction_refs",
    ) or _refs_from_value(context.get("jurisdiction_refs"))
    units = _refs_from(
        report,
        "unit_refs",
        "units",
        "consumed_unit_refs",
    ) or _refs_from_value(context.get("unit_refs"))
    periods = _refs_from(
        report,
        "period_refs",
        "periods",
        "time_refs",
        "time_windows",
        "consumed_period_refs",
    ) or _refs_from_value(context.get("period_refs"))
    geographies = _refs_from(
        report,
        "geography_refs",
        "geographies",
        "geo_refs",
        "consumed_geography_refs",
    ) or _refs_from_value(context.get("geography_refs"))
    explicit_candidates = _refs_from(
        report,
        "candidate_spine_binding_refs",
        "candidate_binding_refs",
        "spine_candidate_refs",
    )
    explicit_blockers = _blocker_ref_tuple(
        report,
        "spine_blocker_refs",
        "binding_blocker_refs",
        "spine_blockers",
    )
    generated_candidates = _producer_spine_candidate_binding_refs(
        component=component,
        context=context,
        candidate_refs=tuple(_refs_from_value(candidate_refs)),
    )
    generated_blockers = tuple(_refs_from_value(blocker_refs))
    candidates = tuple(dict.fromkeys([*explicit_candidates, *generated_candidates]))
    blockers = tuple(dict.fromkeys([*explicit_blockers, *generated_blockers]))
    if context and component and not candidates and not blockers:
        context_id = _optional_text(context.get("context_id")) or "unbound_context"
        blockers = (f"spine-blocker:{component}:candidate-binding-missing:{context_id}",)
    return {
        "consumed_concept_spine_ref": None if concept_ref == "unbound" else concept_ref,
        "consumed_jurisdiction_spine_ref": (
            None if jurisdiction_ref == "unbound" else jurisdiction_ref
        ),
        "canonical_concept_refs": canonical_concepts,
        "jurisdiction_refs": jurisdictions,
        "unit_refs": units,
        "period_refs": periods,
        "geography_refs": geographies,
        "candidate_spine_binding_refs": candidates,
        "spine_blocker_refs": blockers,
        "local_labels": _refs_from(
            report,
            "local_labels",
            "local_only_labels",
            "local_concept_labels",
        ),
    }


def _producer_spine_candidate_binding_refs(
    *,
    component: str | None,
    context: Mapping[str, Any],
    candidate_refs: Sequence[str],
) -> tuple[str, ...]:
    if not component or not context or not candidate_refs:
        return ()
    context_id = _optional_text(context.get("context_id")) or "unbound_context"
    concept_refs = _refs_from_value(context.get("canonical_concept_refs")) or ("unbound_concept",)
    jurisdiction_refs = _refs_from_value(context.get("jurisdiction_refs")) or (
        "unbound_jurisdiction",
    )
    refs: list[str] = []
    for candidate in candidate_refs:
        if candidate.startswith("spine-binding:"):
            refs.append(candidate)
            continue
        candidate_key = _stable_ref(
            {
                "context_id": context_id,
                "component": component,
                "candidate_ref": candidate,
            }
        ).removeprefix("sha256:")[:16]
        for concept_ref in concept_refs:
            for jurisdiction_ref in jurisdiction_refs:
                refs.append(
                    f"spine-binding:{component}:{concept_ref}:{jurisdiction_ref}:{candidate_key}"
                )
    return tuple(dict.fromkeys(refs))


def _refs_from(payload: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
    refs: list[str] = []
    for key in keys:
        refs.extend(_refs_from_value(payload.get(key)))
    return tuple(dict.fromkeys(refs))


def _blocker_ref_tuple(payload: Mapping[str, Any], *keys: str) -> tuple[str, ...]:
    return _refs_from(payload, *keys)


def _refs_from_value(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, Mapping):
        ref = (
            _optional_text(value.get("ref"))
            or _optional_text(value.get("id"))
            or _optional_text(value.get("snapshot_ref"))
            or _optional_text(value.get("legal_snapshot_ref"))
            or _optional_text(value.get("query_ref"))
            or _optional_text(value.get("concept_ref"))
            or _optional_text(value.get("conflict_id"))
            or _optional_text(value.get("competence_ref"))
            or _optional_text(value.get("field_ref"))
            or _optional_text(value.get("feature_ref"))
            or _optional_text(value.get("unit_ref"))
            or _optional_text(value.get("lineage_ref"))
            or _optional_text(value.get("transformation_ref"))
            or _optional_text(value.get("source_id"))
            or _optional_text(value.get("source_ref"))
            or _optional_text(value.get("norm_id"))
            or _optional_text(value.get("method_id"))
            or _optional_text(value.get("method_ref"))
            or _optional_text(value.get("method_output_ref"))
            or _optional_text(value.get("method_result_ref"))
            or _optional_text(value.get("result_ref"))
            or _optional_text(value.get("assumption_gate_ref"))
            or _optional_text(value.get("gate_ref"))
            or _optional_text(value.get("uncertainty_envelope_ref"))
            or _optional_text(value.get("limitation_ref"))
            or _optional_text(value.get("claim_id"))
        )
        if ref:
            return (ref,)
        refs: list[str] = []
        for item in value.values():
            refs.extend(_refs_from_value(item))
        return tuple(dict.fromkeys(refs))
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        refs: list[str] = []
        for item in value:
            refs.extend(_refs_from_value(item))
        return tuple(dict.fromkeys(refs))
    text = _optional_text(value)
    return (text,) if text else ()


def _coerce_ref_tuple(value: object) -> tuple[str, ...]:
    return _refs_from_value(value)


def _first_text(*values: object) -> str:
    for value in values:
        text = _optional_text(value)
        if text:
            return text
    return "unbound"


def _non_empty(value: object) -> str:
    text = _optional_text(value)
    if text is None:
        raise ValueError("required text is missing")
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _stable_ref(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


__all__ = [
    "PRODUCER_SPINE_CONSUMER_COMPONENTS",
    "PRODUCER_SPINE_CONTEXT_SCHEMA_VERSION",
    "ProducerSpineBindingFields",
    "ProducerSpineReadContext",
    "build_producer_spine_binding_fields",
]
