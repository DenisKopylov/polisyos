"""Runtime bridge for L6 intervention levers and method routes.

This module does not own a second lever, method, or legal hierarchy. It reads
the L6 agent-sim bundle, validates it against existing owners, and emits
content-addressed resolution records that N2/N4/N8 can consume.
"""

from __future__ import annotations

import ast
import copy
import importlib
import importlib.util
import json
import math
import os
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal, Protocol, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.interventions import (
    InterventionContext,
    NodeIntervention,
    QueryTarget,
    VariableAssignment,
    identification_plan_for_intervention,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_METRIC_REGISTRY,
    DEFAULT_SELECTOR_FIELD_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
    DEFAULT_UNITS_REGISTRY,
    ConstraintRegistry,
    MechanismTypeRegistry,
    MechanismTypeSpec,
    ParamSpec,
    ParamType,
    SlotRegistry,
)
from polisyos.ir.linker import link_trinity
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.model_layer.types import SelectorOperator
from polisyos.ir.registry.registry_fragments import RegistryBundle
from polisyos.ir.trinity import TrinityBundle
from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
from polisyos.runtime.quality.intervention_atom_binding import (
    build_intervention_atom_binding,
    intervention_atom_target_selector_ref,
)
from polisyos.runtime.quality.world_model_record import (
    WorldModelRecord,
    WorldModelRecordError,
    resolve_intervention_atom_world_binding,
)

if TYPE_CHECKING:
    from polisyos.foundry import MethodRouteConstraint
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext

INTERVENTION_SUBSTRATE_SCHEMA_VERSION = "policyos.runtime.intervention_substrate_lift.v2"
INTERVENTION_SUBSTRATE_ARTIFACT_KIND = "runtime.quality.intervention_substrate_lift"

DEFAULT_L6_BUNDLE_ROOT = Path(
    "production_data/ukraine_agent_simulation_baseline_20260410/production_bundle/bundles"
)
DEFAULT_L3_LEX_DB_PATH = Path(
    "production_data/lex/lex-amendment-only-optimized-20260501-v3/"
    "finalize/lex_knowledge_graph.duckdb"
)
DEFAULT_L6_OWNER_AUTHORITY_PATH = Path(
    "architecture/policy_design_case/layer3_gy_l6_owner_authority_bindings.json"
)
_REPRESENTATIVE_L3_THRESHOLD_ID = "a5429abb6621acb11ed10b20"
_REPRESENTATIVE_L3_AS_OF = "1998-01-01"
_BUDGET_LAW = "budget_law"
_DANGLING_LAW = "dangling_law"
_FUTURE_RELIEF_LAW = "future_relief_law"
_UNKNOWN_LAW_MODALITY = "unknown_legal_modality"
_FREE_GROW_L3_THRESHOLD_ID = "00000109f781085bd1736cf1"
_FREE_GROW_L3_AS_OF = "2026-04-10"
_FREE_GROW_KNOB = "future_child_benefit_intensity"
_FREE_GROW_MECHANISM = "future_child_benefit_transfer"
_FREE_GROW_SLOT = "household_cells.transfer_intensity"
_COMPOSED_WMR_AGENT_LIMIT = 16
_COMPOSED_WMR_REQUIRED_SUBSTRATE_FAMILIES = (
    "budget_flows",
    "firm_fundamentals",
    "household_distribution",
    "distress_enforcement",
    "l2_scholar_kg_causal_priors_transport",
    "l3_lex_kg_admissibility_obligations",
    "l6_intervention_knob_dictionary",
    "l6_lex_intervention_map",
    "l6_observation_contract_routes",
    "l6_policy_scenario_templates",
)


class _MethodSlotProtocol(Protocol):
    contract_id: str | None


class _MethodSignatureProtocol(Protocol):
    fqn: str
    family: str
    data_modalities: Sequence[str]
    input_slots: Sequence[_MethodSlotProtocol]
    output_slots: Sequence[_MethodSlotProtocol]


class _MethodMetadataProtocol(Protocol):
    tags: Sequence[object]
    contracts: object | None
    required_deps: Sequence[object]
    optional_deps: Sequence[object]


class _MethodEntryProtocol(Protocol):
    metadata: _MethodMetadataProtocol


class _MethodRegistryProtocol(Protocol):
    def list_all(self) -> Sequence[_MethodSignatureProtocol]: ...

    def get_entry(self, fqn: str) -> _MethodEntryProtocol | None: ...

    def get(self, fqn: str) -> object: ...


class _ThresholdRefProtocol(Protocol):
    threshold_id: str
    applies_to: str | None


class _RuleThresholdProtocol(Protocol):
    threshold_id: str
    provision_ref: str | None
    applies_to: str | None


class _LegalThresholdEvaluationProtocol(Protocol):
    status: str
    reason: str | None

    def model_dump(self, *, mode: str) -> dict[str, Any]: ...


class _LegalTemporalCompetenceProtocol(Protocol):
    def model_dump(self, *, mode: str) -> dict[str, Any]: ...


class _LegalKnowledgeStoreProtocol(Protocol):
    def resolve_rule_threshold(self, **kwargs: object) -> _RuleThresholdProtocol | None: ...

    def evaluate_rule_threshold(self, **kwargs: object) -> _LegalThresholdEvaluationProtocol: ...

    def resolve_threshold_temporal_competence(
        self,
        **kwargs: object,
    ) -> _LegalTemporalCompetenceProtocol: ...


class _LexProvisionMappingProtocol(Protocol):
    knob_ids: Sequence[str]


class _LexProvisionMappingRegistryProtocol(Protocol):
    def require_mapping(self, provision_ref: str) -> _LexProvisionMappingProtocol: ...

    def require_knob(self, knob_id: str) -> object: ...

    def resolve(self, provision_ref: str, **kwargs: object) -> object: ...


class InterventionSubstrateError(ValueError):
    """Fail-closed error for unresolved or authority-inflating L6 substrate routes."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class RouteStatus(StrEnum):
    """Status emitted by method routing."""

    ROUTED = "routed"
    BLOCKED = "blocked"


class _StrictModel(BaseModel):
    """Strict immutable base for runtime resolution records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class KnobDomain(_StrictModel):
    """Content-bound domain declared by an L6 intervention knob."""

    kind: Literal["range", "discrete"]
    value_type: str = Field(..., min_length=1)
    min_value: float | int | None = None
    max_value: float | int | None = None
    unit: str | None = None

    @model_validator(mode="after")
    def _validate_domain_shape(self) -> KnobDomain:
        if self.kind == "range" and (self.min_value is None or self.max_value is None):
            raise ValueError("range_domain_bounds_missing")
        if (
            self.kind == "range"
            and self.min_value is not None
            and self.max_value is not None
            and float(self.min_value) > float(self.max_value)
        ):
            raise ValueError("range_domain_bounds_inverted")
        return self


class InterventionLeverResolution(_StrictModel):
    """Resolved atom lever-space record for one operator/value pair."""

    schema_version: str = INTERVENTION_SUBSTRATE_SCHEMA_VERSION
    operator_kind: str = Field(..., min_length=1)
    parameter_value: float | int | str | bool
    domain: KnobDomain
    target_world_slots: tuple[str, ...]
    owner_resolution: dict[str, Any]
    source_ref: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


