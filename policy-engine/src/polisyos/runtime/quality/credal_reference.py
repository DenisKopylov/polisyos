"""Credal reference view over L2, L3, L6, and WorldModelRecord.

This module is a view and lift API, not a second reference store. L2/SKG,
L3/Lex, L6 intervention artifacts, and the WorldModelRecord remain the owners.
The view enumerates grounding-essential edges, derives a status from each
owner's own signals, and exposes scoped symbolic lifts for CGF relation checks.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Literal

import duckdb

from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.intervention_substrate import (
    InterventionSubstrateError,
    _production_composed_world_model_record,
    load_l6_intervention_substrate,
    resolve_intervention_lever,
    resolve_law_bound_lever,
    route_observation_family_method,
)
from polisyos.runtime.quality.substrate_registry import (
    DEFAULT_L2_SCHOLAR_KG_PATH,
    DEFAULT_L3_LEX_KG_PATH,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.runtime.quality.world_model_record import WorldModelRecord

CREDAL_REFERENCE_SCHEMA_VERSION = "policyos.runtime.grounding_credal_reference.v1"
GROUNDING_BACKEND_AVAILABILITY_SCHEMA_VERSION = (
    "policyos.runtime.grounding_backend_availability.v1"
)
DEFAULT_REFERENCE_AS_OF = "2026-06-29"
DEFAULT_DATA_FORGE_CATALOG_PATH = (
    "production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb"
)
NUMERIC_SCALING = "basis_points"
ESSENTIAL_EDGE_SCOPE_CRITERION = (
    "An owner edge class is grounding-essential iff a JTCG hard constraint "
    "(slot_exists, allowed_target_type, unit_compatible, lex_applicable, "
    "threshold_satisfied, knob_maps_to, method.treatment/outcome, "
    "admissibility) or an RT1 relation axis (op, target, do_value, sign, "
    "params, unit, scope, population, time, outcome, effect_path, estimand, "
    "admissibility) depends on it."
)
_INCLUDED_EDGE_CLASSES: tuple[dict[str, str], ...] = (
    {
        "modality": "L2_CANONICAL_VARIABLE",
        "owner_table": "ac_skg_variables",
        "dependency": "JTCG target identity; RT1 target/scope/population axes",
        "selection": "all SKG canonical-variable rows",
    },
    {
        "modality": "L2_VARIABLE_HIERARCHY",
        "owner_table": "ac_skg_variables.parent_name/approved_parent_name",
        "dependency": "RT1 specialization/generalization narrower/broader axis",
        "selection": "rows with a parent_name or approved_parent_name signal",
    },
    {
        "modality": "L2_VARIABLE_ALIGNMENT",
        "owner_table": "ac_skg_variable_synonyms",
        "dependency": "JTCG/RT1 synonym and canonical target grounding",
        "selection": "all SKG synonym-alignment rows",
    },
    {
        "modality": "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
        "owner_table": "ds_variable_alignments",
        "dependency": "grounding retrieval and exact raw-to-canonical variable binding",
        "selection": "all production Data Forge variable-alignment rows",
    },
    {
        "modality": "L2_CAUSAL_EDGE",
        "owner_table": "ac_skg_edges",
        "dependency": "RT1 effect_path/sign axes and causal neighbourhood grounding",
        "selection": "all exact SKG causal-edge rows",
    },
    {
        "modality": "L2_FAMILY_EDGE",
        "owner_table": "ac_skg_family_edges",
        "dependency": "RT1 effect_path and specialization/generalization axes",
        "selection": "all SKG family-level causal-edge rows",
    },
    {
        "modality": "L2_MODERATION_EDGE",
        "owner_table": "ac_skg_moderation_edges",
        "dependency": "RT1 estimand/effect_path moderation axis",
        "selection": "all SKG moderation-edge rows",
    },
    {
        "modality": "L2_CAUSAL_CLAIM",
        "owner_table": "ac_causal_claims",
        "dependency": "RT1 sign/effect_path/admissibility axes",
        "selection": "all SKG causal-claim rows",
    },
    {
        "modality": "L2_CONTESTED_EDGE",
        "owner_table": "ac_skg_contested_edges",
        "dependency": "credal ambiguity for conflicting causal directions",
        "selection": "all SKG contested-edge rows",
    },
    {
        "modality": "L3_RULE_THRESHOLD",
        "owner_table": "lex_rule_thresholds joined to lex_normative_ready_facts",
        "dependency": "JTCG lex_applicable/threshold_satisfied/unit_compatible",
        "selection": "all L3 rule-threshold rows",
    },
    {
        "modality": "L3_AMENDMENT",
        "owner_table": "lex_amendments",
        "dependency": "JTCG legal applicability and effective-window status",
        "selection": "all L3 amendment rows",
    },
    {
        "modality": "L3_REFERENCE_EDGE",
        "owner_table": "lex_reference_edges",
        "dependency": "cross-provision admissibility/applicability references",
        "selection": "all resolved and partial L3 cross-reference rows",
    },
    {
        "modality": "L6_KNOB_OPERATOR",
        "owner_table": "intervention_knob_dictionary",
        "dependency": "JTCG knob_maps_to/operator compatibility",
        "selection": "all L6 knob dictionary entries",
    },
    {
        "modality": "L6_KNOB_WORLD_SLOT",
        "owner_table": "intervention_knob_dictionary + WorldModelRecord",
        "dependency": "JTCG allowed target world slots",
        "selection": "all L6 knob-to-world-slot bindings",
    },
    {
        "modality": "L6_LEX_INTERVENTION_MAP",
        "owner_table": "lex_intervention_map",
        "dependency": "JTCG law-to-knob admissibility",
        "selection": "all L6 law-token to knob bindings",
    },
    {
        "modality": "L6_OBSERVATION_CONTRACT_ROUTE",
        "owner_table": "observation_to_contract_manifest",
        "dependency": "JTCG method.treatment/outcome routing",
        "selection": "all observation family routes",
    },
    {
        "modality": "WMR_WORLD_SLOT",
        "owner_table": "WorldModelRecord.policy_slot_map",
        "dependency": "JTCG slot_exists/allowed_target_type/unit_compatible",
        "selection": "all composed WMR policy slots",
    },
    {
        "modality": "WMR_POLICY_SLOT_MAP",
        "owner_table": "WorldModelRecord.policy_slot_map",
        "dependency": "policy-slot map lookup for JTCG target binding",
        "selection": "all composed WMR policy-slot map rows",
    },
)
_EXCLUDED_EDGE_CLASSES: tuple[dict[str, str], ...] = (
    {
        "owner_table": "ds_alignment_audit",
        "criterion_decision": "excluded",
        "reason": (
            "audit trail over ds_variable_alignments; not a separate JTCG/RT1 "
            "edge class once the authoritative alignment row is included"
        ),
    },
    {
        "owner_table": "ds_alignment_hints",
        "criterion_decision": "excluded",
        "reason": (
            "pre-binding hints only; no adopted raw-to-canonical edge and zero "
            "production rows in the current owner store"
        ),
    },
    {
        "owner_table": "ac_claim_adjudications",
        "criterion_decision": "excluded",
        "reason": (
            "claim-quality evidence consumed by L2 claim/edge status derivation, "
            "not a distinct hard-constraint reference edge"
        ),
    },
    {
        "owner_table": "lex_references",
        "criterion_decision": "excluded",
        "reason": (
            "raw reference extraction predecessor; lex_reference_edges is the "
            "resolved/partial cross-provision edge owner"
        ),
    },
    {
        "owner_table": "lex_reference_resolution_audit",
        "criterion_decision": "excluded",
        "reason": (
            "resolution audit trail for lex_reference_edges; not a separate "
            "admissibility edge class"
        ),
    },
)

type CredalReferenceStatus = Literal[
    "confirmed",
    "contested",
    "incomplete",
    "deprecated",
    "out_of_scope",
]
type CompletionKind = Literal[
    "fixed",
    "alternative",
    "may_exist",
    "may_not_exist",
    "partial",
    "excluded",
]
type EdgeKey = tuple[str, str]


@dataclass(frozen=True)
class AdmissibleCompletion:
    """One symbolic reference completion for a credal edge."""

    completion_kind: CompletionKind
    value: Mapping[str, Any] = field(default_factory=dict)
    reason: str = ""

    def to_payload(self) -> dict[str, Any]:
        """Return a stable JSON payload."""

        return {
            "completion_kind": self.completion_kind,
            "reason": self.reason,
            "value": _json_ready(self.value),
        }


@dataclass(frozen=True)
class CredalReferenceEdge:
    """Statused, content-addressed grounding edge in the credal reference."""

    modality: str
    edge_id: str
    status: CredalReferenceStatus
    admissible_completions: tuple[AdmissibleCompletion, ...]
    provenance: Mapping[str, Any]
    unit: str | None = None
    scale: str | None = None
    content_hash: str = ""

    @property
    def key(self) -> EdgeKey:
        """Return the canonical edge key."""

        return (self.modality, self.edge_id)

    @property
    def is_set_valued(self) -> bool:
        """Return whether the edge exposes more than one admissible completion."""

        return len(self.admissible_completions) > 1

    def with_content_hash(self) -> CredalReferenceEdge:
        """Return the same edge with its deterministic content hash populated."""

        return replace(self, content_hash=gy_content_hash(self._hash_payload()))

    def to_payload(self) -> dict[str, Any]:
        """Return a stable payload for contract surfaces and hashing."""

        payload = self._hash_payload()
        payload["content_hash"] = self.content_hash
        return payload

    def _hash_payload(self) -> dict[str, Any]:
        return {
            "admissible_completions": [
                completion.to_payload() for completion in self.admissible_completions
            ],
            "edge_id": self.edge_id,
            "modality": self.modality,
            "provenance": _json_ready(self.provenance),
            "scale": self.scale,
            "status": self.status,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class CredalReference:
    """Content-addressed K_ref view used by CGF relation lifting."""

    schema_version: str
    reference_epoch: str
    reference_hash: str
    as_of: str
    component_versions: Mapping[str, str]
    essential_edges: Mapping[EdgeKey, CredalReferenceEdge]

    def reference_lift(
        self,
        edge_scope: Iterable[EdgeKey | str],
    ) -> dict[str, dict[str, Any]]:
        """Return a scoped symbolic lift for the requested edge keys.

        Missing edges fail closed as ``out_of_scope``. The method never
        enumerates reference completions outside the requested scope.
        """

        lifted: dict[str, dict[str, Any]] = {}
        for key in edge_scope:
            normalized = _normalize_edge_key(key)
            edge = self.essential_edges.get(normalized)
            if edge is None:
                edge = out_of_scope_edge(
                    normalized,
                    reason="edge_not_in_credal_reference",
                )
            lifted[_edge_key_text(edge.key)] = {
                "status": edge.status,
                "admissible_completions": [
                    item.to_payload() for item in edge.admissible_completions
                ],
                "content_hash": edge.content_hash,
                "is_set_valued": edge.is_set_valued,
            }
        return lifted

    def all_essential_confirmed(self, edge_scope: Iterable[EdgeKey | str]) -> bool:
        """Return the CGF bind predicate over a scoped essential edge set."""

        for key in edge_scope:
            normalized = _normalize_edge_key(key)
            edge = self.essential_edges.get(normalized)
            if edge is None or edge.status != "confirmed":
                return False
        return True

    def denominator_counts(self) -> dict[str, dict[str, int]]:
        """Return total and status counts by modality."""

        counters: dict[str, Counter[str]] = defaultdict(Counter)
        for edge in self.essential_edges.values():
            counters[edge.modality]["total"] += 1
            counters[edge.modality][edge.status] += 1
        return {
            modality: dict(sorted(counter.items()))
            for modality, counter in sorted(counters.items())
        }

    def edge_content_hashes(
        self,
        edge_scope: Iterable[EdgeKey | str],
    ) -> dict[str, str]:
        """Return content hashes for a certificate edge scope."""

        hashes: dict[str, str] = {}
        for key in edge_scope:
            normalized = _normalize_edge_key(key)
            edge = self.essential_edges.get(normalized)
            if edge is None:
                hashes[_edge_key_text(normalized)] = out_of_scope_edge(normalized).content_hash
            else:
                hashes[_edge_key_text(normalized)] = edge.content_hash
        return hashes


@dataclass(frozen=True)
class GroundingCertificateReference:
    """Minimal certificate reference envelope consumed by epoch staling."""

    certificate_id: str
    reference_epoch: str
    reference_hash: str
    edge_scope_hashes: Mapping[str, str]


@dataclass(frozen=True)
class CertificateStalenessDecision:
    """Result of comparing a certificate against a current credal reference."""

    status: Literal["current", "stale", "revalidation_required"]
    reasons: tuple[str, ...]
    stale_edge_keys: tuple[str, ...] = ()


@dataclass(frozen=True)
class GroundingBackendAvailability:
    """Content-addressed availability record for CGF grounding backends."""

    schema_version: str
    solver: Mapping[str, Any]
    milp_fallback: Mapping[str, Any]
    sparse: Mapping[str, Any]
    ann: Mapping[str, Any]
    dense: Mapping[str, Any]
    numeric_scaling: str
    required_backend_status: Literal["available", "unavailable"]
    content_hash: str

    def to_payload(self) -> dict[str, Any]:
        """Return a stable JSON payload."""

        return {
            "ann": _json_ready(self.ann),
            "content_hash": self.content_hash,
            "dense": _json_ready(self.dense),
            "milp_fallback": _json_ready(self.milp_fallback),
            "numeric_scaling": self.numeric_scaling,
            "required_backend_status": self.required_backend_status,
            "schema_version": self.schema_version,
            "solver": _json_ready(self.solver),
            "sparse": _json_ready(self.sparse),
        }


def build_credal_reference(
    repo_root: Path,
    *,
    as_of: str = DEFAULT_REFERENCE_AS_OF,
    world_model_record: WorldModelRecord | None = None,
) -> CredalReference:
    """Build the full K_ref view from real L2, L3, L6, and WMR owners."""

    root = repo_root.resolve()
    world_record = world_model_record or _production_world_model_record(root.as_posix())
    edge_index: dict[EdgeKey, CredalReferenceEdge] = {}
    for edge in _iter_l2_edges(root):
        edge_index[edge.key] = edge
    for edge in _iter_l3_edges(root, as_of=as_of):
        edge_index[edge.key] = edge
    for edge in _iter_l6_edges(root, world_model_record=world_record):
        edge_index[edge.key] = edge
    for edge in _iter_wmr_edges(world_record):
        edge_index[edge.key] = edge

    component_versions = _component_versions(edge_index, world_model_record=world_record)
    reference_hash = _reference_hash(
        component_versions=component_versions,
        edge_index=edge_index,
        as_of=as_of,
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of=as_of,
        component_versions=component_versions,
        essential_edges=edge_index,
    )


def reference_lift(
    reference: CredalReference,
    edge_scope: Iterable[EdgeKey | str],
) -> dict[str, dict[str, Any]]:
    """Return the scoped symbolic reference lift used by CGF relation lifting."""

    return reference.reference_lift(edge_scope)


def all_essential_confirmed(
    reference: CredalReference,
    edge_scope: Iterable[EdgeKey | str],
) -> bool:
    """Return whether every scoped essential edge is confirmed."""

    return reference.all_essential_confirmed(edge_scope)


def bind_grounding_certificate_reference(
    reference: CredalReference,
    *,
    certificate_id: str,
    edge_scope: Iterable[EdgeKey | str],
) -> GroundingCertificateReference:
    """Create the epoch/hash binding a GroundingCertificate would carry."""

    return GroundingCertificateReference(
        certificate_id=certificate_id,
        reference_epoch=reference.reference_epoch,
        reference_hash=reference.reference_hash,
        edge_scope_hashes=reference.edge_content_hashes(edge_scope),
    )


def reference_certificate_staleness(
    certificate: GroundingCertificateReference,
    current_reference: CredalReference,
) -> CertificateStalenessDecision:
    """Fail closed when a certificate was computed under an older K_ref epoch."""

    reasons: list[str] = []
    stale_edges: list[str] = []
    if certificate.reference_epoch != current_reference.reference_epoch:
        reasons.append("reference_epoch_changed")
    if certificate.reference_hash != current_reference.reference_hash:
        reasons.append("reference_hash_changed")
    for key_text, old_hash in sorted(certificate.edge_scope_hashes.items()):
        edge = current_reference.essential_edges.get(_normalize_edge_key(key_text))
        new_hash = edge.content_hash if edge else out_of_scope_edge(
            _normalize_edge_key(key_text)
        ).content_hash
        if new_hash != old_hash:
            stale_edges.append(key_text)
    if stale_edges:
        reasons.append("scoped_edge_hash_changed")
    return CertificateStalenessDecision(
        status="current" if not reasons else "stale",
        reasons=tuple(reasons),
        stale_edge_keys=tuple(stale_edges),
    )


def replace_reference_edge(
    reference: CredalReference,
    edge: CredalReferenceEdge,
) -> CredalReference:
    """Return a new K_ref epoch with one repaired/revised edge."""

    updated = dict(reference.essential_edges)
    updated[edge.key] = edge.with_content_hash()
    component_versions = _component_versions(
        updated,
        world_model_record_hash=reference.component_versions["WMR"],
    )
    reference_hash = _reference_hash(
        component_versions=component_versions,
        edge_index=updated,
        as_of=reference.as_of,
    )
    return CredalReference(
        schema_version=reference.schema_version,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of=reference.as_of,
        component_versions=component_versions,
        essential_edges=updated,
    )


def derive_variable_alignment_edge(
    row: Mapping[str, Any],
    *,
    provenance_version: str = "in_memory_free_grow_probe",
) -> CredalReferenceEdge:
    """Derive status for one L2 variable-alignment row from row signals."""

    synonym = str(row.get("synonym") or "").strip()
    canonical = str(row.get("canonical_name") or "").strip()
    confidence = _float(row.get("confidence"), default=0.0)
    approved = bool(row.get("approved"))
    edge_id = f"{synonym}->{canonical}"
    provenance = {
        "owner": "L2",
        "source": "ac_skg_variable_synonyms",
        "version": provenance_version,
        "signals": {
            "approved": approved,
            "confidence": confidence,
            "method": str(row.get("method") or ""),
        },
    }
    if not synonym or not canonical:
        return _edge(
            "L2_VARIABLE_ALIGNMENT",
            edge_id,
            "incomplete",
            _incomplete_completions("alignment_endpoint_missing"),
            provenance,
        )
    if approved and confidence >= 0.8:
        return _confirmed_edge(
            "L2_VARIABLE_ALIGNMENT",
            edge_id,
            {"synonym": synonym, "canonical_name": canonical},
            provenance,
        )
    if confidence >= 0.55:
        return _edge(
            "L2_VARIABLE_ALIGNMENT",
            edge_id,
            "contested",
            (
                AdmissibleCompletion(
                    "alternative",
                    {"synonym": synonym, "canonical_name": canonical},
                    "alignment_candidate_supported",
                ),
                AdmissibleCompletion(
                    "may_not_exist",
                    {"synonym": synonym, "canonical_name": canonical},
                    "alignment_not_owner_approved",
                ),
            ),
            provenance,
        )
    return _edge(
        "L2_VARIABLE_ALIGNMENT",
        edge_id,
        "incomplete",
        _incomplete_completions("alignment_low_confidence_or_unapproved"),
        provenance,
    )


def derive_data_forge_variable_alignment_edge(
    row: Mapping[str, Any],
    *,
    variable_names: set[str],
    provenance_version: str,
) -> CredalReferenceEdge:
    """Derive status for one Data Forge raw-to-canonical variable alignment."""

    dataset_id = str(row.get("dataset_id") or "").strip()
    raw_variable = str(row.get("raw_variable") or "").strip()
    canonical = str(row.get("canonical_var") or "").strip()
    method = str(row.get("method") or "").strip()
    confidence = _float(row.get("confidence"), default=0.0)
    is_proxy = bool(row.get("is_proxy"))
    proxy_penalty = _float(row.get("proxy_penalty"), default=0.0)
    edge_id = f"{dataset_id}:{raw_variable}->{canonical}"
    value = {
        "canonical_var": canonical,
        "dataset_id": dataset_id,
        "is_proxy": is_proxy,
        "raw_variable": raw_variable,
    }
    provenance = {
        "owner": "L2/DataForge",
        "source": "ds_variable_alignments",
        "version": provenance_version,
        "signals": {
            "confidence": confidence,
            "evidence": str(row.get("evidence") or ""),
            "is_proxy": is_proxy,
            "method": method,
            "proxy_penalty": proxy_penalty,
        },
    }
    if not dataset_id or not raw_variable or not canonical:
        return _edge(
            "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
            edge_id,
            "incomplete",
            _incomplete_completions("data_forge_alignment_endpoint_missing"),
            provenance,
        )
    if canonical not in variable_names:
        return _edge(
            "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
            edge_id,
            "incomplete",
            _incomplete_completions("data_forge_alignment_canonical_not_in_l2"),
            provenance,
        )
    if confidence >= 0.8 and not is_proxy and proxy_penalty <= 0.0:
        return _confirmed_edge(
            "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
            edge_id,
            value,
            provenance,
        )
    if confidence >= 0.55:
        return _edge(
            "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
            edge_id,
            "contested",
            (
                AdmissibleCompletion(
                    "alternative",
                    value,
                    "data_forge_alignment_candidate_supported",
                ),
                AdmissibleCompletion(
                    "may_not_exist",
                    value,
                    "data_forge_alignment_proxy_or_not_decisive",
                ),
            ),
            provenance,
        )
    return _edge(
        "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
        edge_id,
        "incomplete",
        _incomplete_completions("data_forge_alignment_low_confidence"),
        provenance,
    )


def out_of_scope_edge(
    key: EdgeKey,
    *,
    reason: str = "edge_not_in_scope",
) -> CredalReferenceEdge:
    """Build a fail-closed synthetic edge for non-existent reference queries."""

    return _edge(
        key[0],
        key[1],
        "out_of_scope",
        (AdmissibleCompletion("excluded", {"edge_key": _edge_key_text(key)}, reason),),
        {"owner": "credal_reference_view", "source": "query_scope"},
    )


def build_grounding_backend_availability() -> GroundingBackendAvailability:
    """Build the content-addressed backend availability gate record."""

    solver = _ortools_cp_sat_status()
    milp = _scipy_milp_status()
    sparse = _duckdb_fts_status()
    ann = _hnswlib_status()
    dense = {
        "status": "deferred",
        "reason": "no local model; gateway /embeddings untested",
        "inclusion_criterion": (
            "enable when CG1 first-pass FTS+alignment recall leaves a measured "
            "semantic-analog tail"
        ),
    }
    fields = {
        "ann": ann,
        "dense": dense,
        "milp_fallback": milp,
        "numeric_scaling": NUMERIC_SCALING,
        "required_backend_status": "available" if solver.get("available") else "unavailable",
        "schema_version": GROUNDING_BACKEND_AVAILABILITY_SCHEMA_VERSION,
        "solver": solver,
        "sparse": sparse,
    }
    return GroundingBackendAvailability(
        **fields,
        content_hash=gy_content_hash(fields),
    )


def essential_edge_scope_definition() -> dict[str, Any]:
    """Return the explicit CG0 essential-edge scope criterion and decisions."""

    return _json_ready(
        {
            "criterion": ESSENTIAL_EDGE_SCOPE_CRITERION,
            "included_edge_classes": list(_INCLUDED_EDGE_CLASSES),
            "excluded_edge_classes": list(_EXCLUDED_EDGE_CLASSES),
        }
    )


def edge_payload_sample(
    reference: CredalReference,
    *,
    statuses: Sequence[str] = ("contested", "deprecated", "incomplete"),
    limit_per_status: int = 1,
) -> dict[str, list[dict[str, Any]]]:
    """Return small evidence samples for contract artifacts."""

    samples: dict[str, list[dict[str, Any]]] = {status: [] for status in statuses}
    for edge in sorted(reference.essential_edges.values(), key=lambda item: item.key):
        if edge.status not in samples:
            continue
        if len(samples[edge.status]) >= limit_per_status:
            continue
        samples[edge.status].append(edge.to_payload())
        if all(len(items) >= limit_per_status for items in samples.values()):
            break
    return samples


def _iter_l2_edges(repo_root: Path) -> Iterable[CredalReferenceEdge]:
    db_path = repo_root / DEFAULT_L2_SCHOLAR_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        version = str(con.execute("SELECT MAX(version_id) FROM ac_skg_versions").fetchone()[0])
        variables = con.execute(
            """
            SELECT canonical_name, approved_canonical_name, is_approved_canonical,
                   resolution_method, resolution_confidence, mention_count,
                   parent_name, approved_parent_name
            FROM ac_skg_variables
            ORDER BY canonical_name
            """
        ).fetchall()
        variable_names = {str(row[0]) for row in variables if row[0]}
        approved_variables = {str(row[0]) for row in variables if row[0] and bool(row[2])}
        for row in variables:
            yield _derive_l2_variable_edge(row, version=version)
        for row in variables:
            parent_edge = _derive_l2_variable_hierarchy_edge(
                row,
                version=version,
                variable_names=variable_names,
                approved_variables=approved_variables,
            )
            if parent_edge is not None:
                yield parent_edge

        for row in con.execute(
            """
            SELECT synonym, canonical_name, method, confidence, approved
            FROM ac_skg_variable_synonyms
            ORDER BY synonym, canonical_name
            """
        ).fetchall():
            yield derive_variable_alignment_edge(
                {
                    "approved": row[4],
                    "canonical_name": row[1],
                    "confidence": row[3],
                    "method": row[2],
                    "synonym": row[0],
                },
                provenance_version=version,
            )

        yield from _iter_data_forge_variable_alignment_edges(
            repo_root,
            variable_names=variable_names,
        )

        contested_edges, contested_claims = _l2_contested_memberships(con)
        for row in con.execute(
            """
            SELECT edge_id, src, dst, direction, n_articles, evidence_strength,
                   confidence, candidate_layer, quality_signals_json
            FROM ac_skg_edges
            ORDER BY edge_id
            """
        ).fetchall():
            yield _derive_l2_causal_edge(
                row,
                version=version,
                variable_names=variable_names,
                approved_variables=approved_variables,
                contested_edges=contested_edges,
            )

        for row in con.execute(
            """
            SELECT family_edge_id, src_family, dst_family, direction, n_articles,
                   n_claims, evidence_strength, confidence, direction_histogram_json,
                   design_tier_histogram_json, candidate_layer, quality_signals_json
            FROM ac_skg_family_edges
            ORDER BY family_edge_id
            """
        ).fetchall():
            yield _derive_l2_family_edge(
                row,
                version=version,
                variable_names=variable_names,
                contested_edges=contested_edges,
            )

        for row in con.execute(
            """
            SELECT moderation_id, base_cause, base_effect, moderator, base_claim_id,
                   direction_of_mod, interaction_coeff, interaction_pvalue,
                   evidence_count, confidence, match_quality, alignment_source,
                   source_refs, skg_version
            FROM ac_skg_moderation_edges
            ORDER BY moderation_id
            """
        ).fetchall():
            yield _derive_l2_moderation_edge(
                row,
                version=version,
                variable_names=variable_names,
            )

        for row in con.execute(
            """
            SELECT id, cause, effect, direction, strength, design_family_hint,
                   claim_extraction_confidence, strong_design_evidence,
                   design_quality_tier, publish_blockers, candidate_layer, trust_score
            FROM ac_causal_claims
            ORDER BY id
            """
        ).fetchall():
            yield _derive_l2_causal_claim(
                row,
                version=version,
                variable_names=variable_names,
                contested_claims=contested_claims,
            )

        for row in con.execute(
            """
            SELECT contested_edge_id, src_family, dst_family, dominant_direction,
                   resolution_status, runtime_support, confidence, positive_weight,
                   negative_weight, mixed_weight, direction_histogram_json,
                   quality_signals_json
            FROM ac_skg_contested_edges
            ORDER BY contested_edge_id
            """
        ).fetchall():
            yield _derive_l2_contested_edge(row, version=version)
    finally:
        con.close()


def _derive_l2_variable_edge(row: Sequence[Any], *, version: str) -> CredalReferenceEdge:
    name = str(row[0] or "").strip()
    approved_name = str(row[1] or "").strip()
    approved = bool(row[2])
    confidence = _float(row[4], default=0.0)
    mention_count = int(row[5] or 0)
    provenance = {
        "owner": "L2",
        "source": "ac_skg_variables",
        "version": version,
        "signals": {
            "approved": approved,
            "approved_canonical_name": approved_name,
            "mention_count": mention_count,
            "resolution_confidence": confidence,
            "resolution_method": str(row[3] or ""),
        },
    }
    if not name:
        return _edge(
            "L2_CANONICAL_VARIABLE",
            "missing",
            "incomplete",
            _incomplete_completions("canonical_variable_name_missing"),
            provenance,
        )
    if approved and confidence >= 0.65:
        return _confirmed_edge(
            "L2_CANONICAL_VARIABLE",
            name,
            {"canonical_name": name, "approved_canonical_name": approved_name or name},
            provenance,
        )
    if approved or approved_name or confidence >= 0.4 or mention_count >= 3:
        return _edge(
            "L2_CANONICAL_VARIABLE",
            name,
            "contested",
            (
                AdmissibleCompletion(
                    "alternative",
                    {"canonical_name": approved_name or name},
                    "candidate_canonical_identity",
                ),
                AdmissibleCompletion(
                    "may_not_exist",
                    {"canonical_name": name},
                    "canonical_identity_not_approved_or_low_confidence",
                ),
            ),
            provenance,
        )
    return _edge(
        "L2_CANONICAL_VARIABLE",
        name,
        "incomplete",
        _incomplete_completions("canonical_variable_unresolved"),
        provenance,
    )


def _derive_l2_variable_hierarchy_edge(
    row: Sequence[Any],
    *,
    version: str,
    variable_names: set[str],
    approved_variables: set[str],
) -> CredalReferenceEdge | None:
    child = str(row[0] or "").strip()
    parent = str((row[6] if len(row) > 6 else "") or "").strip()
    approved_parent = str((row[7] if len(row) > 7 else "") or "").strip()
    target_parent = approved_parent or parent
    if not parent and not approved_parent:
        return None
    confidence = _float(row[4], default=0.0)
    child_approved = bool(row[2])
    value = {
        "approved_parent_name": approved_parent,
        "child": child,
        "parent": target_parent,
        "raw_parent_name": parent,
    }
    provenance = {
        "owner": "L2",
        "source": "ac_skg_variables",
        "version": version,
        "signals": {
            "approved_parent_name": approved_parent,
            "child_approved": child_approved,
            "parent_in_l2": target_parent in variable_names,
            "raw_parent_name": parent,
            "resolution_confidence": confidence,
        },
    }
    edge_id = f"{child}->{target_parent or parent}"
    if not child or not target_parent:
        return _edge(
            "L2_VARIABLE_HIERARCHY",
            edge_id,
            "incomplete",
            _incomplete_completions("variable_hierarchy_endpoint_missing"),
            provenance,
        )
    if target_parent not in variable_names:
        return _edge(
            "L2_VARIABLE_HIERARCHY",
            edge_id,
            "incomplete",
            _incomplete_completions("variable_hierarchy_parent_not_in_l2"),
            provenance,
        )
    if (
        child in approved_variables
        and target_parent in approved_variables
        and confidence >= 0.65
    ):
        return _confirmed_edge("L2_VARIABLE_HIERARCHY", edge_id, value, provenance)
    if child_approved or approved_parent or confidence >= 0.4:
        return _edge(
            "L2_VARIABLE_HIERARCHY",
            edge_id,
            "contested",
            (
                AdmissibleCompletion(
                    "alternative",
                    value,
                    "variable_hierarchy_candidate_supported",
                ),
                AdmissibleCompletion(
                    "may_not_exist",
                    value,
                    "variable_hierarchy_not_decisive",
                ),
            ),
            provenance,
        )
    return _edge(
        "L2_VARIABLE_HIERARCHY",
        edge_id,
        "incomplete",
        _incomplete_completions("variable_hierarchy_unresolved"),
        provenance,
    )


def _iter_data_forge_variable_alignment_edges(
    repo_root: Path,
    *,
    variable_names: set[str],
) -> Iterable[CredalReferenceEdge]:
    db_path = repo_root / DEFAULT_DATA_FORGE_CATALOG_PATH
    if not db_path.is_file():
        return
    version = _data_forge_catalog_version(db_path)
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT dataset_id, raw_variable, canonical_var, method, confidence,
                   evidence, is_proxy, proxy_penalty
            FROM ds_variable_alignments
            ORDER BY dataset_id, raw_variable, canonical_var
            """
        ).fetchall()
        for row in rows:
            yield derive_data_forge_variable_alignment_edge(
                {
                    "canonical_var": row[2],
                    "confidence": row[4],
                    "dataset_id": row[0],
                    "evidence": row[5],
                    "is_proxy": row[6],
                    "method": row[3],
                    "proxy_penalty": row[7],
                    "raw_variable": row[1],
                },
                variable_names=variable_names,
                provenance_version=version,
            )
    finally:
        con.close()


