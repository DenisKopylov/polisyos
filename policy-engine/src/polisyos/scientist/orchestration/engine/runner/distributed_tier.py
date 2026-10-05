"""Shared merge/checkpoint helpers for distributed runner tiers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path
from polisyos.scientist.orchestration.engine.executor import _should_cache
from polisyos.scientist.orchestration.engine.idempotency import (
    NodeResultCache,
    compute_idempotency_key,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.runner.serialization import (
    NativeNodeOutcomeBatch,
    deserialize_outcome_batch,
    deserialize_state,
    serialize_state,
)
from polisyos.scientist.orchestration.engine.runner.state_merge import (
    merge_tier_outcomes,
    merge_tier_states,
    validate_tier_result_aliases,
)

if False:  # pragma: no cover
    pass

_DISTRIBUTED_TIER_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValidationError,
    ValueError,
)
_module_logger = get_logger(__name__)


@dataclass(frozen=True)
class DistributedTierResult:
    """Merged tier state plus checkpoint/cache bookkeeping."""

    state_bytes: bytes
    completed_nodes: list[str]
    cache_entry_refs: dict[str, ArtifactRef]
    node_outcomes: dict[str, NodeOutcome]
    should_abort: bool


def seed_runner_cache(
    *,
    store: Any,
    run_id: str,
    checkpoint_cache_seed_refs: list[ArtifactRef] | None,
    logger: logging.Logger,
) -> NodeResultCache:
    """Restore runner-local node cache from checkpoint refs when available."""

    cache = NodeResultCache(store, run_id=run_id)
    restored = cache.seed_from_entry_refs(list(checkpoint_cache_seed_refs or []))
    if restored:
        logger.info("Recovered %s cached outcomes from checkpoint refs", restored)
    return cache


def project_distributed_node_outcomes(
    *,
    workflow: Any,
    tier_aliases: list[str],
    outcome_bytes_by_alias: dict[str, bytes],
) -> dict[str, dict[str, Any]]:
    """Reduce one tier's full outcomes to report fields without retaining node state."""

    from polisyos.scientist.orchestration.engine.executor import (
        NodeRunRecord,
        _outcome_skip_reason,
        _skip_blocker_for_outcome,
    )

    validate_tier_result_aliases(
        requested_aliases=tier_aliases,
        result_aliases=outcome_bytes_by_alias,
    )
    outcomes = deserialize_outcome_batch(outcome_bytes_by_alias).outcomes
    invocations = {invocation.alias: invocation for invocation in workflow.nodes}
    reports: dict[str, dict[str, Any]] = {}
    for alias, outcome in outcomes.items():
        invocation = invocations.get(alias)
        if invocation is None:
            continue
        reports[alias] = NodeRunRecord(
            alias=alias,
            node_id=str(invocation.node_id),
            status=outcome.status,
            duration_ms=0,
            artifacts=list(outcome.artifacts),
            error=outcome.error,
            skip_reason=(
                _outcome_skip_reason(outcome) if outcome.status == "skip" else None
            ),
            skip_blocker=_skip_blocker_for_outcome(
                alias=alias,
                node_id=str(invocation.node_id),
                outcome=outcome,
            ),
        ).model_dump(mode="json")
    return reports


def build_distributed_execution_result(
    *,
    workflow: Any,
    run_id: str,
    state_bytes: bytes,
    node_reports_by_alias: dict[str, dict[str, Any]],
) -> Any:
    """Build the workflow result from state and compact per-node report projections."""

    from polisyos.scientist.orchestration.engine.executor import (
        NodeRunRecord,
        WorkflowExecutionResult,
        WorkflowReport,
    )

    records = [
        NodeRunRecord.model_validate(node_reports_by_alias[invocation.alias])
        for invocation in workflow.nodes
        if invocation.alias in node_reports_by_alias
    ]
    status = "fail" if any(record.status == "fail" for record in records) else "ok"
    return WorkflowExecutionResult(
        state=deserialize_state(state_bytes),
        report=WorkflowReport(
            workflow_id=workflow.workflow_id,
            run_id=run_id,
            error_policy=workflow.error_policy,
            status=status,
            nodes=records,
        ),
    )


