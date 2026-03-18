from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from polisyos.core.contracts.execution_plan import (
    MethodCatalogEntry,
    MethodCatalogSnapshot,
    MethodDagNode,
)
from polisyos.foundry.methods.base import parse_fqn
from polisyos.foundry.methods.linker import check_linkable
from polisyos.foundry.methods.registry import MethodRegistry

_FIDELITY_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True, slots=True)
class DataCharacteristics:
    """
    Characteristics of the analysis dataset for data-aware method scoring.

    When provided to ``rank_method_catalog_entries()``, methods whose
    ``typical_min_obs`` exceeds the available observations are penalised.
    Instrument/running-variable availability is used to boost or penalise
    methods that require them.
    """

    n_obs: int | None = None
    """Total number of observations available."""
    n_units: int | None = None
    """Number of cross-sectional units (for panel data)."""
    n_periods: int | None = None
    """Number of time periods (for panel/time-series data)."""
    has_instrument: bool = False
    """Whether a valid instrumental variable is available."""
    has_running_variable: bool = False
    """Whether a forcing/running variable is available (for RDD)."""
    is_panel: bool = False
    """Whether the data has a panel structure (unit × time)."""
    treatment_is_binary: bool | None = None
    """True = binary treatment; False = continuous; None = unknown."""
    outcome_is_continuous: bool | None = None
    """True = continuous outcome; False = discrete; None = unknown."""


@dataclass(frozen=True, slots=True)
class MethodSelectionCriteria:
    preferred_kind: str | None = None
    preferred_family: str | None = None
    preferred_variant: str | None = None
    family_prefixes: tuple[str, ...] = ()
    preferred_execution_backends: tuple[str, ...] = ()
    required_data_modalities: tuple[str, ...] = ()
    preferred_data_modalities: tuple[str, ...] = ()
    preferred_determinism_tier: str | None = None
    minimum_fidelity_tier: str | None = None
    runnable_only: bool = True
    exclude_fqns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "family_prefixes", _normalize_tokens(self.family_prefixes))
        object.__setattr__(
            self,
            "preferred_execution_backends",
            _normalize_tokens(self.preferred_execution_backends),
        )
        object.__setattr__(
            self,
            "required_data_modalities",
            _normalize_tokens(self.required_data_modalities),
        )
        object.__setattr__(
            self,
            "preferred_data_modalities",
            _normalize_tokens(self.preferred_data_modalities),
        )
        object.__setattr__(self, "exclude_fqns", _normalize_tokens(self.exclude_fqns))


def rank_method_catalog_entries(
    entries: Iterable[MethodCatalogEntry],
    criteria: MethodSelectionCriteria,
    *,
    limit: int | None = None,
    data: DataCharacteristics | None = None,
) -> list[MethodCatalogEntry]:
    scored: list[tuple[float, MethodCatalogEntry]] = []
    for entry in entries:
        if entry.fqn in criteria.exclude_fqns:
            continue
        if criteria.runnable_only and entry.runnable is False:
            continue
        if criteria.required_data_modalities and not set(criteria.required_data_modalities).issubset(
            set(entry.data_modalities)
        ):
            continue
        if criteria.minimum_fidelity_tier is not None:
            required_rank = _FIDELITY_ORDER.get(criteria.minimum_fidelity_tier, -1)
            entry_rank = _FIDELITY_ORDER.get(entry.fidelity_tier, -1)
            if entry_rank < required_rank:
                continue
        score = _score_entry(entry, criteria)
        if data is not None:
            score += _score_data_characteristics(entry, data)
        if score > float("-inf"):
            scored.append((score, entry))

    scored.sort(key=lambda item: (-item[0], item[1].fqn))
    ranked = [entry for _, entry in scored]
    if limit is None:
        return ranked
    return ranked[: max(0, int(limit))]


def suggest_alternative_methods(
    catalog: MethodCatalogSnapshot,
    *,
    target_entry: MethodCatalogEntry | None = None,
    target_fqn: str | None = None,
    limit: int = 3,
) -> list[MethodCatalogEntry]:
    resolved_target = target_entry
    if resolved_target is None and target_fqn:
        resolved_target = next((entry for entry in catalog.entries if entry.fqn == target_fqn), None)

    if resolved_target is not None:
        preferred_modalities = tuple(resolved_target.data_modalities)
        family_prefixes = _family_prefixes(resolved_target.family)
        criteria = MethodSelectionCriteria(
            preferred_kind=resolved_target.kind,
            preferred_family=resolved_target.family,
            preferred_variant=resolved_target.variant,
            family_prefixes=family_prefixes,
            preferred_execution_backends=(resolved_target.execution_backend,),
            required_data_modalities=(),
            preferred_data_modalities=preferred_modalities,
            preferred_determinism_tier=resolved_target.determinism_tier,
            minimum_fidelity_tier=resolved_target.fidelity_tier,
            runnable_only=True,
            exclude_fqns=(resolved_target.fqn,),
        )
        return rank_method_catalog_entries(catalog.entries, criteria, limit=limit)

    family = None
    variant = None
    if target_fqn:
        try:
            namespace, name, _ = parse_fqn(target_fqn)
            family = namespace
            variant = name
        except ValueError:
            family = None
            variant = None
    criteria = MethodSelectionCriteria(
        preferred_family=family,
        preferred_variant=variant,
        family_prefixes=_family_prefixes(family),
        runnable_only=True,
    )
    return rank_method_catalog_entries(catalog.entries, criteria, limit=limit)


