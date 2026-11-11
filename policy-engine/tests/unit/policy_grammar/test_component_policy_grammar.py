from __future__ import annotations

import json
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import FileSystemCAS, PutOptions, SchemaInfo
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts import UniversalPolicyDesignCase
from polisyos.ir.governance import (
    InterventionSpec,
    PolicyLayerLevel,
    PolicySpec,
    ProblemDomain,
    ProblemFrame,
    ScheduleSpec,
    SelectorPredicate,
)
from polisyos.ir.observation import IdentificationMode
from polisyos.policy_grammar import (
    UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND,
    PolicyGrammarCompiler,
    PolicyGrammarConceptSpineRefs,
    PolicyGrammarConsumerError,
    PolicyGrammarIntent,
    UniversalAuthorityProfile,
    assert_authority_slot_eligible,
    facet_snapshots_for_obligation_graph,
    identification_mode_origin_for_rule,
    load_universal_policy_design_case,
    require_compiled_universal_policy_design_case,
)


def _intervention(
    component_id: str,
    *,
    kind: str,
    population: str,
    region: str,
    mode: IdentificationMode,
    duration: int = 12,
) -> InterventionSpec:
    return InterventionSpec(
        intervention_id=component_id,
        kind=kind,
        target=SelectorPredicate(
            kind="predicate", field="population", operator="==", value=population
        ),
        schedule=ScheduleSpec(start_step=0, duration_steps=duration),
        params={"budget": Decimal("10")},
        target_population_type=population,
        target_region_ids=[region],
        identification_mode=mode,
    )


def _intent(*, reverse: bool = False) -> PolicyGrammarIntent:
    components = [
        _intervention(
            "delivery",
            kind="service",
            population="children",
            region="rural",
            mode=IdentificationMode.SEQUENTIAL,
        ),
        _intervention(
            "financing",
            kind="credit",
            population="msmes",
            region="national",
            mode=IdentificationMode.BOUNDS_ONLY,
        ),
    ]
    return PolicyGrammarIntent.from_problem_policy(
        intent_id="explicit_compound",
        problem_frame=ProblemFrame(
            problem_id="shared_problem",
            domain=ProblemDomain.CUSTOM,
            narrative="A global housing subsidy for urban renters is a separate problem context.",
        ),
        policy_spec=PolicySpec(
            policy_id="compound_policy",
            interventions=list(reversed(components)) if reverse else components,
        ),
    )


def _authority(*, llm: bool = False) -> UniversalAuthorityProfile:
    return UniversalAuthorityProfile(
        profile_id="component_compilation",
        authority_type=PolicyLayerLevel.FEDERAL,
        source_classification="llm_candidate" if llm else "deterministic_producer",
        authoritative_for=("compilation_facets",),
        may_not_use_for=(
            "legal_authority",
            "data_authority",
            "method_authority",
            "closeout_authority",
            "publication_authority",
        ),
    )


def _refs() -> PolicyGrammarConceptSpineRefs:
    return PolicyGrammarConceptSpineRefs(
        concept_spine_ref="concept-spine://components",
        jurisdiction_spine_ref="jurisdiction-spine://components",
        canonical_concept_refs=("concept://declared-action",),
    )


def _compile(intent: PolicyGrammarIntent | None = None) -> UniversalPolicyDesignCase:
    return PolicyGrammarCompiler().compile(
        intent=intent or _intent(), authority_profile=_authority(), concept_spine_refs=_refs()
    )