def _derive_l2_causal_edge(
    row: Sequence[Any],
    *,
    version: str,
    variable_names: set[str],
    approved_variables: set[str],
    contested_edges: Mapping[str, Mapping[str, Any]],
) -> CredalReferenceEdge:
    edge_id, src, dst, direction, n_articles, strength, confidence, layer, quality_json = row
    edge_text = str(edge_id or "").strip()
    src_text = str(src or "").strip()
    dst_text = str(dst or "").strip()
    quality = _json_object(quality_json)
    blockers = _string_list(quality.get("publish_blockers"))
    strong = _json_object(quality.get("strong_design_evidence"))
    tiers = [
        int(item)
        for item in _string_list(quality.get("design_quality_tiers"))
        if str(item).isdigit()
    ]
    provenance = {
        "owner": "L2",
        "source": "ac_skg_edges",
        "version": version,
        "signals": {
            "candidate_layer": str(layer or ""),
            "confidence": _float(confidence),
            "design_quality_tiers": tiers,
            "edge_in_contested_membership": edge_text in contested_edges,
            "evidence_strength": str(strength or ""),
            "n_articles": int(n_articles or 0),
            "publish_blockers": blockers,
            "strong_design_evidence": strong,
        },
    }
    base_value = {"direction": str(direction or ""), "dst": dst_text, "src": src_text}
    if edge_text in contested_edges:
        return _edge(
            "L2_CAUSAL_EDGE",
            edge_text,
            "contested",
            _l2_direction_alternatives(contested_edges[edge_text], fallback=base_value),
            provenance,
        )
    if (
        not edge_text
        or not src_text
        or not dst_text
        or src_text not in variable_names
        or dst_text not in variable_names
    ):
        return _edge(
            "L2_CAUSAL_EDGE",
            edge_text or f"{src_text}->{dst_text}",
            "incomplete",
            _incomplete_completions("causal_edge_endpoint_unresolved"),
            provenance,
        )
    if src_text not in approved_variables or dst_text not in approved_variables:
        return _edge(
            "L2_CAUSAL_EDGE",
            edge_text,
            "incomplete",
            _incomplete_completions("causal_edge_endpoint_not_approved"),
            provenance,
        )
    confidence_value = _float(confidence)
    if confidence_value < 0.35:
        return _edge(
            "L2_CAUSAL_EDGE",
            edge_text,
            "incomplete",
            _incomplete_completions("causal_edge_low_confidence"),
            provenance,
        )
    if blockers or confidence_value < 0.75 or strong.get("any") is False:
        return _edge(
            "L2_CAUSAL_EDGE",
            edge_text,
            "contested",
            (
                AdmissibleCompletion("alternative", base_value, "edge_candidate_supported"),
                AdmissibleCompletion("may_not_exist", base_value, "edge_quality_not_decisive"),
            ),
            provenance,
        )
    return _confirmed_edge("L2_CAUSAL_EDGE", edge_text, base_value, provenance)


