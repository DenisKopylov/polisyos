from __future__ import annotations

from itertools import pairwise

from pydantic import BaseModel, ValidationError

from polisyos.core.errors import ErrorCategory, PolicyOSError
from polisyos.foundry.uncertainty.evaluation_failures import (
    EXCEPTION_CHAIN_EDGE_LIMIT,
    EXCEPTION_CHAIN_NODE_LIMIT,
    classify_evaluation_failure,
)


class _InvalidPayload(BaseModel):
    count: int


class _DeclaredSampleDomainError(Exception):
    pass


class _DeclaredGlobalError(Exception):
    pass


def _cause(outer: BaseException, inner: BaseException) -> BaseException:
    outer.__cause__ = inner
    return outer


def test_evaluation_failure_classifier_preserves_global_error_precedence() -> None:
    validation_error: ValidationError
    try:
        _InvalidPayload.model_validate({"count": "not-an-integer"})
    except ValidationError as exc:
        validation_error = exc
    else:  # pragma: no cover - fixture must fail validation
        raise AssertionError("invalid fixture unexpectedly validated")

    errors = (
        PermissionError("denied"),
        _cause(RuntimeError("wrapped"), OSError("source unavailable")),
        validation_error,
        PolicyOSError("fatal", category=ErrorCategory.FATAL),
        PolicyOSError("invalid", category=ErrorCategory.VALIDATION),
        _cause(RuntimeError("wrapped policy error"), PolicyOSError("fatal")),
        _cause(RuntimeError("wrapped injected error"), _DeclaredGlobalError("global")),
    )

    for error in errors:
        result = classify_evaluation_failure(
            error,
            additional_global_error_types=(_DeclaredGlobalError,),
        )
        assert result.scope == "global"
        assert result.chain_complete is True
        assert result.cycle_detected is False


def test_evaluation_failure_classifier_keeps_transient_and_declared_domain_root_scoped() -> None:
    transient = PolicyOSError("retry", category=ErrorCategory.TRANSIENT)
    sample_domain = _DeclaredSampleDomainError("one sampled input is outside the domain")

    assert classify_evaluation_failure(transient).scope == "transient"
    assert (
        classify_evaluation_failure(
            sample_domain,
            sample_domain_error_type=_DeclaredSampleDomainError,
        ).scope
        == "sample_domain"
    )
    assert (
        classify_evaluation_failure(
            _cause(RuntimeError("wrapped domain"), sample_domain),
            sample_domain_error_type=_DeclaredSampleDomainError,
        ).scope
        == "unknown"
    )
    assert classify_evaluation_failure(RuntimeError("undeclared")).scope == "unknown"


def test_evaluation_failure_classifier_distinguishes_shared_dag_from_cycle() -> None:
    shared = RuntimeError("shared cause")
    left = _cause(RuntimeError("left"), shared)
    right = _cause(RuntimeError("right"), shared)

    shared_result = classify_evaluation_failure(ExceptionGroup("shared", [left, right]))
    assert shared_result.scope == "unknown"
    assert shared_result.chain_complete is True
    assert shared_result.cycle_detected is False
    assert sum(node is shared for node in shared_result.chain) == 1

    cycle = RuntimeError("cycle")
    cycle.__cause__ = cycle
    cycle_result = classify_evaluation_failure(cycle)
    assert cycle_result.scope == "unknown"
    assert cycle_result.chain_complete is True
    assert cycle_result.cycle_detected is True


def test_evaluation_failure_classifier_marks_node_and_edge_truncation_unknown() -> None:
    chain = [RuntimeError(f"cause-{index}") for index in range(EXCEPTION_CHAIN_NODE_LIMIT + 2)]
    for outer, inner in pairwise(chain):
        outer.__cause__ = inner

    node_limited = classify_evaluation_failure(chain[0])
    assert node_limited.scope == "unknown"
    assert len(node_limited.chain) == EXCEPTION_CHAIN_NODE_LIMIT
    assert node_limited.chain_complete is False

    repeated = RuntimeError("repeated child")
    group = ExceptionGroup("wide shared graph", [repeated] * (EXCEPTION_CHAIN_EDGE_LIMIT + 1))
    edge_limited = classify_evaluation_failure(group)
    assert edge_limited.scope == "unknown"
    assert edge_limited.chain_complete is False
