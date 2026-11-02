"""Test-first witnesses for CMP-03 linker matching and semantic parity.

The tests use the real ``SlotLinker`` and ``SlotSpec`` contracts.  B47 is
represented by a two-target augmenting-path case: a source with no contract is
compatible with both targets, while a fixed-contract source can satisfy only
the first target.  B48 pins the requirement that automatic and explicit
linking apply the same semantic and completeness gates.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from itertools import product

import pytest

from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.components.linker import (
    LinkerConfig,
    SlotLinker,
    check_linkable,
)
from polisyos.foundry.methods.components.slot_schema import SemanticCompatibilityError
from polisyos.foundry.methods.exceptions import (
    ShapeMismatchError,
    SlotConnectionError,
    UnitMismatchError,
)

_NEUTRAL_UNIT = Unit(dimension="cmp03", symbol="unit")


def _slot(
    name: str,
    *,
    contract_id: str | None = None,
    slot_type: SlotType = SlotType.SCALAR,
    unit: Unit = _NEUTRAL_UNIT,
    shape: tuple = (),
) -> SlotSpec:
    """Build a minimal slot while keeping all non-target dimensions equal."""
    return SlotSpec(
        name=name,
        slot_type=slot_type,
        unit=unit,
        contract_id=contract_id,
        shape=shape,
    )


def _signature(
    name: str,
    *,
    inputs: tuple[SlotSpec, ...] = (),
    outputs: tuple[SlotSpec, ...] = (),
) -> MethodSignature:
    """Build a real linker signature with no executor or registry dependency."""
    return MethodSignature(
        name=name,
        namespace="tests.cmp03",
        version="1.0.0",
        input_slots=frozenset(inputs),
        output_slots=frozenset(outputs),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
    )


def _bounded_matching_signatures(
    source_names: tuple[str, str],
    target_names: tuple[str, str],
) -> tuple[MethodSignature, MethodSignature]:
    """Return the B47 graph, with names varied independently of contracts."""
    source = _signature(
        "producer",
        outputs=(
            _slot(source_names[0]),  # flexible: compatible with A and B
            _slot(source_names[1], contract_id="contract.B"),  # fixed: B only
        ),
    )
    target = _signature(
        "consumer",
        inputs=(
            _slot(target_names[0], contract_id="contract.B"),
            _slot(target_names[1], contract_id="contract.A"),
        ),
    )
    return source, target


def _binding_sources_by_target(result) -> dict[str, str]:
    """Return the linker's concrete assignment for readable assertions."""
    return {binding.target_slot: binding.source_slot for binding in result.bindings}


@pytest.mark.parametrize(
    ("source_names", "target_names"),
    [
        pytest.param(
            ("a_flexible", "b_fixed"),
            ("c_first", "d_second"),
            id="source-card-counterexample",
        ),
        pytest.param(
            ("left_flexible", "right_fixed"),
            ("alpha_first", "omega_second"),
            id="neutral-slot-renaming",
        ),
        pytest.param(
            ("z_flexible", "a_fixed"),
            ("z_first", "a_second"),
            id="adversarial-inverse-order-neutral-rename",
        ),
    ],
)
def test_auto_finds_bounded_augmenting_path_without_name_dependent_existence(
    source_names: tuple[str, str],
    target_names: tuple[str, str],
) -> None:
    """B47: flexible→second and fixed→first is the complete assignment."""
    source, target = _bounded_matching_signatures(source_names, target_names)

    result = SlotLinker(LinkerConfig.strict()).link(source, target)

    assert result.unconnected_inputs == ()
    assert _binding_sources_by_target(result) == {
        target_names[0]: source_names[1],
        target_names[1]: source_names[0],
    }


def test_semantically_compatible_auto_and_explicit_links_remain_complete() -> None:
    """B48 control: an allowed named semantic conversion remains usable."""
    source = _signature("producer", outputs=(_slot("outcome"),))
    target = _signature("consumer", inputs=(_slot("residual"),))
    linker = SlotLinker(LinkerConfig.semantic_strict())

    auto = linker.link(source, target)
    explicit = linker.link(source, target, explicit_mapping={"outcome": "residual"})

    assert auto.unconnected_inputs == ()
    assert explicit.unconnected_inputs == ()
    assert auto.binding_count == explicit.binding_count == 1


def test_auto_and_explicit_reject_the_same_named_semantic_mismatch() -> None:
    """B48: type-compatible but semantically forbidden links fail both paths."""
    source = _signature("producer", outputs=(_slot("outcome"),))
    target = _signature("consumer", inputs=(_slot("treatment"),))
    linker = SlotLinker(LinkerConfig.semantic_strict())

    with pytest.raises(SemanticCompatibilityError):
        linker.link(source, target, explicit_mapping={"outcome": "treatment"})
    with pytest.raises(SemanticCompatibilityError):
        linker.link(source, target)


