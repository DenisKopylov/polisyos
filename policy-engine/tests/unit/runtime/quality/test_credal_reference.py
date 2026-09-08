from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import duckdb
import pytest

from polisyos.data_forge.domains.academic.knowledge import skg_versioning
from polisyos.data_forge.domains.academic.knowledge.types import (
    CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
    CausalClaimResultV2,
    ClaimVocabularyLimitation,
    ClaimVocabularyProjectionBinding,
    ClaimVocabularySourceRowBinding,
)
from polisyos.ir.analytics.literature import (
    ClaimVocabularyAxisStatus,
    DesignFamily,
    EvidenceStrength,
    SourceBasis,
)
from polisyos.runtime.quality.credal_reference import (
    DEFAULT_L2_SCHOLAR_KG_PATH,
    AdmissibleCompletion,
    CredalReference,
    CredalReferenceEdge,
    _derive_l2_causal_claim,
    _iter_l2_edges,
    all_essential_confirmed,
    bind_grounding_certificate_reference,
    build_credal_reference,
    build_grounding_backend_availability,
    derive_variable_alignment_edge,
    essential_edge_scope_definition,
    reference_certificate_staleness,
    reference_lift,
    replace_reference_edge,
)

REPO_ROOT = Path(__file__).resolve().parents[4]


def _phase5_l6_law_scope():
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality import grounding_relation as atoms
    from polisyos.runtime.quality import intervention_substrate as substrate

    world = substrate.production_composed_world_model_record(REPO_ROOT)
    bundle = substrate.load_l6_intervention_substrate(REPO_ROOT)
    edges = [*owner._iter_l6_edges(REPO_ROOT, world_model_record=world),
             *owner._iter_wmr_edges(world)]
    index = {edge.key: edge for edge in edges}
    versions = owner._component_versions(index, world_model_record=world)
    digest = owner._reference_hash(component_versions=versions, edge_index=index,
                                   as_of=owner.DEFAULT_REFERENCE_AS_OF)
    scoped = CredalReference(owner.CREDAL_REFERENCE_SCHEMA_VERSION,
                            "kref:" + digest.removeprefix("sha256:")[:16], digest,
                            owner.DEFAULT_REFERENCE_AS_OF, versions, index)
    return bundle, scoped, atoms._reference_atoms_from_cg0(scoped)


def _assert_phase5_law_scope_preserved_and_nonconfirmed(bundle, scoped, atoms):
    laws = {edge.edge_id: edge for edge in scoped.essential_edges.values()
            if edge.modality == "L6_LEX_INTERVENTION_MAP"}
    raw = json.loads((REPO_ROOT / "production_data/ukraine_agent_simulation_baseline_20260410/"
                      "production_bundle/bundles/intervention_bundle_v1/lex_intervention_map.json")
                     .read_text())
    assert set(laws) == set(bundle.lex_intervention_map) == set(raw)
    assert {edge.status for edge in laws.values()} == {"incomplete"}
    expected_knobs = set(bundle.knob_dictionary)
    assert {atom.signature.op for atom in atoms} == expected_knobs
    law_keys = {f"{edge.modality}::{edge.edge_id}" for edge in laws.values()}
    for atom in atoms:
        assert law_keys.intersection(atom.edge_scope)
        assert atom.signature.admissibility == "reference_contested"


def test_phase5_law_owner_refusal_survives_credal_and_atom_consumers() -> None:
    _assert_phase5_law_scope_preserved_and_nonconfirmed(*_phase5_l6_law_scope())


def test_phase5_law_resolution_exception_keeps_declared_dependency(monkeypatch) -> None:
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.intervention_substrate import InterventionSubstrateError

    def unresolved(*args, **kwargs):
        raise InterventionSubstrateError("law_threshold_unresolved")

    monkeypatch.setattr(owner, "resolve_law_bound_lever", unresolved)
    _assert_phase5_law_scope_preserved_and_nonconfirmed(*_phase5_l6_law_scope())


@pytest.mark.parametrize("removed", ["status", "association"])
def test_phase5_law_handoff_removal_goes_red(monkeypatch, removed) -> None:
    from polisyos.runtime.quality import credal_reference as owner

    original = owner._edge

    def removed_property(modality, edge_id, status, completions, provenance, **kwargs):
        if modality == "L6_LEX_INTERVENTION_MAP":
            if removed == "status":
                status = "confirmed"
            else:
                completions = owner._incomplete_completions("law_mapping_correspondence_not_established")
        return original(modality, edge_id, status, completions, provenance, **kwargs)

    monkeypatch.setattr(owner, "_edge", removed_property)
    with pytest.raises(AssertionError):
        _assert_phase5_law_scope_preserved_and_nonconfirmed(*_phase5_l6_law_scope())


