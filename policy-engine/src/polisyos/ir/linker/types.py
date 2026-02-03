from __future__ import annotations

from polisyos.ir.applicability import IdSelector, NormApplicability
from polisyos.ir.registry_fragments import RegistryBundle

from .reports import LinkIssue, LinkIssueCode, LinkSeverity


def validate_norm_applicability_refs(
    applicability: NormApplicability,
    registries: RegistryBundle,
    *,
    path_prefix: list[str | int],
) -> list[LinkIssue]:
    """Validate applicability ids against registries and emit LinkIssue entries."""

    issues: list[LinkIssue] = []

    actor_ids: set[str] | None = None
    concept_ids: set[str] | None = None
    jurisdiction_ids: set[str] | None = None

    if registries.actors is not None:
        actor_ids = set(registries.actors.actor_types.keys())
    if registries.concepts is not None:
        concept_ids = set(registries.concepts.concepts.keys())
    if registries.geo is not None:
        jurisdiction_ids = set(registries.geo.areas.keys())

    def _emit_unknown(
        code: LinkIssueCode,
        value: str,
        path: list[str | int],
        data_key: str,
    ) -> None:
        issues.append(
            LinkIssue(
                severity=LinkSeverity.ERROR,
                code=code,
                message=f"Unknown {data_key.replace('_', ' ')} '{value}'",
                path=path,
                data={data_key: value, "where": "norm_applicability"},
            )
        )

    def _check_selector(
        selector: IdSelector,
        known: set[str] | None,
        *,
        code: LinkIssueCode,
        base_path: list[str | int],
        data_key: str,
    ) -> None:
        if known is None:
            return
        for list_name in ("any_of", "all_of", "none_of"):
            values = getattr(selector, list_name)
            for idx, value in enumerate(values):
                if value not in known:
                    _emit_unknown(
                        code,
                        value,
                        path_prefix + base_path + [list_name, idx],
                        data_key,
                    )

    _check_selector(
        applicability.jurisdiction,
        jurisdiction_ids,
        code=LinkIssueCode.UNKNOWN_JURISDICTION,
        base_path=["jurisdiction"],
        data_key="jurisdiction_id",
    )
    _check_selector(
        applicability.subject.actors,
        actor_ids,
        code=LinkIssueCode.UNKNOWN_ACTOR,
        base_path=["subject", "actors"],
        data_key="actor_id",
    )
    _check_selector(
        applicability.subject.concepts,
        concept_ids,
        code=LinkIssueCode.UNKNOWN_CONCEPT,
        base_path=["subject", "concepts"],
        data_key="concept_id",
    )
    _check_selector(
        applicability.object.actors,
        actor_ids,
        code=LinkIssueCode.UNKNOWN_ACTOR,
        base_path=["object", "actors"],
        data_key="actor_id",
    )
    _check_selector(
        applicability.object.concepts,
        concept_ids,
        code=LinkIssueCode.UNKNOWN_CONCEPT,
        base_path=["object", "concepts"],
        data_key="concept_id",
    )

    for idx, exc in enumerate(applicability.exceptions):
        issues.extend(
            validate_norm_applicability_refs(
                exc,
                registries,
                path_prefix=path_prefix + ["exceptions", idx],
            )
        )

    return issues


__all__ = ["validate_norm_applicability_refs"]