def _derive_l2_family_edge(
    row: Sequence[Any],
    *,
    version: str,
    variable_names: set[str],
    contested_edges: Mapping[str, Mapping[str, Any]],
) -> CredalReferenceEdge:
    (
        family_edge_id,
        src_family,
        dst_family,
        direction,
        n_articles,
        n_claims,
        strength,
        confidence,
        _histogram_json,
        tier_histogram_json,
        layer,
        quality_json,
    ) = row
    edge_text = str(family_edge_id or "").strip()
    src_text = str(src_family or "").strip()
    dst_text = str(dst_family or "").strip()
    quality = _json_object(quality_json)
    direction_agreement = _float(quality.get("direction_agreement"), default=0.0)
    conflict_flag = bool(quality.get("conflict_flag"))
    provenance = {
        "owner": "L2",
        "source": "ac_skg_family_edges",
        "version": version,
        "signals": {
            "candidate_layer": str(layer or ""),
            "confidence": _float(confidence),
            "design_tier_histogram": _json_object(tier_histogram_json),
            "direction_agreement": direction_agreement,
            "edge_in_contested_membership": edge_text in contested_edges,
            "evidence_strength": str(strength or ""),
            "n_articles": int(n_articles or 0),
            "n_claims": int(n_claims or 0),
            "quality_signals": quality,
        },
    }
    value = {"direction": str(direction or ""), "dst": dst_text, "src": src_text}
    if edge_text in contested_edges:
        return _edge(
            "L2_FAMILY_EDGE",
            edge_text,
            "contested",
            _l2_direction_alternatives(
                contested_edges[edge_text],
                fallback=value,
            ),
            provenance,
        )
    if (
        not edge_text
        or not src_text
        or not dst_text
        or src_text not in variable_names
        or dst_text not in variable_names
    ):
        return _edge(
            "L2_FAMILY_EDGE",
            edge_text or f"{src_text}->{dst_text}",
            "incomplete",
            _incomplete_completions("family_edge_endpoint_unresolved"),
            provenance,
        )
    confidence_value = _float(confidence)
    if confidence_value < 0.35:
        return _edge(
            "L2_FAMILY_EDGE",
            edge_text,
            "incomplete",
            _incomplete_completions("family_edge_low_confidence"),
            provenance,
        )
    if (
        conflict_flag
        or confidence_value < 0.75
        or direction_agreement < 0.85
        or int(n_claims or 0) < 2
    ):
        return _edge(
            "L2_FAMILY_EDGE",
            edge_text,
            "contested",
            (
                AdmissibleCompletion("alternative", value, "family_edge_candidate_supported"),
                AdmissibleCompletion("may_not_exist", value, "family_edge_quality_not_decisive"),
            ),
            provenance,
        )
    return _confirmed_edge("L2_FAMILY_EDGE", edge_text, value, provenance)


