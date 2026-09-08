"""Exercise retained source identity through production queries, CAS and replay."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from polisyos.core import artifacts
from polisyos.data_forge.read_api import academic as bridge


@pytest.fixture
def source(tmp_path: Path) -> tuple[Path, bridge.SourceIdentitySelection]:
    path = tmp_path / "source.duckdb"
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE ac_skg_simulation_parameters AS SELECT 'n1' numeric_id, "
        "'W1' openalex_id, '[\"c1\"]' linked_claim_ids_json, "
        "'[\"e1\"]' linked_edges_json, 2.0 point_estimate, "
        "'[1.0,3.0]' confidence_interval_json, 'percent' unit"
    )
    con.execute(
        "CREATE TABLE ac_causal_claims AS SELECT 'c1' id, 'W1' work_id, "
        "'tax' cause, 'employment' effect, 'positive' direction"
    )
    con.execute(
        "CREATE TABLE ac_skg_edge_evidence AS SELECT 'c1' claim_id, 'W1' openalex_id, "
        "'e1' edge_id, 1 skg_version, 'tax' src, 'employment' dst, 'positive' direction"
    )
    con.execute(
        "CREATE TABLE ac_skg_edges AS SELECT 'e1' edge_id, 'tax' src, "
        "'employment' dst, 'positive' direction"
    )
    con.execute(
        "CREATE TABLE ac_skg_articles AS SELECT 'W1' openalex_id, 1 skg_version, "
        "'Candidate extraction' extraction_json"
    )
    con.execute("CREATE TABLE ac_works AS SELECT 'W1' id, 'Retained text' abstract")
    con.execute("CREATE TABLE ac_skg_versions AS SELECT 1 version_id")
    con.close()
    return path, bridge.SourceIdentitySelection(
        numeric_id="n1",
        claim_id="c1",
        edge_id="e1",
        work_id="W1",
        skg_version=1,
    )


def _owner(path: Path) -> bridge.SourceSnapshot:
    return bridge.SourceSnapshot(
        path=path,
        reference=str(path.resolve()),
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
    )


def test_source_identity_is_persisted_replayed_and_keeps_n8_blocked(source, tmp_path):
    path, selection = source
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(
        source=_owner(path),
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    result = bridge.replay_source_identity_bundle(
        ref=ref,
        selection=selection,
        source=_owner(path),
        store=store,
        scratch=tmp_path / "spill",
    )
    assert result.status == "source_reference_identity_recomputed"
    assert result.production_value_eligible is False
    assert result.numeric_semantics == "not_established"
    assert result.source_snapshot_authenticity == "not_established"
    assert result.n8_admission == "blocked"
    assert len(result.rows) == 7
    assert result.rows[0].cells[-1].value == "percent"


@pytest.mark.parametrize(
    "mutation",
    [
        "work",
        "version",
        "edge",
        "linked_claim",
        "direction",
        "malformed",
        "ambiguous",
        "missing",
    ],
)
def test_source_join_mismatch_refuses_even_with_all_identity_markers(source, tmp_path, mutation):
    path, selection = source
    sql = {
        "work": "UPDATE ac_causal_claims SET work_id='W-other'",
        "version": "UPDATE ac_skg_articles SET skg_version=2",
        "edge": "UPDATE ac_skg_edges SET dst='unrelated'",
        "linked_claim": "UPDATE ac_skg_simulation_parameters SET linked_claim_ids_json='[\"other\"]'",
        "direction": "UPDATE ac_causal_claims SET direction='negative'",
        "malformed": "UPDATE ac_skg_simulation_parameters SET linked_claim_ids_json='{}'",
        "ambiguous": "INSERT INTO ac_skg_simulation_parameters SELECT * FROM ac_skg_simulation_parameters",
        "missing": "DELETE FROM ac_skg_versions",
    }[mutation]
    with duckdb.connect(str(path)) as con:
        con.execute(sql)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(
        source=_owner(path),
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    result = bridge.replay_source_identity_bundle(
        ref=ref,
        selection=selection,
        source=_owner(path),
        store=store,
        scratch=tmp_path / "spill",
    )
    assert result.status == "refused"
    assert result.refusal_reasons


def test_replay_requires_current_root_bytes(source, tmp_path):
    path, selection = source
    owner = _owner(path)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(
        source=owner,
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    with duckdb.connect(str(path)) as con:
        con.execute("UPDATE ac_works SET abstract='Substituted bytes'")
    with pytest.raises(ValueError, match="snapshot"):
        bridge.replay_source_identity_bundle(
            ref=ref,
            selection=selection,
            source=owner,
            store=store,
            scratch=tmp_path / "spill",
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "row",
        "row_hash",
        "status",
        "purpose",
        "numeric_semantics",
        "bool_alias",
        "float_alias",
    ],
)
def test_new_valid_cas_object_cannot_substitute_recomputed_identity(source, tmp_path, mutation):
    path, selection = source
    owner = _owner(path)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(
        source=owner,
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    payload = json.loads(store.get_bytes(ref.artifact_id))
    if mutation == "row":
        payload["rows"][0]["cells"][-1]["value"] = "standardized_mean_difference"
    elif mutation == "row_hash":
        payload["rows"][0]["sha256"] = "0" * 64
    elif mutation in {"bool_alias", "float_alias"}:
        payload["rows"][-1]["cells"][0]["value"] = True if mutation == "bool_alias" else 1.0
    else:
        payload[mutation] = "certified"
    forged = store.put_bytes(
        json.dumps(payload).encode(),
        artifacts.ArtifactWriteOptions(
            kind="academic.source_reference_identity",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name="academic.source_reference_identity", version="1.0"),
            producer=artifacts.ProducerInfo(component="candidate", version="1"),
        ),
    )
    with pytest.raises(ValueError):
        bridge.replay_source_identity_bundle(
            ref=forged,
            selection=selection,
            source=owner,
            store=store,
            scratch=tmp_path / "spill",
        )


def test_replay_cannot_choose_subject_from_candidate_bundle(source, tmp_path):
    path, selection = source
    owner = _owner(path)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(
        source=owner,
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    with pytest.raises(ValueError, match="selection"):
        bridge.replay_source_identity_bundle(
            ref=ref,
            source=owner,
            selection=selection.model_copy(update={"claim_id": "other"}),
            store=store,
            scratch=tmp_path / "spill",
        )


@pytest.mark.parametrize(
    ("database_type", "literal", "expected"),
    [
        ("DECIMAL(38,20)", "'1.12345678901234567890'", "1.12345678901234567890"),
        ("TIMESTAMP_NS", "'2026-09-07 01:02:03.123456789'", "2026-09-07 01:02:03.123456789"),
        ("INTEGER[]", "[1,2,NULL]", "[1, 2, NULL]"),
    ],
)
def test_native_database_values_survive_public_producer_and_replay(
    source,
    tmp_path,
    database_type,
    literal,
    expected,
):
    path, selection = source
    with duckdb.connect(str(path)) as con:
        con.execute(f"ALTER TABLE ac_works ADD COLUMN exact_value {database_type}")
        con.execute(f"UPDATE ac_works SET exact_value={literal}")  # noqa: S608 - fixed test literals
    owner = _owner(path)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(
        source=owner,
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    result = bridge.replay_source_identity_bundle(
        ref=ref,
        source=owner,
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    assert result.status == "source_reference_identity_recomputed"
    cell = next(cell for row in result.rows for cell in row.cells if cell.name == "exact_value")
    assert cell.value == expected
    assert cell.database_type == database_type


@pytest.mark.parametrize("kind", ["external_view", "virtual_column"])
def test_snapshot_only_source_refuses_unretained_query_inputs(source, tmp_path, kind):
    path, selection = source
    external = tmp_path / "outside.csv"
    external.write_text("id,abstract\nW1,External text\n")
    with duckdb.connect(str(path)) as con:
        con.execute("DROP TABLE ac_works")
        if kind == "external_view":
            quoted = str(external).replace("'", "''")
            query = f"CREATE VIEW ac_works AS SELECT * FROM read_csv('{quoted}', header=true)"  # noqa: S608
            con.execute(query)
        else:
            con.execute(
                "CREATE TABLE ac_works (id VARCHAR, abstract VARCHAR, "
                "unretained DATE GENERATED ALWAYS AS (current_date()))"
            )
            con.execute("INSERT INTO ac_works(id,abstract) VALUES ('W1','Retained text')")
    owner = _owner(path)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    ref = bridge.produce_source_identity_bundle(
        source=owner,
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    result = bridge.replay_source_identity_bundle(
        ref=ref,
        source=owner,
        selection=selection,
        store=store,
        scratch=tmp_path / "spill",
    )
    assert result.status == "refused"
    assert result.refusal_reasons


def test_snapshot_does_not_ignore_real_uncheckpointed_wal(source, tmp_path):
    path, selection = source
    owner = _owner(path)
    store = artifacts.FileSystemCAS(tmp_path / "cas")
    with duckdb.connect(str(path)) as con:
        con.execute("UPDATE ac_works SET abstract='Only journaled in WAL'")
        assert path.with_name(path.name + ".wal").exists()
        with pytest.raises(ValueError, match="wal_not_bound"):
            bridge.produce_source_identity_bundle(
                source=owner,
                selection=selection,
                store=store,
                scratch=tmp_path / "spill",
            )
