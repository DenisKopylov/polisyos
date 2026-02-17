from __future__ import annotations

from polisyos.lex.batch.structurer import extract_provisions


def test_extract_provisions_fallback_chunks_have_unique_anchors() -> None:
    # No article headers -> fallback chunking path.
    text = ("Тестовий суцільний текст без структури.\n" * 300).strip()

    spans = extract_provisions(
        text,
        enable_paragraphs=True,
        fallback_chunk_chars=600,
        fallback_chunk_overlap=100,
    )

    assert len(spans) > 1
    anchors = [s.anchor_path for s in spans]
    assert len(set(anchors)) == len(anchors)
    assert all(s.kind == "full_text" for s in spans)
    assert all(s.is_fallback_chunk for s in spans)
    assert all(s.parent_anchor == "full" for s in spans)
    assert all(s.token_est > 0 for s in spans)
    assert all(bool(s.text_hash) for s in spans)