def _derive_l2_moderation_edge(
    row: Sequence[Any],
    *,
    version: str,
    variable_names: set[str],
) -> CredalReferenceEdge:
    (
        moderation_id,
        base_cause,
        base_effect,
        moderator,
        base_claim_id,
        direction_of_mod,
        interaction_coeff,
        interaction_pvalue,
        evidence_count,
        confidence,
        match_quality,
        alignment_source,
        source_refs,
        skg_version,
    ) = row
    edge_text = str(moderation_id or "").strip()
    cause_text = str(base_cause or "").strip()
    effect_text = str(base_effect or "").strip()
    moderator_text = str(moderator or "").strip()
    direction_text = str(direction_of_mod or "").strip()
    pvalue = _float(interaction_pvalue, default=1.0)
    coeff = _float(interaction_coeff, default=0.0)
    confidence_value = _float(confidence)
    value = {
        "base_cause": cause_text,
        "base_claim_id": str(base_claim_id or ""),
        "base_effect": effect_text,
        "direction_of_mod": direction_text,
        "interaction_coeff": coeff,
        "moderator": moderator_text,
    }
    provenance = {
        "owner": "L2",
        "source": "ac_skg_moderation_edges",
        "version": version,
        "signals": {
            "alignment_source": str(alignment_source or ""),
            "confidence": confidence_value,
            "evidence_count": int(evidence_count or 0),
            "interaction_pvalue": pvalue,
            "match_quality": str(match_quality or ""),
            "skg_version": int(skg_version or 0),
            "source_refs": _json_list(source_refs),
        },
    }
    if (
        not edge_text
        or not cause_text
        or not effect_text
        or not moderator_text
        or cause_text not in variable_names
        or effect_text not in variable_names
        or moderator_text not in variable_names
    ):
        return _edge(
            "L2_MODERATION_EDGE",
            edge_text or f"{cause_text}->{effect_text}|{moderator_text}",
            "incomplete",
            _incomplete_completions("moderation_edge_endpoint_unresolved"),
            provenance,
        )
    if confidence_value < 0.35:
        return _edge(
            "L2_MODERATION_EDGE",
            edge_text,
            "incomplete",
            _incomplete_completions("moderation_edge_low_confidence"),
            provenance,
        )
    if (
        direction_text.casefold() in {"", "null", "unknown"}
        or interaction_coeff is None
        or interaction_pvalue is None
        or pvalue > 0.1
        or confidence_value < 0.75
        or str(match_quality or "").casefold() != "exact_claim_ref"
    ):
        return _edge(
            "L2_MODERATION_EDGE",
            edge_text,
            "contested",
            (
                AdmissibleCompletion(
                    "alternative",
                    value,
                    "moderation_effect_candidate_supported",
                ),
                AdmissibleCompletion(
                    "may_not_exist",
                    value,
                    "moderation_effect_not_decisive",
                ),
            ),
            provenance,
        )
    return _confirmed_edge("L2_MODERATION_EDGE", edge_text, value, provenance)


