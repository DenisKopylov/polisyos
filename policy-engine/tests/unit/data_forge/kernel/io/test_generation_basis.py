from __future__ import annotations

from polisyos.data_forge.kernel.io.generation_basis import (
    build_generation_basis,
    compare_generation_basis,
)


def test_generation_basis_is_order_independent_and_content_bound() -> None:
    first = build_generation_basis(
        basis_kind="test_artifact",
        generator_rule_version="test.generator.v1",
        members=(("b", b"two"), ("a", b"one")),
    )
    repeated = build_generation_basis(
        basis_kind="test_artifact",
        generator_rule_version="test.generator.v1",
        members=(("a", b"one"), ("b", b"two")),
    )
    changed = build_generation_basis(
        basis_kind="test_artifact",
        generator_rule_version="test.generator.v1",
        members=(("a", b"one changed"), ("b", b"two")),
    )

    assert first == repeated
    assert tuple(member.identifier for member in first.members) == ("a", "b")
    assert first.basis_digest != changed.basis_digest


def test_generation_basis_comparison_names_both_generations() -> None:
    current = build_generation_basis(
        basis_kind="test_artifact",
        generator_rule_version="test.generator.v2",
        members=(("source", b"current"),),
    )
    old = build_generation_basis(
        basis_kind="test_artifact",
        generator_rule_version="test.generator.v1",
        members=(("source", b"old"),),
    )

    matching = compare_generation_basis(current.to_dict(), current=current)
    missing = compare_generation_basis(None, current=current)
    incompatible = compare_generation_basis(old.to_dict(), current=current)

    assert matching.status == "current"
    assert matching.recorded_generation == current.basis_digest
    assert matching.current_generation == current.basis_digest
    assert missing.status == "missing"
    assert missing.recorded_generation == "unrecorded"
    assert missing.current_generation == current.basis_digest
    assert incompatible.status == "incompatible"
    assert incompatible.recorded_generation == old.basis_digest
    assert incompatible.current_generation == current.basis_digest
    assert incompatible.recorded_rule_version == "test.generator.v1"
    assert incompatible.current_rule_version == "test.generator.v2"


def test_generation_basis_comparison_rejects_a_forged_digest() -> None:
    current = build_generation_basis(
        basis_kind="test_artifact",
        generator_rule_version="test.generator.v1",
        members=(("source", b"current"),),
    )
    forged = current.to_dict()
    forged["basis_digest"] = "sha256:" + ("0" * 64)

    comparison = compare_generation_basis(forged, current=current)

    assert comparison.status == "malformed"
    assert comparison.recorded_generation == "malformed"
    assert comparison.current_generation == current.basis_digest