class InterventionLeverRefusal(_StrictModel):
    """Content-bound refusal for a selected candidate with no L6 binding."""

    schema_version: str = INTERVENTION_SUBSTRATE_SCHEMA_VERSION
    status: Literal["candidate_unbound", "acquisition_required"]
    operator_kind: str = Field(..., min_length=1)
    instrument: str = Field(..., min_length=1)
    lever_id: str = Field(..., min_length=1)
    reason_code: str = Field(..., min_length=1)
    candidate_entry_content_hash: str = Field(
        ...,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    selected_registry_entry_hash: str = Field(
        ...,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    substrate_input_content_hash: str = Field(
        ...,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    context_binding_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    substrate_registry_content_hash: str = Field(
        ...,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    world_model_record_content_hash: str = Field(
        ...,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    source_refs: tuple[str, ...]
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_refusal_content(self) -> InterventionLeverRefusal:
        if not self.source_refs or any(not item.strip() for item in self.source_refs):
            raise ValueError("intervention_lever_refusal_source_refs_missing")
        payload = gy_artifact_self_identity_projection(self)
        expected = gy_content_hash(payload)
        if self.content_hash != expected:
            raise ValueError("intervention_lever_refusal_content_hash_mismatch")
        return self


class LawAuthorityRef(_StrictModel):
    """Owner-derived L3 authority for one legal modality/provision binding."""

    threshold_id: str | None = None
    metric: str | None = None
    doc_family_id: str | None = None
    provision_ref: str | None = None
    candidate_unit: str | None = None
    applies_to: str | None = None
    as_of: str | None = None
    jurisdiction: str | None = None
    domain: str | None = None

    @model_validator(mode="after")
    def _threshold_key_required(self) -> LawAuthorityRef:
        if not self.threshold_id and not self.metric:
            raise ValueError("law_authority_threshold_key_missing")
        return self


class LawLeverResolution(_StrictModel):
    """Candidate law/knob trace with independently bounded current authority.

    A real threshold evaluation does not verify its correspondence to a knob.
    Historical v1 records remain readable, but never grant current authority.
    """

    schema_version: str = INTERVENTION_SUBSTRATE_SCHEMA_VERSION
    law_token: str = Field(..., min_length=1)
    status: Literal["admissible", "blocked"]
    knob: InterventionLeverResolution
    threshold_id: str = Field(..., min_length=1)
    provision_ref: str = Field(..., min_length=1)
    legal_threshold_evaluation: dict[str, Any]
    temporal_competence: dict[str, Any]
    mapping_predicate_provenance: Literal["consumer_asserted", "not_established"] = (
        "not_established"
    )
    mapping_evidence_ref: None = None
    current_authority_status: Literal["blocked"] = "blocked"
    mapping_reason_code: Literal["law_mapping_correspondence_not_established"] = (
        "law_mapping_correspondence_not_established"
    )
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _current_mapping_authority_requires_evidence(self) -> LawLeverResolution:
        if self.schema_version == INTERVENTION_SUBSTRATE_SCHEMA_VERSION:
            if self.status != "blocked":
                raise ValueError("law_mapping_correspondence_not_established")
            if self.content_hash != gy_content_hash(gy_artifact_self_identity_projection(self)):
                raise ValueError("law_mapping_resolution_content_hash_mismatch")
        elif self.schema_version == "policyos.runtime.intervention_substrate_lift.v1":
            historical = self.model_dump(mode="json")
            for key in (
                "mapping_evidence_ref",
                "mapping_predicate_provenance",
                "current_authority_status",
                "mapping_reason_code",
                "content_hash",
            ):
                historical.pop(key)
            if self.content_hash != gy_content_hash(historical):
                raise ValueError("law_mapping_historical_content_hash_mismatch")
        else:
            raise ValueError("law_mapping_epoch_unsupported")
        return self


class ObservationMethodRoute(_StrictModel):
    """Resolved observation family -> method contract -> registry method route."""

    schema_version: str = INTERVENTION_SUBSTRATE_SCHEMA_VERSION
    family: str = Field(..., min_length=1)
    status: RouteStatus
    target_contract_id: str = Field(..., min_length=1)
    target_contract_fqn: str | None = None
    selected_method_fqn: str | None = None
    reason_code: str | None = None
    registry_method_count: int = Field(..., ge=0)
    candidate_method_fqns: tuple[str, ...] = ()
    unavailable_method_fqns: tuple[str, ...] = ()
    manifest_route_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")


class InterventionSubstrateBundle(_StrictModel):
    """Loaded L6 bundle payload and source hashes."""

    schema_version: str = INTERVENTION_SUBSTRATE_SCHEMA_VERSION
    knob_dictionary: dict[str, Any]
    lex_intervention_map: dict[str, Any]
    observation_manifest: dict[str, Any]
    policy_scenario_templates: dict[str, Any] = Field(default_factory=dict)
    slot_family_manifest: dict[str, Any] = Field(default_factory=dict)
    world_mechanism_manifest: dict[str, Any] = Field(default_factory=dict)
    lex_authority_manifest: dict[str, Any] = Field(default_factory=dict)
    owner_authority_manifest: dict[str, Any] = Field(default_factory=dict)
    source_refs: dict[str, str]
    source_content_hashes: dict[str, str]
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _validate_content_hash(self) -> InterventionSubstrateBundle:
        _assert_intervention_substrate_bundle_content_hash(self)
        return self


def intervention_substrate_bundle_content_hash(
    bundle: InterventionSubstrateBundle | Mapping[str, Any],
) -> str:
    """Return the canonical full-payload hash for an L6 substrate bundle."""

    payload = gy_artifact_self_identity_projection(bundle)
    return gy_content_hash(payload)


def verify_intervention_substrate_bundle_content_hash(
    bundle: InterventionSubstrateBundle,
) -> InterventionSubstrateBundle:
    """Verify and return a fresh snapshot of one L6 substrate bundle."""

    payload = bundle.model_dump(mode="python")
    _assert_intervention_substrate_bundle_content_hash(payload)
    return InterventionSubstrateBundle.model_validate(payload)


def _assert_intervention_substrate_bundle_content_hash(
    bundle: InterventionSubstrateBundle | Mapping[str, Any],
) -> None:
    expected = intervention_substrate_bundle_content_hash(bundle)
    actual = (
        bundle.content_hash
        if isinstance(bundle, InterventionSubstrateBundle)
        else str(bundle.get("content_hash") or "")
    )
    if actual != expected:
        raise InterventionSubstrateError(
            "intervention_substrate_bundle_content_hash_mismatch",
            f"expected {expected}, got {actual}",
        )


def replace_intervention_substrate_bundle(
    bundle: InterventionSubstrateBundle,
    *,
    update: Mapping[str, Any],
) -> InterventionSubstrateBundle:
    """Return a validated bundle after content-addressing top-level updates."""

    if "content_hash" in update:
        raise InterventionSubstrateError(
            "intervention_substrate_content_hash_update_forbidden"
        )
    verified = verify_intervention_substrate_bundle_content_hash(bundle)
    payload = gy_artifact_self_identity_projection(verified)
    payload.update(
        dict(update)
    )
    payload["content_hash"] = intervention_substrate_bundle_content_hash(payload)
    return InterventionSubstrateBundle.model_validate(payload)


def default_l6_bundle_paths(repo_root: Path) -> dict[str, Path]:
    """Return canonical L6 agent-sim bundle paths under ``repo_root``."""

    root = repo_root / DEFAULT_L6_BUNDLE_ROOT
    return {
        "intervention_knob_dictionary": (
            root / "intervention_bundle_v1/intervention_knob_dictionary.json"
        ),
        "lex_intervention_map": root / "intervention_bundle_v1/lex_intervention_map.json",
        "observation_to_contract_manifest": (
            root / "method_contract_bundle_v1/observation_to_contract_manifest.json"
        ),
        "policy_scenario_templates": (
            root / "intervention_bundle_v1/policy_scenario_templates.json"
        ),
        "slot_family_manifest": root / "runtime_bundle_v1/slot_family_manifest.json",
        "owner_authority_bindings": repo_root / DEFAULT_L6_OWNER_AUTHORITY_PATH,
    }


def load_l6_intervention_substrate(repo_root: Path) -> InterventionSubstrateBundle:
    """Load the real L6 agent-sim control artifacts with content hashes."""

    paths = default_l6_bundle_paths(repo_root.resolve())
    required = (
        "intervention_knob_dictionary",
        "lex_intervention_map",
        "observation_to_contract_manifest",
    )
    missing = [name for name in required if not paths[name].is_file()]
    if missing:
        raise InterventionSubstrateError(
            "l6_control_artifact_missing",
            ", ".join(sorted(missing)),
        )
    payloads: dict[str, dict[str, Any]] = {}
    source_refs: dict[str, str] = {}
    source_hashes: dict[str, str] = {}
    for name, path in paths.items():
        if not path.exists():
            if name in required:
                raise InterventionSubstrateError("l6_control_artifact_missing", name)
            payloads[name] = {}
            continue
        payload = _read_json_object(path)
        payloads[name] = payload
        source_refs[name] = _repo_ref(path, repo_root)
        source_hashes[name] = gy_content_hash(payload)

    fields = {
        "schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "knob_dictionary": payloads["intervention_knob_dictionary"],
        "lex_intervention_map": payloads["lex_intervention_map"],
        "observation_manifest": payloads["observation_to_contract_manifest"],
        "policy_scenario_templates": payloads.get("policy_scenario_templates", {}),
        "slot_family_manifest": payloads.get("slot_family_manifest", {}),
        "world_mechanism_manifest": (
            payloads.get("owner_authority_bindings", {}).get("world_mechanism_manifest")
            or {}
        ),
        "lex_authority_manifest": (
            payloads.get("owner_authority_bindings", {}).get("lex_authority_manifest")
            or {}
        ),
        "owner_authority_manifest": payloads.get("owner_authority_bindings", {}),
        "source_refs": source_refs,
        "source_content_hashes": source_hashes,
    }
    return InterventionSubstrateBundle(
        **fields,
        content_hash=intervention_substrate_bundle_content_hash(fields),
    )


def resolve_intervention_lever(
    bundle: InterventionSubstrateBundle,
    *,
    operator_kind: str,
    parameter_value: object,
    world_model_record: WorldModelRecord | None = None,
    cycle_substrate_context: CycleSubstrateContext | None = None,
) -> InterventionLeverResolution | InterventionLeverRefusal:
    """Resolve an atom operator/value against the L6 knob dictionary."""

    bundle = verify_intervention_substrate_bundle_content_hash(bundle)
    operator = str(operator_kind or "").strip()
    if not operator:
        raise InterventionSubstrateError("knob_operator_missing")
    if cycle_substrate_context is not None:
        from polisyos.runtime.quality.cycle_substrate import (
            revalidate_cycle_substrate_context,
        )

        context = revalidate_cycle_substrate_context(cycle_substrate_context)
        if (
            world_model_record is not None
            and world_model_record.content_hash
            != context.world_model_record_content_hash
        ):
            raise InterventionSubstrateError(
                "cycle_substrate_world_model_record_mismatch"
            )
        if (
            context.intervention_substrate is not None
            and context.intervention_substrate.content_hash != bundle.content_hash
        ):
            raise InterventionSubstrateError(
                "cycle_substrate_l6_bundle_content_mismatch"
            )
        if context.candidate_levers:
            if context.intervention_substrate is None:
                raise InterventionSubstrateError(
                    "cycle_substrate_l6_bundle_missing"
                )
            matches = tuple(
                candidate
                for candidate in context.candidate_levers
                if operator in {candidate.instrument, candidate.lever_id}
            )
            if not matches:
                raise InterventionSubstrateError(
                    "cycle_substrate_candidate_lever_unresolved",
                    operator,
                )
            if len(matches) != 1:
                raise InterventionSubstrateError(
                    "cycle_substrate_candidate_lever_ambiguous",
                    operator,
                )
            candidate = matches[0]
            if {
                operator,
                candidate.instrument,
                candidate.lever_id,
            }.intersection(bundle.knob_dictionary):
                raise InterventionSubstrateError(
                    "cycle_substrate_candidate_binding_contradiction",
                    operator,
                )
            fields = {
                "schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
                "status": "candidate_unbound",
                "operator_kind": operator,
                "instrument": candidate.instrument,
                "lever_id": candidate.lever_id,
                "reason_code": "knob_operator_unresolved",
                "candidate_entry_content_hash": candidate.entry_content_hash,
                "selected_registry_entry_hash": (
                    candidate.selected_registry_entry_hash
                ),
                "substrate_input_content_hash": (
                    candidate.substrate_input_content_hash
                ),
                "context_binding_hash": context.context_binding_hash,
                "substrate_registry_content_hash": (
                    context.substrate_registry_content_hash
                ),
                "world_model_record_content_hash": (
                    context.world_model_record_content_hash
                ),
                "source_refs": candidate.source_refs,
            }
            return InterventionLeverRefusal(
                **fields,
                content_hash=gy_content_hash(fields),
            )
    raw_knob = _mapping_or_none(bundle.knob_dictionary.get(operator))
    if raw_knob is None:
        raise InterventionSubstrateError("knob_operator_unresolved", operator)
    domain = _knob_domain(raw_knob)
    bound_value = _validate_value_in_domain(
        operator_kind=operator,
        value=parameter_value,
        domain=domain,
        raw_knob=raw_knob,
    )
    atom, world_binding = _resolve_owner_atom_world_binding(
        bundle=bundle,
        operator_kind=operator,
        raw_knob=raw_knob,
        parameter_value=bound_value,
        world_model_record=world_model_record,
    )
    target_slots = tuple(binding.slot_id for binding in world_binding.target_slot_bindings)
    fields = {
        "schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "operator_kind": operator,
        "parameter_value": bound_value,
        "domain": domain.model_dump(mode="json"),
        "target_world_slots": tuple(target_slots),
        "owner_resolution": {
            "atom_id": atom.atom_id,
            "atom_content_hash": atom.content_hash,
            "world_model_record_id": world_binding.world_model_record_id,
            "world_model_record_content_hash": world_binding.world_model_record_content_hash,
            "target_slot_bindings": [
                binding.model_dump(mode="json")
                for binding in world_binding.target_slot_bindings
            ],
        },
        "source_ref": bundle.source_refs.get(
            "intervention_knob_dictionary",
            "in_memory://intervention_knob_dictionary",
        ),
    }
    return InterventionLeverResolution(
        **fields,
        content_hash=gy_content_hash(fields),
    )


def resolve_law_bound_lever(
    bundle: InterventionSubstrateBundle,
    *,
    law_token: str,
    knob_id: str,
    parameter_value: object,
    legal_store: _LegalKnowledgeStoreProtocol,
    world_model_record: WorldModelRecord | None = None,
) -> LawLeverResolution:
    """Resolve a legal modality to a knob and evaluate L3 admissibility."""

    bundle = verify_intervention_substrate_bundle_content_hash(bundle)
    token = str(law_token or "").strip()
    knob = str(knob_id or "").strip()
    mapped_knobs = _lex_map_knobs(bundle.lex_intervention_map, token)
    if knob not in mapped_knobs:
        raise InterventionSubstrateError(
            "lex_map_knob_not_bound",
            f"{token} does not bind {knob}",
        )
    if _mapping_or_none(bundle.knob_dictionary.get(knob)) is None:
        raise InterventionSubstrateError("lex_map_knob_unresolved", knob)
    authority = _law_authority(bundle, token, knob)
    lever = resolve_intervention_lever(
        bundle,
        operator_kind=knob,
        parameter_value=parameter_value,
        world_model_record=world_model_record,
    )
    if not authority.as_of:
        raise InterventionSubstrateError("law_authority_as_of_missing", token)
    threshold = legal_store.resolve_rule_threshold(
        threshold_id=authority.threshold_id,
        metric=authority.metric,
        applies_to=authority.applies_to,
        as_of=authority.as_of,
        jurisdiction=authority.jurisdiction,
        domain=authority.domain,
        doc_family_id=authority.doc_family_id,
    )
    if threshold is None:
        raise InterventionSubstrateError("law_threshold_unresolved", token)
    if not threshold.provision_ref:
        raise InterventionSubstrateError("law_provision_unresolved", threshold.threshold_id)
    if authority.provision_ref and authority.provision_ref != threshold.provision_ref:
        raise InterventionSubstrateError(
            "law_provision_content_mismatch",
            f"{authority.provision_ref} != {threshold.provision_ref}",
        )
    candidate_unit = authority.candidate_unit or lever.domain.unit
    if not candidate_unit:
        raise InterventionSubstrateError("law_candidate_unit_missing", token)
    applies_to = authority.applies_to or threshold.applies_to
    if not applies_to:
        raise InterventionSubstrateError("law_threshold_scope_missing", token)
    evaluation = legal_store.evaluate_rule_threshold(
        threshold_id=threshold.threshold_id,
        candidate_value=float(lever.parameter_value),
        candidate_unit=candidate_unit,
        applies_to=applies_to,
        as_of=authority.as_of,
        jurisdiction=authority.jurisdiction,
        domain=authority.domain,
        doc_family_id=authority.doc_family_id,
    )
    temporal = legal_store.resolve_threshold_temporal_competence(
        threshold_id=threshold.threshold_id,
        as_of=authority.as_of,
    )
    fields = {
        "schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "law_token": token,
        "status": "blocked",
        "knob": lever.model_dump(mode="json"),
        "threshold_id": threshold.threshold_id,
        "provision_ref": threshold.provision_ref,
        "legal_threshold_evaluation": evaluation.model_dump(mode="json"),
        "temporal_competence": temporal.model_dump(mode="json"),
        "mapping_predicate_provenance": "consumer_asserted",
        "mapping_evidence_ref": None,
        "current_authority_status": "blocked",
        "mapping_reason_code": "law_mapping_correspondence_not_established",
    }
    return LawLeverResolution(**fields, content_hash=gy_content_hash(fields))


def route_observation_family_method(
    bundle: InterventionSubstrateBundle,
    *,
    family: str,
    registry: _MethodRegistryProtocol | None = None,
) -> ObservationMethodRoute:
    """Route an observation family to an available Foundry method."""

    bundle = verify_intervention_substrate_bundle_content_hash(bundle)
    family_id = str(family or "").strip()
    route = _manifest_route(bundle.observation_manifest, family_id)
    contract_id, contract_fqn = _route_contract(route)
    _assert_compiled_contract(bundle.observation_manifest, contract_id)
    resolved_registry = registry
    if resolved_registry is None:
        registry_module = importlib.import_module(
            "polisyos.foundry.extensions.registry"
        )

        with registry_module.controlled_builtin_foundry_method_registry_scope() as (
            controlled_registry,
            _registry_report,
        ):
            return route_observation_family_method(
                bundle,
                family=family_id,
                registry=controlled_registry,
            )
    registry_methods = list(resolved_registry.list_all())
    candidates = _registered_methods_for_contract(
        resolved_registry,
        contract_id,
        contract_fqn=contract_fqn,
    )
    available: list[str] = []
    unavailable: list[str] = []
    for signature in candidates:
        entry = resolved_registry.get_entry(signature.fqn)
        missing_deps = _missing_method_dependencies(entry)
        if missing_deps:
            unavailable.append(signature.fqn)
        else:
            available.append(signature.fqn)
    status = RouteStatus.ROUTED if available else RouteStatus.BLOCKED
    selected = sorted(available)[0] if available else None
    if selected:
        reason_code = None
    elif candidates:
        reason_code = "method_unavailable_python314"
    else:
        reason_code = "method_route_unresolved"
    route_fields = {
        "schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "family": family_id,
        "status": status,
        "target_contract_id": contract_id,
        "target_contract_fqn": contract_fqn,
        "selected_method_fqn": selected,
        "reason_code": reason_code,
        "registry_method_count": len(registry_methods),
        "candidate_method_fqns": tuple(sorted(signature.fqn for signature in candidates)),
        "unavailable_method_fqns": tuple(sorted(unavailable)),
        "manifest_route_hash": gy_content_hash(route),
    }
    return ObservationMethodRoute(
        **route_fields,
        content_hash=gy_content_hash(route_fields),
    )


def resolve_observation_manifest_routes(
    bundle: InterventionSubstrateBundle,
) -> tuple[ObservationMethodRoute, ...]:
    """Validate the full manifest and resolve every family through its existing owner."""
    bundle = verify_intervention_substrate_bundle_content_hash(bundle)
    raw_routes = bundle.observation_manifest.get("routes")
    if not isinstance(raw_routes, list) or not raw_routes:
        raise InterventionSubstrateError("observation_manifest_invalid")
    families: list[str] = []
    for row in raw_routes:
        if not isinstance(row, Mapping) or not isinstance(row.get("family"), str):
            raise InterventionSubstrateError("observation_manifest_invalid")
        family = row["family"].strip()
        if not family:
            raise InterventionSubstrateError("observation_family_missing")
        families.append(family)
    if len(set(families)) != len(families):
        raise InterventionSubstrateError("family_route_ambiguous")
    registry_module = importlib.import_module("polisyos.foundry.extensions.registry")
    with registry_module.controlled_builtin_foundry_method_registry_scope() as (registry, _report):
        return tuple(
            route_observation_family_method(bundle, family=family, registry=registry)
            for family in sorted(families)
        )


def project_value_method_route_constraint(
    bundle: InterventionSubstrateBundle,
    *,
    family: str | None = None,
    family_candidates: Sequence[str] = (),
) -> MethodRouteConstraint:
    """Project one unambiguous owner route as a Foundry candidate constraint.

    All manifest rows are validated before selecting the requested family. An
    unresolvable source is never converted to an unconstrained advisor query.
    """
    from polisyos.foundry import MethodRouteConstraint

    routes = resolve_observation_manifest_routes(bundle)
    invalid = [
        row
        for row in routes
        if row.status == RouteStatus.BLOCKED and row.reason_code != "method_unavailable_python314"
    ]
    if invalid:
        raise InterventionSubstrateError(invalid[0].reason_code or "method_route_unresolved")
    by_family = {row.family: row for row in routes}
    if family is None:
        matches = set(family_candidates).intersection(by_family)
        if len(matches) != 1:
            raise InterventionSubstrateError(
                "observation_family_ambiguous" if matches else "observation_family_missing"
            )
        family = next(iter(matches))
    if family not in by_family:
        raise InterventionSubstrateError("family_route_unresolved", family)
    route = by_family[family]
    if route.status != RouteStatus.ROUTED:
        raise InterventionSubstrateError(route.reason_code or "method_route_unresolved", family)
    return MethodRouteConstraint(
        family=family,
        target_contract_id=route.target_contract_id,
        allowed_method_fqns=tuple(
            fqn for fqn in route.candidate_method_fqns if fqn not in route.unavailable_method_fqns
        ),
        manifest_content_hash=gy_content_hash(bundle.observation_manifest),
        route_content_hashes=tuple(row.content_hash for row in routes),
    )


def intervention_substrate_behavior_report(repo_root: Path) -> dict[str, Any]:
    """Exercise the L6 intervention substrate over real data and mutation witnesses."""

    registry_module = importlib.import_module("polisyos.foundry.extensions.registry")
    from polisyos.runtime.quality.substrate_registry import (
        SubstrateLayer,
        build_substrate_registry_from_existing_catalogs,
    )

    repo_root = repo_root.resolve()
    bundle = load_l6_intervention_substrate(repo_root)
    world_record = _production_composed_world_model_record(repo_root.as_posix())
    lex_module = importlib.import_module("polisyos.lex.knowledge.store")
    lex_store = lex_module.LegalKnowledgeStore(
        repo_root / DEFAULT_L3_LEX_DB_PATH,
        (repo_root / DEFAULT_L3_LEX_DB_PATH).parent,
        canonical_db_ref_path=DEFAULT_L3_LEX_DB_PATH,
    )
    threshold = lex_store.resolve_rule_threshold(
        threshold_id=_REPRESENTATIVE_L3_THRESHOLD_ID,
        as_of=_REPRESENTATIVE_L3_AS_OF,
    )
    if threshold is None:
        raise InterventionSubstrateError(
            "representative_l3_threshold_unresolved",
            _REPRESENTATIVE_L3_THRESHOLD_ID,
        )
    free_grow_threshold = lex_store.resolve_rule_threshold(
        threshold_id=_FREE_GROW_L3_THRESHOLD_ID,
        as_of=_FREE_GROW_L3_AS_OF,
    )
    if free_grow_threshold is None:
        raise InterventionSubstrateError(
            "free_grow_l3_threshold_unresolved",
            _FREE_GROW_L3_THRESHOLD_ID,
        )

    cases: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    coverage = _coverage_report(
        bundle=bundle,
        lex_store=lex_store,
        world_model_record=world_record,
    )

    def record(
        *,
        case_id: str,
        passed: bool,
        expected: str,
        actual: str,
        detail: Mapping[str, Any],
    ) -> None:
        case = {
            "case_id": case_id,
            "expected": expected,
            "actual": actual,
            "detail": _json_ready(detail),
        }
        cases.append(case)
        if not passed:
            issues.append({"code": "intervention_substrate_behavior_failed", **case})

    world_coverage = coverage["world_slot"]
    record(
        case_id="all_real_knobs_resolve_world_slots",
        passed=(world_coverage["total"] > 0 and world_coverage["bound"] == world_coverage["total"]),
        expected="all_real_knobs_bind_through_n2_n3_owner",
        actual=f"{world_coverage['bound']}/{world_coverage['total']}",
        detail=world_coverage,
    )

    lever = resolve_intervention_lever(
        bundle,
        operator_kind="budget_allocation_multiplier",
        parameter_value=1.25,
        world_model_record=world_record,
    )
    record(
        case_id="knob_in_domain_resolves_world_slot",
        passed=(
            lever.domain.min_value == 0.0
            and lever.domain.max_value == 2.0
            and lever.target_world_slots == ("government.balance",)
        ),
        expected="real_knob_domain_and_manifest_slot_bound",
        actual=(
            "real_knob_domain_and_manifest_slot_bound"
            if lever.target_world_slots == ("government.balance",)
            else "domain_or_slot_not_bound"
        ),
        detail=lever.model_dump(mode="json"),
    )

    out_code = _error_code(
        lambda: resolve_intervention_lever(
            bundle,
            operator_kind="budget_allocation_multiplier",
            parameter_value=2.25,
            world_model_record=world_record,
        )
    )
    unknown_code = _error_code(
        lambda: resolve_intervention_lever(
            bundle,
            operator_kind="unknown_budget_knob",
            parameter_value=1.0,
            world_model_record=world_record,
        )
    )
    record(
        case_id="knob_out_of_domain_and_unknown_operator_fail_closed",
        passed=(
            out_code == "knob_parameter_out_of_domain"
            and unknown_code == "knob_operator_unresolved"
        ),
        expected="out_of_domain_and_unknown_operator_rejected",
        actual=f"{out_code}|{unknown_code}",
        detail={"out_of_domain_code": out_code, "unknown_code": unknown_code},
    )

    law_coverage = coverage["law_trace"]
    record(
        case_id="all_real_laws_trace_l3_thresholds",
        passed=(law_coverage["total"] > 0 and law_coverage["traced"] == law_coverage["total"]),
        expected="all_real_law_routes_trace_real_l3_provisions_and_knobs",
        actual=f"{law_coverage['traced']}/{law_coverage['total']}",
        detail=law_coverage,
    )

    admitted = resolve_law_bound_lever(
        bundle,
        law_token=_BUDGET_LAW,
        knob_id="budget_allocation_multiplier",
        parameter_value=0.24,
        legal_store=lex_store,
        world_model_record=world_record,
    )
    blocked = resolve_law_bound_lever(
        bundle,
        law_token=_BUDGET_LAW,
        knob_id="budget_allocation_multiplier",
        parameter_value=0.26,
        legal_store=lex_store,
        world_model_record=world_record,
    )
    record(
        case_id="law_bound_lever_traces_l3_threshold_and_blocks_violation",
        passed=(
            admitted.status == "blocked"
            and admitted.legal_threshold_evaluation.get("status") == "admitted"
            and admitted.mapping_evidence_ref is None
            and admitted.provision_ref == threshold.provision_ref
            and blocked.status == "blocked"
            and blocked.legal_threshold_evaluation.get("reason") == "threshold_violated"
        ),
        expected="real_threshold_admit_and_block_with_unverified_correspondence_ceiling",
        actual=f"{admitted.status}|{blocked.legal_threshold_evaluation.get('reason')}",
        detail={
            "admitted": admitted.model_dump(mode="json"),
            "blocked": blocked.model_dump(mode="json"),
        },
    )
    transposed_manifest = copy.deepcopy(bundle.lex_authority_manifest)
    law_entries = {row["law_token"]: row
                   for row in transposed_manifest["intervention_map_entries"]}
    budget_entry, tax_entry = law_entries[_BUDGET_LAW], law_entries["tax_relief_statute"]
    budget_entry["provision_ref"], tax_entry["provision_ref"] = (
        tax_entry["provision_ref"], budget_entry["provision_ref"])
    transposed = resolve_law_bound_lever(
        replace_intervention_substrate_bundle(
            bundle, update={"lex_authority_manifest": transposed_manifest},
        ), law_token=tax_entry["law_token"], knob_id="tax_relief_rate", parameter_value=0.24,
        legal_store=lex_store, world_model_record=world_record,
    )
    record(
        case_id="real_unrelated_law_target_cannot_authorize",
        passed=(transposed.status == "blocked" and transposed.mapping_evidence_ref is None
                and transposed.mapping_predicate_provenance == "consumer_asserted"
                and transposed.legal_threshold_evaluation["status"] == "admitted"),
        expected="numeric_success_cannot_authorize_transposed_real_law_correspondence",
        actual=transposed.status, detail=transposed.model_dump(mode="json"),
    )

    dangling_bundle = replace_intervention_substrate_bundle(
        bundle,
        update={
            "lex_intervention_map": {
                **bundle.lex_intervention_map,
                _DANGLING_LAW: ("not_a_real_knob",),
            }
        },
    )
    dangling_code = _error_code(
        lambda: resolve_law_bound_lever(
            dangling_bundle,
            law_token=_DANGLING_LAW,
            knob_id="not_a_real_knob",
            parameter_value=0.1,
            legal_store=lex_store,
            world_model_record=world_record,
        )
    )
    unknown_law_code = _error_code(
        lambda: resolve_law_bound_lever(
            bundle,
            law_token=_UNKNOWN_LAW_MODALITY,
            knob_id="budget_allocation_multiplier",
            parameter_value=0.1,
            legal_store=lex_store,
            world_model_record=world_record,
        )
    )
    record(
        case_id="dangling_law_map_fails_closed",
        passed=(
            dangling_code == "lex_map_knob_unresolved"
            and unknown_law_code == "law_modality_unresolved"
        ),
        expected="dangling_knob_and_unknown_law_rejected",
        actual=f"{dangling_code}|{unknown_law_code}",
        detail={
            "dangling_code": dangling_code,
            "unknown_law_code": unknown_law_code,
        },
    )

    with registry_module.controlled_builtin_foundry_method_registry_scope() as (
        registry,
        _registry_report,
    ):
        method_coverage = coverage["method_route"]
        record(
            case_id="family_method_route_real_available_and_truthful_blockers",
            passed=(
                method_coverage["total"] > 0
                and method_coverage["available"] > 0
                and method_coverage["unresolved"] == 0
                and (
                    method_coverage["available"] + method_coverage["unavailable_python314"]
                    == method_coverage["total"]
                )
            ),
            expected="all_manifest_families_resolve_to_registered_method_or_truthful_python314_blocker",
            actual=(
                f"available={method_coverage['available']}/"
                f"{method_coverage['total']};"
                f"unavailable={method_coverage['unavailable_python314']};"
                f"unresolved={method_coverage['unresolved']}"
            ),
            detail=method_coverage,
        )
        unavailable_route = route_observation_family_method(
            _unavailable_route_bundle(bundle),
            family="python314_unavailable_route_family",
            registry=registry,
        )
        record(
            case_id="nonexistent_contract_cannot_borrow_bart_metadata",
            passed=(
                unavailable_route.status == RouteStatus.BLOCKED
                and unavailable_route.reason_code == "method_route_unresolved"
                and not unavailable_route.candidate_method_fqns
            ),
            expected="nonexistent_bart_input_type_is_unresolved_despite_matching_tokens",
            actual=f"{unavailable_route.status}|{unavailable_route.reason_code}",
            detail=unavailable_route.model_dump(mode="json"),
        )
        from unittest.mock import patch

        with patch(__name__ + "._missing_method_dependencies", return_value=("absent_probe_dep",)):
            dependency_removed = route_observation_family_method(
                bundle, family="budget_flows", registry=registry,
            )
        record(
            case_id="family_method_route_python314_unavailable_truthful_blocker",
            passed=(dependency_removed.status == RouteStatus.BLOCKED
                    and dependency_removed.reason_code == "method_unavailable_python314"
                    and bool(dependency_removed.candidate_method_fqns)
                    and not dependency_removed.selected_method_fqn),
            expected="dependency_removal_control_blocks_a_real_input_contract",
            actual=str(dependency_removed.reason_code),
            detail={"control": "dependency availability removed in memory; not a station census",
                    "route": dependency_removed.model_dump(mode="json")},
        )
        grown = _free_grow_bundle(
            bundle,
            threshold=free_grow_threshold,
            as_of=_FREE_GROW_L3_AS_OF,
        )
        grown_lever = resolve_intervention_lever(
            grown,
            operator_kind=_FREE_GROW_KNOB,
            parameter_value=0.2,
            world_model_record=world_record,
        )
        grown_law = resolve_law_bound_lever(
            grown,
            law_token=_FUTURE_RELIEF_LAW,
            knob_id=_FREE_GROW_KNOB,
            parameter_value=0.2,
            legal_store=lex_store,
            world_model_record=world_record,
        )
        grown_route = route_observation_family_method(
            grown,
            family="future_budget_flows",
            registry=registry,
        )
        record(
            case_id="free_grow_knob_law_family_routes",
            passed=(
                grown_lever.target_world_slots == (_FREE_GROW_SLOT,)
                and grown_law.status == "blocked"
                and grown_law.mapping_evidence_ref is None
                and grown_route.status == RouteStatus.ROUTED
            ),
            expected="new_candidate_entries_route_without_code_change_with_law_authority_blocked",
            actual=f"{grown_lever.target_world_slots}|{grown_law.status}|{grown_route.status}",
            detail={
                "lever": grown_lever.model_dump(mode="json"),
                "law": grown_law.model_dump(mode="json"),
                "route": grown_route.model_dump(mode="json"),
            },
        )
        mutations = _remove_property_mutation_report(
            bundle=bundle,
            dangling_bundle=dangling_bundle,
            registry=registry,
            lex_store=lex_store,
            world_model_record=world_record,
        )

    unknown_family_code = _error_code(
        lambda: route_observation_family_method(bundle, family="unknown_family")
    )
    record(
        case_id="unknown_family_fails_closed",
        passed=unknown_family_code == "family_route_unresolved",
        expected="unknown_family_rejected_not_defaulted",
        actual=unknown_family_code,
        detail={"unknown_family_code": unknown_family_code},
    )

    registry = build_substrate_registry_from_existing_catalogs(repo_root)
    l6_entries = registry.resolve(layer=SubstrateLayer.L6)
    l6_agent_sim = [
        entry for entry in l6_entries if entry.source_id == "production_data:ukraine_simulation"
    ]
    record(
        case_id="s0_registers_l6_agent_sim_bundle",
        passed=bool(l6_agent_sim)
        and bool(bundle.policy_scenario_templates)
        and "policy_scenario_templates" in bundle.source_refs,
        expected="l6_agent_sim_registered_in_s0_and_scenario_templates_registered",
        actual="registered" if l6_agent_sim else "missing",
        detail={
            "l6_entries": [entry.model_dump(mode="json") for entry in l6_agent_sim],
            "scenario_templates_ref": bundle.source_refs.get("policy_scenario_templates"),
        },
    )

    consumers = _manifest_consumer_behavior_report(bundle, world_record)
    if consumers["status"] != "pass":
        issues.append({"code": "manifest_consumer_behavior_failed", "detail": consumers})
    law_consumers = _law_credal_consumer_behavior_report(repo_root, bundle, world_record)
    if law_consumers["status"] != "pass":
        issues.append({"code": "law_credal_consumer_behavior_failed", "detail": law_consumers})
    strangles = _intervention_substrate_strangle_receipts(
        repo_root, consumers=consumers, law_resolution=admitted, law_consumers=law_consumers,
    )
    if any(receipt["status"] != "strangled" for receipt in strangles):
        issues.append({"code": "intervention_substrate_default_not_strangled"})
    mutation_green = [mutation for mutation in mutations if mutation["status"] != "red"]
    if mutation_green:
        issues.append(
            {
                "code": "intervention_substrate_remove_property_mutation_not_red",
                "mutations": mutation_green,
            }
        )
    return {
        "schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "status": "pass" if not issues else "fail",
        "case_count": len(cases),
        "cases": cases,
        "issues": issues,
        "remove_property_mutations": mutations,
        "coverage": coverage,
        "manifest_consumers": consumers,
        "law_credal_consumers": law_consumers,
        "strangle_receipts": strangles,
        "authority_limitations": [
            {
                "conjunct": "law_to_knob_correspondence_and_authorized_law_free_growth",
                "status": "not_established",
                "capability": "verification_missing",
                "reason": "No independent correspondence source/verifier in the admitted chain.",
            }
        ],
        "source_content_hashes": dict(bundle.source_content_hashes),
        "bundle_content_hash": bundle.content_hash,
    }


def _law_credal_consumer_behavior_report(
    repo_root: Path, bundle: InterventionSubstrateBundle, world_record: WorldModelRecord,
) -> dict[str, Any]:
    """Recompute the scoped L6/WMR handoff without issuing a full K_ref or certificate."""
    from dataclasses import replace

    from polisyos.runtime.quality import credal_reference, grounding_relation

    edges = [*credal_reference._iter_l6_edges(repo_root, world_model_record=world_record),
             *credal_reference._iter_wmr_edges(world_record)]
    laws = [edge for edge in edges if edge.modality == "L6_LEX_INTERVENTION_MAP"]
    source_ids = sorted(bundle.lex_intervention_map)
    raw_ids = sorted(_read_json_object(default_l6_bundle_paths(repo_root)["lex_intervention_map"]))
    actual_ids = sorted(edge.edge_id for edge in laws)

    def project(rows: Sequence[Any]) -> tuple[Any, tuple[Any, ...]]:
        index = {edge.key: edge for edge in rows}
        versions = credal_reference._component_versions(index, world_model_record=world_record)
        digest = credal_reference._reference_hash(component_versions=versions, edge_index=index,
                                                 as_of=credal_reference.DEFAULT_REFERENCE_AS_OF)
        reference = credal_reference.CredalReference(
            credal_reference.CREDAL_REFERENCE_SCHEMA_VERSION,
            "kref:" + digest.removeprefix("sha256:")[:16], digest,
            credal_reference.DEFAULT_REFERENCE_AS_OF, versions, index,
        )
        return reference, grounding_relation._reference_atoms_from_cg0(reference)

    reference, atoms = project(edges)
    expected = []
    for operator, raw_knob in sorted(bundle.knob_dictionary.items()):
        knob = resolve_intervention_lever(bundle, operator_kind=operator,
            parameter_value=_representative_knob_value(raw_knob, knob_id=operator),
            world_model_record=world_record)
        for slot in world_record.policy_slot_map:
            if grounding_relation._operator_target_compatible(
                reference, op_id=operator, domain=knob.domain.model_dump(mode="json"),
                target_slot=slot.slot_id, explicit_slots=knob.target_world_slots,
            ):
                expected.append((operator, (slot.slot_id,)))
    actual = sorted((atom.signature.op, atom.signature.X_do) for atom in atoms)

    def valid(rows: Sequence[Any], projected_atoms: Sequence[Any]) -> bool:
        law_keys = {credal_reference._edge_key_text(edge.key) for edge in rows
                    if edge.modality == "L6_LEX_INTERVENTION_MAP"}
        return all(edge.status == "incomplete" for edge in rows
                   if edge.modality == "L6_LEX_INTERVENTION_MAP") and all(
            atom.signature.admissibility == "reference_contested"
            and bool(law_keys.intersection(atom.edge_scope))
            for atom in projected_atoms)

    confirmed_removed = [replace(edge, status="confirmed").with_content_hash()
                         if edge in laws else edge for edge in edges]
    association_removed = [replace(edge, admissible_completions=
        credal_reference._incomplete_completions("law_mapping_correspondence_not_established")
    ).with_content_hash() if edge in laws else edge for edge in edges]
    _ref, confirmed_atoms = project(confirmed_removed)
    _ref, dropped_atoms = project(association_removed)
    status_red = not valid(confirmed_removed, confirmed_atoms)
    association_red = not valid(association_removed, dropped_atoms)
    passed = (source_ids == raw_ids == actual_ids and actual == sorted(expected)
              and bool(atoms) and valid(edges, atoms) and status_red and association_red)
    return {"status": "pass" if passed else "fail",
        "scope": "Actual L6 and WMR owner outputs only; not a complete K_ref or certificate",
        "source_law_identities": source_ids, "raw_law_identities": raw_ids,
        "consumer_law_identities": actual_ids,
        "semantic_atom_identities": actual, "independent_knob_x_wmr_identities": sorted(expected),
        "laws": [edge.to_payload() for edge in laws],
        "atoms": [{"operator": atom.signature.op, "targets": atom.signature.X_do,
                   "admissibility": atom.signature.admissibility, "edge_scope": atom.edge_scope}
                  for atom in atoms],
        "remove_status_keep_markers_goes_red": status_red,
        "remove_association_keep_incomplete_goes_red": association_red}


def _manifest_consumer_behavior_report(
    bundle: InterventionSubstrateBundle,
    world_record: WorldModelRecord,
) -> dict[str, Any]:
    """Run the real candidate consumers; these probes never create a governed design."""
    from unittest.mock import patch

    from polisyos.runtime.quality import design_generation, generation_cycle

    raw_rows = bundle.observation_manifest["routes"]
    source_ids = sorted(row["family"] for row in raw_rows)
    routes = resolve_observation_manifest_routes(bundle)
    owner_ids = sorted(route.family for route in routes)
    results: list[dict[str, Any]] = []

    def select(manifest: object, family: str, **inputs: object) -> dict[str, Any]:
        return generation_cycle._select_value_method(
            candidate={"candidate_id": family},
            problem={},
            inputs={
                "observation_to_contract_manifest": manifest,
                "observation_family": family,
                **inputs,
            },
        )

    for route in routes:
        positive = select(bundle.observation_manifest, route.family)
        broken = copy.deepcopy(bundle.observation_manifest)
        for row in broken["routes"]:
            if row["family"] == route.family:
                row["target_contract"] = {"contract_id": "gy.invalid.contract"}
        negative = select(
            broken,
            route.family,
            owner_validated=True,
            route_constraint={
                "manifest_content_hash": gy_content_hash(bundle.observation_manifest)
            },
        )
        explicit = select(
            bundle.observation_manifest, route.family, method_fqn="bayesian.gp.gp_regression@1.0.0"
        )
        positive_valid = (
            positive.get("selected_method_fqn") in route.candidate_method_fqns
            if positive["status"] == "selected"
            else positive.get("blockers") == ("value_method_route_no_native_value_output",)
        )
        results.append(
            {
                "family": route.family,
                "owner": route.model_dump(mode="json"),
                "positive": _json_ready(positive),
                "fake_source": _json_ready(negative),
                "outside_request": _json_ready(explicit),
                "passed": positive_valid
                and negative["status"] == "blocked"
                and explicit["status"] == "blocked",
            }
        )

    eligible = [row for row in results if row["positive"]["status"] == "selected"]
    if not eligible:
        return {"status": "fail", "reason": "real_native_value_route_missing", "routes": results}
    exemplar = eligible[0]["family"]
    from polisyos.runtime.quality.cycle_substrate import build_cycle_substrate_context
    from polisyos.runtime.quality.substrate_registry import (
        build_substrate_registry_from_existing_catalogs,
    )

    registry = build_substrate_registry_from_existing_catalogs(_repo_root_for_bundle(bundle))
    context = build_cycle_substrate_context(
        design_problem_ref=gy_content_hash({"candidate_route_probe": bundle.content_hash}),
        domain="candidate_route_probe", substrate_registry=registry,
        selected_registry_entry_hashes=tuple(
            entry.entry_content_hash
            for entry in world_record.substrate_registry_ref.resolved_entries
        ),
        world_model_record=world_record, intervention_substrate=bundle,
        candidate_levers=(), transport_context=None,
        source_pack_content_hash=None, substrate_input_content_hash=None,
    )
    configured_default = generation_cycle._DefaultSimulationBoundFoundryValuePort(
        repo_root=_repo_root_for_bundle(bundle), cycle_substrate_context=context,
        observation_family=exemplar,
    )

    def configured_selection() -> dict[str, Any]:
        inputs = generation_cycle._value_method_selection_inputs(
            **configured_default._selection_configuration(),
        )
        return generation_cycle._select_value_method(candidate={}, problem={}, inputs=inputs)

    configured_positive = configured_selection()
    actual_configuration_inputs = generation_cycle._value_method_selection_inputs(
        **configured_default._selection_configuration(),
    )
    original_configuration = generation_cycle._value_method_selection_inputs

    def remove_family_configuration(**kwargs: object) -> dict[str, Any]:
        inputs = original_configuration(**kwargs)
        inputs.pop("observation_family", None)
        return inputs

    def remove_source_configuration(**kwargs: object) -> dict[str, Any]:
        inputs = original_configuration(**kwargs)
        inputs.pop("observation_to_contract_manifest", None)
        return inputs

    with patch.object(
        generation_cycle, "_value_method_selection_inputs", remove_family_configuration,
    ):
        configured_family_removed = configured_selection()
    with patch.object(
        generation_cycle, "_value_method_selection_inputs", remove_source_configuration,
    ):
        configured_source_removed = configured_selection()
    configured_owner_methods = set(
        next(route for route in routes if route.family == exemplar).candidate_method_fqns,
    )
    configured_valid = (configured_positive["status"] == "selected"
                        and configured_positive["selected_method_fqn"] in configured_owner_methods)
    configured_family_red = configured_family_removed["status"] != "selected"
    configured_source_red = (
        configured_source_removed.get("selected_method_fqn") not in configured_owner_methods
    )
    source_without_routes = copy.deepcopy(bundle.observation_manifest)
    del source_without_routes["routes"]
    malformed_controls = {
        "routes_deleted_declarations_retained": source_without_routes,
        "explicit_null": None,
        "empty_object": {},
        "empty_array": [],
        "scalar": "not a source manifest",
        "legacy_advisory_shape_in_source_slot": {"contracts": [{"data_modality": "panel"}]},
    }
    shape_results = {}
    for name, malformed in malformed_controls.items():
        selection = select(malformed, exemplar)
        try:
            generation_cycle._value_method_route_constraint(
                candidate={}, problem={}, inputs={
                    "observation_to_contract_manifest": malformed,
                    "observation_family": exemplar,
                },
            )
        except ValueError as exc:
            replay = {"status": "blocked", "reason": str(exc)}
        else:
            replay = {"status": "accepted"}
        shape_results[name] = {"selection": _json_ready(selection), "context_intake": replay}
    original_intake = generation_cycle._value_method_route_constraint

    def removed_presence_intake(
        *, candidate: object, problem: object, inputs: Mapping[str, Any],
    ) -> MethodRouteConstraint | None:
        raw = inputs.get("observation_to_contract_manifest")
        if not isinstance(raw, Mapping) or "routes" not in raw:
            return None
        return original_intake(candidate=candidate, problem=problem, inputs=inputs)

    with patch.object(generation_cycle, "_value_method_route_constraint", removed_presence_intake):
        missing_source_removed = select(source_without_routes, exemplar)
        source_shape_happy = select(bundle.observation_manifest, exemplar)
    grown = copy.deepcopy(bundle.observation_manifest)
    new_row = copy.deepcopy(next(row for row in raw_rows if row["family"] == exemplar))
    new_row["family"] = "gy_data_only_novel_family"
    grown["routes"].append(new_row)
    grown_result = select(grown, new_row["family"])
    duplicate = copy.deepcopy(grown)
    duplicate["routes"].append({**new_row, "mode": "different_mode"})
    ambiguous = select(duplicate, new_row["family"])
    missing_family = generation_cycle._select_value_method(
        candidate={},
        problem={},
        inputs={"observation_to_contract_manifest": grown},
    )
    invalid_compilation = copy.deepcopy(grown)
    exemplar_target = new_row["target_contract"]["contract_id"]
    for artifact in invalid_compilation["artifacts"]:
        if artifact["target_contract"]["contract_id"] == exemplar_target:
            artifact["target_contract"]["contract_id"] = "gy.different.contract"
    n8_invalid_compilation = select(invalid_compilation, new_row["family"])
    broken_all = copy.deepcopy(bundle.observation_manifest)
    for row in broken_all["routes"]:
        row["target_contract"] = {"contract_id": "gy.invalid.contract"}
    invalid_bundle = replace_intervention_substrate_bundle(
        bundle,
        update={"observation_manifest": broken_all},
    )
    atom, _binding = _resolve_owner_atom_world_binding(
        bundle=bundle,
        operator_kind="budget_allocation_multiplier",
        raw_knob=bundle.knob_dictionary["budget_allocation_multiplier"],
        parameter_value=1.25,
        world_model_record=world_record,
    )
    # A candidate input for the search-only consumer, not an assembled promotion candidate.
    candidate = SimpleNamespace(candidate_id="gy_s3_route_probe", atom=atom)
    problem = SimpleNamespace(
        outcome_of_interest=SimpleNamespace(
            target_variable="government.balance", metric_id="budget"
        ),
        problem_statement="Budget",
    )

    def rank() -> object:
        return design_generation.rank_shadow_candidates_with_graph_causal_surrogate(
            (candidate,),
            design_problem=problem,
            repo_root=_repo_root_for_bundle(bundle),
        )[0]

    with patch.object(design_generation, "load_l6_intervention_substrate", return_value=bundle):
        n4_valid = rank()
    with patch.object(
        design_generation, "load_l6_intervention_substrate", return_value=invalid_bundle
    ):
        n4_invalid = rank()
    # Remove actual source validation, retaining a valid declaration and all markers.
    # The same negative assertion must go red while the happy path remains valid.
    with patch(__name__ + "._assert_compiled_contract", return_value=None):
        n8_removed = select(invalid_compilation, new_row["family"])
        n8_happy = select(grown, new_row["family"])
    with (
        patch.object(
            design_generation, "load_l6_intervention_substrate", return_value=invalid_bundle
        ),
        patch.object(design_generation, "resolve_observation_manifest_routes", return_value=routes),
    ):
        n4_removed = rank()
    n4_families = sorted(
        ref.removeprefix("observation_family:")
        for ref in n4_valid.feature_refs
        if ref.startswith("observation_family:")
    )
    passed = (
        source_ids == owner_ids == n4_families
        and all(row["passed"] for row in results)
        and configured_valid and configured_family_red and configured_source_red
        and actual_configuration_inputs["observation_to_contract_manifest"]
        == bundle.observation_manifest
        and all(row["selection"]["status"] == "blocked"
                and row["context_intake"]["status"] == "blocked"
                for row in shape_results.values())
        and missing_source_removed["status"] == "selected"
        and source_shape_happy["status"] == "selected"
        and grown_result["status"] == "selected"
        and n8_invalid_compilation["status"] == "blocked"
        and ambiguous["status"] == "blocked"
        and missing_family["status"] == "blocked"
        and n4_valid.trust_level == "search_guiding"
        and not n4_valid.promotion_allowed
        and n4_invalid.trust_level == "proposal_only"
        and not n4_invalid.promotion_allowed
        and n8_removed["status"] == "selected"
        and n8_happy["status"] == "selected"
        and n4_removed.trust_level == "search_guiding"
        and not n4_removed.promotion_allowed
    )
    return {
        "status": "pass" if passed else "fail",
        "source_identity_set": source_ids,
        "owner_identity_set": owner_ids,
        "n4_identity_set": n4_families,
        "routes": results,
        "configured_default_bridge": {
            "scope": (
                "Actual candidate-only context producer over the real WMR/registry/bundle; "
                "no N5 execution or promotion receipt"
            ),
            "context_content_hash": context.content_hash,
            "source_bundle_content_hash": bundle.content_hash,
            "requested_family": configured_default.observation_family,
            "positive": _json_ready(configured_positive),
            "remove_family_forwarding_goes_red": configured_family_red,
            "remove_bound_source_forwarding_goes_red": configured_source_red,
        },
        "supplied_source_shape_controls": shape_results,
        "supplied_source_presence_removal": {
            "missing_routes_negative_goes_red": missing_source_removed["status"] == "selected",
            "happy_source_stays_valid": source_shape_happy["status"] == "selected",
        },
        "data_only_growth": _json_ready(grown_result),
        "invalid_compilation_keeps_native_target": _json_ready(n8_invalid_compilation),
        "ambiguous_family": _json_ready(ambiguous),
        "missing_family": _json_ready(missing_family),
        "n4_positive": n4_valid.model_dump(mode="json"),
        "n4_fake_source": n4_invalid.model_dump(mode="json"),
        "owner_validation_removal": {
            "n8_negative_goes_red": n8_removed["status"] == "selected",
            "n8_happy_stays_valid": n8_happy["status"] == "selected",
            "n4_negative_goes_red": n4_removed.trust_level == "search_guiding",
            "n8_actual": _json_ready(n8_removed),
            "n4_actual": n4_removed.model_dump(mode="json"),
        },
    }


def _intervention_substrate_strangle_receipts(
    repo_root: Path,
    *,
    consumers: Mapping[str, Any],
    law_resolution: LawLeverResolution,
    law_consumers: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Reconcile the complete Python call set and execute replaced default behavior."""
    paths = sorted(
        path.relative_to(repo_root).as_posix() for path in (repo_root / "src").rglob("*.py")
    )
    walked = sorted(
        (Path(root) / filename).relative_to(repo_root).as_posix()
        for root, _dirs, files in os.walk(repo_root / "src")
        for filename in files
        if filename.endswith(".py")
    )
    if paths != walked:
        raise InterventionSubstrateError("strangle_source_denominator_mismatch")
    names = {
        "_observation_manifest_families",
        "_select_value_method",
        "select_value_method_for_problem",
        "rank_shadow_candidates_with_graph_causal_surrogate",
        "resolve_law_bound_lever",
    }
    callers: dict[str, list[str]] = {name: [] for name in sorted(names)}
    for path in paths:
        tree = ast.parse((repo_root / path).read_text(encoding="utf-8"), filename=path)
        aliases = {
            alias.asname or alias.name: alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            name = aliases.get(name, name)
            if name in callers:
                callers[name].append(f"{path}:{node.lineno}")
    specs = (
        (
            "n8_raw_manifest_ignored",
            "_select_value_method",
            "manifest ignored as flat hints",
            "source-derived owner constraint",
            consumers["status"] == "pass",
        ),
        (
            "_observation_manifest_families",
            "rank_shadow_candidates_with_graph_causal_surrogate",
            "family names earn route bonus",
            "complete validated routes earn candidate bonus",
            consumers["status"] == "pass" and not callers["_observation_manifest_families"],
        ),
        (
            "threshold_pass_implies_law_admissible",
            "resolve_law_bound_lever",
            "numeric threshold admits law/knob mapping",
            "unverified correspondence blocks authority",
            law_consumers["status"] == "pass"
            and law_resolution.status == "blocked"
            and law_resolution.mapping_evidence_ref is None
            and law_resolution.legal_threshold_evaluation["status"] == "admitted",
        ),
    )
    receipts = []
    for predecessor, replacement, before, after, passed in specs:
        payload = {
            "schema_version": "policyos.runtime.intervention_substrate_strangle.v1",
            "predecessor_ref": predecessor,
            "replacement_ref": replacement,
            "default_before": before,
            "default_after": after,
            "disposition": "default_flipped",
            "status": "strangled" if passed else "drift",
            "remaining_callers": callers.get(predecessor, []),
            "replacement_callers": sorted(callers[replacement]),
            "source_file_denominator": {
                "file_type": "src/**/*.py",
                "identities": paths,
                "independent_identity_hash": gy_content_hash(walked),
            },
            "verified_by": "intervention_substrate_behavior_report",
            "behavior_content_hash": gy_content_hash(
                consumers
                if replacement != "resolve_law_bound_lever"
                else {"resolution": law_resolution.model_dump(mode="json"),
                      "handoff": law_consumers}
            ),
        }
        receipts.append({**payload, "content_hash": gy_content_hash(payload)})
    return receipts


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise InterventionSubstrateError("json_object_expected", path.as_posix())
    return dict(payload)


def _repo_root_for_bundle(bundle: InterventionSubstrateBundle) -> Path:
    refs = [
        str(ref).removeprefix("repo://")
        for ref in bundle.source_refs.values()
        if str(ref).startswith("repo://")
    ]
    required_refs = [ref for ref in refs if ref]
    if not required_refs:
        raise InterventionSubstrateError("repo_root_unresolved_for_composed_wmr")
    for candidate in (Path.cwd(), *Path.cwd().parents):
        root = candidate.resolve()
        if all((root / ref).exists() for ref in required_refs):
            return root
    raise InterventionSubstrateError(
        "repo_root_unresolved_for_composed_wmr",
        ", ".join(sorted(required_refs)),
    )


@lru_cache(maxsize=4)
def _production_composed_world_model_record(repo_root: str) -> WorldModelRecord:
    from polisyos.core.artifacts import FileSystemCAS
    from polisyos.runtime.quality.data_state_substrate import (
        build_production_data_state_world_model_record,
    )

    root = Path(repo_root).resolve()
    built = build_production_data_state_world_model_record(
        FileSystemCAS(root / ".tmp/gy-s-composed-wmr-cas"),
        repo_root=root,
        workspace_dir=root / ".tmp/gy-s-composed-wmr-world",
        agent_limit=_COMPOSED_WMR_AGENT_LIMIT,
        required_substrate_families=_COMPOSED_WMR_REQUIRED_SUBSTRATE_FAMILIES,
    )
    return built.world_model.record


def production_composed_world_model_record(repo_root: str | Path) -> WorldModelRecord:
    """Return the cached production WMR composed by the existing owner."""

    return _production_composed_world_model_record(Path(repo_root).resolve().as_posix())


def intervention_generation_registry_bundle(repo_root: str | Path) -> RegistryBundle:
    """Return the existing L6 slot/mechanism registries for the N4 linker."""

    bundle = load_l6_intervention_substrate(Path(repo_root).resolve())
    slots = _owner_slot_registry(bundle)
    mechanisms = _owner_mechanism_registry(bundle, slot_registry=slots)
    return _owner_registry_bundle(mechanism_registry=mechanisms, slot_registry=slots)


def _resolve_owner_atom_world_binding(
    *,
    bundle: InterventionSubstrateBundle,
    operator_kind: str,
    raw_knob: Mapping[str, Any],
    parameter_value: float | int | str | bool,
    world_model_record: WorldModelRecord | None = None,
) -> tuple[Any, Any]:
    slot_registry = _owner_slot_registry(bundle)
    mechanism_registry = _owner_mechanism_registry(
        bundle,
        slot_registry=slot_registry,
    )
    mechanism_id = _knob_mechanism_id(
        operator_kind,
        raw_knob,
        mechanism_registry=mechanism_registry,
    )
    param_id = _knob_param_id(
        raw_knob,
        mechanism_id=mechanism_id,
        mechanism_registry=mechanism_registry,
    )
    world_record = world_model_record or _production_composed_world_model_record(
        _repo_root_for_bundle(bundle).as_posix()
    )
    intervention = _owner_intervention_spec(
        operator_kind=operator_kind,
        mechanism_id=mechanism_id,
        param_id=param_id,
        parameter_value=parameter_value,
    )
    linked_bundle, report = link_trinity(
        _owner_trinity_bundle(intervention, world_record=world_record),
        _owner_registry_bundle(
            mechanism_registry=mechanism_registry,
            slot_registry=slot_registry,
        ),
    )
    if not report.ok:
        raise InterventionSubstrateError(
            "knob_owner_intervention_unresolved",
            json.dumps([issue.model_dump(mode="json") for issue in report.issues], sort_keys=True),
        )
    linked = linked_bundle.bindings.interventions[0]
    causal = NodeIntervention(
        assignments=tuple(
            VariableAssignment(
                variable=slot_id,
                value_expr=str(_owner_param_value(parameter_value)),
            )
            for slot_id in linked.writes_slots
        )
    )
    selector_ref = intervention_atom_target_selector_ref(intervention)
    atom = build_intervention_atom_binding(
        problem_frame_ref=_hash_ref("l6-owner-problem-frame"),
        policy_spec_ref=_hash_ref("l6-owner-policy-spec"),
        intervention=intervention,
        linked_intervention=linked,
        causal_intervention=causal,
        query_target=QueryTarget(
            outcome_variables=("l6_intervention_effect",),
            conditioning=("l6_agent_sim_world",),
            functional="average_treatment_effect",
        ),
        identification_plan=identification_plan_for_intervention(causal),
        causal_context=InterventionContext(
            source_domain="l6_agent_sim_observed_world",
            target_domain="l6_agent_sim_policy_world",
            selection_diagram_ref=selector_ref,
            available_data_refs=(bundle.content_hash,),
            assumptions=("l6_knob_content_bound_to_trinity_owner",),
        ),
        world_model_record_ref=world_record.world_model_record_id,
        producer_ref="runtime.quality.intervention_substrate",
        provenance_refs=(
            bundle.source_refs.get(
                "intervention_knob_dictionary",
                "in_memory://intervention_knob_dictionary",
            ),
            bundle.source_content_hashes.get("intervention_knob_dictionary", bundle.content_hash),
        ),
        operator_proof_type_map={mechanism_id: "node"},
        estimand_metric_id="l6_intervention_effect",
        estimand_unit_id="ratio",
        source_population="l6_agent_sim_observed_world",
        target_population="l6_agent_sim_policy_world",
        status="grounded",
    )
    try:
        world_binding = resolve_intervention_atom_world_binding(atom, world_record)
    except WorldModelRecordError as exc:
        if exc.code == "world_slot_state_path_missing":
            raise InterventionSubstrateError("world_slot_unresolved", str(exc)) from exc
        raise InterventionSubstrateError(exc.code, str(exc)) from exc
    return atom, world_binding


def _owner_intervention_spec(
    *,
    operator_kind: str,
    mechanism_id: str,
    param_id: str,
    parameter_value: float | int | str | bool,
) -> InterventionSpec:
    return InterventionSpec(
        intervention_id=_owner_intervention_id(operator_kind),
        kind=mechanism_id,
        target=SelectorPredicate(
            field="id",
            operator=SelectorOperator.EQUALS,
            value="all",
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=1),
        params={param_id: _owner_param_value(parameter_value)},
        priority=0,
        measurement_expectations={"l6_operator_kind": operator_kind},
    )


def _owner_trinity_bundle(
    intervention: InterventionSpec,
    *,
    world_record: WorldModelRecord,
) -> TrinityBundle:
    return TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="l6_agent_sim_intervention_substrate",
            domain=ProblemDomain.FISCAL,
        ),
        policy_spec=PolicySpec(
            policy_id="l6_agent_sim_policy",
            problem_frame_ref=_hash_ref("l6-agent-sim-problem"),
            interventions=[intervention],
        ),
        model_spec=ModelSpec(
            model_id=world_record.simulation_model_ref.model_id,
            data_snapshot_ref=world_record.simulation_model_ref.data_snapshot_ref,
            registry_bundle_ref=world_record.simulation_model_ref.registry_bundle_ref,
            calibrated=world_record.simulation_model_ref.calibrated,
            calibration_ref=world_record.simulation_model_ref.calibration_ref,
        ),
    )


def _owner_slot_registry(bundle: InterventionSubstrateBundle) -> SlotRegistry:
    declared_slots = _slot_manifest_slots(bundle.slot_family_manifest)
    if not declared_slots:
        raise InterventionSubstrateError("world_slot_manifest_missing")
    slots: dict[str, Any] = {}
    for slot_id in sorted(declared_slots):
        slot = DEFAULT_SLOT_REGISTRY.slots.get(slot_id)
        if slot is None or not slot.state_path:
            raise InterventionSubstrateError("world_slot_unresolved", slot_id)
        if not _foundry_global_state_path_exists(str(slot.state_path)):
            raise InterventionSubstrateError(
                "world_slot_state_path_missing",
                f"{slot_id}:{slot.state_path}",
            )
        slots[slot_id] = slot
    return SlotRegistry(
        slots=slots,
        notes=[
            "L6 policy slots are selected from the production slot_family_manifest "
            "and validated against Foundry GlobalState before WMR binding."
        ],
    )


def _owner_mechanism_registry(
    bundle: InterventionSubstrateBundle,
    *,
    slot_registry: SlotRegistry,
) -> MechanismTypeRegistry:
    manifest = _mapping_or_none(bundle.world_mechanism_manifest)
    mechanisms = _mapping_or_none((manifest or {}).get("mechanisms"))
    if not mechanisms:
        raise InterventionSubstrateError("knob_owner_mechanism_manifest_missing")
    owner_specs: dict[str, MechanismTypeSpec] = {}
    for mechanism_id, raw in sorted(mechanisms.items()):
        raw_mechanism = _mapping_or_none(raw)
        if raw_mechanism is None:
            raise InterventionSubstrateError(
                "knob_owner_mechanism_unresolved",
                str(mechanism_id),
            )
        spec = _owner_mechanism_spec(
            str(mechanism_id),
            raw_mechanism,
            slot_registry=slot_registry,
        )
        owner_specs[spec.mechanism_id] = spec
    return MechanismTypeRegistry(
        mechanisms={
            **DEFAULT_MECHANISM_REGISTRY.mechanisms,
            **owner_specs,
        },
        notes=[
            "Default IR mechanisms plus L6 mechanisms loaded from the tracked "
            "owner authority manifest; L6 writes are not registered in code."
        ],
    )


def _owner_mechanism_spec(
    mechanism_id: str,
    raw_mechanism: Mapping[str, Any],
    *,
    slot_registry: SlotRegistry,
) -> MechanismTypeSpec:
    declared_id = _optional_text(raw_mechanism.get("mechanism_id")) or mechanism_id
    if declared_id != mechanism_id:
        raise InterventionSubstrateError(
            "knob_owner_mechanism_unresolved",
            f"{mechanism_id}!={declared_id}",
        )
    reads_slots = list(
        _string_tuple(raw_mechanism.get("reads_slots") or raw_mechanism.get("reads"))
    )
    writes_slots = list(
        _string_tuple(raw_mechanism.get("writes_slots") or raw_mechanism.get("writes"))
    )
    if not writes_slots:
        raise InterventionSubstrateError("knob_owner_write_slots_missing", mechanism_id)
    for slot_id in sorted({*reads_slots, *writes_slots}):
        if slot_id not in slot_registry.slots:
            raise InterventionSubstrateError("world_slot_unresolved", slot_id)

    raw_params = _mapping_or_none(raw_mechanism.get("params")) or {}
    params: dict[str, ParamSpec] = {}
    for param_id, raw_param in sorted(raw_params.items()):
        param_payload = _mapping_or_none(raw_param) or {}
        params[str(param_id)] = ParamSpec(
            param_id=str(param_payload.get("param_id") or param_id),
            required=_bool_value(param_payload.get("required")),
            value_type=_param_type_value(param_payload.get("value_type")),
            min_value=_decimal_value(param_payload.get("min_value")),
            max_value=_decimal_value(param_payload.get("max_value")),
            trainable=_bool_value(param_payload.get("trainable")),
            unit_id=_optional_text(param_payload.get("unit_id")),
            description=_optional_text(param_payload.get("description")),
            enum_values=(
                list(_string_tuple(param_payload.get("enum_values")))
                if param_payload.get("enum_values") is not None
                else None
            ),
        )
    return MechanismTypeSpec(
        mechanism_id=mechanism_id,
        params=params,
        reads_slots=reads_slots,
        writes_slots=writes_slots,
        default_merge={
            str(slot_id): str(rule_id)
            for slot_id, rule_id in (
                _mapping_or_none(raw_mechanism.get("default_merge")) or {}
            ).items()
        },
        description=_optional_text(raw_mechanism.get("description")),
    )


def _owner_registry_bundle(
    *,
    mechanism_registry: MechanismTypeRegistry,
    slot_registry: SlotRegistry,
) -> RegistryBundle:
    return RegistryBundle(
        mechanisms=mechanism_registry,
        slots=slot_registry,
        merge_rules=DEFAULT_MERGE_RULE_REGISTRY,
        selector_fields=DEFAULT_SELECTOR_FIELD_REGISTRY,
        units=DEFAULT_UNITS_REGISTRY,
        metrics=DEFAULT_METRIC_REGISTRY,
        constraints=ConstraintRegistry(constraints={}),
    )


def _owner_intervention_id(operator_kind: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char == "_" else "_"
        for char in operator_kind.casefold()
    ).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"l6_{cleaned}"
    return cleaned[:80]


def _hash_ref(seed: str) -> str:
    return gy_content_hash({"seed": seed})


def _free_grow_bundle(
    bundle: InterventionSubstrateBundle,
    *,
    threshold: _ThresholdRefProtocol,
    as_of: str = _REPRESENTATIVE_L3_AS_OF,
) -> InterventionSubstrateBundle:
    return replace_intervention_substrate_bundle(
        bundle,
        update={
            "knob_dictionary": {
                **bundle.knob_dictionary,
                _FREE_GROW_KNOB: {
                    "default": 0.0,
                    "mechanism_id": _FREE_GROW_MECHANISM,
                    "type": "float",
                    "min": 0.0,
                    "max": 0.4,
                    "param_path": "params.intensity",
                },
            },
            "world_mechanism_manifest": {
                **bundle.world_mechanism_manifest,
                "mechanisms": {
                    **(
                        _mapping_or_none(
                            bundle.world_mechanism_manifest.get("mechanisms")
                        )
                        or {}
                    ),
                    _FREE_GROW_MECHANISM: {
                        "mechanism_id": _FREE_GROW_MECHANISM,
                        "params": {
                            "intensity": {
                                "param_id": "intensity",
                                "required": True,
                                "value_type": "decimal",
                                "min_value": 0,
                                "max_value": 0.4,
                                "unit_id": "ratio",
                            }
                        },
                        "reads_slots": [_FREE_GROW_SLOT],
                        "writes_slots": [_FREE_GROW_SLOT],
                        "default_merge": {_FREE_GROW_SLOT: "override"},
                        "provenance_refs": [
                            "runtime:free-grow-owner-mechanism-writes-real-wmr-slot"
                        ],
                    },
                },
            },
            "lex_intervention_map": {
                **bundle.lex_intervention_map,
                _FUTURE_RELIEF_LAW: {
                    "knob_ids": [_FREE_GROW_KNOB],
                },
            },
            "lex_authority_manifest": {
                **bundle.lex_authority_manifest,
                "intervention_map_entries": [
                    *_mapping_list(
                        bundle.lex_authority_manifest.get("intervention_map_entries")
                    ),
                    {
                        "law_token": _FUTURE_RELIEF_LAW,
                        "provision_ref": f"lex_rule_thresholds:{threshold.threshold_id}",
                        "intervention_kind": _FREE_GROW_MECHANISM,
                        "knob_ids": [_FREE_GROW_KNOB],
                        "measurement_expectations": {
                            "applies_to": threshold.applies_to,
                            "as_of": as_of,
                            "candidate_unit": "ratio",
                        },
                        "metadata": {
                            "law_token": _FUTURE_RELIEF_LAW,
                            "provenance": "runtime free-grow owner artifact",
                        },
                    },
                ],
            },
            "observation_manifest": {
                **bundle.observation_manifest,
                "routes": [
                    *_mapping_list(bundle.observation_manifest.get("routes")),
                    {
                        "family": "future_budget_flows",
                        "identification_mode": "point_identified",
                        "target_contract": {
                            "contract_id": "foundry.causal.panel_observational_data.v1",
                            "contract_fqn": (
                                "polisyos.foundry.methods.catalog.causal.protocols."
                                "PanelObservationalData"
                            ),
                        },
                    },
                ],
                "artifacts": _mapping_list(bundle.observation_manifest.get("artifacts")),
            },
        }
    )


def _remove_property_mutation_report(
    *,
    bundle: InterventionSubstrateBundle,
    dangling_bundle: InterventionSubstrateBundle,
    registry: _MethodRegistryProtocol,
    lex_store: _LegalKnowledgeStoreProtocol,
    world_model_record: WorldModelRecord,
) -> list[dict[str, str]]:
    dead_route_bundle = _dead_route_bundle(bundle)
    checks = [
        (
            "unknown_op_admits",
            "knob_operator_unresolved",
            lambda: resolve_intervention_lever(
                bundle,
                operator_kind="unknown_budget_knob",
                parameter_value=1.0,
                world_model_record=world_model_record,
            ),
        ),
        (
            "out_of_domain_clamps",
            "knob_parameter_out_of_domain",
            lambda: resolve_intervention_lever(
                bundle,
                operator_kind="budget_allocation_multiplier",
                parameter_value=2.25,
                world_model_record=world_model_record,
            ),
        ),
        (
            "dangling_map_binds_anyway",
            "lex_map_knob_unresolved",
            lambda: resolve_law_bound_lever(
                dangling_bundle,
                law_token=_DANGLING_LAW,
                knob_id="not_a_real_knob",
                parameter_value=0.1,
                legal_store=lex_store,
                world_model_record=world_model_record,
            ),
        ),
        (
            "dead_route_succeeds",
            "method_route_unresolved",
            lambda: route_observation_family_method(
                dead_route_bundle,
                family="dead_route_family",
                registry=registry,
            ),
        ),
        (
            "owner_slot_reference_binds_without_owner_validation",
            "world_slot_unresolved",
            lambda: _owner_slot_reference_binds_without_owner_validation_signal(
                bundle,
                world_model_record=world_model_record,
            ),
        ),
        (
            "law_provision_reference_binds_without_l3_validation",
            "law_threshold_unresolved",
            lambda: _law_provision_reference_binds_without_l3_validation_signal(
                bundle,
                lex_store=lex_store,
                world_model_record=world_model_record,
            ),
        ),
        (
            "world_slot_owner_derivation_disabled_drops_coverage",
            "world_slot_owner_derivation_coverage_collapsed",
            lambda: _world_slot_owner_derivation_disabled_signal(
                bundle,
                lex_store=lex_store,
                world_model_record=world_model_record,
            ),
        ),
        (
            "world_slot_hardcoded_bypass_rejected",
            "knob_owner_mechanism_manifest_missing",
            lambda: _world_slot_hardcoded_bypass_signal(bundle),
        ),
        (
            "unknown_family_defaults",
            "family_route_unresolved",
            lambda: route_observation_family_method(
                bundle,
                family="unknown_family",
                registry=registry,
            ),
        ),
    ]
    results: list[dict[str, str]] = []
    for mutation_id, expected_code, thunk in checks:
        try:
            outcome = thunk()
        except InterventionSubstrateError as exc:
            status = "red" if exc.code == expected_code else "unexpected"
            actual = exc.code
        else:
            if (
                isinstance(outcome, ObservationMethodRoute)
                and outcome.reason_code == expected_code
            ):
                status = "red"
                actual = str(outcome.reason_code)
            else:
                status = "green"
                actual = "admitted"
        results.append(
            {
                "mutation_id": mutation_id,
                "expected_red_signal": expected_code,
                "actual_signal": actual,
                "status": status,
            }
        )
    return results


def _coverage_report(
    *,
    bundle: InterventionSubstrateBundle,
    lex_store: _LegalKnowledgeStoreProtocol,
    world_model_record: WorldModelRecord,
) -> dict[str, Any]:
    bundle = verify_intervention_substrate_bundle_content_hash(bundle)
    registry_module = importlib.import_module(
        "polisyos.foundry.extensions.registry"
    )

    world_details: list[dict[str, Any]] = []
    world_bound = 0
    for knob_id, raw in sorted(bundle.knob_dictionary.items()):
        raw_knob = _mapping_or_none(raw)
        if raw_knob is None:
            world_details.append(
                {"knob_id": knob_id, "status": "unresolved", "reason": "knob_row_not_object"}
            )
            continue
        try:
            value = _representative_knob_value(raw_knob, knob_id=str(knob_id))
            resolved = resolve_intervention_lever(
                bundle,
                operator_kind=str(knob_id),
                parameter_value=value,
                world_model_record=world_model_record,
            )
        except InterventionSubstrateError as exc:
            world_details.append(
                {"knob_id": knob_id, "status": "unresolved", "reason": exc.code}
            )
            continue
        world_bound += 1 if resolved.target_world_slots else 0
        world_details.append(
            {
                "knob_id": knob_id,
                "status": "bound" if resolved.target_world_slots else "unresolved",
                "target_world_slots": list(resolved.target_world_slots),
                "owner_atom_id": resolved.owner_resolution.get("atom_id"),
            }
        )

    law_details: list[dict[str, Any]] = []
    law_traced = 0
    for law_token in sorted(bundle.lex_intervention_map):
        try:
            knob_ids = _lex_map_knobs(bundle.lex_intervention_map, law_token)
            if not knob_ids:
                raise InterventionSubstrateError("lex_map_knob_unresolved", law_token)
            knob_id = knob_ids[0]
            raw_knob = _mapping_or_none(bundle.knob_dictionary.get(knob_id))
            if raw_knob is None:
                raise InterventionSubstrateError("lex_map_knob_unresolved", knob_id)
            value = _representative_knob_value(raw_knob, knob_id=knob_id)
            resolved_law = resolve_law_bound_lever(
                bundle,
                law_token=law_token,
                knob_id=knob_id,
                parameter_value=value,
                legal_store=lex_store,
                world_model_record=world_model_record,
            )
        except InterventionSubstrateError as exc:
            law_details.append(
                {"law_token": law_token, "status": "unresolved", "reason": exc.code}
            )
            continue
        law_traced += 1
        law_details.append(
            {
                "law_token": law_token,
                "status": resolved_law.status,
                "knob_id": resolved_law.knob.operator_kind,
                "threshold_id": resolved_law.threshold_id,
                "provision_ref": resolved_law.provision_ref,
                "threshold_reason": resolved_law.legal_threshold_evaluation.get("reason"),
            }
        )

    method_details: list[dict[str, Any]] = []
    method_available = 0
    method_unavailable = 0
    method_unresolved = 0
    with registry_module.controlled_builtin_foundry_method_registry_scope() as (
        registry,
        _registry_report,
    ):
        for route in _mapping_list(bundle.observation_manifest.get("routes")):
            family = str(route.get("family") or "").strip()
            if not family:
                continue
            try:
                resolved_route = route_observation_family_method(
                    bundle,
                    family=family,
                    registry=registry,
                )
            except InterventionSubstrateError as exc:
                method_unresolved += 1
                method_details.append(
                    {"family": family, "status": "unresolved", "reason": exc.code}
                )
                continue
            if resolved_route.status == RouteStatus.ROUTED:
                method_available += 1
            elif resolved_route.reason_code == "method_unavailable_python314":
                method_unavailable += 1
            else:
                method_unresolved += 1
            method_details.append(resolved_route.model_dump(mode="json"))

    return {
        "world_slot": {
            "total": len(bundle.knob_dictionary),
            "bound": world_bound,
            "unresolved": len(bundle.knob_dictionary) - world_bound,
            "details": world_details,
        },
        "law_trace": {
            "total": len(bundle.lex_intervention_map),
            "traced": law_traced,
            "unresolved": len(bundle.lex_intervention_map) - law_traced,
            "details": law_details,
        },
        "method_route": {
            "total": len(_mapping_list(bundle.observation_manifest.get("routes"))),
            "available": method_available,
            "unavailable_python314": method_unavailable,
            "unresolved": method_unresolved,
            "details": method_details,
        },
    }


def _representative_knob_value(
    raw_knob: Mapping[str, Any],
    *,
    knob_id: str,
) -> float | int | str | bool:
    values = _sequence_or_none(raw_knob.get("values") or raw_knob.get("allowed_values"))
    if values:
        value = values[0]
        if not isinstance(value, str | int | float | bool):
            raise InterventionSubstrateError("knob_parameter_type_unsupported", knob_id)
        return value
    min_value = raw_knob.get("min", raw_knob.get("min_value"))
    max_value = raw_knob.get("max", raw_knob.get("max_value"))
    if not _is_number(min_value) or not _is_number(max_value):
        raise InterventionSubstrateError("knob_domain_bounds_non_numeric", knob_id)
    return (float(min_value) + float(max_value)) / 2.0


def _dead_route_bundle(bundle: InterventionSubstrateBundle) -> InterventionSubstrateBundle:
    dead_contract = "foundry.dead.unregistered_contract.v1"
    observation_manifest = {
        **bundle.observation_manifest,
        "routes": [
            *_mapping_list(bundle.observation_manifest.get("routes")),
            {
                "family": "dead_route_family",
                "identification_mode": "point_identified",
                "target_contract": {
                    "contract_id": dead_contract,
                    "contract_fqn": "polisyos.foundry.methods.catalog.dead.Unregistered",
                },
            },
        ],
        "artifacts": [
            *_mapping_list(bundle.observation_manifest.get("artifacts")),
            {
                "artifact_ref": "in_memory://dead_route_contract",
                "status": "compiled",
                "target_contract": {"contract_id": dead_contract},
            },
        ],
    }
    return replace_intervention_substrate_bundle(
        bundle,
        update={
            "observation_manifest": observation_manifest,
        }
    )


def _unavailable_route_bundle(bundle: InterventionSubstrateBundle) -> InterventionSubstrateBundle:
    unavailable_contract = "foundry.bayesian.bart_regression.v1"
    observation_manifest = {
        **bundle.observation_manifest,
        "routes": [
            *_mapping_list(bundle.observation_manifest.get("routes")),
            {
                "family": "python314_unavailable_route_family",
                "identification_mode": "point_identified",
                "target_contract": {
                    "contract_id": unavailable_contract,
                    "contract_fqn": (
                        "polisyos.foundry.methods.catalog.bayesian.protocols."
                        "BartRegressionData"
                    ),
                },
            },
        ],
        "artifacts": [
            *_mapping_list(bundle.observation_manifest.get("artifacts")),
            {
                "artifact_ref": "in_memory://python314_unavailable_route_contract",
                "status": "compiled",
                "target_contract": {"contract_id": unavailable_contract},
            },
        ],
    }
    return replace_intervention_substrate_bundle(
        bundle,
        update={
            "observation_manifest": observation_manifest,
        }
    )


def _owner_slot_reference_binds_without_owner_validation_signal(
    bundle: InterventionSubstrateBundle,
    *,
    world_model_record: WorldModelRecord,
) -> object:
    fake_slot = "owner_validation_probe.fake_slot"
    fake_knob = "owner_validation_probe_fake_slot_knob"
    fake_mechanism = "owner_validation_probe_fake_slot_mechanism"
    raw_families = _mapping_or_none(bundle.slot_family_manifest.get("families")) or {}
    mutated_slot_manifest = {
        **bundle.slot_family_manifest,
        "families": {
            **raw_families,
            "owner_validation_probe_fake_family": {"slots": [fake_slot]},
        },
    }
    mutated = replace_intervention_substrate_bundle(
        bundle,
        update={
            "knob_dictionary": {
                **bundle.knob_dictionary,
                fake_knob: {
                    "default": 0.0,
                    "type": "float",
                    "min": 0.0,
                    "max": 1.0,
                    "mechanism_id": fake_mechanism,
                    "param_path": "params.intensity",
                },
            },
            "slot_family_manifest": mutated_slot_manifest,
            "world_mechanism_manifest": {
                **bundle.world_mechanism_manifest,
                "mechanisms": {
                    **(
                        _mapping_or_none(
                            bundle.world_mechanism_manifest.get("mechanisms")
                        )
                        or {}
                    ),
                    fake_mechanism: {
                        "mechanism_id": fake_mechanism,
                        "params": {
                            "intensity": {
                                "param_id": "intensity",
                                "required": True,
                                "value_type": "decimal",
                                "min_value": 0,
                                "max_value": 1,
                                "unit_id": "ratio",
                            }
                        },
                        "reads_slots": [fake_slot],
                        "writes_slots": [fake_slot],
                        "default_merge": {fake_slot: "override"},
                    },
                },
            },
        }
    )
    return resolve_intervention_lever(
        mutated,
        operator_kind=fake_knob,
        parameter_value=0.5,
        world_model_record=world_model_record,
    )


def _law_provision_reference_binds_without_l3_validation_signal(
    bundle: InterventionSubstrateBundle,
    *,
    lex_store: _LegalKnowledgeStoreProtocol,
    world_model_record: WorldModelRecord,
) -> object:
    fake_law = "owner_validation_probe_fake_l3_law"
    fake_threshold_id = "ffffffffffffffffffffffff"
    knob_id = next(iter(sorted(bundle.knob_dictionary)))
    raw_knob = _mapping_or_none(bundle.knob_dictionary[knob_id]) or {}
    mutated = replace_intervention_substrate_bundle(
        bundle,
        update={
            "lex_intervention_map": {
                **bundle.lex_intervention_map,
                fake_law: {"knob_ids": [knob_id]},
            },
            "lex_authority_manifest": {
                **bundle.lex_authority_manifest,
                "intervention_map_entries": [
                    *_mapping_list(
                        bundle.lex_authority_manifest.get("intervention_map_entries")
                    ),
                    {
                        "law_token": fake_law,
                        "provision_ref": f"lex_rule_thresholds:{fake_threshold_id}",
                        "intervention_kind": knob_id,
                        "knob_ids": [knob_id],
                        "measurement_expectations": {
                            "as_of": _REPRESENTATIVE_L3_AS_OF,
                            "candidate_unit": "ratio",
                        },
                        "metadata": {
                            "law_token": fake_law,
                            "provenance": "runtime owner-validation mutation",
                        },
                    },
                ],
            },
        }
    )
    return resolve_law_bound_lever(
        mutated,
        law_token=fake_law,
        knob_id=knob_id,
        parameter_value=_representative_knob_value(raw_knob, knob_id=knob_id),
        legal_store=lex_store,
        world_model_record=world_model_record,
    )


def _world_slot_owner_derivation_disabled_signal(
    bundle: InterventionSubstrateBundle,
    *,
    lex_store: _LegalKnowledgeStoreProtocol,
    world_model_record: WorldModelRecord,
) -> dict[str, Any]:
    mutated = replace_intervention_substrate_bundle(
        bundle,
        update={
            "world_mechanism_manifest": {"schema_version": "1.0", "mechanisms": {}},
        }
    )
    coverage = _coverage_report(
        bundle=mutated,
        lex_store=lex_store,
        world_model_record=world_model_record,
    )
    if coverage["world_slot"]["total"] > 0 and coverage["world_slot"]["bound"] == 0:
        raise InterventionSubstrateError("world_slot_owner_derivation_coverage_collapsed")
    return coverage


def _world_slot_hardcoded_bypass_signal(bundle: InterventionSubstrateBundle) -> object:
    raw_knobs: dict[str, Any] = {}
    for knob_id, raw in bundle.knob_dictionary.items():
        raw_knob = _mapping_or_none(raw) or {}
        raw_knobs[str(knob_id)] = {
            **raw_knob,
            "mechanism_id": "parallel_raw_slot_only",
            "target_world_slots": ["government.balance"],
        }
    mutated = replace_intervention_substrate_bundle(
        bundle,
        update={
            "knob_dictionary": raw_knobs,
            "world_mechanism_manifest": {"schema_version": "1.0", "mechanisms": {}},
        }
    )
    first_knob = next(iter(sorted(mutated.knob_dictionary)))
    return resolve_intervention_lever(
        mutated,
        operator_kind=first_knob,
        parameter_value=_representative_knob_value(
            _mapping_or_none(mutated.knob_dictionary[first_knob]) or {},
            knob_id=first_knob,
        ),
    )


def _error_code(thunk: Callable[[], object]) -> str:
    try:
        thunk()
    except InterventionSubstrateError as exc:
        return exc.code
    return "admitted"


def _json_ready(value: object) -> object:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _repo_ref(path: Path, repo_root: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        rel = path.resolve().as_posix()
    return f"repo://{rel}"


def _mapping_or_none(value: object) -> dict[str, Any] | None:
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _knob_domain(raw_knob: Mapping[str, Any]) -> KnobDomain:
    value_type = str(raw_knob.get("type") or raw_knob.get("value_type") or "").strip()
    if not value_type:
        raise InterventionSubstrateError("knob_domain_type_missing")
    values = _sequence_or_none(raw_knob.get("values") or raw_knob.get("allowed_values"))
    if values is not None:
        return KnobDomain(
            kind="discrete",
            value_type=value_type,
            min_value=None,
            max_value=None,
            unit=_optional_text(raw_knob.get("unit")),
        )
    min_value = raw_knob.get("min", raw_knob.get("min_value"))
    max_value = raw_knob.get("max", raw_knob.get("max_value"))
    if min_value is None or max_value is None:
        raise InterventionSubstrateError("knob_domain_bounds_missing")
    if not _is_number(min_value) or not _is_number(max_value):
        raise InterventionSubstrateError("knob_domain_bounds_non_numeric")
    return KnobDomain(
        kind="range",
        value_type=value_type,
        min_value=float(min_value),
        max_value=float(max_value),
        unit=_optional_text(raw_knob.get("unit")),
    )


def _validate_value_in_domain(
    *,
    operator_kind: str,
    value: object,
    domain: KnobDomain,
    raw_knob: Mapping[str, Any],
) -> float | int | str | bool:
    if domain.kind == "discrete":
        allowed = tuple(
            _sequence_or_none(raw_knob.get("values") or raw_knob.get("allowed_values"))
            or ()
        )
        if value not in allowed:
            raise InterventionSubstrateError("knob_parameter_out_of_domain", operator_kind)
        if not isinstance(value, str | int | float | bool):
            raise InterventionSubstrateError("knob_parameter_type_unsupported", operator_kind)
        return value
    token = domain.value_type.casefold()
    if token in {"float", "number", "numeric"}:
        if not _is_number(value):
            raise InterventionSubstrateError("knob_parameter_type_mismatch", operator_kind)
        candidate: float | int = float(value)
    elif token in {"int", "integer"}:
        if isinstance(value, bool) or not isinstance(value, int):
            raise InterventionSubstrateError("knob_parameter_type_mismatch", operator_kind)
        candidate = int(value)
    else:
        raise InterventionSubstrateError("knob_parameter_type_unsupported", token)
    if domain.min_value is None or domain.max_value is None:
        raise InterventionSubstrateError("knob_domain_bounds_missing", operator_kind)
    if not (float(domain.min_value) <= float(candidate) <= float(domain.max_value)):
        raise InterventionSubstrateError("knob_parameter_out_of_domain", operator_kind)
    return candidate


def _knob_mechanism_id(
    operator_kind: str,
    raw_knob: Mapping[str, Any],
    *,
    mechanism_registry: MechanismTypeRegistry,
) -> str:
    mechanism_id = str(
        raw_knob.get("mechanism_id")
        or raw_knob.get("intervention_kind")
        or operator_kind
    ).strip()
    if mechanism_id not in mechanism_registry.mechanisms:
        raise InterventionSubstrateError("knob_owner_mechanism_unresolved", mechanism_id)
    return mechanism_id


def _knob_param_id(
    raw_knob: Mapping[str, Any],
    *,
    mechanism_id: str,
    mechanism_registry: MechanismTypeRegistry,
) -> str:
    explicit = _optional_text(raw_knob.get("param_id"))
    if explicit:
        return explicit
    param_path = _optional_text(raw_knob.get("param_path"))
    if param_path:
        return _param_key_from_path(param_path)
    mechanism = mechanism_registry.mechanisms.get(mechanism_id)
    if mechanism is not None and len(mechanism.params) == 1:
        return next(iter(mechanism.params))
    raise InterventionSubstrateError("knob_owner_param_unresolved", mechanism_id)


def _knob_param_path(
    raw_knob: Mapping[str, Any],
    *,
    mechanism_id: str,
    mechanism_registry: MechanismTypeRegistry,
) -> str:
    param_path = _optional_text(raw_knob.get("param_path"))
    if param_path:
        return param_path
    param_id = _knob_param_id(
        raw_knob,
        mechanism_id=mechanism_id,
        mechanism_registry=mechanism_registry,
    )
    return f"params.{param_id}"


def _knob_default(raw_knob: Mapping[str, Any], *, knob_id: str) -> float | int | str | bool:
    if "default" in raw_knob:
        value = raw_knob["default"]
    elif "default_value" in raw_knob:
        value = raw_knob["default_value"]
    else:
        raise InterventionSubstrateError("knob_owner_default_missing", knob_id)
    if not isinstance(value, str | int | float | bool):
        raise InterventionSubstrateError("knob_owner_default_unsupported", knob_id)
    return value


def _param_key_from_path(param_path: str) -> str:
    cleaned = str(param_path or "").strip()
    if not cleaned:
        raise InterventionSubstrateError("knob_owner_param_path_missing")
    return cleaned.split(".")[-1]


def _owner_param_value(value: float | int | str | bool) -> str | int | bool:
    if isinstance(value, bool | int | str):
        return value
    return str(value)


def _owner_optional_param_value(value: object) -> str | int | bool | None:
    if value is None:
        return None
    if not isinstance(value, str | int | float | bool):
        raise InterventionSubstrateError("knob_owner_param_value_unsupported", str(value))
    return _owner_param_value(value)


def _validate_target_slots_against_manifest(
    slot_family_manifest: Mapping[str, Any],
    target_slots: Sequence[str],
) -> None:
    declared = _slot_manifest_slots(slot_family_manifest)
    if not declared:
        return
    missing = sorted(set(target_slots).difference(declared))
    if missing:
        raise InterventionSubstrateError(
            "world_slot_unresolved",
            ", ".join(missing),
        )


def _slot_manifest_slots(slot_family_manifest: Mapping[str, Any]) -> set[str]:
    families = _mapping_or_none(slot_family_manifest.get("families")) or {}
    slots: set[str] = set()
    for raw_family in families.values():
        family = _mapping_or_none(raw_family) or {}
        for slot in _string_tuple(family.get("slots")):
            slots.add(slot)
    return slots


def _lex_map_knobs(lex_map: Mapping[str, Any], law_token: str) -> tuple[str, ...]:
    raw = lex_map.get(law_token)
    if raw is None:
        raise InterventionSubstrateError("law_modality_unresolved", law_token)
    if isinstance(raw, Mapping):
        return _string_tuple(raw.get("knobs") or raw.get("knob_ids") or raw.get("knob_id"))
    return _string_tuple(raw)


def _law_authority(
    bundle: InterventionSubstrateBundle,
    law_token: str,
    knob_id: str,
) -> LawAuthorityRef:
    owner_entry = _law_owner_entry(bundle, law_token=law_token, knob_id=knob_id)
    expectations = _mapping_or_none(owner_entry.get("measurement_expectations")) or {}
    provision_ref = _optional_text(owner_entry.get("provision_ref"))
    if not provision_ref:
        raise InterventionSubstrateError("law_authority_missing", law_token)
    registry = _lex_owner_registry(bundle)
    try:
        mapping = registry.require_mapping(provision_ref)
        registry.require_knob(knob_id)
        registry.resolve(
            provision_ref,
            intervention_id=_owner_intervention_id(
                str(owner_entry.get("intervention_kind") or knob_id)
            ),
            target=SelectorPredicate(
                field="id",
                operator=SelectorOperator.EQUALS,
                value="all",
            ),
            schedule=ScheduleSpec(start_step=0, duration_steps=1),
            knob_value_overrides={
                knob_id: _owner_param_value(
                    _knob_default(bundle.knob_dictionary[knob_id], knob_id=knob_id)
                )
            },
        )
    except Exception as exc:
        raise InterventionSubstrateError("law_authority_missing", law_token) from exc
    if knob_id not in mapping.knob_ids:
        raise InterventionSubstrateError(
            "lex_map_knob_not_bound",
            f"{law_token} does not bind {knob_id}",
        )
    threshold_id = _optional_text(
        owner_entry.get("threshold_id") or expectations.get("threshold_id")
    )
    metric = _optional_text(owner_entry.get("metric") or expectations.get("metric"))
    if not threshold_id and provision_ref.startswith("lex_rule_thresholds:"):
        threshold_id = provision_ref.split(":", 1)[1].strip()
    if not threshold_id and not metric:
        raise InterventionSubstrateError("law_authority_missing", law_token)
    as_of = _optional_text(owner_entry.get("as_of") or expectations.get("as_of"))
    if not as_of:
        raise InterventionSubstrateError("law_authority_as_of_missing", law_token)
    authority_fields = {
        "threshold_id": threshold_id,
        "metric": metric,
        "doc_family_id": _optional_text(
            owner_entry.get("doc_family_id") or expectations.get("doc_family_id")
        ),
        "provision_ref": (
            provision_ref
            if provision_ref.startswith("duckdb://")
            else None
        ),
        "candidate_unit": _optional_text(
            owner_entry.get("candidate_unit") or expectations.get("candidate_unit")
        ),
        "applies_to": _optional_text(
            owner_entry.get("applies_to") or expectations.get("applies_to")
        ),
        "as_of": as_of,
        "jurisdiction": _optional_text(
            owner_entry.get("jurisdiction") or expectations.get("jurisdiction")
        ),
        "domain": _optional_text(owner_entry.get("domain") or expectations.get("domain")),
    }
    return LawAuthorityRef.model_validate(
        {key: value for key, value in authority_fields.items() if value is not None}
    )


def _law_owner_entry(
    bundle: InterventionSubstrateBundle,
    *,
    law_token: str,
    knob_id: str,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    for raw in _mapping_list(bundle.lex_authority_manifest.get("intervention_map_entries")):
        entry = _mapping_or_none(raw)
        if entry is None:
            continue
        if _law_token_from_owner_entry(entry) != law_token:
            continue
        if knob_id not in _string_tuple(
            entry.get("knob_ids") or entry.get("knobs") or entry.get("knob_id")
        ):
            continue
        matches.append(entry)
    if not matches:
        raise InterventionSubstrateError("law_authority_missing", law_token)
    if len(matches) > 1:
        raise InterventionSubstrateError("law_authority_ambiguous", law_token)
    return matches[0]


def _law_token_from_owner_entry(entry: Mapping[str, Any]) -> str:
    metadata = _mapping_or_none(entry.get("metadata")) or {}
    token = _optional_text(entry.get("law_token") or metadata.get("law_token"))
    if not token:
        raise InterventionSubstrateError("law_authority_missing", "law_token")
    return token


def _lex_owner_registry(
    bundle: InterventionSubstrateBundle,
) -> _LexProvisionMappingRegistryProtocol:
    lex_artifacts = importlib.import_module("polisyos.lex.intervention_artifacts")
    slot_registry = _owner_slot_registry(bundle)
    mechanism_registry = _owner_mechanism_registry(bundle, slot_registry=slot_registry)
    intervention_entries: list[dict[str, Any]] = []
    for raw in _mapping_list(bundle.lex_authority_manifest.get("intervention_map_entries")):
        entry = _mapping_or_none(raw)
        if entry is None:
            continue
        law_token = _law_token_from_owner_entry(entry)
        knob_ids = _string_tuple(
            entry.get("knob_ids") or entry.get("knobs") or entry.get("knob_id")
        )
        provision_ref = _optional_text(entry.get("provision_ref"))
        intervention_kind = _optional_text(entry.get("intervention_kind"))
        if not provision_ref or not intervention_kind or not knob_ids:
            continue
        expectations = dict(_mapping_or_none(entry.get("measurement_expectations")) or {})
        expectations.update(
            {
                key: entry[key]
                for key in (
                    "threshold_id",
                    "metric",
                    "candidate_unit",
                    "applies_to",
                    "as_of",
                )
                if key in entry
            }
        )
        intervention_entries.append(
            {
                "provision_ref": provision_ref,
                "intervention_kind": intervention_kind,
                "knob_ids": list(knob_ids),
                "measurement_expectations": expectations,
                "metadata": {"law_token": str(law_token)},
            }
        )
    knob_entries: list[dict[str, Any]] = []
    for knob_id, raw in bundle.knob_dictionary.items():
        raw_knob = _mapping_or_none(raw)
        if raw_knob is None:
            continue
        mechanism_id = _knob_mechanism_id(
            str(knob_id),
            raw_knob,
            mechanism_registry=mechanism_registry,
        )
        knob_entries.append(
            {
                "knob_id": str(knob_id),
                "param_id": _knob_param_id(
                    raw_knob,
                    mechanism_id=mechanism_id,
                    mechanism_registry=mechanism_registry,
                ),
                "param_path": _knob_param_path(
                    raw_knob,
                    mechanism_id=mechanism_id,
                    mechanism_registry=mechanism_registry,
                ),
                "default_value": _owner_param_value(
                    _knob_default(raw_knob, knob_id=str(knob_id))
                ),
                "min_value": _owner_optional_param_value(
                    raw_knob.get("min", raw_knob.get("min_value"))
                ),
                "max_value": _owner_optional_param_value(
                    raw_knob.get("max", raw_knob.get("max_value"))
                ),
                "metadata": {"mechanism_id": mechanism_id},
            }
        )
    return lex_artifacts.LexProvisionMappingRegistry(
        intervention_map_entries=intervention_entries,
        knob_dictionary_entries=knob_entries,
    )


def _manifest_route(observation_manifest: Mapping[str, Any], family: str) -> dict[str, Any]:
    routes = _mapping_list(observation_manifest.get("routes"))
    matches = [route for route in routes if str(route.get("family") or "").strip() == family]
    if len(matches) > 1:
        raise InterventionSubstrateError("family_route_ambiguous", family)
    if matches:
        return matches[0]
    raise InterventionSubstrateError("family_route_unresolved", family)


def _route_contract(route: Mapping[str, Any]) -> tuple[str, str | None]:
    target = _mapping_or_none(route.get("target_contract")) or route
    contract_id = str(
        target.get("contract_id")
        or target.get("method_contract_target")
        or target.get("contract_target")
        or ""
    ).strip()
    if not contract_id:
        raise InterventionSubstrateError("family_route_contract_missing")
    contract_fqn = _optional_text(target.get("contract_fqn"))
    return contract_id, contract_fqn


def _assert_compiled_contract(observation_manifest: Mapping[str, Any], contract_id: str) -> None:
    artifacts = _mapping_list(observation_manifest.get("artifacts"))
    if not artifacts:
        raise InterventionSubstrateError("compiled_contract_artifact_missing", contract_id)
    for artifact in artifacts:
        target = _mapping_or_none(artifact.get("target_contract")) or {}
        if str(target.get("contract_id") or "").strip() != contract_id:
            continue
        if str(artifact.get("status") or "").strip() != "compiled":
            raise InterventionSubstrateError("compiled_contract_not_available", contract_id)
        return
    raise InterventionSubstrateError("compiled_contract_artifact_missing", contract_id)


def _registered_methods_for_contract(
    registry: _MethodRegistryProtocol,
    contract_id: str,
    *,
    contract_fqn: str | None = None,
) -> tuple[_MethodSignatureProtocol, ...]:
    # Metadata tokens can neither prove nor exhaust the actual input relation.
    from polisyos.foundry import method_accepts_input_contract

    matches = []
    for signature in registry.list_all():
        try:
            method = registry.get(signature.fqn)
        except (ImportError, KeyError, ValueError):
            continue
        if method_accepts_input_contract(method, contract_id):
            matches.append(signature)
    return tuple(sorted(matches, key=lambda item: item.fqn))


def _missing_method_dependencies(entry: _MethodEntryProtocol | None) -> tuple[str, ...]:
    if entry is None:
        return ("registry_entry_missing",)
    deps = tuple(str(dep).strip() for dep in entry.metadata.required_deps if str(dep).strip())
    missing = [dep for dep in deps if not _module_available(dep)]
    missing.extend(
        dep
        for dep in entry.metadata.optional_deps
        if str(dep).strip() in {"dowhy", "econml", "cvxpy"}
        and not _module_available(str(dep).strip())
    )
    return tuple(sorted(set(missing)))


def _module_available(dep: str) -> bool:
    module_name = {
        "scikit-learn": "sklearn",
        "sklearn": "sklearn",
    }.get(dep, dep.replace("-", "_"))
    return importlib.util.find_spec(module_name) is not None


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _sequence_or_none(value: object) -> Sequence[object] | None:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return value
    return None


def _string_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        items = (value,)
    elif isinstance(value, Sequence) and not isinstance(value, bytes | bytearray):
        items = tuple(value)
    elif value is None:
        items = ()
    else:
        items = (value,)
    output: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return tuple(output)


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes"}
    return bool(value)


def _param_type_value(value: object) -> ParamType:
    token = str(value or ParamType.DECIMAL.value).strip().casefold()
    try:
        return ParamType(token)
    except ValueError:
        raise InterventionSubstrateError("knob_owner_param_type_unresolved", token) from None


def _decimal_value(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise InterventionSubstrateError("knob_owner_param_bound_invalid", str(value))
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise InterventionSubstrateError("knob_owner_param_bound_invalid", str(value)) from exc


def _foundry_global_state_path_exists(state_path: str) -> bool:
    if not state_path:
        return False
    state_module = importlib.import_module("polisyos.foundry.contracts.state")
    return _annotation_path_exists(
        state_module.GlobalState,
        tuple(part for part in state_path.split(".") if part),
    )


def _annotation_path_exists(annotation: object, parts: tuple[str, ...]) -> bool:
    if not parts:
        return True
    resolved = _strip_optional_annotation(annotation)
    fields = getattr(resolved, "__dataclass_fields__", None)
    if isinstance(fields, Mapping):
        field = fields.get(parts[0])
        if field is None:
            return False
        if len(parts) == 1:
            return True
        return _annotation_path_exists(getattr(field, "type", None), parts[1:])
    annotations = getattr(resolved, "__annotations__", None)
    if isinstance(annotations, Mapping) and parts[0] in annotations:
        if len(parts) == 1:
            return True
        return _annotation_path_exists(annotations[parts[0]], parts[1:])
    return False


def _strip_optional_annotation(annotation: object) -> object:
    args = tuple(arg for arg in get_args(annotation) if arg is not type(None))
    if len(args) == 1 and get_origin(annotation) is not None:
        return args[0]
    return annotation


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _is_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    return math.isfinite(float(value))


__all__ = [
    "INTERVENTION_SUBSTRATE_ARTIFACT_KIND",
    "INTERVENTION_SUBSTRATE_SCHEMA_VERSION",
    "InterventionLeverRefusal",
    "InterventionLeverResolution",
    "InterventionSubstrateBundle",
    "InterventionSubstrateError",
    "KnobDomain",
    "LawLeverResolution",
    "ObservationMethodRoute",
    "default_l6_bundle_paths",
    "intervention_generation_registry_bundle",
    "intervention_substrate_behavior_report",
    "intervention_substrate_bundle_content_hash",
    "load_l6_intervention_substrate",
    "production_composed_world_model_record",
    "project_value_method_route_constraint",
    "replace_intervention_substrate_bundle",
    "resolve_intervention_lever",
    "resolve_law_bound_lever",
    "resolve_observation_manifest_routes",
    "route_observation_family_method",
    "verify_intervention_substrate_bundle_content_hash",
]
