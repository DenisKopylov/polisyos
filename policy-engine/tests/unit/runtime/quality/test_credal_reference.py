from __future__ import annotations

import hashlib
import json
from collections import UserDict
from collections.abc import Hashable, Iterable, Iterator
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
    WorkRecord,
)
from polisyos.ir.analytics.literature import (
    ClaimVocabularyAxisStatus,
    DesignFamily,
    EvidenceStrength,
    SourceBasis,
)
from polisyos.runtime.quality.credal_reference import (
    CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
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
    _derive_l3_threshold_edge,
    _iter_l2_edges,
    _reference_hash,
    all_essential_confirmed,
    bind_grounding_certificate_reference,
    build_grounding_backend_availability,
    credal_reference_data_forge_catalog_source_profile,
    credal_reference_l2_source_profile,
    derive_variable_alignment_edge,
    essential_edge_scope_definition,
    reference_certificate_staleness,
    reference_lift,
    replace_reference_edge,
)
from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
from tests._helpers.catalog_source_admission import admit_fixture_catalog_source

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
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
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
        essential_edges={
            **complete.essential_edges,
            missing_profile.key: missing_profile,
        },
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


def test_profileless_v3_credal_reference_is_refused() -> None:
    from polisyos.runtime.quality import credal_reference as owner

    with pytest.raises(
        ValueError,
        match="credal_reference_catalog_source_profile_missing",
    ):
        CredalReference(
            schema_version=owner.CREDAL_REFERENCE_SCHEMA_VERSION,
            reference_epoch="kref:unbound-profileless-v3",
            reference_hash="sha256:" + "5" * 64,
            as_of="2026-10-14",
            component_versions={},
            essential_edges={},
        )


@pytest.mark.parametrize(
    "schema_version",
    [
        "policyos.runtime.grounding_credal_reference.v1",
        CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    ],
)
def test_supported_historical_profileless_reference_schemas_stay_readable(
    schema_version: str,
) -> None:
    historical = CredalReference(
        schema_version=schema_version,
        reference_epoch="kref:historical-profileless",
        reference_hash="sha256:" + "4" * 64,
        as_of="2026-10-11",
        component_versions={},
        essential_edges={},
    )
    assert historical.schema_version == schema_version
    assert credal_reference_l2_source_profile(historical) is None


def test_unknown_profileless_reference_schema_is_rejected_at_construction() -> None:
    from dataclasses import replace

    historical = CredalReference(
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
        reference_epoch="kref:historical-profileless",
        reference_hash="sha256:" + "4" * 64,
        as_of="2026-10-11",
        component_versions={},
        essential_edges={},
    )
    with pytest.raises(ValueError, match="credal_reference_schema_not_supported"):
        replace(
            historical,
            schema_version="policyos.runtime.grounding_credal_reference.v999",
        )


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


def test_catalog_row_profile_stream_preserves_full_hash_and_tuple_primary_key_guard() -> None:
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality.credal_reference import (
        _profile_data_forge_alignment_rows,
    )

    columns = [
        "dataset_id",
        "raw_variable",
        "canonical_var",
        "method",
        "confidence",
        "evidence",
        "is_proxy",
        "proxy_penalty",
    ]
    rows = [
        ("dataset-a", "tax", "policy.tax", "direct", 0.9, "доказ", False, 0.0),
        ("dataset-b", "income", "policy.income", "proxy", 0.75, None, True, 0.2),
    ]
    count, digest = _profile_data_forge_alignment_rows(iter(rows))
    assert count == len(rows)
    assert digest == gy_content_hash({"columns": columns, "rows": tuple(rows)})
    assert _profile_data_forge_alignment_rows(iter(rows[:-1]))[1] != digest
    with pytest.raises(
        ValueError,
        match="credal_reference_data_forge_alignment_primary_key_duplicate",
    ):
        _profile_data_forge_alignment_rows(iter([rows[0], rows[0]]))


def test_catalog_edge_key_collision_refuses_second_distinct_tuple_identity() -> None:
    from types import SimpleNamespace

    from polisyos.runtime.quality import credal_reference as owner

    rows = (
        ("x", "y:z", "w", "direct", 0.9, "first", False, 0.0),
        ("x:y", "z", "w", "direct", 0.9, "second", False, 0.0),
    )
    profile = SimpleNamespace(source_version="fixture-v1", content_hash="sha256:" + "a" * 64)
    source = SimpleNamespace(profile=profile, iter_rows=lambda: iter(rows))
    edge_index = {}

    def add_edges() -> None:
        for edge in owner._iter_data_forge_variable_alignment_edges(
            Path("."),
            variable_names=set(),
            catalog_source=source,
            existing_edge_index=edge_index,
        ):
            owner._insert_l2_edge(edge_index, edge)

    with pytest.raises(
        ValueError,
        match="credal_reference_data_forge_alignment_edge_identity_collision",
    ):
        add_edges()

    assert len(edge_index) == 1
    assert next(iter(edge_index.values())).edge_id == "x:y:z->w"


def test_l3_successor_index_matches_legacy_dates_without_per_row_id_metadata() -> None:
    from datetime import date

    from polisyos.runtime.quality import credal_reference as owner

    class BatchedRows:
        def __init__(self, rows):
            self._rows = iter(rows)
            self.max_batch = 0

        def fetchmany(self, size):
            batch = []
            for _ in range(size):
                try:
                    batch.append(next(self._rows))
                except StopIteration:
                    break
            self.max_batch = max(self.max_batch, len(batch))
            return batch

    threshold_metadata = BatchedRows(
        [
            ("t1", "family", "m", "u", "scope", "2020-01-01"),
            ("t2", "family", "m", "u", "scope", "2020-01-01"),
            ("t3", "family", "m", "u", "scope", "2022-03-04"),
            ("t4", "", "", "", "", "01.02.2021"),
            ("t5", "", "", "", "", "invalid"),
            ("t6", "", "", "", "", "2023-04-05"),
            ("", "", "", "", "", "2024-01-01"),
        ]
    )
    threshold_successors = owner._temporal_successors(
        threshold_metadata,
        id_index=0,
        group_indexes=(1, 2, 3, 4),
        date_index=5,
        require_nonempty_group_indexes=(),
    )
    assert len(threshold_successors) == 2
    assert threshold_successors[(("family", "m", "u", "scope"), date(2020, 1, 1))] == (
        date(2022, 3, 4)
    )
    assert owner._temporal_successor_for_row(
        threshold_successors,
        (
            "t2",
            "ignored",
            "m",
            "ignored",
            "ignored",
            "ignored",
            "u",
            "scope",
            "family",
            "2020-01-01",
        ),
        id_index=0,
        group_indexes=(8, 2, 6, 7),
        date_index=9,
        require_nonempty_group_indexes=(),
    ) == date(2022, 3, 4)
    assert threshold_successors[(("", "", "", ""), date(2021, 2, 1))] == date(2023, 4, 5)
    assert threshold_metadata.max_batch == 7

    amendment_metadata = BatchedRows(
        [
            ("a1", "doc", "anchor", "2020-01-01"),
            ("a2", "doc", "anchor", "2021-03-04"),
            ("a3", "doc", "anchor", "2022-05-06"),
            ("a4", "", "anchor", "2023-01-01"),
            ("a5", "doc", "", "2020-02-03"),
            ("a6", "doc", "", "2022-02-03"),
            ("a7", "", "anchor", "2024-01-01"),
        ]
    )
    amendment_successors = owner._temporal_successors(
        amendment_metadata,
        id_index=0,
        group_indexes=(1, 2),
        date_index=3,
        require_nonempty_group_indexes=(0,),
    )
    assert len(amendment_successors) == 3
    assert amendment_successors[(("doc", "anchor"), date(2020, 1, 1))] == date(2021, 3, 4)
    assert owner._temporal_successor_for_row(
        amendment_successors,
        (
            "a5",
            "amending",
            "doc",
            True,
            "type",
            "",
            "old",
            "new",
            "2020-02-03",
            0.9,
            "{}",
        ),
        id_index=0,
        group_indexes=(2, 5),
        date_index=8,
        require_nonempty_group_indexes=(0,),
    ) == date(2022, 2, 3)
    assert amendment_metadata.max_batch == 7


