"""Benchmark authority policy facade over `BenchmarkRegistry`."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.scientist.evals.datasets import (
    BenchmarkStalenessPolicy,
    stale_entries_for_refs,
)
from polisyos.scientist.evals.leakage import hidden_benchmark_ref_ids
from polisyos.scientist.search.benchmark_registry import (
    BenchmarkRegistry,
    BenchmarkRegistryEntry,
    FrontierBenchmarkBundle,
)

__all__ = [
    "BenchmarkAuthority",
    "BenchmarkAuthorityVerdict",
    "PromotionEvidenceRequest",
]


class PromotionEvidenceRequest(BaseModel):
    """Request benchmark evidence required for a readiness or promotion decision."""

    model_config = ConfigDict(extra="forbid")

    family: str = Field(min_length=1)
    claim_mode: Literal["proof_only", "bounds", "estimation"]
    readiness_target: str | None = None
    query_type: str | None = None
    estimator_name: str | None = None
    capability_id: str | None = None
    workflow_id: str | None = None
    risk_tier: Literal["low", "medium", "high"] = "medium"
    run_id: str | None = None
    loop_id: str | None = None
    benchmark_pack_ref: ArtifactRef | None = None
    registry_lookup_required: bool = True


class BenchmarkAuthorityVerdict(BaseModel):
    """Fail-closed benchmark authority decision for a promotion request."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    request: PromotionEvidenceRequest
    bundle: FrontierBenchmarkBundle
    missing: list[str] = Field(default_factory=list)
    stale: list[str] = Field(default_factory=list)
    leakage_warnings: list[str] = Field(default_factory=list)
    default_enable_allowed: bool
    rationale: str

    def public_export(self) -> dict[str, object]:
        """Return a public-safe summary with hidden holdout artifact ids removed."""

        from polisyos.scientist.evals.reports import (
            export_public_benchmark_authority_verdict,
        )

        return export_public_benchmark_authority_verdict(self)


class BenchmarkAuthority:
    """Policy facade that keeps `BenchmarkRegistry` as the persistence authority."""

    def __init__(
        self,
        registry: BenchmarkRegistry,
        *,
        staleness_policy: BenchmarkStalenessPolicy | None = None,
    ) -> None:
        self._registry = registry
        self._staleness_policy = staleness_policy or BenchmarkStalenessPolicy()

    def required_evidence(self, request: PromotionEvidenceRequest) -> list[str]:
        """Return missing evidence names for the request using the underlying registry."""

        return self._registry.require_promotion_evidence(
            family=request.family,
            claim_mode=request.claim_mode,
            run_id=request.run_id,
            loop_id=request.loop_id,
            query_type=request.query_type,
            estimator_name=request.estimator_name,
            readiness_target=request.readiness_target,
        )

    def verdict(
        self,
        request: PromotionEvidenceRequest,
        *,
        now: datetime | None = None,
    ) -> BenchmarkAuthorityVerdict:
        """Resolve a benchmark bundle and decide whether it can support promotion."""

        bundle = self._registry.resolve_family_bundle(
            family=request.family,
            claim_mode=request.claim_mode,
            run_id=request.run_id,
            loop_id=request.loop_id,
            query_type=request.query_type,
            estimator_name=request.estimator_name,
            readiness_target=request.readiness_target,
        )
        snapshot = self._registry.snapshot()
        missing = list(bundle.missing_for_promotion())
        missing.extend(_risk_tier_missing(request, bundle))
        missing.extend(_registry_lookup_missing(request, snapshot.entries))
        stale = stale_entries_for_refs(
            snapshot.entries,
            _bundle_refs(bundle),
            policy=self._staleness_policy,
            now=now or datetime.now(UTC),
        )
        leakage_warnings = _leakage_warnings(bundle)
        default_enable_allowed = bool(not missing and not stale)
        return BenchmarkAuthorityVerdict(
            request=request,
            bundle=bundle,
            missing=sorted(set(missing)),
            stale=stale,
            leakage_warnings=leakage_warnings,
            default_enable_allowed=default_enable_allowed,
            rationale=_rationale(
                missing=missing,
                stale=stale,
                request=request,
            ),
        )


def _risk_tier_missing(
    request: PromotionEvidenceRequest,
    bundle: FrontierBenchmarkBundle,
) -> list[str]:
    if request.risk_tier != "high":
        return []
    if request.claim_mode == "proof_only":
        return []
    if not bundle.sentinel_evaluation_refs:
        return ["sentinel_evaluation_refs"]
    return []


def _registry_lookup_missing(
    request: PromotionEvidenceRequest,
    entries: list[BenchmarkRegistryEntry],
) -> list[str]:
    if not request.registry_lookup_required or request.benchmark_pack_ref is None:
        return []
    requested_ref_id = str(request.benchmark_pack_ref.artifact_id)
    if any(str(entry.artifact_ref.artifact_id) == requested_ref_id for entry in entries):
        return []
    return ["registered_benchmark_pack_ref"]


def _bundle_refs(bundle: FrontierBenchmarkBundle) -> list[ArtifactRef]:
    refs: list[ArtifactRef] = []
    if bundle.selection_evaluation_ref is not None:
        refs.append(bundle.selection_evaluation_ref)
    if bundle.hidden_holdout_evaluation_ref is not None:
        refs.append(bundle.hidden_holdout_evaluation_ref)
    refs.extend(bundle.rotating_challenge_evaluation_refs)
    refs.extend(bundle.sentinel_evaluation_refs)
    refs.extend(bundle.adversarial_artifact_refs)
    return refs


def _leakage_warnings(bundle: FrontierBenchmarkBundle) -> list[str]:
    hidden_refs = hidden_benchmark_ref_ids(bundle)
    if not hidden_refs:
        return []
    return ["hidden_holdout_refs_present_internal_only"]


def _rationale(
    *,
    missing: list[str],
    stale: list[str],
    request: PromotionEvidenceRequest,
) -> str:
    if missing:
        return (
            f"Promotion for {request.family}/{request.claim_mode} is blocked because "
            f"required benchmark evidence is missing: {', '.join(sorted(set(missing)))}."
        )
    if stale:
        return (
            f"Promotion for {request.family}/{request.claim_mode} is blocked because "
            f"benchmark evidence is stale: {', '.join(stale)}."
        )
    return (
        f"Promotion for {request.family}/{request.claim_mode} is allowed by the "
        "benchmark authority for the documented benchmark scope."
    )