def _derive_l2_causal_claim(
    row: Sequence[Any],
    *,
    version: str,
    variable_names: set[str],
    contested_claims: set[str],
) -> CredalReferenceEdge:
    (
        claim_id,
        cause,
        effect,
        direction,
        strength,
        design_family,
        extraction_confidence,
        strong_design,
        design_tier,
        blockers,
        layer,
        trust_score,
    ) = row
    claim = str(claim_id or "").strip()
    cause_text = str(cause or "").strip()
    effect_text = str(effect or "").strip()
    blocker_list = _split_blockers(blockers)
    trust = _float(trust_score)
    tier = int(design_tier or 99)
    provenance = {
        "owner": "L2",
        "source": "ac_causal_claims",
        "version": version,
        "signals": {
            "candidate_layer": str(layer or ""),
            "claim_in_contested_membership": claim in contested_claims,
            "design_family_hint": str(design_family or ""),
            "design_quality_tier": tier,
            "extraction_confidence": _float(extraction_confidence),
            "publish_blockers": blocker_list,
            "strong_design_evidence": bool(strong_design),
            "trust_score": trust,
        },
    }
    value = {
        "cause": cause_text,
        "direction": str(direction or ""),
        "effect": effect_text,
        "strength": str(strength or ""),
    }
    if claim in contested_claims:
        return _edge(
            "L2_CAUSAL_CLAIM",
            claim,
            "contested",
            (
                AdmissibleCompletion("alternative", value, "claim_contested_membership"),
                AdmissibleCompletion("may_not_exist", value, "conflicting_claim_refs"),
            ),
            provenance,
        )
    if not claim or not cause_text or not effect_text:
        return _edge(
            "L2_CAUSAL_CLAIM",
            claim or f"{cause_text}->{effect_text}",
            "incomplete",
            _incomplete_completions("causal_claim_endpoint_missing"),
            provenance,
        )
    if cause_text not in variable_names or effect_text not in variable_names:
        return _edge(
            "L2_CAUSAL_CLAIM",
            claim,
            "incomplete",
            _incomplete_completions("causal_claim_endpoint_unresolved"),
            provenance,
        )
    if trust < 0.35:
        return _edge(
            "L2_CAUSAL_CLAIM",
            claim,
            "incomplete",
            _incomplete_completions("causal_claim_low_trust"),
            provenance,
        )
    if blocker_list or trust < 0.65 or tier > 3 or not bool(strong_design):
        return _edge(
            "L2_CAUSAL_CLAIM",
            claim,
            "contested",
            (
                AdmissibleCompletion("alternative", value, "claim_candidate_supported"),
                AdmissibleCompletion("may_not_exist", value, "claim_quality_not_decisive"),
            ),
            provenance,
        )
    return _confirmed_edge("L2_CAUSAL_CLAIM", claim, value, provenance)


def _derive_l2_contested_edge(row: Sequence[Any], *, version: str) -> CredalReferenceEdge:
    (
        contested_id,
        src_family,
        dst_family,
        dominant_direction,
        resolution_status,
        runtime_support,
        confidence,
        positive_weight,
        negative_weight,
        mixed_weight,
        histogram_json,
        quality_json,
    ) = row
    provenance = {
        "owner": "L2",
        "source": "ac_skg_contested_edges",
        "version": version,
        "signals": {
            "confidence": _float(confidence),
            "dominant_direction": str(dominant_direction or ""),
            "negative_weight": _float(negative_weight),
            "positive_weight": _float(positive_weight),
            "mixed_weight": _float(mixed_weight),
            "resolution_status": str(resolution_status or ""),
            "runtime_support": str(runtime_support or ""),
            "quality_signals": _json_object(quality_json),
        },
    }
    fallback = {
        "direction": str(dominant_direction or ""),
        "dst": str(dst_family or ""),
        "src": str(src_family or ""),
    }
    status: CredalReferenceStatus = (
        "confirmed" if str(resolution_status or "").casefold() == "resolved" else "contested"
    )
    completions = (
        (AdmissibleCompletion("fixed", fallback, "contested_edge_resolved"),)
        if status == "confirmed"
        else _l2_direction_alternatives(
            {"direction_histogram_json": histogram_json},
            fallback=fallback,
        )
    )
    return _edge(
        "L2_CONTESTED_EDGE",
        str(contested_id or ""),
        status,
        completions,
        provenance,
    )


def _l2_contested_memberships(
    con: duckdb.DuckDBPyConnection,
) -> tuple[dict[str, Mapping[str, Any]], set[str]]:
    edge_membership: dict[str, Mapping[str, Any]] = {}
    claim_membership: set[str] = set()
    for row in con.execute(
        """
        SELECT contested_edge_id, claim_refs, direction_histogram_json,
               quality_signals_json
        FROM ac_skg_contested_edges
        """
    ).fetchall():
        contested_id = str(row[0] or "")
        for claim_id in _json_list(row[1]):
            claim_membership.add(str(claim_id))
        quality = _json_object(row[3])
        for field_name in ("exact_edge_ids", "family_edge_ids"):
            for edge_id in _json_list(quality.get(field_name)):
                edge_membership[str(edge_id)] = {
                    "contested_edge_id": contested_id,
                    "direction_histogram_json": row[2],
                    "quality_signals": quality,
                }
    return edge_membership, claim_membership


