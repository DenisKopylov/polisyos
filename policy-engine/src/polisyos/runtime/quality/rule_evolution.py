"""Compatibility facade for runtime rule-evolution contracts.

The shared, import-boundary-safe contract lives in
`polisyos.core.contracts.rule_evolution`. Runtime keeps this module as the
public experimental facade used by existing replay and closeout callers.
"""

from __future__ import annotations

from polisyos.core.contracts.rule_evolution import (
    RULE_EVOLUTION_CONTRACT_ID,
    RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION,
    RULE_EVOLUTION_RECORD_FAMILY,
    RULE_EVOLUTION_REGISTRY_KIND,
    RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION,
    RULE_EVOLUTION_REPLAY_SCHEMA_VERSION,
    build_rule_evolution_registry,
    build_rule_evolution_replay_context,
    logic_hash_for_rule,
    persist_rule_evolution_registry,
    public_rule_evolution_annotation,
)

__all__ = [
    "RULE_EVOLUTION_CONTRACT_ID",
    "RULE_EVOLUTION_PUBLIC_ANNOTATION_SCHEMA_VERSION",
    "RULE_EVOLUTION_RECORD_FAMILY",
    "RULE_EVOLUTION_REGISTRY_KIND",
    "RULE_EVOLUTION_REGISTRY_SCHEMA_VERSION",
    "RULE_EVOLUTION_REPLAY_SCHEMA_VERSION",
    "build_rule_evolution_registry",
    "build_rule_evolution_replay_context",
    "logic_hash_for_rule",
    "persist_rule_evolution_registry",
    "public_rule_evolution_annotation",
]