def test_l3_owner_stream_matches_legacy_full_payload_and_tail_removal(
    tmp_path: Path,
) -> None:
    from collections import defaultdict

    from polisyos.runtime.quality import credal_reference as owner

    db_path = tmp_path / owner.DEFAULT_L3_LEX_KG_PATH
    db_path.parent.mkdir(parents=True)
    with duckdb.connect(str(db_path)) as connection:
        connection.execute(
            "CREATE TABLE lex_normative_ready_facts ("
            "fact_id VARCHAR PRIMARY KEY, doc_family_id VARCHAR, effective_from VARCHAR, "
            "effective_to VARCHAR, temporal_state VARCHAR, temporal_resolution_status VARCHAR, "
            "quality_band VARCHAR, gate_reason_codes VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE lex_rule_thresholds ("
            "threshold_id VARCHAR PRIMARY KEY, fact_id VARCHAR, metric VARCHAR, operator VARCHAR, "
            "value_decimal VARCHAR, value_text VARCHAR, unit VARCHAR, applies_to VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE lex_amendments ("
            "amendment_id VARCHAR PRIMARY KEY, amending_doc_id VARCHAR, amended_doc_id VARCHAR, "
            "target_resolution_expected BOOLEAN, amendment_type VARCHAR, target_anchor VARCHAR, "
            "old_text_uk VARCHAR, new_text_uk VARCHAR, effective_from VARCHAR, confidence DOUBLE, "
            "metadata VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE lex_reference_edges ("
            "reference_edge_id VARCHAR PRIMARY KEY, source_doc_id VARCHAR, "
            "source_doc_family_id VARCHAR, source_anchor VARCHAR, target_doc_id VARCHAR, "
            "target_doc_family_id VARCHAR, target_doc_reestr_code VARCHAR, "
            "target_doc_number VARCHAR, target_doc_type VARCHAR, target_doc_date_acc VARCHAR, "
            "target_doc_status VARCHAR, target_anchor VARCHAR, relation_type VARCHAR, "
            "matched_by VARCHAR, resolution_confidence DOUBLE, resolution_status VARCHAR, "
            "version_id INTEGER, metadata VARCHAR)"
        )
        connection.executemany(
            "INSERT INTO lex_normative_ready_facts VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    "f1",
                    "family",
                    "2020-01-01",
                    "2021-01-01",
                    "active",
                    "exact",
                    "non_ready",
                    "[]",
                ),
                ("f2", "family", "2022-03-04", None, "active", "exact", "ready", "[]"),
                ("f3", "", "01.02.2021", None, "active", "exact", "ready", "[]"),
                ("f4", "", "2023-04-05", None, "active", "exact", "ready", "[]"),
                (
                    "f5",
                    "invalid-family",
                    "not-a-date",
                    None,
                    "active",
                    "exact",
                    "ready",
                    "[]",
                ),
            ],
        )
        threshold_source_rows = [
            ("t1", "f1", "m", "<=", "1", None, "u", "scope"),
            ("t1b", "f1", "m", "<=", "1", None, "u", "scope"),
            ("t2", "f2", "m", "<=", "2", None, "u", "scope"),
            ("t3", "f3", "", "<=", "3", None, "", ""),
            ("t4", "f4", "", "<=", "4", None, "", ""),
            ("t5", "f5", "x", "<=", "5", None, "u", "scope"),
            ("t6", "missing-fact", "missing", "<=", "6", None, "u", "scope"),
            ("zz-tail", "missing-tail", "tail", "<=", "7", None, "u", "scope"),
        ]
        connection.executemany(
            "INSERT INTO lex_rule_thresholds VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            threshold_source_rows,
        )
        amendment_source_rows = [
            (
                "a1",
                "amender",
                "doc",
                True,
                "replace",
                "alpha",
                "old",
                "new",
                "2020-01-01",
                0.9,
                "{}",
            ),
            (
                "a2",
                "amender",
                "doc",
                True,
                "replace",
                "alpha",
                "old",
                "new",
                "2021-03-04",
                0.9,
                "{}",
            ),
            (
                "a3",
                "amender",
                "doc",
                True,
                "replace",
                "alpha",
                "old",
                "new",
                "2022-05-06",
                0.9,
                "{}",
            ),
            (
                "a4",
                "amender",
                "",
                False,
                "replace",
                "alpha",
                "old",
                "new",
                "2023-01-01",
                0.9,
                "{}",
            ),
            (
                "a5",
                "amender",
                "doc",
                True,
                "replace",
                "",
                "old",
                "new",
                "2020-02-03",
                0.9,
                "{}",
            ),
            (
                "a6",
                "amender",
                "doc",
                True,
                "replace",
                "",
                "old",
                "new",
                "2022-02-03",
                0.9,
                "{}",
            ),
            (
                "",
                "amender",
                "doc",
                True,
                "replace",
                "alpha",
                "old",
                "new",
                "2024-01-01",
                0.9,
                "{}",
            ),
        ]
        connection.executemany(
            "INSERT INTO lex_amendments VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            amendment_source_rows,
        )
        connection.execute(
            "INSERT INTO lex_reference_edges VALUES "
            "('ref-1','source','family','anchor','target','target-family','code','n1',"
            "'law','2020-01-01','active','target-anchor','cites','exact',0.9,'resolved',7,'{}')"
        )

    def legacy_successors(rows, *, id_index, group_indexes, date_index, nonempty=()):
        grouped = defaultdict(list)
        for row in rows:
            row_id = str(row[id_index] or "")
            key = tuple(str(row[index] or "") for index in group_indexes)
            start = owner._parse_date(row[date_index])
            if row_id and start is not None and all(key[index] for index in nonempty):
                grouped[key].append((row_id, start))
        output = {}
        for items in grouped.values():
            ordered = sorted(items, key=lambda item: item[1])
            for index, (row_id, start) in enumerate(ordered[:-1]):
                for _, candidate in ordered[index + 1 :]:
                    if candidate > start:
                        output[row_id] = candidate
                        break
        return output

    as_of = "2010-01-01"
    with duckdb.connect(str(db_path), read_only=True) as connection:
        version_row = connection.execute(
            "SELECT MAX(effective_from) FROM lex_amendments"
        ).fetchone()
        version = str(version_row[0] or db_path.parent.name)
        threshold_rows = connection.execute(
            """SELECT t.threshold_id, t.fact_id, t.metric, t.operator, t.value_decimal,
                      t.value_text, t.unit, t.applies_to, f.doc_family_id, f.effective_from,
                      f.effective_to, f.temporal_state, f.temporal_resolution_status,
                      f.quality_band, f.gate_reason_codes
               FROM lex_rule_thresholds t
               LEFT JOIN lex_normative_ready_facts f ON t.fact_id=f.fact_id
               ORDER BY t.threshold_id"""
        ).fetchall()
        amendment_rows = connection.execute(
            """SELECT amendment_id, amending_doc_id, amended_doc_id,
                      target_resolution_expected, amendment_type, target_anchor,
                      old_text_uk, new_text_uk, effective_from, confidence, metadata
               FROM lex_amendments ORDER BY amendment_id"""
        ).fetchall()
        reference_rows = connection.execute(
            """SELECT reference_edge_id, source_doc_id, source_doc_family_id, source_anchor,
                      target_doc_id, target_doc_family_id, target_doc_reestr_code,
                      target_doc_number, target_doc_type, target_doc_date_acc, target_doc_status,
                      target_anchor, relation_type, matched_by, resolution_confidence,
                      resolution_status, version_id, metadata
               FROM lex_reference_edges ORDER BY reference_edge_id"""
        ).fetchall()

    threshold_next = legacy_successors(
        threshold_rows,
        id_index=0,
        group_indexes=(8, 2, 6, 7),
        date_index=9,
    )
    amendment_next = legacy_successors(
        amendment_rows,
        id_index=0,
        group_indexes=(2, 5),
        date_index=8,
        nonempty=(0,),
    )
    expected = [
        owner._derive_l3_threshold_edge(
            row,
            version=version,
            as_of=as_of,
            next_start=threshold_next.get(str(row[0] or "")),
        )
        for row in threshold_rows
    ]
    expected.extend(
        owner._derive_l3_amendment_edge(
            row,
            version=version,
            as_of=as_of,
            next_start=amendment_next.get(str(row[0] or "")),
        )
        for row in amendment_rows
    )
    expected.extend(owner._derive_l3_reference_edge(row, version=version) for row in reference_rows)
    actual = tuple(owner._iter_l3_edges(tmp_path, as_of=as_of))

    assert len(actual) == len(threshold_source_rows) + len(amendment_source_rows) + 1
    assert [edge.to_payload() for edge in actual] == [edge.to_payload() for edge in expected]

    import shutil

    snapshot_root = tmp_path / "l3-snapshot-mutation"
    snapshot_db = snapshot_root / owner.DEFAULT_L3_LEX_KG_PATH
    snapshot_db.parent.mkdir(parents=True)
    replacement_db = snapshot_db.with_name(f"{snapshot_db.name}.replacement")
    shutil.copyfile(db_path, snapshot_db)
    shutil.copyfile(db_path, replacement_db)
    with duckdb.connect(str(replacement_db)) as connection:
        connection.execute(
            "UPDATE lex_rule_thresholds SET value_text='changed' WHERE threshold_id='zz-tail'"
        )

    in_flight = iter(owner._iter_l3_edges(snapshot_root, as_of=as_of))
    first_edge = next(in_flight)
    opened_db = snapshot_db.with_name(f"{snapshot_db.name}.opened")
    snapshot_db.replace(opened_db)
    replacement_db.replace(snapshot_db)
    in_flight_edges = (first_edge, *in_flight)
    assert [edge.to_payload() for edge in in_flight_edges] == [
        edge.to_payload() for edge in expected
    ]
    assert [edge.to_payload() for edge in owner._iter_l3_edges(snapshot_root, as_of=as_of)] != [
        edge.to_payload() for edge in expected
    ]

    by_key = {edge.key: edge for edge in actual}
    versions = owner._component_versions(by_key)
    reference_hash = owner._reference_hash(
        component_versions=versions,
        edge_index=by_key,
        as_of=as_of,
        schema_version=owner.CREDAL_REFERENCE_SCHEMA_VERSION,
    )
    assert reference_hash == owner._reference_hash(
        component_versions=owner._component_versions({edge.key: edge for edge in expected}),
        edge_index={edge.key: edge for edge in expected},
        as_of=as_of,
        schema_version=owner.CREDAL_REFERENCE_SCHEMA_VERSION,
    )
    assert by_key[("L3_RULE_THRESHOLD", "t1")].provenance["signals"]["next_effective_from"] == (
        "2022-03-04"
    )
    assert by_key[("L3_RULE_THRESHOLD", "t3")].provenance["signals"]["next_effective_from"] == (
        "2023-04-05"
    )
    assert by_key[("L3_RULE_THRESHOLD", "t6")].provenance["signals"]["effective_from"] == ""
    assert by_key[("L3_AMENDMENT", "a3")].provenance["signals"]["next_effective_from"] is None

    with duckdb.connect(str(db_path)) as connection:
        connection.execute("DELETE FROM lex_rule_thresholds WHERE threshold_id='zz-tail'")
    after_tail_removal = tuple(owner._iter_l3_edges(tmp_path, as_of=as_of))
    after_index = {edge.key: edge for edge in after_tail_removal}
    after_hash = owner._reference_hash(
        component_versions=owner._component_versions(after_index),
        edge_index=after_index,
        as_of=as_of,
        schema_version=owner.CREDAL_REFERENCE_SCHEMA_VERSION,
    )
    assert len(after_tail_removal) == len(actual) - 1
    assert after_hash != reference_hash


def test_prepared_skg_rows_drive_kref_without_claiming_data_forge_source(
    tmp_path: Path,
) -> None:
    from polisyos.data_forge.domains.academic.knowledge.skg_store import (
        ensure_skg_schema,
    )
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
    assert data_forge_alignment.provenance["selected_catalog_source_profile_hash"]


_PHASE5_FIXTURE_LAW_ID = "fixture_candidate_only_law_token"
_PHASE5_FIXTURE_KNOB_ID = "budget_allocation_multiplier"
_PHASE5_FIXTURE_SLOT_ID = "government.balance"


def _phase5_preflight_fixture_destinations(
    root: Path,
    output_destinations: Iterable[Path],
    *,
    extra_destinations: Iterable[Path] = (),
) -> None:
    """Prove every planned fixture output is fresh, distinct, and root-contained."""
    root = root.resolve()
    destinations = (*output_destinations, *extra_destinations)
    resolved_destinations: list[Path] = []
    for destination in destinations:
        if destination.exists() or destination.is_symlink():
            raise AssertionError("phase5_fixture_destination_not_fresh")
        resolved = destination.resolve()
        if not resolved.is_relative_to(root):
            raise AssertionError("phase5_fixture_destination_outside_root")
        current = destination
        while current != root:
            if current.is_symlink():
                raise AssertionError("phase5_fixture_destination_symlinked")
            if current == current.parent:
                raise AssertionError("phase5_fixture_destination_outside_root")
            current = current.parent
        resolved_destinations.append(resolved)
    if len(resolved_destinations) != len(set(resolved_destinations)):
        raise AssertionError("phase5_fixture_destinations_alias")


def _phase5_skg_fixture_output_paths(root: Path) -> tuple[Path, ...]:
    """Name the controlled SKG fixture database and its writer-owned outputs."""
    database_path = root.resolve() / DEFAULT_L2_SCHOLAR_KG_PATH
    wal_path = database_path.with_suffix(database_path.suffix + ".wal")
    staging_path = database_path.with_suffix(database_path.suffix + ".staging")
    staging_database_path = staging_path / "graph-load.sqlite"
    return database_path, wal_path, staging_path, staging_database_path


def _phase5_build_synthetic_skg_fixture(
    root: Path,
    records: Iterable[WorkRecord],
) -> Path:
    """Preflight all controlled SKG outputs before creating the fixture or producer."""
    root = root.resolve()
    database_path, wal_path, staging_path, staging_database_path = _phase5_skg_fixture_output_paths(
        root
    )
    _phase5_preflight_fixture_destinations(
        root,
        (database_path, wal_path, staging_path, staging_database_path),
    )
    database_path.parent.mkdir(parents=True, exist_ok=True)
    from tests._helpers.academic_skg import build_synthetic_academic_skg_source

    build_synthetic_academic_skg_source(records=records, db_path=database_path)
    assert database_path.resolve().is_relative_to(root)
    return database_path


def _phase5_l6_fixture_paths(
    root: Path,
    *,
    extra_destinations: Iterable[Path] = (),
) -> dict[str, Path]:
    """Write one explicitly synthetic L6 fixture below the caller-selected root."""
    from polisyos.runtime.quality.intervention_substrate import default_l6_bundle_paths

    root = root.resolve()
    paths = default_l6_bundle_paths(root)
    mechanism = {
        "mechanism_id": _PHASE5_FIXTURE_KNOB_ID,
        "params": {
            "multiplier": {
                "param_id": "multiplier",
                "required": True,
                "value_type": "decimal",
                "min_value": 0,
                "max_value": 2,
                "unit_id": "ratio",
            }
        },
        "reads_slots": [_PHASE5_FIXTURE_SLOT_ID],
        "writes_slots": [_PHASE5_FIXTURE_SLOT_ID],
        "default_merge": {_PHASE5_FIXTURE_SLOT_ID: "override"},
        "provenance_refs": ["tests:phase5-candidate-fixture-only"],
    }
    payloads = {
        "intervention_knob_dictionary": {
            _PHASE5_FIXTURE_KNOB_ID: {
                "default": 1.0,
                "type": "float",
                "min": 0.0,
                "max": 2.0,
                "unit": "ratio",
                "mechanism_id": _PHASE5_FIXTURE_KNOB_ID,
                "param_id": "multiplier",
                "param_path": "params.multiplier",
            }
        },
        "lex_intervention_map": {_PHASE5_FIXTURE_LAW_ID: {"knob_ids": [_PHASE5_FIXTURE_KNOB_ID]}},
        "observation_to_contract_manifest": {"routes": [], "artifacts": []},
        "slot_family_manifest": {
            "families": {"controlled_candidate_fixture": {"slots": [_PHASE5_FIXTURE_SLOT_ID]}}
        },
        "owner_authority_bindings": {
            "world_mechanism_manifest": {"mechanisms": {_PHASE5_FIXTURE_KNOB_ID: mechanism}},
            "lex_authority_manifest": {
                "intervention_map_entries": [
                    {
                        "law_token": _PHASE5_FIXTURE_LAW_ID,
                        "provision_ref": "fixture-only:opaque-provision-handle",
                        "intervention_kind": _PHASE5_FIXTURE_KNOB_ID,
                        "knob_ids": [_PHASE5_FIXTURE_KNOB_ID],
                        "threshold_id": "fixture-only-empty-threshold",
                        "as_of": "2026-10-18",
                        "candidate_unit": "ratio",
                        "applies_to": "synthetic_fixture_population",
                        "measurement_expectations": {
                            "threshold_id": "fixture-only-empty-threshold",
                            "as_of": "2026-10-18",
                            "candidate_unit": "ratio",
                            "applies_to": "synthetic_fixture_population",
                        },
                        "metadata": {"law_token": _PHASE5_FIXTURE_LAW_ID},
                    }
                ]
            },
        },
    }
    _phase5_preflight_fixture_destinations(
        root,
        tuple(paths[name] for name in payloads),
        extra_destinations=extra_destinations,
    )
    for name, payload in payloads.items():
        path = paths[name]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, sort_keys=True) + "\n")
        assert path.resolve().is_relative_to(root)
    return paths