def _iter_l3_edges(repo_root: Path, *, as_of: str) -> Iterable[CredalReferenceEdge]:
    db_path = repo_root / DEFAULT_L3_LEX_KG_PATH
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        version = str(
            con.execute("SELECT MAX(effective_from) FROM lex_amendments").fetchone()[0]
            or db_path.parent.name
        )
        threshold_rows = con.execute(
            """
            SELECT t.threshold_id, t.fact_id, t.metric, t.operator, t.value_decimal,
                   t.value_text, t.unit, t.applies_to,
                   f.doc_family_id, f.effective_from, f.effective_to,
                   f.temporal_state, f.temporal_resolution_status,
                   f.quality_band, f.gate_reason_codes
            FROM lex_rule_thresholds t
            LEFT JOIN lex_normative_ready_facts f ON t.fact_id = f.fact_id
            ORDER BY t.threshold_id
            """
        ).fetchall()
        next_threshold_starts = _next_starts_for_thresholds(threshold_rows)
        for row in threshold_rows:
            yield _derive_l3_threshold_edge(
                row,
                version=version,
                as_of=as_of,
                next_start=next_threshold_starts.get(str(row[0] or "")),
            )

        amendment_rows = con.execute(
            """
            SELECT amendment_id, amending_doc_id, amended_doc_id,
                   target_resolution_expected, amendment_type, target_anchor,
                   old_text_uk, new_text_uk, effective_from, confidence,
                   metadata
            FROM lex_amendments
            ORDER BY amendment_id
            """
        ).fetchall()
        next_amendment_starts = _next_starts_for_amendments(amendment_rows)
        for row in amendment_rows:
            yield _derive_l3_amendment_edge(
                row,
                version=version,
                as_of=as_of,
                next_start=next_amendment_starts.get(str(row[0] or "")),
            )

        for row in con.execute(
            """
            SELECT reference_edge_id, source_doc_id, source_doc_family_id,
                   source_anchor, target_doc_id, target_doc_family_id,
                   target_doc_reestr_code, target_doc_number, target_doc_type,
                   target_doc_date_acc, target_doc_status, target_anchor,
                   relation_type, matched_by, resolution_confidence,
                   resolution_status, version_id, metadata
            FROM lex_reference_edges
            ORDER BY reference_edge_id
            """
        ).fetchall():
            yield _derive_l3_reference_edge(row, version=version)
    finally:
        con.close()


def _derive_l3_threshold_edge(
    row: Sequence[Any],
    *,
    version: str,
    as_of: str,
    next_start: date | None,
) -> CredalReferenceEdge:
    (
        threshold_id,
        fact_id,
        metric,
        operator,
        value_decimal,
        value_text,
        unit,
        applies_to,
        doc_family_id,
        effective_from,
        effective_to,
        temporal_state,
        temporal_resolution_status,
        quality_band,
        gate_reason_codes,
    ) = row
    threshold = str(threshold_id or "").strip()
    as_of_date = _parse_date(as_of)
    start = _parse_date(effective_from)
    end = _parse_date(effective_to)
    provenance = {
        "owner": "L3",
        "source": "lex_rule_thresholds",
        "version": version,
        "signals": {
            "as_of": as_of,
            "doc_family_id": str(doc_family_id or ""),
            "effective_from": str(effective_from or ""),
            "effective_to": str(effective_to or ""),
            "gate_reason_codes": _split_blockers(gate_reason_codes),
            "next_effective_from": _date_text(next_start),
            "quality_band": str(quality_band or ""),
            "temporal_resolution_status": str(temporal_resolution_status or ""),
            "temporal_state": str(temporal_state or ""),
        },
    }
    value = {
        "applies_to": str(applies_to or ""),
        "fact_id": str(fact_id or ""),
        "metric": str(metric or ""),
        "operator": str(operator or ""),
        "unit": str(unit or ""),
        "value_decimal": str(value_decimal or ""),
        "value_text": str(value_text or ""),
    }
    if (
        not threshold
        or not metric
        or not operator
        or not (value_decimal or value_text)
        or not applies_to
    ):
        return _edge(
            "L3_RULE_THRESHOLD",
            threshold or str(fact_id or "missing_threshold"),
            "incomplete",
            _incomplete_completions("threshold_key_or_value_incomplete"),
            provenance,
            unit=str(unit or "") or None,
            scale=_threshold_scale(unit),
        )
    if as_of_date is None:
        status: CredalReferenceStatus = "incomplete"
        completions = _incomplete_completions("as_of_unparseable")
    elif start is not None and as_of_date < start:
        status = "out_of_scope"
        completions = (
            AdmissibleCompletion("excluded", value, "threshold_not_yet_effective_for_asof"),
        )
    elif (end is not None and as_of_date >= end) or (
        next_start is not None and as_of_date >= next_start
    ):
        status = "deprecated"
        completions = (
            AdmissibleCompletion("excluded", value, "threshold_superseded_or_expired"),
        )
    elif str(temporal_resolution_status or "").casefold() == "partial":
        status = "contested"
        completions = (
            AdmissibleCompletion("alternative", value, "threshold_temporal_partial"),
            AdmissibleCompletion("partial", value, "threshold_effective_window_partial"),
        )
    else:
        status = "confirmed"
        completions = (AdmissibleCompletion("fixed", value, "threshold_in_force"),)
    return _edge(
        "L3_RULE_THRESHOLD",
        threshold,
        status,
        completions,
        provenance,
        unit=str(unit or "") or None,
        scale=_threshold_scale(unit),
    )


def _derive_l3_amendment_edge(
    row: Sequence[Any],
    *,
    version: str,
    as_of: str,
    next_start: date | None,
) -> CredalReferenceEdge:
    (
        amendment_id,
        amending_doc_id,
        amended_doc_id,
        expected,
        amendment_type,
        target_anchor,
        old_text,
        new_text,
        effective_from,
        confidence,
        metadata,
    ) = row
    amendment = str(amendment_id or "").strip()
    as_of_date = _parse_date(as_of)
    start = _parse_date(effective_from)
    provenance = {
        "owner": "L3",
        "source": "lex_amendments",
        "version": version,
        "signals": {
            "as_of": as_of,
            "confidence": _float(confidence),
            "effective_from": str(effective_from or ""),
            "metadata": _json_object(metadata),
            "next_effective_from": _date_text(next_start),
            "target_resolution_expected": bool(expected),
        },
    }
    value = {
        "amended_doc_id": str(amended_doc_id or ""),
        "amending_doc_id": str(amending_doc_id or ""),
        "amendment_type": str(amendment_type or ""),
        "target_anchor": str(target_anchor or ""),
    }
    if not amendment or (bool(expected) and not amended_doc_id):
        return _edge(
            "L3_AMENDMENT",
            amendment or "missing_amendment",
            "incomplete",
            _incomplete_completions("amendment_target_resolution_missing"),
            provenance,
        )
    if start is None:
        return _edge(
            "L3_AMENDMENT",
            amendment,
            "incomplete",
            _incomplete_completions("amendment_effective_from_missing"),
            provenance,
        )
    if as_of_date is None:
        return _edge(
            "L3_AMENDMENT",
            amendment,
            "incomplete",
            _incomplete_completions("as_of_unparseable"),
            provenance,
        )
    if as_of_date < start:
        return _edge(
            "L3_AMENDMENT",
            amendment,
            "out_of_scope",
            (AdmissibleCompletion("excluded", value, "amendment_not_yet_effective_for_asof"),),
            provenance,
        )
    if next_start is not None and as_of_date >= next_start:
        return _edge(
            "L3_AMENDMENT",
            amendment,
            "deprecated",
            (AdmissibleCompletion("excluded", value, "amendment_superseded"),),
            provenance,
        )
    if _float(confidence) < 0.7:
        return _edge(
            "L3_AMENDMENT",
            amendment,
            "contested",
            (
                AdmissibleCompletion("alternative", value, "amendment_low_confidence"),
                AdmissibleCompletion(
                    "partial",
                    {
                        "new_text_present": bool(new_text),
                        "old_text_present": bool(old_text),
                    },
                    "amendment_text_partial",
                ),
            ),
            provenance,
        )
    return _confirmed_edge("L3_AMENDMENT", amendment, value, provenance)


def _derive_l3_reference_edge(row: Sequence[Any], *, version: str) -> CredalReferenceEdge:
    (
        reference_edge_id,
        source_doc_id,
        source_doc_family_id,
        source_anchor,
        target_doc_id,
        target_doc_family_id,
        target_doc_reestr_code,
        target_doc_number,
        target_doc_type,
        target_doc_date_acc,
        target_doc_status,
        target_anchor,
        relation_type,
        matched_by,
        resolution_confidence,
        resolution_status,
        version_id,
        metadata,
    ) = row
    edge_id = str(reference_edge_id or "").strip()
    source_doc = str(source_doc_id or "").strip()
    target_doc = str(target_doc_id or "").strip()
    target_family = str(target_doc_family_id or "").strip()
    relation = str(relation_type or "").strip()
    status_text = str(resolution_status or "").strip().casefold()
    confidence = _float(resolution_confidence)
    metadata_obj = _json_object(metadata)
    value = {
        "relation_type": relation,
        "source_anchor": str(source_anchor or ""),
        "source_doc_family_id": str(source_doc_family_id or ""),
        "source_doc_id": source_doc,
        "target_anchor": str(target_anchor or ""),
        "target_doc_family_id": target_family,
        "target_doc_id": target_doc,
        "target_doc_number": str(target_doc_number or ""),
        "target_doc_reestr_code": str(target_doc_reestr_code or ""),
        "target_doc_status": str(target_doc_status or ""),
        "target_doc_type": str(target_doc_type or ""),
    }
    provenance = {
        "owner": "L3",
        "source": "lex_reference_edges",
        "version": str(version_id or "") or version,
        "signals": {
            "matched_by": str(matched_by or ""),
            "metadata": metadata_obj,
            "resolution_confidence": confidence,
            "resolution_status": status_text,
            "target_doc_date_acc": str(target_doc_date_acc or ""),
        },
    }
    if not edge_id or not source_doc or not relation:
        return _edge(
            "L3_REFERENCE_EDGE",
            edge_id or f"{source_doc}->{target_doc or target_family}",
            "incomplete",
            _incomplete_completions("lex_reference_source_or_relation_missing"),
            provenance,
        )
    if not target_doc and not target_family:
        completion_kind: CompletionKind = "partial" if confidence >= 0.55 else "may_exist"
        return _edge(
            "L3_REFERENCE_EDGE",
            edge_id,
            "contested" if confidence >= 0.55 else "incomplete",
            (
                AdmissibleCompletion(
                    completion_kind,
                    value,
                    "lex_reference_target_partial",
                ),
                AdmissibleCompletion(
                    "may_not_exist",
                    value,
                    "lex_reference_target_unresolved",
                ),
            ),
            provenance,
        )
    if confidence < 0.35:
        return _edge(
            "L3_REFERENCE_EDGE",
            edge_id,
            "incomplete",
            _incomplete_completions("lex_reference_low_confidence"),
            provenance,
        )
    if status_text in {"resolved", "confirmed", "exact"} and confidence >= 0.75:
        return _confirmed_edge("L3_REFERENCE_EDGE", edge_id, value, provenance)
    return _edge(
        "L3_REFERENCE_EDGE",
        edge_id,
        "contested",
        (
            AdmissibleCompletion("alternative", value, "lex_reference_candidate_supported"),
            AdmissibleCompletion("partial", value, "lex_reference_resolution_partial"),
        ),
        provenance,
    )


