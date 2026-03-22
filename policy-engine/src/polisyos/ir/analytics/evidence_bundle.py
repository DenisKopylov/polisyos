"""EvidenceBundle IR — machine-readable audit trail for causal identification and estimation.

Assembles proof steps, data provenance, and diagnostic scores into a single
serializable object for audit, reproducibility, and explanation purposes.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.negative_certificate import FallbackResult


def _fingerprint(data: Any) -> str:
    """Return a 16-char SHA-256 hex fingerprint of JSON-serializable data."""
    try:
        content = json.dumps(data, sort_keys=True, default=str)
    except Exception:
        content = str(data)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


class ProofStep(BaseModel):
    """A single step in a do-calculus / identification proof.

    This is the JSON-serializable IR counterpart of the internal
    ``ProofStep`` frozen dataclass in ``id_engine.py``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_name: str
    """Name of the rule applied (e.g. 'RULE1', 'C_COMPONENT', 'HEDGE')."""

    description: str
    """Human-readable description of what the rule accomplished."""

    variables_affected: tuple[str, ...] = ()
    """Variables whose status changed during this step."""

    graph_subset: str = ""
    """Compact description of the graph scope at this step."""

    rule_formal_name: str = ""
    """Formal name of the rule in do-calculus literature (e.g. 'do-calculus rule 3', 'c-component factorization')."""

    applicable_theorem: str = ""
    """Theorem or lemma reference (e.g. 'do-calculus-R3', 'ID-algorithm', 'hedge-certificate')."""

    graph_state_before: str = ""
    """Compact description of the graph state before this rule was applied."""

    graph_state_after: str = ""
    """Compact description of the graph state after this rule was applied."""


class DataProvenance(BaseModel):
    """Provenance record for a single data source used in estimation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_ref: str
    """Identifier of the dataset (matches DataKnowledgeBase.dataset_ref)."""

    n_obs: int | None = None
    """Number of observations in the dataset."""

    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    """Data quality score [0, 1]."""

    domain: str = "source"
    """Domain identifier ('source', 'target', 'experimental')."""

    availability_status: str = "available"
    """Availability status ('available', 'partial', 'proxy_only', 'unavailable')."""


class CompilationStep(BaseModel):
    """Records the transition from EstimandAST → ExecutorGraph."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    estimand_shape: str
    """EstimandShape.value (e.g. 'backdoor', 'frontdoor', 'transport_reweight')."""

    estimation_strategy: str
    """EstimationStrategy.value (e.g. 'aipw', 'dml', 'density_ratio_reweight')."""

    n_executor_nodes: int
    """Number of nodes in the compiled ExecutorGraph."""

    nuisance_components: tuple[str, ...] = ()
    """Names of nuisance components emitted by the compiler (e.g. 'propensity', 'outcome_model')."""

    compiler_warnings: tuple[str, ...] = ()
    """Any warnings raised during compilation."""


class EstimationStep(BaseModel):
    """Records the execution of one MethodDagNode in the executor."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node_id: str
    """Identifier of the executor node."""

    method_fqn: str
    """Fully-qualified method name (namespace.name)."""

    method_version: str | None = None
    """SemVer string of the method version used."""

    backend: str = ""
    """Compute backend used (e.g. 'numpy', 'sklearn', 'jax')."""

    params_hash: str = ""
    """Truncated SHA-256 of the params dict — does not store raw params."""

    wall_time_ms: float | None = None
    """Wall-clock execution time in milliseconds."""

    determinism_tier: str = ""
    """DeterminismTier.value at execution time."""

    warnings: tuple[str, ...] = ()
    """Any warnings emitted by this node."""

    is_nuisance: bool = False
    """True if this was a nuisance estimator node."""


class EvidenceBundle(BaseModel):
    """Machine-readable audit trail for a causal identification and estimation run.

    Stores the full proof of identification (proof_steps), the data sources
    used (data_provenance), diagnostic scores, and method configuration.
    Intended for reproducibility, explainability, and policy-level audit.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    """Unique identifier for this analysis run."""

    query_str: str
    """Human-readable query string (e.g. 'P(Y | do(X), Z, domain=target)')."""

    estimand_ast: dict[str, Any] = Field(default_factory=dict)
    """Serialized EstimandAST (model_dump()).

    Stored as dict to avoid circular imports between IR and foundry layers.
    Consumers can reconstruct via ``EstimandAST.model_validate(bundle.estimand_ast)``.
    """

    proof_steps: tuple[ProofStep, ...] = ()
    """Ordered sequence of identification proof steps."""

    data_provenance: tuple[DataProvenance, ...] = ()
    """Data sources used in this run."""

    diagnostic_scores: dict[str, float] = Field(default_factory=dict)
    """Key diagnostic metrics (e.g. 'overlap_score', 'positivity_score')."""

    method_config: dict[str, Any] = Field(default_factory=dict)
    """Configuration of the estimator(s) used."""

    identification_status: str = ""
    """Status string from IdentificationResult.status.value."""

    algorithm_version: str = ""
    """Version string of the identification algorithm used."""

    created_at: str = ""
    """ISO 8601 timestamp of when this bundle was created."""

    # ------------------------------------------------------------------
    # 5.1 — full proof trail additions
    # ------------------------------------------------------------------

    graph_fingerprint: str = ""
    """Truncated SHA-256 of the CausalGraphModel at run time."""

    estimand_fingerprint: str = ""
    """Truncated SHA-256 of the serialised EstimandAST."""

    compilation_steps: tuple[CompilationStep, ...] = ()
    """Steps recording the EstimandAST → ExecutorGraph compilation."""

    estimation_steps: tuple[EstimationStep, ...] = ()
    """Per-node execution records from the executor."""

    # ------------------------------------------------------------------
    # 5.2 — diagnostic dashboard
    # ------------------------------------------------------------------

    diagnostic_dashboard: dict[str, Any] | None = None
    """Serialised DiagnosticDashboardData.  Stored as dict to avoid circular
    imports; reconstruct with DiagnosticDashboardData.model_validate(bundle.diagnostic_dashboard)."""

    # ------------------------------------------------------------------
    # 5.4 — quality report
    # ------------------------------------------------------------------

    quality_report: dict[str, Any] | None = None
    """Serialised CausalQualityReport.  Reconstruct with
    CausalQualityReport.model_validate(bundle.quality_report)."""

    fallback_result: FallbackResult | None = None
    """Typed fallback chain artifact for negative-identification runs."""

    def to_summary(self) -> str:
        """Return a concise human-readable summary of this bundle."""
        n_steps = len(self.proof_steps)
        n_data = len(self.data_provenance)
        if self.diagnostic_scores:
            scores_str = ", ".join(
                f"{k}={v:.3f}" for k, v in self.diagnostic_scores.items()
            )
        else:
            scores_str = "none"
        grade = ""
        if self.quality_report:
            grade = f" grade={self.quality_report.get('composite_grade', '?')}"
        fp = f" graph={self.graph_fingerprint!r}" if self.graph_fingerprint else ""
        return (
            f"EvidenceBundle[{self.run_id}] "
            f"query={self.query_str!r} "
            f"status={self.identification_status!r} "
            f"proof_steps={n_steps} "
            f"data_sources={n_data} "
            f"diagnostics=[{scores_str}]"
            f"{fp}{grade}"
        )


__all__ = [
    "_fingerprint",
    "ProofStep",
    "DataProvenance",
    "CompilationStep",
    "EstimationStep",
    "EvidenceBundle",
]
