"""DataKnowledgeBase — multi-domain data availability registry.

Used by the ID engine to determine which probability distributions are
available in which domains / datasets, and by the EstimandCompiler to score
whether a given EstimandAST can be estimated from available data.

Design:
  - Frozen Pydantic (extra="forbid") — project standard
  - No NetworkX, no external dependencies
  - Convertible from an existing SelectionDiagram (backward-compat bridge)
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.transportability import SelectionDiagram
    from polisyos.ir.data.harmonizer import HarmonizationReport


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class DistributionAvailability(str, Enum):
    """How well a required distribution is covered by a known dataset."""

    AVAILABLE = "available"  # full coverage, all variables present
    PARTIAL = "partial"  # some variables missing or proxied
    PROXY_ONLY = "proxy_only"  # only proxy variable(s) exist
    UNAVAILABLE = "unavailable"  # no matching dataset


# ---------------------------------------------------------------------------
# Dataset entry
# ---------------------------------------------------------------------------


class DatasetEntry(BaseModel):
    """Describes a single available dataset / distribution in some domain."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_ref: str  # unique key; matches DistributionRef.dataset_ref
    variables: tuple[str, ...]  # observed variables in this dataset
    domain: DistributionDomain
    availability: DistributionAvailability = DistributionAvailability.AVAILABLE
    n_obs: int | None = None  # sample size (None = unknown)
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)

    # optional: which intervention sets are available in this dataset
    available_interventions: tuple[tuple[str, ...], ...] = ()
    # e.g. (("X",),) means P(·|do(X)) is available


# ---------------------------------------------------------------------------
# DataKnowledgeBase
# ---------------------------------------------------------------------------