def _phase5_l6_candidate_world_model_record():
    """Build a typed, local-only WMR with no calibration or external authority claim."""
    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        DataForgeBindingRef,
        FabricWorldRef,
        FoundryBindingRef,
        PolicySlotBinding,
        ResolvedSubstrateEntryRef,
        SimulationModelRef,
        SkgCausalPriorRef,
        SubstrateRegistryRef,
        WorldModelLimitations,
        WorldModelRecord,
        world_model_record_content_hash,
    )

    def digest(label: str) -> str:
        return "sha256:" + hashlib.sha256(label.encode()).hexdigest()

    fields = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "candidate_unverified",
        "created_at": "2026-10-18T00:00:00+00:00",
        "producer_ref": "tests.phase5_candidate_fixture_only",
        "region_or_jurisdiction": "fixture-only",
        "population_scope": "synthetic_fixture_population",
        "policy_domain": "fixture-only",
        "valid_time_scope": "fixture-only",
        "tx_time_scope": "2026-10-18T00:00:00+00:00",
        "resolution": "fixture-only",
        "branch_mode": BranchMode.SCENARIO,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root="fixture-only://synthetic-world",
            snapshot_id="fixture-only-world",
            branch="candidate",
            world_query_policy="fixture-only",
            provenance_manifest_ref="fixture-only://provenance",
            content_query_digest=digest("fixture-world-query"),
            content_query_row_count=1,
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id="fixture-only-data",
            release_id="fixture-only-release",
            role="fixture-only",
            read_api_identity="tests.fixture-only",
            snapshot_ref="fixture-only://data",
            merkle_root="fixture-only-merkle-root",
            data_hash=digest("fixture-data"),
            provenance_manifest_ref="fixture-only://data-provenance",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=digest("fixture-model-ref"),
            model_spec_hash=digest("fixture-model-hash"),
            model_id="fixture_only_model",
            data_snapshot_ref=digest("fixture-snapshot"),
            registry_bundle_ref=digest("fixture-registry"),
            fidelity_level="declared_candidate_fixture",
            calibrated=False,
            calibration_ref=None,
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=digest("fixture-input-bindings"),
            bound_state_snapshot_ref=digest("fixture-state"),
            mapping_rules_ref=digest("fixture-mapping-rules"),
            state_slot_digest=digest("fixture-state-slots"),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref="fixture-only://unselected-skg",
            skg_version_id="fixture-only-version",
            source_data_snapshot_id="fixture-only-snapshot",
        ),
        "substrate_registry_ref": SubstrateRegistryRef(
            substrate_version_id="substrate_version_" + hashlib.sha256(b"fixture").hexdigest()[:16],
            content_hash=digest("fixture-substrate-registry"),
            resolved_entries=(
                ResolvedSubstrateEntryRef(
                    source_id="fixture-only-source",
                    family_id="fixture-only-family",
                    layer="L1",
                    coverage_score=0.0,
                    trust_tier="not_established",
                    trust_cap=0.0,
                    identification_mode="not_established",
                    schema_regime_id="fixture-only-v1",
                    data_version="fixture-only-version",
                    snapshot_id="fixture-only-snapshot",
                    source_snapshot_id="fixture-only-snapshot",
                    entry_content_hash=digest("fixture-entry"),
                ),
            ),
        ),
        "policy_slot_map": (
            PolicySlotBinding(
                slot_id=_PHASE5_FIXTURE_SLOT_ID,
                state_path="government_balance",
                unit="ratio",
                entity_scope="government",
                temporal_granularity="fixture-only",
            ),
        ),
        "limitations": WorldModelLimitations(
            admissibility_blockers=(
                "synthetic_fixture_only",
                "external_law_authority_not_established",
                "calibration_not_established",
            )
        ),
    }
    draft = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=digest("placeholder"),
        **fields,
    )
    content_hash = world_model_record_content_hash(draft)
    return WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _phase5_l6_law_scope(root: Path):
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality import grounding_relation as atoms
    from polisyos.runtime.quality import intervention_substrate as substrate

    root = root.resolve()
    lex_path = root / owner.DEFAULT_L3_LEX_KG_PATH
    paths = _phase5_l6_fixture_paths(root, extra_destinations=(lex_path,))
    world = _phase5_l6_candidate_world_model_record()
    lex_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(lex_path)) as connection:
        connection.execute("CREATE TABLE lex_rule_thresholds (threshold_id VARCHAR)")
    assert lex_path.resolve().is_relative_to(root)

    bundle = substrate.load_l6_intervention_substrate(root)
    raw_map = json.loads(paths["lex_intervention_map"].read_text())
    assert bundle.lex_intervention_map == raw_map
    edges = [
        *owner._iter_l6_edges(root, world_model_record=world),
        *owner._iter_wmr_edges(world),
    ]
    index = {edge.key: edge for edge in edges}
    versions = owner._component_versions(index, world_model_record=world)
    digest = owner._reference_hash(
        component_versions=versions,
        edge_index=index,
        as_of=owner.DEFAULT_REFERENCE_AS_OF,
        schema_version=owner.CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    )
    scoped = CredalReference(
        owner.CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
        "kref:" + digest.removeprefix("sha256:")[:16],
        digest,
        owner.DEFAULT_REFERENCE_AS_OF,
        versions,
        index,
    )
    return root, bundle, scoped, atoms._reference_atoms_from_cg0(scoped)


def _assert_phase5_atom_law_lifts(atoms, law_keys: set[str]) -> None:
    """Check every law projection emitted into every selected atom."""
    from polisyos.data_forge.domains.legal.source_relation import (
        LEGAL_SOURCE_RELATION_REFUSAL,
    )

    expected_refusal = LEGAL_SOURCE_RELATION_REFUSAL.to_payload()
    assert law_keys
    covered_law_keys: set[str] = set()
    for atom in atoms:
        atom_law_keys = law_keys.intersection(atom.reference_lift)
        for law_key in atom_law_keys:
            projection = atom.reference_lift[law_key]
            assert projection["status"] == "incomplete"
            assert "source_relation_refusal" in projection
            assert projection["source_relation_refusal"] == expected_refusal
            assert any(
                completion.get("completion_kind") == "may_exist"
                and completion.get("reason") == LEGAL_SOURCE_RELATION_REFUSAL.code
                for completion in projection["admissible_completions"]
            )
            covered_law_keys.add(law_key)
    assert covered_law_keys == law_keys


def _assert_phase5_law_scope_preserved_and_nonconfirmed(root, bundle, scoped, atoms):
    from polisyos.data_forge.domains.legal.source_relation import (
        LEGAL_SOURCE_RELATION_REFUSAL,
    )
    from polisyos.runtime.quality import intervention_substrate as substrate

    laws = {
        edge.edge_id: edge
        for edge in scoped.essential_edges.values()
        if edge.modality == "L6_LEX_INTERVENTION_MAP"
    }
    raw_path = substrate.default_l6_bundle_paths(root)["lex_intervention_map"]
    assert raw_path.resolve().is_relative_to(root.resolve())
    raw = json.loads(raw_path.read_text())
    assert set(laws) == set(bundle.lex_intervention_map) == set(raw)
    assert {edge.status for edge in laws.values()} == {"incomplete"}
    expected_pairs = {
        (law_token, knob_id)
        for law_token, mapping in raw.items()
        for knob_id in mapping["knob_ids"]
    }
    observed_pairs = {
        (edge.edge_id, str(completion.value["knob_id"]))
        for edge in laws.values()
        for completion in edge.admissible_completions
        if completion.completion_kind == "may_exist" and "knob_id" in completion.value
    }
    assert observed_pairs == expected_pairs
    assert all(
        any(
            completion.completion_kind == "may_exist"
            and completion.reason == "legal_source_relation_verification_not_established"
            for completion in edge.admissible_completions
        )
        for edge in laws.values()
    )
    expected_knobs = set(bundle.knob_dictionary)
    assert {atom.signature.op for atom in atoms} == expected_knobs
    law_keys = {f"{edge.modality}::{edge.edge_id}" for edge in laws.values()}
    _assert_phase5_atom_law_lifts(atoms, law_keys)
    lifted = reference_lift(scoped, law_keys)
    assert all(item["status"] == "incomplete" for item in lifted.values())
    assert all_essential_confirmed(scoped, law_keys) is False
    assert all(
        item["source_relation_refusal"] == LEGAL_SOURCE_RELATION_REFUSAL.to_payload()
        for item in lifted.values()
    )
    for atom in atoms:
        assert law_keys.intersection(atom.edge_scope)
        assert atom.signature.admissibility == "reference_contested"


def test_phase5_l6_fixture_rejects_malformed_mapping_input(tmp_path: Path) -> None:
    from polisyos.runtime.quality.intervention_substrate import (
        InterventionSubstrateError,
        load_l6_intervention_substrate,
    )

    root = tmp_path.resolve()
    paths = _phase5_l6_fixture_paths(root)
    malformed = paths["lex_intervention_map"]
    malformed.write_text("[]\n")
    assert malformed.resolve().is_relative_to(root)
    with pytest.raises(InterventionSubstrateError, match="json_object_expected"):
        load_l6_intervention_substrate(root)


def test_phase5_fixture_path_preflight_rejects_escape_before_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality import intervention_substrate

    root = tmp_path / "fresh-fixture-root"
    escaped_destination = tmp_path / "outside-fixture-root.json"
    assert not root.exists()
    assert not escaped_destination.exists()
    original_paths = intervention_substrate.default_l6_bundle_paths

    def escaped_paths(selected_root: Path) -> dict[str, Path]:
        paths = original_paths(selected_root)
        paths["lex_intervention_map"] = escaped_destination
        return paths

    monkeypatch.setattr(
        intervention_substrate,
        "default_l6_bundle_paths",
        escaped_paths,
    )
    with pytest.raises(AssertionError, match="phase5_fixture_destination_outside_root"):
        _phase5_l6_fixture_paths(root)
    assert not root.exists()
    assert not escaped_destination.exists()


def test_phase5_skg_fixture_path_preflight_rejects_escape_before_factory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests._helpers import academic_skg

    root = tmp_path / "fresh-skg-fixture-root"
    escaped_database = tmp_path / "outside-skg-fixture.duckdb"
    assert not root.exists()
    assert not escaped_database.exists()
    factory_calls: list[Path] = []

    def forbidden_factory(*, records: Iterable[object], db_path: Path) -> object:
        del records
        factory_calls.append(db_path)
        raise AssertionError("synthetic_skg_factory_called_before_fixture_preflight")

    monkeypatch.setitem(
        globals(),
        "DEFAULT_L2_SCHOLAR_KG_PATH",
        Path("../outside-skg-fixture.duckdb"),
    )
    monkeypatch.setattr(
        academic_skg,
        "build_synthetic_academic_skg_source",
        forbidden_factory,
    )
    with pytest.raises(AssertionError, match="phase5_fixture_destination_outside_root"):
        _phase5_build_synthetic_skg_fixture(root, records=())
    assert factory_calls == []
    assert not root.exists()
    assert all(
        not path.exists() and not path.is_symlink()
        for path in _phase5_skg_fixture_output_paths(root)
    )


def test_phase5_law_owner_refusal_survives_credal_and_atom_consumers(
    tmp_path: Path,
) -> None:
    _assert_phase5_law_scope_preserved_and_nonconfirmed(*_phase5_l6_law_scope(tmp_path))


@pytest.mark.parametrize(
    "schema_version",
    [
        "policyos.runtime.grounding_credal_reference.v1",
        CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    ],
)
def test_replayed_legacy_lex_mapping_is_candidate_only_in_current_atoms(
    schema_version: str,
) -> None:
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.grounding_relation import GroundingRelationEngine
    from polisyos.runtime.quality.promotion_sequence import _CredalReferenceReplayRecord

    edges = {
        ("L6_KNOB_OPERATOR", "tax_relief_rate"): owner._confirmed_edge(
            "L6_KNOB_OPERATOR",
            "tax_relief_rate",
            {
                "operator_kind": "tax_relief_rate",
                "parameter_domain": {"minimum": 0, "maximum": 1, "unit": "ratio"},
            },
            {
                "owner": "L6",
                "source": "intervention_knob_dictionary",
                "version": "legacy",
            },
            unit="ratio",
        ),
        ("L6_KNOB_WORLD_SLOT", "tax_relief_rate"): owner._confirmed_edge(
            "L6_KNOB_WORLD_SLOT",
            "tax_relief_rate",
            {
                "operator_kind": "tax_relief_rate",
                "target_world_slots": ["global.tax_rate"],
                "world_model_record_id": "wmr:controlled",
            },
            {
                "owner": "L6",
                "source": "intervention_knob_dictionary",
                "version": "legacy",
            },
            unit="ratio",
        ),
        ("L6_LEX_INTERVENTION_MAP", "tax_relief_statute"): owner._confirmed_edge(
            "L6_LEX_INTERVENTION_MAP",
            "tax_relief_statute",
            {
                "knob_id": "tax_relief_rate",
                "provision_ref": "controlled:provision",
                "threshold_id": "controlled:threshold",
            },
            {
                "owner": "L6",
                "source": "lex_intervention_map",
                "version": "legacy",
                "signals": {"law_token": "tax_relief_statute"},
            },
        ),
        ("WMR_WORLD_SLOT", "global.tax_rate"): owner._confirmed_edge(
            "WMR_WORLD_SLOT",
            "global.tax_rate",
            {"world_slot": "global.tax_rate", "value_type": "float"},
            {"owner": "WMR", "source": "world_model_record", "version": "controlled"},
            unit="ratio",
        ),
        ("WMR_POLICY_SLOT_MAP", "tax_slot:global.tax_rate"): owner._confirmed_edge(
            "WMR_POLICY_SLOT_MAP",
            "tax_slot:global.tax_rate",
            {"world_slot": "global.tax_rate", "binding_id": "tax_slot"},
            {"owner": "WMR", "source": "world_model_record", "version": "controlled"},
            unit="ratio",
        ),
    }
    component_versions = owner._component_versions(
        edges,
        world_model_record_hash="controlled-wmr-v1",
    )
    reference_hash = _reference_hash(
        component_versions=component_versions,
        edge_index=edges,
        as_of="2026-06-29",
        schema_version=schema_version,
    )
    reference = CredalReference(
        schema_version=schema_version,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions=component_versions,
        essential_edges=edges,
    )
    stored_law_edge = reference.essential_edges[("L6_LEX_INTERVENTION_MAP", "tax_relief_statute")]

    serialized = _CredalReferenceReplayRecord.from_reference(reference).model_dump(mode="json")
    replayed = _CredalReferenceReplayRecord.model_validate(serialized).to_reference()
    law_key = "L6_LEX_INTERVENTION_MAP::tax_relief_statute"
    lifted = reference_lift(replayed, [law_key])[law_key]

    assert replayed == reference
    assert replayed.essential_edges[stored_law_edge.key] == stored_law_edge
    assert lifted["status"] == "incomplete"
    assert lifted["source_relation_refusal"] == {
        "code": "legal_source_relation_verification_not_established",
        "status": "verification_missing",
    }
    assert lifted["admissible_completions"] == [
        {
            "completion_kind": "may_exist",
            "reason": "legal_source_relation_verification_not_established",
            "value": {
                "knob_id": "tax_relief_rate",
                "provision_ref": "controlled:provision",
                "threshold_id": "controlled:threshold",
            },
        }
    ]
    assert all_essential_confirmed(replayed, [law_key]) is False

    atoms = GroundingRelationEngine(replayed).reference_atoms
    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.signature.admissibility == "reference_contested"
    assert (
        atom.reference_lift[law_key]["source_relation_refusal"] == lifted["source_relation_refusal"]
    )


