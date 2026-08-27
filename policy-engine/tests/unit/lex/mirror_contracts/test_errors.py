from polisyos.core.errors import ErrorCategory
from polisyos.lex.errors import LexVersioningError


def test_lex_error_carries_policy_error_metadata() -> None:
    """Lex-local failures retain the routing metadata required by runtime consumers."""
    error = LexVersioningError(
        "version index unreadable",
        doc_source_id="ua:law:123",
        doc_version_id="ua:law:123:v2",
        details={"artifact_id": "a" * 64},
    )

    assert error.category is ErrorCategory.FATAL
    assert error.stage == "versioning"
    assert error.doc_source_id == "ua:law:123"
    assert error.doc_version_id == "ua:law:123:v2"
    assert error.to_dict()["details"] == {"artifact_id": "a" * 64}