def method_selection_payload(entries: Sequence[MethodCatalogEntry]) -> list[dict[str, object]]:
    payload: list[dict[str, object]] = []
    for entry in entries:
        item: dict[str, object] = {
            "fqn": entry.fqn,
            "kind": entry.kind,
            "family": entry.family,
            "variant": entry.variant,
            "execution_backend": entry.execution_backend,
            "data_modalities": list(entry.data_modalities),
            "fidelity_tier": entry.fidelity_tier,
            "determinism_tier": entry.determinism_tier,
            "runnable": entry.runnable,
            "disabled_reasons": list(entry.disabled_reasons),
            "dependency_posture": dict(entry.dependency_posture),
        }
        # Include rich semantic fields when non-empty to enrich LLM context
        if entry.description:
            item["description"] = entry.description
        if entry.when_to_use:
            item["when_to_use"] = entry.when_to_use
        if entry.when_not_to_use:
            item["when_not_to_use"] = entry.when_not_to_use
        if entry.citations:
            item["citations"] = list(entry.citations)
        if entry.assumptions:
            item["assumptions"] = list(entry.assumptions)
        if entry.prerequisites:
            item["prerequisites"] = list(entry.prerequisites)
        if entry.diagnostic_checks:
            item["diagnostic_checks"] = list(entry.diagnostic_checks)
        if entry.typical_min_obs is not None:
            item["typical_min_obs"] = entry.typical_min_obs
        if entry.output_interpretation:
            item["output_interpretation"] = entry.output_interpretation
        payload.append(item)
    return payload


def suggest_adapter_methods(
    catalog: MethodCatalogSnapshot,
    *,
    source_fqn: str | None = None,
    target_fqn: str | None = None,
    source_signature: Any = None,
    target_signature: Any = None,
    limit: int = 3,
    registry: MethodRegistry | None = None,
    exclude_fqns: Sequence[str] = (),
) -> list[MethodCatalogEntry]:
    reg = registry or MethodRegistry.get_instance()
    source_sig = source_signature or _signature_for_fqn(reg, source_fqn)
    target_sig = target_signature or _signature_for_fqn(reg, target_fqn)
    if source_sig is None or target_sig is None:
        return []

    excluded = set(_normalize_tokens(exclude_fqns))
    if source_fqn:
        excluded.add(str(source_fqn))
    if target_fqn:
        excluded.add(str(target_fqn))

    ranked: list[tuple[float, MethodCatalogEntry]] = []
    for entry in catalog.entries:
        if entry.fqn in excluded:
            continue
        if entry.runnable is False:
            continue
        candidate_sig = _signature_for_fqn(reg, entry.fqn)
        if candidate_sig is None:
            continue
        if not check_linkable(source_sig, candidate_sig):
            continue
        if not check_linkable(candidate_sig, target_sig):
            continue
        score = _adapter_score(
            entry,
            source_signature=source_sig,
            candidate_signature=candidate_sig,
            target_signature=target_sig,
        )
        ranked.append((score, entry))

    ranked.sort(key=lambda item: (-item[0], item[1].fqn))
    return [entry for _, entry in ranked[: max(0, int(limit))]]


def suggest_plan_node_alternatives(
    catalog: MethodCatalogSnapshot,
    *,
    node: MethodDagNode,
    plan_nodes: Sequence[MethodDagNode],
    target_entry: MethodCatalogEntry | None = None,
    target_fqn: str | None = None,
    limit: int = 3,
    registry: MethodRegistry | None = None,
) -> list[MethodCatalogEntry]:
    candidate_limit = max(int(limit) * 8, 24)
    candidates = suggest_alternative_methods(
        catalog,
        target_entry=target_entry,
        target_fqn=target_fqn,
        limit=candidate_limit,
    )
    if not candidates:
        return []

    reg = registry or MethodRegistry.get_instance()
    node_by_id = {item.node_id: item for item in plan_nodes}
    downstream_nodes = tuple(
        item for item in plan_nodes if node.node_id in set(item.depends_on or [])
    )
    upstream_signatures = tuple(
        signature
        for signature in (
            _signature_for_node(reg, node_by_id.get(dep_id)) for dep_id in node.depends_on or []
        )
        if signature is not None
    )
    downstream_signatures = tuple(
        signature for signature in (_signature_for_node(reg, item) for item in downstream_nodes) if signature is not None
    )
    target_signature = _signature_for_fqn(reg, node.method_fqn)

    rescored: list[tuple[float, MethodCatalogEntry]] = []
    for index, candidate in enumerate(candidates):
        score = float(len(candidates) - index)
        score += _plan_node_score(
            reg,
            candidate,
            node=node,
            upstream_signatures=upstream_signatures,
            downstream_signatures=downstream_signatures,
            target_signature=target_signature,
        )
        rescored.append((score, candidate))
    rescored.sort(key=lambda item: (-item[0], item[1].fqn))
    return [entry for _, entry in rescored[: max(0, int(limit))]]


