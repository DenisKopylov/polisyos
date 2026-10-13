from __future__ import annotations

import hashlib
import json
import os
from collections import UserDict
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType
from typing import cast

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
    CompletionKind,
    CredalReference,
    CredalReferenceEdge,
    CredalReferenceSourceProfile,
    CredalReferenceStatus,
    _component_versions,
    _credal_reference_source_profile_content_hash,
    _derive_l2_causal_claim,
    _iter_l2_edges,
    _reference_hash,
    all_essential_confirmed,
    bind_grounding_certificate_reference,
    build_credal_reference,
    build_grounding_backend_availability,
    credal_reference_l2_source_profile,
    derive_variable_alignment_edge,
    essential_edge_scope_definition,
    reference_certificate_staleness,
    reference_lift,
    replace_reference_edge,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
_MISSING_FIXTURE_MARKER = object()


def _selected_l2_profile_fixture(
    *,
    source_read_prepared_at_utc: str = "2026-10-11T19:00:00Z",
    source_snapshot_sha256: str = "2" * 64,
    source_version_id: int = 7,
    world_model_record_content_hash: str = "sha256:" + "1" * 64,
) -> CredalReferenceSourceProfile:
    from polisyos.pdc._impl.world_model_record import SkgCausalPriorRef

    snapshot_ref = f"duckdb:///controlled/source.duckdb#v{source_version_id}"
    body = {
        "schema_version": "runtime.quality.credal_reference_skg_source_profile.v1",
        "selection_owner": "world_model_record.skg_causal_prior_ref",
        "world_model_record_content_hash": world_model_record_content_hash,
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref=snapshot_ref,
            skg_version_id=str(source_version_id),
            source_data_snapshot_id="controlled-snapshot",
        ).model_dump(mode="json"),
        "source_snapshot_ref": snapshot_ref,
        "source_snapshot_sha256": source_snapshot_sha256,
        "source_binding_schema_version": "prepared-skg-read.v1",
        "query_version": "skg-query.v1",
        "source_read_prepared_at_utc": source_read_prepared_at_utc,
        "authority_band": "candidate",
        "source_snapshot_authenticity": "not_established",
        "currentness_status": "not_established",
        "time_semantics": "read_transaction_opened_at",
    }
    return CredalReferenceSourceProfile.model_validate(
        {
            **body,
            "content_hash": _credal_reference_source_profile_content_hash(body),
        }
    )


def _profiled_l2_reference(
    profile: CredalReferenceSourceProfile,
) -> CredalReference:
    edges = {}
    for edge_id in ("edge-a", "edge-b"):
        edge = CredalReferenceEdge(
            modality="L2_CAUSAL_EDGE",
            edge_id=edge_id,
            status="contested",
            admissible_completions=(AdmissibleCompletion("may_exist"),),
            provenance={
                "owner": "L2",
                "source": "ac_skg_edges",
                "selected_source_profile": profile.model_dump(mode="json"),
            },
        ).with_content_hash()
        edges[edge.key] = edge
    component_versions = _component_versions(
        edges,
        l2_source_profile_hash=profile.content_hash,
    )
    reference_hash = _reference_hash(
        component_versions=component_versions,
        edge_index=edges,
        as_of="2026-10-11",
    )
    return CredalReference(
        schema_version="policyos.runtime.grounding_credal_reference.v2",
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-10-11",
        component_versions=component_versions,
        essential_edges=edges,
    )


def test_selected_l2_profile_requires_every_l2_edge_and_rejects_removal() -> None:
    from dataclasses import replace

    profile = _selected_l2_profile_fixture()
    assert profile.source_read_prepared_at_utc.endswith("Z")
    complete = _profiled_l2_reference(profile)
    assert credal_reference_l2_source_profile(complete) == profile

    first_edge = next(iter(complete.essential_edges.values()))
    missing_profile = replace(
        first_edge,
        provenance={
            key: value
            for key, value in first_edge.provenance.items()
            if key != "selected_source_profile"
        },
        content_hash="",
    ).with_content_hash()
    damaged = replace(
        complete,
        essential_edges={**complete.essential_edges, missing_profile.key: missing_profile},
    )
    with pytest.raises(
        ValueError,
        match="credal_reference_skg_source_profile_denominator_mismatch",
    ):
        credal_reference_l2_source_profile(damaged)


def test_selected_skg_profile_does_not_claim_independent_data_forge_edges() -> None:
    from dataclasses import replace

    profile = _selected_l2_profile_fixture()
    selected_skg = _profiled_l2_reference(profile)
    data_forge_edge = CredalReferenceEdge(
        modality="L2_DATA_FORGE_VARIABLE_ALIGNMENT",
        edge_id="controlled-dataset:raw->canonical",
        status="contested",
        admissible_completions=(AdmissibleCompletion("may_exist"),),
        provenance={
            "owner": "L2/DataForge",
            "source": "ds_variable_alignments",
            "version": "controlled-catalog",
        },
    ).with_content_hash()
    with_independent_source = replace(
        selected_skg,
        essential_edges={
            **selected_skg.essential_edges,
            data_forge_edge.key: data_forge_edge,
        },
    )
    assert credal_reference_l2_source_profile(with_independent_source) == profile

    falsely_profiled_data_forge_edge = replace(
        data_forge_edge,
        provenance={
            **data_forge_edge.provenance,
            "selected_source_profile": profile.model_dump(mode="json"),
        },
        content_hash="",
    ).with_content_hash()
    falsely_profiled = replace(
        with_independent_source,
        essential_edges={
            **selected_skg.essential_edges,
            falsely_profiled_data_forge_edge.key: falsely_profiled_data_forge_edge,
        },
    )
    with pytest.raises(
        ValueError,
        match="credal_reference_skg_source_profile_denominator_mismatch",
    ):
        credal_reference_l2_source_profile(falsely_profiled)


def test_read_transaction_time_is_provenance_not_semantic_kref_identity() -> None:
    first_profile = _selected_l2_profile_fixture(source_read_prepared_at_utc="2026-10-11T19:00:00Z")
    second_profile = _selected_l2_profile_fixture(
        source_read_prepared_at_utc="2026-10-11T19:01:00Z"
    )
    first_reference = _profiled_l2_reference(first_profile)
    second_reference = _profiled_l2_reference(second_profile)

    assert first_profile.source_read_prepared_at_utc != second_profile.source_read_prepared_at_utc
    assert first_profile.content_hash == second_profile.content_hash
    assert first_reference.component_versions == second_reference.component_versions
    assert first_reference.reference_hash == second_reference.reference_hash
    assert first_reference.reference_epoch == second_reference.reference_epoch
    assert credal_reference_l2_source_profile(first_reference) == first_profile
    assert credal_reference_l2_source_profile(second_reference) == second_profile
    for edge_key in first_reference.essential_edges:
        first_edge = first_reference.essential_edges[edge_key]
        second_edge = second_reference.essential_edges[edge_key]
        assert first_edge.content_hash == second_edge.content_hash
        first_time = first_edge.to_payload()["provenance"]["selected_source_profile"][
            "source_read_prepared_at_utc"
        ]
        second_time = second_edge.to_payload()["provenance"]["selected_source_profile"][
            "source_read_prepared_at_utc"
        ]
        assert first_time != second_time


def test_skg_byte_or_selected_version_change_changes_semantic_kref_identity() -> None:
    baseline = _profiled_l2_reference(_selected_l2_profile_fixture())
    changed_bytes = _profiled_l2_reference(
        _selected_l2_profile_fixture(source_snapshot_sha256="3" * 64)
    )
    changed_version = _profiled_l2_reference(
        _selected_l2_profile_fixture(
            source_version_id=8,
            world_model_record_content_hash="sha256:" + "4" * 64,
        )
    )

    assert baseline.reference_hash != changed_bytes.reference_hash
    assert baseline.component_versions != changed_bytes.component_versions
    assert baseline.reference_hash != changed_version.reference_hash
    assert baseline.component_versions != changed_version.component_versions