@pytest.mark.parametrize("reverse", [False, True])
def test_compound_keeps_component_scopes_and_modes_without_shared_prose_pollution(
    reverse: bool,
) -> None:
    case = _compile(_intent(reverse=reverse))

    assert case.schema_version == "policyos.universal_policy_design_case.v2"
    assert case.status == "compiled"
    assert case.facets is None
    components = {component.component_id: component for component in case.components}
    assert set(components) == {"delivery", "financing"}
    assert components["delivery"].facets.instrument_type.value == "service"
    assert components["delivery"].facets.delivery_channel.value == "public_service"
    assert components["delivery"].facets.population_predicate.value == "children"
    assert components["delivery"].facets.geography_predicate.value == "rural"
    assert components["delivery"].facets.method_need.value == IdentificationMode.SEQUENTIAL
    assert components["financing"].facets.instrument_type.value == "credit"
    assert components["financing"].facets.population_predicate.value == "msmes"
    assert components["financing"].facets.geography_predicate.value == "national"
    assert components["financing"].facets.method_need.value == IdentificationMode.BOUNDS_ONLY
    assert all(component.facets.time_predicate.value == "annual" for component in case.components)
    rows = facet_snapshots_for_obligation_graph(case)
    assert len(rows) == 22
    for row in rows:
        metadata = row["metadata"]
        component_id = metadata["component_id"]
        assert row["scope"] == (
            "children:rural" if component_id == "delivery" else "msmes:national"
        )
        assert (
            metadata["source_intervention_sha256"]
            == components[component_id].source_intervention_sha256
        )
        assert metadata["component_limitations"] == (
            "policy_grammar_shared_context_not_component_scoped",
        )
        assert metadata["source_intent_sha256"] == case.source_intent_sha256
    assert len({row["facet_id"] for row in rows}) == 22


def test_same_instrument_components_keep_distinct_scopes() -> None:
    intent = _intent()
    policy = intent.policy_spec
    assert policy is not None
    second = _intervention(
        "other_delivery",
        kind="service",
        population="patients",
        region="urban",
        mode=IdentificationMode.PARTIALLY_IDENTIFIED,
    )
    policy = policy.model_copy(update={"interventions": [policy.interventions[0], second]})
    case = _compile(intent.model_copy(update={"policy_spec": policy}))
    grouped = {component.component_id: component.facets for component in case.components}

    assert case.status == "compiled"
    assert grouped["delivery"].population_predicate.value == "children"
    assert grouped["other_delivery"].population_predicate.value == "patients"
    assert grouped["other_delivery"].geography_predicate.value == "urban"
    assert grouped["other_delivery"].method_need.value == IdentificationMode.PARTIALLY_IDENTIFIED


def test_same_mode_compound_preserves_independent_component_scope() -> None:
    intent = _intent()
    policy = intent.policy_spec
    assert policy is not None
    policy = policy.model_copy(
        update={
            "interventions": [
                intervention.model_copy(
                    update={"identification_mode": IdentificationMode.POINT_IDENTIFIED}
                )
                for intervention in policy.interventions
            ]
        }
    )
    case = _compile(intent.model_copy(update={"policy_spec": policy}))

    observed = {
        component.component_id: (
            component.facets.instrument_type.value,
            component.facets.population_predicate.value,
            component.facets.geography_predicate.value,
        )
        for component in case.components
    }
    assert observed == {
        "delivery": ("service", "children", "rural"),
        "financing": ("credit", "msmes", "national"),
    }


def test_v2_identity_binds_changed_declared_source_and_shared_text() -> None:
    intent = _intent()
    original = _compile(intent)
    policy = intent.policy_spec
    assert policy is not None
    changed_intervention = policy.interventions[0].model_copy(
        update={"params": {"budget": Decimal("11")}}
    )
    changed_policy = policy.model_copy(
        update={"interventions": [changed_intervention, policy.interventions[1]]}
    )
    changed = _compile(intent.model_copy(update={"policy_spec": changed_policy}))
    text_changed = _compile(intent.model_copy(update={"text": "Different declared context."}))

    assert original.case_id != changed.case_id
    assert original.case_id != text_changed.case_id
    assert original.source_intent_sha256 != changed.source_intent_sha256
    assert original.components[0].source_intervention_sha256 != (
        changed.components[0].source_intervention_sha256
    )
    assert original.components[0].facets == changed.components[0].facets


