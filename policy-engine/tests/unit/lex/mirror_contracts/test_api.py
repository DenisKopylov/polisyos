from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from polisyos.data_forge.errors import LexIndexError as DataForgeIndexError
from polisyos.lex import api
from polisyos.lex.errors import LexIndexError
from polisyos.lex.normpack import assemble_pack, select_sources
from polisyos.lex.types import (
    ActiveVersionResult,
    NormPackBuildRequest,
    SelectedDocVersion,
)


def test_source_selection_uses_lex_active_version_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """NormPack source selection consumes Lex's adapted active-version read result."""
    monkeypatch.setattr(
        select_sources,
        "_load_world_facts",
        lambda _root: pd.DataFrame(columns=select_sources._FACT_COLUMNS),
    )
    monkeypatch.setattr(
        select_sources,
        "load_doc_meta_artifact",
        lambda *_args, **_kwargs: SimpleNamespace(jurisdiction="UA", props={}),
    )
    monkeypatch.setattr(
        api,
        "resolve_active_version",
        lambda **_kwargs: ActiveVersionResult(
            doc_source_id="ua:law:123",
            as_of_iso="2026-08-27",
            selected_doc_version_id="ua:law:123:v2",
            selected_doc_meta_artifact_id="a" * 64,
            selection_policy_id="lex.versioning_v1.effective_range_then_published_at",
            used_version_index_artifact_id="b" * 64,
            explanation=["selected_via=version_index"],
        ),
    )

    selected, warnings = select_sources.select_active_doc_versions(
        cas=object(),  # type: ignore[arg-type]
        fact_log_root=tmp_path,
        request=NormPackBuildRequest(jurisdiction="ua", as_of="2026-08-27"),
        jurisdiction_norm="ua",
        as_of_norm="2026-08-27",
        doc_source_ids=["ua:law:123"],
    )

    assert warnings == []
    assert selected == [
        SelectedDocVersion(
            doc_source_id="ua:law:123",
            doc_version_id="ua:law:123:v2",
            doc_meta_artifact_id="a" * 64,
            selection_policy_id="lex.versioning_v1.effective_range_then_published_at",
            used_version_index_artifact_id="b" * 64,
            explanation=["selected_via=version_index"],
        )
    ]


def test_provision_index_failure_is_translated_at_lex_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Data Forge provision-index error cannot escape from Lex NormPack assembly."""
    selected_doc = SelectedDocVersion(
        doc_source_id="ua:law:123",
        doc_version_id="ua:law:123:v2",
        doc_meta_artifact_id="a" * 64,
        selection_policy_id="lex.versioning_v1.effective_range_then_published_at",
        used_version_index_artifact_id="b" * 64,
        explanation=[],
    )
    monkeypatch.setattr(
        assemble_pack,
        "load_doc_meta",
        lambda *_args, **_kwargs: SimpleNamespace(
            normalized_ref="c" * 64,
            doc_source_id="ua:law:123",
            doc_version_id="ua:law:123:v2",
            props={"lex": {"provision_index_ref": "d" * 64}},
        ),
    )
    monkeypatch.setattr(
        assemble_pack.legal_read_api,
        "load_provision_index",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            DataForgeIndexError("provision index unreadable", doc_source_id="ua:law:123")
        ),
    )

    with pytest.raises(LexIndexError) as raised:
        assemble_pack._select_provisions(
            cas=object(),  # type: ignore[arg-type]
            selected_doc_versions=[selected_doc],
            domain_norm=None,
            max_provisions=None,
        )

    assert raised.value.doc_source_id == "ua:law:123"
    assert raised.value.stage == "index"