def test_l6_projection_opens_selected_lex_database_through_public_facade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    import duckdb

    from polisyos.lex import knowledge
    from polisyos.runtime.quality import credal_reference as owner

    relative_db_path = Path("fixture/lex.duckdb")
    db_path = tmp_path / relative_db_path
    db_path.parent.mkdir()
    connection = duckdb.connect(str(db_path))
    connection.close()
    monkeypatch.setattr(owner, "DEFAULT_L3_LEX_KG_PATH", relative_db_path)
    monkeypatch.setattr(
        owner,
        "load_l6_intervention_substrate",
        lambda _root: SimpleNamespace(
            content_hash="fixture-content",
            knob_dictionary={},
            lex_intervention_map={},
        ),
    )
    monkeypatch.setattr(owner, "_iter_l6_observation_route_edges", lambda *_args, **_kwargs: ())

    store_type = knowledge.LegalKnowledgeStore
    opened: list[store_type] = []

    class TrackedLegalKnowledgeStore(store_type):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            opened.append(self)

    monkeypatch.setattr(knowledge, "LegalKnowledgeStore", TrackedLegalKnowledgeStore)

    assert list(owner._iter_l6_edges(tmp_path, world_model_record=object())) == []
    assert len(opened) == 1
    assert opened[0]._db_path == db_path
    opened[0].close()


def test_phase5_law_resolution_exception_keeps_declared_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.intervention_substrate import (
        InterventionSubstrateError,
    )

    def unresolved(*args, **kwargs):
        raise InterventionSubstrateError("law_threshold_unresolved")

    monkeypatch.setattr(owner, "resolve_law_bound_lever", unresolved)
    _root, bundle, scoped, atoms = _phase5_l6_law_scope(tmp_path)
    laws = {
        edge.edge_id: edge
        for edge in scoped.essential_edges.values()
        if edge.modality == "L6_LEX_INTERVENTION_MAP"
    }
    assert set(laws) == set(bundle.lex_intervention_map)
    assert {edge.status for edge in laws.values()} == {"incomplete"}
    unresolved_edges = tuple(
        edge
        for edge in laws.values()
        if any(
            completion.reason == "law_threshold_unresolved"
            for completion in edge.admissible_completions
        )
    )
    assert unresolved_edges
    assert all(
        any(
            completion.completion_kind == "may_exist" and completion.value.get("knob_id")
            for completion in edge.admissible_completions
        )
        for edge in unresolved_edges
    )
    assert {atom.signature.admissibility for atom in atoms} == {"reference_contested"}


def test_l3_threshold_with_complete_temporal_fields_stays_incomplete_without_relation_receipt() -> (
    None
):
    from polisyos.data_forge.domains.legal.source_relation import (
        LEGAL_SOURCE_RELATION_REFUSAL,
    )

    edge = _derive_l3_threshold_edge(
        (
            "threshold:employee-cap",
            "fact:employee-cap",
            "employee_count",
            "<=",
            "50",
            None,
            "persons",
            "microenterprise",
            "ua-law-family:1",
            "2026-01-01",
            None,
            "in_force",
            "resolved",
            "high",
            "",
        ),
        version="controlled-lex-v1",
        as_of="2026-04-01",
        next_start=None,
    )

    assert edge.modality == "L3_RULE_THRESHOLD"
    assert edge.status == "incomplete"
    assert edge.provenance["signals"]["source_relation_refusal"] == (
        LEGAL_SOURCE_RELATION_REFUSAL.to_payload()
    )
    assert all(
        completion.value == {} and completion.reason == LEGAL_SOURCE_RELATION_REFUSAL.code
        for completion in edge.admissible_completions
    )