def _next_starts_for_thresholds(rows: Sequence[Sequence[Any]]) -> dict[str, date]:
    grouped: dict[tuple[str, str, str, str], list[tuple[str, date]]] = defaultdict(list)
    for row in rows:
        threshold_id = str(row[0] or "")
        key = (
            str(row[8] or ""),
            str(row[2] or ""),
            str(row[6] or ""),
            str(row[7] or ""),
        )
        start = _parse_date(row[9])
        if threshold_id and start is not None:
            grouped[key].append((threshold_id, start))
    next_starts: dict[str, date] = {}
    for items in grouped.values():
        ordered = sorted(items, key=lambda item: item[1])
        for index, (threshold_id, start) in enumerate(ordered[:-1]):
            for _, candidate_start in ordered[index + 1 :]:
                if candidate_start > start:
                    next_starts[threshold_id] = candidate_start
                    break
    return next_starts


def _next_starts_for_amendments(rows: Sequence[Sequence[Any]]) -> dict[str, date]:
    grouped: dict[tuple[str, str], list[tuple[str, date]]] = defaultdict(list)
    for row in rows:
        amendment_id = str(row[0] or "")
        key = (str(row[2] or ""), str(row[5] or ""))
        start = _parse_date(row[8])
        if amendment_id and key[0] and start is not None:
            grouped[key].append((amendment_id, start))
    next_starts: dict[str, date] = {}
    for items in grouped.values():
        ordered = sorted(items, key=lambda item: item[1])
        for index, (amendment_id, start) in enumerate(ordered[:-1]):
            for _, candidate_start in ordered[index + 1 :]:
                if candidate_start > start:
                    next_starts[amendment_id] = candidate_start
                    break
    return next_starts


def _iter_l6_edges(
    repo_root: Path,
    *,
    world_model_record: WorldModelRecord,
) -> Iterable[CredalReferenceEdge]:
    bundle = load_l6_intervention_substrate(repo_root)
    lex_module = importlib.import_module("polisyos.lex.knowledge.store")
    lex_store = lex_module.LegalKnowledgeStore(
        repo_root / DEFAULT_L3_LEX_KG_PATH,
        (repo_root / DEFAULT_L3_LEX_KG_PATH).parent,
    )
    version = bundle.content_hash
    for knob_id, raw in sorted(bundle.knob_dictionary.items()):
        raw_knob = _mapping(raw)
        provenance = {
            "owner": "L6",
            "source": "intervention_knob_dictionary",
            "version": version,
            "signals": {"knob_id": knob_id, "raw_keys": sorted(raw_knob)},
        }
        if not raw_knob:
            yield _edge(
                "L6_KNOB_OPERATOR",
                str(knob_id),
                "incomplete",
                _incomplete_completions("knob_row_not_object"),
                provenance,
            )
            continue
        value = _representative_knob_value(raw_knob)
        try:
            resolved = resolve_intervention_lever(
                bundle,
                operator_kind=str(knob_id),
                parameter_value=value,
                world_model_record=world_model_record,
            )
        except InterventionSubstrateError as exc:
            yield _edge(
                "L6_KNOB_OPERATOR",
                str(knob_id),
                "incomplete",
                _incomplete_completions(exc.code),
                provenance,
            )
            yield _edge(
                "L6_KNOB_WORLD_SLOT",
                str(knob_id),
                "incomplete",
                _incomplete_completions(exc.code),
                provenance,
            )
            continue
        yield _confirmed_edge(
            "L6_KNOB_OPERATOR",
            str(knob_id),
            {
                "operator_kind": resolved.operator_kind,
                "parameter_domain": resolved.domain.model_dump(mode="json"),
            },
            provenance,
            unit=resolved.domain.unit,
        )
        yield _confirmed_edge(
            "L6_KNOB_WORLD_SLOT",
            str(knob_id),
            {
                "operator_kind": resolved.operator_kind,
                "target_world_slots": list(resolved.target_world_slots),
                "world_model_record_id": world_model_record.world_model_record_id,
            },
            provenance,
            unit=resolved.domain.unit,
        )

    for law_token, raw_map in sorted(bundle.lex_intervention_map.items()):
        knob_ids = _knob_ids_from_lex_map(raw_map)
        provenance = {
            "owner": "L6",
            "source": "lex_intervention_map",
            "version": version,
            "signals": {"knob_ids": knob_ids, "law_token": law_token},
        }
        if not knob_ids:
            yield _edge(
                "L6_LEX_INTERVENTION_MAP",
                str(law_token),
                "incomplete",
                _incomplete_completions("lex_map_knob_missing"),
                provenance,
            )
            continue
        knob_id = knob_ids[0]
        raw_knob = _mapping(bundle.knob_dictionary.get(knob_id))
        try:
            resolved = resolve_law_bound_lever(
                bundle,
                law_token=str(law_token),
                knob_id=knob_id,
                parameter_value=_representative_knob_value(raw_knob),
                legal_store=lex_store,
                world_model_record=world_model_record,
            )
        except InterventionSubstrateError as exc:
            yield _edge(
                "L6_LEX_INTERVENTION_MAP",
                str(law_token),
                "incomplete",
                _incomplete_completions(exc.code),
                provenance,
            )
            continue
        yield _confirmed_edge(
            "L6_LEX_INTERVENTION_MAP",
            str(law_token),
            {
                "knob_id": resolved.knob.operator_kind,
                "provision_ref": resolved.provision_ref,
                "threshold_id": resolved.threshold_id,
            },
            provenance,
        )

    for route in _mapping_list(bundle.observation_manifest.get("routes")):
        family = str(route.get("family") or "").strip()
        provenance = {
            "owner": "L6",
            "source": "observation_to_contract_manifest",
            "version": version,
            "signals": {"family": family, "route": route},
        }
        if not family:
            yield _edge(
                "L6_OBSERVATION_CONTRACT_ROUTE",
                "missing_family",
                "incomplete",
                _incomplete_completions("observation_family_missing"),
                provenance,
            )
            continue
        try:
            resolved_route = route_observation_family_method(bundle, family=family)
        except InterventionSubstrateError as exc:
            yield _edge(
                "L6_OBSERVATION_CONTRACT_ROUTE",
                family,
                "incomplete",
                _incomplete_completions(exc.code),
                provenance,
            )
            continue
        if resolved_route.status == "routed":
            yield _confirmed_edge(
                "L6_OBSERVATION_CONTRACT_ROUTE",
                family,
                resolved_route.model_dump(mode="json"),
                provenance,
            )
        else:
            yield _edge(
                "L6_OBSERVATION_CONTRACT_ROUTE",
                family,
                "incomplete",
                _incomplete_completions(resolved_route.reason_code or "method_route_blocked"),
                provenance,
            )


def _iter_wmr_edges(world_model_record: WorldModelRecord) -> Iterable[CredalReferenceEdge]:
    version = world_model_record.content_hash
    for slot in sorted(world_model_record.policy_slot_map, key=lambda item: item.slot_id):
        provenance = {
            "owner": "WMR",
            "source": "WorldModelRecord.policy_slot_map",
            "version": version,
            "signals": {
                "entity_scope": slot.entity_scope,
                "state_path": slot.state_path,
                "temporal_granularity": slot.temporal_granularity,
                "unit": slot.unit,
            },
        }
        value = {
            "entity_scope": slot.entity_scope,
            "slot_id": slot.slot_id,
            "state_path": slot.state_path,
            "temporal_granularity": slot.temporal_granularity,
            "unit": slot.unit,
            "world_model_record_id": world_model_record.world_model_record_id,
        }
        status: CredalReferenceStatus = (
            "confirmed"
            if slot.slot_id and slot.state_path and slot.entity_scope
            else "incomplete"
        )
        completions = (
            (AdmissibleCompletion("fixed", value, "world_slot_present_in_wmr"),)
            if status == "confirmed"
            else _incomplete_completions("world_slot_typeless_or_missing")
        )
        yield _edge("WMR_WORLD_SLOT", slot.slot_id, status, completions, provenance, unit=slot.unit)
        yield _edge(
            "WMR_POLICY_SLOT_MAP",
            f"{world_model_record.world_model_record_id}:{slot.slot_id}",
            status,
            completions,
            provenance,
            unit=slot.unit,
        )