def merge_and_checkpoint_tier(
    *,
    workflow: Any,
    tier_aliases: list[str],
    invocations: dict[str, Any],
    result_bytes_by_alias: dict[str, bytes],
    base_state_bytes: bytes,
    registry: Any,
    checkpoint_hook: Any | None,
    cache: NodeResultCache | None,
    completed_nodes: list[str],
    workflow_fingerprint: str,
    conflict_policy: Any,
    logger: logging.Logger,
    result_format: Literal["node_outcome", "state"] = "node_outcome",
) -> DistributedTierResult:
    """Merge distributed tier outcomes by declared writes and checkpoint merged state."""

    validate_tier_result_aliases(
        requested_aliases=tier_aliases,
        result_aliases=result_bytes_by_alias,
    )
    if not result_bytes_by_alias:
        return DistributedTierResult(
            state_bytes=base_state_bytes,
            completed_nodes=list(completed_nodes),
            cache_entry_refs={},
            node_outcomes={},
            should_abort=False,
        )

    write_specs = _build_write_specs(
        tier_aliases=tier_aliases,
        invocations=invocations,
        registry=registry,
    )
    if result_format == "state":
        state_bytes = merge_tier_states(
            base_state_bytes,
            result_bytes_by_alias,
            write_specs=write_specs,
            conflict_policy=conflict_policy,
        )
        node_outcomes: dict[str, NodeOutcome] = {}
        status_evidence: NativeNodeOutcomeBatch | None = None
        should_abort = False
    else:
        outcome_merge = merge_tier_outcomes(
            base_state_bytes,
            result_bytes_by_alias,
            requested_aliases=tier_aliases,
            write_specs=write_specs,
            conflict_policy=conflict_policy,
        )
        node_outcomes = outcome_merge.node_outcomes
        status_evidence = outcome_merge.status_evidence
        has_failure = any(outcome.status == "fail" for outcome in node_outcomes.values())
        should_abort = has_failure and workflow.error_policy == "fail_fast"
        state_bytes = base_state_bytes if should_abort else outcome_merge.state_bytes
    merged_state = deserialize_state(state_bytes)
    base_state = deserialize_state(base_state_bytes)
    status_verified_successes = (
        status_evidence.successful_outcomes if status_evidence is not None else {}
    )
    successful_aliases = [
        alias for alias in tier_aliases if alias in status_verified_successes
    ]
    cache_entry_refs = (
        _persist_cache_entries(
            tier_aliases=successful_aliases,
            invocations=invocations,
            registry=registry,
            node_outcomes=node_outcomes,
            status_evidence=status_evidence,
            base_state=base_state,
            cache=cache,
            logger=logger,
        )
        if not should_abort
        else {}
    )

    checkpoint_aliases = (
        successful_aliases
        if status_evidence is not None
        else [alias for alias in tier_aliases if alias in result_bytes_by_alias]
    )
    merged_completed = list(completed_nodes)
    if not should_abort:
        merged_completed.extend(checkpoint_aliases)

    if checkpoint_hook is not None and checkpoint_aliases and not should_abort:
        if status_evidence is None:
            mark_unestablished = getattr(
                checkpoint_hook,
                "mark_completed_node_status_unestablished",
                None,
            )
            if not callable(mark_unestablished):
                raise ValueError("checkpoint_completed_node_status_not_established")
            mark_unestablished()
        elif successful_aliases:
            mark_established = getattr(
                checkpoint_hook,
                "mark_completed_node_status_established",
                None,
            )
            if callable(mark_established):
                mark_established(prior_completed_nodes=list(completed_nodes))

        alias = checkpoint_aliases[-1]
        tier_checkpoint = getattr(checkpoint_hook, "on_tier_complete", None)
        if callable(tier_checkpoint):
            checkpoint_result = tier_checkpoint(
                state=merged_state,
                alias=alias,
                node_id=str(invocations[alias].node_id),
                completed_nodes=list(merged_completed),
                workflow_id=workflow.workflow_id,
                workflow_fingerprint=workflow_fingerprint,
                cache_entry_refs=[
                    cache_entry_refs[successful_alias]
                    for successful_alias in successful_aliases
                    if successful_alias in cache_entry_refs
                ],
            )
        else:
            # Legacy hooks accept one node callback. Publish one complete frontier
            # at the final successful alias; never expose a prefix for a finished tier.
            node_checkpoint = getattr(checkpoint_hook, "on_node_complete", None)
            checkpoint_result = (
                node_checkpoint(
                    state=merged_state,
                    alias=alias,
                    node_id=str(invocations[alias].node_id),
                    completed_nodes=list(merged_completed),
                    workflow_id=workflow.workflow_id,
                    workflow_fingerprint=workflow_fingerprint,
                    cache_entry_ref=cache_entry_refs.get(alias),
                )
                if callable(node_checkpoint)
                else None
            )
        if checkpoint_result is not None:
            merged_state = merged_state.model_copy(
                update={"last_checkpoint_ref": checkpoint_result.checkpoint_ref}
            )

    return DistributedTierResult(
        state_bytes=serialize_state(merged_state),
        completed_nodes=merged_completed,
        cache_entry_refs=cache_entry_refs,
        node_outcomes=node_outcomes,
        should_abort=should_abort,
    )


def _build_write_specs(
    *,
    tier_aliases: list[str],
    invocations: dict[str, Any],
    registry: Any,
) -> dict[str, list[str]]:
    specs: dict[str, list[str]] = {}
    for alias in tier_aliases:
        if alias not in invocations:
            continue
        node = registry.get(invocations[alias].node_id)
        specs[alias] = list(getattr(node.spec, "state_writes", ()))
    return specs


def _persist_cache_entries(
    *,
    tier_aliases: list[str],
    invocations: dict[str, Any],
    registry: Any,
    node_outcomes: dict[str, NodeOutcome],
    status_evidence: NativeNodeOutcomeBatch | None,
    base_state: Any,
    cache: NodeResultCache | None,
    logger: logging.Logger,
) -> dict[str, ArtifactRef]:
    refs: dict[str, ArtifactRef] = {}
    if cache is None or status_evidence is None:
        return refs

    for alias in tier_aliases:
        outcome = node_outcomes.get(alias)
        if (
            outcome is None
            or not status_evidence.admits_success(alias, outcome)
        ):
            continue
        invocation = invocations[alias]
        node_id = str(invocation.node_id)
        if not _should_cache(node_id):
            continue
        try:
            node = registry.get(invocation.node_id)
            cache_key = compute_idempotency_key(
                spec=node.spec,
                state=base_state,
                bind_params=invocation.params,
            )
            refs[alias] = cache.put(
                cache_key,
                node_id=node_id,
                outcome=outcome,
            )
        except _DISTRIBUTED_TIER_ERRORS as exc:
            emit_degraded_path(
                component="engine.runner.distributed_tier",
                operation="store_cache_entry",
                reason="cache_bypass",
                exc=exc,
                details={"alias": alias, "node_id": node_id},
                log=_module_logger,
            )
    return refs


__all__ = [
    "DistributedTierResult",
    "build_distributed_execution_result",
    "merge_and_checkpoint_tier",
    "project_distributed_node_outcomes",
    "seed_runner_cache",
]