def test_profileless_historical_l2_reference_stays_readable() -> None:
    historical = CredalReference(
        schema_version="policyos.runtime.grounding_credal_reference.v1",
        reference_epoch="kref:historical-profileless",
        reference_hash="sha256:" + "4" * 64,
        as_of="2026-10-11",
        component_versions={},
        essential_edges={},
    )
    assert credal_reference_l2_source_profile(historical) is None


def test_selected_l2_profile_rejects_unqualified_read_time() -> None:
    from polisyos.pdc import gy_content_hash

    profile = _selected_l2_profile_fixture()
    body = profile.model_dump(mode="json", exclude={"content_hash"})
    body["source_read_prepared_at_utc"] = "2026-10-11T21:00:00+02:00"
    with pytest.raises(
        ValueError,
        match="credal_reference_skg_source_read_time_unqualified",
    ):
        CredalReferenceSourceProfile.model_validate({**body, "content_hash": gy_content_hash(body)})


def test_prepared_skg_rows_drive_kref_without_claiming_data_forge_source(
    tmp_path: Path,
) -> None:
    from polisyos.data_forge.domains.academic.knowledge.skg_store import ensure_skg_schema
    from polisyos.runtime.quality import credal_reference as owner

    skg_path = tmp_path / DEFAULT_L2_SCHOLAR_KG_PATH
    skg_path.parent.mkdir(parents=True)
    with duckdb.connect(str(skg_path)) as con:
        ensure_skg_schema(con)
        con.execute("INSERT INTO ac_skg_versions(version_id) VALUES (7)")
        con.execute(
            "INSERT INTO ac_skg_variables "
            "(canonical_name, normalized_name, display_name, approved_canonical_name, "
            "is_approved_canonical, resolution_method, resolution_confidence, mention_count) "
            "VALUES ('policy.tax_rate','policy.tax_rate','Tax rate','policy.tax_rate',"
            "TRUE,'controlled',0.95,5)"
        )
        con.execute(
            "INSERT INTO ac_skg_variable_synonyms "
            "(synonym, canonical_name, method, confidence, approved) "
            "VALUES ('tax level','policy.tax_rate','controlled',0.95,TRUE)"
        )
        con.execute(
            "CREATE TABLE ac_causal_claims (id VARCHAR, work_id VARCHAR, cause VARCHAR, "
            "effect VARCHAR, direction VARCHAR, strength VARCHAR, mechanism VARCHAR, "
            "domain VARCHAR, trust_score FLOAT, strong_design_evidence BOOLEAN, "
            "design_quality_tier INTEGER, publish_blockers VARCHAR, candidate_layer VARCHAR)"
        )
        con.execute("CREATE TABLE ac_works (id VARCHAR, title VARCHAR, year INTEGER)")
        con.execute("CREATE TABLE ac_causal_claims_raw (synthetic BOOLEAN)")
        con.execute("INSERT INTO ac_causal_claims_raw VALUES (FALSE)")

    catalog_path = tmp_path / owner.DEFAULT_DATA_FORGE_CATALOG_PATH
    catalog_path.parent.mkdir(parents=True)
    with duckdb.connect(str(catalog_path)) as con:
        con.execute(
            "CREATE TABLE ds_variable_alignments (dataset_id VARCHAR, raw_variable VARCHAR, "
            "canonical_var VARCHAR, method VARCHAR, confidence FLOAT, evidence VARCHAR, "
            "is_proxy BOOLEAN, proxy_penalty FLOAT)"
        )
        con.execute(
            "INSERT INTO ds_variable_alignments VALUES "
            "('dataset-a','tax amount','policy.tax_rate','controlled',0.91,"
            "'dataset catalog alignment',FALSE,0.0)"
        )

    edges = tuple(_iter_l2_edges(tmp_path))
    skg_alignment = next(edge for edge in edges if edge.modality == "L2_VARIABLE_ALIGNMENT")
    data_forge_alignment = next(
        edge for edge in edges if edge.modality == "L2_DATA_FORGE_VARIABLE_ALIGNMENT"
    )
    assert skg_alignment.provenance["owner"] == "L2"
    assert skg_alignment.provenance["source"] == "ac_skg_variable_synonyms"
    assert skg_alignment.provenance["selected_source_profile"]["source_snapshot_ref"].endswith(
        "#v7"
    )
    assert skg_alignment.provenance["selected_source_profile"]["source_snapshot_sha256"]
    assert data_forge_alignment.provenance["owner"] == "L2/DataForge"
    assert data_forge_alignment.provenance["source"] == "ds_variable_alignments"
    assert "selected_source_profile" not in data_forge_alignment.provenance


def _phase5_l6_law_scope():
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality import grounding_relation as atoms
    from polisyos.runtime.quality import intervention_substrate as substrate

    world = substrate.production_composed_world_model_record(REPO_ROOT)
    bundle = substrate.load_l6_intervention_substrate(REPO_ROOT)
    edges = [
        *owner._iter_l6_edges(REPO_ROOT, world_model_record=world),
        *owner._iter_wmr_edges(world),
    ]
    index = {edge.key: edge for edge in edges}
    versions = owner._component_versions(index, world_model_record=world)
    digest = owner._reference_hash(
        component_versions=versions, edge_index=index, as_of=owner.DEFAULT_REFERENCE_AS_OF
    )
    scoped = CredalReference(
        owner.CREDAL_REFERENCE_SCHEMA_VERSION,
        "kref:" + digest.removeprefix("sha256:")[:16],
        digest,
        owner.DEFAULT_REFERENCE_AS_OF,
        versions,
        index,
    )
    return bundle, scoped, atoms._reference_atoms_from_cg0(scoped)


def _assert_phase5_law_scope_preserved_and_nonconfirmed(bundle, scoped, atoms):
    laws = {
        edge.edge_id: edge
        for edge in scoped.essential_edges.values()
        if edge.modality == "L6_LEX_INTERVENTION_MAP"
    }
    raw = json.loads(
        (
            REPO_ROOT / "production_data/ukraine_agent_simulation_baseline_20260410/"
            "production_bundle/bundles/intervention_bundle_v1/lex_intervention_map.json"
        ).read_text()
    )
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
                completions = owner._incomplete_completions(
                    "law_mapping_correspondence_not_established"
                )
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
    old_hash = owner._reference_hash(
        component_versions=current.component_versions,
        edge_index=current.essential_edges,
        as_of=current.as_of,
        schema_version=historical_schema,
    )
    historical = replace(
        current,
        schema_version=historical_schema,
        reference_hash=old_hash,
        reference_epoch="kref:" + old_hash.removeprefix("sha256:")[:16],
    )
    assert _CredalReferenceReplayRecord.from_reference(historical).to_reference() == historical
    edge = next(iter(historical.essential_edges.values()))
    assert owner.replace_reference_edge(historical, edge) == historical
    assert current.schema_version == "policyos.runtime.grounding_credal_reference.v2"
    certificate = owner.bind_grounding_certificate_reference(
        historical,
        certificate_id="historical_epoch_replay_control",
        edge_scope=(edge.key,),
    )
    assert owner.reference_certificate_staleness(certificate, current).status != "current"