def test_unsupported_component_blocks_without_exposing_partial_compilation() -> None:
    intent = _intent()
    policy = intent.policy_spec
    assert policy is not None
    invalid = policy.interventions[1].model_copy(
        update={"kind": "unknown_action", "target_population_type": "unclassified"}
    )
    case = _compile(
        intent.model_copy(
            update={
                "policy_spec": policy.model_copy(
                    update={"interventions": [policy.interventions[0], invalid]}
                )
            }
        )
    )

    assert case.status == "blocked"
    assert not case.components
    assert case.facets is None
    assert any("financing" in blocker.message for blocker in case.blockers)
    with pytest.raises(PolicyGrammarConsumerError, match="blocked"):
        facet_snapshots_for_obligation_graph(case)


def test_compound_candidate_keeps_protected_authority_ceiling() -> None:
    case = PolicyGrammarCompiler().compile(
        intent=_intent(), authority_profile=_authority(llm=True), concept_spine_refs=_refs()
    )

    assert case.status == "candidate_unverified"
    assert len(case.components) == 2
    for purpose in ("data_authority", "method_authority", "publication_authority"):
        with pytest.raises(PolicyGrammarConsumerError, match="candidate_unverified"):
            assert_authority_slot_eligible(case, purpose)


@pytest.mark.parametrize(
    "mutation", ["v1", "unscoped", "duplicate", "bad_hash", "partial", "blocking_component"]
)
def test_v2_wire_rejects_component_shape_or_version_grafts(mutation: str) -> None:
    payload = _compile().model_dump(mode="json")
    if mutation == "v1":
        payload["schema_version"] = "policyos.universal_policy_design_case.v1"
    elif mutation == "unscoped":
        payload["facets"] = payload["components"][0]["facets"]
    elif mutation == "duplicate":
        payload["components"].append(payload["components"][0])
    elif mutation == "bad_hash":
        payload["components"][0]["source_intervention_sha256"] = "sha256:unknown"
    elif mutation == "blocking_component":
        payload["blockers"][0]["severity"] = "blocked"
    else:
        payload["status"] = "blocked"
    with pytest.raises(ValidationError):
        UniversalPolicyDesignCase.model_validate(payload)


def test_singleton_v1_wire_keeps_legacy_shape_and_reader(tmp_path: Path) -> None:
    intent = _intent()
    policy = intent.policy_spec
    assert policy is not None
    singleton = intent.model_copy(
        update={
            "text": None,
            "problem_frame": None,
            "policy_spec": policy.model_copy(update={"interventions": [policy.interventions[0]]}),
        }
    )
    store = FileSystemCAS(tmp_path / "cas")
    saved = PolicyGrammarCompiler().compile_and_persist(
        store=store, intent=singleton, authority_profile=_authority(), concept_spine_refs=_refs()
    )
    payload = saved.case.model_dump(mode="json")

    assert saved.case.schema_version == "policyos.universal_policy_design_case.v1"
    assert "components" not in payload
    assert "source_intent_sha256" not in payload
    assert store.get_manifest(saved.artifact_ref).artifact_schema.version == (
        "policyos.universal_policy_design_case.v1"
    )
    loaded = load_universal_policy_design_case(FileSystemCAS(tmp_path / "cas"), saved.artifact_ref)
    assert require_compiled_universal_policy_design_case(loaded).facets == saved.case.facets


def test_component_reader_refuses_same_payload_under_legacy_schema_profile(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    case = _compile()
    ref = store.put_json(
        case.model_dump(mode="json", exclude={"persisted_artifact_ref"}),
        PutOptions(
            kind=UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND,
                version="policyos.universal_policy_design_case.v1",
            ),
        ),
        canon_spec=CanonSpec(),
    )

    with pytest.raises(ValueError, match="component_artifact_schema_mismatch"):
        load_universal_policy_design_case(FileSystemCAS(tmp_path / "cas"), ref)