def test_phase5_historical_reference_replay_keeps_epoch_and_current_stales_it() -> None:
    from dataclasses import replace

    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.promotion_sequence import _CredalReferenceReplayRecord

    _bundle, current, _atoms = _phase5_l6_law_scope()
    historical_schema = "policyos.runtime.grounding_credal_reference.v1"
    old_hash = owner._reference_hash(component_versions=current.component_versions,
        edge_index=current.essential_edges, as_of=current.as_of, schema_version=historical_schema)
    historical = replace(current, schema_version=historical_schema, reference_hash=old_hash,
                         reference_epoch="kref:" + old_hash.removeprefix("sha256:")[:16])
    assert _CredalReferenceReplayRecord.from_reference(historical).to_reference() == historical
    edge = next(iter(historical.essential_edges.values()))
    assert owner.replace_reference_edge(historical, edge) == historical
    assert current.schema_version == "policyos.runtime.grounding_credal_reference.v2"
    certificate = owner.bind_grounding_certificate_reference(
        historical, certificate_id="historical_epoch_replay_control", edge_scope=(edge.key,),
    )
    assert owner.reference_certificate_staleness(certificate, current).status != "current"


def test_credal_reference_consumes_bound_layer_vintage_before_first_yield(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / DEFAULT_L2_SCHOLAR_KG_PATH
    db_path.parent.mkdir(parents=True)
    with duckdb.connect(str(db_path)) as con:
        con.execute("CREATE TABLE ac_skg_versions (version_id INTEGER)")
        con.execute("INSERT INTO ac_skg_versions VALUES (1)")
        con.execute(
            "CREATE TABLE ac_skg_variables (canonical_name VARCHAR, "
            "approved_canonical_name VARCHAR, is_approved_canonical BOOLEAN, "
            "resolution_method VARCHAR, resolution_confidence DOUBLE, "
            "mention_count INTEGER, parent_name VARCHAR, approved_parent_name VARCHAR)"
        )
        con.execute(
            "INSERT INTO ac_skg_variables VALUES "
            "('cause', 'cause', TRUE, 'fixture', 0.9, 3, NULL, NULL)"
        )
    with db_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()

    unregistered = iter(_iter_l2_edges(tmp_path))
    try:
        assert next(unregistered).edge_id == "cause"
    finally:
        unregistered.close()

    monkeypatch.setattr(skg_versioning, "_HISTORICAL_SNAPSHOT_SHA256", digest, raising=False)
    registered = iter(_iter_l2_edges(tmp_path))
    try:
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            next(registered)
    finally:
        registered.close()


@pytest.fixture(scope="module")
def reference() -> CredalReference:
    os.environ.setdefault("JAX_PLATFORM_NAME", "cpu")
    os.environ.setdefault("JAX_PLATFORMS", "cpu")
    return build_credal_reference(REPO_ROOT)


def test_contested_edge_lifts_set_valued_and_blocks_confirmation(
    reference: CredalReference,
) -> None:
    contested = _first_edge(reference, "L2_CONTESTED_EDGE", "contested")

    lift = reference_lift(reference, [contested.key])
    lifted = lift[f"{contested.modality}::{contested.edge_id}"]

    assert lifted["status"] == "contested"
    assert lifted["is_set_valued"] is True
    assert len(lifted["admissible_completions"]) > 1
    assert all_essential_confirmed(reference, [contested.key]) is False
    assert "scalar_confidence" not in str(lifted)


def test_fake_edge_fails_closed_out_of_scope(reference: CredalReference) -> None:
    fake_key = ("L2_CAUSAL_EDGE", "cg0_fake_novel_edge_not_in_reference")

    lift = reference_lift(reference, [fake_key])
    lifted = lift["L2_CAUSAL_EDGE::cg0_fake_novel_edge_not_in_reference"]

    assert lifted["status"] == "out_of_scope"
    assert all_essential_confirmed(reference, [fake_key]) is False


def test_free_grow_alignment_statuses_without_known_edge_table() -> None:
    edge = derive_variable_alignment_edge(
        {
            "approved": True,
            "canonical_name": "cg0.free_grow_reference_probe",
            "confidence": 0.91,
            "method": "unit_test_free_grow_probe",
            "synonym": "cg0 novel alignment synonym",
        }
    )

    assert edge.status == "confirmed"
    assert edge.key == (
        "L2_VARIABLE_ALIGNMENT",
        "cg0 novel alignment synonym->cg0.free_grow_reference_probe",
    )
    assert edge.provenance["signals"]["method"] == "unit_test_free_grow_probe"


def test_expanded_essential_scope_classes_are_counted(reference: CredalReference) -> None:
    counts = reference.denominator_counts()
    scope = essential_edge_scope_definition()
    modalities = {
        edge_class["modality"] for edge_class in scope["included_edge_classes"]
    }

    assert "L2_FAMILY_EDGE" in modalities
    assert "L2_MODERATION_EDGE" in modalities
    assert "L2_DATA_FORGE_VARIABLE_ALIGNMENT" in modalities
    assert "L3_REFERENCE_EDGE" in modalities
    assert counts["L2_FAMILY_EDGE"]["total"] == 15945
    assert counts["L2_MODERATION_EDGE"]["total"] == 25035
    assert counts["L2_DATA_FORGE_VARIABLE_ALIGNMENT"]["total"] == 20326
    assert counts["L3_REFERENCE_EDGE"]["total"] == 73793


def test_exact_and_family_edge_payloads_match_pre_split_oracles(
    reference: CredalReference,
) -> None:
    """Freeze complete payload behavior for the two forbidden Runtime paths."""

    expected = {
        ("L2_CAUSAL_EDGE", "000fccc608c3d9b6447fd636"): (
            '{"admissible_completions":[{"completion_kind":"alternative",'
            '"reason":"edge_candidate_supported","value":{"direction":"null",'
            '"dst":"health.appointment_attendance","src":"digital.sms_reminder"}},'
            '{"completion_kind":"may_not_exist","reason":"edge_quality_not_decisive",'
            '"value":{"direction":"null","dst":"health.appointment_attendance",'
            '"src":"digital.sms_reminder"}}],"content_hash":'
            '"sha256:5b340aa61431fab375278ccf3e0d833b99c2515ae9ec5e565b04080e8c3ee84b",'
            '"edge_id":"000fccc608c3d9b6447fd636","modality":"L2_CAUSAL_EDGE",'
            '"provenance":{"owner":"L2","signals":{"candidate_layer":"candidate",'
            '"confidence":0.55,"design_quality_tiers":[1],'
            '"edge_in_contested_membership":false,"evidence_strength":"meta_analysis",'
            '"n_articles":1,"publish_blockers":["paper_classified_non_empirical"],'
            '"strong_design_evidence":{"all":false,"any":false,"count":0,'
            '"share_pct":0.0}},"source":"ac_skg_edges","version":"1"},'
            '"scale":null,"status":"contested","unit":null}'
        ),
        ("L2_FAMILY_EDGE", "000771faec1207ef6d7aaa31"): (
            '{"admissible_completions":[{"completion_kind":"may_exist",'
            '"reason":"family_edge_endpoint_unresolved","value":{}},'
            '{"completion_kind":"may_not_exist",'
            '"reason":"family_edge_endpoint_unresolved","value":{}},'
            '{"completion_kind":"partial","reason":"family_edge_endpoint_unresolved",'
            '"value":{}}],"content_hash":'
            '"sha256:0149a83f050a1f565189c4af228bd731739de1c57fdabeade484f4b6d14213fa",'
            '"edge_id":"000771faec1207ef6d7aaa31","modality":"L2_FAMILY_EDGE",'
            '"provenance":{"owner":"L2","signals":{"candidate_layer":"family",'
            '"confidence":0.06428995006744742,"design_tier_histogram":{"3":1},'
            '"direction_agreement":1.0,"edge_in_contested_membership":false,'
            '"evidence_strength":"observational","n_articles":1,"n_claims":1,'
            '"quality_signals":{"conflict_flag":false,"direction_agreement":1.0,'
            '"exact_edge_count":1,"exact_edge_ids":["000771faec1207ef6d7aaa31"],'
            '"n_unique_claims":1,"n_unique_works":1}},'
            '"source":"ac_skg_family_edges","version":"1"},'
            '"scale":null,"status":"incomplete","unit":null}'
        ),
    }

    for key, oracle in expected.items():
        edge = reference.essential_edges[key]
        payload = json.dumps(
            edge.to_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        assert payload == oracle


def test_reference_repair_stales_dependent_certificate(
    reference: CredalReference,
) -> None:
    contested = _first_edge(reference, "L2_CONTESTED_EDGE", "contested")
    certificate = bind_grounding_certificate_reference(
        reference,
        certificate_id="cg0-unit-staling",
        edge_scope=[contested.key],
    )
    repaired_edge = CredalReferenceEdge(
        modality=contested.modality,
        edge_id=contested.edge_id,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"repaired_from": contested.edge_id},
                "unit_test_reference_repair",
            ),
        ),
        provenance={**dict(contested.provenance), "unit_test": "reference_repair"},
        unit=contested.unit,
        scale=contested.scale,
    )

    repaired_reference = replace_reference_edge(reference, repaired_edge)
    staleness = reference_certificate_staleness(certificate, repaired_reference)

    assert repaired_reference.reference_epoch != reference.reference_epoch
    assert staleness.status == "stale"
    assert "scoped_edge_hash_changed" in staleness.reasons


