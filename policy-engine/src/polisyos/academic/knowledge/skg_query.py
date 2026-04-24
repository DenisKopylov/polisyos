"""Topic/run-aware SKG query helpers for SCM stages."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
from pydantic import ValidationError

from polisyos.academic.knowledge.canonical_resolver import (
    CanonicalVariableResolver,
    ResolutionResult,
)
from polisyos.academic.knowledge.skg_store import EVIDENCE_WEIGHTS, parent_canonical_name
from polisyos.academic.knowledge.store import ScholarKnowledgeStore
from polisyos.academic.knowledge.types import (
    BoundaryConditionResult,
    CausalClaimResult,
    ParameterEstimateResult,
    ParameterPrior,
)
from polisyos.common.logger import get_logger
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import (
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


@dataclass(frozen=True)
class EdgeSupportRecord:
    """Summarize the evidence currently supporting one SKG edge after claim/article synthesis."""

    edge_id: str
    src: str
    dst: str
    direction: str
    confidence: float
    evidence_strength: str
    n_unique_works: int
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


class SKGQuery:
    """Read-only query API for SKG tables in academic DuckDB."""

    def __init__(self, db_path: Path, index_dir: Path) -> None:
        self._db_path = Path(db_path)
        self._store = ScholarKnowledgeStore(db_path, index_dir)
        self._con = duckdb.connect(str(db_path), read_only=True)
        self._resolver: CanonicalVariableResolver | None = None

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
            CausalClaimResult(
                id=row.edge_id,
                work_id=row.article_refs[0] if row.article_refs else "",
                cause=row.src,
                effect=row.dst,
                direction=row.direction,
                strength=row.evidence_strength,
                mechanism=(
                    "contested_summary" if mode == "contested" else f"{row.source_layer}_support"
                ),
                domain=self._edge_domain(row.src, row.dst),
                trust_score=row.confidence,
                work_title=f"{row.n_unique_works} work(s) synthesized",
                work_year=None,
            )
            for row in rows
        ]

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
            parameter = self._to_evidence_parameter(parameter_name, payload)
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
        if resolved is not None and resolved.canonical_name:
            candidates.extend(self._observed_names_for_approved_canonical(resolved.canonical_name))
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
        rows = self._con.execute(
            f"""
            SELECT edge_id, target_context_id, transport_confidence, match_mode,
                   matched_moderators_json, generic_penalty, context_match_reward
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
            merged[key] = EdgeSupportRecord(
                edge_id=existing.edge_id if existing.source_layer == "exact" else row.edge_id,
                src=row.src,
                dst=row.dst,
                direction=row.direction,
                confidence=max(existing.confidence, row.confidence),
                evidence_strength=self._strongest_strength(
                    existing.evidence_strength,
                    row.evidence_strength,
                ),
                n_unique_works=max(existing.n_unique_works, row.n_unique_works, len(article_refs)),
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
                    evidence_strength=str(row[6]),
                    n_unique_works=int(row[4] or len(article_refs)),
                    article_refs=article_refs,
                    source_layer="exact",
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
                    evidence_strength=str(row[10]),
                    n_unique_works=int(row[3] or len(article_refs)),
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
                    evidence_strength=str(row[8]),
                    n_unique_works=int(row[4] or len(article_refs)),
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
    def _strongest_strength(*values: str) -> str:
        best = EvidenceStrength.UNKNOWN.value
        best_score = EVIDENCE_WEIGHTS[best]
        for value in values:
            score = EVIDENCE_WEIGHTS.get(
                str(value), EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value]
            )
            if score > best_score:
                best = str(value)
                best_score = score
        return best

    @staticmethod
    def _to_evidence_parameter(name: str, payload: dict[str, Any]) -> EvidenceParameter | None:
        try:
            return EvidenceParameter.model_validate(payload)
        except (ValidationError, ValueError, TypeError) as exc:
            logger.debug("EvidenceParameter.model_validate fallback: %s", exc)

        raw_value = payload.get("value", payload.get("estimate"))
        if raw_value is None:
            return None

        try:
            value = float(raw_value)
        except (ValueError, TypeError):
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
            return EvidenceParameter(
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
        except (ValidationError, ValueError, TypeError):
            return None

    def latest_skg_version_id(self) -> int | None:
        try:
            row = self._con.execute("SELECT MAX(version_id) FROM ac_skg_versions").fetchone()
        except duckdb.Error:
            return None
        if not row or row[0] is None:
            return None
        return int(row[0])

    def skg_snapshot_ref(self, *, version_id: int | None = None) -> str | None:
        resolved_version = version_id if version_id is not None else self.latest_skg_version_id()
        if resolved_version is None:
            return None
        return f"duckdb://{self._db_path}#v{int(resolved_version)}"

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
                "evidence_strength": self._strongest_strength(
                    str(existing.get("evidence_strength") or ""),
                    str(row.get("evidence_strength") or ""),
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
            payload = {
                "edge_id": str(row[0]),
                "src": str(row[1]),
                "dst": str(row[2]),
                "direction": str(row[3]),
                "n_articles": int(row[4] or len(article_refs)),
                "article_refs": article_refs,
                "scope_conditions": self._parse_json_list(row[8]),
                "evidence_strength": str(row[6]),
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
            result.append(
                {
                    "edge_id": str(row[0]),
                    "src": str(row[1]),
                    "dst": str(row[2]),
                    "direction": str(row[3]),
                    "n_articles": int(row[4] or 0),
                    "article_refs": self._parse_json_list(row[5]),
                    "scope_conditions": [],
                    "evidence_strength": str(row[6]),
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
    "LiteraturePriorResult",
    "ParameterCandidate",
    "SKGQuery",
]