def test_phase5_atom_consumer_refusal_removal_goes_red(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.data_forge.domains.legal.source_relation import (
        LEGAL_SOURCE_RELATION_REFUSAL,
    )

    original_reference_lift = CredalReference.reference_lift

    def omit_atom_refusal(self, edge_scope):
        projected = original_reference_lift(self, edge_scope)
        for key, value in projected.items():
            if key.startswith("L6_LEX_INTERVENTION_MAP::"):
                value.pop("source_relation_refusal", None)
        return projected

    monkeypatch.setattr(CredalReference, "reference_lift", omit_atom_refusal)
    _root, _bundle, scoped, atoms = _phase5_l6_law_scope(tmp_path)
    laws = {
        edge.edge_id: edge
        for edge in scoped.essential_edges.values()
        if edge.modality == "L6_LEX_INTERVENTION_MAP"
    }
    law_keys = {f"L6_LEX_INTERVENTION_MAP::{law_id}" for law_id in laws}
    assert law_keys
    assert all(edge.status == "incomplete" for edge in laws.values())
    assert all(
        any(
            completion.reason == LEGAL_SOURCE_RELATION_REFUSAL.code
            for completion in edge.admissible_completions
        )
        for edge in laws.values()
    )
    atom_lift_law_keys = {
        law_key for atom in atoms for law_key in law_keys.intersection(atom.reference_lift)
    }
    assert atom_lift_law_keys == law_keys
    assert all(
        "source_relation_refusal" not in atom.reference_lift[law_key]
        for atom in atoms
        for law_key in law_keys.intersection(atom.reference_lift)
    )
    with pytest.raises(AssertionError):
        _assert_phase5_atom_law_lifts(atoms, law_keys)


@pytest.mark.parametrize("removed", ["status", "association"])
def test_phase5_law_handoff_removal_goes_red(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, removed: str
) -> None:
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
        _assert_phase5_law_scope_preserved_and_nonconfirmed(*_phase5_l6_law_scope(tmp_path))


def test_phase5_historical_reference_replay_keeps_epoch_and_current_stales_it(
    tmp_path: Path,
) -> None:
    from dataclasses import replace

    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.promotion_sequence import _CredalReferenceReplayRecord

    _root, _bundle, current, _atoms = _phase5_l6_law_scope(tmp_path)
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
    assert current.schema_version == CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION
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
    from polisyos.runtime.quality import credal_reference as owner

    edges = {
        ("L2_CONTESTED_EDGE", "controlled-contested"): owner._edge(
            "L2_CONTESTED_EDGE",
            "controlled-contested",
            "contested",
            (
                AdmissibleCompletion("alternative", {"src": "x", "dst": "y"}, "fixture_candidate"),
                AdmissibleCompletion(
                    "may_not_exist", {"src": "x", "dst": "y"}, "fixture_uncertain"
                ),
            ),
            {"owner": "L2", "source": "controlled_fixture"},
        ),
        ("L2_FAMILY_EDGE", "controlled-family"): owner._edge(
            "L2_FAMILY_EDGE",
            "controlled-family",
            "incomplete",
            (AdmissibleCompletion("may_exist", {}, "family_edge_endpoint_unresolved"),),
            {"owner": "L2", "source": "controlled_fixture"},
        ),
        ("L2_MODERATION_EDGE", "controlled-moderation"): owner._edge(
            "L2_MODERATION_EDGE",
            "controlled-moderation",
            "incomplete",
            (AdmissibleCompletion("may_exist", {}, "moderation_fixture_unresolved"),),
            {"owner": "L2", "source": "controlled_fixture"},
        ),
        ("L2_DATA_FORGE_VARIABLE_ALIGNMENT", "controlled-alignment"): owner._edge(
            "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
            "controlled-alignment",
            "incomplete",
            (AdmissibleCompletion("may_exist", {}, "alignment_fixture_unresolved"),),
            {"owner": "L2/DataForge", "source": "controlled_fixture"},
        ),
        ("L3_REFERENCE_EDGE", "controlled-reference"): owner._edge(
            "L3_REFERENCE_EDGE",
            "controlled-reference",
            "incomplete",
            (AdmissibleCompletion("may_exist", {}, "reference_fixture_unresolved"),),
            {"owner": "L3", "source": "controlled_fixture"},
        ),
    }
    component_versions = owner._component_versions(
        edges,
        world_model_record_hash="sha256:" + "5" * 64,
    )
    reference_hash = _reference_hash(
        component_versions=component_versions,
        edge_index=edges,
        as_of="2026-06-29",
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions=component_versions,
        essential_edges=edges,
    )


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


def test_expanded_essential_scope_classes_are_counted(
    reference: CredalReference,
) -> None:
    counts = reference.denominator_counts()
    scope = essential_edge_scope_definition()
    modalities = {edge_class["modality"] for edge_class in scope["included_edge_classes"]}

    assert "L2_FAMILY_EDGE" in modalities
    assert "L2_MODERATION_EDGE" in modalities
    assert "L2_DATA_FORGE_VARIABLE_ALIGNMENT" in modalities
    assert "L3_REFERENCE_EDGE" in modalities
    assert counts["L2_FAMILY_EDGE"]["total"] == 1
    assert counts["L2_MODERATION_EDGE"]["total"] == 1
    assert counts["L2_DATA_FORGE_VARIABLE_ALIGNMENT"]["total"] == 1
    assert counts["L3_REFERENCE_EDGE"]["total"] == 1


def test_historical_l2_edge_payloads_roundtrip_without_current_recomputation() -> None:
    """Keep historical edge bytes readable without forwarding the blocked source vintage."""

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

    historical_edges: dict[tuple[str, str], CredalReferenceEdge] = {}
    for key, oracle in expected.items():
        payload = json.loads(oracle)
        edge = CredalReferenceEdge(
            modality=payload["modality"],
            edge_id=payload["edge_id"],
            status=payload["status"],
            admissible_completions=tuple(
                AdmissibleCompletion(
                    item["completion_kind"],
                    item["value"],
                    item["reason"],
                )
                for item in payload["admissible_completions"]
            ),
            provenance=payload["provenance"],
            unit=payload["unit"],
            scale=payload["scale"],
            content_hash=payload["content_hash"],
        )
        assert edge.key == key
        assert edge.with_content_hash().to_payload() == payload
        historical_edges[key] = edge

    from polisyos.runtime.quality import credal_reference as owner

    component_versions = owner._component_versions(
        historical_edges,
        world_model_record_hash="sha256:" + "5" * 64,
    )
    reference_hash = _reference_hash(
        component_versions=component_versions,
        edge_index=historical_edges,
        as_of="2026-06-29",
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    )
    historical_reference = CredalReference(
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-06-29",
        component_versions=component_versions,
        essential_edges=historical_edges,
    )
    lifted = reference_lift(historical_reference, historical_edges)
    assert {key: item["status"] for key, item in lifted.items()} == {
        f"{modality}::{edge_id}": payload["status"]
        for (modality, edge_id), oracle in expected.items()
        for payload in (json.loads(oracle),)
    }


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
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    )
    reference = CredalReference(
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
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

    schema_version = MutableWireText(CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION, "mutable-schema")
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
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    )
    return CredalReference(
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
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
    value = {
        "direction": "positive",
        "dst": "controlled-outcome",
        "src": "controlled-policy",
    }
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
        provenance={
            **dict(contested.provenance),
            "controlled_revision": "candidate-v2",
        },
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


def test_credal_controlled_default_vintage_refusal_constructs_no_source_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.data_forge.domains.academic.knowledge.types import (
        EstimateCandidate,
        WorkRecord,
    )

    root = tmp_path.resolve()
    record = WorkRecord(
        id="controlled-stale-vintage-source",
        title="Synthetic historical-vintage refusal fixture",
        abstract="Synthetic test fixture; no production or causal claim.",
        year=2026,
        estimates=[
            EstimateCandidate(
                value=0.0,
                pattern_name="controlled_candidate_fixture",
                variable_hint="cause",
            )
        ],
        metadata={
            "synthetic": True,
            "fixture_scope": "credal_vintage_refusal_test_only",
        },
    )
    db_path = _phase5_build_synthetic_skg_fixture(root, records=(record,))
    with db_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    monkeypatch.setattr(skg_versioning, "_HISTORICAL_SNAPSHOT_SHA256", digest, raising=False)

    profile_validations: list[object] = []
    original_model_validate = CredalReferenceSourceProfile.model_validate

    def profile_validation_spy(
        _cls: type[CredalReferenceSourceProfile],
        value: object,
        *args: object,
        **kwargs: object,
    ) -> CredalReferenceSourceProfile:
        profile_validations.append(value)
        return original_model_validate(value, *args, **kwargs)

    monkeypatch.setattr(
        CredalReferenceSourceProfile,
        "model_validate",
        classmethod(profile_validation_spy),
    )
    edges = iter(_iter_l2_edges(root))
    try:
        with pytest.raises(ValueError, match="not_reproducible_under_current_rule"):
            next(edges)
    finally:
        edges.close()
    assert profile_validations == []


def _write_n4_catalog(path: Path, rows: tuple[tuple[object, ...], ...]) -> None:
    from polisyos.data_forge.domains.catalog.batch.core_sources.schema import (
        create_alignment_review_basis_table,
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as connection:
        connection.execute("DROP TABLE IF EXISTS ds_variable_alignments")
        connection.execute(
            """
            CREATE TABLE ds_variable_alignments (
                dataset_id VARCHAR NOT NULL,
                raw_variable VARCHAR NOT NULL,
                canonical_var VARCHAR NOT NULL,
                method VARCHAR NOT NULL,
                confidence FLOAT NOT NULL,
                evidence VARCHAR NOT NULL,
                is_proxy BOOLEAN DEFAULT FALSE,
                proxy_penalty FLOAT DEFAULT 0.0,
                PRIMARY KEY (dataset_id, raw_variable, canonical_var)
            )
            """
        )
        create_alignment_review_basis_table(connection)
        for row in rows:
            connection.execute(
                "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )


def _selected_n4_catalog_source(repo_root: Path, snapshot_root: Path) -> CatalogServingSourcePaths:
    root = repo_root.resolve()
    snapshot = snapshot_root.resolve()
    database = snapshot / "datasets" / "graph" / "dataset_catalog.duckdb"
    return admit_fixture_catalog_source(
        repo_root=root, database_path=database, catalog_run_profile="prod_core_blocking"
    )


def _build_n4_reference_from_selected_catalog(
    monkeypatch: pytest.MonkeyPatch,
    repo_root: Path,
    source: CatalogServingSourcePaths,
) -> CredalReference:
    import asyncio
    from contextlib import contextmanager
    from types import SimpleNamespace

    from polisyos.data_forge.domains.academic.knowledge import skg_query
    from polisyos.data_forge.read_api.academic import PreparedSKGCredalSourceRows
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.substrate_registry import run_catalog_source_awaitable

    selected_profile = _selected_l2_profile_fixture()
    selected_rows = PreparedSKGCredalSourceRows(
        source_snapshot_ref=selected_profile.source_snapshot_ref,
        source_snapshot_sha256=selected_profile.source_snapshot_sha256,
        version_id=7,
        variables=(
            skg_query._CredalVariableRow(
                "policy.tax_rate",
                "policy.tax_rate",
                True,
                "controlled-fixture",
                0.95,
                2,
                None,
                None,
            ),
        ),
        variable_synonyms=(),
        causal_edges=(),
        family_edges=(),
        moderation_edges=(),
        contested_edges=(),
        causal_claim_results=(),
        synthetic_column_present=False,
        synthetic_values=(),
    )

    class _PreparedReadFixture:
        def read_credal_source_rows(self) -> PreparedSKGCredalSourceRows:
            return selected_rows

        def _prepare_credal_source_stream(self) -> SimpleNamespace:
            return SimpleNamespace(
                source_snapshot_ref=selected_rows.source_snapshot_ref,
                source_snapshot_sha256=selected_rows.source_snapshot_sha256,
                version_id=selected_rows.version_id,
                iter_variables=lambda: iter(selected_rows.variables),
                iter_variable_synonyms=lambda: iter(selected_rows.variable_synonyms),
                iter_causal_edges=lambda: iter(selected_rows.causal_edges),
                iter_family_edges=lambda: iter(selected_rows.family_edges),
                iter_moderation_edges=lambda: iter(selected_rows.moderation_edges),
                iter_contested_edges=lambda: iter(selected_rows.contested_edges),
                iter_causal_claim_results=lambda: iter(selected_rows.causal_claim_results),
                iter_synthetic_values=lambda: iter(selected_rows.synthetic_values),
            )

    @contextmanager
    def _prepared_l2_source(_root: Path, _world: object) -> Iterator[object]:
        yield owner._PreparedL2Source(
            prepared_read=_PreparedReadFixture(),
            profile=selected_profile,
            version="7",
        )

    monkeypatch.setattr(owner, "_prepared_l2_source", _prepared_l2_source)
    monkeypatch.setattr(owner, "_iter_l3_edges", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(owner, "_iter_l6_edges", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(owner, "_iter_wmr_edges", lambda *_args, **_kwargs: ())
    world = SimpleNamespace(content_hash="sha256:" + "1" * 64)

    async def _build():
        await asyncio.sleep(0)
        return owner.build_credal_reference(repo_root, world_model_record=world)

    return asyncio.run(run_catalog_source_awaitable(source, _build()))


def test_selected_catalog_context_binds_all_alignment_rows_into_kref(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.substrate_registry import (
        default_substrate_catalog_paths,
    )

    root = tmp_path.resolve()
    default_path = default_substrate_catalog_paths(root).l1_dcat_path
    _write_n4_catalog(
        default_path,
        (
            (
                "default",
                "tax",
                "policy.tax_rate",
                "default",
                0.91,
                "default basis",
                False,
                0.0,
            ),
        ),
    )
    selected_a_path = (
        root / "snapshots" / "catalog-a" / "datasets" / "graph" / "dataset_catalog.duckdb"
    )
    selected_a_rows = (
        ("selected-a", "tax", "policy.tax_rate", "a", 0.92, "A canonical", False, 0.0),
        (
            "selected-a",
            "raw unknown",
            "unmapped.canonical",
            "a",
            0.89,
            "A other",
            False,
            0.0,
        ),
    )
    _write_n4_catalog(selected_a_path, selected_a_rows)
    source_a = _selected_n4_catalog_source(root, root / "snapshots" / "catalog-a")

    reference_a = _build_n4_reference_from_selected_catalog(monkeypatch, root, source_a)
    profile_a = credal_reference_data_forge_catalog_source_profile(reference_a)
    assert profile_a is not None
    assert profile_a.selection_owner == "catalog_serving_source_paths"
    assert profile_a.selection_basis == "explicit_path_candidate_only"
    assert profile_a.source_database_path == str(selected_a_path.resolve())
    assert profile_a.alignment_row_count == 2
    assert profile_a.alignment_rows_sha256
    assert profile_a.authority_band == "candidate"
    assert profile_a.source_snapshot_authenticity == "not_established"
    assert profile_a.currentness_status == "not_established"
    selected_a_edges = tuple(
        edge
        for edge in reference_a.essential_edges.values()
        if edge.modality == "L2_DATA_FORGE_VARIABLE_ALIGNMENT"
    )
    assert len(selected_a_edges) == 2
    assert any(edge.status == "incomplete" for edge in selected_a_edges)
    assert {
        edge.provenance["selected_catalog_source_profile_hash"] for edge in selected_a_edges
    } == {profile_a.content_hash}

    # The operational review sidecar is not producer semantic evidence and
    # must not perturb the public credal reference hash.
    with duckdb.connect(str(selected_a_path)) as connection:
        connection.execute(
            "INSERT INTO ds_alignment_review_basis "
            "(dataset_id, raw_variable, basis_version, basis_json, basis_sha256) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                "selected-a",
                "tax",
                "policyos.catalog.alignment_review_basis.v2",
                '{"review":"one"}',
                "1" * 64,
            ],
        )
    reference_a_with_review_basis = _build_n4_reference_from_selected_catalog(
        monkeypatch, root, source_a
    )
    assert reference_a_with_review_basis.reference_hash == reference_a.reference_hash
    with duckdb.connect(str(selected_a_path)) as connection:
        connection.execute(
            "UPDATE ds_alignment_review_basis SET basis_json = ?, basis_sha256 = ? "
            "WHERE dataset_id = 'selected-a' AND raw_variable = 'tax'",
            ['{"review":"two"}', "2" * 64],
        )
    reference_a_with_changed_review_basis = _build_n4_reference_from_selected_catalog(
        monkeypatch, root, source_a
    )
    assert reference_a_with_changed_review_basis.reference_hash == reference_a.reference_hash

    _write_n4_catalog(
        default_path,
        (
            (
                "default",
                "changed",
                "policy.tax_rate",
                "default",
                0.99,
                "changed default",
                False,
                0.0,
            ),
        ),
    )
    reference_a_after_default_change = _build_n4_reference_from_selected_catalog(
        monkeypatch,
        root,
        source_a,
    )
    assert reference_a_after_default_change.reference_hash == reference_a.reference_hash

    selected_b_path = (
        root / "snapshots" / "catalog-b" / "datasets" / "graph" / "dataset_catalog.duckdb"
    )
    selected_b_rows = (
        ("selected-b", "income", "policy.tax_rate", "b", 0.96, "B basis", False, 0.0),
    )
    _write_n4_catalog(selected_b_path, selected_b_rows)
    source_b = _selected_n4_catalog_source(root, root / "snapshots" / "catalog-b")
    reference_b = _build_n4_reference_from_selected_catalog(monkeypatch, root, source_b)
    profile_b = credal_reference_data_forge_catalog_source_profile(reference_b)

    assert profile_b is not None
    assert profile_b.source_database_path == str(selected_b_path.resolve())
    assert profile_b.alignment_row_count == 1
    assert reference_b.reference_hash != reference_a.reference_hash


def test_selected_catalog_denominator_survives_absent_l2_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio
    from contextlib import contextmanager
    from types import SimpleNamespace

    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.substrate_registry import run_catalog_source_awaitable

    root = tmp_path.resolve()
    snapshot_root = root / "snapshots" / "catalog-without-l2"
    catalog_path = snapshot_root / "datasets" / "graph" / "dataset_catalog.duckdb"
    rows = (
        ("selected", "tax", "policy.tax_rate", "source", 0.92, "tax map", False, 0.0),
        (
            "selected",
            "unknown",
            "unmapped.canonical",
            "source",
            0.89,
            "other",
            False,
            0.0,
        ),
    )
    _write_n4_catalog(catalog_path, rows)
    source = _selected_n4_catalog_source(root, snapshot_root)

    @contextmanager
    def _absent_l2(_root: Path, _world: object) -> Iterator[None]:
        yield None

    monkeypatch.setattr(owner, "_prepared_l2_source", _absent_l2)
    monkeypatch.setattr(owner, "_iter_l3_edges", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(owner, "_iter_l6_edges", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(owner, "_iter_wmr_edges", lambda *_args, **_kwargs: ())
    world = SimpleNamespace(content_hash="sha256:" + "1" * 64)

    async def _build():
        await asyncio.sleep(0)
        return owner.build_credal_reference(root, world_model_record=world)

    reference = asyncio.run(run_catalog_source_awaitable(source, _build()))
    profile = credal_reference_data_forge_catalog_source_profile(reference)
    edges = tuple(
        edge
        for edge in reference.essential_edges.values()
        if edge.modality == "L2_DATA_FORGE_VARIABLE_ALIGNMENT"
    )

    assert profile is not None
    assert profile.alignment_row_count == len(rows) == len(edges)
    assert "L2_SOURCE_PROFILE" not in reference.component_versions
    assert reference.component_versions["DATA_FORGE_CATALOG_SOURCE_PROFILE"] == profile.content_hash
    assert {edge.status for edge in edges} == {"incomplete"}
    assert {edge.provenance["selected_catalog_source_profile_hash"] for edge in edges} == {
        profile.content_hash
    }


def test_empty_selected_catalog_profile_survives_replay_and_present_source_never_falls_back(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.runtime.quality.promotion_sequence import _CredalReferenceReplayRecord
    from polisyos.runtime.quality.substrate_registry import (
        default_substrate_catalog_paths,
    )

    root = tmp_path.resolve()
    default_path = default_substrate_catalog_paths(root).l1_dcat_path
    _write_n4_catalog(
        default_path,
        (
            (
                "default",
                "tax",
                "policy.tax_rate",
                "default",
                0.91,
                "default basis",
                False,
                0.0,
            ),
        ),
    )
    empty_path = root / "snapshots" / "empty" / "datasets" / "graph" / "dataset_catalog.duckdb"
    _write_n4_catalog(empty_path, ())
    source_empty = _selected_n4_catalog_source(root, root / "snapshots" / "empty")
    empty_reference = _build_n4_reference_from_selected_catalog(
        monkeypatch,
        root,
        source_empty,
    )
    empty_profile = credal_reference_data_forge_catalog_source_profile(empty_reference)
    assert empty_profile is not None
    assert empty_profile.alignment_row_count == 0
    assert empty_profile.alignment_rows_sha256
    assert empty_reference.component_versions["DATA_FORGE_CATALOG_SOURCE_PROFILE"] == (
        empty_profile.content_hash
    )
    assert not any(
        edge.modality == "L2_DATA_FORGE_VARIABLE_ALIGNMENT"
        for edge in empty_reference.essential_edges.values()
    )
    replay = _CredalReferenceReplayRecord.from_reference(empty_reference)
    assert replay.data_forge_catalog_source_profile == empty_profile
    assert replay.to_reference() == empty_reference

    # Missing bytes fail at the actual selector, before a source context exists.
    with pytest.raises(ValueError, match="catalog_source_database_missing"):
        _selected_n4_catalog_source(root, root / "snapshots" / "missing")

    malformed_path = (
        root / "snapshots" / "malformed" / "datasets" / "graph" / "dataset_catalog.duckdb"
    )
    malformed_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(malformed_path)):
        pass
    (malformed_path.parent / "manifest.json").write_text("{", encoding="utf-8")
    malformed_source = _selected_n4_catalog_source(root, root / "snapshots" / "malformed")
    with pytest.raises(
        ValueError,
        match="credal_reference_data_forge_manifest_invalid",
    ):
        _build_n4_reference_from_selected_catalog(monkeypatch, root, malformed_source)

    missing_table_path = (
        root / "snapshots" / "missing-table" / "datasets" / "graph" / "dataset_catalog.duckdb"
    )
    missing_table_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(missing_table_path)) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER)")
    missing_table_source = _selected_n4_catalog_source(
        root,
        root / "snapshots" / "missing-table",
    )
    with pytest.raises(
        ValueError,
        match="credal_reference_data_forge_catalog_read_failed",
    ):
        _build_n4_reference_from_selected_catalog(monkeypatch, root, missing_table_source)


@pytest.mark.parametrize(
    ("case", "expected_status", "expected_reason"),
    [
        ("resolved", "confirmed", None),
        ("refused_candidate_unbound", "incomplete", "knob_operator_unresolved"),
        ("refused_acquisition_required", "incomplete", "knob_operator_unresolved"),
        ("malformed", "incomplete", "knob_domain_type_missing"),
    ],
)
def test_l6_intervention_result_union_preserves_typed_edge_and_bounded_lift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_status: str,
    expected_reason: str | None,
) -> None:
    """Keep typed refusals on edges while exposing only their bounded lift."""

    from types import SimpleNamespace

    from polisyos.lex import knowledge
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality import intervention_substrate as substrate

    knob_entry: dict[str, str | int | float] = {"min": 0.0, "max": 1.0}
    if case != "malformed":
        knob_entry["type"] = "float"
    knob_dictionary = {"fixture_knob": knob_entry}
    source_refs = {"intervention_knob_dictionary": "fixture://l6/knobs"}
    source_hashes = {"intervention_knob_dictionary": gy_content_hash(knob_dictionary)}
    bundle_fields = {
        "schema_version": substrate.INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
        "knob_dictionary": knob_dictionary,
        "lex_intervention_map": {},
        "observation_manifest": {},
        "policy_scenario_templates": {},
        "slot_family_manifest": {},
        "world_mechanism_manifest": {},
        "lex_authority_manifest": {},
        "owner_authority_manifest": {},
        "source_refs": source_refs,
        "source_content_hashes": source_hashes,
    }
    bundle = substrate.InterventionSubstrateBundle(
        **bundle_fields,
        content_hash=gy_content_hash(bundle_fields),
    )

    class UnusedLegalStore:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

    monkeypatch.setattr(knowledge, "LegalKnowledgeStore", UnusedLegalStore)
    monkeypatch.setattr(owner, "DEFAULT_L3_LEX_KG_PATH", Path("fixture/lex.duckdb"))
    monkeypatch.setattr(owner, "load_l6_intervention_substrate", lambda _root: bundle)
    monkeypatch.setattr(owner, "_iter_l6_observation_route_edges", lambda *_args, **_kwargs: ())
    world_model_record = SimpleNamespace(world_model_record_id="wmr:controlled")

    refusal = None
    if case == "resolved":

        def owner_binding(*_args: object, **_kwargs: object) -> tuple[object, object]:
            atom = SimpleNamespace(
                atom_id="atom:fixture",
                content_hash="sha256:" + "a" * 64,
            )

            class SlotBinding:
                slot_id = "government.balance"

                def model_dump(self, *, mode: str) -> dict[str, str]:
                    assert mode == "json"
                    return {"slot_id": self.slot_id}

            slot_binding = SlotBinding()
            world_binding = SimpleNamespace(
                world_model_record_id=world_model_record.world_model_record_id,
                world_model_record_content_hash="sha256:" + "b" * 64,
                target_slot_bindings=(slot_binding,),
            )
            return atom, world_binding

        monkeypatch.setattr(substrate, "_resolve_owner_atom_world_binding", owner_binding)
    elif case.startswith("refused_"):
        status = case.removeprefix("refused_")
        refusal_fields = {
            "schema_version": substrate.INTERVENTION_SUBSTRATE_SCHEMA_VERSION,
            "status": status,
            "operator_kind": "fixture_knob",
            "instrument": "fixture.instrument",
            "lever_id": "fixture_knob",
            "reason_code": "knob_operator_unresolved",
            "candidate_entry_content_hash": "sha256:" + "c" * 64,
            "selected_registry_entry_hash": "sha256:" + "d" * 64,
            "substrate_input_content_hash": "sha256:" + "e" * 64,
            "context_binding_hash": "sha256:" + "f" * 64,
            "substrate_registry_content_hash": "sha256:" + "1" * 64,
            "world_model_record_content_hash": "sha256:" + "2" * 64,
            "source_refs": ("fixture://candidate/lever",),
        }
        refusal = substrate.InterventionLeverRefusal.model_validate(
            {**refusal_fields, "content_hash": gy_content_hash(refusal_fields)}
        )
        monkeypatch.setattr(owner, "resolve_intervention_lever", lambda *_args, **_kwargs: refusal)

    edges = tuple(owner._iter_l6_edges(tmp_path, world_model_record=world_model_record))
    assert {edge.modality for edge in edges} == {
        "L6_KNOB_OPERATOR",
        "L6_KNOB_WORLD_SLOT",
    }
    assert {edge.status for edge in edges} == {expected_status}

    edge_index = {edge.key: edge for edge in edges}
    component_versions = owner._component_versions(
        edge_index,
        world_model_record_hash="controlled-wmr-v1",
    )
    reference_hash = owner._reference_hash(
        component_versions=component_versions,
        edge_index=edge_index,
        as_of="2026-10-16",
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
    )
    reference = CredalReference(
        schema_version=CREDAL_REFERENCE_LEGACY_SCHEMA_VERSION,
        reference_epoch=f"kref:{reference_hash.removeprefix('sha256:')[:16]}",
        reference_hash=reference_hash,
        as_of="2026-10-16",
        component_versions=component_versions,
        essential_edges=edge_index,
    )
    scope = tuple(edge.key for edge in edges)
    projection = reference.reference_lift(scope)
    assert {item["status"] for item in projection.values()} == {expected_status}
    assert reference.all_essential_confirmed(scope) is (expected_status == "confirmed")

    if refusal is not None:
        expected_refusal = refusal.model_dump(mode="json")
        for edge in edges:
            assert edge.provenance["resolution_refusal"] == expected_refusal
            lifted = projection[f"{edge.modality}::{edge.edge_id}"]
            assert lifted["status"] == "incomplete"
            assert lifted["content_hash"] == edge.content_hash
            assert refusal.reason_code in {
                completion["reason"] for completion in lifted["admissible_completions"]
            }
            assert "resolution_refusal" not in lifted
            assert "source_refs" not in lifted
    elif expected_reason is not None:
        assert all(
            any(completion.reason == expected_reason for completion in edge.admissible_completions)
            for edge in edges
        )
        assert all("resolution_refusal" not in edge.provenance for edge in edges)
    else:
        assert all("resolution_refusal" not in edge.provenance for edge in edges)


def test_frozen_reference_snapshots_preserve_unhashable_protocol() -> None:
    from polisyos.runtime.quality.credal_reference import _freeze_reference_payload

    list_snapshot = _freeze_reference_payload(["candidate"])
    public_mapping_snapshot = CredalReferenceEdge(
        modality="L6_KNOB_OPERATOR",
        edge_id="fixture_knob",
        status="incomplete",
        admissible_completions=(),
        provenance={"candidate_values": ["candidate"]},
    ).provenance
    public_nested_list = public_mapping_snapshot["candidate_values"]

    for snapshot in (list_snapshot, public_mapping_snapshot, public_nested_list):
        assert type(snapshot).__hash__ is None
        assert not isinstance(snapshot, Hashable)
        with pytest.raises(TypeError, match="unhashable type"):
            hash(snapshot)


def test_float_projection_preserves_supported_numeric_inputs() -> None:
    from decimal import Decimal

    from polisyos.runtime.quality.credal_reference import _float

    assert _float("1.25") == 1.25
    assert _float(Decimal("2.5")) == 2.5
    assert _float(object(), default=3.75) == 3.75


def _seed_n7_full_owner_source_fixture(
    root: Path, *, row_count: int = 257
) -> tuple[Path, Path, Path, Path]:
    """Seed all selected N7 owner relations below one controlled root."""
    from polisyos.data_forge.domains.academic.knowledge.skg_store import (
        ensure_skg_schema,
    )
    from polisyos.runtime.quality import credal_reference as owner

    snapshot_root = root / "snapshots" / "n7-full-source"
    catalog_path = snapshot_root / "datasets" / "graph" / "dataset_catalog.duckdb"
    catalog_path.parent.mkdir(parents=True)
    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute(
            "CREATE TABLE ds_variable_alignments ("
            "dataset_id VARCHAR, raw_variable VARCHAR, canonical_var VARCHAR, "
            "method VARCHAR, confidence FLOAT, evidence VARCHAR, "
            "is_proxy BOOLEAN, proxy_penalty FLOAT)"
        )
        connection.executemany(
            "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f"dataset-{index:03d}",
                    f"raw-{index:03d}",
                    f"variable-{index:03d}",
                    "controlled_fixture",
                    0.92,
                    f"catalog-evidence-{index:03d}",
                    False,
                    0.0,
                )
                for index in range(row_count)
            ],
        )

    skg_path = root / DEFAULT_L2_SCHOLAR_KG_PATH
    skg_path.parent.mkdir(parents=True)
    with duckdb.connect(str(skg_path)) as connection:
        ensure_skg_schema(connection)
        connection.execute("INSERT INTO ac_skg_versions(version_id) VALUES (7)")
        connection.executemany(
            "INSERT INTO ac_skg_variables "
            "(canonical_name, normalized_name, display_name, approved_canonical_name, "
            "is_approved_canonical, resolution_method, resolution_confidence, mention_count) "
            "VALUES (?, ?, 'Fixture variable', ?, TRUE, 'controlled_fixture', 0.95, 2)",
            [
                (f"variable-{index:03d}", f"variable-{index:03d}", f"variable-{index:03d}")
                for index in range(row_count)
            ],
        )
        connection.executemany(
            "INSERT INTO ac_skg_variable_synonyms "
            "(synonym, canonical_name, method, confidence, approved) "
            "VALUES (?, ?, 'controlled_fixture', 0.95, TRUE)",
            [(f"synonym-{index:03d}", f"variable-{index:03d}") for index in range(row_count)],
        )
        connection.executemany(
            "INSERT INTO ac_skg_edges "
            "(edge_id, src, dst, direction, n_articles, article_refs, "
            "evidence_strength, confidence, candidate_layer, quality_signals_json) "
            "VALUES (?, ?, ?, 'increases', 3, '[]', 'strong', 0.9, 'controlled', '{}')",
            [
                (
                    f"causal-{index:03d}",
                    f"variable-{index:03d}",
                    f"variable-{(index + 1) % row_count:03d}",
                )
                for index in range(row_count)
            ],
        )
        connection.executemany(
            "INSERT INTO ac_skg_family_edges "
            "(family_edge_id, src_family, dst_family, direction, n_articles, n_claims, "
            "article_refs, claim_refs, evidence_strength, confidence, "
            "direction_histogram_json, design_tier_histogram_json, candidate_layer, "
            "quality_signals_json) "
            "VALUES (?, ?, ?, 'increases', 3, 2, '[]', '[]', 'strong', 0.9, "
            "'{}', '{}', 'controlled', ?)",
            [
                (
                    f"family-edge-{index:03d}",
                    f"family-{index:03d}",
                    f"family-{(index + 1) % row_count:03d}",
                    "{}",
                )
                for index in range(row_count)
            ],
        )
        connection.executemany(
            "INSERT INTO ac_skg_moderation_edges "
            "(moderation_id, base_cause, base_effect, moderator, base_claim_id, "
            "direction_of_mod, interaction_coeff, interaction_pvalue, evidence_count, "
            "confidence, match_quality, alignment_source, source_refs, skg_version) "
            "VALUES (?, ?, ?, ?, ?, 'decreases', -0.2, 0.05, 3, 0.9, "
            "'exact_claim_ref', 'controlled_fixture', '[]', 7)",
            [
                (
                    f"moderation-{index:03d}",
                    f"variable-{index:03d}",
                    f"variable-{(index + 1) % row_count:03d}",
                    f"variable-{(index + 2) % row_count:03d}",
                    f"claim-{index:03d}",
                )
                for index in range(row_count)
            ],
        )
        connection.executemany(
            "INSERT INTO ac_skg_contested_edges "
            "(contested_edge_id, src_family, dst_family, article_refs, claim_refs, "
            "dominant_direction, resolution_status, runtime_support, evidence_strength, "
            "confidence, positive_weight, negative_weight, mixed_weight, "
            "direction_histogram_json, quality_signals_json) "
            "VALUES (?, ?, ?, '[]', ?, 'increases', 'resolved', 'strong', 'strong', "
            "0.9, 1.0, 0.0, 0.0, '{}', ?)",
            [
                (
                    f"causal-{index:03d}",
                    f"family-{index:03d}",
                    f"family-{(index + 1) % row_count:03d}",
                    f'["claim-{index:03d}"]',
                    json.dumps({"exact_edge_ids": [f"causal-{index:03d}"]}),
                )
                for index in range(row_count)
            ],
        )
        connection.execute(
            "CREATE TABLE ac_causal_claims (id VARCHAR, work_id VARCHAR, cause VARCHAR, "
            "effect VARCHAR, direction VARCHAR, strength VARCHAR, mechanism VARCHAR, "
            "domain VARCHAR, trust_score FLOAT, strong_design_evidence BOOLEAN, "
            "design_quality_tier INTEGER, publish_blockers VARCHAR, candidate_layer VARCHAR)"
        )
        connection.execute("CREATE TABLE ac_works (id VARCHAR, title VARCHAR, year INTEGER)")
        connection.executemany(
            "INSERT INTO ac_works VALUES (?, ?, 2025)",
            [(f"work-{index:03d}", f"Controlled work {index:03d}") for index in range(row_count)],
        )
        connection.executemany(
            "INSERT INTO ac_causal_claims VALUES (?, ?, ?, ?, 'positive', 'rct', "
            "'controlled mechanism', 'fixture-domain', 0.9, TRUE, 3, '[]', 'controlled')",
            [
                (
                    f"claim-{index:03d}",
                    f"work-{index:03d}",
                    f"variable-{index:03d}",
                    f"variable-{(index + 1) % row_count:03d}",
                )
                for index in range(row_count)
            ],
        )
        connection.execute("CREATE TABLE ac_causal_claims_raw (synthetic BOOLEAN)")
        connection.executemany(
            "INSERT INTO ac_causal_claims_raw VALUES (?)",
            [(index == row_count - 1,) for index in range(row_count)],
        )

    l3_path = root / owner.DEFAULT_L3_LEX_KG_PATH
    l3_path.parent.mkdir(parents=True)
    with duckdb.connect(str(l3_path)) as connection:
        connection.execute(
            "CREATE TABLE lex_normative_ready_facts ("
            "fact_id VARCHAR, doc_family_id VARCHAR, effective_from VARCHAR, "
            "effective_to VARCHAR, temporal_state VARCHAR, temporal_resolution_status VARCHAR, "
            "quality_band VARCHAR, gate_reason_codes VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE lex_rule_thresholds (threshold_id VARCHAR, fact_id VARCHAR, "
            "metric VARCHAR, operator VARCHAR, value_decimal VARCHAR, value_text VARCHAR, "
            "unit VARCHAR, applies_to VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE lex_amendments (amendment_id VARCHAR, amending_doc_id VARCHAR, "
            "amended_doc_id VARCHAR, target_resolution_expected BOOLEAN, amendment_type VARCHAR, "
            "target_anchor VARCHAR, old_text_uk VARCHAR, new_text_uk VARCHAR, "
            "effective_from VARCHAR, confidence DOUBLE, metadata VARCHAR)"
        )
        connection.execute(
            "CREATE TABLE lex_reference_edges (reference_edge_id VARCHAR, source_doc_id VARCHAR, "
            "source_doc_family_id VARCHAR, source_anchor VARCHAR, target_doc_id VARCHAR, "
            "target_doc_family_id VARCHAR, target_doc_reestr_code VARCHAR, "
            "target_doc_number VARCHAR, target_doc_type VARCHAR, target_doc_date_acc VARCHAR, "
            "target_doc_status VARCHAR, target_anchor VARCHAR, relation_type VARCHAR, "
            "matched_by VARCHAR, resolution_confidence DOUBLE, resolution_status VARCHAR, "
            "version_id INTEGER, metadata VARCHAR)"
        )
        dates = [f"2020-{1 + index // 28:02d}-{1 + index % 28:02d}" for index in range(row_count)]
        connection.executemany(
            "INSERT INTO lex_normative_ready_facts VALUES (?, 'fixture-family', ?, NULL, "
            "'active', 'exact', 'ready', '[]')",
            [(f"fact-{index:03d}", dates[index]) for index in range(row_count)],
        )
        connection.executemany(
            "INSERT INTO lex_rule_thresholds VALUES (?, ?, 'income', '<=', '1.0', "
            "NULL, 'ratio', 'fixture')",
            [(f"threshold-{index:03d}", f"fact-{index:03d}") for index in range(row_count)],
        )
        connection.executemany(
            "INSERT INTO lex_amendments VALUES (?, ?, ?, TRUE, 'controlled_fixture', ?, "
            "'old text', 'new text', ?, 0.9, '{}')",
            [
                (
                    f"amendment-{index:03d}",
                    f"amending-doc-{index:03d}",
                    f"amended-doc-{index:03d}",
                    f"anchor-{index:03d}",
                    dates[index],
                )
                for index in range(row_count)
            ],
        )
        connection.executemany(
            "INSERT INTO lex_reference_edges VALUES (?, ?, 'fixture-source-family', ?, ?, "
            "'fixture-target-family', 'fixture-reestr', ?, 'law', '2020-01-01', 'active', ?, "
            "'cites', 'controlled_fixture', 0.9, 'resolved', 7, '{}')",
            [
                (
                    f"reference-{index:03d}",
                    f"source-doc-{index:03d}",
                    f"source-anchor-{index:03d}",
                    f"target-doc-{index:03d}",
                    f"number-{index:03d}",
                    f"target-anchor-{index:03d}",
                )
                for index in range(row_count)
            ],
        )

    return snapshot_root, catalog_path, skg_path, l3_path


def test_full_kref_build_matches_source_bound_materialized_skg_counterpart(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compare real PreparedSKGRead output and the complete materialized build."""
    import asyncio
    from collections import Counter
    from contextlib import contextmanager
    from datetime import UTC, datetime

    from polisyos.data_forge.domains.academic.knowledge import skg_query
    from polisyos.data_forge.domains.academic.knowledge.skg_query import (
        _preflight_causal_claim_results_v2,
        iter_causal_claim_results_v2,
    )
    from polisyos.data_forge.read_api.academic import PreparedSKGCredalSourceRows
    from polisyos.pdc._impl.world_model_record import (
        SkgCausalPriorRef,
        WorldModelRecord,
        world_model_record_content_hash,
    )
    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.substrate_registry import run_catalog_source_awaitable

    root = tmp_path.resolve()
    row_count = 257
    snapshot_root, catalog_path, skg_path, _l3_path = _seed_n7_full_owner_source_fixture(
        root, row_count=row_count
    )
    source = _selected_n4_catalog_source(root, snapshot_root)
    fixture_world = _phase5_l6_candidate_world_model_record()
    world_fields = fixture_world.model_dump(mode="python")
    world_fields["skg_causal_prior_ref"] = SkgCausalPriorRef(
        skg_snapshot_ref=f"duckdb://{skg_path.resolve()}#v7",
        skg_version_id="7",
        source_data_snapshot_id="n7-controlled-source-fixture",
    )
    world_draft = WorldModelRecord.model_construct(**world_fields)
    world_hash = world_model_record_content_hash(world_draft)
    world_fields["content_hash"] = world_hash
    world_fields["world_model_record_id"] = (
        f"world_model_record_{world_hash.removeprefix('sha256:')[:16]}"
    )
    world = WorldModelRecord.model_validate(world_fields)

    original_prepared_l2_source = owner._prepared_l2_source

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 20, 12, 0, tzinfo=tz or UTC)

    monkeypatch.setattr(owner, "datetime", FixedDateTime)
    monkeypatch.setattr(skg_query, "datetime", FixedDateTime)
    l6_edge = CredalReferenceEdge(
        modality="L6_KNOB_OPERATOR",
        edge_id="fixture-knob",
        status="incomplete",
        admissible_completions=(
            AdmissibleCompletion("may_exist", {"value": 1}, "fixture_unresolved"),
        ),
        provenance={"owner": "L6", "source": "controlled-fixture"},
    ).with_content_hash()
    monkeypatch.setattr(owner, "_iter_l6_edges", lambda *_args, **_kwargs: (l6_edge,))

    with original_prepared_l2_source(root, world) as selected:
        assert selected is not None
        source_profile = selected.profile
        assert selected.prepared_read.matches_path(skg_path)
        assert selected.prepared_read.source_generation_matches()
        with duckdb.connect(str(skg_path), read_only=True) as connection:
            query_basis = skg_query._CREDAL_SOURCE_QUERY_BASIS
            for query_id, statement in query_basis.items():
                if query_id != "synthetic_values":
                    connection.execute(f"EXPLAIN {statement}").fetchall()
            _preflight_causal_claim_results_v2(connection)
            materialized_rows = PreparedSKGCredalSourceRows(
                source_snapshot_ref=selected.profile.source_snapshot_ref,
                source_snapshot_sha256=selected.profile.source_snapshot_sha256,
                version_id=int(connection.execute(query_basis["version"]).fetchone()[0]),
                variables=tuple(
                    skg_query._CredalVariableRow(*row)
                    for row in connection.execute(query_basis["variables"]).fetchall()
                ),
                variable_synonyms=tuple(
                    skg_query._CredalSynonymRow(*row)
                    for row in connection.execute(query_basis["variable_synonyms"]).fetchall()
                ),
                causal_edges=tuple(
                    skg_query._CredalCausalEdgeRow(*row)
                    for row in connection.execute(query_basis["causal_edges"]).fetchall()
                ),
                family_edges=tuple(
                    skg_query._CredalFamilyEdgeRow(*row)
                    for row in connection.execute(query_basis["family_edges"]).fetchall()
                ),
                moderation_edges=tuple(
                    skg_query._CredalModerationRow(*row)
                    for row in connection.execute(query_basis["moderation_edges"]).fetchall()
                ),
                contested_edges=tuple(
                    skg_query._CredalContestedEdgeRow(*row)
                    for row in connection.execute(query_basis["contested_edges"]).fetchall()
                ),
                causal_claim_results=tuple(iter_causal_claim_results_v2(connection)),
                synthetic_column_present=(
                    connection.execute(query_basis["synthetic_column"]).fetchone() is not None
                ),
                synthetic_values=tuple(
                    row[0] for row in connection.execute(query_basis["synthetic_values"]).fetchall()
                ),
            )
        assert selected.prepared_read.source_generation_matches()
        assert materialized_rows.source_snapshot_ref == source_profile.source_snapshot_ref
        assert materialized_rows.source_snapshot_sha256 == source_profile.source_snapshot_sha256
        assert materialized_rows.version_id == 7
    assert len(materialized_rows.variables) == row_count
    assert len(materialized_rows.variable_synonyms) == row_count
    assert len(materialized_rows.causal_edges) == row_count
    assert len(materialized_rows.family_edges) == row_count
    assert len(materialized_rows.moderation_edges) == row_count
    assert len(materialized_rows.contested_edges) == row_count
    assert len(materialized_rows.causal_claim_results) == row_count
    assert materialized_rows.synthetic_column_present is True
    assert len(materialized_rows.synthetic_values) == row_count
    expected_indexes = range(row_count)
    assert {row.canonical_name for row in materialized_rows.variables} == {
        f"variable-{index:03d}" for index in expected_indexes
    }
    assert {row.synonym for row in materialized_rows.variable_synonyms} == {
        f"synonym-{index:03d}" for index in expected_indexes
    }
    assert {row.edge_id for row in materialized_rows.causal_edges} == {
        f"causal-{index:03d}" for index in expected_indexes
    }
    assert {row.family_edge_id for row in materialized_rows.family_edges} == {
        f"family-edge-{index:03d}" for index in expected_indexes
    }
    assert {row.moderation_id for row in materialized_rows.moderation_edges} == {
        f"moderation-{index:03d}" for index in expected_indexes
    }
    assert {row.contested_edge_id for row in materialized_rows.contested_edges} == {
        f"causal-{index:03d}" for index in expected_indexes
    }
    assert {row.id for row in materialized_rows.causal_claim_results} == {
        f"claim-{index:03d}" for index in expected_indexes
    }
    assert Counter(materialized_rows.synthetic_values) == Counter({False: row_count - 1, True: 1})
    assert materialized_rows.synthetic_values[-1] is True

    class RowView:
        def __init__(self, rows: PreparedSKGCredalSourceRows) -> None:
            self.source_rows = rows
            self.source_snapshot_ref = rows.source_snapshot_ref
            self.source_snapshot_sha256 = rows.source_snapshot_sha256
            self.version_id = rows.version_id

        def iter_variables(self) -> Iterator[object]:
            return iter(self.source_rows.variables)

        def iter_variable_synonyms(self) -> Iterator[object]:
            return iter(self.source_rows.variable_synonyms)

        def iter_causal_edges(self) -> Iterator[object]:
            return iter(self.source_rows.causal_edges)

        def iter_family_edges(self) -> Iterator[object]:
            return iter(self.source_rows.family_edges)

        def iter_moderation_edges(self) -> Iterator[object]:
            return iter(self.source_rows.moderation_edges)

        def iter_contested_edges(self) -> Iterator[object]:
            return iter(self.source_rows.contested_edges)

        def iter_causal_claim_results(self) -> Iterator[object]:
            return iter(self.source_rows.causal_claim_results)

        def iter_synthetic_values(self) -> Iterator[bool | None]:
            return iter(self.source_rows.synthetic_values)

    class MaterializedRead:
        def __init__(self, rows: PreparedSKGCredalSourceRows) -> None:
            self.rows = rows

        def _prepare_credal_source_stream(self) -> RowView:
            return RowView(self.rows)

    @contextmanager
    def materialized_source(_root: Path, _world: object) -> Iterator[object]:
        yield owner._PreparedL2Source(
            prepared_read=MaterializedRead(materialized_rows),
            profile=source_profile,
            version=str(materialized_rows.version_id),
        )

    def build(*, materialized: bool = False) -> CredalReference:
        monkeypatch.setattr(
            owner,
            "_prepared_l2_source",
            materialized_source if materialized else original_prepared_l2_source,
        )

        async def build_async() -> CredalReference:
            return owner.build_credal_reference(
                root,
                as_of="2026-10-11",
                world_model_record=world,
            )

        return asyncio.run(run_catalog_source_awaitable(source, build_async()))

    streamed = build()

    def edge_ids(modality: str) -> set[str]:
        return {
            edge.edge_id for edge in streamed.essential_edges.values() if edge.modality == modality
        }

    def expected_ids(prefix: str) -> set[str]:
        return {f"{prefix}-{index:03d}" for index in expected_indexes}

    assert edge_ids("L2_CANONICAL_VARIABLE") == expected_ids("variable")
    assert edge_ids("L2_VARIABLE_ALIGNMENT") == {
        f"synonym-{index:03d}->variable-{index:03d}" for index in expected_indexes
    }
    assert edge_ids("L2_DATA_FORGE_VARIABLE_ALIGNMENT") == {
        f"dataset-{index:03d}:raw-{index:03d}->variable-{index:03d}" for index in expected_indexes
    }
    for modality, prefix in (
        ("L2_CAUSAL_EDGE", "causal"),
        ("L2_FAMILY_EDGE", "family-edge"),
        ("L2_MODERATION_EDGE", "moderation"),
        ("L2_CAUSAL_CLAIM", "claim"),
        ("L2_CONTESTED_EDGE", "causal"),
        ("L3_RULE_THRESHOLD", "threshold"),
        ("L3_AMENDMENT", "amendment"),
        ("L3_REFERENCE_EDGE", "reference"),
    ):
        assert edge_ids(modality) == expected_ids(prefix), modality

    materialized = build(materialized=True)
    assert streamed == materialized
    assert streamed.reference_hash == materialized.reference_hash
    assert streamed.component_versions == materialized.component_versions
    assert streamed.data_forge_catalog_source_profile == (
        materialized.data_forge_catalog_source_profile
    )
    streamed_l2_profile = owner.credal_reference_l2_source_profile(streamed)
    materialized_l2_profile = owner.credal_reference_l2_source_profile(materialized)
    assert streamed_l2_profile == materialized_l2_profile
    streamed_payloads = {key: edge.to_payload() for key, edge in streamed.essential_edges.items()}
    materialized_payloads = {
        key: edge.to_payload() for key, edge in materialized.essential_edges.items()
    }
    assert streamed_payloads == materialized_payloads
    assert Counter(
        (edge.modality, edge.status) for edge in streamed.essential_edges.values()
    ) == Counter((edge.modality, edge.status) for edge in materialized.essential_edges.values())
    modality_counts = Counter(edge.modality for edge in streamed.essential_edges.values())
    for modality in (
        "L2_CANONICAL_VARIABLE",
        "L2_VARIABLE_ALIGNMENT",
        "L2_DATA_FORGE_VARIABLE_ALIGNMENT",
        "L2_CAUSAL_EDGE",
        "L2_FAMILY_EDGE",
        "L2_MODERATION_EDGE",
        "L2_CAUSAL_CLAIM",
        "L2_CONTESTED_EDGE",
        "L3_RULE_THRESHOLD",
        "L3_AMENDMENT",
        "L3_REFERENCE_EDGE",
    ):
        assert modality_counts[modality] == row_count, modality
    assert {edge.status for edge in streamed.essential_edges.values()} >= {
        "confirmed",
        "contested",
        "incomplete",
    }
    assert all(
        edge.provenance.get("synthetic") is True
        for edge in streamed.essential_edges.values()
        if edge.modality.startswith("L2_")
    )
    assert streamed.component_versions["L2_SOURCE_PROFILE"] == source_profile.content_hash
    catalog_profile = streamed.data_forge_catalog_source_profile
    assert catalog_profile is not None
    assert streamed.component_versions["DATA_FORGE_CATALOG_SOURCE_PROFILE"] == (
        catalog_profile.content_hash
    )

    with duckdb.connect(str(catalog_path)) as connection:
        connection.execute("DELETE FROM ds_variable_alignments WHERE dataset_id = 'dataset-256'")
    after_catalog_tail_removal = build()
    assert after_catalog_tail_removal.reference_hash != streamed.reference_hash
    assert after_catalog_tail_removal.data_forge_catalog_source_profile is not None
    assert after_catalog_tail_removal.data_forge_catalog_source_profile.alignment_row_count == 256
    assert (
        after_catalog_tail_removal.data_forge_catalog_source_profile.alignment_rows_sha256
        != catalog_profile.alignment_rows_sha256
    )

    with duckdb.connect(str(skg_path)) as connection:
        connection.execute("DELETE FROM ac_skg_variables WHERE canonical_name = 'variable-256'")
    after_skg_tail_removal = build()
    assert after_skg_tail_removal.reference_hash != after_catalog_tail_removal.reference_hash
    after_skg_profile = owner.credal_reference_l2_source_profile(after_skg_tail_removal)
    before_skg_profile = owner.credal_reference_l2_source_profile(streamed)
    assert after_skg_profile is not None and before_skg_profile is not None
    assert after_skg_profile.source_snapshot_sha256 != (before_skg_profile.source_snapshot_sha256)
    assert after_skg_tail_removal.component_versions != streamed.component_versions


def test_selected_catalog_replacement_between_profile_and_edge_pass_fails_closed(
    tmp_path: Path,
) -> None:
    """A selected catalog replacement after profiling cannot change the edge pass."""
    import asyncio
    import os

    from polisyos.runtime.quality import credal_reference as owner
    from polisyos.runtime.quality.substrate_registry import run_catalog_source_awaitable

    root = tmp_path.resolve()
    snapshot_root = root / "snapshots" / "catalog-generation-change"
    catalog_path = snapshot_root / "datasets" / "graph" / "dataset_catalog.duckdb"
    replacement_path = catalog_path.with_name("catalog-replacement.duckdb")
    catalog_path.parent.mkdir(parents=True)

    def write_catalog(path: Path, rows: tuple[tuple[object, ...], ...]) -> None:
        with duckdb.connect(str(path)) as connection:
            connection.execute(
                "CREATE TABLE ds_variable_alignments ("
                "dataset_id VARCHAR, raw_variable VARCHAR, canonical_var VARCHAR, "
                "method VARCHAR, confidence FLOAT, evidence VARCHAR, "
                "is_proxy BOOLEAN, proxy_penalty FLOAT)"
            )
            if rows:
                connection.executemany(
                    "INSERT INTO ds_variable_alignments VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )

    write_catalog(
        catalog_path,
        (
            ("a", "tax", "policy.tax_rate", "a", 0.91, "A", False, 0.0),
            ("z", "tax2", "policy.tax_rate", "z", 0.92, "Z", False, 0.0),
        ),
    )
    write_catalog(
        replacement_path,
        (("replacement", "income", "policy.income", "new", 0.95, "N", False, 0.0),),
    )
    source = _selected_n4_catalog_source(root, snapshot_root)

    async def exercise_generation_boundary() -> None:
        with owner._read_data_forge_catalog_source(root) as selected:
            assert selected is not None
            first_profile = selected.profile
            assert first_profile.alignment_row_count == 2
            os.replace(replacement_path, catalog_path)
            with pytest.raises(
                ValueError,
                match="dataset_registry_kref_source_generation_changed",
            ):
                tuple(selected.iter_rows())

        with owner._read_data_forge_catalog_source(root) as fresh:
            assert fresh is not None
            assert fresh.profile.alignment_row_count == 1
            assert fresh.profile.alignment_rows_sha256 != (first_profile.alignment_rows_sha256)
            assert tuple(fresh.iter_rows()) == (
                (
                    "replacement",
                    "income",
                    "policy.income",
                    "new",
                    0.95,
                    "N",
                    False,
                    0.0,
                ),
            )

    asyncio.run(run_catalog_source_awaitable(source, exercise_generation_boundary()))


def test_selected_owner_payload_readers_batch_and_refuse_payload_fetchall(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every selected owner cursor batches its nonempty full-source denominator."""
    from collections import Counter, defaultdict

    from polisyos.data_forge.domains.academic.knowledge import skg_query
    from polisyos.data_forge.domains.catalog.knowledge import (
        registry as catalog_registry,
    )
    from polisyos.runtime.quality import credal_reference as credal_reference_module

    row_count = 257
    root = tmp_path.resolve()
    _snapshot_root, catalog_path, skg_path, _l3_path = _seed_n7_full_owner_source_fixture(
        root, row_count=row_count
    )

    class QueryTracker:
        def __init__(self) -> None:
            self.read_batches: dict[str, list[list[int]]] = defaultdict(list)
            self.payload_fetchall: list[str] = []
            self.unclassified_fetchmany: list[tuple[str, int, int]] = []
            self.explain_fetchall_count = 0

        @staticmethod
        def owner_for(statement: str) -> str | None:
            normalized = " ".join(statement.casefold().split())
            if normalized.startswith("explain "):
                return None
            if "ds_variable_alignments" in normalized:
                return "catalog.alignment"
            if "ac_causal_claims_raw" in normalized:
                return "skg.synthetic_values"
            if "from ac_causal_claims c left join ac_works w" in normalized:
                return "skg.causal_claim_results"
            for table, route in (
                ("ac_skg_variables", "skg.variables"),
                ("ac_skg_variable_synonyms", "skg.variable_synonyms"),
                ("ac_skg_edges", "skg.causal_edges"),
                ("ac_skg_family_edges", "skg.family_edges"),
                ("ac_skg_moderation_edges", "skg.moderation_edges"),
                ("ac_skg_contested_edges", "skg.contested_edges"),
            ):
                if f"from main.{table}" in normalized:
                    return route
            if "lex_rule_thresholds" in normalized:
                if "select t.threshold_id, f.doc_family_id" in normalized:
                    return "l3.threshold_metadata"
                return "l3.threshold_rows"
            if "lex_amendments" in normalized:
                if "select amendment_id, amended_doc_id" in normalized:
                    return "l3.amendment_metadata"
                return "l3.amendment_rows"
            if "lex_reference_edges" in normalized:
                return "l3.reference_edges"
            return None

        def begin_read(self, statement: str) -> tuple[str | None, list[int] | None]:
            route = self.owner_for(statement)
            if route is None:
                return None, None
            batches: list[int] = []
            self.read_batches[route].append(batches)
            return route, batches

    tracker = QueryTracker()
    real_duckdb = duckdb

    class GuardedConnection:
        def __init__(self, connection: object) -> None:
            self._connection = connection
            self._statement = ""
            self._result = None
            self._route: str | None = None
            self._batches: list[int] | None = None

        def execute(self, statement: str, *args: object, **kwargs: object) -> GuardedConnection:
            self._statement = statement
            self._route, self._batches = tracker.begin_read(statement)
            self._result = self._connection.execute(statement, *args, **kwargs)
            return self

        def fetchmany(self, size: int = 1):
            if size > 256:
                raise AssertionError("owner_fetchmany_exceeded_batch_cap")
            rows = self._result.fetchmany(size)
            if self._batches is not None:
                self._batches.append(len(rows))
                if len(rows) > size:
                    raise AssertionError("owner_fetchmany_exceeded_requested_batch")
            elif not self._statement.lstrip().casefold().startswith("explain"):
                tracker.unclassified_fetchmany.append((self._statement, size, len(rows)))
            return rows

        def fetchall(self):
            if self._statement.lstrip().casefold().startswith("explain"):
                tracker.explain_fetchall_count += 1
                return self._result.fetchall()
            tracker.payload_fetchall.append(self._statement)
            raise AssertionError("owner_payload_fetchall_forbidden")

        def fetchone(self):
            return self._result.fetchone()

        def __getattr__(self, name: str) -> object:
            return getattr(self._connection, name)

    class DuckDBSpy:
        Error = real_duckdb.Error

        def connect(self, *args: object, **kwargs: object) -> GuardedConnection:
            return GuardedConnection(real_duckdb.connect(*args, **kwargs))

    spy_module = DuckDBSpy()
    monkeypatch.setattr(catalog_registry, "duckdb", spy_module)
    monkeypatch.setattr(skg_query, "duckdb", spy_module)
    monkeypatch.setattr(credal_reference_module, "duckdb", spy_module)

    with catalog_registry.DatasetRegistry(catalog_path)._prepare_kref_alignment_read() as reader:
        catalog_rows = tuple(reader.iter_rows())
    prepared_read = skg_query.SKGQuery.prepare_read(
        db_path=skg_path,
        index_dir=skg_path.parent / "index",
    )
    try:
        rows = prepared_read.read_credal_source_rows()
    finally:
        prepared_read.close()
    l3_edges = tuple(credal_reference_module._iter_l3_edges(root, as_of="2026-10-20"))

    assert len(catalog_rows) == row_count
    for stream in (
        rows.variables,
        rows.variable_synonyms,
        rows.causal_edges,
        rows.family_edges,
        rows.moderation_edges,
        rows.contested_edges,
        rows.causal_claim_results,
        rows.synthetic_values,
    ):
        assert len(stream) == row_count
    assert len(l3_edges) == row_count * 3
    l3_counts = Counter(edge.modality for edge in l3_edges)
    assert l3_counts == {
        "L3_RULE_THRESHOLD": row_count,
        "L3_AMENDMENT": row_count,
        "L3_REFERENCE_EDGE": row_count,
    }

    expected_routes = {
        "catalog.alignment",
        "skg.variables",
        "skg.variable_synonyms",
        "skg.causal_edges",
        "skg.family_edges",
        "skg.moderation_edges",
        "skg.contested_edges",
        "skg.causal_claim_results",
        "skg.synthetic_values",
        "l3.threshold_metadata",
        "l3.threshold_rows",
        "l3.amendment_metadata",
        "l3.amendment_rows",
        "l3.reference_edges",
    }
    assert set(tracker.read_batches) == expected_routes
    for route in expected_routes:
        reads = tracker.read_batches[route]
        assert reads, route
        for batches in reads:
            nonempty_batches = [size for size in batches if size]
            assert sum(nonempty_batches) == row_count, route
            assert 256 in nonempty_batches, route
            assert max(nonempty_batches) <= 256, route
    assert tracker.payload_fetchall == []
    assert tracker.unclassified_fetchmany == []
    assert tracker.explain_fetchall_count > 0