@lru_cache(maxsize=2)
def _production_world_model_record(repo_root: str) -> WorldModelRecord:
    return _production_composed_world_model_record(repo_root)


def _component_versions(
    edge_index: Mapping[EdgeKey, CredalReferenceEdge],
    *,
    world_model_record: WorldModelRecord | None = None,
    world_model_record_hash: str | None = None,
) -> dict[str, str]:
    by_component: dict[str, list[str]] = defaultdict(list)
    for edge in edge_index.values():
        by_component[_component_for_modality(edge.modality)].append(edge.content_hash)
    component_versions = {
        component: _hash_sequence(hashes)
        for component, hashes in sorted(by_component.items())
    }
    if world_model_record is not None:
        component_versions["WMR"] = world_model_record.content_hash
    elif world_model_record_hash is not None:
        component_versions["WMR"] = world_model_record_hash
    return component_versions


def _reference_hash(
    *,
    component_versions: Mapping[str, str],
    edge_index: Mapping[EdgeKey, CredalReferenceEdge],
    as_of: str,
) -> str:
    return gy_content_hash(
        {
            "as_of": as_of,
            "component_versions": dict(sorted(component_versions.items())),
            "edge_content_hashes": sorted(edge.content_hash for edge in edge_index.values()),
            "schema_version": CREDAL_REFERENCE_SCHEMA_VERSION,
        }
    )


def _component_for_modality(modality: str) -> str:
    if modality.startswith("L2_"):
        return "L2"
    if modality.startswith("L3_"):
        return "L3"
    if modality.startswith("L6_"):
        return "L6"
    if modality.startswith("WMR_"):
        return "WMR"
    return "UNKNOWN"


def _hash_sequence(items: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for item in sorted(items):
        digest.update(item.encode("utf-8"))
        digest.update(b"\n")
    return "sha256:" + digest.hexdigest()


def _edge(
    modality: str,
    edge_id: str,
    status: CredalReferenceStatus,
    completions: Sequence[AdmissibleCompletion],
    provenance: Mapping[str, Any],
    *,
    unit: str | None = None,
    scale: str | None = None,
) -> CredalReferenceEdge:
    return CredalReferenceEdge(
        modality=modality,
        edge_id=str(edge_id),
        status=status,
        admissible_completions=tuple(completions),
        provenance=provenance,
        unit=unit,
        scale=scale,
    ).with_content_hash()


def _confirmed_edge(
    modality: str,
    edge_id: str,
    value: Mapping[str, Any],
    provenance: Mapping[str, Any],
    *,
    unit: str | None = None,
    scale: str | None = None,
) -> CredalReferenceEdge:
    return _edge(
        modality,
        edge_id,
        "confirmed",
        (AdmissibleCompletion("fixed", value, "owner_signal_confirmed"),),
        provenance,
        unit=unit,
        scale=scale,
    )


def _incomplete_completions(reason: str) -> tuple[AdmissibleCompletion, ...]:
    return (
        AdmissibleCompletion("may_exist", {}, reason),
        AdmissibleCompletion("may_not_exist", {}, reason),
        AdmissibleCompletion("partial", {}, reason),
    )


def _l2_direction_alternatives(
    contested: Mapping[str, Any],
    *,
    fallback: Mapping[str, Any],
) -> tuple[AdmissibleCompletion, ...]:
    histogram = _json_object(contested.get("direction_histogram_json"))
    directions = sorted(str(direction) for direction in histogram if str(direction))
    if not directions:
        direction = str(fallback.get("direction") or "")
        directions = [direction] if direction else ["unknown"]
    completions = [
        AdmissibleCompletion(
            "alternative",
            {**dict(fallback), "direction": direction},
            "contested_direction_alternative",
        )
        for direction in directions
    ]
    completions.append(
        AdmissibleCompletion("may_not_exist", dict(fallback), "contested_edge_may_not_hold")
    )
    return tuple(completions)


def _ortools_cp_sat_status() -> dict[str, Any]:
    try:
        cp_model = importlib.import_module("ortools.sat.python.cp_model")
        version = importlib.metadata.version("ortools")
        model = cp_model.CpModel()
        bool_var = model.NewBoolVar("assumption_probe")
        model.Add(bool_var == 1)
        model.AddAssumption(bool_var)
        solver = cp_model.CpSolver()
        has_unsat_core = hasattr(model, "AddAssumption") and hasattr(
            solver,
            "SufficientAssumptionsForInfeasibility",
        )
        return {
            "available": True,
            "name": "ortools_cp_sat",
            "unsat_core": "assumptions" if has_unsat_core else "unavailable",
            "version": version,
        }
    except Exception as exc:  # pragma: no cover - availability varies by env
        return {
            "available": False,
            "error": type(exc).__name__,
            "name": "ortools_cp_sat",
            "unsat_core": "unavailable",
            "version": None,
        }


def _scipy_milp_status() -> dict[str, Any]:
    try:
        optimize = importlib.import_module("scipy.optimize")
        scipy_version = importlib.metadata.version("scipy")
        return {
            "available": hasattr(optimize, "milp"),
            "name": "scipy.optimize.milp",
            "solver": "HiGHS",
            "version": scipy_version,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "available": False,
            "error": type(exc).__name__,
            "name": "scipy.optimize.milp",
            "solver": "HiGHS",
            "version": None,
        }


def _duckdb_fts_status() -> dict[str, Any]:
    try:
        con = duckdb.connect(":memory:")
        try:
            con.execute("LOAD fts")
        finally:
            con.close()
        return {"available": True, "name": "duckdb_fts", "version": duckdb.__version__}
    except Exception as exc:  # pragma: no cover
        return {
            "available": False,
            "error": type(exc).__name__,
            "name": "duckdb_fts",
            "version": getattr(duckdb, "__version__", None),
        }


def _hnswlib_status() -> dict[str, Any]:
    try:
        module = importlib.import_module("hnswlib")
        try:
            version = importlib.metadata.version("hnswlib")
        except importlib.metadata.PackageNotFoundError:
            version = getattr(module, "__version__", "unknown")
        return {"available": True, "name": "hnswlib", "version": version}
    except Exception as exc:  # pragma: no cover
        return {
            "available": False,
            "error": type(exc).__name__,
            "name": "hnswlib",
            "version": None,
        }


def _normalize_edge_key(key: EdgeKey | str) -> EdgeKey:
    if isinstance(key, tuple) and len(key) == 2:
        return (str(key[0]), str(key[1]))
    text = str(key)
    if "::" in text:
        left, right = text.split("::", 1)
        return (left, right)
    if ":" in text:
        left, right = text.split(":", 1)
        return (left, right)
    raise ValueError(f"invalid_edge_key:{text}")


def _edge_key_text(key: EdgeKey) -> str:
    return f"{key[0]}::{key[1]}"


def _parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    if "." in text:
        pieces = text.split(".")
        if len(pieces) >= 3:
            try:
                day, month, year = int(pieces[0]), int(pieces[1]), int(pieces[2][:4])
                return date(year, month, day)
            except ValueError:
                return None
    return None


def _date_text(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _data_forge_catalog_version(db_path: Path) -> str:
    manifest_path = db_path.parent / "manifest.json"
    if manifest_path.is_file():
        try:
            manifest = _json_object(manifest_path.read_text(encoding="utf-8"))
        except OSError:
            manifest = {}
        published_at = str(manifest.get("published_at") or "").strip()
        if published_at:
            return published_at
    return db_path.parent.name


def _json_object(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _json_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return list(parsed) if isinstance(parsed, list) else []
    return []


def _json_ready(value: object) -> object:
    return json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _string_list(value: object) -> list[str]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [str(item) for item in value]
    return []


def _split_blockers(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    parsed = _json_list(text)
    if parsed:
        return [str(item) for item in parsed if str(item)]
    return [item.strip() for item in text.split(",") if item.strip()]


def _float(value: object, *, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _threshold_scale(unit: object) -> str | None:
    unit_text = str(unit or "").casefold()
    if unit_text in {"percent", "%", "ratio", "basis_points", "bps"}:
        return NUMERIC_SCALING
    return None


def _representative_knob_value(raw_knob: Mapping[str, Any]) -> float | int | str | bool:
    values = raw_knob.get("values") or raw_knob.get("allowed_values")
    if isinstance(values, Sequence) and not isinstance(values, str | bytes | bytearray) and values:
        value = values[0]
        return value if isinstance(value, str | int | float | bool) else str(value)
    min_value = _float(raw_knob.get("min", raw_knob.get("min_value")))
    max_value = _float(raw_knob.get("max", raw_knob.get("max_value")))
    return (min_value + max_value) / 2.0


def _knob_ids_from_lex_map(value: object) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        raw = value.get("knobs") or value.get("knob_ids") or value.get("knob_id")
    else:
        raw = value
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Sequence):
        return tuple(str(item) for item in raw if str(item))
    return ()


__all__ = [
    "CREDAL_REFERENCE_SCHEMA_VERSION",
    "GROUNDING_BACKEND_AVAILABILITY_SCHEMA_VERSION",
    "AdmissibleCompletion",
    "CertificateStalenessDecision",
    "CredalReference",
    "CredalReferenceEdge",
    "GroundingBackendAvailability",
    "GroundingCertificateReference",
    "all_essential_confirmed",
    "bind_grounding_certificate_reference",
    "build_credal_reference",
    "build_grounding_backend_availability",
    "derive_data_forge_variable_alignment_edge",
    "derive_variable_alignment_edge",
    "edge_payload_sample",
    "essential_edge_scope_definition",
    "out_of_scope_edge",
    "reference_certificate_staleness",
    "reference_lift",
    "replace_reference_edge",
]
