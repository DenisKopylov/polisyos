"""Public analytics abstraction module API."""
from __future__ import annotations

import math
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.analytics.structural_causal_model import NodeMechanism, StructuralCausalModelSpec
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.refs import (
    AbstractionCertificateRef,
    ArtifactRefModel,
    FiniteStateAbstractionMapRef,
)

_FINITE_STATE_ABSTRACTION_MAP_SCHEMA_NAME = "ir.finite_state_abstraction_map"
_FINITE_STATE_ABSTRACTION_MAP_SCHEMA_VERSION = "1.0"
_ABSTRACTION_CERTIFICATE_SCHEMA_NAME = "ir.abstraction_certificate"
_ABSTRACTION_CERTIFICATE_SCHEMA_VERSION = "1.0"
_EXACT_MATCH_TOLERANCE = 1e-9


def _ensure_non_empty(value: str, *, field_name: str) -> str:
    candidate = str(value).strip()
    if not candidate:
        raise ValueError(f"{field_name} must be non-empty")
    return candidate


def _ensure_finite(value: float | None, *, field_name: str) -> float | None:
    if value is None:
        return None
    casted = float(value)
    if not math.isfinite(casted):
        raise ValueError(f"{field_name} must be finite")
    return casted


def _validate_artifact_ref(ref: ArtifactRefModel, *, field_name: str) -> ArtifactRefModel:
    if not str(ref.kind).strip():
        raise ValueError(f"{field_name}.kind must be non-empty")
    if not str(ref.media_type).strip():
        raise ValueError(f"{field_name}.media_type must be non-empty")
    return ref


class AbstractionPreservationType(str, Enum):
    """Abstraction preservation type public type."""
    EXACT = "exact"
    APPROXIMATE = "approximate"
    POLICY_VALUE_ONLY = "policy_value_only"
    INVALID = "invalid"


class VariableStateAbstraction(BaseModel):
    """One-to-one variable/state quotient used by the exact finite-state verifier."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    micro_variable: str
    macro_variable: str
    state_map: dict[str, str]

    @field_validator("micro_variable", "macro_variable", mode="before")
    @classmethod
    def _validate_strings(cls, value: Any, info: Any) -> str:
        return _ensure_non_empty(str(value), field_name=str(info.field_name))

    @model_validator(mode="after")
    def _validate_state_map(self) -> "VariableStateAbstraction":
        if not self.state_map:
            raise ValueError("state_map must be non-empty")
        for micro_state, macro_state in self.state_map.items():
            _ensure_non_empty(micro_state, field_name="state_map.micro_state")
            _ensure_non_empty(macro_state, field_name="state_map.macro_state")
        return self


class FiniteStateAbstractionMap(BaseModel):
    """Exact finite-state variable/state quotient map for micro-to-macro verification."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    variable_maps: tuple[VariableStateAbstraction, ...]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_variables(self) -> "FiniteStateAbstractionMap":
        if not self.variable_maps:
            raise ValueError("variable_maps must be non-empty")
        micro_vars = [item.micro_variable for item in self.variable_maps]
        macro_vars = [item.macro_variable for item in self.variable_maps]
        if len(set(micro_vars)) != len(micro_vars):
            raise ValueError("micro_variable values must be unique")
        if len(set(macro_vars)) != len(macro_vars):
            raise ValueError("macro_variable values must be unique")
        return self

    @property
    def micro_to_macro(self) -> dict[str, str]:
        return {item.micro_variable: item.macro_variable for item in self.variable_maps}

    @property
    def by_micro_variable(self) -> dict[str, VariableStateAbstraction]:
        return {item.micro_variable: item for item in self.variable_maps}

    @property
    def by_macro_variable(self) -> dict[str, VariableStateAbstraction]:
        return {item.macro_variable: item for item in self.variable_maps}


