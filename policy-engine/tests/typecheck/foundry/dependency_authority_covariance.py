"""Static witness for covariant semantic-domain references."""

from __future__ import annotations

from typing import Literal, assert_never

from polisyos.foundry.methods.catalog.dependency_authority import (
    MethodCatalogDependencyAuthorityResult,
    SourceRejectedMethodCatalogDependencyProfile,
    SourceUnestablishedMethodCatalogDependencyProfile,
    UnestablishedMethodCatalogDependencyProfile,
)
from polisyos.foundry.methods.catalog.dependency_evidence import (
    DigestDomain,
    DomainDigest,
    FoundryRecordRef,
)


def consume_any_digest(value: DomainDigest[DigestDomain]) -> None:
    del value


def consume_any_record(value: FoundryRecordRef[DigestDomain]) -> None:
    del value


def test_specific_domain_ref_satisfies_generic_repository_without_cast(
    digest: DomainDigest[Literal[DigestDomain.PYPROJECT]],
    record: FoundryRecordRef[Literal[DigestDomain.CANONICAL_SOURCE]],
) -> None:
    consume_any_digest(digest)
    consume_any_record(record)


def negative_union_is_exhaustive(result: MethodCatalogDependencyAuthorityResult) -> None:
    if isinstance(result, SourceRejectedMethodCatalogDependencyProfile):
        return
    if isinstance(result, SourceUnestablishedMethodCatalogDependencyProfile):
        return
    if isinstance(result, UnestablishedMethodCatalogDependencyProfile):
        return
    assert_never(result)