def test_backend_availability_pins_cp_sat_and_defers_dense() -> None:
    backend = build_grounding_backend_availability().to_payload()

    assert backend["required_backend_status"] == "available"
    assert backend["solver"]["name"] == "ortools_cp_sat"
    assert backend["solver"]["available"] is True
    assert backend["solver"]["unsat_core"] == "assumptions"
    assert backend["milp_fallback"]["solver"] == "HiGHS"
    assert backend["sparse"]["name"] == "duckdb_fts"
    assert backend["ann"]["name"] == "hnswlib"
    assert backend["dense"]["status"] == "deferred"


def _claim_result(**updates: object) -> CausalClaimResultV2:
    source = ClaimVocabularySourceRowBinding(
        source_table="ac_causal_claims",
        source_schema_version="legacy_v1",
        source_identity="claim-1|work-1",
        source_row_sha256="a" * 64,
    )
    values: dict[str, object] = {
        "id": "claim-1",
        "work_id": "work-1",
        "cause": "x",
        "effect": "y",
        "direction": "positive",
        "trust_score": 0.9,
        "strong_design_evidence": True,
        "design_quality_tier": 1,
        "legacy_strength_label": "rct",
        "limitations": (ClaimVocabularyLimitation.AMBIGUOUS_LEGACY_VOCABULARY,),
        "projection_binding": ClaimVocabularyProjectionBinding(
            projection_rule_version=CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
            subject_kind="claim_row",
            source_rows=(source,),
            projected_vocabulary_sha256="b" * 64,
        ),
    }
    values.update(updates)
    return CausalClaimResultV2.model_validate(values)