@pytest.mark.parametrize(
    "synthetic_marker",
    [
        pytest.param(True, id="true"),
        pytest.param(False, id="false"),
        pytest.param(None, id="null"),
        pytest.param("true", id="string"),
        pytest.param(1, id="integer"),
        pytest.param("", id="empty-string"),
        pytest.param(_MISSING_FIXTURE_MARKER, id="missing"),
    ],
)
@pytest.mark.parametrize(
    "fixture_scope",
    [
        pytest.param("candidate_only", id="nonempty"),
        pytest.param(_MISSING_FIXTURE_MARKER, id="missing"),
        pytest.param("", id="empty"),
        pytest.param(" \t\n", id="whitespace"),
        pytest.param(7, id="integer"),
        pytest.param(["candidate_only"], id="list"),
    ],
)
def test_synthetic_academic_skg_fixture_requires_exact_nonempty_scope_before_producer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    synthetic_marker: object,
    fixture_scope: object,
) -> None:
    from polisyos.data_forge.domains.academic.batch import graph_builder
    from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord
    from tests._helpers.academic_skg import build_synthetic_academic_skg_source

    metadata = {}
    if synthetic_marker is not _MISSING_FIXTURE_MARKER:
        metadata["synthetic"] = synthetic_marker
    if fixture_scope is not _MISSING_FIXTURE_MARKER:
        metadata["fixture_scope"] = fixture_scope
    record = WorkRecord(
        id="synthetic-skg-scope-boundary",
        title="Synthetic scope boundary",
        metadata=metadata,
    )
    db_path = tmp_path / "scope-boundary" / "academic-skg.duckdb"
    db_path.parent.mkdir()
    producer_calls = []
    producer_result = object()

    def producer_spy(**kwargs):
        producer_calls.append(kwargs)
        return producer_result

    monkeypatch.setattr(graph_builder, "build_graph", producer_spy)
    admitted_markers = synthetic_marker is True and fixture_scope == "candidate_only"
    if admitted_markers:
        assert build_synthetic_academic_skg_source(records=(record,), db_path=db_path) is (
            producer_result
        )
        assert len(producer_calls) == 1
        assert producer_calls[0]["records"] == (record,)
        assert producer_calls[0]["db_path"] == db_path
        return

    wal_path = db_path.with_suffix(db_path.suffix + ".wal")
    staging_path = db_path.with_suffix(db_path.suffix + ".staging")
    staging_artifact_path = staging_path / "graph-load.sqlite"
    db_path.write_bytes(b"preserved database bytes")
    wal_path.write_bytes(b"preserved wal bytes")
    staging_path.mkdir()
    staging_artifact_path.write_bytes(b"preserved staging bytes")
    before = {path: path.read_bytes() for path in (db_path, wal_path, staging_artifact_path)}
    with pytest.raises(
        ValueError,
        match="synthetic_academic_skg_requires_explicit_synthetic_records",
    ):
        build_synthetic_academic_skg_source(records=(record,), db_path=db_path)
    assert producer_calls == []
    assert {path: path.read_bytes() for path in before} == before


@pytest.mark.parametrize("artifact", ["database", "wal", "staging"])
def test_synthetic_academic_skg_fixture_preserves_existing_writer_artifacts(
    tmp_path: Path,
    artifact: str,
) -> None:
    from polisyos.data_forge.domains.academic.knowledge.types import WorkRecord
    from tests._helpers.academic_skg import build_synthetic_academic_skg_source

    db_path = tmp_path / "existing-academic-skg.duckdb"
    if artifact == "database":
        preserved_path = db_path
    elif artifact == "wal":
        preserved_path = db_path.with_suffix(db_path.suffix + ".wal")
    else:
        preserved_path = db_path.with_suffix(db_path.suffix + ".staging") / "graph-load.sqlite"
    preserved_path.parent.mkdir(parents=True, exist_ok=True)
    preserved_bytes = b"preserve-existing-writer-artifact"
    preserved_path.write_bytes(preserved_bytes)
    record = WorkRecord(
        id="existing-target-control",
        title="Explicit synthetic candidate",
        metadata={"synthetic": True, "fixture_scope": "negative_test_only"},
    )

    with pytest.raises(ValueError, match="synthetic_academic_skg_seed_target_exists"):
        build_synthetic_academic_skg_source(records=(record,), db_path=db_path)
    assert preserved_path.read_bytes() == preserved_bytes


