"""
Conflict resolution for multi-source data composition.

Implements policies for resolving conflicts when multiple sources provide
overlapping data for the same dimensions.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from polisyos.common.logger import get_logger
from polisyos.core.canon import content_hash
from polisyos.fabric.connectors.federation.types import (
    AuditLevel,
    ConflictCandidate,
    ConflictContext,
    ConflictPolicy,
    ConflictResolution,
    ConflictResolutionError,
    MergeLogEntry,
)
from polisyos.fabric.finite import is_finite_number

logger = get_logger(__name__)


class ConflictResolver:
    """
    Resolves conflicts when multiple sources provide overlapping data.

    Each policy implements a different resolution strategy. Resolutions can
    optionally emit merge log entries for transparency and auditability.
    """

    def __init__(
        self,
        policy: ConflictPolicy,
        *,
        tie_breaker_seed: str | None = None,
        store_logs: bool = False,
    ) -> None:
        """
        Initialize resolver with a specific policy.

        Args:
            policy: The conflict resolution policy to use
            tie_breaker_seed: Optional seed for deterministic tie-breaking
            store_logs: If True, keep an internal conflict log
        """
        self.policy = policy
        self._tie_breaker_seed = tie_breaker_seed
        self._store_logs = store_logs
        self._resolution_count = 0
        self._conflict_log: list[MergeLogEntry] = []

    def resolve_conflict(
        self,
        candidates: list[ConflictCandidate],
        context: ConflictContext,
        *,
        policy_override: ConflictPolicy | None = None,
        record_log: bool | None = None,
    ) -> ConflictResolution:
        """
        Resolve a conflict between multiple candidate values.

        Args:
            candidates: List of candidate values with metadata
            context: Additional context (row, column, request)
            policy_override: Override the resolver policy for this conflict
            record_log: If True, include a merge log entry in the result

        Returns:
            ConflictResolution with chosen value and reasoning

        Raises:
            ConflictResolutionError: If conflict cannot be resolved
        """
        if not candidates:
            raise ConflictResolutionError("Cannot resolve conflict with no candidates")

        policy = policy_override or self.policy

        # Filter out nulls if any non-null values exist
        effective_candidates = self._filter_null_candidates(candidates)

        if len(effective_candidates) == 1:
            chosen = effective_candidates[0]
            resolution = ConflictResolution(
                chosen_candidate=chosen,
                reasoning="single_source",
                all_candidates=candidates,
            )
        else:
            if policy == ConflictPolicy.TRUST_HIGHEST:
                resolution = self._resolve_by_trust(effective_candidates, context)
            elif policy == ConflictPolicy.MOST_RECENT:
                resolution = self._resolve_by_recency(effective_candidates, context)
            elif policy == ConflictPolicy.MANUAL_PRIORITY:
                resolution = self._resolve_by_manual_priority(
                    effective_candidates, context
                )
            elif policy == ConflictPolicy.MEDIAN:
                resolution = self._resolve_by_median(effective_candidates, context)
            elif policy == ConflictPolicy.FIRST_AVAILABLE:
                resolution = self._resolve_first_available(
                    effective_candidates, context
                )
            else:
                raise ConflictResolutionError(f"Unknown policy: {policy}")

        # Build log entry if requested
        should_log = record_log
        if should_log is None:
            should_log = self._store_logs or context.request.audit_level != AuditLevel.NONE

        if should_log:
            log_entry = self._build_log_entry(
                candidates=candidates,
                resolution=resolution,
                context=context,
                policy=policy,
            )
            resolution.log_entry = log_entry
            if self._store_logs:
                self._conflict_log.append(log_entry)

        self._resolution_count += 1
        return resolution

    def resolve_batch(
        self,
        conflicts: list[tuple[list[ConflictCandidate], ConflictContext]],
        *,
        policy_override: ConflictPolicy | None = None,
        record_log: bool | None = None,
    ) -> list[ConflictResolution]:
        """
        Resolve multiple conflicts in batch for performance.

        Args:
            conflicts: List of (candidates, context) tuples
            policy_override: Optional policy override for all conflicts
            record_log: Whether to record logs for all conflicts

        Returns:
            List of ConflictResolutions in same order
        """
        return [
            self.resolve_conflict(
                candidates,
                context,
                policy_override=policy_override,
                record_log=record_log,
            )
            for candidates, context in conflicts
        ]

    def _resolve_by_trust(
        self,
        candidates: list[ConflictCandidate],
        context: ConflictContext,
    ) -> ConflictResolution:
        """
        Resolve by preferring higher TrustLevel.

        Tie-breaking: MOST_RECENT, then deterministic hash.
        """
        highest_trust = max(c.metadata.metadata.trust_level for c in candidates)
        tied = [
            c for c in candidates if c.metadata.metadata.trust_level == highest_trust
        ]

        if len(tied) == 1:
            chosen = tied[0]
            reasoning = (
                f"TRUST_HIGHEST: {chosen.source_id} "
                f"({chosen.metadata.metadata.trust_level.name})"
            )
            return ConflictResolution(
                chosen_candidate=chosen,
                reasoning=reasoning,
                all_candidates=candidates,
            )

        # Tie-break by recency
        most_recent = self._resolve_by_recency(tied, context)
        if most_recent:
            most_recent.reasoning = (
                f"TRUST_HIGHEST (tie-break MOST_RECENT): {most_recent.reasoning}"
            )
            return most_recent

        # Final deterministic tie-break
        chosen = self._stable_tie_break(tied, context)
        reasoning = (
            f"TRUST_HIGHEST (stable tie-break): {chosen.source_id} "
            f"({chosen.metadata.metadata.trust_level.name})"
        )
        return ConflictResolution(
            chosen_candidate=chosen,
            reasoning=reasoning,
            all_candidates=candidates,
        )

    def _resolve_by_recency(
        self,
        candidates: list[ConflictCandidate],
        context: ConflictContext,
    ) -> ConflictResolution:
        """
        Resolve by preferring most recently updated data.
        """
        def recency(candidate: ConflictCandidate) -> datetime:
            return candidate.metadata.last_updated or candidate.metadata.fetched_at

        max_time = max(recency(c) for c in candidates)
        tied = [c for c in candidates if recency(c) == max_time]

        if len(tied) == 1:
            chosen = tied[0]
        else:
            chosen = self._stable_tie_break(tied, context)

        reasoning = (
            f"MOST_RECENT: {chosen.source_id} "
            f"(updated {recency(chosen).isoformat()})"
        )

        return ConflictResolution(
            chosen_candidate=chosen,
            reasoning=reasoning,
            all_candidates=candidates,
        )

    def _resolve_by_manual_priority(
        self,
        candidates: list[ConflictCandidate],
        context: ConflictContext,
    ) -> ConflictResolution:
        """
        Resolve using user-provided priority map.

        Higher priority number = higher preference.
        """
        priority_map = context.request.manual_priorities or {}

        max_priority = max(priority_map.get(c.source_id, 0) for c in candidates)
        tied = [c for c in candidates if priority_map.get(c.source_id, 0) == max_priority]

        if len(tied) == 1:
            chosen = tied[0]
        else:
            chosen = self._stable_tie_break(tied, context)

        reasoning = (
            f"MANUAL_PRIORITY: {chosen.source_id} "
            f"(priority={priority_map.get(chosen.source_id, 0)})"
        )

        return ConflictResolution(
            chosen_candidate=chosen,
            reasoning=reasoning,
            all_candidates=candidates,
        )

    def _resolve_by_median(
        self,
        candidates: list[ConflictCandidate],
        context: ConflictContext,
    ) -> ConflictResolution:
        """
        Resolve using statistical median.

        For numeric data: compute median of all values.
        For non-numeric: fall back to TRUST_HIGHEST unless strict.
        """
        numeric_values: list[float] = []
        numeric_candidates: list[ConflictCandidate] = []
        skipped_non_finite = 0

        for candidate in candidates:
            try:
                value = float(candidate.value)
                if is_finite_number(value):
                    numeric_values.append(value)
                    numeric_candidates.append(candidate)
                else:
                    skipped_non_finite += 1
            except (TypeError, ValueError):
                continue

        if skipped_non_finite and context.request.strict_conflicts:
            raise ConflictResolutionError(
                f"MEDIAN policy cannot resolve non-finite data for column {context.column}"
            )

        if not numeric_values:
            if context.request.strict_conflicts:
                raise ConflictResolutionError(
                    f"MEDIAN policy cannot handle non-numeric or non-finite data for column {context.column}"
                )
            logger.warning(
                "MEDIAN policy cannot handle non-numeric/non-finite data; falling back to TRUST_HIGHEST",
                column=context.column,
            )
            return self._resolve_by_trust(candidates, context)

        if skipped_non_finite:
            logger.warning(
                "MEDIAN policy ignored non-finite candidates",
                column=context.column,
                skipped=skipped_non_finite,
            )

        median_value = float(np.median(numeric_values))
        closest = [
            c for c in numeric_candidates if abs(float(c.value) - median_value) < 1e-10
        ]

        if closest:
            chosen = self._stable_tie_break(closest, context)
            reasoning = f"MEDIAN: {chosen.source_id} (value={chosen.value})"
        else:
            # Choose closest to median
            chosen = min(
                numeric_candidates,
                key=lambda c: abs(float(c.value) - median_value),
            )
            reasoning = (
                f"MEDIAN: {chosen.source_id} (value={chosen.value} "
                f"closest to median={median_value:.6g})"
            )

        return ConflictResolution(
            chosen_candidate=chosen,
            reasoning=reasoning,
            all_candidates=candidates,
        )

    def _resolve_first_available(
        self,
        candidates: list[ConflictCandidate],
        context: ConflictContext,
    ) -> ConflictResolution:
        """
        Resolve by taking first non-null value.

        Candidates are ordered deterministically.
        """
        ordered = self._order_for_first_available(candidates, context)
        for candidate in ordered:
            if not self._is_null(candidate.value):
                reasoning = f"FIRST_AVAILABLE: {candidate.source_id}"
                return ConflictResolution(
                    chosen_candidate=candidate,
                    reasoning=reasoning,
                    all_candidates=candidates,
                )

        # All null - take first
        chosen = ordered[0]
        reasoning = f"FIRST_AVAILABLE: {chosen.source_id} (all values null)"
        return ConflictResolution(
            chosen_candidate=chosen,
            reasoning=reasoning,
            all_candidates=candidates,
        )

    def _filter_null_candidates(
        self, candidates: list[ConflictCandidate]
    ) -> list[ConflictCandidate]:
        non_null = [c for c in candidates if not self._is_null(c.value)]
        return non_null if non_null else candidates

    @staticmethod
    def _is_null(value: Any) -> bool:
        try:
            return pd.isna(value)
        except Exception:
            return value is None

    def _order_for_first_available(
        self,
        candidates: list[ConflictCandidate],
        context: ConflictContext,
    ) -> list[ConflictCandidate]:
        priority_map = context.request.manual_priorities or {}
        if priority_map:
            return sorted(
                candidates,
                key=lambda c: priority_map.get(c.source_id, 0),
                reverse=True,
            )
        return sorted(candidates, key=lambda c: c.source_id)

    def _stable_tie_break(
        self,
        candidates: list[ConflictCandidate],
        context: ConflictContext,
    ) -> ConflictCandidate:
        seed = (
            context.request.tie_breaker_seed
            or self._tie_breaker_seed
            or ""
        )

        def stable_key(candidate: ConflictCandidate) -> int:
            row_key = context.row_key or candidate.row_key or {}
            payload = {
                "seed": seed,
                "source_id": candidate.source_id,
                "row_key": row_key,
                "column": context.column or "",
            }
            encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
            return int(content_hash(encoded), 16)

        return min(candidates, key=stable_key)

    def _build_log_entry(
        self,
        candidates: list[ConflictCandidate],
        resolution: ConflictResolution,
        context: ConflictContext,
        policy: ConflictPolicy,
    ) -> MergeLogEntry:
        """
        Create a MergeLogEntry for this resolution.
        """
        if not candidates:
            raise ConflictResolutionError("Cannot log conflict with no candidates")

        source_a = candidates[0]
        source_b = candidates[1] if len(candidates) > 1 else candidates[0]

        row_key = context.row_key or source_a.row_key or source_b.row_key

        return MergeLogEntry(
            row_index=context.row_index,
            row_key=row_key,
            column=context.column,
            conflict_type=context.conflict_type,
            source_a_id=source_a.source_id,
            source_a_value=source_a.value,
            source_a_trust=source_a.metadata.metadata.trust_level,
            source_b_id=source_b.source_id,
            source_b_value=source_b.value,
            source_b_trust=source_b.metadata.metadata.trust_level,
            chosen_source=resolution.chosen_candidate.source_id,
            chosen_value=resolution.chosen_candidate.value,
            resolution_reason=resolution.reasoning,
            resolution_policy=policy.value,
            timestamp=None,
        )

    def get_conflict_log(self) -> list[MergeLogEntry]:
        """Get all logged conflict resolutions."""
        return self._conflict_log.copy()

    def reset_log(self) -> None:
        """Clear conflict log (useful for testing)."""
        self._conflict_log.clear()
        self._resolution_count = 0

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about conflict resolutions."""
        return {
            "policy": self.policy.value,
            "total_resolutions": self._resolution_count,
            "logged_conflicts": len(self._conflict_log),
            "sources_involved": len(
                {
                    source_id
                    for entry in self._conflict_log
                    for source_id in [entry.source_a_id, entry.source_b_id]
                }
            ),
        }
