"""Test-first witnesses for CMP-03 linker matching and semantic parity.

The tests use the real ``SlotLinker`` and ``SlotSpec`` contracts.  B47 is
represented by a two-target augmenting-path case: a source with no contract is
compatible with both targets, while a fixed-contract source can satisfy only
the first target.  B48 pins the requirement that automatic and explicit
linking apply the same semantic and completeness gates.
"""

from __future__ import annotations

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
