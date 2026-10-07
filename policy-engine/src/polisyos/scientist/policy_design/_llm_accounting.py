"""Explicit accounting-owner admission for LLM-backed policy workers."""

from __future__ import annotations

from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware


class PolicyWorkerAccountingAdmissionError(PolicyOSError):
    """A requested worker budget has no single initialized durable owner."""

    default_category = ErrorCategory.VALIDATION
    default_stage = "scientist.policy_design.llm_accounting"


def worker_budget_state(
    *,
    budget_state: BudgetState | None,
    budget_middleware: BudgetMiddleware | None,
) -> BudgetState | None:
    """Admit an explicit durable contour before factory or provider work.

    Neither input means the existing unbudgeted contour. A raw state is not
    a settlement owner, and cannot be silently replaced by middleware limits.
    This read does not select a path, bootstrap a ledger, reserve, or mint an
    observed producer event. The enforcer performs atomic intent admission.
    """
    if budget_state is not None:
        raise PolicyWorkerAccountingAdmissionError(
            "Policy worker budgeting requires an initialized BudgetMiddleware; "
            "do not supply a separate raw BudgetState",
            code=(
                "worker_budget_owner_conflict"
                if budget_middleware is not None
                else "worker_budget_owner_required"
            ),
        )
    if budget_middleware is None:
        return None
    try:
        # This public property reads the actual initialized ledger contract.
        # A memory-only middleware cannot manufacture a durable identity.
        _ = budget_middleware.settlement_owner_identity
        return budget_middleware.budget_state
    except Exception as exc:
        raise PolicyWorkerAccountingAdmissionError(
            "Policy worker BudgetMiddleware has no readable initialized settlement owner",
            code="worker_budget_owner_unavailable",
        ) from exc
