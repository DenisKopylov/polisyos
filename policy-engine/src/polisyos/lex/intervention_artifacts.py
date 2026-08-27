"""Artifact loaders and registries for Lex provision-to-policy mappings.

The registry objects in this module sit between legal extraction and intervention compilation:
JSON/parquet artifacts describe provision mappings, knob dictionaries, and program crosswalks,
then ``LexProvisionMappingRegistry.resolve`` materializes a ``LexProvisionDirective`` that can
be compiled into IR intervention contracts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from pydantic import Field, field_validator, model_validator

from polisyos.ir.governance.policy_spec import (
    CompiledLexIntervention as _CompiledLexIntervention,
)
from polisyos.ir.governance.policy_spec import (
    TemporalInterventionSequence,
)
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorExpr
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.kernel.values import ParamValue
from polisyos.ir.observation.bundles import StrategicResponseSpecsBundle
from polisyos.ir.observation.contracts import IdentificationMode, StrategicResponseChannel
from polisyos.ir.trinity import TrinityBundle

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping, Sequence

_JSON_LIST_KEYS = ("entries", "mappings", "items", "data")


class LexInterventionMapEntry(KernelModel):
    """Mapping from a legal provision to an executable policy intervention."""

    provision_ref: str = Field(..., min_length=1, max_length=200)
    intervention_kind: str = Field(..., pattern=ID_PATTERN)
    identification_mode: IdentificationMode | None = None
    strategic_response_expected: bool = False
    transmission_channels: list[StrategicResponseChannel] = Field(default_factory=list)
    target_population_type: str | None = Field(None, max_length=120)
    target_sector_ids: list[str] = Field(default_factory=list)
    target_region_ids: list[str] = Field(default_factory=list)
    measurement_expectations: dict[str, Any] = Field(default_factory=dict)
    knob_ids: list[str] = Field(..., min_length=1)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_strategy_channels(self) -> LexInterventionMapEntry:
        if self.strategic_response_expected and not self.transmission_channels:
            raise ValueError(
                "transmission_channels are required when strategic_response_expected=True"
            )
        return self


class InterventionKnobDictionaryEntry(KernelModel):
    """Dictionary entry describing one tunable intervention knob."""

    knob_id: str = Field(..., pattern=ID_PATTERN)
    param_id: str = Field(..., pattern=ID_PATTERN)
    param_path: str = Field(..., min_length=1, max_length=120)
    default_value: ParamValue
    min_value: ParamValue | None = None
    max_value: ParamValue | None = None
    tunable: bool = True
    sensitivity_priority: int = Field(default=5, ge=1, le=10)
    notes: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProvisionProgramCrosswalkEntry(KernelModel):
    """Crosswalk from a legal provision reference to a delivery program."""

    provision_ref: str = Field(..., min_length=1, max_length=200)
    program_id: str = Field(..., min_length=1, max_length=120)
    program_name: str = Field(..., min_length=1, max_length=255)
    target_region_ids: list[str] = Field(default_factory=list)
    target_sector_ids: list[str] = Field(default_factory=list)
    provenance_source: str | None = Field(None, max_length=255)
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list, max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LexPolicyBundleInput(KernelModel):
    """Bundle used to hand Lex-compiled interventions into Scientist and Foundry workflows.

    Attributes:
        trinity_bundle: Problem/policy/model context that anchors the candidate policy family.
        compiled_interventions: ``CompiledLexIntervention`` payloads or mapping-compatible rows.
        temporal_sequences: Optional ordered treatment sequences for DTR tasks.
        strategic_response_bundle: Optional expectations bundle for performative-response handling.
        metadata: Runtime/search metadata forwarded into candidate and search-plan generation.
    """

    trinity_bundle: TrinityBundle
    compiled_interventions: list[_CompiledLexIntervention] = Field(default_factory=list)
    temporal_sequences: list[TemporalInterventionSequence] = Field(default_factory=list)
    strategic_response_bundle: StrategicResponseSpecsBundle | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("compiled_interventions", mode="before")
    @classmethod
    def _coerce_missing_compiled_interventions(cls, value: Any) -> Any:
        """Preserve the public ``None``-as-empty compatibility contract."""
        return [] if value is None else value

def load_lex_intervention_map_entries(
    path: str | Path,
) -> list[LexInterventionMapEntry]:
    """Load provision-to-intervention mappings from a JSON artifact."""

    payload = _load_json_payload(path)
    return [LexInterventionMapEntry.model_validate(row) for row in payload]


def load_intervention_knob_dictionary_entries(
    path: str | Path,
) -> list[InterventionKnobDictionaryEntry]:
    """Load intervention knob dictionary entries from a JSON artifact."""

    payload = _load_json_payload(path)
    return [InterventionKnobDictionaryEntry.model_validate(row) for row in payload]


def load_provision_program_crosswalk_entries(
    path: str | Path,
) -> list[ProvisionProgramCrosswalkEntry]:
    """Load provision/program crosswalk entries from a parquet artifact."""

    resolved_path = Path(path)
    if resolved_path.exists():
        frame = pd.read_parquet(resolved_path)
        records = frame.to_dict(orient="records")
    else:
        json_fallback = resolved_path.with_suffix(".json")
        if resolved_path.suffix != ".parquet" or not json_fallback.exists():
            frame = pd.read_parquet(resolved_path)
            records = frame.to_dict(orient="records")
        else:
            records = _load_json_payload(json_fallback)
    return [ProvisionProgramCrosswalkEntry.model_validate(row) for row in records]


class LexProvisionMappingRegistry:
    """Lookup registry for provision mappings, knobs, and program crosswalks."""

    def __init__(
        self,
        *,
        intervention_map_entries: Iterable[LexInterventionMapEntry | Mapping[str, Any]] = (),
        knob_dictionary_entries: Iterable[InterventionKnobDictionaryEntry | Mapping[str, Any]] = (),
        crosswalk_entries: Iterable[ProvisionProgramCrosswalkEntry | Mapping[str, Any]] = (),
    ) -> None:
        self._intervention_map_entries: dict[str, LexInterventionMapEntry] = {}
        self._knob_dictionary_entries: dict[str, InterventionKnobDictionaryEntry] = {}
        self._crosswalk_entries: dict[str, ProvisionProgramCrosswalkEntry] = {}

        for entry in intervention_map_entries:
            self.register_intervention_map_entry(entry)
        for entry in knob_dictionary_entries:
            self.register_knob_dictionary_entry(entry)
        for entry in crosswalk_entries:
            self.register_crosswalk_entry(entry)

    @classmethod
    def from_artifacts(
        cls,
        *,
        intervention_map_path: str | Path,
        knob_dictionary_path: str | Path,
        crosswalk_path: str | Path | None = None,
    ) -> LexProvisionMappingRegistry:
        """Build a registry from exported mapping, knob, and optional crosswalk artifacts."""
        return cls(
            intervention_map_entries=load_lex_intervention_map_entries(intervention_map_path),
            knob_dictionary_entries=load_intervention_knob_dictionary_entries(knob_dictionary_path),
            crosswalk_entries=(
                load_provision_program_crosswalk_entries(crosswalk_path)
                if crosswalk_path is not None
                else ()
            ),
        )

    def register_intervention_map_entry(
        self,
        entry: LexInterventionMapEntry | Mapping[str, Any],
    ) -> LexInterventionMapEntry:
        """Register one provision mapping and reject duplicate ``provision_ref`` keys."""
        resolved = (
            entry
            if isinstance(entry, LexInterventionMapEntry)
            else LexInterventionMapEntry.model_validate(entry)
        )
        if resolved.provision_ref in self._intervention_map_entries:
            raise ValueError(
                f"duplicate intervention mapping for provision_ref '{resolved.provision_ref}'"
            )
        self._intervention_map_entries[resolved.provision_ref] = resolved
        return resolved

    def register_knob_dictionary_entry(
        self,
        entry: InterventionKnobDictionaryEntry | Mapping[str, Any],
    ) -> InterventionKnobDictionaryEntry:
        """Register one knob definition and reject duplicate ``knob_id`` keys."""
        resolved = (
            entry
            if isinstance(entry, InterventionKnobDictionaryEntry)
            else InterventionKnobDictionaryEntry.model_validate(entry)
        )
        if resolved.knob_id in self._knob_dictionary_entries:
            raise ValueError(f"duplicate knob dictionary entry '{resolved.knob_id}'")
        self._knob_dictionary_entries[resolved.knob_id] = resolved
        return resolved

    def register_crosswalk_entry(
        self,
        entry: ProvisionProgramCrosswalkEntry | Mapping[str, Any],
    ) -> ProvisionProgramCrosswalkEntry:
        """Register one provision-to-program crosswalk and reject duplicate provision refs."""
        resolved = (
            entry
            if isinstance(entry, ProvisionProgramCrosswalkEntry)
            else ProvisionProgramCrosswalkEntry.model_validate(entry)
        )
        if resolved.provision_ref in self._crosswalk_entries:
            raise ValueError(f"duplicate provision crosswalk entry for '{resolved.provision_ref}'")
        self._crosswalk_entries[resolved.provision_ref] = resolved
        return resolved

    def get_mapping(self, provision_ref: str) -> LexInterventionMapEntry | None:
        """Return the mapping entry for ``provision_ref`` or ``None`` if it is not registered."""
        return self._intervention_map_entries.get(provision_ref)

    def require_mapping(self, provision_ref: str) -> LexInterventionMapEntry:
        """Return the mapping entry for ``provision_ref`` or raise ``KeyError``."""
        resolved = self.get_mapping(provision_ref)
        if resolved is None:
            raise KeyError(f"intervention mapping not found for provision_ref '{provision_ref}'")
        return resolved

    def get_knob(self, knob_id: str) -> InterventionKnobDictionaryEntry | None:
        """Return a knob dictionary entry by ``knob_id`` or ``None``."""
        return self._knob_dictionary_entries.get(knob_id)

    def require_knob(self, knob_id: str) -> InterventionKnobDictionaryEntry:
        """Return a knob dictionary entry by ``knob_id`` or raise ``KeyError``."""
        resolved = self.get_knob(knob_id)
        if resolved is None:
            raise KeyError(f"knob dictionary entry not found for knob_id '{knob_id}'")
        return resolved

    def get_crosswalk(self, provision_ref: str) -> ProvisionProgramCrosswalkEntry | None:
        """Return the delivery-program crosswalk for a provision if one is available."""
        return self._crosswalk_entries.get(provision_ref)

    def resolve(
        self,
        provision_ref: str,
        *,
        intervention_id: str,
        target: SelectorExpr | Mapping[str, Any],
        schedule: ScheduleSpec | Mapping[str, Any],
        params: Mapping[str, ParamValue] | None = None,
        knob_value_overrides: Mapping[str, ParamValue] | None = None,
        target_population_type: str | None = None,
        target_sector_ids: Sequence[str] | None = None,
        target_region_ids: Sequence[str] | None = None,
        measurement_expectations: Mapping[str, Any] | None = None,
        identification_mode: IdentificationMode | None = None,
        strategic_response_expected: bool | None = None,
        transmission_channels: Sequence[StrategicResponseChannel] | None = None,
        notes: Sequence[str] = (),
        metadata: Mapping[str, Any] | None = None,
    ) -> Any:
        """Materialize a ``LexProvisionDirective`` from registry entries and caller overrides.

        Returns:
            Fully populated directive ready for ``LexInterventionCompiler.compile``.

        Raises:
            KeyError: If ``provision_ref`` is unknown or ``knob_value_overrides`` contains unknown
                knob ids.
        """
        from polisyos.lex.interventions import InterventionKnobSpec, LexProvisionDirective

        resolved_map = self.require_mapping(provision_ref)
        resolved_crosswalk = self.get_crosswalk(provision_ref)
        remaining_overrides = dict(knob_value_overrides or {})
        resolved_params = dict(params or {})
        resolved_knobs: list[InterventionKnobSpec] = []

        for knob_id in resolved_map.knob_ids:
            knob_entry = self.require_knob(knob_id)
            param_key = _param_key_from_path(knob_entry.param_path)
            default_value = remaining_overrides.pop(
                knob_id,
                resolved_params.get(param_key, knob_entry.default_value),
            )
            resolved_params.setdefault(param_key, default_value)
            resolved_knobs.append(
                InterventionKnobSpec(
                    param_id=knob_entry.param_id,
                    param_path=knob_entry.param_path,
                    default_value=default_value,
                    min_value=knob_entry.min_value,
                    max_value=knob_entry.max_value,
                    tunable=knob_entry.tunable,
                    sensitivity_priority=knob_entry.sensitivity_priority,
                    notes=list(knob_entry.notes),
                )
            )

        if remaining_overrides:
            raise KeyError(
                "unknown knob_value_overrides: " + ", ".join(sorted(remaining_overrides))
            )

        resolved_metadata = dict(metadata or {})
        resolved_metadata["knob_ids"] = list(resolved_map.knob_ids)
        resolved_metadata["provision_ref"] = provision_ref
        if resolved_map.confidence_score is not None:
            resolved_metadata["mapping_confidence_score"] = resolved_map.confidence_score
        if resolved_map.metadata:
            resolved_metadata["mapping_metadata"] = dict(resolved_map.metadata)

        if resolved_crosswalk is not None:
            resolved_metadata["program_id"] = resolved_crosswalk.program_id
            resolved_metadata["program_name"] = resolved_crosswalk.program_name
            if resolved_crosswalk.provenance_source is not None:
                resolved_metadata["crosswalk_provenance_source"] = (
                    resolved_crosswalk.provenance_source
                )
            if resolved_crosswalk.confidence_score is not None:
                resolved_metadata["crosswalk_confidence_score"] = (
                    resolved_crosswalk.confidence_score
                )
            if resolved_crosswalk.metadata:
                resolved_metadata["crosswalk_metadata"] = dict(resolved_crosswalk.metadata)

        return LexProvisionDirective(
            provision_ref=provision_ref,
            intervention_id=intervention_id,
            intervention_kind=resolved_map.intervention_kind,
            target=target,
            schedule=schedule,
            params=resolved_params,
            knobs=resolved_knobs,
            target_population_type=(
                target_population_type
                if target_population_type is not None
                else resolved_map.target_population_type
            ),
            target_sector_ids=_merge_sequence_override(
                override=target_sector_ids,
                primary=resolved_map.target_sector_ids,
                secondary=(
                    resolved_crosswalk.target_sector_ids if resolved_crosswalk is not None else ()
                ),
            ),
            target_region_ids=_merge_sequence_override(
                override=target_region_ids,
                primary=resolved_map.target_region_ids,
                secondary=(
                    resolved_crosswalk.target_region_ids if resolved_crosswalk is not None else ()
                ),
            ),
            measurement_expectations={
                **dict(resolved_map.measurement_expectations),
                **dict(measurement_expectations or {}),
            },
            identification_mode=(
                identification_mode
                if identification_mode is not None
                else resolved_map.identification_mode
            ),
            strategic_response_expected=(
                strategic_response_expected
                if strategic_response_expected is not None
                else resolved_map.strategic_response_expected
            ),
            transmission_channels=list(
                transmission_channels
                if transmission_channels is not None
                else resolved_map.transmission_channels
            ),
            notes=[*resolved_map.notes, *list(notes)],
            metadata=resolved_metadata,
        )


def _load_json_payload(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [dict(item) for item in payload]
    if isinstance(payload, dict):
        for key in _JSON_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(item) for item in value]
    raise ValueError(f"expected a JSON list payload at {path}")


def _param_key_from_path(param_path: str) -> str:
    normalized = param_path.removeprefix("params.")
    return normalized.split(".", 1)[0]


def _merge_sequence_override(
    *,
    override: Sequence[str] | None,
    primary: Sequence[str],
    secondary: Sequence[str],
) -> list[str]:
    if override is not None:
        return list(override)
    seen: set[str] = set()
    merged: list[str] = []
    for value in [*primary, *secondary]:
        if value in seen:
            continue
        seen.add(value)
        merged.append(value)
    return merged


__all__ = [
    "InterventionKnobDictionaryEntry",
    "LexInterventionMapEntry",
    "LexPolicyBundleInput",
    "LexProvisionMappingRegistry",
    "ProvisionProgramCrosswalkEntry",
    "load_intervention_knob_dictionary_entries",
    "load_lex_intervention_map_entries",
    "load_provision_program_crosswalk_entries",
]
