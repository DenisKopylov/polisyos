import polisyos.lex.types as lex_types
from polisyos.lex.types import ActiveVersionResult, ActiveVersionStrategy


def test_lex_types_expose_only_read_side_versioning_contracts() -> None:
    """Runtime callers can configure and receive active-version reads without writer DTOs."""
    strategy = ActiveVersionStrategy(
        version_index_artifact_id="a" * 64,
        include_candidates=True,
    )
    result = ActiveVersionResult(
        doc_source_id="ua:law:123",
        as_of_iso="2026-08-27",
        selected_doc_version_id=None,
        selected_doc_meta_artifact_id=None,
        selection_policy_id="lex.versioning_v1.effective_range_then_published_at",
        used_version_index_artifact_id="a" * 64,
        explanation=["no_resolved_temporal_candidate"],
    )

    assert strategy.version_index_artifact_id == "a" * 64
    assert result.selected_doc_version_id is None
    assert not hasattr(lex_types, "LegalDocSource")
    assert not hasattr(lex_types, "WorldEventRefLike")
