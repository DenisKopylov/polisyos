"""Compatibility facade for Scientist-owned deterministic replay contracts.

New first-party consumers import :mod:`polisyos.scientist.replay.deterministic`.
This module preserves the historical Runtime import path with the exact same
public objects so downstream callers can migrate without ABI drift.
"""

from __future__ import annotations

from polisyos.scientist.replay import deterministic as _deterministic

CompletenessLevel = _deterministic.CompletenessLevel
CompletenessReport = _deterministic.CompletenessReport
MissingArtifact = _deterministic.MissingArtifact
ReplayBundleMeasurement = _deterministic.ReplayBundleMeasurement
ReplayPlan = _deterministic.ReplayPlan
ReplayStrategy = _deterministic.ReplayStrategy
SeedResolution = _deterministic.SeedResolution
VerificationConfig = _deterministic.VerificationConfig
VerificationMode = _deterministic.VerificationMode
VerificationResult = _deterministic.VerificationResult
build_replay_plan = _deterministic.build_replay_plan
compare_current_environment = _deterministic.compare_current_environment
completeness_check = _deterministic.completeness_check
determine_replay_strategy = _deterministic.determine_replay_strategy
measure_replayable_audit_bundle = _deterministic.measure_replayable_audit_bundle
normalize_artifact_id = _deterministic.normalize_artifact_id
resolve_effective_seed = _deterministic.resolve_effective_seed
set_global_seeds = _deterministic.set_global_seeds
try_parse_artifact_id = _deterministic.try_parse_artifact_id
verify_replay = _deterministic.verify_replay

__all__ = [
    "CompletenessLevel",
    "CompletenessReport",
    "MissingArtifact",
    "ReplayBundleMeasurement",
    "ReplayPlan",
    "ReplayStrategy",
    "SeedResolution",
    "VerificationConfig",
    "VerificationMode",
    "VerificationResult",
    "build_replay_plan",
    "compare_current_environment",
    "completeness_check",
    "determine_replay_strategy",
    "measure_replayable_audit_bundle",
    "normalize_artifact_id",
    "resolve_effective_seed",
    "set_global_seeds",
    "try_parse_artifact_id",
    "verify_replay",
]
