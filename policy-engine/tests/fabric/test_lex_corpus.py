from __future__ import annotations

import json
import re
from pathlib import Path

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.io.db import SimulationDB
from polisyos.fabric.world.materialize import materialize_world_duckdb_from_fact_log
from polisyos.lex.api import (
    build_legal_structure,
    build_version_index,
    ingest_legal_doc_bytes,
    resolve_active_version,
)
from polisyos.lex.corpus.index import load_provision_index
from polisyos.lex.types import LegalDocSource


def _load_json_artifact(cas: FileSystemCAS, artifact_id: str) -> dict:
    payload = json.loads(cas.get_bytes(ArtifactID.model_validate(artifact_id)))
    assert isinstance(payload, dict)
    return payload


def _ua_source(
    *,
    official_id: str,
    effective_from: str | None = None,
    effective_to: str | None = None,
) -> LegalDocSource:
    return LegalDocSource(
        official_id=official_id,
        canonical_url=None,
        license="public",
        jurisdiction="UA",
        language="uk",
        source_type="legal_manual_seed",
        source_url="https://zakon.example/act",
        published_at_iso=effective_from,
        effective_from_iso=effective_from,
        effective_to_iso=effective_to,
    )


def test_lex_structure_fragment_ids_are_deterministic(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")

    text = """
ЗАКОН УКРАЇНИ

Стаття 1. Загальні положення
1) Перший пункт.

Стаття 2. Інше
1. Інший пункт.
""".strip()

    ingest = ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=_ua_source(official_id="UA:LAW-DET"),
        raw_bytes=text.encode("utf-8"),
        mime="text/plain",
    )

    result_1 = build_legal_structure(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
    )
    result_2 = build_legal_structure(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
    )

    assert result_1.fragment_ids == result_2.fragment_ids


def test_lex_structure_offsets_and_anchor_paths_are_valid(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")

    text = """
ЗАКОН УКРАЇНИ

Стаття 1. Загальні положення
Частина 1 Додаткова частина
1) Перший пункт.
a) Підпункт.

Стаття 2. Інше
1. Інший пункт.
""".strip()

    ingest = ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=_ua_source(official_id="UA:LAW-OFFSETS"),
        raw_bytes=text.encode("utf-8"),
        mime="text/plain",
    )
    structured = build_legal_structure(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
    )

    normalized_payload = _load_json_artifact(cas, str(ingest.normalized_ref))
    normalized_text = normalized_payload["text"]
    index = load_provision_index(cas, structured.provision_index_artifact_id)

    text_len = len(normalized_text)
    patterns = {
        "article": re.compile(r"^art:\d+$"),
        "part": re.compile(r"^art:\d+/part:\d+$"),
        "point": re.compile(r"^art:\d+(/part:\d+)?/pt:\d+$"),
        "subpoint": re.compile(r"^art:\d+(/part:\d+)?/pt:\d+/sub:[a-zа-я]$", re.IGNORECASE),
        "paragraph": re.compile(
            r"^art:\d+(/part:\d+)?(/pt:\d+)?(/sub:[a-zа-я])?/para:\d+$",
            re.IGNORECASE,
        ),
    }

    for provision in index.provisions:
        assert 0 <= provision.offset_start < provision.offset_end <= text_len
        pattern = patterns[provision.kind]
        assert pattern.fullmatch(provision.anchor_path), provision.anchor_path


def test_lex_resolve_active_version_is_deterministic(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")

    source_v1 = _ua_source(
        official_id="UA:LAW-VERSION",
        effective_from="2024-01-01",
        effective_to="2024-12-31",
    )
    source_v2 = _ua_source(
        official_id="UA:LAW-VERSION",
        effective_from="2025-01-01",
        effective_to=None,
    )

    v1 = ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source_v1,
        raw_bytes=b"version 1",
        mime="text/plain",
        options=None,
    )
    v2 = ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source_v2,
        raw_bytes=b"version 2",
        mime="text/plain",
        options=None,
    )

    build_version_index(
        cas=cas,
        fact_log_root=tmp_path,
        doc_source_id=v1.doc_source_id,
    )

    active_2024 = resolve_active_version(
        cas=cas,
        doc_source_id=v1.doc_source_id,
        as_of_iso="2024-06-01",
    )
    active_2025 = resolve_active_version(
        cas=cas,
        doc_source_id=v1.doc_source_id,
        as_of_iso="2025-06-01",
    )
    active_2025_repeat = resolve_active_version(
        cas=cas,
        doc_source_id=v1.doc_source_id,
        as_of_iso="2025-06-01",
    )

    assert active_2024.selected_doc_version_id == v1.doc_version_id
    assert active_2025.selected_doc_version_id == v2.doc_version_id
    assert active_2025.selected_doc_version_id == active_2025_repeat.selected_doc_version_id


