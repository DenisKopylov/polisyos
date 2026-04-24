"""Shared merge/checkpoint helpers for distributed runner tiers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from polisyos.common.logger import get_logger
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.engine.executor import _should_cache
from polisyos.scientist.engine.idempotency import NodeResultCache, compute_idempotency_key
from polisyos.scientist.engine.protocol import NodeOutcome
from polisyos.scientist.engine.runner.serialization import (
    deserialize_state,
    serialize_state,
)
from polisyos.scientist.engine.runner.state_merge import merge_tier_states
from polisyos.scientist.error_semantics import emit_degraded_path

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
) -> DistributedTierResult:
    """Merge distributed tier outcomes by declared writes and checkpoint merged state."""

    if not result_bytes_by_alias:
        return DistributedTierResult(
            state_bytes=base_state_bytes,
            completed_nodes=list(completed_nodes),
            cache_entry_refs={},
        )

    write_specs = _build_write_specs(
        tier_aliases=tier_aliases,
        invocations=invocations,
        registry=registry,
    )
    state_bytes = merge_tier_states(
        base_state_bytes,
        result_bytes_by_alias,
        write_specs=write_specs,
        conflict_policy=conflict_policy,
    )
    merged_state = deserialize_state(state_bytes)
    base_state = deserialize_state(base_state_bytes)
    cache_entry_refs = _persist_cache_entries(
        tier_aliases=tier_aliases,
        invocations=invocations,
        registry=registry,
        result_bytes_by_alias=result_bytes_by_alias,
        base_state=base_state,
        cache=cache,
        logger=logger,
    )

    merged_completed = list(completed_nodes)
    for alias in tier_aliases:
        if alias not in result_bytes_by_alias:
            continue
        merged_completed.append(alias)
        if checkpoint_hook is None:
            continue
        checkpoint_result = checkpoint_hook.on_node_complete(
            state=merged_state,
            alias=alias,
            node_id=str(invocations[alias].node_id),
            completed_nodes=list(merged_completed),
            workflow_id=workflow.workflow_id,
            workflow_fingerprint=workflow_fingerprint,
            cache_entry_ref=cache_entry_refs.get(alias),
        )
        if checkpoint_result is not None:
            merged_state = merged_state.model_copy(
                update={"last_checkpoint_ref": checkpoint_result.checkpoint_ref}
            )

    return DistributedTierResult(
        state_bytes=serialize_state(merged_state),
        completed_nodes=merged_completed,
        cache_entry_refs=cache_entry_refs,
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
    result_bytes_by_alias: dict[str, bytes],
    base_state: Any,
    cache: NodeResultCache | None,
    logger: logging.Logger,
) -> dict[str, ArtifactRef]:
    refs: dict[str, ArtifactRef] = {}
    if cache is None:
        return refs

    for alias in tier_aliases:
        result_bytes = result_bytes_by_alias.get(alias)
        if result_bytes is None:
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
                outcome=NodeOutcome(
                    status="ok",
                    state=deserialize_state(result_bytes),
                ),
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


__all__ = ["DistributedTierResult", "merge_and_checkpoint_tier", "seed_runner_cache"]
