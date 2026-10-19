from __future__ import annotations


def test_generation_basis_is_exposed_from_runtime_safe_read_api() -> None:
    from polisyos.data_forge.kernel.io.generation_basis import (
        GenerationBasis as OwnerGenerationBasis,
    )
    from polisyos.data_forge.kernel.io.generation_basis import (
        build_generation_basis as owner_build_generation_basis,
    )
    from polisyos.data_forge.read_api import GenerationBasis, build_generation_basis

    assert GenerationBasis is OwnerGenerationBasis
    assert build_generation_basis is owner_build_generation_basis
    basis = build_generation_basis(
        basis_kind="test.member-set",
        generator_rule_version="1",
        members=(("member-b", b"b"), ("member-a", b"a")),
    )
    assert tuple(member.identifier for member in basis.members) == ("member-a", "member-b")
    assert basis.basis_digest.startswith("sha256:")
    assert not hasattr(basis, "is_current")


def test_threshold_atom_read_api_alias_preserves_candidate_type_identity() -> None:
    from polisyos.data_forge.domains.legal.contracts import ThresholdAtom as OwnerThresholdAtom
    from polisyos.data_forge.read_api.legal import ThresholdAtom

    assert ThresholdAtom is OwnerThresholdAtom