def authoring_catalog_payload(
    catalog: MethodCatalogSnapshot,
    *,
    limit_families: int = 12,
    per_family: int = 2,
) -> dict[str, Any]:
    ranked = rank_method_catalog_entries(
        catalog.entries,
        MethodSelectionCriteria(runnable_only=True),
    )
    grouped: dict[str, list[MethodCatalogEntry]] = defaultdict(list)
    for entry in ranked:
        grouped[entry.family].append(entry)

    families: list[dict[str, Any]] = []
    for family in sorted(
        grouped,
        key=lambda item: (
            grouped[item][0].kind,
            item,
        ),
    ):
        if len(families) >= max(1, int(limit_families)):
            break
        sample = grouped[family][: max(1, int(per_family))]
        families.append(
            {
                "family": family,
                "kind": sample[0].kind,
                "data_modalities": sorted(
                    {modality for entry in sample for modality in entry.data_modalities}
                ),
                "methods": method_selection_payload(sample),
            }
        )

    unavailable = [entry for entry in catalog.entries if entry.runnable is False]
    return {
        "source_schema_version": catalog.schema_version,
        "snapshot_id": catalog.snapshot_id,
        "runnable_method_count": sum(1 for entry in catalog.entries if entry.runnable),
        "unavailable_method_count": len(unavailable),
        "recommended_families": families,
        "notable_unavailable_families": sorted(
            {entry.family for entry in unavailable[: max(1, int(limit_families))]}
        ),
    }


def _score_entry(entry: MethodCatalogEntry, criteria: MethodSelectionCriteria) -> float:
    score = 0.0

    if criteria.preferred_kind is not None:
        if entry.kind != criteria.preferred_kind:
            score -= 25.0
        else:
            score += 25.0

    if criteria.preferred_family is not None:
        if entry.family == criteria.preferred_family:
            score += 100.0
        elif entry.family.startswith(criteria.preferred_family):
            score += 60.0

    if criteria.preferred_variant is not None:
        if entry.variant == criteria.preferred_variant or entry.name == criteria.preferred_variant:
            score += 70.0

    family_prefix_bonus = 0.0
    for idx, prefix in enumerate(criteria.family_prefixes):
        if entry.family.startswith(prefix):
            family_prefix_bonus = max(family_prefix_bonus, 30.0 - float(idx))
    score += family_prefix_bonus

    if criteria.preferred_execution_backends:
        if entry.execution_backend in criteria.preferred_execution_backends:
            order = criteria.preferred_execution_backends.index(entry.execution_backend)
            score += 18.0 - float(order)
        else:
            score -= 8.0

    if criteria.preferred_data_modalities:
        overlap = set(criteria.preferred_data_modalities) & set(entry.data_modalities)
        score += 8.0 * float(len(overlap))

    if criteria.preferred_determinism_tier is not None:
        if entry.determinism_tier == criteria.preferred_determinism_tier:
            score += 6.0

    if criteria.minimum_fidelity_tier is not None:
        score += float(_FIDELITY_ORDER.get(entry.fidelity_tier, 0))

    if entry.runnable:
        score += 20.0
    score -= float(len(entry.disabled_reasons))
    return score