class DataKnowledgeBase(BaseModel):
    """Registry of available datasets / probability distributions across domains.

    Produced from a SelectionDiagram or provided directly.  Used by:
    - id_engine to check whether a required P(·) is available
    - EstimandCompiler to determine dataset bindings for MethodDagNodes
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    datasets: tuple[DatasetEntry, ...] = ()

    # ---------------------------------------------------------------------------
    # Query API
    # ---------------------------------------------------------------------------

    def can_identify_distribution(
        self,
        dist_ref: DistributionRef,
    ) -> tuple[DistributionAvailability, str | None]:
        """Find the best matching dataset entry for a DistributionRef.

        Matching rules (in priority order):
        1. Exact match on domain + variables (superset of required vars) + interventions
        2. Partial match on domain + some variables
        3. UNAVAILABLE

        Returns (availability, dataset_ref or None).
        """
        req_vars = set(dist_ref.variables) | set(dist_ref.conditioning)
        req_interventions = set(dist_ref.intervention_set)

        best: tuple[DistributionAvailability, str | None] = (
            DistributionAvailability.UNAVAILABLE,
            None,
        )
        best_score = -1.0

        for entry in self.datasets:
            if entry.domain is not dist_ref.domain:
                continue
            entry_vars = set(entry.variables)
            # Check intervention availability
            if req_interventions:
                has_intervention = any(
                    req_interventions <= set(iv) for iv in entry.available_interventions
                )
                if not has_intervention:
                    continue
            # Coverage score
            covered = len(req_vars & entry_vars)
            total = len(req_vars)
            if covered == 0:
                continue
            coverage = covered / total if total > 0 else 1.0
            score = coverage * entry.quality_score

            if coverage >= 1.0:
                avail = DistributionAvailability.AVAILABLE
            elif coverage >= 0.5:
                avail = DistributionAvailability.PARTIAL
            else:
                avail = DistributionAvailability.PROXY_ONLY

            if score > best_score:
                best_score = score
                best = (avail, entry.dataset_ref)

        return best

    def score_estimand(
        self,
        ast: EstimandAST,
    ) -> tuple[float, list[str]]:
        """Score overall feasibility of estimating an estimand from available data.

        Returns:
            (feasibility_score, missing_dataset_refs)
            feasibility_score: 0.0 (impossible) to 1.0 (fully feasible)
            missing_dataset_refs: list of dataset_ref values that are unavailable
        """
        dist_refs = ast.collect_distribution_refs()
        if not dist_refs:
            return 1.0, []

        scores: list[float] = []
        missing: list[str] = []
        for dr in dist_refs:
            avail, _found_ref = self.can_identify_distribution(dr)
            if avail is DistributionAvailability.AVAILABLE:
                scores.append(1.0)
            elif avail is DistributionAvailability.PARTIAL:
                scores.append(0.6)
            elif avail is DistributionAvailability.PROXY_ONLY:
                scores.append(0.3)
            else:
                scores.append(0.0)
                missing.append(
                    dr.dataset_ref or f"unknown({dr.domain.value}:{','.join(dr.variables)})"
                )

        overall = sum(scores) / len(scores)
        return overall, missing

    def get_dataset_ref_for(self, dist_ref: DistributionRef) -> str | None:
        """Return the best matching dataset_ref for a DistributionRef, or None."""
        _, ref = self.can_identify_distribution(dist_ref)
        return ref

    def all_dataset_refs(self) -> list[str]:
        """Return all known dataset_ref values."""
        return [d.dataset_ref for d in self.datasets]

    def with_added_entry(self, entry: DatasetEntry) -> DataKnowledgeBase:
        """Return a new DataKnowledgeBase with *entry* appended.

        No-op (returns self) if an entry with the same ``dataset_ref`` already exists.
        """
        if any(d.dataset_ref == entry.dataset_ref for d in self.datasets):
            return self
        return DataKnowledgeBase(datasets=(*self.datasets, entry))

    def missing_distribution_refs(self, ast: EstimandAST) -> list[str]:
        """Return dataset refs from *ast* that have UNAVAILABLE availability in this KB."""
        result: list[str] = []
        for dr in ast.collect_distribution_refs():
            avail, _ = self.can_identify_distribution(dr)
            if avail is DistributionAvailability.UNAVAILABLE:
                result.append(
                    dr.dataset_ref or f"unknown({dr.domain.value}:{','.join(dr.variables)})"
                )
        return result

    def proxy_coverage_fraction(self, ast: EstimandAST) -> float:
        """Fraction of required distributions that are PROXY_ONLY or PARTIAL in this KB."""
        refs = ast.collect_distribution_refs()
        if not refs:
            return 0.0
        proxy_statuses = {DistributionAvailability.PROXY_ONLY, DistributionAvailability.PARTIAL}
        proxy_count = sum(
            1 for dr in refs if self.can_identify_distribution(dr)[0] in proxy_statuses
        )
        return proxy_count / len(refs)

    # ---------------------------------------------------------------------------
    # Classmethod constructors
    # ---------------------------------------------------------------------------

    @classmethod
    def from_selection_diagram(
        cls,
        diagram: SelectionDiagram,
        *,
        source_dataset_ref: str = "source",
        target_dataset_ref: str | None = None,
        source_n_obs: int | None = None,
        target_n_obs: int | None = None,
    ) -> DataKnowledgeBase:
        """Build a DataKnowledgeBase from an existing SelectionDiagram.

        Source context → DatasetEntry(domain=SOURCE, all graph nodes).
        Target context → DatasetEntry(domain=TARGET, non-S-node variables) if
                         target_dataset_ref is provided.
        """
        graph_vars = tuple(diagram.base_graph.nodes)
        s_node_vars = frozenset(sn.target_variable for sn in diagram.s_nodes)

        source_entry = DatasetEntry(
            dataset_ref=source_dataset_ref,
            variables=graph_vars,
            domain=DistributionDomain.SOURCE,
            n_obs=source_n_obs,
        )
        entries: list[DatasetEntry] = [source_entry]

        if target_dataset_ref is not None:
            # Target dataset typically has measurement for S-node affected variables
            target_vars = tuple(s_node_vars) if s_node_vars else graph_vars
            target_entry = DatasetEntry(
                dataset_ref=target_dataset_ref,
                variables=target_vars,
                domain=DistributionDomain.TARGET,
                n_obs=target_n_obs,
            )
            entries.append(target_entry)

        return cls(datasets=tuple(entries))

    @classmethod
    def from_dataset_refs(
        cls,
        *,
        source_ref: str,
        source_vars: tuple[str, ...],
        target_ref: str | None = None,
        target_vars: tuple[str, ...] = (),
        experimental_ref: str | None = None,
        experimental_vars: tuple[str, ...] = (),
        experimental_interventions: tuple[tuple[str, ...], ...] = (),
    ) -> DataKnowledgeBase:
        """Convenience constructor for the common two-dataset (source + target) case."""
        entries: list[DatasetEntry] = [
            DatasetEntry(
                dataset_ref=source_ref,
                variables=source_vars,
                domain=DistributionDomain.SOURCE,
            )
        ]
        if target_ref is not None:
            entries.append(
                DatasetEntry(
                    dataset_ref=target_ref,
                    variables=target_vars or source_vars,
                    domain=DistributionDomain.TARGET,
                )
            )
        if experimental_ref is not None:
            entries.append(
                DatasetEntry(
                    dataset_ref=experimental_ref,
                    variables=experimental_vars or source_vars,
                    domain=DistributionDomain.EXPERIMENTAL,
                    available_interventions=experimental_interventions,
                )
            )
        return cls(datasets=tuple(entries))

    @classmethod
    def from_harmonized(
        cls,
        report: HarmonizationReport,
        *,
        source_domain: DistributionDomain = DistributionDomain.SOURCE,
        target_domain: DistributionDomain = DistributionDomain.TARGET,
    ) -> DataKnowledgeBase:
        """Build a DataKnowledgeBase from a :class:`~polisyos.ir.data.harmonizer.HarmonizationReport`.

        Automatically derives data availability from the harmonization outcome:

        - Harmonized variables with no mismatches → :attr:`DistributionAvailability.AVAILABLE`
        - Harmonized variables with coercible type mismatches or imputed missing
          vars → :attr:`DistributionAvailability.PARTIAL`

        Two :class:`DatasetEntry` objects are created when
        ``report.target_dataset_ref`` is set (one per domain).

        Parameters
        ----------
        report:
            Frozen :class:`HarmonizationReport` produced by
            :meth:`DomainHarmonizer.align`.
        source_domain:
            :class:`DistributionDomain` to assign to the source entry.
        target_domain:
            :class:`DistributionDomain` to assign to the target entry.

        Raises
        ------
        ValueError
            If ``report.is_compatible`` is ``False`` (i.e. errors are present).
        """
        if not report.is_compatible:
            raise ValueError(
                f"Cannot build DataKnowledgeBase from an incompatible "
                f"HarmonizationReport. Errors: {list(report.errors)}"
            )

        has_quality_issues = bool(report.type_mismatches or report.missing_variables)
        source_availability = (
            DistributionAvailability.PARTIAL
            if has_quality_issues
            else DistributionAvailability.AVAILABLE
        )

        source_entry = DatasetEntry(
            dataset_ref=report.source_dataset_ref,
            variables=report.harmonized_variables,
            domain=source_domain,
            availability=source_availability,
            n_obs=report.n_source_obs,
        )
        entries: list[DatasetEntry] = [source_entry]

        if report.target_dataset_ref:
            target_vars = tuple(dict.fromkeys(m.target_variable for m in report.resolved_mappings))
            target_entry = DatasetEntry(
                dataset_ref=report.target_dataset_ref,
                variables=target_vars or report.harmonized_variables,
                domain=target_domain,
                availability=DistributionAvailability.AVAILABLE,
                n_obs=report.n_target_obs,
            )
            entries.append(target_entry)

        return cls(datasets=tuple(entries))


__all__ = [
    "DataKnowledgeBase",
    "DatasetEntry",
    "DistributionAvailability",
]
