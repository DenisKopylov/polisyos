"""Topic/run-aware SKG query helpers for SCM stages."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.contracts import DataTrust, ValueOuterSet
from polisyos.data_forge.domains.academic.knowledge.canonical_resolver import (
    CanonicalVariableResolver,
    ResolutionResult,
)
from polisyos.data_forge.domains.academic.knowledge.skg_store import (
    EVIDENCE_WEIGHTS,
    decode_edge_evidence_strength,
    parent_canonical_name,
)
from polisyos.data_forge.domains.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.data_forge.domains.academic.knowledge.types import (
    BoundaryConditionResult,
    CausalClaimResult,
    CausalClaimResultV1,
    ClaimVocabularySourceRowBinding,
    ParameterEstimateResult,
    ParameterPrior,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import (
    ClaimVocabularyAxisStatus,
    EvidenceParameter,
    EvidenceStrength,
    ParameterType,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class LiteraturePriorResult:
    """Literature prior result data model."""

    variable: str
    prior: ParameterPrior | None
    estimates: list[ParameterEstimateResult]


@dataclass(frozen=True)
class ParameterCandidate:
    """Parameter candidate public type."""

    parameter: EvidenceParameter
    source_context: ContextProfile | None
    transport_penalty: float = 0.0
    transport_notes: tuple[str, ...] = ()
    requires_expert_review: bool = False
    source_layer: str = "raw_parameter"
    linked_claim_ids: tuple[str, ...] = ()
    linked_edge_ids: tuple[str, ...] = ()
    uncertainty_source: str = ""
    quality_flags: tuple[str, ...] = ()
    normalization_diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class EdgeSupportRecord:
    """Summarize the evidence currently supporting one SKG edge after claim/article synthesis."""

    edge_id: str
    src: str
    dst: str
    direction: str
    confidence: float
    evidence_strength: str | None
    n_unique_works: int
    evidence_strength_status: ClaimVocabularyAxisStatus = ClaimVocabularyAxisStatus.CANDIDATE
    n_claims: int = 0
    article_refs: tuple[str, ...] = ()
    claim_refs: tuple[str, ...] = ()
    source_layer: str = "exact"
    conflict_flag: bool = False
    quality_flags: tuple[str, ...] = ()
    dominant_direction_agreement: float = 1.0
    positive_weight: float = 0.0
    negative_weight: float = 0.0
    mixed_weight: float = 0.0
    strongest_dissent_strength: str = ""
    strongest_dissent_year: int | None = None
    resolution_status: str = ""
    source_bindings: tuple[ClaimVocabularySourceRowBinding, ...] = ()


@dataclass(frozen=True)
class EdgeTransportRecord:
    """Summarize how strongly an SKG edge transports into a target context profile."""

    edge_id: str
    target_context_id: str
    transport_confidence: float
    match_mode: str = ""
    matched_moderators_count: int = 0
    generic_penalty: float = 0.0
    context_match_reward: float = 0.0
    base_confidence: float = 0.0


@dataclass(frozen=True)
class GroundedCausalPriorResolution:
    """Resolve-bind-validate result for a candidate effect against the SKG."""

    status: str
    cause: str
    effect: str
    estimand: str
    scope_context_id: str
    skg_version_id: int
    skg_snapshot_ref: str
    edge_id: str | None
    relevance_score: float
    content_bind_status: str
    validation_status: str
    blockers: tuple[str, ...] = ()
    transport_ref: str | None = None
    transport_confidence: float | None = None


class SKGQuery:
    """Read-only query API for SKG tables in academic DuckDB."""

    def __init__(self, db_path: Path, index_dir: Path) -> None:
        self._db_path = Path(db_path)
        self._store = ScholarKnowledgeStore(db_path, index_dir)
        self._con = duckdb.connect(str(db_path), read_only=True)
        self._resolver: CanonicalVariableResolver | None = None
        self._transport_confidence_floor: float | None = None

    def query_prior(
        self,
        *,
        variable: str,
        domain: str | None = None,
        country: str | None = None,
    ) -> LiteraturePriorResult:
        estimates = self._store.get_parameter_estimates(variable, domain=domain, country=country)
        if not estimates:
            return LiteraturePriorResult(variable=variable, prior=None, estimates=[])

        values = np.array([e.estimate for e in estimates])
        weights = np.array([max(0.01, e.trust_score) for e in estimates])
        weights = weights / weights.sum()

        weighted_mean = float(np.average(values, weights=weights))
        weighted_std = float(np.sqrt(np.average((values - weighted_mean) ** 2, weights=weights)))
        weighted_std = max(weighted_std, 0.01)
        prior_low = float(np.percentile(values, 10))
        prior_high = float(np.percentile(values, 90))

        best_design = (
            sorted(estimates, key=lambda e: e.trust_score, reverse=True)[0].study_design
            if estimates
            else ""
        )
        prior = ParameterPrior(
            variable=variable,
            prior_mean=weighted_mean,
            prior_std=weighted_std,
            prior_low=prior_low,
            prior_high=prior_high,
            n_studies=len(estimates),
            best_design=best_design,
            as_calibration_prior={
                "distribution": "normal",
                "mean": weighted_mean,
                "std": weighted_std,
            },
        )
        return LiteraturePriorResult(variable=variable, prior=prior, estimates=estimates)

    def query_claims(
        self,
        *,
        cause: str,
        effect: str,
        min_trust: float = 0.5,
        support_mode: str = "exact",
        limit: int = 32,
    ) -> list[CausalClaimResult]:
        mode = self._normalize_support_mode(support_mode)
        if mode == "exact":
            return self._store.get_causal_claims(cause, effect, min_trust=min_trust)
        rows = self.query_edge_support(
            cause=cause,
            effect=effect,
            min_confidence=min_trust,
            support_mode=mode,
            limit=limit,
        )
        return [
            self._store.project_edge_summary(
                source_table={
                    "exact": "ac_skg_edges",
                    "family": "ac_skg_family_edges",
                    "contested": "ac_skg_contested_edges",
                    "hybrid": "ac_skg_edges",
                }.get(row.source_layer, "ac_skg_edges"),
                source_identity=row.edge_id,
                source_bindings=row.source_bindings or None,
                cause=row.src,
                effect=row.dst,
                direction=row.direction,
                evidence_strength=row.evidence_strength,
                mechanism=(
                    "contested_summary" if mode == "contested" else f"{row.source_layer}_support"
                ),
                domain=self._edge_domain(row.src, row.dst),
                trust_score=row.confidence,
                work_title=f"{row.n_unique_works} work(s) synthesized",
                work_id=row.article_refs[0] if row.article_refs else "",
            )
            for row in rows
        ]

    def query_claims_v1_audit(
        self,
        *,
        cause: str,
        effect: str,
        min_trust: float = 0.5,
    ) -> list[CausalClaimResultV1]:
        """Deprecated audit-only claim view; never used by semantic consumers."""
        return self._store.get_causal_claims_v1_audit(cause, effect, min_trust=min_trust)

    def query_boundary_conditions(self, *, work_id: str) -> list[BoundaryConditionResult]:
        return self._store.get_boundary_conditions_for_work(work_id)

    def query_parameters(
        self,
        parameter_name: str,
        *,
        target_context: ContextProfile | None = None,
        limit: int = 256,
        layer: str = "auto",
        require_simulation_ready: bool = True,
    ) -> list[ParameterCandidate]:
        clean_name = str(parameter_name).strip()
        if not clean_name:
            return []
        lookup_names, canonical_gap_resolved = self._parameter_lookup_names(
            clean_name,
            need_type="parameter",
        )

        selected_layer = self._normalize_parameter_layer(layer)
        results: list[ParameterCandidate] = []

        if selected_layer in {"auto", "simulation", "hybrid"}:
            for lookup_name in lookup_names:
                sim_results = self._query_simulation_parameter_candidates(
                    lookup_name,
                    target_context=target_context,
                    limit=limit,
                )
                if sim_results:
                    results.extend(
                        self._annotate_candidates(
                            sim_results,
                            query_name=clean_name,
                            canonical_gap_resolved=(
                                lookup_name != clean_name or canonical_gap_resolved
                            ),
                        )
                    )
                    break
            if selected_layer == "simulation":
                return results

        if results and selected_layer == "auto":
            return results[:limit]

        if selected_layer in {"auto", "raw", "hybrid"}:
            raw_candidates: list[ParameterCandidate] = []
            for lookup_name in lookup_names:
                raw_candidates = self._query_raw_parameter_candidates(
                    lookup_name,
                    target_context=target_context,
                    limit=limit,
                )
                if raw_candidates:
                    raw_candidates = self._annotate_candidates(
                        raw_candidates,
                        query_name=clean_name,
                        canonical_gap_resolved=(
                            lookup_name != clean_name or canonical_gap_resolved
                        ),
                    )
                    break
            if require_simulation_ready:
                raw_candidates = [
                    replace(
                        candidate,
                        requires_expert_review=True,
                        quality_flags=tuple(
                            sorted(
                                {
                                    *candidate.quality_flags,
                                    "raw_parameter_fallback",
                                    "simulation_ready_missing",
                                }
                            )
                        ),
                        transport_notes=(*candidate.transport_notes, "raw_parameter_fallback"),
                    )
                    for candidate in raw_candidates
                ]
            results.extend(raw_candidates)

        deduped: dict[tuple[str, float | None, str, str], ParameterCandidate] = {}
        for candidate in results:
            key = (
                candidate.parameter.name,
                candidate.parameter.value,
                candidate.source_layer,
                candidate.parameter.evidence_strength.value,
            )
            existing = deduped.get(key)
            if existing is None:
                deduped[key] = candidate
                continue
            deduped[key] = (
                existing
                if self._candidate_priority(existing) >= self._candidate_priority(candidate)
                else candidate
            )
        ordered = sorted(deduped.values(), key=self._candidate_priority, reverse=True)
        return ordered[:limit]

    def _query_simulation_parameter_candidates(
        self,
        parameter_name: str,
        *,
        target_context: ContextProfile | None,
        limit: int,
    ) -> list[ParameterCandidate]:
        if not self._table_exists("ac_skg_simulation_parameters"):
            return []
        has_ci = self._column_exists("ac_skg_simulation_parameters", "confidence_interval_json")
        has_std_error = self._column_exists("ac_skg_simulation_parameters", "std_error")
        has_source_layer = self._column_exists("ac_skg_simulation_parameters", "source_layer")
        has_uncertainty_source = self._column_exists(
            "ac_skg_simulation_parameters", "uncertainty_source"
        )
        has_quality_flags = self._column_exists(
            "ac_skg_simulation_parameters", "quality_flags_json"
        )
        extra_select = []
        extra_select.append(
            "confidence_interval_json" if has_ci else "'[]' AS confidence_interval_json"
        )
        extra_select.append("std_error" if has_std_error else "NULL AS std_error")
        extra_select.append(
            "source_layer" if has_source_layer else "'simulation_ready' AS source_layer"
        )
        extra_select.append(
            "uncertainty_source" if has_uncertainty_source else "'' AS uncertainty_source"
        )
        extra_select.append(
            "quality_flags_json" if has_quality_flags else "'[]' AS quality_flags_json"
        )

        rows = self._con.execute(
            f"""
            SELECT numeric_id, openalex_id, canonical_name, estimate_type, point_estimate,
                   estimate_sign, unit, evidence_strength,
                   {", ".join(extra_select)},
                   linked_claim_ids_json, linked_edges_json, context_json
            FROM ac_skg_simulation_parameters
            WHERE canonical_name = ?
            LIMIT ?
            """,
            [parameter_name, int(limit)],
        ).fetchall()

        out: list[ParameterCandidate] = []
        for row in rows:
            ci_payload = self._parse_json_list_or_number_pair(row[8])
            std_error = self._safe_float(row[9])
            source_layer = str(row[10] or "simulation_ready").strip() or "simulation_ready"
            uncertainty_source = str(row[11] or "").strip() or (
                "confidence_interval"
                if ci_payload is not None
                else "std_error"
                if std_error is not None
                else ""
            )
            quality_flags = tuple(self._parse_json_list(row[12]))
            linked_claim_ids = tuple(self._parse_json_list(row[13]))
            linked_edge_ids = tuple(self._linked_edge_refs(self._parse_json_mixed_list(row[14])))
            source_context = self._parse_context_profile(row[15])
            parameter = self._to_evidence_parameter(
                parameter_name,
                {
                    "display_name": parameter_name,
                    "value": self._safe_float(row[4]),
                    "unit": str(row[6] or "").strip() or None,
                    "evidence_strength": str(row[7] or ""),
                    "confidence_interval": list(ci_payload) if ci_payload is not None else None,
                    "std_error": std_error,
                },
            )
            if parameter is None:
                continue
            transport_penalty, transport_notes, requires_expert_review = (
                self._transport_metadata_for_parameter(
                    parameter_name,
                    source_context=source_context,
                    target_context=target_context,
                    linked_edge_refs=linked_edge_ids,
                )
            )
            out.append(
                ParameterCandidate(
                    parameter=parameter,
                    source_context=source_context,
                    transport_penalty=transport_penalty,
                    transport_notes=tuple(transport_notes),
                    requires_expert_review=requires_expert_review,
                    source_layer=source_layer,
                    linked_claim_ids=linked_claim_ids,
                    linked_edge_ids=linked_edge_ids,
                    uncertainty_source=uncertainty_source,
                    quality_flags=quality_flags,
                )
            )
        return out

    def _query_raw_parameter_candidates(
        self,
        parameter_name: str,
        *,
        target_context: ContextProfile | None,
        limit: int,
    ) -> list[ParameterCandidate]:
        if not self._table_exists("ac_skg_parameters"):
            return []
        rows = self._con.execute(
            """
            SELECT parameter_json, context_json
            FROM ac_skg_parameters
            WHERE canonical_name = ?
            LIMIT ?
            """,
            [parameter_name, int(limit)],
        ).fetchall()

        out: list[ParameterCandidate] = []
        for parameter_json, context_json in rows:
            payload = self._parse_json_dict(parameter_json)
            if payload is None:
                continue
            normalization_diagnostics: list[str] = []
            parameter = self._to_evidence_parameter(
                parameter_name,
                payload,
                diagnostics=normalization_diagnostics,
            )
            if parameter is None:
                continue
            source_context = self._parse_context_profile(context_json)
            transport_penalty, transport_notes, requires_expert_review = (
                self._transport_metadata_for_parameter(
                    parameter_name,
                    source_context=source_context,
                    target_context=target_context,
                    linked_edge_refs=(),
                )
            )
            quality_flags: list[str] = []
            if parameter.confidence_interval is None and parameter.std_error is None:
                quality_flags.append("uncertainty_missing")
            out.append(
                ParameterCandidate(
                    parameter=parameter,
                    source_context=source_context,
                    transport_penalty=transport_penalty,
                    transport_notes=tuple(transport_notes),
                    requires_expert_review=requires_expert_review,
                    source_layer="raw_parameter",
                    linked_claim_ids=(),
                    linked_edge_ids=(),
                    uncertainty_source="confidence_interval"
                    if parameter.confidence_interval is not None
                    else "std_error"
                    if parameter.std_error is not None
                    else "",
                    quality_flags=tuple(quality_flags),
                    normalization_diagnostics=tuple(normalization_diagnostics),
                )
            )
        return out

    def _transport_metadata_for_parameter(
        self,
        parameter_name: str,
        *,
        source_context: ContextProfile | None,
        target_context: ContextProfile | None,
        linked_edge_refs: tuple[str, ...],
    ) -> tuple[float, list[str], bool]:
        notes: list[str] = []
        penalty = 0.0
        requires_expert_review = False

        if source_context is None:
            penalty += 0.15
            notes.append("source_context_missing")
            requires_expert_review = True
        elif not self._context_profile_exists(source_context.context_id):
            penalty += 0.10
            notes.append("source_context_profile_missing")
        elif target_context is not None:
            try:
                context_distance = float(source_context.distance_to(target_context))
            except Exception:
                context_distance = None
            if context_distance is not None:
                notes.append(f"context_distance:{context_distance:.2f}")
                if context_distance >= 0.30:
                    penalty += min(0.20, context_distance * 0.20)
                    notes.append("context_mismatch")
                    requires_expert_review = True
                elif context_distance >= 0.15:
                    penalty += min(0.10, context_distance * 0.10)
                    notes.append("context_gap")

        if target_context is not None:
            if not self._context_profile_exists(target_context.context_id):
                penalty += 0.10
                notes.append("target_context_profile_missing")
                requires_expert_review = True
            else:
                transport_confidence = self._transport_confidence_for_edges(
                    linked_edge_refs,
                    target_context.context_id,
                )
                if transport_confidence is None:
                    penalty += 0.05
                    notes.append("transport_score_unavailable")
                else:
                    penalty = max(0.0, penalty - min(0.15, transport_confidence * 0.15))
                    notes.append(f"transport_confidence:{transport_confidence:.2f}")
                    transport_records = self.query_edge_transport(
                        linked_edge_refs,
                        target_context_id=target_context.context_id,
                    )
                    if any(record.matched_moderators_count > 0 for record in transport_records):
                        notes.append("moderator_match")
                        penalty = max(0.0, penalty - 0.05)
                    if any(
                        float(record.context_match_reward or 0.0) > 0.0
                        for record in transport_records
                    ):
                        notes.append("context_match_positive")
                    if any(
                        float(record.generic_penalty or 0.0) > 0.0 for record in transport_records
                    ):
                        notes.append("generic_transport_penalty")

        moderation_edges = self._moderation_signal_count(parameter_name)
        if moderation_edges > 0:
            notes.append(f"moderation_edges:{moderation_edges}")
            if "moderator_match" not in notes:
                penalty += min(0.15, 0.03 * moderation_edges)
                notes.append("moderator_review_needed")

        return min(0.5, penalty), notes, requires_expert_review

    def _canonical_resolver(self) -> CanonicalVariableResolver:
        if self._resolver is None:
            try:
                self._resolver = CanonicalVariableResolver.from_connection(self._con)
            except Exception:
                self._resolver = CanonicalVariableResolver(approved_names=(), approved_synonyms={})
        return self._resolver

    def resolve_runtime_canonical(
        self,
        raw_name: str,
        *,
        need_type: str | None = None,
        runtime_priority: bool | None = None,
    ) -> ResolutionResult:
        clean_name = str(raw_name).strip()
        if not clean_name:
            return ResolutionResult(
                raw_name="",
                canonical_name=None,
                method="empty",
                confidence=0.0,
                approved=False,
                review_required=True,
            )
        try:
            return self._canonical_resolver().resolve(
                clean_name,
                need_type=need_type,
                runtime_priority=runtime_priority,
            )
        except Exception:
            return ResolutionResult(
                raw_name=clean_name,
                canonical_name=None,
                method="resolver_error",
                confidence=0.0,
                approved=False,
                review_required=True,
            )

    def _observed_names_for_approved_canonical(self, canonical_name: str) -> list[str]:
        clean_name = str(canonical_name).strip()
        if not clean_name or not self._table_exists("ac_skg_variables"):
            return []
        try:
            rows = self._con.execute(
                """
                SELECT canonical_name, normalized_name
                FROM ac_skg_variables
                WHERE approved_canonical_name = ?
                   OR canonical_name = ?
                   OR normalized_name = ?
                ORDER BY mention_count DESC, canonical_name ASC
                """,
                [clean_name, clean_name, clean_name],
            ).fetchall()
        except duckdb.Error:
            return []
        observed: list[str] = []
        for canonical_value, normalized_value in rows:
            for candidate in (canonical_value, normalized_value):
                clean_candidate = str(candidate or "").strip()
                if clean_candidate:
                    observed.append(clean_candidate)
        return list(dict.fromkeys(observed))

    def _approved_synonym_neighbors(self, variable_name: str) -> list[str]:
        clean_name = str(variable_name).strip()
        if not clean_name or not self._table_exists("ac_skg_variable_synonyms"):
            return []
        try:
            rows = self._con.execute(
                """
                SELECT synonym, canonical_name
                FROM ac_skg_variable_synonyms
                WHERE approved = TRUE
                  AND (synonym = ? OR canonical_name = ?)
                ORDER BY confidence DESC, synonym ASC, canonical_name ASC
                """,
                [clean_name, clean_name],
            ).fetchall()
        except duckdb.Error:
            return []
        neighbors: list[str] = []
        for synonym, canonical_name in rows:
            for candidate in (synonym, canonical_name):
                token = str(candidate or "").strip()
                if token:
                    neighbors.append(token)
        return list(dict.fromkeys(neighbors))

    def _child_canonical_names(self, parent_name: str) -> list[str]:
        """Return child canonical names that use ``parent_name`` as a suffix.

        For parent-level seed variables like ``unemployment_rate``, this finds
        domain-prefixed variants such as ``labor.unemployment_rate`` that
        actually appear as src/dst in the SKG edges.
        """
        clean = str(parent_name).strip()
        if not clean:
            return []
        pattern = f"%.{clean}"
        children: list[str] = []
        for table, col in (
            ("ac_skg_family_edges", "src_family"),
            ("ac_skg_family_edges", "dst_family"),
            ("ac_skg_edges", "src"),
            ("ac_skg_edges", "dst"),
        ):
            if not self._table_exists(table):
                continue
            try:
                rows = self._con.execute(
                    f"SELECT DISTINCT {col} FROM {table} WHERE {col} LIKE ? OR {col} = ?",
                    [pattern, clean],
                ).fetchall()
                children.extend(str(row[0]) for row in rows if row and row[0])
            except Exception:
                continue
        return list(dict.fromkeys(children))

    def _parameter_lookup_names(
        self,
        parameter_name: str,
        *,
        need_type: str = "parameter",
    ) -> tuple[list[str], bool]:
        clean_name = str(parameter_name).strip()
        if not clean_name:
            return [], False
        candidates = [clean_name]
        resolved = self.resolve_runtime_canonical(
            clean_name,
            need_type=need_type,
            runtime_priority=True,
        )
        if (
            resolved is not None
            and resolved.canonical_name
            and resolved.canonical_name != clean_name
        ):
            candidates.append(resolved.canonical_name)
        candidates.extend(self._approved_synonym_neighbors(clean_name))
        if resolved is not None and resolved.canonical_name:
            candidates.extend(self._observed_names_for_approved_canonical(resolved.canonical_name))
            candidates.extend(self._approved_synonym_neighbors(resolved.canonical_name))
            parent = parent_canonical_name(resolved.canonical_name)
            if (
                need_type in {"causal_edge", "scholar_query"}
                and parent
                and parent != resolved.canonical_name
            ):
                candidates.extend(self._observed_names_for_approved_canonical(parent))
            # For parent-level canonical names (no dot), also expand to child
            # variables that use this as a prefix (e.g. "unemployment_rate" ->
            # "labor.unemployment_rate").
            if need_type in {"causal_edge", "scholar_query"} and "." not in resolved.canonical_name:
                candidates.extend(self._child_canonical_names(resolved.canonical_name))
        return list(dict.fromkeys(candidate for candidate in candidates if candidate)), bool(
            resolved is not None
            and resolved.canonical_name
            and (resolved.canonical_name != clean_name or len(candidates) > 1)
        )

    def _annotate_candidates(
        self,
        candidates: list[ParameterCandidate],
        *,
        query_name: str,
        canonical_gap_resolved: bool,
    ) -> list[ParameterCandidate]:
        annotated: list[ParameterCandidate] = []
        for candidate in candidates:
            flags = list(candidate.quality_flags)
            if (
                candidate.parameter.confidence_interval is None
                and candidate.parameter.std_error is None
            ) and "no_uncertainty" not in flags:
                flags.append("no_uncertainty")
            if canonical_gap_resolved and "canonical_gap_resolved" not in flags:
                flags.append("canonical_gap_resolved")
            notes = list(candidate.transport_notes)
            if canonical_gap_resolved and "canonical_gap_resolved" not in notes:
                notes.append("canonical_gap_resolved")
            parameter = candidate.parameter
            if canonical_gap_resolved and parameter.name != query_name:
                parameter = parameter.model_copy(
                    update={
                        "name": query_name,
                        "display_name": query_name,
                    }
                )
            annotated.append(
                replace(
                    candidate,
                    parameter=parameter,
                    transport_notes=tuple(notes),
                    quality_flags=tuple(flags),
                )
            )
        return annotated

    def _context_profile_exists(self, context_id: str | None) -> bool:
        clean_context_id = str(context_id or "").strip()
        if not clean_context_id or not self._table_exists("ac_skg_context_profiles"):
            return False
        try:
            row = self._con.execute(
                """
                SELECT 1
                FROM ac_skg_context_profiles
                WHERE context_id = ? OR profile_id = ?
                LIMIT 1
                """,
                [clean_context_id, clean_context_id],
            ).fetchone()
        except duckdb.Error:
            return False
        return bool(row)

    def _moderation_signal_count(self, parameter_name: str) -> int:
        if not self._table_exists("ac_skg_moderation_edges"):
            return 0
        clean_name = str(parameter_name).strip()
        if not clean_name:
            return 0
        try:
            row = self._con.execute(
                """
                SELECT COUNT(*)
                FROM ac_skg_moderation_edges
                WHERE moderator = ?
                   OR moderator ILIKE ?
                   OR moderator ILIKE ?
                """,
                [clean_name, f"%.{clean_name}", f"{clean_name}.%"],
            ).fetchone()
        except duckdb.Error:
            return 0
        return int(row[0]) if row and row[0] is not None else 0

    def _transport_confidence_for_edges(
        self,
        linked_edge_refs: tuple[str, ...],
        target_context_id: str,
    ) -> float | None:
        clean_context_id = str(target_context_id or "").strip()
        if (
            not clean_context_id
            or not linked_edge_refs
            or not self._table_exists("ac_skg_transport_scores")
        ):
            return None
        placeholders = ", ".join(["?"] * len(linked_edge_refs))
        try:
            row = self._con.execute(
                f"""
                SELECT AVG(transport_confidence)
                FROM ac_skg_transport_scores
                WHERE target_context_id = ?
                  AND edge_id IN ({placeholders})
                """,
                [clean_context_id, *linked_edge_refs],
            ).fetchone()
        except duckdb.Error:
            return None
        value = self._safe_float(row[0] if row else None)
        return value

    def query_edge_transport(
        self,
        edge_ids: list[str] | tuple[str, ...],
        *,
        target_context_id: str,
    ) -> list[EdgeTransportRecord]:
        clean_context_id = str(target_context_id or "").strip()
        clean_edge_ids = sorted(
            {str(edge_id).strip() for edge_id in edge_ids if str(edge_id).strip()}
        )
        if (
            not clean_context_id
            or not clean_edge_ids
            or not self._table_exists("ac_skg_transport_scores")
        ):
            return []
        placeholders = ", ".join(["?"] * len(clean_edge_ids))
        base_confidence_sql = (
            "base_confidence"
            if self._column_exists("ac_skg_transport_scores", "base_confidence")
            else "transport_confidence"
        )
        rows = self._con.execute(
            f"""
            SELECT edge_id, target_context_id, transport_confidence, match_mode,
                   matched_moderators_json, generic_penalty, context_match_reward
                   , {base_confidence_sql} AS base_confidence
            FROM ac_skg_transport_scores
            WHERE target_context_id = ?
              AND edge_id IN ({placeholders})
            ORDER BY transport_confidence DESC, edge_id ASC
            """,
            [clean_context_id, *clean_edge_ids],
        ).fetchall()
        results: list[EdgeTransportRecord] = []
        for row in rows:
            matched = self._parse_json_list(row[4])
            if not matched:
                mixed = self._parse_json_mixed_list(row[4])
                matched_count = len(mixed)
            else:
                matched_count = len(matched)
            results.append(
                EdgeTransportRecord(
                    edge_id=str(row[0]),
                    target_context_id=str(row[1]),
                    transport_confidence=float(row[2] or 0.0),
                    match_mode=str(row[3] or ""),
                    matched_moderators_count=matched_count,
                    generic_penalty=float(row[5] or 0.0),
                    context_match_reward=float(row[6] or 0.0),
                    base_confidence=float(row[7] or 0.0),
                )
            )
        return results

    def _table_exists(self, table_name: str) -> bool:
        try:
            row = self._con.execute(
                """
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = ?
                LIMIT 1
                """,
                [str(table_name)],
            ).fetchone()
        except duckdb.Error:
            return False
        return bool(row)

    def _column_exists(self, table_name: str, column_name: str) -> bool:
        try:
            row = self._con.execute(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = ? AND column_name = ?
                LIMIT 1
                """,
                [str(table_name), str(column_name)],
            ).fetchone()
        except duckdb.Error:
            return False
        return bool(row)

    def query_edge_support(
        self,
        *,
        cause: str,
        effect: str,
        min_confidence: float = 0.25,
        support_mode: str = "hybrid",
        limit: int = 32,
    ) -> list[EdgeSupportRecord]:
        clean_cause = str(cause).strip()
        clean_effect = str(effect).strip()
        if not clean_cause or not clean_effect:
            return []
        rows = self._query_edge_support_for_names(
            cause=clean_cause,
            effect=clean_effect,
            min_confidence=min_confidence,
            support_mode=support_mode,
            limit=limit,
        )
        if rows:
            return rows[:limit]
        canonical_causes, _ = self._parameter_lookup_names(clean_cause, need_type="causal_edge")
        canonical_effects, _ = self._parameter_lookup_names(clean_effect, need_type="causal_edge")
        candidate_pairs = [(clean_cause, clean_effect)]
        candidate_pairs.extend(
            (candidate_cause, candidate_effect)
            for candidate_cause in canonical_causes
            for candidate_effect in canonical_effects
            if candidate_cause and candidate_effect
        )
        dedup_pairs = list(dict.fromkeys(candidate_pairs))
        if dedup_pairs == [(clean_cause, clean_effect)]:
            return []
        merged: dict[tuple[str, str, str], EdgeSupportRecord] = {}
        for candidate_cause, candidate_effect in dedup_pairs[1:]:
            rows = self._query_edge_support_for_names(
                cause=candidate_cause,
                effect=candidate_effect,
                min_confidence=min_confidence,
                support_mode=support_mode,
                limit=limit,
            )
            for row in rows:
                key = (row.src, row.dst, row.direction)
                existing = merged.get(key)
                if existing is None or row.confidence > existing.confidence:
                    merged[key] = row
        return sorted(merged.values(), key=lambda item: item.confidence, reverse=True)[:limit]

    def _query_edge_support_for_names(
        self,
        *,
        cause: str,
        effect: str,
        min_confidence: float,
        support_mode: str,
        limit: int,
    ) -> list[EdgeSupportRecord]:
        clean_cause = str(cause).strip()
        clean_effect = str(effect).strip()
        if not clean_cause or not clean_effect:
            return []
        mode = self._normalize_support_mode(support_mode)
        if mode == "contested":
            contested_rows = self._query_contested_edge_support(
                clean_cause,
                clean_effect,
                min_confidence=min_confidence,
                limit=limit,
            )
            if contested_rows:
                return contested_rows[:limit]
            hybrid_rows = self.query_edge_support(
                cause=clean_cause,
                effect=clean_effect,
                min_confidence=min_confidence,
                support_mode="hybrid",
                limit=max(limit, 8),
            )
            direction_set = {
                str(row.direction or "").strip().lower()
                for row in hybrid_rows
                if str(row.direction or "").strip()
            }
            if len(direction_set) > 1:
                return hybrid_rows[:limit]
            return [row for row in hybrid_rows if bool(row.conflict_flag)][:limit]
        rows: list[EdgeSupportRecord] = []
        if mode in {"exact", "hybrid"}:
            rows.extend(
                self._query_exact_edge_support(
                    clean_cause,
                    clean_effect,
                    min_confidence=min_confidence,
                    limit=limit,
                )
            )
            if mode == "exact":
                return rows[:limit]
        if mode in {"family", "hybrid"}:
            rows.extend(
                self._query_family_edge_support(
                    clean_cause,
                    clean_effect,
                    min_confidence=min_confidence,
                    limit=limit,
                )
            )

        merged: dict[tuple[str, str, str], EdgeSupportRecord] = {}
        for row in rows:
            key = (row.src, row.dst, row.direction)
            existing = merged.get(key)
            if existing is None:
                merged[key] = row
                continue
            article_refs = tuple(sorted({*existing.article_refs, *row.article_refs}))
            claim_refs = tuple(sorted({*existing.claim_refs, *row.claim_refs}))
            quality_flags = tuple(sorted({*existing.quality_flags, *row.quality_flags}))
            source_bindings = tuple(
                dict.fromkeys((*existing.source_bindings, *row.source_bindings))
            )
            evidence_strength = self._strongest_strength(
                existing.evidence_strength,
                row.evidence_strength,
            )
            merged[key] = EdgeSupportRecord(
                edge_id=existing.edge_id if existing.source_layer == "exact" else row.edge_id,
                src=row.src,
                dst=row.dst,
                direction=row.direction,
                confidence=max(existing.confidence, row.confidence),
                evidence_strength=evidence_strength,
                n_unique_works=max(existing.n_unique_works, row.n_unique_works, len(article_refs)),
                evidence_strength_status=(
                    ClaimVocabularyAxisStatus.CANDIDATE
                    if evidence_strength is not None
                    else ClaimVocabularyAxisStatus.NOT_ESTABLISHED
                ),
                n_claims=max(existing.n_claims, row.n_claims, len(claim_refs)),
                article_refs=article_refs,
                claim_refs=claim_refs,
                source_layer="hybrid",
                conflict_flag=bool(existing.conflict_flag or row.conflict_flag),
                quality_flags=quality_flags,
                dominant_direction_agreement=min(
                    existing.dominant_direction_agreement, row.dominant_direction_agreement
                ),
                positive_weight=max(existing.positive_weight, row.positive_weight),
                negative_weight=max(existing.negative_weight, row.negative_weight),
                mixed_weight=max(existing.mixed_weight, row.mixed_weight),
                strongest_dissent_strength=existing.strongest_dissent_strength
                or row.strongest_dissent_strength,
                strongest_dissent_year=existing.strongest_dissent_year
                or row.strongest_dissent_year,
                resolution_status=existing.resolution_status or row.resolution_status,
                source_bindings=source_bindings,
            )
        return sorted(merged.values(), key=lambda item: item.confidence, reverse=True)[:limit]

    def _query_exact_edge_support(
        self,
        cause: str,
        effect: str,
        *,
        min_confidence: float,
        limit: int,
    ) -> list[EdgeSupportRecord]:
        if not self._table_exists("ac_skg_edges"):
            return []
        rows = self._con.execute(
            """
            SELECT edge_id, src, dst, direction, n_articles, article_refs, evidence_strength, confidence
            FROM ac_skg_edges
            WHERE src = ? AND dst = ? AND confidence >= ?
            ORDER BY confidence DESC, edge_id ASC
            LIMIT ?
            """,
            [cause, effect, float(min_confidence), int(limit)],
        ).fetchall()
        out: list[EdgeSupportRecord] = []
        for row in rows:
            article_refs = tuple(self._parse_json_list(row[5]))
            out.append(
                EdgeSupportRecord(
                    edge_id=str(row[0]),
                    src=str(row[1]),
                    dst=str(row[2]),
                    direction=str(row[3]),
                    confidence=float(row[7]),
                    evidence_strength=self._decoded_evidence_strength(row[6]),
                    n_unique_works=int(row[4] or len(article_refs)),
                    evidence_strength_status=self._decoded_evidence_strength_status(row[6]),
                    article_refs=article_refs,
                    source_layer="exact",
                    source_bindings=(self._store.source_row_binding_for_edge("ac_skg_edges", str(row[0])),),
                )
            )
        return out

    def _query_contested_edge_support(
        self,
        cause: str,
        effect: str,
        *,
        min_confidence: float,
        limit: int,
    ) -> list[EdgeSupportRecord]:
        if not self._table_exists("ac_skg_contested_edges"):
            return []
        has_weighted_columns = self._column_exists("ac_skg_contested_edges", "positive_weight")
        rows = self._con.execute(
            f"""
            SELECT contested_edge_id, src_family, dst_family, n_articles, n_claims,
                   article_refs, claim_refs, dominant_direction, resolution_status,
                   runtime_support, evidence_strength, confidence,
                   {"positive_weight, negative_weight, mixed_weight, dominant_direction_agreement, strongest_dissent_strength, strongest_dissent_year," if has_weighted_columns else "0.0 AS positive_weight, 0.0 AS negative_weight, 0.0 AS mixed_weight, 0.0 AS dominant_direction_agreement, '' AS strongest_dissent_strength, NULL AS strongest_dissent_year,"}
                   direction_histogram_json, quality_signals_json
            FROM ac_skg_contested_edges
            WHERE src_family = ? AND dst_family = ? AND confidence >= ?
            ORDER BY confidence DESC, contested_edge_id ASC
            LIMIT ?
            """,
            [cause, effect, float(min_confidence), int(limit)],
        ).fetchall()
        out: list[EdgeSupportRecord] = []
        for row in rows:
            article_refs = tuple(self._parse_json_list(row[5]))
            claim_refs = tuple(self._parse_json_list(row[6]))
            quality_signals = self._parse_json_dict(row[19]) or {}
            resolution_status = str(row[8] or "")
            quality_flags = [f"resolution:{resolution_status}"] if resolution_status else []
            quality_flags.append("directional_conflict")
            if bool(quality_signals.get("family_edge_count")):
                quality_flags.append("family_synthesis")
            out.append(
                EdgeSupportRecord(
                    edge_id=str(row[0]),
                    src=str(row[1]),
                    dst=str(row[2]),
                    direction=str(row[7] or "mixed"),
                    confidence=float(row[11]),
                    evidence_strength=self._decoded_evidence_strength(row[10]),
                    n_unique_works=int(row[3] or len(article_refs)),
                    evidence_strength_status=self._decoded_evidence_strength_status(row[10]),
                    n_claims=int(row[4] or len(claim_refs)),
                    article_refs=article_refs,
                    claim_refs=claim_refs,
                    source_layer="contested",
                    conflict_flag=True,
                    quality_flags=tuple(quality_flags),
                    dominant_direction_agreement=float(row[15] or 0.0),
                    positive_weight=float(row[12] or 0.0),
                    negative_weight=float(row[13] or 0.0),
                    mixed_weight=float(row[14] or 0.0),
                    strongest_dissent_strength=str(row[16] or ""),
                    strongest_dissent_year=int(row[17]) if row[17] is not None else None,
                    resolution_status=resolution_status,
                    source_bindings=(self._store.source_row_binding_for_edge("ac_skg_contested_edges", str(row[0])),),
                )
            )
        return out

    def _query_family_edge_support(
        self,
        cause: str,
        effect: str,
        *,
        min_confidence: float,
        limit: int,
    ) -> list[EdgeSupportRecord]:
        if not self._table_exists("ac_skg_family_edges"):
            return []
        rows = self._con.execute(
            """
            SELECT family_edge_id, src_family, dst_family, direction, n_articles, n_claims,
                   article_refs, claim_refs, evidence_strength, confidence, quality_signals_json
            FROM ac_skg_family_edges
            WHERE src_family = ? AND dst_family = ? AND confidence >= ?
            ORDER BY confidence DESC, family_edge_id ASC
            LIMIT ?
            """,
            [cause, effect, float(min_confidence), int(limit)],
        ).fetchall()
        out: list[EdgeSupportRecord] = []
        for row in rows:
            article_refs = tuple(self._parse_json_list(row[6]))
            claim_refs = tuple(self._parse_json_list(row[7]))
            quality_signals = self._parse_json_dict(row[10]) or {}
            quality_flags: list[str] = []
            if bool(quality_signals.get("conflict_flag")):
                quality_flags.append("directional_conflict")
            out.append(
                EdgeSupportRecord(
                    edge_id=str(row[0]),
                    src=str(row[1]),
                    dst=str(row[2]),
                    direction=str(row[3]),
                    confidence=float(row[9]),
                    evidence_strength=self._decoded_evidence_strength(row[8]),
                    n_unique_works=int(row[4] or len(article_refs)),
                    evidence_strength_status=self._decoded_evidence_strength_status(row[8]),
                    n_claims=int(row[5] or len(claim_refs)),
                    article_refs=article_refs,
                    claim_refs=claim_refs,
                    source_layer="family",
                    conflict_flag=bool(quality_signals.get("conflict_flag")),
                    quality_flags=tuple(quality_flags),
                    dominant_direction_agreement=float(
                        quality_signals.get("direction_agreement") or 1.0
                    ),
                    resolution_status="moderated"
                    if bool(quality_signals.get("moderated_conflict"))
                    else "",
                    source_bindings=(self._store.source_row_binding_for_edge("ac_skg_family_edges", str(row[0])),),
                )
            )
        return out

    def query_edge_priors(
        self,
        *,
        min_confidence: float = 0.0,
        limit: int = 100,
        edge_layer: str = "exact",
    ) -> list[dict[str, object]]:
        return self.query_prior_for_variables(
            [],
            min_confidence=min_confidence,
            limit=limit,
            edge_layer=edge_layer,
        )

    @staticmethod
    def _parse_json_list(value: object) -> list[str]:
        try:
            payload = json.loads(str(value or "[]"))
        except (json.JSONDecodeError, ValueError, TypeError):
            return []
        if not isinstance(payload, list):
            return []
        result: list[str] = []
        for item in payload:
            text = str(item).strip()
            if text:
                result.append(text)
        return result

    @staticmethod
    def _parse_json_mixed_list(value: object) -> list[Any]:
        try:
            payload = json.loads(str(value or "[]"))
        except (json.JSONDecodeError, ValueError, TypeError):
            return []
        return payload if isinstance(payload, list) else []

    @staticmethod
    def _parse_json_dict(value: object) -> dict | None:
        if value in (None, ""):
            return None
        if isinstance(value, dict):
            return dict(value)
        try:
            payload = json.loads(str(value))
        except (json.JSONDecodeError, ValueError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    @staticmethod
    def _parse_json_list_or_number_pair(value: object) -> tuple[float, float] | None:
        try:
            payload = (
                json.loads(str(value or "[]")) if not isinstance(value, (list, tuple)) else value
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            return None
        if not isinstance(payload, (list, tuple)) or len(payload) != 2:
            return None
        try:
            lo = float(payload[0])
            hi = float(payload[1])
        except (TypeError, ValueError):
            return None
        return (lo, hi)

    @staticmethod
    def _safe_float(value: object) -> float | None:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    def _parameter_estimate_by_id(self, estimate_id: str) -> ParameterEstimateResult | None:
        clean_id = str(estimate_id or "").strip()
        if not clean_id or not self._table_exists("ac_parameter_estimates"):
            return None
        row = self._con.execute(
            """
            SELECT e.id, e.work_id, e.variable_name, e.estimate, e.ci_low, e.ci_high,
                   e.std_error, e.unit, e.domain, e.study_design, e.sample_size,
                   e.country, e.period_start, e.period_end, e.trust_score, e.raw_context,
                   COALESCE(w.title, '') AS work_title,
                   w.year
            FROM ac_parameter_estimates e
            LEFT JOIN ac_works w ON w.id = e.work_id
            WHERE e.id = ?
            LIMIT 1
            """,
            [clean_id],
        ).fetchone()
        if row is None:
            return None
        return ParameterEstimateResult(
            id=str(row[0] or ""),
            work_id=str(row[1] or ""),
            variable_name=str(row[2] or ""),
            estimate=float(row[3]),
            ci_low=None if row[4] is None else float(row[4]),
            ci_high=None if row[5] is None else float(row[5]),
            std_error=None if row[6] is None else float(row[6]),
            unit=str(row[7] or ""),
            domain=str(row[8] or ""),
            study_design=str(row[9] or ""),
            sample_size=None if row[10] is None else int(row[10]),
            country=str(row[11] or ""),
            period_start=None if row[12] is None else int(row[12]),
            period_end=None if row[13] is None else int(row[13]),
            trust_score=float(row[14] or 0.0),
            raw_context=str(row[15] or ""),
            work_title=str(row[16] or ""),
            work_year=None if row[17] is None else int(row[17]),
        )

    def _design_evidence_for_estimate(
        self,
        estimate: ParameterEstimateResult,
        *,
        design_tier_override: int | None,
    ) -> dict[str, Any]:
        tier = design_tier_override
        strong_design_evidence = False
        publish_blockers = ""
        if tier is None and estimate.work_id:
            row = self._con.execute(
                """
                SELECT MIN(design_quality_tier) AS design_quality_tier,
                       MAX(CASE WHEN strong_design_evidence THEN 1 ELSE 0 END) AS strong_design,
                       STRING_AGG(COALESCE(publish_blockers, ''), ';') AS publish_blockers
                FROM (
                    SELECT design_quality_tier, strong_design_evidence, '' AS publish_blockers
                    FROM ac_causal_claims
                    WHERE work_id = ? AND design_quality_tier IS NOT NULL
                    UNION ALL
                    SELECT design_quality_tier, strong_design_evidence, publish_blockers
                    FROM ac_claim_adjudications
                    WHERE work_id = ? AND design_quality_tier IS NOT NULL
                )
                """,
                [estimate.work_id, estimate.work_id],
            ).fetchone()
            if row and row[0] is not None:
                tier = int(row[0])
                strong_design_evidence = bool(row[1])
                publish_blockers = str(row[2] or "")
        tiers = self._design_quality_tier_taxonomy()
        tier_rank = tiers.index(tier) if tier in tiers else len(tiers)
        if tier is None:
            identification_mode = "proxy_identified"
        elif tier_rank == 0:
            identification_mode = "point_identified"
        elif tier_rank < max(1, len(tiers) - 1):
            identification_mode = "partially_identified"
        else:
            identification_mode = "proxy_identified"
        certified_rank_cap = max(0, len(tiers) // 2)
        assumptions = [
            "l2_identification_conditional_on_declared_design_assumptions",
            f"l2_design_tier:{'unresolved' if tier is None else tier}",
            f"l2_design_tier_rank:{tier_rank}",
        ]
        if strong_design_evidence:
            assumptions.append("l2_strong_design_evidence_declared")
        if publish_blockers.strip():
            assumptions.append("l2_publish_blockers_present")
        return {
            "tier": tier,
            "tier_rank": tier_rank,
            "certified_rank_cap": certified_rank_cap,
            "identification_mode": identification_mode,
            "assumptions": tuple(assumptions),
        }

    def _design_quality_tier_taxonomy(self) -> tuple[int, ...]:
        if not self._table_exists("ac_claim_adjudications") and not self._table_exists(
            "ac_causal_claims"
        ):
            return ()
        rows = self._con.execute(
            """
            SELECT DISTINCT design_quality_tier
            FROM (
                SELECT design_quality_tier FROM ac_causal_claims
                UNION ALL
                SELECT design_quality_tier FROM ac_claim_adjudications
            )
            WHERE design_quality_tier IS NOT NULL
            ORDER BY design_quality_tier ASC
            """
        ).fetchall()
        return tuple(int(row[0]) for row in rows if row[0] is not None)

    @staticmethod
    def _data_trust_from_score(score: float, *, authority_ref: str) -> DataTrust:
        bounded = SKGQuery._bounded_unit_interval(score)
        return DataTrust(
            tier="l2_numeric_trust",
            trust_cap=bounded,
            trust_multiplier=bounded,
            min_coverage=0.0,
            max_coverage=1.0,
            promotion_floor=0.2,
            authority_ref=authority_ref,
        )

    @staticmethod
    def _bounded_unit_interval(value: float) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _transport_widening_multiplier(record: EdgeTransportRecord) -> float:
        base = SKGQuery._bounded_unit_interval(record.base_confidence)
        confidence = SKGQuery._bounded_unit_interval(record.transport_confidence)
        generic_penalty = max(0.0, float(record.generic_penalty or 0.0))
        context_reward = max(0.0, float(record.context_match_reward or 0.0))
        mode_penalties = {
            "exact": 0.0,
            "claim_ref": 0.05,
            "moderator_match": 0.08,
            "profile_match": 0.10,
            "generic": 0.35,
            "weak": 0.45,
            "fallback": 0.55,
        }
        mode_penalty = mode_penalties.get(
            str(record.match_mode or "").strip().lower(),
            max(0.0, base - confidence),
        )
        transport_loss = max(0.0, base - confidence)
        uncertainty = transport_loss + generic_penalty + mode_penalty
        uncertainty = max(0.0, uncertainty - min(context_reward, 0.25))
        return 1.0 + min(4.0, max(0.05, uncertainty))

    def _transport_confidence_floor_from_data(self) -> float:
        """Return the L2-derived floor for scope transport admissibility."""

        if self._transport_confidence_floor is not None:
            return self._transport_confidence_floor
        if not self._table_exists("ac_skg_transport_scores"):
            self._transport_confidence_floor = 1.0
            return self._transport_confidence_floor
        try:
            row = self._con.execute(
                """
                SELECT COALESCE(QUANTILE_CONT(transport_confidence, 0.10), 1.0)
                FROM ac_skg_transport_scores
                WHERE transport_confidence IS NOT NULL
                """
            ).fetchone()
        except duckdb.Error:
            row = None
        self._transport_confidence_floor = self._bounded_unit_interval(
            1.0 if row is None or row[0] is None else float(row[0])
        )
        return self._transport_confidence_floor

    def _edge_content_match_score(
        self,
        *,
        requested_cause: str,
        requested_effect: str,
        record: EdgeSupportRecord,
    ) -> float:
        cause_score = self._resolved_variable_identity_score(requested_cause, record.src)
        effect_score = self._resolved_variable_identity_score(requested_effect, record.dst)
        return cause_score * effect_score

    def _resolved_variable_identity_score(self, requested: str, candidate: str) -> float:
        requested_aliases = self._variable_identity_aliases(requested)
        candidate_aliases = self._variable_identity_aliases(candidate)
        if not requested_aliases or not candidate_aliases:
            return 0.0
        if requested_aliases & candidate_aliases:
            return 1.0
        return max(
            self._variable_identity_score(left, right)
            for left in requested_aliases
            for right in candidate_aliases
        )

    def _variable_identity_aliases(self, value: str) -> set[str]:
        clean = str(value or "").strip()
        if not clean:
            return set()
        aliases = set(self._parameter_lookup_names(clean, need_type="causal_edge")[0])
        aliases.add(clean)
        return {item.strip().lower() for item in aliases if item.strip()}

    @staticmethod
    def _variable_identity_score(requested: str, candidate: str) -> float:
        requested_norm = str(requested or "").strip().lower()
        candidate_norm = str(candidate or "").strip().lower()
        if not requested_norm or not candidate_norm:
            return 0.0
        if requested_norm == candidate_norm:
            return 1.0
        requested_tokens = set(requested_norm.replace("_", ".").split("."))
        candidate_tokens = set(candidate_norm.replace("_", ".").split("."))
        if not requested_tokens or not candidate_tokens:
            return 0.0
        overlap = len(requested_tokens & candidate_tokens)
        union = len(requested_tokens | candidate_tokens)
        return overlap / union if union else 0.0

    @staticmethod
    def _edge_domain(src: str, dst: str) -> str:
        for candidate in (src, dst):
            token = str(candidate).strip()
            if "." in token:
                return token.split(".", 1)[0]
        return ""

    @staticmethod
    def _parse_context_profile(value: object) -> ContextProfile | None:
        payload = SKGQuery._parse_json_dict(value)
        if payload is None:
            return None
        try:
            return ContextProfile.model_validate(payload)
        except (ValidationError, ValueError, TypeError):
            return None

    @staticmethod
    def _linked_edge_refs(payload: list[Any]) -> tuple[str, ...]:
        refs: set[str] = set()
        for item in payload:
            if isinstance(item, str) and item.strip():
                refs.add(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            edge_id = str(item.get("edge_id") or "").strip()
            if edge_id:
                refs.add(edge_id)
                continue
            src = str(item.get("src") or "").strip()
            dst = str(item.get("dst") or "").strip()
            direction = str(item.get("direction") or "").strip()
            if src and dst:
                refs.add(f"{src}->{dst}" + (f":{direction}" if direction else ""))
        return tuple(sorted(refs))

    @staticmethod
    def _normalize_parameter_layer(layer: str) -> str:
        token = str(layer or "auto").strip().lower()
        if token not in {"auto", "simulation", "raw", "hybrid"}:
            return "auto"
        return token

    @staticmethod
    def _normalize_support_mode(mode: str) -> str:
        token = str(mode or "exact").strip().lower()
        if token in {"contested_summary", "contested"}:
            return "contested"
        if token not in {"exact", "family", "hybrid"}:
            return "exact"
        return token

    @staticmethod
    def _candidate_priority(candidate: ParameterCandidate) -> tuple[float, float, float, int]:
        strength_weight = EVIDENCE_WEIGHTS.get(
            candidate.parameter.evidence_strength.value,
            EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value],
        )
        layer_weight = {
            "simulation_ready": 1.0,
            "simulation": 1.0,
            "curated_numeric": 0.95,
            "raw_parameter": 0.65,
        }.get(candidate.source_layer, 0.75)
        uncertainty_bonus = (
            0.15
            if candidate.parameter.confidence_interval or candidate.parameter.std_error
            else 0.0
        )
        review_penalty = -0.1 if candidate.requires_expert_review else 0.0
        return (
            layer_weight + uncertainty_bonus + review_penalty,
            strength_weight,
            1.0 - float(candidate.transport_penalty or 0.0),
            len(candidate.linked_claim_ids),
        )

    @staticmethod
    def _strongest_strength(*values: str | None) -> str | None:
        present = [
            strength.value
            for value in values
            for strength, _ in (decode_edge_evidence_strength(value),)
            if strength is not None
        ]
        if not present:
            return None
        best = present[0]
        best_score = EVIDENCE_WEIGHTS.get(
            best, EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value]
        )
        for value in present[1:]:
            score = EVIDENCE_WEIGHTS.get(
                str(value), EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value]
            )
            if score > best_score:
                best = str(value)
                best_score = score
        return best

    @staticmethod
    def _decoded_evidence_strength(value: object) -> str | None:
        strength, _ = decode_edge_evidence_strength(value)
        return strength.value if strength is not None else None

    @staticmethod
    def _decoded_evidence_strength_status(value: object) -> ClaimVocabularyAxisStatus:
        _, status = decode_edge_evidence_strength(value)
        return status

    @staticmethod
    def _normalize_evidence_parameter_payload(
        name: str,
        payload: dict[str, Any],
        *,
        diagnostics: list[str] | None = None,
    ) -> dict[str, Any]:
        normalized = dict(payload)
        candidate_name = str(normalized.get("name") or "").strip()
        if not candidate_name:
            for key in ("parameter", "canonical_name", "variable", "variable_hint"):
                candidate_name = str(normalized.get(key) or "").strip()
                if candidate_name:
                    if diagnostics is not None:
                        diagnostics.append(f"mapped:{key}->name")
                    break
        normalized["name"] = candidate_name or name
        normalized.setdefault("display_name", normalized["name"])

        if (
            normalized.get("confidence_interval") is None
            and normalized.get("ci_low") is not None
            and normalized.get("ci_high") is not None
        ):
            normalized["confidence_interval"] = (
                normalized.get("ci_low"),
                normalized.get("ci_high"),
            )
            if diagnostics is not None:
                diagnostics.append("mapped:ci_low/ci_high->confidence_interval")

        context_snippet = str(normalized.get("context_snippet") or "").strip()
        if context_snippet and not normalized.get("heterogeneity_note"):
            normalized["heterogeneity_note"] = context_snippet
            if diagnostics is not None:
                diagnostics.append("mapped:context_snippet->heterogeneity_note")

        transfer_conditions = normalized.get("transfer_conditions")
        if isinstance(transfer_conditions, list):
            retained_conditions = [str(item) for item in transfer_conditions if str(item)]
        else:
            retained_conditions = []
        pattern_name = str(normalized.get("pattern_name") or "").strip()
        if pattern_name:
            retained_conditions.append(f"pattern:{pattern_name}")
            if diagnostics is not None:
                diagnostics.append("retained:pattern_name->transfer_conditions")
        variable_hint = str(normalized.get("variable_hint") or "").strip()
        if variable_hint and variable_hint != normalized["name"]:
            retained_conditions.append(f"variable_hint:{variable_hint}")
            if diagnostics is not None:
                diagnostics.append("retained:variable_hint->transfer_conditions")
        confidence = normalized.get("confidence")
        if confidence is not None:
            try:
                retained_conditions.append(f"extraction_confidence:{float(confidence):g}")
            except (TypeError, ValueError):
                retained_conditions.append(f"extraction_confidence:{confidence}")
            if diagnostics is not None:
                diagnostics.append("retained:confidence->transfer_conditions")
        if retained_conditions:
            normalized["transfer_conditions"] = sorted(set(retained_conditions))

        allowed_fields = set(EvidenceParameter.model_fields)
        canonical_payload = {
            key: value for key, value in normalized.items() if key in allowed_fields
        }
        if diagnostics is not None:
            known_alias_fields = {
                "canonical_name",
                "ci_high",
                "ci_low",
                "confidence",
                "context_snippet",
                "parameter",
                "pattern_name",
                "variable",
                "variable_hint",
            }
            for key in sorted(set(normalized) - allowed_fields - known_alias_fields):
                diagnostics.append(f"dropped:{key}")
        return canonical_payload

    @staticmethod
    def _to_evidence_parameter(
        name: str,
        payload: dict[str, Any],
        *,
        diagnostics: list[str] | None = None,
    ) -> EvidenceParameter | None:
        normalized_payload = SKGQuery._normalize_evidence_parameter_payload(
            name,
            payload,
            diagnostics=diagnostics,
        )
        try:
            return EvidenceParameter.model_validate(normalized_payload)
        except (ValidationError, ValueError, TypeError) as exc:
            logger.debug("EvidenceParameter.model_validate fallback: %s", exc)
            if diagnostics is not None:
                diagnostics.append(f"fallback:validation_failed:{type(exc).__name__}")

        raw_value = payload.get("value", payload.get("estimate"))
        if raw_value is None:
            if diagnostics is not None:
                diagnostics.append("dropped:missing_value")
            return None

        try:
            value = float(raw_value)
        except (ValueError, TypeError):
            if diagnostics is not None:
                diagnostics.append("dropped:non_numeric_value")
            return None

        confidence_interval: tuple[float, float] | None = None
        ci_payload = payload.get("confidence_interval")
        if isinstance(ci_payload, (list, tuple)) and len(ci_payload) == 2:
            try:
                confidence_interval = (float(ci_payload[0]), float(ci_payload[1]))
            except (ValueError, TypeError):
                confidence_interval = None
        elif payload.get("ci_low") is not None and payload.get("ci_high") is not None:
            try:
                confidence_interval = (
                    float(payload.get("ci_low")),
                    float(payload.get("ci_high")),
                )
            except (ValueError, TypeError):
                confidence_interval = None

        std_error_raw = payload.get("std_error")
        try:
            std_error = None if std_error_raw is None else float(std_error_raw)
        except (ValueError, TypeError):
            std_error = None

        evidence_strength_raw = payload.get("evidence_strength")
        try:
            evidence_strength = EvidenceStrength(str(evidence_strength_raw))
        except ValueError:
            evidence_strength = EvidenceStrength.UNKNOWN

        try:
            parameter = EvidenceParameter(
                name=name,
                display_name=str(payload.get("display_name") or name),
                parameter_type=ParameterType.QUANTITATIVE,
                value=value,
                confidence_interval=confidence_interval,
                std_error=std_error,
                unit=(
                    str(payload.get("unit")).strip()
                    if payload.get("unit") not in (None, "")
                    else None
                ),
                evidence_strength=evidence_strength,
                time_period=str(payload.get("time_period") or ""),
                geographic_scope=str(payload.get("geographic_scope") or ""),
            )
            if diagnostics is not None:
                diagnostics.append("fallback:manual_evidence_parameter")
            return parameter
        except (ValidationError, ValueError, TypeError):
            if diagnostics is not None:
                diagnostics.append("dropped:manual_fallback_validation_failed")
            return None

    def latest_skg_version_id(self) -> int | None:
        try:
            row = self._con.execute("SELECT MAX(version_id) FROM ac_skg_versions").fetchone()
        except duckdb.Error:
            return None
        if not row or row[0] is None:
            return None
        return int(row[0])

    def has_skg_version_id(self, *, version_id: int) -> bool:
        """Return whether the SKG store contains ``version_id``."""

        try:
            row = self._con.execute(
                "SELECT 1 FROM ac_skg_versions WHERE version_id = ? LIMIT 1",
                [int(version_id)],
            ).fetchone()
        except (duckdb.Error, TypeError, ValueError):
            return False
        return row is not None

    def skg_snapshot_ref(self, *, version_id: int | None = None) -> str | None:
        resolved_version = version_id if version_id is not None else self.latest_skg_version_id()
        if resolved_version is None:
            return None
        return f"duckdb://{self._db_path}#v{int(resolved_version)}"

    def parameter_estimate_value_outer_set(
        self,
        *,
        estimate_id: str,
        world_model_record_ref: str,
        epoch: str,
        trust_score_override: float | None = None,
        design_tier_override: int | None = None,
    ) -> ValueOuterSet:
        """Lower one real L2 parameter estimate into the GY-N-V carrier."""

        estimate = self._parameter_estimate_by_id(estimate_id)
        if estimate is None:
            raise ValueError(f"l2_parameter_estimate_unresolved:{estimate_id}")
        return self.lower_parameter_estimate_to_value_outer_set(
            estimate=estimate,
            world_model_record_ref=world_model_record_ref,
            epoch=epoch,
            trust_score_override=trust_score_override,
            design_tier_override=design_tier_override,
        )

    def lower_parameter_estimate_to_value_outer_set(
        self,
        *,
        estimate: ParameterEstimateResult,
        world_model_record_ref: str,
        epoch: str,
        trust_score_override: float | None = None,
        design_tier_override: int | None = None,
    ) -> ValueOuterSet:
        """Lower an L2 interval estimate without collapsing CI uncertainty to a point."""

        if estimate.ci_low is None or estimate.ci_high is None:
            raise ValueError(f"l2_parameter_estimate_ci_missing:{estimate.id}")
        lower = float(estimate.ci_low)
        upper = float(estimate.ci_high)
        if lower > upper:
            raise ValueError(f"l2_parameter_estimate_ci_invalid:{estimate.id}")
        design_evidence = self._design_evidence_for_estimate(
            estimate,
            design_tier_override=design_tier_override,
        )
        identification_mode = design_evidence["identification_mode"]
        assumptions = list(design_evidence["assumptions"])
        if upper > lower and identification_mode in {"point", "point_identified"}:
            identification_mode = "partial_identified"
            assumptions.append("l2_interval_estimate_identification_is_conditional")
        trust_score = (
            float(trust_score_override)
            if trust_score_override is not None
            else float(estimate.trust_score)
        )
        trust_score = self._bounded_unit_interval(trust_score)
        representation_status = (
            "certified"
            if upper > lower
            and trust_score >= 0.5
            and design_evidence["tier"] is not None
            and design_evidence["tier_rank"] <= design_evidence["certified_rank_cap"]
            else "search_only"
        )
        return ValueOuterSet.interval_box(
            coordinates=(estimate.variable_name,),
            lower=(lower,),
            upper=(upper,),
            identification_mode=identification_mode,
            assumptions=tuple(assumptions),
            assumption_status="declared",
            calibration_scope={
                "substrate": "L2:scholar_knowledge",
                "estimate_id": estimate.id,
                "work_id": estimate.work_id,
                "unit": estimate.unit,
                "country": estimate.country,
                "period_start": "" if estimate.period_start is None else str(estimate.period_start),
                "period_end": "" if estimate.period_end is None else str(estimate.period_end),
                "lowering_status": "parameter_estimate_ci_interval",
                "design_tier": "" if design_evidence["tier"] is None else str(design_evidence["tier"]),
            },
            data_trust=self._data_trust_from_score(
                trust_score,
                authority_ref=f"duckdb://{self._db_path}#ac_parameter_estimates/{estimate.id}",
            ),
            world_model_record_ref=world_model_record_ref,
            epoch=epoch,
            representation_status=representation_status,
        )

    def transport_value_outer_set(
        self,
        value_set: ValueOuterSet,
        *,
        edge_id: str,
        target_context_id: str,
    ) -> ValueOuterSet:
        """Apply real SKG transport as a bounded widening of an existing ValueOuterSet."""

        records = self.query_edge_transport([edge_id], target_context_id=target_context_id)
        if not records:
            return self.untransported_value_outer_set(
                value_set,
                edge_id=edge_id,
                target_context_id=target_context_id,
                reason="transport_unavailable_for_scope",
            )
        record = records[0]
        floor = self._transport_confidence_floor_from_data()
        if self._bounded_unit_interval(record.transport_confidence) < floor:
            return self.untransported_value_outer_set(
                value_set,
                edge_id=edge_id,
                target_context_id=target_context_id,
                reason="transport_confidence_below_floor",
                transport_record=record,
            )
        widening = self._transport_widening_multiplier(record)
        lower: list[float] = []
        upper: list[float] = []
        for lo, hi in zip(value_set.lower, value_set.upper, strict=True):
            width = max(float(hi) - float(lo), 1e-9)
            midpoint = (float(lo) + float(hi)) / 2.0
            widened_width = width * widening
            half_width = widened_width / 2.0
            lower.append(midpoint - half_width)
            upper.append(midpoint + half_width)
        identification_mode = (
            "proxy_identified"
            if value_set.identification_status in {"proxy", "blocked"}
            else "partially_identified"
        )
        assumptions = (
            *value_set.assumptions,
            f"l2_transport_edge:{record.edge_id}",
            f"l2_transport_target_context:{record.target_context_id}",
            f"l2_transport_confidence:{record.transport_confidence:.6f}",
        )
        calibration_scope = dict(value_set.calibration_scope)
        calibration_scope.update(
            {
                "transport_ref": (
                    f"duckdb://{self._db_path}#ac_skg_transport_scores/"
                    f"{record.edge_id}:{record.target_context_id}"
                ),
                "transport_edge_id": record.edge_id,
                "target_context_id": record.target_context_id,
                "transport_match_mode": record.match_mode,
                "transport_confidence": f"{record.transport_confidence:.12g}",
                "lowering_status": "transported_limited",
                "source_width": ",".join(f"{width:.12g}" for width in value_set.width),
                "widening_multiplier": f"{widening:.12g}",
            }
        )
        return ValueOuterSet.interval_box(
            coordinates=value_set.coordinates,
            lower=tuple(lower),
            upper=tuple(upper),
            identification_mode=identification_mode,
            assumptions=tuple(assumptions),
            assumption_status="declared",
            calibration_scope=calibration_scope,
            data_trust=self._data_trust_from_score(
                min(value_set.data_trust.effective_score, record.transport_confidence),
                authority_ref=calibration_scope["transport_ref"],
            ),
            world_model_record_ref=value_set.world_model_record_ref,
            epoch=value_set.epoch,
            representation_status=value_set.representation_status,
        )

    def untransported_value_outer_set(
        self,
        value_set: ValueOuterSet,
        *,
        edge_id: str,
        target_context_id: str,
        reason: str,
        transport_record: EdgeTransportRecord | None = None,
    ) -> ValueOuterSet:
        """Return a search-only, non-promotable bound for unavailable cross-scope transport."""

        lower: list[float] = []
        upper: list[float] = []
        floor = self._transport_confidence_floor_from_data()
        for lo, hi in zip(value_set.lower, value_set.upper, strict=True):
            lo_float = float(lo)
            hi_float = float(hi)
            width = max(hi_float - lo_float, 1e-9)
            midpoint = (lo_float + hi_float) / 2.0
            # Keep the interval finite for the ValueOuterSet carrier, but make the
            # lack of transport load-bearing through search_only + zero trust.
            untransported_width = width * (1.0 + 10.0 * max(0.1, 1.0 - floor))
            half_width = untransported_width / 2.0
            lower.append(midpoint - half_width)
            upper.append(midpoint + half_width)
        calibration_scope = dict(value_set.calibration_scope)
        calibration_scope.update(
            {
                "transport_edge_id": str(edge_id),
                "target_context_id": str(target_context_id),
                "lowering_status": "transport_unavailable_for_scope",
                "transport_reason": str(reason),
                "transport_confidence_floor": f"{floor:.12g}",
                "transport_confidence": (
                    ""
                    if transport_record is None
                    else f"{transport_record.transport_confidence:.12g}"
                ),
            }
        )
        if transport_record is not None:
            calibration_scope["transport_ref"] = (
                f"duckdb://{self._db_path}#ac_skg_transport_scores/"
                f"{transport_record.edge_id}:{transport_record.target_context_id}"
            )
        return ValueOuterSet.interval_box(
            coordinates=value_set.coordinates,
            lower=tuple(lower),
            upper=tuple(upper),
            identification_mode="unidentified",
            assumptions=(
                *value_set.assumptions,
                f"l2_transport_edge:{edge_id}",
                f"l2_transport_target_context:{target_context_id}",
                f"l2_transport_reason:{reason}",
            ),
            assumption_status="out_of_scope",
            calibration_scope=calibration_scope,
            data_trust=self._data_trust_from_score(
                0.0,
                authority_ref=(
                    f"duckdb://{self._db_path}#ac_skg_transport_scores/"
                    f"{edge_id}:{target_context_id}:untransported"
                ),
            ),
            world_model_record_ref=value_set.world_model_record_ref,
            epoch=value_set.epoch,
            representation_status="search_only",
        )

    def _contested_claim_rows(self, claim_refs: tuple[str, ...]) -> dict[str, dict[str, str]]:
        clean_refs = tuple(dict.fromkeys(ref for ref in claim_refs if str(ref).strip()))
        if not clean_refs:
            return {}
        placeholders = ", ".join(["?"] * len(clean_refs))
        claims: dict[str, dict[str, str]] = {}
        if self._table_exists("ac_causal_claims"):
            rows = self._con.execute(
                f"""
                SELECT id, work_id, cause, effect, direction
                FROM ac_causal_claims
                WHERE id IN ({placeholders})
                ORDER BY id ASC
                """,
                list(clean_refs),
            ).fetchall()
            for row in rows:
                claims[str(row[0])] = {
                    "work_id": str(row[1] or ""),
                    "cause": str(row[2] or ""),
                    "effect": str(row[3] or ""),
                    "direction": str(row[4] or ""),
                }
        if self._table_exists("ac_claim_adjudications"):
            rows = self._con.execute(
                f"""
                SELECT claim_id, work_id, cause, effect, claim_type
                FROM ac_claim_adjudications
                WHERE claim_id IN ({placeholders})
                ORDER BY claim_id ASC
                """,
                list(clean_refs),
            ).fetchall()
            for row in rows:
                claim_id = str(row[0])
                existing = claims.get(claim_id, {})
                claims[claim_id] = {
                    "work_id": existing.get("work_id") or str(row[1] or ""),
                    "cause": existing.get("cause") or str(row[2] or ""),
                    "effect": existing.get("effect") or str(row[3] or ""),
                    "direction": existing.get("direction") or str(row[4] or ""),
                }
        return claims

    def _parameter_estimates_for_work_ids(
        self,
        work_ids: tuple[str, ...],
    ) -> list[ParameterEstimateResult]:
        clean_work_ids = tuple(dict.fromkeys(work_id for work_id in work_ids if work_id))
        if not clean_work_ids:
            return []
        placeholders = ", ".join(["?"] * len(clean_work_ids))
        rows = self._con.execute(
            f"""
            SELECT e.id, e.work_id, e.variable_name, e.estimate, e.ci_low, e.ci_high,
                   e.std_error, e.unit, e.domain, e.study_design, e.sample_size,
                   e.country, e.period_start, e.period_end, e.trust_score,
                   e.raw_context, w.title, w.year
            FROM ac_parameter_estimates e
            LEFT JOIN ac_works w ON w.id = e.work_id
            WHERE e.work_id IN ({placeholders})
              AND e.ci_low IS NOT NULL
              AND e.ci_high IS NOT NULL
            ORDER BY e.work_id ASC, e.id ASC
            """,
            list(clean_work_ids),
        ).fetchall()
        estimates: list[ParameterEstimateResult] = []
        for row in rows:
            estimates.append(
                ParameterEstimateResult(
                    id=str(row[0] or ""),
                    work_id=str(row[1] or ""),
                    variable_name=str(row[2] or ""),
                    estimate=float(row[3]),
                    ci_low=None if row[4] is None else float(row[4]),
                    ci_high=None if row[5] is None else float(row[5]),
                    std_error=None if row[6] is None else float(row[6]),
                    unit=str(row[7] or ""),
                    domain=str(row[8] or ""),
                    study_design=str(row[9] or ""),
                    sample_size=None if row[10] is None else int(row[10]),
                    country=str(row[11] or ""),
                    period_start=None if row[12] is None else int(row[12]),
                    period_end=None if row[13] is None else int(row[13]),
                    trust_score=float(row[14] or 0.0),
                    raw_context=str(row[15] or ""),
                    work_title=str(row[16] or ""),
                    work_year=None if row[17] is None else int(row[17]),
                )
            )
        return estimates

    @staticmethod
    def _direction_sign(direction: str) -> int:
        direction_registry = {
            "positive": 1,
            "increase": 1,
            "negative": -1,
            "decrease": -1,
            "mixed": 0,
            "ambiguous": 0,
            "non_linear": 0,
            "nonlinear": 0,
        }
        return direction_registry.get(str(direction or "").strip().lower(), 0)

    def _oriented_contested_interval(
        self,
        *,
        estimate: ParameterEstimateResult,
        direction: str,
    ) -> tuple[float, float]:
        if estimate.ci_low is None or estimate.ci_high is None:
            raise ValueError(f"l2_contested_estimate_ci_missing:{estimate.id}")
        lo = float(estimate.ci_low)
        hi = float(estimate.ci_high)
        if lo > hi:
            lo, hi = hi, lo
        sign = self._direction_sign(direction)
        if sign > 0:
            return lo, hi
        magnitude = max(abs(lo), abs(hi), 1e-9)
        if sign < 0:
            return -magnitude, min(0.0, -min(abs(lo), abs(hi)))
        return -magnitude, magnitude

    def contested_edge_value_outer_set(
        self,
        *,
        contested_edge_id: str,
        world_model_record_ref: str,
        epoch: str,
    ) -> ValueOuterSet:
        """Lower a contested SKG edge into explicit structural ambiguity."""

        if not self._table_exists("ac_skg_contested_edges"):
            raise ValueError("l2_contested_edges_unavailable")
        id_column = (
            "edge_id"
            if self._column_exists("ac_skg_contested_edges", "edge_id")
            else "contested_edge_id"
        )
        src_column = (
            "src" if self._column_exists("ac_skg_contested_edges", "src") else "src_family"
        )
        dst_column = (
            "dst" if self._column_exists("ac_skg_contested_edges", "dst") else "dst_family"
        )
        row = self._con.execute(
            f"""
            SELECT {id_column}, {src_column}, {dst_column},
                   positive_weight, negative_weight, mixed_weight,
                   confidence, evidence_strength, claim_refs
            FROM ac_skg_contested_edges
            WHERE {id_column} = ?
            LIMIT 1
            """,
            [contested_edge_id],
        ).fetchone()
        if row is None:
            raise ValueError(f"l2_contested_edge_unresolved:{contested_edge_id}")
        confidence = self._bounded_unit_interval(float(row[6] or 0.0))
        claim_refs = tuple(self._parse_json_list(row[8]))
        if not claim_refs:
            raise ValueError(f"l2_contested_claim_refs_missing:{contested_edge_id}")
        claims = self._contested_claim_rows(claim_refs)
        work_ids = tuple(claim["work_id"] for claim in claims.values() if claim.get("work_id"))
        estimates = self._parameter_estimates_for_work_ids(work_ids)
        if not estimates:
            raise ValueError(f"l2_contested_estimates_unresolved:{contested_edge_id}")
        claim_by_work: dict[str, list[dict[str, str]]] = {}
        for claim in claims.values():
            work_id = claim.get("work_id", "")
            if work_id:
                claim_by_work.setdefault(work_id, []).append(claim)
        intervals: list[tuple[float, float]] = []
        estimate_refs: list[str] = []
        for estimate in estimates:
            claim_rows = claim_by_work.get(estimate.work_id) or [{"direction": ""}]
            for claim in claim_rows:
                intervals.append(
                    self._oriented_contested_interval(
                        estimate=estimate,
                        direction=claim.get("direction", ""),
                    )
                )
            estimate_refs.append(estimate.id)
        lower = min(lo for lo, _ in intervals)
        upper = max(hi for _, hi in intervals)
        if not lower < 0.0 < upper:
            spread = max(abs(lower), abs(upper), 1e-6)
            lower = -spread
            upper = spread
        resolved_claim_count = len(claims)
        return ValueOuterSet.interval_box(
            coordinates=(f"{row[1]}->{row[2]}",),
            lower=(lower,),
            upper=(upper,),
            identification_mode="proxy_identified",
            assumptions=(
                f"l2_contested_edge:{contested_edge_id}",
                "l2_structural_ambiguity_direction_disagreement",
                "l2_contested_envelope_from_claim_ref_estimates",
            ),
            assumption_status="declared",
            calibration_scope={
                "substrate": "L2:scholar_knowledge",
                "contested_edge_id": contested_edge_id,
                "source_variable": str(row[1]),
                "target_variable": str(row[2]),
                "claim_refs": json.dumps(sorted(claim_refs), sort_keys=True),
                "resolved_claim_count": str(resolved_claim_count),
                "estimate_refs": json.dumps(sorted(set(estimate_refs)), sort_keys=True),
                "estimate_count": str(len(set(estimate_refs))),
                "lowering_status": "structural_ambiguity_estimate_envelope",
            },
            data_trust=self._data_trust_from_score(
                confidence,
                authority_ref=f"duckdb://{self._db_path}#ac_skg_contested_edges/{contested_edge_id}",
            ),
            world_model_record_ref=world_model_record_ref,
            epoch=epoch,
            representation_status="search_only",
        )

    def resolve_grounded_causal_prior(
        self,
        *,
        cause: str,
        effect: str,
        estimand: str,
        scope_context_id: str,
        required_skg_version_id: int,
        min_relevance: float = 0.55,
    ) -> GroundedCausalPriorResolution:
        """Resolve, content-bind, and validate a candidate effect against SKG priors."""

        clean_cause = str(cause).strip()
        clean_effect = str(effect).strip()
        clean_scope = str(scope_context_id or "").strip()
        snapshot_ref = self.skg_snapshot_ref(version_id=required_skg_version_id) or ""
        blockers: list[str] = []
        if not self.has_skg_version_id(version_id=required_skg_version_id):
            blockers.append("skg_version_unresolved")
        if not clean_cause or not clean_effect:
            blockers.append("candidate_effect_unresolved")
        if blockers:
            return GroundedCausalPriorResolution(
                status="blocked",
                cause=clean_cause,
                effect=clean_effect,
                estimand=str(estimand),
                scope_context_id=clean_scope,
                skg_version_id=int(required_skg_version_id),
                skg_snapshot_ref=snapshot_ref,
                edge_id=None,
                relevance_score=0.0,
                content_bind_status="unbound",
                validation_status="failed_closed",
                blockers=tuple(blockers),
            )
        records = self.query_edge_support(
            cause=clean_cause,
            effect=clean_effect,
            min_confidence=0.0,
            support_mode="hybrid",
            limit=8,
        )
        scored: list[tuple[float, EdgeSupportRecord, EdgeTransportRecord | None]] = []
        untransported: list[
            tuple[float, EdgeSupportRecord, EdgeTransportRecord | None, tuple[str, ...]]
        ] = []
        transport_floor = self._transport_confidence_floor_from_data() if clean_scope else 0.0
        for record in records:
            content_score = self._edge_content_match_score(
                requested_cause=clean_cause,
                requested_effect=clean_effect,
                record=record,
            )
            if content_score <= 0.0:
                continue
            transport_record = None
            transport_score = 0.0
            if clean_scope:
                transports = self.query_edge_transport(
                    [record.edge_id],
                    target_context_id=clean_scope,
                )
                transport_record = transports[0] if transports else None
                if transport_record is None:
                    untransported.append(
                        (
                            0.55 * content_score
                            + 0.25 * self._bounded_unit_interval(record.confidence),
                            record,
                            None,
                            ("transport_unavailable_for_scope",),
                        )
                    )
                    continue
                transport_score = float(transport_record.transport_confidence)
                if self._bounded_unit_interval(transport_score) < transport_floor:
                    untransported.append(
                        (
                            0.55 * content_score
                            + 0.25 * self._bounded_unit_interval(record.confidence)
                            + 0.20 * self._bounded_unit_interval(transport_score),
                            record,
                            transport_record,
                            ("transport_confidence_below_floor",),
                        )
                    )
                    continue
            relevance = (
                0.55 * content_score
                + 0.25 * self._bounded_unit_interval(record.confidence)
                + 0.20 * self._bounded_unit_interval(transport_score)
            )
            scored.append((relevance, record, transport_record))
        if not scored:
            if untransported:
                relevance, best, transport_record, transport_blockers = max(
                    untransported,
                    key=lambda item: (item[0], item[1].confidence, item[1].edge_id),
                )
                transport_ref = (
                    None
                    if transport_record is None
                    else f"duckdb://{self._db_path}#ac_skg_transport_scores/"
                    f"{transport_record.edge_id}:{transport_record.target_context_id}"
                )
                return GroundedCausalPriorResolution(
                    status="search_only",
                    cause=clean_cause,
                    effect=clean_effect,
                    estimand=str(estimand),
                    scope_context_id=clean_scope,
                    skg_version_id=int(required_skg_version_id),
                    skg_snapshot_ref=snapshot_ref,
                    edge_id=best.edge_id,
                    relevance_score=relevance,
                    content_bind_status="content_bound_untransported",
                    validation_status="failed_closed",
                    blockers=transport_blockers,
                    transport_ref=transport_ref,
                    transport_confidence=(
                        None
                        if transport_record is None
                        else transport_record.transport_confidence
                    ),
                )
            return GroundedCausalPriorResolution(
                status="blocked",
                cause=clean_cause,
                effect=clean_effect,
                estimand=str(estimand),
                scope_context_id=clean_scope,
                skg_version_id=int(required_skg_version_id),
                skg_snapshot_ref=snapshot_ref,
                edge_id=None,
                relevance_score=0.0,
                content_bind_status="unbound",
                validation_status="failed_closed",
                blockers=("skg_prior_resolution_empty",),
            )
        relevance, best, transport_record = max(scored, key=lambda item: (item[0], item[1].confidence))
        if relevance < min_relevance:
            return GroundedCausalPriorResolution(
                status="blocked",
                cause=clean_cause,
                effect=clean_effect,
                estimand=str(estimand),
                scope_context_id=clean_scope,
                skg_version_id=int(required_skg_version_id),
                skg_snapshot_ref=snapshot_ref,
                edge_id=best.edge_id,
                relevance_score=relevance,
                content_bind_status="content_mismatch",
                validation_status="failed_closed",
                blockers=("skg_prior_relevance_below_threshold",),
            )
        transport_ref = (
            None
            if transport_record is None
            else f"duckdb://{self._db_path}#ac_skg_transport_scores/"
            f"{transport_record.edge_id}:{transport_record.target_context_id}"
        )
        return GroundedCausalPriorResolution(
            status="bound",
            cause=clean_cause,
            effect=clean_effect,
            estimand=str(estimand),
            scope_context_id=clean_scope,
            skg_version_id=int(required_skg_version_id),
            skg_snapshot_ref=snapshot_ref,
            edge_id=best.edge_id,
            relevance_score=relevance,
            content_bind_status="content_bound",
            validation_status="validated",
            blockers=(),
            transport_ref=transport_ref,
            transport_confidence=(
                None if transport_record is None else transport_record.transport_confidence
            ),
        )

    def query_prior_for_variables(
        self,
        variables: list[str],
        *,
        min_confidence: float = 0.0,
        limit: int = 256,
        domain: str | None = None,
        edge_layer: str = "exact",
    ) -> list[dict[str, object]]:
        expanded_variables: set[str] = set()
        for item in variables:
            clean_item = str(item).strip()
            if not clean_item:
                continue
            for candidate in self._parameter_lookup_names(clean_item, need_type="causal_edge")[0]:
                if candidate:
                    expanded_variables.add(candidate)
        clean_variables = sorted(expanded_variables)
        mode = self._normalize_support_mode(edge_layer)
        rows: list[dict[str, object]] = []
        if mode in {"exact", "hybrid"}:
            rows.extend(
                self._query_prior_rows_from_exact(
                    clean_variables=clean_variables,
                    min_confidence=min_confidence,
                    limit=limit,
                    domain=domain,
                )
            )
            if mode == "exact":
                return rows[:limit]
        if mode in {"family", "hybrid"}:
            rows.extend(
                self._query_prior_rows_from_family(
                    clean_variables=clean_variables,
                    min_confidence=min_confidence,
                    limit=limit,
                    domain=domain,
                )
            )

        merged: dict[tuple[str, str, str], dict[str, object]] = {}
        for row in rows:
            key = (str(row["src"]), str(row["dst"]), str(row["direction"]))
            existing = merged.get(key)
            if existing is None:
                merged[key] = row
                continue
            article_refs = sorted({*existing.get("article_refs", []), *row.get("article_refs", [])})
            quality_signals = {
                **dict(existing.get("quality_signals") or {}),
                **dict(row.get("quality_signals") or {}),
                "layers": sorted(
                    {
                        *existing.get("quality_signals", {}).get(
                            "layers", [existing.get("candidate_layer", "exact")]
                        ),
                        *row.get("quality_signals", {}).get(
                            "layers", [row.get("candidate_layer", "family")]
                        ),
                    }
                ),
            }
            evidence_strength = self._strongest_strength(
                existing.get("evidence_strength"),
                row.get("evidence_strength"),
            )
            merged[key] = {
                **existing,
                "edge_id": existing.get("edge_id") or row.get("edge_id"),
                "confidence": max(float(existing["confidence"]), float(row["confidence"])),
                "n_articles": max(
                    int(existing.get("n_articles") or 0),
                    int(row.get("n_articles") or 0),
                    len(article_refs),
                ),
                "article_refs": article_refs,
                "evidence_strength": evidence_strength,
                "evidence_strength_status": (
                    "candidate" if evidence_strength is not None else "not_established"
                ),
                "candidate_layer": "hybrid",
                "quality_signals": quality_signals,
            }
        ordered = sorted(merged.values(), key=lambda item: float(item["confidence"]), reverse=True)
        return ordered[:limit]

    def _query_prior_rows_from_exact(
        self,
        *,
        clean_variables: list[str],
        min_confidence: float,
        limit: int,
        domain: str | None,
    ) -> list[dict[str, object]]:
        if not self._table_exists("ac_skg_edges"):
            return []
        filters = ["confidence >= ?"]
        params: list[object] = [float(min_confidence)]
        if clean_variables:
            placeholders = ", ".join(["?"] * len(clean_variables))
            filters.insert(0, f"(src IN ({placeholders}) OR dst IN ({placeholders}))")
            params = [*clean_variables, *clean_variables, *params]
        if domain:
            filters.append("(src ILIKE ? OR dst ILIKE ?)")
            pattern = f"{domain.strip()}.%"
            params.extend([pattern, pattern])
        params.append(int(limit))

        has_candidate_layer = self._column_exists("ac_skg_edges", "candidate_layer")
        has_quality_json = self._column_exists("ac_skg_edges", "quality_signals_json")
        extra_select = ""
        if has_candidate_layer:
            extra_select += ", candidate_layer"
        if has_quality_json:
            extra_select += ", quality_signals_json"
        rows = self._con.execute(
            (
                "SELECT edge_id, src, dst, direction, n_articles, article_refs, "
                "evidence_strength, confidence, scope_conditions "
                f"{extra_select} "
                "FROM ac_skg_edges "
                f"WHERE {' AND '.join(filters)} "
                "ORDER BY confidence DESC, edge_id ASC "
                "LIMIT ?"
            ),
            params,
        ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            article_refs = self._parse_json_list(row[5])
            evidence_strength, evidence_strength_status = decode_edge_evidence_strength(row[6])
            payload = {
                "edge_id": str(row[0]),
                "src": str(row[1]),
                "dst": str(row[2]),
                "direction": str(row[3]),
                "n_articles": int(row[4] or len(article_refs)),
                "article_refs": article_refs,
                "scope_conditions": self._parse_json_list(row[8]),
                "evidence_strength": (
                    evidence_strength.value if evidence_strength is not None else None
                ),
                "evidence_strength_status": evidence_strength_status.value,
                "confidence": float(row[7]),
                "candidate_layer": "exact",
                "quality_signals": {"layers": ["exact"]},
            }
            idx = 9
            if has_candidate_layer:
                payload["candidate_layer"] = str(row[idx])
                idx += 1
            if has_quality_json:
                payload["quality_signals"] = self._parse_json_dict(row[idx]) or {
                    "layers": ["exact"]
                }
            result.append(payload)
        return result

    def _query_prior_rows_from_family(
        self,
        *,
        clean_variables: list[str],
        min_confidence: float,
        limit: int,
        domain: str | None,
    ) -> list[dict[str, object]]:
        if not self._table_exists("ac_skg_family_edges"):
            return []
        filters = ["confidence >= ?"]
        params: list[object] = [float(min_confidence)]
        if clean_variables:
            placeholders = ", ".join(["?"] * len(clean_variables))
            filters.insert(0, f"(src_family IN ({placeholders}) OR dst_family IN ({placeholders}))")
            params = [*clean_variables, *clean_variables, *params]
        if domain:
            pattern = f"{domain.strip()}.%"
            filters.append("(src_family ILIKE ? OR dst_family ILIKE ?)")
            params.extend([pattern, pattern])
        params.append(int(limit))
        rows = self._con.execute(
            (
                "SELECT family_edge_id, src_family, dst_family, direction, n_articles, article_refs, "
                "evidence_strength, confidence, quality_signals_json "
                "FROM ac_skg_family_edges "
                f"WHERE {' AND '.join(filters)} "
                "ORDER BY confidence DESC, family_edge_id ASC "
                "LIMIT ?"
            ),
            params,
        ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            evidence_strength, evidence_strength_status = decode_edge_evidence_strength(row[6])
            result.append(
                {
                    "edge_id": str(row[0]),
                    "src": str(row[1]),
                    "dst": str(row[2]),
                    "direction": str(row[3]),
                    "n_articles": int(row[4] or 0),
                    "article_refs": self._parse_json_list(row[5]),
                    "scope_conditions": [],
                    "evidence_strength": (
                        evidence_strength.value if evidence_strength is not None else None
                    ),
                    "evidence_strength_status": evidence_strength_status.value,
                    "confidence": float(row[7]),
                    "candidate_layer": "family",
                    "quality_signals": self._parse_json_dict(row[8]) or {"layers": ["family"]},
                }
            )
        return result

    def close(self) -> None:
        self._store.close()
        self._con.close()


__all__ = [
    "EdgeSupportRecord",
    "EdgeTransportRecord",
    "GroundedCausalPriorResolution",
    "LiteraturePriorResult",
    "ParameterCandidate",
    "SKGQuery",
]