class AbstractionCertificate(BaseModel):
    """Certificate for query-preserving finite-state abstraction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    micro_graph_ref: ArtifactRefModel
    macro_graph_ref: ArtifactRefModel
    abstraction_map_ref: FiniteStateAbstractionMapRef
    preservation_type: AbstractionPreservationType
    preserved_queries: tuple[str, ...] = ()
    error_bound: float | None = None
    validation_notes: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("preserved_queries", "validation_notes", mode="before")
    @classmethod
    def _coerce_string_tuples(cls, value: Any) -> tuple[str, ...]:
        if value in (None, ()):
            return ()
        if not isinstance(value, (tuple, list)):
            raise ValueError("tuple fields must be a tuple/list of strings")
        return tuple(_ensure_non_empty(str(item), field_name="tuple_item") for item in value)

    @field_validator("error_bound", mode="before")
    @classmethod
    def _validate_error_bound(cls, value: Any) -> Any:
        return _ensure_finite(value, field_name="error_bound")

    @model_validator(mode="after")
    def _validate_contract(self) -> "AbstractionCertificate":
        _validate_artifact_ref(self.micro_graph_ref, field_name="micro_graph_ref")
        _validate_artifact_ref(self.macro_graph_ref, field_name="macro_graph_ref")
        if self.preservation_type in {
            AbstractionPreservationType.EXACT,
            AbstractionPreservationType.INVALID,
        } and self.error_bound is not None:
            raise ValueError(
                "exact and invalid abstraction certificates must not publish a numeric error_bound"
            )
        if self.preservation_type is AbstractionPreservationType.EXACT and not self.preserved_queries:
            raise ValueError("exact abstraction certificates must list preserved_queries")
        return self


def persist_finite_state_abstraction_map(
    store: ArtifactStore,
    abstraction_map: FiniteStateAbstractionMap,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _FINITE_STATE_ABSTRACTION_MAP_SCHEMA_NAME,
    schema_version: str = _FINITE_STATE_ABSTRACTION_MAP_SCHEMA_VERSION,
) -> FiniteStateAbstractionMapRef:
    """Persist finite state abstraction map helper."""
    ref = put_json_artifact(
        store,
        abstraction_map.model_dump(mode="json"),
        kind="ir.finite_state_abstraction_map",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return FiniteStateAbstractionMapRef.model_validate(ref)


def load_finite_state_abstraction_map(
    store: ArtifactStore,
    ref: FiniteStateAbstractionMapRef,
) -> FiniteStateAbstractionMap:
    """Load finite state abstraction map."""
    payload = get_json_artifact(store, ref.artifact_id)
    return FiniteStateAbstractionMap.model_validate(payload)


def persist_abstraction_certificate(
    store: ArtifactStore,
    certificate: AbstractionCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _ABSTRACTION_CERTIFICATE_SCHEMA_NAME,
    schema_version: str = _ABSTRACTION_CERTIFICATE_SCHEMA_VERSION,
) -> AbstractionCertificateRef:
    """Persist abstraction certificate helper."""
    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.abstraction_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return AbstractionCertificateRef.model_validate(ref)


def load_abstraction_certificate(
    store: ArtifactStore,
    ref: AbstractionCertificateRef,
) -> AbstractionCertificate:
    """Load abstraction certificate."""
    payload = get_json_artifact(store, ref.artifact_id)
    return AbstractionCertificate.model_validate(payload)


def _mechanism_by_variable(spec: StructuralCausalModelSpec) -> dict[str, NodeMechanism]:
    return {mechanism.variable: mechanism for mechanism in spec.mechanisms}


def _normalized_distribution(
    distribution: dict[str, Any],
    *,
    state_space: tuple[str, ...],
    field_name: str,
) -> dict[str, float]:
    missing = sorted(set(state_space) - set(distribution))
    extra = sorted(set(distribution) - set(state_space))
    if missing or extra:
        raise ValueError(
            f"{field_name} must align with state_space exactly; missing={missing}, extra={extra}"
        )
    normalized: dict[str, float] = {}
    total = 0.0
    for state in state_space:
        value = _ensure_finite(distribution[state], field_name=f"{field_name}.{state}")
        if value is None or value < 0.0:
            raise ValueError(f"{field_name}.{state} must be non-negative")
        normalized[state] = float(value)
        total += float(value)
    if not math.isclose(total, 1.0, rel_tol=0.0, abs_tol=_EXACT_MATCH_TOLERANCE):
        raise ValueError(f"{field_name} must sum to 1.0, got {total}")
    return normalized


def _conditional_key(
    parents: tuple[str, ...],
    assignment: dict[str, str],
) -> tuple[tuple[str, str], ...]:
    return tuple((parent, assignment[parent]) for parent in parents)


def _extract_finite_state_table(
    mechanism: NodeMechanism,
) -> tuple[tuple[str, ...], dict[tuple[tuple[str, str], ...], dict[str, float]]]:
    params = mechanism.family_params
    if not isinstance(params, dict):
        raise ValueError(f"{mechanism.variable}.family_params must be a mapping")
    raw_state_space = params.get("state_space")
    if not isinstance(raw_state_space, list) or not raw_state_space:
        raise ValueError(f"{mechanism.variable}.family_params.state_space must be a non-empty list")
    state_space = tuple(
        _ensure_non_empty(str(state), field_name=f"{mechanism.variable}.state_space")
        for state in raw_state_space
    )
    if len(set(state_space)) != len(state_space):
        raise ValueError(f"{mechanism.variable}.state_space must be unique")

    root_distribution = params.get("distribution", params.get("probabilities"))
    if not mechanism.parents:
        if not isinstance(root_distribution, dict):
            raise ValueError(
                f"{mechanism.variable}.family_params.distribution must be a mapping for root variables"
            )
        return (
            state_space,
            {(): _normalized_distribution(root_distribution, state_space=state_space, field_name=f"{mechanism.variable}.distribution")},
        )

    raw_entries = params.get("conditional_distribution", params.get("conditional_probabilities"))
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError(
            f"{mechanism.variable}.family_params.conditional_distribution must be a non-empty list"
        )

    table: dict[tuple[tuple[str, str], ...], dict[str, float]] = {}
    parent_tuple = tuple(mechanism.parents)
    for idx, entry in enumerate(raw_entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{mechanism.variable}.conditional_distribution[{idx}] must be a mapping")
        raw_when = entry.get("when")
        raw_distribution = entry.get("distribution")
        if not isinstance(raw_when, dict) or not isinstance(raw_distribution, dict):
            raise ValueError(
                f"{mechanism.variable}.conditional_distribution[{idx}] must contain when and distribution mappings"
            )
        if set(raw_when) != set(parent_tuple):
            raise ValueError(
                f"{mechanism.variable}.conditional_distribution[{idx}].when must match parents exactly"
            )
        assignment = {
            parent: _ensure_non_empty(raw_when[parent], field_name=f"{mechanism.variable}.when.{parent}")
            for parent in parent_tuple
        }
        key = _conditional_key(parent_tuple, assignment)
        if key in table:
            raise ValueError(f"{mechanism.variable}.conditional_distribution contains duplicate parent assignments")
        table[key] = _normalized_distribution(
            raw_distribution,
            state_space=state_space,
            field_name=f"{mechanism.variable}.conditional_distribution[{idx}].distribution",
        )
    return state_space, table


def _aggregate_distribution(
    distribution: dict[str, float],
    state_map: dict[str, str],
) -> dict[str, float]:
    aggregated: dict[str, float] = {}
    for micro_state, probability in distribution.items():
        macro_state = state_map[micro_state]
        aggregated[macro_state] = aggregated.get(macro_state, 0.0) + float(probability)
    return aggregated


def _distributions_match(
    left: dict[str, float],
    right: dict[str, float],
) -> bool:
    if set(left) != set(right):
        return False
    for key in left:
        if not math.isclose(left[key], right[key], rel_tol=0.0, abs_tol=_EXACT_MATCH_TOLERANCE):
            return False
    return True


def verify_finite_state_exact_abstraction(
    micro_scm: StructuralCausalModelSpec,
    macro_scm: StructuralCausalModelSpec,
    abstraction_map: FiniteStateAbstractionMap,
    *,
    micro_graph_ref: ArtifactRefModel,
    macro_graph_ref: ArtifactRefModel,
    abstraction_map_ref: FiniteStateAbstractionMapRef,
    preserved_queries: tuple[str, ...] | list[str] | None = None,
) -> AbstractionCertificate:
    """Verify a one-to-one finite-state abstraction and return a certificate."""

    notes: list[str] = []
    try:
        if micro_scm.graph.graph_type.value != "dag" or macro_scm.graph.graph_type.value != "dag":
            notes.append("exact_finite_state_abstraction_requires_dag_graphs")
            raise ValueError(notes[-1])

        micro_mechanisms = _mechanism_by_variable(micro_scm)
        macro_mechanisms = _mechanism_by_variable(macro_scm)
        mapping_by_micro = abstraction_map.by_micro_variable
        mapping_by_macro = abstraction_map.by_macro_variable

        if set(mapping_by_micro) != set(micro_mechanisms):
            notes.append("abstraction_map_must_cover_all_micro_variables")
            raise ValueError(notes[-1])
        if set(mapping_by_macro) != set(macro_mechanisms):
            notes.append("abstraction_map_must_cover_all_macro_variables")
            raise ValueError(notes[-1])

        for micro_variable, variable_map in mapping_by_micro.items():
            macro_variable = variable_map.macro_variable
            micro_mechanism = micro_mechanisms[micro_variable]
            macro_mechanism = macro_mechanisms[macro_variable]

            mapped_parents = tuple(
                abstraction_map.micro_to_macro.get(parent, "")
                for parent in micro_mechanism.parents
            )
            if mapped_parents != tuple(macro_mechanism.parents):
                notes.append(
                    f"parent_structure_mismatch:{micro_variable}->{macro_variable}"
                )
                raise ValueError(notes[-1])

            micro_state_space, micro_table = _extract_finite_state_table(micro_mechanism)
            macro_state_space, macro_table = _extract_finite_state_table(macro_mechanism)

            if set(variable_map.state_map) != set(micro_state_space):
                notes.append(
                    f"state_map_must_cover_micro_state_space:{micro_variable}"
                )
                raise ValueError(notes[-1])
            if not set(variable_map.state_map.values()).issubset(set(macro_state_space)):
                notes.append(
                    f"state_map_targets_unknown_macro_states:{micro_variable}->{macro_variable}"
                )
                raise ValueError(notes[-1])

            for macro_parent_key, macro_distribution in macro_table.items():
                compatible_micro_keys = []
                for micro_parent_key in micro_table:
                    compatible = True
                    for micro_parent, micro_state in micro_parent_key:
                        mapped_macro_parent = abstraction_map.micro_to_macro[micro_parent]
                        expected_macro_state = dict(macro_parent_key)[mapped_macro_parent]
                        parent_map = mapping_by_micro[micro_parent].state_map
                        if parent_map[micro_state] != expected_macro_state:
                            compatible = False
                            break
                    if compatible:
                        compatible_micro_keys.append(micro_parent_key)

                if not compatible_micro_keys:
                    notes.append(
                        f"missing_micro_parent_assignment_for_macro_context:{macro_variable}"
                    )
                    raise ValueError(notes[-1])

                aggregated_candidates = [
                    _aggregate_distribution(micro_table[micro_key], variable_map.state_map)
                    for micro_key in compatible_micro_keys
                ]
                first_candidate = aggregated_candidates[0]
                if not all(
                    _distributions_match(first_candidate, candidate)
                    for candidate in aggregated_candidates[1:]
                ):
                    notes.append(
                        f"micro_conditionals_not_lumpable:{micro_variable}->{macro_variable}"
                    )
                    raise ValueError(notes[-1])
                if not _distributions_match(first_candidate, macro_distribution):
                    notes.append(
                        f"macro_distribution_mismatch:{micro_variable}->{macro_variable}"
                    )
                    raise ValueError(notes[-1])

        return AbstractionCertificate(
            micro_graph_ref=micro_graph_ref,
            macro_graph_ref=macro_graph_ref,
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.EXACT,
            preserved_queries=tuple(preserved_queries or ("observational", "interventional")),
            error_bound=None,
            validation_notes=tuple(notes) if notes else ("exact_finite_state_abstraction_verified",),
        )
    except ValueError:
        return AbstractionCertificate(
            micro_graph_ref=micro_graph_ref,
            macro_graph_ref=macro_graph_ref,
            abstraction_map_ref=abstraction_map_ref,
            preservation_type=AbstractionPreservationType.INVALID,
            preserved_queries=(),
            error_bound=None,
            validation_notes=tuple(notes) if notes else ("exact_finite_state_abstraction_invalid",),
        )


__all__ = [
    "AbstractionCertificate",
    "AbstractionPreservationType",
    "FiniteStateAbstractionMap",
    "VariableStateAbstraction",
    "load_abstraction_certificate",
    "load_finite_state_abstraction_map",
    "persist_abstraction_certificate",
    "persist_finite_state_abstraction_map",
    "verify_finite_state_exact_abstraction",
]