def test_check_linkable_rejects_semantic_mismatch_without_raising() -> None:
    """B48: the preflight helper reports forbidden edges as non-linkable."""
    source = _signature("producer", outputs=(_slot("outcome"),))
    target = _signature("consumer", inputs=(_slot("treatment"),))

    assert check_linkable(source, target) is False


@pytest.mark.parametrize("explicit", [True, False], ids=["explicit", "auto"])
def test_auto_and_explicit_reject_the_same_incomplete_assignment(explicit: bool) -> None:
    """B48 control: strict completeness is shared by both linking routes."""
    source = _signature("producer", outputs=(_slot("required"),))
    target = _signature(
        "consumer",
        inputs=(_slot("missing"), _slot("required")),
    )
    linker = SlotLinker(LinkerConfig.strict())
    mapping = {"required": "required"} if explicit else None

    with pytest.raises(SlotConnectionError, match=r"(?i)unconnected"):
        linker.link(source, target, explicit_mapping=mapping)


@pytest.mark.parametrize(
    ("explicit", "expected"),
    [
        pytest.param(True, UnitMismatchError, id="explicit"),
        pytest.param(False, SlotConnectionError, id="auto"),
    ],
)
def test_unit_dimension_guard_remains_active_for_both_routes(
    explicit: bool,
    expected: type[Exception],
) -> None:
    """B47 control: matching must not turn a unit mismatch into a link."""
    source = _signature(
        "producer",
        outputs=(_slot("source", unit=Unit("currency", "USD")),),
    )
    target = _signature(
        "consumer",
        inputs=(_slot("target", unit=Unit("time", "yr")),),
    )
    linker = SlotLinker(LinkerConfig.strict())
    mapping = {"source": "target"} if explicit else None

    with pytest.raises(expected):
        linker.link(source, target, explicit_mapping=mapping)


@pytest.mark.parametrize(
    ("explicit", "expected"),
    [
        pytest.param(True, ShapeMismatchError, id="explicit"),
        pytest.param(False, SlotConnectionError, id="auto"),
    ],
)
def test_shape_guard_remains_active_for_both_routes(
    explicit: bool,
    expected: type[Exception],
) -> None:
    """B47 control: strict shape compatibility remains a hard gate."""
    source = _signature(
        "producer",
        outputs=(_slot("source", slot_type=SlotType.TENSOR, shape=(2, 3)),),
    )
    target = _signature(
        "consumer",
        inputs=(_slot("target", slot_type=SlotType.TENSOR, shape=(2, 4)),),
    )
    linker = SlotLinker(LinkerConfig.strict())
    mapping = {"source": "target"} if explicit else None

    with pytest.raises(expected):
        linker.link(source, target, explicit_mapping=mapping)


def test_contract_guard_remains_active_for_both_routes() -> None:
    """B47 control: incompatible declared contracts are never matched."""
    source = _signature(
        "producer",
        outputs=(_slot("source", contract_id="contract.A"),),
    )
    target = _signature(
        "consumer",
        inputs=(_slot("target", contract_id="contract.B"),),
    )
    linker = SlotLinker(LinkerConfig.strict())

    with pytest.raises(SlotConnectionError):
        linker.link(source, target, explicit_mapping={"source": "target"})
    with pytest.raises(SlotConnectionError):
        linker.link(source, target)


def test_selected_edge_diagnostics_follow_actual_rematching() -> None:
    """Rematching cannot report a structurally forbidden loop-local source."""
    source, target = _bounded_matching_signatures(
        ("a_flexible", "b_fixed"), ("c_first", "d_second")
    )
    result = SlotLinker(LinkerConfig.strict()).link(source, target)

    assert _binding_sources_by_target(result) == {"c_first": "b_fixed", "d_second": "a_flexible"}
    assert "Auto-linked: b_fixed -> c_first" in result.warnings
    assert "Auto-linked: a_flexible -> d_second" in result.warnings
    assert not any("b_fixed -> d_second" in warning for warning in result.warnings)
    assert any(
        "used 'b_fixed'" in warning and "['a_flexible']" in warning for warning in result.warnings
    )


@pytest.mark.parametrize("preference", [False, True])
def test_single_source_name_preference_is_global_after_cardinality(preference: bool) -> None:
    """An earlier target cannot consume the only exact-name source by accident."""
    source = _signature("one", outputs=(_slot("right"),))
    target = _signature("two", inputs=(_slot("left"), _slot("right")))
    result = SlotLinker(LinkerConfig(prefer_exact_names=preference)).link(source, target)
    assert _binding_sources_by_target(result) == {"right" if preference else "left": "right"}


