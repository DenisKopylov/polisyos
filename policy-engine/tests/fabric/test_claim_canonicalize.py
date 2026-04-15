from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from polisyos.fabric.claims.backends.regex_numeric_v1 import extract
from polisyos.fabric.claims.canonicalize import (
    canonicalize_id,
    detect_canonical_id_collisions,
    parse_decimal_value_text,
)
from polisyos.fabric.claims.types import ChunkContext, ClaimExtractOptions
from polisyos.ir.world.doc import DocMeta


def _doc_meta() -> DocMeta:
    return DocMeta(
        doc_source_id="doc_source",
        doc_version_id="doc_version",
        canonical_url="https://example.com/doc",
        retrieved_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        mime="text/plain",
        license="cc-by",
        raw_ref="sha256:" + ("0" * 64),
    )


def test_canonicalize_id_preserves_unicode_losslessly() -> None:
    canonical = canonicalize_id("Київ")
    assert canonical == "u043au0438u0457u0432"
    assert canonicalize_id(canonical) == canonical


def test_canonicalize_id_supports_optional_transliteration() -> None:
    assert canonicalize_id("Käse Straße", transliterate=True) == "kase_strasse"
    assert canonicalize_id("ＡBC") == "abc"


def test_detect_canonical_id_collisions_in_transliteration_mode() -> None:
    collisions = detect_canonical_id_collisions(
        ["cafe", "café", "cafeteria"],
        transliterate=True,
    )
    assert collisions == {"cafe": ("cafe", "café")}


def test_parse_decimal_value_text_supports_locale_and_scientific_notation() -> None:
    assert parse_decimal_value_text("1.000,50") == Decimal("1000.50")
    assert parse_decimal_value_text("1,23e3") == Decimal("1.23E+3")


def test_regex_numeric_backend_extracts_locale_and_scientific_numbers() -> None:
    normalized_text = "GDP reached 1,23e3 usd while inflation hit 1.000,50 %."
    context = ChunkContext(
        fragment_id="fragment_1",
        doc_version_id="doc_version",
        offset_start=0,
        offset_end=len(normalized_text),
        text_preview=normalized_text,
    )

    claims = extract(
        ctx=context,
        meta=_doc_meta(),
        normalized_text=normalized_text,
        options=ClaimExtractOptions(),
    )

    assert [claim.value_text for claim in claims] == ["1,23e3", "1.000,50"]
    assert [claim.value_decimal for claim in claims] == [
        Decimal("1.23E+3"),
        Decimal("1000.50"),
    ]
    assert [claim.unit_id for claim in claims] == ["usd", "percent"]
