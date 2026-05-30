"""W6.C obligation graph compiler and ledger contracts.

The package owns C38's three-tier obligation ledger:

* an unbounded candidate ledger that never blocks closeout;
* a canonical bundle ledger bounded by family/scope/authority/time/remedy;
* a complexity-budgeted blocking frontier.
"""

from __future__ import annotations

from ._impl.compiler import (
    ObligationGraphCompileError,
    compile_obligation_graph,
    obligation_graph_audit_surface,
    write_obligation_graph_artifact,
)
from ._impl.models import (
    OBLIGATION_GRAPH_CONTRACT_ID,
    OBLIGATION_GRAPH_SCHEMA_VERSION,
    BundleKey,
    CandidateLedgerEntry,
    ComplexityBudget,
    DeadlineBinding,
    DeferredObligationRecord,
    DeferredState,
    FacetSnapshot,
    FrontierItem,
    GovernedObligationRule,
    ObligationBundle,
    ObligationCandidateInput,
    ObligationGraph,
    PriorityClass,
    SourceClass,
)

__all__ = [
    "OBLIGATION_GRAPH_CONTRACT_ID",
    "OBLIGATION_GRAPH_SCHEMA_VERSION",
    "BundleKey",
    "CandidateLedgerEntry",
    "ComplexityBudget",
    "DeadlineBinding",
    "DeferredObligationRecord",
    "DeferredState",
    "FacetSnapshot",
    "FrontierItem",
    "GovernedObligationRule",
    "ObligationBundle",
    "ObligationCandidateInput",
    "ObligationGraph",
    "ObligationGraphCompileError",
    "PriorityClass",
    "SourceClass",
    "compile_obligation_graph",
    "obligation_graph_audit_surface",
    "write_obligation_graph_artifact",
]