def test_runtime_causal_claim_emits_typed_axes_and_preserves_status_logic() -> None:
    legacy_result = _claim_result()

    confirmed = _derive_l2_causal_claim(
        legacy_result,
        version="fixture-v1",
        variable_names={"x", "y"},
        contested_claims=set(),
    )
    contested = _derive_l2_causal_claim(
        legacy_result,
        version="fixture-v1",
        variable_names={"x", "y"},
        contested_claims={"claim-1"},
    )
    incomplete = _derive_l2_causal_claim(
        legacy_result,
        version="fixture-v1",
        variable_names={"x"},
        contested_claims=set(),
    )

    assert (confirmed.status, contested.status, incomplete.status) == (
        "confirmed",
        "contested",
        "incomplete",
    )
    value = confirmed.admissible_completions[0].value
    assert "strength" not in value
    assert value == {
        "cause": "x",
        "direction": "positive",
        "effect": "y",
        "design_family_hint": None,
        "design_family_hint_status": "not_established",
        "evidence_strength": None,
        "evidence_strength_status": "not_established",
        "claim_extraction_confidence": None,
        "claim_extraction_confidence_status": "not_established",
        "source_basis": None,
        "source_basis_status": "not_established",
    }
    provenance = confirmed.provenance["signals"]["claim_vocabulary"]
    assert provenance["legacy_strength_label"] == "rct"
    assert provenance["limitations"] == ["ambiguous_legacy_vocabulary"]
    assert provenance["projection_binding"]["source_rows"][0]["source_identity"] == (
        "claim-1|work-1"
    )


def test_runtime_causal_claim_keeps_disagreeing_candidate_axes_separate() -> None:
    result = _claim_result(
        legacy_strength_label=None,
        limitations=(),
        design_family_hint=DesignFamily.RCT,
        design_family_hint_status=ClaimVocabularyAxisStatus.CANDIDATE,
        evidence_strength=EvidenceStrength.OBSERVATIONAL,
        evidence_strength_status=ClaimVocabularyAxisStatus.CANDIDATE,
        claim_extraction_confidence=0.81,
        claim_extraction_confidence_status=ClaimVocabularyAxisStatus.CANDIDATE,
        source_basis=SourceBasis.ABSTRACT_ONLY,
        source_basis_status=ClaimVocabularyAxisStatus.CANDIDATE,
    )

    edge = _derive_l2_causal_claim(
        result,
        version="fixture-v2",
        variable_names={"x", "y"},
        contested_claims=set(),
    )

    value = edge.admissible_completions[0].value
    assert value["design_family_hint"] == "rct"
    assert value["evidence_strength"] == "observational"
    assert value["claim_extraction_confidence"] == 0.81
    assert value["source_basis"] == "abstract_only"
    assert "strength" not in value


def _first_edge(
    reference: CredalReference,
    modality: str,
    status: str,
) -> CredalReferenceEdge:
    for edge in sorted(reference.essential_edges.values(), key=lambda item: item.key):
        if edge.modality == modality and edge.status == status:
            return edge
    raise AssertionError(f"missing {modality} edge with status {status}")