def test_compound_cas_persistence_and_fresh_process_consumer(tmp_path: Path) -> None:
    cas_root = tmp_path / "cas"
    store = FileSystemCAS(cas_root)
    saved = PolicyGrammarCompiler().compile_and_persist(
        store=store, intent=_intent(), authority_profile=_authority(), concept_spine_refs=_refs()
    )
    assert store.get_manifest(saved.artifact_ref).artifact_schema.version == (
        "policyos.universal_policy_design_case.v2"
    )
    script = """
import json, sys
from pathlib import Path
from polisyos.core.artifacts import ArtifactRef, FileSystemCAS
from polisyos.policy_grammar import load_universal_policy_design_case, facet_snapshots_for_obligation_graph
store = FileSystemCAS.open_existing_read_only(Path(sys.argv[1]))
case = load_universal_policy_design_case(store, ArtifactRef.model_validate_json(sys.argv[2]))
rows = facet_snapshots_for_obligation_graph(case)
print(json.dumps({'case': case.case_id, 'rows': rows}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script, str(cas_root), saved.artifact_ref.model_dump_json()],
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    observed = json.loads(completed.stdout)
    assert observed["case"] == saved.case.case_id
    assert len(observed["rows"]) == 22
    assert {row["metadata"]["component_id"] for row in observed["rows"]} == {
        "delivery",
        "financing",
    }
    assert {
        (row["metadata"]["component_id"], row["value"])
        for row in observed["rows"]
        if row["facet_type"] == "method_need"
    } == {("delivery", "sequential"), ("financing", "bounds_only")}


@pytest.mark.parametrize(
    "text",
    [
        (
            "Provide vaccination services to rural children and concessional credit "
            "to MSMEs in 2026."
        ),
        (
            "Provide concessional credit to MSMEs in 2026 and vaccination services "
            "to rural children."
        ),
        (
            "Provide a service to rural children and another service to urban "
            "patients, with budget funding in 2026."
        ),
        (
            "Provide a voucher to students and another voucher to households "
            "with annual budget funding."
        ),
    ],
)
def test_unstructured_competing_population_choices_refuse_hybrid_projection(text: str) -> None:
    case = _compile(PolicyGrammarIntent(intent_id="unstructured_compound", text=text))

    assert case.facets is None
    assert case.status == "blocked"
    assert not case.components
    blocker = next(
        blocker
        for blocker in case.blockers
        if blocker.code == "policy_grammar_population_composition_unsupported"
    )
    records = blocker.details["selector_candidates"]
    assert (
        len(
            {
                record["candidate_value"]
                for record in records
                if record["facet_name"] == "population_predicate"
                and record["evidence_role"] == "explicit_controlled_token"
            }
        )
        >= 2
    )
    assert blocker.details["semantic_scope_provenance"] == "not_established"
    assert all(record["matched_terms"] and record["rule_ref"] for record in records)
    with pytest.raises(PolicyGrammarConsumerError, match="blocked"):
        facet_snapshots_for_obligation_graph(case)


@pytest.mark.parametrize(
    ("text", "facet_name", "value"),
    [
        (
            "Create a concessional credit programme for MSMEs in 2026 to preserve employment.",
            "population_predicate",
            "msmes",
        ),
        (
            "Provide a means-tested housing voucher subsidy for low-income renters "
            "through municipal service centres with annual appropriations.",
            "instrument_type",
            "subsidy",
        ),
    ],
)
def test_contextual_selector_ambiguity_preserves_singleton_with_declared_limitation(
    text: str, facet_name: str, value: str, tmp_path: Path
) -> None:
    intent = PolicyGrammarIntent(intent_id="bounded_singleton", text=text)
    store = FileSystemCAS(tmp_path / "cas")
    saved = PolicyGrammarCompiler().compile_and_persist(
        store=store, intent=intent, authority_profile=_authority(), concept_spine_refs=_refs()
    )
    case = load_universal_policy_design_case(FileSystemCAS(tmp_path / "cas"), saved.artifact_ref)

    assert case.schema_version == "policyos.universal_policy_design_case.v2"
    assert case.source_intent_sha256 is not None
    assert not case.components
    assert store.get_manifest(saved.artifact_ref).artifact_schema.version == case.schema_version
    assert case.status == "compiled"
    assert case.facets is not None
    assert getattr(case.facets, facet_name).value == value
    assert any(
        blocker.code == "policy_grammar_facet_choice_not_scoped" and blocker.severity == "warning"
        for blocker in case.blockers
    )
    rows = facet_snapshots_for_obligation_graph(case)
    assert rows
    assert all(row["metadata"]["semantic_scope_provenance"] == "not_established" for row in rows)
    assert all(row["metadata"]["source_intent_sha256"] == case.source_intent_sha256 for row in rows)
    details = rows[0]["metadata"]["grammar_limitation_details"]
    records = [record for detail in details for record in detail["selector_candidates"]]
    assert all(record["matched_terms"] and record["rule_ref"] for record in records)
    if facet_name == "population_predicate":
        fallback = next(record for record in records if record["candidate_value"] == "workers")
        assert fallback["evidence_role"] == "inferential_fallback"
        assert fallback["matched_terms"] == ["employment"]
    else:
        assert {record["candidate_value"] for record in records} >= {"subsidy", "service"}


@pytest.mark.parametrize("details", [{}, {"semantic_scope_provenance": "not_established"}])
def test_legacy_v1_refuses_even_empty_extended_blocker_details(details: dict[str, str]) -> None:
    legacy = _compile(PolicyGrammarIntent(intent_id="legacy_blocked", text="Unclassified input."))
    assert legacy.schema_version == "policyos.universal_policy_design_case.v1"
    assert legacy.blockers
    payload = legacy.model_dump(mode="json")
    payload["blockers"][0]["details"] = details

    with pytest.raises(ValidationError, match=r"v1.*blocker details"):
        UniversalPolicyDesignCase.model_validate(payload)


@pytest.mark.parametrize(
    ("new_field", "value"), [("components", []), ("source_intent_sha256", None)]
)
def test_legacy_v1_refuses_empty_extended_case_fields(new_field: str, value: object) -> None:
    legacy = _compile(PolicyGrammarIntent(intent_id="legacy_blocked", text="Unclassified input."))
    payload = legacy.model_dump(mode="json")
    payload[new_field] = value

    with pytest.raises(ValidationError, match=r"v1.*cannot carry components"):
        UniversalPolicyDesignCase.model_validate(payload)


def test_scalar_v2_cannot_lose_its_only_representation() -> None:
    scalar = _compile(
        PolicyGrammarIntent(
            intent_id="scalar_projection",
            text="Create annual concessional credit for MSMEs to preserve employment.",
        )
    )
    assert scalar.schema_version == "policyos.universal_policy_design_case.v2"
    payload = scalar.model_dump(mode="json")
    payload["facets"] = None

    with pytest.raises(ValidationError, match=r"v2.*requires scalar facets or compiled components"):
        UniversalPolicyDesignCase.model_validate(payload)


def test_legacy_body_cannot_be_presented_under_extended_manifest_profile(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas")
    legacy = _compile(
        PolicyGrammarIntent(
            intent_id="legacy_scalar",
            text="Provide an annual health service for rural children with budget funding.",
        )
    )
    assert legacy.schema_version == "policyos.universal_policy_design_case.v1"
    ref = store.put_json(
        legacy.model_dump(mode="json", exclude={"persisted_artifact_ref"}),
        PutOptions(
            kind=UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=UNIVERSAL_POLICY_DESIGN_CASE_ARTIFACT_KIND,
                version="policyos.universal_policy_design_case.v2",
            ),
        ),
        canon_spec=CanonSpec(),
    )

    with pytest.raises(ValueError, match="component_artifact_schema_mismatch"):
        load_universal_policy_design_case(FileSystemCAS(tmp_path / "cas"), ref)


def _explicit_mode_intent(mode: IdentificationMode) -> PolicyGrammarIntent:
    return PolicyGrammarIntent.from_problem_policy(
        intent_id="explicit_method_source",
        problem_frame=ProblemFrame(
            problem_id="method_source",
            domain=ProblemDomain.CUSTOM,
            narrative="Improve the selected outcome.",
        ),
        policy_spec=PolicySpec(
            policy_id="method_source",
            interventions=[
                _intervention(
                    "delivery",
                    kind="service",
                    population="children",
                    region="rural",
                    mode=mode,
                )
            ],
        ),
    )


@pytest.mark.parametrize("mode", tuple(IdentificationMode))
def test_explicit_policy_mode_retains_its_actual_derivation_origin(
    mode: IdentificationMode,
) -> None:
    case = _compile(_explicit_mode_intent(mode))
    assert case.facets is not None
    assert case.facets.method_need.value == mode
    assert case.facets.method_need.derivation_rule_ref == (
        "policyos.policy_grammar.facet_derivation.v1:method_need:explicit_policy_spec.v1"
    )
    row = next(
        row
        for row in facet_snapshots_for_obligation_graph(case)
        if row["facet_type"] == "method_need"
    )
    assert row["metadata"]["identification_mode_origin"] == "explicit_policy_spec"


def test_equal_point_modes_keep_distinct_default_and_explicit_origin_after_cas_read(
    tmp_path: Path,
) -> None:
    intents = [
        PolicyGrammarIntent(
            intent_id="ordinary_default",
            text="Provide an annual health service for rural children with budget funding.",
        ),
        _explicit_mode_intent(IdentificationMode.POINT_IDENTIFIED),
    ]
    store = FileSystemCAS(tmp_path / "cas")
    loaded_cases = []
    for intent in intents:
        saved = PolicyGrammarCompiler().compile_and_persist(
            store=store, intent=intent, authority_profile=_authority(), concept_spine_refs=_refs()
        )
        loaded_cases.append(
            load_universal_policy_design_case(FileSystemCAS(tmp_path / "cas"), saved.artifact_ref)
        )
    projected = [
        next(
            row
            for row in facet_snapshots_for_obligation_graph(case)
            if row["facet_type"] == "method_need"
        )
        for case in loaded_cases
    ]

    assert [row["value"] for row in projected] == ["point_identified", "point_identified"]
    assert [row["metadata"]["identification_mode_origin"] for row in projected] == [
        "default_point",
        "explicit_policy_spec",
    ]
    assert (
        projected[0]["metadata"]["derivation_rule_ref"]
        != projected[1]["metadata"]["derivation_rule_ref"]
    )


def test_lexical_rollout_is_inferred_sequential_and_does_not_become_explicit() -> None:
    case = _compile(
        PolicyGrammarIntent(
            intent_id="ordinary_rollout",
            text="Phase a health service for rural children with annual budget funding.",
        )
    )
    row = next(
        row
        for row in facet_snapshots_for_obligation_graph(case)
        if row["facet_type"] == "method_need"
    )

    assert row["value"] == "sequential"
    assert row["metadata"]["identification_mode_origin"] == "inferred_sequential"
    assert row["metadata"]["derivation_rule_ref"] == (
        "policyos.policy_grammar.facet_derivation.v1:method_need:inferred_sequential.v1"
    )


@pytest.mark.parametrize(
    "rule_ref",
    [
        "policyos.policy_grammar.facet_derivation.v1:method_need",
        "point_identified",
        "policyos.policy_grammar.facet_derivation.v1:method_need:explicit_policy_spec.v1:foreign",
    ],
)
def test_generic_or_unknown_method_rule_does_not_establish_explicit_origin(rule_ref: str) -> None:
    case = _compile(_explicit_mode_intent(IdentificationMode.POINT_IDENTIFIED))
    assert case.facets is not None
    method = case.facets.method_need.model_copy(update={"derivation_rule_ref": rule_ref})
    historical_shape = case.model_copy(
        update={"facets": case.facets.model_copy(update={"method_need": method})}
    )
    row = next(
        row
        for row in facet_snapshots_for_obligation_graph(historical_shape)
        if row["facet_type"] == "method_need"
    )

    assert row["value"] == "point_identified"
    assert row["metadata"]["identification_mode_origin"] == "not_established"
    assert identification_mode_origin_for_rule(rule_ref) == "not_established"
