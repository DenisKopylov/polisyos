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
    CredalReferenceSourceProfile,
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