def _score_data_characteristics(
    entry: MethodCatalogEntry,
    data: DataCharacteristics,
) -> float:
    """
    Adjust score based on observed data characteristics.

    Rewards methods that are well-suited to the available data;
    penalises methods whose requirements cannot be met.
    """
    score = 0.0

    # Penalise methods that need more observations than we have
    if data.n_obs is not None and entry.typical_min_obs is not None:
        if data.n_obs < entry.typical_min_obs:
            # Scale penalty: worse the further below minimum
            ratio = data.n_obs / max(entry.typical_min_obs, 1)
            score -= 20.0 * (1.0 - ratio)

    # IV methods: boost when instrument is available, penalise when not
    _iv_tags = {"iv", "instrumental_variable", "2sls", "gmm"}
    entry_tags = {t.lower() for t in entry.tags}
    is_iv_method = bool(_iv_tags & entry_tags) or "iv" in entry.family.lower()
    if is_iv_method:
        if data.has_instrument:
            score += 15.0
        else:
            score -= 20.0

    # RDD methods: boost when running variable available, penalise when not
    _rdd_tags = {"rdd", "regression_discontinuity", "kink_design"}
    is_rdd_method = bool(_rdd_tags & entry_tags) or "rdd" in entry.family.lower()
    if is_rdd_method:
        if data.has_running_variable:
            score += 15.0
        else:
            score -= 20.0

    # Panel methods: boost when panel structure available
    _panel_tags = {"panel", "did", "difference_in_differences", "fixed_effects"}
    is_panel_method = bool(_panel_tags & entry_tags) or "panel" in entry.family.lower()
    if is_panel_method and data.is_panel:
        score += 8.0

    # Cross-section methods: slight boost when only cross-section available
    _cross_section_tags = {"cross_section", "cross_sectional"}
    is_cs_method = bool(_cross_section_tags & entry_tags)
    if is_cs_method and not data.is_panel:
        score += 4.0

    return score


def _family_prefixes(family: str | None) -> tuple[str, ...]:
    if not family:
        return ()
    parts = [part for part in str(family).split(".") if part]
    prefixes = [".".join(parts[:idx]) for idx in range(len(parts), 0, -1)]
    return _normalize_tokens(prefixes)


def _normalize_tokens(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return ()
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = str(value).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        result.append(token)
    return tuple(result)


def _signature_for_node(
    registry: MethodRegistry,
    node: MethodDagNode | None,
):
    if node is None:
        return None
    return _signature_for_fqn(registry, node.method_fqn)


def _signature_for_fqn(registry: MethodRegistry, fqn: str | None):
    if not fqn:
        return None
    try:
        return registry.get(fqn).signature
    except Exception:
        return None


def _plan_node_score(
    registry: MethodRegistry,
    candidate: MethodCatalogEntry,
    *,
    node: MethodDagNode,
    upstream_signatures: Sequence[Any],
    downstream_signatures: Sequence[Any],
    target_signature: Any,
) -> float:
    candidate_signature = _signature_for_fqn(registry, candidate.fqn)
    if candidate_signature is None:
        return float("-inf")

    score = 0.0
    if target_signature is not None and candidate_signature.input_slot_names == target_signature.input_slot_names:
        score += 18.0
    if target_signature is not None and candidate_signature.output_slot_names == target_signature.output_slot_names:
        score += 18.0

    if node.backend:
        if candidate.execution_backend == str(node.backend):
            score += 12.0
        else:
            score -= 4.0

    requested_reads = {slot for slot in node.reads_slots if slot}
    requested_writes = {slot for slot in node.writes_slots if slot}
    score += 2.0 * len(requested_reads & set(candidate_signature.input_slot_names))
    score += 2.0 * len(requested_writes & set(candidate_signature.output_slot_names))

    if upstream_signatures:
        compatible_upstream = sum(
            1 for signature in upstream_signatures if check_linkable(signature, candidate_signature)
        )
        if compatible_upstream == len(upstream_signatures):
            score += 42.0
        else:
            score -= 25.0 * float(len(upstream_signatures) - compatible_upstream)

    if downstream_signatures:
        compatible_downstream = sum(
            1 for signature in downstream_signatures if check_linkable(candidate_signature, signature)
        )
        if compatible_downstream == len(downstream_signatures):
            score += 38.0
        else:
            score -= 22.0 * float(len(downstream_signatures) - compatible_downstream)

    return score


def _adapter_score(
    entry: MethodCatalogEntry,
    *,
    source_signature: Any,
    candidate_signature: Any,
    target_signature: Any,
) -> float:
    score = 0.0
    if entry.kind == "pure":
        score += 8.0
    elif entry.kind == "simulation":
        score -= 12.0
    elif entry.kind == "mechanism":
        score -= 18.0

    score += 6.0 * len(set(candidate_signature.input_slot_names) & set(source_signature.output_slot_names))
    score += 6.0 * len(set(candidate_signature.output_slot_names) & set(target_signature.input_slot_names))
    score -= 1.5 * float(abs(len(candidate_signature.input_slot_names) - len(source_signature.output_slot_names)))
    score -= 1.5 * float(abs(len(candidate_signature.output_slot_names) - len(target_signature.input_slot_names)))
    if entry.determinism_tier == "library_deterministic":
        score += 4.0
    if entry.execution_backend == "numpy":
        score += 3.0
    return score


__all__ = [
    "DataCharacteristics",
    "MethodSelectionCriteria",
    "authoring_catalog_payload",
    "method_selection_payload",
    "rank_method_catalog_entries",
    "suggest_adapter_methods",
    "suggest_plan_node_alternatives",
    "suggest_alternative_methods",
]