def test_global_unit_score_preserves_the_only_identity_conversion() -> None:
    """A later indifferent target must not displace an earlier exact unit."""
    source = _signature(
        "units",
        outputs=(
            _slot("a", unit=Unit("length", "m", 1)),
            _slot("b", unit=Unit("length", "cm", 0.01)),
        ),
    )
    target = _signature(
        "lengths",
        inputs=(
            _slot("first", unit=Unit("length", "m", 1)),
            _slot("second", unit=Unit("length", "mm", 0.001)),
        ),
    )
    result = SlotLinker(LinkerConfig(prefer_exact_names=False)).link(source, target)
    # Both second-target choices need conversion, while only a→first keeps
    # an identity. This is a unit-score optimum, not a name-score example.
    assert _binding_sources_by_target(result) == {"first": "a", "second": "b"}
    assert result.get_binding("first").requires_conversion is False
    assert result.get_binding("second").conversion_factor == pytest.approx(10)


def test_global_shape_score_retains_the_only_identity_shape() -> None:
    source = _signature(
        "shapes",
        outputs=(
            _slot("a", slot_type=SlotType.TENSOR, shape=(2,)),
            _slot("b", slot_type=SlotType.TENSOR, shape=(1,)),
        ),
    )
    target = _signature(
        "targets",
        inputs=(
            _slot("first", slot_type=SlotType.TENSOR, shape=(2,)),
            _slot("second", slot_type=SlotType.TENSOR, shape=(2, 2)),
        ),
    )
    result = SlotLinker(LinkerConfig(prefer_exact_names=False)).link(source, target)
    assert _binding_sources_by_target(result) == {"first": "a", "second": "b"}


def test_global_warning_score_preserves_the_only_overlapping_bounds() -> None:
    source = _signature(
        "bounds",
        outputs=(
            replace(_slot("a"), bounds=(0, 10)),
            replace(_slot("b"), bounds=(20, 30)),
        ),
    )
    target = _signature(
        "targets",
        inputs=(
            replace(_slot("first"), bounds=(0, 10)),
            replace(_slot("second"), bounds=(40, 50)),
        ),
    )
    result = SlotLinker(LinkerConfig(prefer_exact_names=False)).link(source, target)
    assert _binding_sources_by_target(result) == {"first": "a", "second": "b"}
    assert not result.get_binding("first").compatibility.warnings
    assert result.get_binding("second").compatibility.warnings


@pytest.mark.parametrize("preference", [False, True])
def test_all_three_slot_contract_graphs_match_independent_exhaustive_oracle(
    preference: bool,
) -> None:
    """All729 declared contract graphs maximize coverage, then exact-name score."""
    histogram: Counter[int] = Counter()
    names = ("slot0", "slot1", "slot2")
    for declarations in product((None, "A", "B"), repeat=6):
        source_contracts, target_contracts = declarations[:3], declarations[3:]
        source = _signature(
            "source",
            outputs=tuple(
                _slot(name, contract_id=contract)
                for name, contract in zip(names, source_contracts, strict=True)
            ),
        )
        target = _signature(
            "target",
            inputs=tuple(
                _slot(name, contract_id=contract)
                for name, contract in zip(names, target_contracts, strict=True)
            ),
        )
        # Exhaustive assignments derive admissibility from the declared wildcard
        # contract relation, without invoking the producer's matcher or score.
        candidates = []
        for assignment in product((None, 0, 1, 2), repeat=3):
            used = [index for index in assignment if index is not None]
            if len(used) != len(set(used)):
                continue
            if any(
                source_contracts[source_index] is not None
                and target_contracts[target_index] is not None
                and source_contracts[source_index] != target_contracts[target_index]
                for target_index, source_index in enumerate(assignment)
                if source_index is not None
            ):
                continue
            pairs = tuple((names[t], names[v]) for t, v in enumerate(assignment) if v is not None)
            exact = sum(t == v for t, v in enumerate(assignment)) if preference else 0
            candidates.append((-len(pairs), -exact, pairs))
        expected = min(candidates)
        result = SlotLinker(LinkerConfig(prefer_exact_names=preference)).link(source, target)
        actual = tuple(sorted((b.target_slot, b.source_slot) for b in result.bindings))
        assert actual == expected[2], declarations
        histogram[len(actual)] += 1
    assert histogram == {3: 583, 2: 120, 1: 24, 0: 2}
