from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from polisyos.ir.model_layer.canon import (
    CanonSpec,
    CanonViolation,
    content_hash,
    from_canonical_bytes,
    to_canonical_bytes,
)
from pydantic import BaseModel, ValidationError

from polisyos.ir.loading.fact_log import Fact, FactProvenance
from polisyos.ir.migrations.base import (
    MigrationSchemaVersionError,
    migrate_artifact,
    register_migration,
)
from polisyos.ir.world.ids import claim_id_from_payload


class _NestedModel(BaseModel):
    value: int
    optional: str | None = None


@dataclass(frozen=True)
class _DataclassEnvelope:
    name: str
    nested: _NestedModel
    optional: str | None = None


def _deep_list(depth: int) -> list[object]:
    root: list[object] = []
    current = root
    for _ in range(depth):
        child: list[object] = []
        current.append(child)
        current = child
    return root


def _deep_dict(depth: int) -> dict[str, object]:
    root: dict[str, object] = {}
    current = root
    for idx in range(depth):
        child: dict[str, object] = {}
        current[f"k{idx}"] = child
        current = child
    return root


def _fact_provenance() -> FactProvenance:
    return FactProvenance(
        source_id="source.test",
        license="cc0",
        raw_hash="sha256:" + "b" * 64,
    )


def test_unknown_canonical_type_is_rejected_on_decode_and_encode() -> None:
    with pytest.raises(CanonViolation, match="Unknown canonical _type"):
        from_canonical_bytes(b'{"_type":"future_datetime","value":"2026"}')

    with pytest.raises(CanonViolation, match="Unknown canonical _type"):
        to_canonical_bytes({"_type": "future_datetime", "value": "2026"})


def test_dataclass_canonicalization_recurses_into_nested_basemodel() -> None:
    payload = _DataclassEnvelope(name="outer", nested=_NestedModel(value=7))

    assert to_canonical_bytes(payload) == b'{"name":"outer","nested":{"value":7}}'
    assert to_canonical_bytes(payload, CanonSpec(exclude_none=False)) == (
        b'{"name":"outer","nested":{"optional":null,"value":7},"optional":null}'
    )


def test_none_policy_excludes_structured_fields_but_preserves_raw_mapping_nulls() -> None:
    structured = _DataclassEnvelope(name="outer", nested=_NestedModel(value=7))

    assert b"optional" not in to_canonical_bytes(structured)
    assert to_canonical_bytes({"optional": None}) == b'{"optional":null}'


def test_canonicalization_rejects_excessive_recursion_depth() -> None:
    with pytest.raises(CanonViolation, match="max_depth=4"):
        to_canonical_bytes(_deep_list(8), CanonSpec(max_depth=4))


def test_world_payload_normalization_rejects_excessive_recursion_depth() -> None:
    with pytest.raises(CanonViolation, match="World ID payload depth"):
        claim_id_from_payload(
            claim_payload={
                "predicate_id": "pred.test",
                "subject_id": "entity.test",
                "value_text": "10",
                "source_kind": "dataset",
                "source_artifacts": ["sha256:" + "c" * 64],
                "qualifiers": _deep_dict(140),
            }
        )


def test_timezone_normalization_canonicalizes_equivalent_instants() -> None:
    plus_two = timezone(timedelta(hours=2))
    local = datetime(2026, 4, 12, 14, 30, tzinfo=plus_two)
    utc = datetime(2026, 4, 12, 12, 30, tzinfo=UTC)

    assert to_canonical_bytes({"t": local}) == to_canonical_bytes({"t": utc})
    assert b"2026-04-12T12:30:00Z" in to_canonical_bytes({"t": local})


def test_analytics_float_canonicalization_is_explicit_and_stable() -> None:
    payload = {"negative_zero": -0.0, "estimate": 0.125}

    with pytest.raises(CanonViolation):
        to_canonical_bytes(payload)

    canonical = to_canonical_bytes(payload, CanonSpec(forbid_floats=False))
    assert canonical == (
        b'{"estimate":{"_type":"float","repr":"0.125"},'
        b'"negative_zero":{"_type":"float","repr":"0"}}'
    )


def test_fact_tx_time_is_mandatory_and_normalized_to_utc() -> None:
    fact = Fact(
        fact_id="sha256:" + "a" * 64,
        subject_id="entity.test",
        predicate_id="pred.test",
        object_value="10",
        tx_time=datetime(2026, 4, 12, 15, 30, tzinfo=timezone(timedelta(hours=3))),
        provenance=_fact_provenance(),
    )

    assert fact.tx_time == "2026-04-12T12:30:00Z"

    with pytest.raises(ValidationError):
        Fact(
            fact_id="sha256:" + "a" * 64,
            subject_id="entity.test",
            predicate_id="pred.test",
            object_value="10",
            provenance=_fact_provenance(),
        )

    with pytest.raises(ValidationError, match="timezone"):
        Fact(
            fact_id="sha256:" + "a" * 64,
            subject_id="entity.test",
            predicate_id="pred.test",
            object_value="10",
            tx_time=datetime(2026, 4, 12, 12, 30),
            provenance=_fact_provenance(),
        )


def test_cas_fixture_corpus_hashes_are_stable() -> None:
    fixtures = {
        "ordered_mapping": (
            {"b": 2, "a": 1, "nested": {"z": "last", "m": None}},
            CanonSpec(),
            "sha256:fd7a343733fe0b599596ed704b17818dea7844ceee589ac794859213c2df74bc",
        ),
        "typed_scalars": (
            {
                "when": datetime(
                    2026,
                    4,
                    12,
                    15,
                    30,
                    tzinfo=timezone(timedelta(hours=3)),
                ),
                "amount": Decimal("12.3400"),
                "blob": b"policy",
            },
            CanonSpec(),
            "sha256:4ad72c5572f5f8aaf7a44f44b772dad65bfbd7c71f10ee0bc8922f553a30d9a9",
        ),
        "analytics_float": (
            {"effect": -0.0, "estimate": 0.125},
            CanonSpec(forbid_floats=False),
            "sha256:f3a9cec0b4cc76042b10304051904a5646d26794d27cd8b7d535adac11f5cc93",
        ),
    }

    for payload, spec, expected in fixtures.values():
        assert content_hash(to_canonical_bytes(payload, spec), prefix=True) == expected


def test_sha1_is_only_available_as_deprecated_explicit_legacy_branch() -> None:
    assert content_hash(b"abc", prefix=True).startswith("sha256:")
    with pytest.warns(DeprecationWarning, match="sha1 content hashing is deprecated"):
        assert content_hash(b"abc", algorithm="sha1", prefix=True).startswith("sha1:")


def test_migration_schema_version_must_match_registered_edge() -> None:
    @register_migration("ws0a_mismatch", "1.0", "1.1")
    def _bad_migration(data: dict[str, object]) -> dict[str, object]:
        return {**data, "schema_version": "9.9"}

    with pytest.raises(MigrationSchemaVersionError, match=r"schema_version='9\.9'"):
        migrate_artifact({"schema_version": "1.0"}, "ws0a_mismatch", "1.1")


def test_migration_without_schema_version_is_stamped_by_registered_edge() -> None:
    @register_migration("ws0a_stamp", "1.0", "1.1")
    def _migration(data: dict[str, object]) -> dict[str, object]:
        payload = dict(data)
        payload.pop("schema_version")
        payload["added"] = True
        return payload

    assert migrate_artifact({"schema_version": "1.0"}, "ws0a_stamp", "1.1") == {
        "schema_version": "1.1",
        "added": True,
    }