def test_lex_resolve_active_version_does_not_fallback_to_published_at_only(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")

    source = LegalDocSource(
        official_id="UA:LAW-PUBLISHED-ONLY",
        canonical_url=None,
        license="public",
        jurisdiction="UA",
        language="uk",
        source_type="legal_manual_seed",
        source_url="https://zakon.example/act",
        published_at_iso="2024-01-01",
        effective_from_iso=None,
        effective_to_iso=None,
    )

    ingest = ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=source,
        raw_bytes=b"published-only version",
        mime="text/plain",
        options=None,
    )

    build_version_index(
        cas=cas,
        fact_log_root=tmp_path,
        doc_source_id=ingest.doc_source_id,
    )

    resolved = resolve_active_version(
        cas=cas,
        doc_source_id=ingest.doc_source_id,
        as_of_iso="2024-06-01",
    )

    assert resolved.selected_doc_version_id is None
    assert "no_resolved_temporal_candidate" in resolved.explanation


def test_lex_phase16_end_to_end_with_duckdb(tmp_path: Path) -> None:
    cas = FileSystemCAS(tmp_path / "cas")
    db = SimulationDB(db_path=str(tmp_path / "sim.duckdb"))

    text = """
ЗАКОН УКРАЇНИ

Стаття 1. Загальні положення
1) Перший пункт.

Стаття 2. Інше
1. Інший пункт.
""".strip()

    ingest = ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=tmp_path,
        source=_ua_source(official_id="UA:LAW-INTEG", effective_from="2024-01-01"),
        raw_bytes=text.encode("utf-8"),
        mime="text/plain",
    )
    structured = build_legal_structure(
        cas=cas,
        fact_log_root=tmp_path,
        doc_meta_artifact_id=ingest.doc_meta_artifact_id,
    )
    build_version_index(
        cas=cas,
        fact_log_root=tmp_path,
        doc_source_id=ingest.doc_source_id,
    )

    materialize_world_duckdb_from_fact_log(tmp_path, db, cas)

    row = db.conn.execute(
        "SELECT COUNT(*) FROM world.doc_versions WHERE doc_version_id = ?",
        [ingest.doc_version_id],
    ).fetchone()
    assert row is not None
    assert row[0] == 1

    fragments_row = db.conn.execute(
        """
        SELECT COUNT(*)
        FROM world.doc_fragments
        WHERE doc_version_id = ?
          AND (anchor_kind = 'article' OR props_json LIKE '%"lex_kind":"article"%')
        """,
        [ingest.doc_version_id],
    ).fetchone()
    assert fragments_row is not None
    assert fragments_row[0] > 0

    edges_row = db.conn.execute(
        """
        SELECT COUNT(*)
        FROM world.world_edges
        WHERE kind = 'doc.has_fragment'
          AND src_id = ?
        """,
        [ingest.doc_version_id],
    ).fetchone()
    assert edges_row is not None
    assert edges_row[0] >= len(structured.fragment_ids)

    event_row = db.conn.execute(
        """
        SELECT COUNT(*)
        FROM world.world_events
        WHERE activity_id = 'prov.activity.lex_corpus.structure'
        """
    ).fetchone()
    assert event_row is not None
    assert event_row[0] >= 1

    props_row = db.conn.execute(
        "SELECT props_ref FROM world.world_nodes WHERE node_id = ?",
        [ingest.doc_source_id],
    ).fetchone()
    assert props_row is not None
    assert props_row[0] is not None