def test_credal_reference_consumes_bound_layer_vintage_before_first_yield(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.data_forge.domains.academic.knowledge.types import (
        EstimateCandidate,
        WorkRecord,
    )
    from tests._helpers.academic_skg import build_synthetic_academic_skg_source

    db_path = tmp_path / DEFAULT_L2_SCHOLAR_KG_PATH
    db_path.parent.mkdir(parents=True)
    record = WorkRecord(
        id="controlled-vintage-source",
        title="Synthetic vintage-control source",
        abstract="Synthetic fixture data; no causal or production claim.",
        year=2026,
        estimates=[
            EstimateCandidate(
                value=0.0,
                pattern_name="controlled_candidate_fixture",
                variable_hint="cause",
            )
        ],
        metadata={"synthetic": True, "fixture_scope": "credal_vintage_test_only"},
    )
    build_synthetic_academic_skg_source(records=(record,), db_path=db_path)
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
    modalities = {edge_class["modality"] for edge_class in scope["included_edge_classes"]}

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


def test_credal_json_ready_exact_builtin_fastpaths_match_json_roundtrip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import math
    import sys

    from polisyos.runtime.quality import credal_reference as owner

    class IntSubclass(int):
        pass

    class FloatSubclass(float):
        pass

    fastpath_values: tuple[object, ...] = (
        None,
        True,
        False,
        "",
        "unicode — preserved",
        0,
        -17,
        1.25,
        -0.0,
        math.ulp(0.0),
        {},
        [],
        (),
    )
    expected = [
        json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
        for value in fastpath_values
    ]

    def reject_json_roundtrip(*args: object, **kwargs: object) -> object:
        raise AssertionError("exact built-in fastpath must not call the JSON roundtrip")

    with monkeypatch.context() as guarded:
        guarded.setattr(owner.json, "dumps", reject_json_roundtrip)
        actual = [owner._json_ready(value) for value in fastpath_values]

    assert [type(value) for value in actual] == [type(value) for value in expected]
    assert actual == expected
    assert math.copysign(1.0, float(actual[8])) == -1.0
    for original, normalized in zip(fastpath_values[-3:], actual[-3:], strict=True):
        assert normalized is not original
        assert normalized is not owner._json_ready(original)

    fallback_values: tuple[object, ...] = (
        float("inf"),
        float("nan"),
        {"nested": [1, "value", None]},
        IntSubclass(7),
        FloatSubclass(1.5),
    )
    for value in fallback_values:
        actual_value = owner._json_ready(value)
        expected_value = json.loads(
            json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        )
        assert type(actual_value) is type(expected_value)
        assert json.dumps(
            actual_value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ) == json.dumps(
            expected_value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    max_digits = sys.get_int_max_str_digits()
    if max_digits:
        with pytest.raises(ValueError):
            owner._json_ready(10**max_digits)


def test_credal_json_ready_fallback_preserves_sorted_stateful_default_order() -> None:
    from polisyos.runtime.quality import credal_reference as owner

    def run_ready(*, use_owner: bool) -> tuple[object, list[str]]:
        calls: list[str] = []

        class StatefulDefault:
            def __init__(self, label: str) -> None:
                self.label = label

            def __str__(self) -> str:
                calls.append(self.label)
                return f"{self.label}-{len(calls)}"

        value = {"z": StatefulDefault("z"), "a": StatefulDefault("a")}
        if use_owner:
            result = owner._json_ready(value)
        else:
            result = json.loads(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str))
        return result, calls

    actual, actual_calls = run_ready(use_owner=True)
    expected, expected_calls = run_ready(use_owner=False)
    assert actual == expected == {"a": "a-1", "z": "z-2"}
    assert actual_calls == expected_calls == ["a", "z"]


def test_l6_observation_route_edges_use_one_validated_manifest_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from collections.abc import Iterator
    from contextlib import contextmanager

    from polisyos.foundry.extensions import registry as foundry_registry
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.intervention_substrate import (
        INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        InterventionSubstrateBundle,
        intervention_substrate_bundle_content_hash,
    )

    raw_routes = [
        {
            "family": "family-b",
            "target_contract": {"contract_id": "contract-b"},
        },
        {
            "family": "family-a",
            "target_contract": {"contract_id": "contract-a"},
        },
    ]
    raw_artifacts = [
        {"target_contract": {"contract_id": "contract-a"}, "status": "compiled"},
        {"target_contract": {"contract_id": "contract-b"}, "status": "compiled"},
    ]
    bundle_fields: dict[str, object] = {
        "schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "knob_dictionary": {},
        "lex_intervention_map": {},
        "observation_manifest": {"routes": raw_routes, "artifacts": raw_artifacts},
        "policy_scenario_templates": {},
        "slot_family_manifest": {},
        "world_mechanism_manifest": {},
        "lex_authority_manifest": {},
        "owner_authority_manifest": {},
        "source_refs": {},
        "source_content_hashes": {},
    }
    bundle_fields["content_hash"] = intervention_substrate_bundle_content_hash(bundle_fields)
    bundle = InterventionSubstrateBundle.model_validate(bundle_fields)
    registry = foundry_registry.MethodRegistry()
    registry_scopes: list[None] = []

    @contextmanager
    def one_controlled_registry_scope() -> Iterator[
        tuple[
            foundry_registry.MethodRegistry,
            foundry_registry.FoundryExtensionRegistryReport,
        ]
    ]:
        registry_scopes.append(None)
        yield registry, foundry_registry.FoundryExtensionRegistryReport()

    monkeypatch.setattr(
        foundry_registry,
        "controlled_builtin_foundry_method_registry_scope",
        one_controlled_registry_scope,
    )

    edges = list(owner._iter_l6_observation_route_edges(bundle, version="fixture-v1"))

    assert len(registry_scopes) == 1
    assert [edge.edge_id for edge in edges] == ["family-b", "family-a"]
    assert [edge.status for edge in edges] == ["incomplete", "incomplete"]
    assert [edge.admissible_completions[0].reason for edge in edges] == [
        "method_route_unresolved",
        "method_route_unresolved",
    ]
    assert [edge.provenance["signals"]["route"] for edge in edges] == raw_routes


def test_l6_observation_route_edges_keep_per_row_refusals_for_invalid_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.intervention_substrate import (
        INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        InterventionSubstrateBundle,
        ObservationMethodRoute,
        intervention_substrate_bundle_content_hash,
    )

    raw_routes = [
        {"family": " duplicate "},
        {"family": "duplicate"},
        {"target_contract": "missing-family"},
    ]
    bundle_fields: dict[str, object] = {
        "schema_version": INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "knob_dictionary": {},
        "lex_intervention_map": {},
        "observation_manifest": {"routes": raw_routes},
        "policy_scenario_templates": {},
        "slot_family_manifest": {},
        "world_mechanism_manifest": {},
        "lex_authority_manifest": {},
        "owner_authority_manifest": {},
        "source_refs": {},
        "source_content_hashes": {},
    }
    bundle_fields["content_hash"] = intervention_substrate_bundle_content_hash(bundle_fields)
    bundle = InterventionSubstrateBundle.model_validate(bundle_fields)
    per_family_calls: list[str] = []

    actual_route_resolution = owner.route_observation_family_method

    def reject_family(
        actual_bundle: InterventionSubstrateBundle,
        *,
        family: str,
    ) -> ObservationMethodRoute:
        assert actual_bundle is bundle
        per_family_calls.append(family)
        return actual_route_resolution(actual_bundle, family=family)

    monkeypatch.setattr(owner, "route_observation_family_method", reject_family)

    edges = list(owner._iter_l6_observation_route_edges(bundle, version="fixture-v1"))

    assert per_family_calls == ["duplicate", "duplicate"]
    assert [edge.edge_id for edge in edges] == [
        "duplicate",
        "duplicate",
        "missing_family",
    ]
    assert [edge.status for edge in edges] == ["incomplete", "incomplete", "incomplete"]
    assert [edge.admissible_completions[0].reason for edge in edges] == [
        "family_route_ambiguous",
        "family_route_ambiguous",
        "observation_family_missing",
    ]
    assert [edge.provenance["signals"]["route"] for edge in edges] == raw_routes


def test_credal_reference_captures_deep_immutable_source_content() -> None:
    """Caller aliases cannot revise a selected reference after construction."""

    completion_value = {"nested": {"items": ["captured-completion"]}}
    provenance = {"nested": {"items": ["captured-provenance"]}}
    completion = AdmissibleCompletion("fixed", completion_value)
    edge = CredalReferenceEdge(
        modality="L2_CAUSAL_EDGE",
        edge_id="captured-edge",
        status="confirmed",
        admissible_completions=(completion,),
        provenance=provenance,
    ).with_content_hash()
    source_edges = {edge.key: edge}
    source_versions = {"WMR": "selected-world-model"}
    reference_hash = _reference_hash(
        component_versions=source_versions,
        edge_index=source_edges,
        as_of="2026-10-13",
    )
    reference = CredalReference(
        schema_version="policyos.runtime.grounding_credal_reference.v2",
        reference_epoch="kref:selected-epoch",
        reference_hash=reference_hash,
        as_of="2026-10-13",
        component_versions=source_versions,
        essential_edges=source_edges,
    )

    completion_value["nested"]["items"].append("caller-change")
    provenance["nested"]["items"].append("caller-change")
    source_versions["WMR"] = "caller-change"
    replacement = CredalReferenceEdge(
        modality="L2_CAUSAL_EDGE",
        edge_id="replacement-edge",
        status="contested",
        admissible_completions=(AdmissibleCompletion("may_exist"),),
        provenance={"owner": "caller-replacement"},
    ).with_content_hash()
    source_edges[edge.key] = replacement

    assert len(source_edges) == len(reference.essential_edges) == 1
    assert reference.schema_version == "policyos.runtime.grounding_credal_reference.v2"
    assert reference.reference_epoch == "kref:selected-epoch"
    assert reference.reference_hash == reference_hash
    assert reference.as_of == "2026-10-13"
    assert reference.component_versions["WMR"] == "selected-world-model"
    captured = reference.essential_edges[edge.key]
    assert captured.admissible_completions[0].value["nested"]["items"] == ("captured-completion",)
    assert captured.provenance["nested"]["items"] == ("captured-provenance",)
    assert captured.to_payload()["admissible_completions"][0]["value"]["nested"]["items"] == [
        "captured-completion"
    ]
    assert captured.to_payload()["provenance"]["nested"]["items"] == ["captured-provenance"]

    with pytest.raises(TypeError):
        reference.component_versions["WMR"] = "mutated"  # type: ignore[index]
    with pytest.raises(TypeError):
        reference.essential_edges[edge.key] = replacement  # type: ignore[index]
    captured_provenance_items = captured.provenance["nested"]["items"]
    captured_completion_items = captured.admissible_completions[0].value["nested"]["items"]
    captured_hash = captured.content_hash
    assert isinstance(captured_provenance_items, tuple)
    assert isinstance(captured_completion_items, tuple)
    assert captured_provenance_items == ["captured-provenance"]
    assert captured_completion_items == ["captured-completion"]
    with pytest.raises(AttributeError):
        captured_provenance_items.append("mutated")
    with pytest.raises(TypeError):
        list.append(captured_provenance_items, "base-append-mutation")
    with pytest.raises(TypeError):
        list.__setitem__(captured_completion_items, 0, "base-setitem-mutation")
    assert captured.content_hash == captured_hash
    assert captured.to_payload()["admissible_completions"][0]["value"]["nested"]["items"] == [
        "captured-completion"
    ]
    assert captured.to_payload()["provenance"]["nested"]["items"] == ["captured-provenance"]


def test_credal_reference_snapshots_mutable_legacy_json_fallback_values() -> None:
    """Mutable values accepted through ``default=str`` stay fixed after capture."""

    class MutableTextFallback:
        def __init__(self, value: str) -> None:
            self.value = value

        def __str__(self) -> str:
            return self.value

    class MutableBytesFallback(bytes):
        display: str

        def __new__(cls, value: bytes, display: str) -> MutableBytesFallback:
            instance = super().__new__(cls, value)
            instance.display = display
            return instance

        def __str__(self) -> str:
            return self.display

    completion_bytes = bytearray(b"completion-before")
    completion_text = MutableTextFallback("completion-text-before")
    completion_bytes_subclass = MutableBytesFallback(
        b"completion-subclass", "completion-subclass-before"
    )
    provenance_bytes = bytearray(b"provenance-before")
    provenance_text = MutableTextFallback("provenance-text-before")
    provenance_bytes_subclass = MutableBytesFallback(
        b"provenance-subclass", "provenance-subclass-before"
    )
    completion_value = {
        "bytes": completion_bytes,
        "custom": completion_text,
        "subclass_bytes": completion_bytes_subclass,
    }
    provenance = {
        "bytes": provenance_bytes,
        "custom": provenance_text,
        "subclass_bytes": provenance_bytes_subclass,
    }
    expected_completion = json.loads(
        json.dumps(completion_value, ensure_ascii=False, sort_keys=True, default=str)
    )
    expected_provenance = json.loads(
        json.dumps(provenance, ensure_ascii=False, sort_keys=True, default=str)
    )
    assert expected_completion == {
        "bytes": "bytearray(b'completion-before')",
        "custom": "completion-text-before",
        "subclass_bytes": "completion-subclass-before",
    }
    assert expected_provenance == {
        "bytes": "bytearray(b'provenance-before')",
        "custom": "provenance-text-before",
        "subclass_bytes": "provenance-subclass-before",
    }

    edge = CredalReferenceEdge(
        modality="L2_CAUSAL_EDGE",
        edge_id="mutable-fallback-edge",
        status="confirmed",
        admissible_completions=(AdmissibleCompletion("fixed", completion_value),),
        provenance=provenance,
    ).with_content_hash()
    captured_hash = edge.content_hash

    completion_bytes.extend(b"-caller-change")
    completion_text.value = "completion-text-after"
    completion_bytes_subclass.display = "completion-subclass-after"
    provenance_bytes.extend(b"-caller-change")
    provenance_text.value = "provenance-text-after"
    provenance_bytes_subclass.display = "provenance-subclass-after"

    payload = edge.to_payload()
    assert payload["admissible_completions"][0]["value"] == expected_completion
    assert payload["provenance"] == expected_provenance
    assert edge.content_hash == captured_hash


def test_credal_mapping_snapshot_preserves_legacy_json_fallback_wire() -> None:
    """Generic mappings keep default=str wire output while their lookup view is frozen."""

    nested_user_mapping_data = {"owner": "nested-before", "status": True}
    nested_user_mapping = UserDict(nested_user_mapping_data)
    completion_data = {"owner": "completion-before", "nested": nested_user_mapping}
    completion_mapping = UserDict(completion_data)
    provenance_data = {"owner": "provenance-before", "status": True}
    provenance_mapping = MappingProxyType(provenance_data)
    exact_dict_data = {"nested": UserDict({"owner": "dict-nested-before"})}

    expected_completion = json.loads(
        json.dumps(completion_mapping, ensure_ascii=False, sort_keys=True, default=str)
    )
    expected_exact_dict = json.loads(
        json.dumps(exact_dict_data, ensure_ascii=False, sort_keys=True, default=str)
    )
    expected_provenance = json.loads(
        json.dumps(provenance_mapping, ensure_ascii=False, sort_keys=True, default=str)
    )
    edge = CredalReferenceEdge(
        modality="L2_CAUSAL_EDGE",
        edge_id="generic-mapping-wire-edge",
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion("fixed", completion_mapping),
            AdmissibleCompletion("fixed", exact_dict_data),
        ),
        provenance=provenance_mapping,
    ).with_content_hash()
    captured_hash = edge.content_hash

    payload = edge.to_payload()
    assert payload["admissible_completions"][0]["value"] == expected_completion
    assert payload["admissible_completions"][1]["value"] == expected_exact_dict
    assert payload["provenance"] == expected_provenance
    assert edge.admissible_completions[0].value["owner"] == "completion-before"
    assert edge.admissible_completions[0].value["nested"]["owner"] == "nested-before"
    assert edge.provenance["owner"] == "provenance-before"

    completion_data["owner"] = "completion-after"
    nested_user_mapping_data["owner"] = "nested-after"
    provenance_data["owner"] = "provenance-after"
    exact_dict_data["nested"]["owner"] = "dict-nested-after"

    assert edge.content_hash == captured_hash
    assert edge.to_payload()["admissible_completions"][0]["value"] == expected_completion
    assert edge.to_payload()["admissible_completions"][1]["value"] == expected_exact_dict
    assert edge.to_payload()["provenance"] == expected_provenance
    assert edge.admissible_completions[0].value["owner"] == "completion-before"
    assert edge.admissible_completions[0].value["nested"]["owner"] == "nested-before"
    assert edge.provenance["owner"] == "provenance-before"


