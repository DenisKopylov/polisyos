"""Keep governed W6.C matches inside their selected intervention component."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

import pytest

from polisyos.ir.governance import PolicyLayerLevel
from polisyos.obligation_graph import (
    BundleKey,
    FacetSnapshot,
    GovernedObligationRule,
    ObligationGraphCompileError,
    SourceClass,
    compile_obligation_graph,
)
from polisyos.policy_grammar import (
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarIntent,
    UniversalAuthorityProfile,
    facet_snapshots_for_obligation_graph,
)

NOW = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
_INTENT_DIGEST = "sha256:" + "2" * 64


def _component_facets(
    component_id: str,
    *,
    instrument: str,
    population: str,
    scope: str | None = None,
    temporal_window: str = "2026",
    authority_profile: str = "candidate",
    source_digest: str | None = None,
) -> tuple[FacetSnapshot, ...]:
    selected_scope = scope or f"{population}:north"
    selected_digest = source_digest or f"sha256:{sha256(component_id.encode()).hexdigest()}"
    common = {
        "component_id": component_id,
        "source_intervention_sha256": selected_digest,
        "source_intent_sha256": _INTENT_DIGEST,
        "source_contract_refs": (f"intervention://{component_id}",),
        "component_limitations": ("candidate_only",),
        "component_limitation_messages": ("This component remains a candidate.",),
    }
    return tuple(
        FacetSnapshot(
            facet_id=f"case:component:{component_id}:{facet_type}",
            facet_type=facet_type,
            value=value,
            concept_ref=f"concept://{facet_type}",
            scope=selected_scope,
            authority_profile=authority_profile,
            temporal_window=temporal_window,
            metadata=common,
        )
        for facet_type, value in (
            ("instrument_type", instrument),
            ("population_predicate", population),
            ("method_need", "bounds_only"),
        )
    )


def _rule(
    *,
    required_facets: dict[str, str] | None = None,
    rule_id: str = "rule:component-obligation",
    logic: dict[str, object] | None = None,
) -> GovernedObligationRule:
    return GovernedObligationRule(
        rule_id=rule_id,
        rule_family="data",
        rule_version="2026.11",
        logic_hash="sha256:" + "a" * 64,
        owner="team-data-forge",
        scope="municipal",
        authority_level="governed",
        evidence_basis="registered rule evidence",
        public_revalidation_effect="review_affected_claim",
        obligation_text="Bind the selected component to its own evidence.",
        authority_profile="candidate",
        temporal_window="case_lifecycle",
        remedy_path="source_evidence",
        required_facets=required_facets or {},
        logic=logic or {},
    )


def _graph(facets: tuple[FacetSnapshot, ...], rule: GovernedObligationRule):
    return compile_obligation_graph(
        run_id="run-component-scoped",
        facets=facets,
        governed_rules=(rule,),
        generated_at=NOW,
        intent_text="Shared policy context containing service and credit components.",
    )


def test_component_rule_never_cross_joins_facets_from_distinct_interventions() -> None:
    facets = (
        *_component_facets("service", instrument="public_service", population="families"),
        *_component_facets("credit", instrument="credit", population="msmes"),
    )

    graph = _graph(
        facets,
        _rule(
            required_facets={
                "instrument_type": "public_service",
                "population_predicate": "msmes",
            }
        ),
    )

    assert graph.candidate_ledger == ()
    assert graph.bundle_ledger == ()


def test_component_candidate_retains_every_facet_and_shared_limitations() -> None:
    service = _component_facets("service", instrument="public_service", population="families")
    credit = _component_facets("credit", instrument="credit", population="msmes")

    graph = _graph(
        (*service, *credit),
        _rule(
            required_facets={
                "instrument_type": "public_service",
                "population_predicate": "families",
            }
        ),
    )

    assert len(graph.candidate_ledger) == 1
    candidate = graph.candidate_ledger[0]
    assert candidate.source_class is SourceClass.GOVERNED_RULE
    assert candidate.scope == "municipal"
    assert candidate.metadata["rule_scope"] == "municipal"
    assert candidate.metadata["component_id"] == "service"
    service_digest = f"sha256:{sha256(b'service').hexdigest()}"
    assert candidate.metadata["source_intervention_sha256"] == service_digest
    assert candidate.metadata["component_facet_refs"] == tuple(
        sorted(facet.facet_id for facet in service)
    )
    assert candidate.metadata["matched_component_facet_refs"] == tuple(
        sorted(facet.facet_id for facet in service if facet.facet_type != "method_need")
    )
    assert set(candidate.metadata["component_facet_refs"]).issubset(candidate.lineage_refs)
    assert candidate.metadata["component_limitations"] == ("candidate_only",)
    assert candidate.metadata["component_limitation_messages"] == (
        "This component remains a candidate.",
    )
    assert candidate.metadata["source_intent_sha256"] == _INTENT_DIGEST
    assert candidate.metadata["source_contract_refs"] == ("intervention://service",)
    key = graph.bundle_ledger[0].bundle_key
    assert key.scope == "municipal"
    assert key.component_id == "service"
    assert key.source_intervention_sha256 == service_digest
    assert key.applicability_scope == service[0].scope
    assert key.applicability_temporal_window == "2026"
    assert key.applicability_authority_profile == "candidate"


def test_identical_component_obligations_keep_distinct_claim_bindings_and_bundles() -> None:
    service = _component_facets("service", instrument="public_service", population="families")
    credit = _component_facets("credit", instrument="public_service", population="families")

    graph = _graph(
        (*service, *credit),
        _rule(required_facets={"instrument_type": "public_service"}),
    )

    assert len(graph.candidate_ledger) == 2
    assert graph.candidate_ledger[0].candidate_id != graph.candidate_ledger[1].candidate_id
    assert {candidate.metadata["component_id"] for candidate in graph.candidate_ledger} == {
        "credit",
        "service",
    }
    assert len(graph.bundle_ledger) == 2
    assert {bundle.bundle_key.component_id for bundle in graph.bundle_ledger} == {
        "credit",
        "service",
    }
    assert all(bundle.child_count == 1 for bundle in graph.bundle_ledger)


def test_component_order_and_removal_preserve_only_the_selected_candidate() -> None:
    service = _component_facets("service", instrument="public_service", population="families")
    credit = _component_facets("credit", instrument="credit", population="msmes")
    rule = _rule(required_facets={"instrument_type": "public_service"})

    forward = _graph((*service, *credit), rule)
    reverse = _graph((*credit, *service), rule)
    removed = _graph(service, rule)

    assert [row.candidate_id for row in forward.candidate_ledger] == [
        row.candidate_id for row in reverse.candidate_ledger
    ]
    assert forward.bundle_ledger[0].bundle_id == reverse.bundle_ledger[0].bundle_id
    assert [row.metadata["component_id"] for row in forward.candidate_ledger] == ["service"]
    assert [row.candidate_id for row in forward.candidate_ledger] == [
        row.candidate_id for row in removed.candidate_ledger
    ]


def test_legacy_facets_keep_default_bundle_wire_without_component_fields() -> None:
    key = BundleKey(
        family="data",
        scope="municipal",
        authority_profile="candidate",
        temporal_window="case_lifecycle",
        remedy_path="source_evidence",
    )

    assert key.model_dump(mode="json") == {
        "family": "data",
        "scope": "municipal",
        "authority_profile": "candidate",
        "temporal_window": "case_lifecycle",
        "remedy_path": "source_evidence",
    }

    graph = _graph(
        (
            FacetSnapshot(
                facet_id="legacy:service",
                facet_type="instrument_type",
                value="public_service",
                concept_ref="concept://instrument_type",
                scope="region:north",
                authority_profile="candidate",
                temporal_window="2026",
            ),
        ),
        _rule(required_facets={"instrument_type": "public_service"}),
    )
    assert graph.bundle_ledger[0].bundle_id == (
        "bundle-data-municipal-candidate-case_lifecycle-source_evidence"
    )


def test_v1_bridge_carries_selected_case_refs_and_relevant_grammar_limitations() -> None:
    intent = PolicyGrammarIntent(
        intent_id="v1-warning-transport",
        text=("Create a concessional credit programme for MSMEs in 2026 to preserve employment."),
    )
    case = PolicyGrammarCompiler().compile(
        intent=intent,
        authority_profile=UniversalAuthorityProfile(
            profile_id="candidate-local",
            authority_type=PolicyLayerLevel.FEDERAL,
            source_classification="deterministic_producer",
            authoritative_for=("compilation_facets",),
            may_not_use_for=("legal_authority", "publication_authority"),
        ),
        concept_spine_refs=PolicyGrammarConceptSpineRefs(
            concept_spine_ref="concept-spine://v1-warning",
            jurisdiction_spine_ref="jurisdiction-spine://v1-warning",
            canonical_concept_refs=("concept://policy",),
        ),
    )
    projected = facet_snapshots_for_obligation_graph(case)
    facets = tuple(FacetSnapshot.model_validate(row) for row in projected)
    graph = compile_obligation_graph(
        run_id="run-v1-warning-transport",
        facets=facets,
        governed_rules=(_rule(required_facets={"instrument_type": "credit"}),),
        generated_at=NOW,
        intent_text=intent.text,
    )

    assert len(graph.candidate_ledger) == 1
    candidate = graph.candidate_ledger[0]
    matched_ref = f"{case.case_id}:instrument_type"
    all_case_refs = tuple(sorted(str(row["facet_id"]) for row in projected))
    assert candidate.metadata["matched_facet_refs"] == (matched_ref,)
    assert candidate.metadata["selected_case_facet_refs"] == all_case_refs
    assert candidate.metadata["selected_case_binding"] == {
        "case_id": case.case_id,
        "scope": facets[0].scope,
        "authority_profile": facets[0].authority_profile,
        "temporal_window": facets[0].temporal_window,
    }
    assert set(all_case_refs).issubset(candidate.lineage_refs)
    expected_warnings = tuple(blocker for blocker in case.blockers if blocker.severity == "warning")
    assert candidate.metadata["grammar_limitations"] == tuple(
        blocker.code for blocker in expected_warnings
    )
    assert candidate.metadata["grammar_limitation_messages"] == tuple(
        blocker.message for blocker in expected_warnings
    )
    assert candidate.metadata["grammar_limitation_details"] == tuple(
        blocker.details for blocker in expected_warnings
    )
    assert any(
        selector["facet_name"] == "population_predicate"
        for detail in candidate.metadata["grammar_limitation_details"]
        for selector in detail["selector_candidates"]
    )
    assert candidate.metadata["semantic_scope_provenance"] == "not_established"
    assert candidate.source_class is SourceClass.GOVERNED_RULE
    frontier = next(
        item for item in graph.blocking_frontier if candidate.candidate_id in item.candidate_refs
    )
    frontier_candidate_metadata = frontier.metadata["candidate_metadata_refs"][
        candidate.candidate_id
    ]
    assert frontier_candidate_metadata["selected_case_facet_refs"] == all_case_refs
    assert (
        frontier_candidate_metadata["selected_case_binding"]
        == candidate.metadata["selected_case_binding"]
    )
    assert (
        frontier_candidate_metadata["grammar_limitation_details"]
        == candidate.metadata["grammar_limitation_details"]
    )


def test_component_candidate_carries_deduplicated_grammar_limitation_details() -> None:
    limitation = {
        "grammar_limitations": ("policy_grammar_facet_choice_not_scoped",),
        "grammar_limitation_messages": ("The scalar choice is not component scoped.",),
        "grammar_limitation_details": (
            {
                "selector_candidates": [
                    {
                        "facet_name": "instrument_type",
                        "candidate_value": "public_service",
                        "matched_terms": ["service"],
                        "rule_ref": "policyos.policy_grammar.facet_derivation.v1:instrument_type:public_service",
                        "evidence_role": "explicit_controlled_token",
                    }
                ],
                "semantic_scope_provenance": "not_established",
                "supported_envelope": "controlled_selector_candidate_only",
            },
        ),
        "semantic_scope_provenance": "not_established",
    }
    service = tuple(
        facet.model_copy(update={"metadata": {**facet.metadata, **limitation}})
        for facet in _component_facets(
            "service", instrument="public_service", population="families"
        )
    )
    graph = _graph(
        service,
        _rule(required_facets={"instrument_type": "public_service"}),
    )

    assert len(graph.candidate_ledger) == 1
    candidate = graph.candidate_ledger[0]
    assert candidate.metadata["grammar_limitations"] == ("policy_grammar_facet_choice_not_scoped",)
    assert candidate.metadata["grammar_limitation_messages"] == (
        "The scalar choice is not component scoped.",
    )
    assert len(candidate.metadata["grammar_limitation_details"]) == 1
    assert candidate.metadata["semantic_scope_provenance"] == "not_established"


@pytest.mark.parametrize(
    ("facets", "reason"),
    [
        (
            (
                *_component_facets("service", instrument="public_service", population="families"),
                FacetSnapshot(
                    facet_id="legacy:unscoped",
                    facet_type="instrument_type",
                    value="credit",
                    concept_ref="concept://instrument",
                    scope="families:north",
                    authority_profile="candidate",
                    temporal_window="2026",
                ),
            ),
            "component_facet_lineage_incomplete",
        ),
        (
            tuple(
                facet.model_copy(
                    update={
                        "metadata": {
                            **facet.metadata,
                            "source_intervention_sha256": "not-a-digest",
                        }
                    }
                )
                for facet in _component_facets(
                    "service", instrument="public_service", population="families"
                )
            ),
            "component_facet_lineage_incomplete",
        ),
        (
            (
                *_component_facets("service", instrument="public_service", population="families"),
                _component_facets("service", instrument="credit", population="families")[
                    0
                ].model_copy(update={"facet_id": "case:component:service:instrument-conflict"}),
            ),
            "component_facet_axis_ambiguous",
        ),
        (
            tuple(
                facet.model_copy(update={"scope": "another:population"})
                if facet.facet_type == "method_need"
                else facet
                for facet in _component_facets(
                    "service", instrument="public_service", population="families"
                )
            ),
            "component_facet_scope_inconsistent",
        ),
    ],
)
def test_ambiguous_or_incomplete_component_groups_fail_closed(
    facets: tuple[FacetSnapshot, ...], reason: str
) -> None:
    with pytest.raises(ObligationGraphCompileError, match=reason):
        _graph(facets, _rule(required_facets={"instrument_type": "public_service"}))


def test_unanchored_shared_rule_is_emitted_once_for_the_whole_policy() -> None:
    facets = (
        *_component_facets("service", instrument="public_service", population="families"),
        *_component_facets("credit", instrument="credit", population="msmes"),
    )

    graph = _graph(facets, _rule(rule_id="shared-context"))

    assert len(graph.candidate_ledger) == 1
    assert graph.candidate_ledger[0].candidate_id == "rule:shared-context"
    assert "component_id" not in graph.candidate_ledger[0].metadata
    assert graph.candidate_ledger[0].scope == "municipal"
