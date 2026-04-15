from __future__ import annotations

from pathlib import Path

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.ir.analytics.estimand import (
    DistributionDomain,
    DistributionRef,
    EstimandAST,
    ProductNode,
    SumNode,
    normalize_estimand_ast,
    persist_estimand_ast,
)


def _semantically_equivalent_estimands() -> tuple[EstimandAST, EstimandAST]:
    left = EstimandAST(
        query_str="P(Y|do(X))",
        root=SumNode(
            summation_vars=("Z",),
            operand=ProductNode(
                factors=(
                    DistributionRef(
                        domain=DistributionDomain.SOURCE,
                        variables=("Z",),
                    ),
                    ProductNode(
                        factors=(
                            DistributionRef(
                                domain=DistributionDomain.SOURCE,
                                variables=("Y",),
                                conditioning=("Z", "X"),
                            ),
                        )
                    ),
                )
            ),
        ),
        treatment="X",
        outcome="Y",
        all_variables=("Y", "X", "Z"),
        identification_method="backdoor",
    )
    right = EstimandAST(
        query_str="ATE via backdoor",
        root=SumNode(
            summation_vars=("Z",),
            operand=ProductNode(
                factors=(
                    DistributionRef(
                        domain=DistributionDomain.SOURCE,
                        variables=("Y",),
                        conditioning=("X", "Z"),
                    ),
                    DistributionRef(
                        domain=DistributionDomain.SOURCE,
                        variables=("Z",),
                    ),
                )
            ),
        ),
        treatment="X",
        outcome="Y",
        all_variables=("Z", "Y", "X"),
        identification_method="backdoor",
    )
    return left, right


def test_estimand_normalization_dedupes_semantically_equivalent_payloads() -> None:
    left, right = _semantically_equivalent_estimands()

    normalized_left = normalize_estimand_ast(left)
    normalized_right = normalize_estimand_ast(right)

    assert normalized_left == normalized_right
    assert normalized_left.content_hash(prefix=True) == normalized_right.content_hash(prefix=True)


def test_estimand_persistence_uses_normalized_cas_payload(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path)
    left, right = _semantically_equivalent_estimands()

    left_ref = persist_estimand_ast(store, left)
    right_ref = persist_estimand_ast(store, right)

    assert left_ref.artifact_id == right_ref.artifact_id


def test_normalization_collapses_single_factor_products() -> None:
    estimand = EstimandAST(
        query_str="P(Y)",
        root=ProductNode(
            factors=(
                DistributionRef(
                    domain=DistributionDomain.SOURCE,
                    variables=("Y",),
                ),
            )
        ),
        treatment="X",
        outcome="Y",
        all_variables=("Y", "X"),
    )

    normalized = normalize_estimand_ast(estimand)

    assert isinstance(normalized.root, DistributionRef)