def test_credal_reference_captures_json_scalar_subclasses_as_builtin_wire_values() -> None:
    """The selected snapshot preserves old JSON values without retaining subclasses."""

    class MutableWireText(str):
        display: str

        def __new__(cls, value: str, display: str) -> MutableWireText:
            instance = super().__new__(cls, value)
            instance.display = display
            return instance

        def __str__(self) -> str:
            return self.display

    class MutableWireInteger(int):
        display: str

        def __new__(cls, value: int, display: str) -> MutableWireInteger:
            instance = super().__new__(cls, value)
            instance.display = display
            return instance

        def __str__(self) -> str:
            return self.display

    class MutableWireFloat(float):
        display: str

        def __new__(cls, value: float, display: str) -> MutableWireFloat:
            instance = super().__new__(cls, value)
            instance.display = display
            return instance

        def __str__(self) -> str:
            return self.display

    modality = MutableWireText("L2_CAUSAL_EDGE", "mutable-modality")
    edge_id = MutableWireText("scalar-wire-edge", "mutable-edge-id")
    status_value = MutableWireText("confirmed", "mutable-status")
    status = cast("CredalReferenceStatus", status_value)
    completion_kind_value = MutableWireText("fixed", "mutable-kind")
    completion_kind = cast("CompletionKind", completion_kind_value)
    reason = MutableWireText("wire-reason", "mutable-reason")
    unit = MutableWireText("wire-unit", "mutable-unit")
    scale = MutableWireText("wire-scale", "mutable-scale")
    supplied_hash = MutableWireText("sha256:wire-value", "mutable-hash")
    text_value = MutableWireText("wire-text", "mutable-text")
    integer_value = MutableWireInteger(17, "mutable-integer")
    float_value = MutableWireFloat(0.25, "mutable-float")
    text_key = MutableWireText("text-key", "mutable-text-key")
    integer_key = MutableWireInteger(2, "mutable-integer-key")
    float_key = MutableWireFloat(3.5, "mutable-float-key")
    raw_value = {
        "text": text_value,
        "integer": integer_value,
        "float": float_value,
        "text-key": {text_key: "text-key-value"},
        "integer-key": {integer_key: "integer-key-value"},
        "float-key": {float_key: "float-key-value"},
    }
    provenance_key = MutableWireText("source-key", "mutable-source-key")
    raw_provenance = {provenance_key: text_value}
    legacy_completion = {
        "completion_kind": completion_kind,
        "reason": reason,
        "value": raw_value,
    }
    legacy_edge_payload = {
        "admissible_completions": [legacy_completion],
        "edge_id": edge_id,
        "modality": modality,
        "provenance": raw_provenance,
        "scale": scale,
        "status": status,
        "unit": unit,
        "content_hash": supplied_hash,
    }
    expected_edge_payload = json.loads(
        json.dumps(legacy_edge_payload, ensure_ascii=False, sort_keys=True, default=str)
    )

    schema_version = MutableWireText("schema-wire", "mutable-schema")
    reference_epoch = MutableWireText("epoch-wire", "mutable-epoch")
    reference_hash = MutableWireText("hash-wire", "mutable-reference-hash")
    as_of = MutableWireText("2026-10-13", "mutable-as-of")
    component_key = MutableWireText("L2", "mutable-component-key")
    component_value = MutableWireText("source-version", "mutable-component-value")
    raw_component_versions = {component_key: component_value}
    expected_reference_fields = json.loads(
        json.dumps(
            {
                "schema_version": schema_version,
                "reference_epoch": reference_epoch,
                "reference_hash": reference_hash,
                "as_of": as_of,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )
    expected_component_versions = json.loads(
        json.dumps(raw_component_versions, ensure_ascii=False, sort_keys=True, default=str)
    )

    edge = CredalReferenceEdge(
        modality=modality,
        edge_id=edge_id,
        status=status,
        admissible_completions=(AdmissibleCompletion(completion_kind, raw_value, reason),),
        provenance=raw_provenance,
        unit=unit,
        scale=scale,
        content_hash=supplied_hash,
    )
    selected_key = (modality, edge_id)
    reference = CredalReference(
        schema_version=schema_version,
        reference_epoch=reference_epoch,
        reference_hash=reference_hash,
        as_of=as_of,
        component_versions=raw_component_versions,
        essential_edges={selected_key: edge},
    )
    frozen_hash = edge.with_content_hash().content_hash

    for value in (
        modality,
        edge_id,
        status_value,
        completion_kind_value,
        reason,
        unit,
        scale,
        supplied_hash,
        text_value,
        integer_value,
        float_value,
        text_key,
        integer_key,
        float_key,
        schema_version,
        reference_epoch,
        reference_hash,
        as_of,
        component_key,
        component_value,
        provenance_key,
    ):
        value.display = "mutated-after-selection"

    assert edge.to_payload() == expected_edge_payload
    assert edge.with_content_hash().content_hash == frozen_hash
    assert type(edge.modality) is str
    assert type(edge.edge_id) is str
    assert type(edge.status) is str
    assert type(edge.unit) is str
    assert type(edge.scale) is str
    assert type(edge.content_hash) is str
    completion = edge.admissible_completions[0]
    assert type(completion.completion_kind) is str
    assert type(completion.reason) is str
    value = completion.value
    assert type(value["text"]) is str
    assert type(value["integer"]) is int
    assert type(value["float"]) is float
    assert type(next(iter(value["text-key"]))) is str
    assert type(next(iter(value["integer-key"]))) is int
    assert type(next(iter(value["float-key"]))) is float
    assert type(next(iter(edge.provenance))) is str
    assert reference.schema_version == expected_reference_fields["schema_version"]
    assert reference.reference_epoch == expected_reference_fields["reference_epoch"]
    assert reference.reference_hash == expected_reference_fields["reference_hash"]
    assert reference.as_of == expected_reference_fields["as_of"]
    assert type(reference.schema_version) is str
    assert type(reference.reference_epoch) is str
    assert type(reference.reference_hash) is str
    assert type(reference.as_of) is str
    assert reference.component_versions == expected_component_versions
    assert type(next(iter(reference.component_versions))) is str
    assert type(next(iter(reference.component_versions.values()))) is str
    captured_key = next(iter(reference.essential_edges))
    assert captured_key == ("L2_CAUSAL_EDGE", "scalar-wire-edge")
    assert all(type(part) is str for part in captured_key)


@pytest.mark.parametrize("source_key", [("", "edge-a"), ("L2_CAUSAL_EDGE", " ")])
def test_credal_reference_rejects_unusable_edge_source_keys(
    source_key: tuple[str, str],
) -> None:
    reference = _profiled_l2_reference(_selected_l2_profile_fixture())
    edge = next(iter(reference.essential_edges.values()))

    with pytest.raises(ValueError, match="credal_reference_edge_source_key_invalid"):
        replace(reference, essential_edges={source_key: edge})


def test_credal_reference_rejects_edge_key_that_differs_from_source_key() -> None:
    reference = _profiled_l2_reference(_selected_l2_profile_fixture())
    edge = next(iter(reference.essential_edges.values()))

    with pytest.raises(ValueError, match="credal_reference_edge_source_key_mismatch"):
        replace(reference, essential_edges={(edge.modality, f"{edge.edge_id}-other"): edge})


def test_credal_snapshot_reuses_stateful_fallback_for_wire_and_lookup() -> None:
    """A fallback is captured once and shared with the immutable lookup view."""

    class StatefulFallback:
        def __init__(self, label: str, calls: list[str]) -> None:
            self.label = label
            self.calls = calls

        def __str__(self) -> str:
            self.calls.append(self.label)
            return f"{self.label}-{len(self.calls)}"

    expected_calls: list[str] = []
    expected_wire = json.loads(
        json.dumps(
            {
                "z": StatefulFallback("expected-z", expected_calls),
                "a": StatefulFallback("expected-a", expected_calls),
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    )
    assert expected_calls == ["expected-a", "expected-z"]

    actual_calls: list[str] = []
    completion = AdmissibleCompletion(
        "fixed",
        {
            "z": StatefulFallback("actual-z", actual_calls),
            "a": StatefulFallback("actual-a", actual_calls),
        },
        "stateful fallback probe",
    )

    assert actual_calls == ["actual-a", "actual-z"]
    assert completion.value["a"] == "actual-a-1"
    assert completion.value["z"] == "actual-z-2"
    assert completion.to_payload()["value"] == {
        "a": "actual-a-1",
        "z": "actual-z-2",
    }
    assert completion.to_payload()["value"] == {
        key: value.replace("expected", "actual") for key, value in expected_wire.items()
    }
    assert actual_calls == ["actual-a", "actual-z"]


def test_credal_snapshot_rejects_recursive_json_values() -> None:
    """Recursive JSON containers retain the standard encoder's bounded refusal."""

    recursive: dict[str, object] = {}
    recursive["self"] = recursive

    with pytest.raises(ValueError, match="Circular reference detected"):
        json.dumps(recursive, ensure_ascii=False, sort_keys=True, default=str)
    with pytest.raises(ValueError, match="Circular reference detected"):
        AdmissibleCompletion("fixed", recursive, "recursive fallback probe")


def _r1219_controlled_reference(
    edges: tuple[CredalReferenceEdge, ...],
    *,
    profile: CredalReferenceSourceProfile | None = None,
    as_of: str = "2026-10-13",
) -> CredalReference:
    """Build a test-only K_ref from explicitly supplied controlled edges."""
    edge_index = {edge.key: edge for edge in edges}
    assert len(edge_index) == len(edges)
    if profile is not None:
        expected_profile = profile.model_dump(mode="json")
        assert all(
            edge.to_payload()["provenance"].get("selected_source_profile") == expected_profile
            for edge in edges
            if edge.provenance.get("owner") == "L2"
        )
    component_versions = _component_versions(
        edge_index,
        l2_source_profile_hash=profile.content_hash if profile is not None else None,
    )
    reference_hash = _reference_hash(
        component_versions=component_versions,
        edge_index=edge_index,
        as_of=as_of,
    )
    return CredalReference(
        schema_version="policyos.runtime.grounding_credal_reference.v2",
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of=as_of,
        component_versions=component_versions,
        essential_edges=edge_index,
    )


def test_credal_controlled_contested_edge_lifts_set_valued_and_blocks_confirmation() -> None:
    profile = _selected_l2_profile_fixture()
    seed = _profiled_l2_reference(profile)
    template = seed.essential_edges[("L2_CAUSAL_EDGE", "edge-a")]
    value = {"direction": "positive", "dst": "controlled-outcome", "src": "controlled-policy"}
    contested = CredalReferenceEdge(
        modality=template.modality,
        edge_id=template.edge_id,
        status="contested",
        admissible_completions=(
            AdmissibleCompletion(
                "alternative",
                value,
                "controlled_direction_candidate",
            ),
            AdmissibleCompletion(
                "may_not_exist",
                value,
                "controlled_alternative_absence",
            ),
        ),
        provenance=template.provenance,
        unit=template.unit,
        scale=template.scale,
    ).with_content_hash()
    reference = _r1219_controlled_reference((contested,), profile=profile, as_of=seed.as_of)

    assert credal_reference_l2_source_profile(reference) == profile
    assert profile.authority_band == "candidate"
    assert profile.source_snapshot_authenticity == "not_established"
    assert profile.currentness_status == "not_established"
    lifted = reference_lift(reference, [contested.key])[
        f"{contested.modality}::{contested.edge_id}"
    ]
    assert lifted["status"] == "contested"
    assert lifted["is_set_valued"] is True
    assert len(lifted["admissible_completions"]) == 2
    assert all_essential_confirmed(reference, [contested.key]) is False


def test_credal_controlled_synthetic_source_fake_edge_and_removal_fail_closed(
    tmp_path: Path,
) -> None:
    from polisyos.data_forge.domains.academic.knowledge.types import (
        EstimateCandidate,
        WorkRecord,
    )
    from tests._helpers.academic_skg import build_synthetic_academic_skg_source

    db_path = tmp_path / DEFAULT_L2_SCHOLAR_KG_PATH
    db_path.parent.mkdir(parents=True)
    record = WorkRecord(
        id="r1219-controlled-source",
        title="Controlled synthetic source",
        abstract="Synthetic test input; no production or authority claim.",
        year=2026,
        estimates=[
            EstimateCandidate(
                value=0.0,
                pattern_name="r1219_controlled_candidate",
                variable_hint="cause",
            )
        ],
        metadata={"synthetic": True, "fixture_scope": "r1219_controlled_semantic_test"},
    )
    build_synthetic_academic_skg_source(records=(record,), db_path=db_path)
    assert db_path.is_file()
    source_edges = tuple(_iter_l2_edges(tmp_path))
    selected_source_edges = tuple(
        edge for edge in source_edges if edge.provenance.get("owner") == "L2"
    )
    assert selected_source_edges
    profile_payload = selected_source_edges[0].to_payload()["provenance"]["selected_source_profile"]
    profile = CredalReferenceSourceProfile.model_validate(profile_payload)
    reference = _r1219_controlled_reference(source_edges, profile=profile)

    assert profile.selection_owner == "legacy.default_l2_source"
    assert profile.source_snapshot_authenticity == "not_established"
    assert profile.currentness_status == "not_established"
    assert credal_reference_l2_source_profile(reference) == profile
    fake_key = ("L2_CAUSAL_EDGE", "r1219-controlled-fake-edge")
    fake_text = f"{fake_key[0]}::{fake_key[1]}"
    fake_lift = reference.reference_lift([fake_key])[fake_text]
    assert fake_lift["status"] == "out_of_scope"
    assert all_essential_confirmed(reference, [fake_key]) is False

    removal_reference = _profiled_l2_reference(profile)
    present_edge = removal_reference.essential_edges[("L2_CAUSAL_EDGE", "edge-a")]
    present_key = f"{present_edge.modality}::{present_edge.edge_id}"
    assert removal_reference.reference_lift([present_edge.key])[present_key]["status"] == (
        present_edge.status
    )
    reduced_edges = tuple(
        edge for edge in removal_reference.essential_edges.values() if edge.key != present_edge.key
    )
    reduced = _r1219_controlled_reference(
        reduced_edges,
        profile=profile,
        as_of=removal_reference.as_of,
    )
    removed_lift = reduced.reference_lift([present_edge.key])[present_key]
    assert credal_reference_l2_source_profile(reduced) == profile
    assert present_edge.key not in reduced.essential_edges
    assert removed_lift["status"] == "out_of_scope"
    assert all_essential_confirmed(reduced, [present_edge.key]) is False


def _r1219_controlled_status_edge(
    modality: str,
    edge_id: str,
    status: CredalReferenceStatus,
) -> CredalReferenceEdge:
    completion_kind = {
        "confirmed": "fixed",
        "contested": "alternative",
        "incomplete": "partial",
    }[status]
    return CredalReferenceEdge(
        modality=modality,
        edge_id=edge_id,
        status=status,
        admissible_completions=(
            AdmissibleCompletion(
                completion_kind,
                {"controlled_fixture": True},
                "explicit_controlled_denominator",
            ),
        ),
        provenance={"owner": "controlled_test_input", "synthetic": True},
    ).with_content_hash()


def test_credal_controlled_essential_scope_counts_use_exact_fixture_denominator() -> None:
    controlled_edges = (
        _r1219_controlled_status_edge("L2_FAMILY_EDGE", "family-contested", "contested"),
        _r1219_controlled_status_edge("L2_FAMILY_EDGE", "family-incomplete", "incomplete"),
        _r1219_controlled_status_edge("L2_MODERATION_EDGE", "moderation-contested", "contested"),
        _r1219_controlled_status_edge(
            "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
            "alignment-confirmed",
            "confirmed",
        ),
        _r1219_controlled_status_edge("L3_REFERENCE_EDGE", "reference-incomplete", "incomplete"),
    )
    reference = _r1219_controlled_reference(controlled_edges)
    counts = reference.denominator_counts()
    scope_modalities = {
        edge_class["modality"]
        for edge_class in essential_edge_scope_definition()["included_edge_classes"]
    }

    assert {
        "L2_FAMILY_EDGE",
        "L2_MODERATION_EDGE",
        "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
        "L3_REFERENCE_EDGE",
    } <= scope_modalities
    assert counts == {
        "L2_DATA_FORGE_VARIABLE_ALIGNMENT": {"confirmed": 1, "total": 1},
        "L2_FAMILY_EDGE": {"contested": 1, "incomplete": 1, "total": 2},
        "L2_MODERATION_EDGE": {"contested": 1, "total": 1},
        "L3_REFERENCE_EDGE": {"incomplete": 1, "total": 1},
    }
    assert sum(row["total"] for row in counts.values()) == len(controlled_edges)


def test_credal_controlled_exact_and_family_payloads_roundtrip_against_independent_oracle() -> None:
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.credal_reference import (
        _derive_l2_causal_edge,
        _derive_l2_family_edge,
    )

    def assert_wire_roundtrip(
        edge: CredalReferenceEdge,
        expected_core: dict[str, object],
    ) -> None:
        expected_payload = {
            **expected_core,
            "content_hash": gy_content_hash(expected_core),
        }
        assert edge.to_payload() == expected_payload
        wire = json.dumps(
            edge.to_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        decoded = json.loads(wire)
        assert decoded == expected_payload
        replayed = CredalReferenceEdge(
            modality=decoded["modality"],
            edge_id=decoded["edge_id"],
            status=decoded["status"],
            admissible_completions=tuple(
                AdmissibleCompletion(
                    completion_kind=item["completion_kind"],
                    value=item["value"],
                    reason=item["reason"],
                )
                for item in decoded["admissible_completions"]
            ),
            provenance=decoded["provenance"],
            unit=decoded["unit"],
            scale=decoded["scale"],
            content_hash=decoded["content_hash"],
        )
        assert replayed.to_payload() == expected_payload

    causal_quality = {
        "design_quality_tiers": [2],
        "publish_blockers": ["controlled_nonempirical_signal"],
        "strong_design_evidence": {
            "all": False,
            "any": False,
            "count": 0,
            "share_pct": 0.0,
        },
    }
    causal_row = (
        "controlled-causal-edge",
        "controlled-policy",
        "controlled-outcome",
        "positive",
        2,
        "meta_analysis",
        0.55,
        "candidate",
        json.dumps(causal_quality, sort_keys=True),
    )
    causal_edge = _derive_l2_causal_edge(
        causal_row,
        version="controlled-v1",
        variable_names={"controlled-policy", "controlled-outcome"},
        approved_variables={"controlled-policy", "controlled-outcome"},
        contested_edges={},
    )
    causal_value = {
        "direction": "positive",
        "dst": "controlled-outcome",
        "src": "controlled-policy",
    }
    causal_core = {
        "admissible_completions": [
            {
                "completion_kind": "alternative",
                "reason": "edge_candidate_supported",
                "value": causal_value,
            },
            {
                "completion_kind": "may_not_exist",
                "reason": "edge_quality_not_decisive",
                "value": causal_value,
            },
        ],
        "edge_id": "controlled-causal-edge",
        "modality": "L2_CAUSAL_EDGE",
        "provenance": {
            "owner": "L2",
            "source": "ac_skg_edges",
            "version": "controlled-v1",
            "signals": {
                "candidate_layer": "candidate",
                "confidence": 0.55,
                "design_quality_tiers": [2],
                "edge_in_contested_membership": False,
                "evidence_strength": "meta_analysis",
                "n_articles": 2,
                "publish_blockers": ["controlled_nonempirical_signal"],
                "strong_design_evidence": {
                    "all": False,
                    "any": False,
                    "count": 0,
                    "share_pct": 0.0,
                },
            },
        },
        "scale": None,
        "status": "contested",
        "unit": None,
    }
    assert_wire_roundtrip(causal_edge, causal_core)

    family_quality = {
        "conflict_flag": False,
        "direction_agreement": 0.7,
        "exact_edge_count": 1,
        "exact_edge_ids": ["controlled-family-edge"],
        "n_unique_claims": 2,
        "n_unique_works": 2,
    }
    family_row = (
        "controlled-family-edge",
        "controlled-policy",
        "controlled-outcome",
        "positive",
        3,
        2,
        "observational",
        0.6,
        '{"positive":2}',
        '{"2":2}',
        "family",
        json.dumps(family_quality, sort_keys=True),
    )
    family_edge = _derive_l2_family_edge(
        family_row,
        version="controlled-v1",
        variable_names={"controlled-policy", "controlled-outcome"},
        contested_edges={},
    )
    family_value = {
        "direction": "positive",
        "dst": "controlled-outcome",
        "src": "controlled-policy",
    }
    family_core = {
        "admissible_completions": [
            {
                "completion_kind": "alternative",
                "reason": "family_edge_candidate_supported",
                "value": family_value,
            },
            {
                "completion_kind": "may_not_exist",
                "reason": "family_edge_quality_not_decisive",
                "value": family_value,
            },
        ],
        "edge_id": "controlled-family-edge",
        "modality": "L2_FAMILY_EDGE",
        "provenance": {
            "owner": "L2",
            "source": "ac_skg_family_edges",
            "version": "controlled-v1",
            "signals": {
                "candidate_layer": "family",
                "confidence": 0.6,
                "design_tier_histogram": {"2": 2},
                "direction_agreement": 0.7,
                "edge_in_contested_membership": False,
                "evidence_strength": "observational",
                "n_articles": 3,
                "n_claims": 2,
                "quality_signals": family_quality,
            },
        },
        "scale": None,
        "status": "contested",
        "unit": None,
    }
    assert_wire_roundtrip(family_edge, family_core)


def test_credal_controlled_certificate_stales_after_source_content_repair() -> None:
    profile = _selected_l2_profile_fixture()
    seed = _profiled_l2_reference(profile)
    baseline = _r1219_controlled_reference(
        tuple(seed.essential_edges.values()),
        profile=profile,
        as_of=seed.as_of,
    )
    contested = baseline.essential_edges[("L2_CAUSAL_EDGE", "edge-a")]
    certificate = bind_grounding_certificate_reference(
        baseline,
        certificate_id="r1219-controlled-certificate",
        edge_scope=(contested.key,),
    )
    repaired = CredalReferenceEdge(
        modality=contested.modality,
        edge_id=contested.edge_id,
        status="confirmed",
        admissible_completions=(
            AdmissibleCompletion(
                "fixed",
                {"controlled_revision": "candidate-v2"},
                "controlled_source_repair",
            ),
        ),
        provenance={**dict(contested.provenance), "controlled_revision": "candidate-v2"},
        unit=contested.unit,
        scale=contested.scale,
    ).with_content_hash()
    current_edges = tuple(
        repaired if edge.key == repaired.key else edge for edge in baseline.essential_edges.values()
    )
    current = _r1219_controlled_reference(
        current_edges,
        profile=profile,
        as_of=baseline.as_of,
    )
    staleness = reference_certificate_staleness(certificate, current)

    assert credal_reference_l2_source_profile(baseline) == profile
    assert credal_reference_l2_source_profile(current) == profile
    assert profile.source_snapshot_authenticity == "not_established"
    assert profile.currentness_status == "not_established"
    assert current.reference_hash != baseline.reference_hash
    assert current.reference_epoch != baseline.reference_epoch
    assert staleness.status == "stale"
    assert "reference_epoch_changed" in staleness.reasons
    assert "reference_hash_changed" in staleness.reasons
    assert "scoped_edge_hash_changed" in staleness.reasons
    assert staleness.stale_edge_keys == (f"{contested.modality}::{contested.edge_id}",)


def test_credal_production_default_vintage_refusal_constructs_no_source_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import credal_reference as owner

    controlled_profile = _selected_l2_profile_fixture()
    controlled = _profiled_l2_reference(controlled_profile)
    assert credal_reference_l2_source_profile(controlled) == controlled_profile
    assert controlled_profile.authority_band == "candidate"
    assert controlled_profile.source_snapshot_authenticity == "not_established"
    assert controlled_profile.currentness_status == "not_established"

    profile_validations: list[object] = []
    original_model_validate = owner.CredalReferenceSourceProfile.model_validate

    def profile_validation_spy(
        _cls: type[CredalReferenceSourceProfile],
        value: object,
        *args: object,
        **kwargs: object,
    ) -> CredalReferenceSourceProfile:
        profile_validations.append(value)
        return original_model_validate(value, *args, **kwargs)

    monkeypatch.setattr(
        owner.CredalReferenceSourceProfile,
        "model_validate",
        classmethod(profile_validation_spy),
    )
    with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
        owner.build_credal_reference(REPO_ROOT)
    assert profile_validations == []
