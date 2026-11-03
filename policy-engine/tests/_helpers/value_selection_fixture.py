"""Declared finite Foundry intake for selection-scope integration tests."""

from dataclasses import replace
from typing import ClassVar

from polisyos.foundry.extensions._builtin_loader import builtin_foundry_method_components
from polisyos.foundry.extensions.api import component_for_method
from polisyos.foundry.methods.base import MethodSignature
from polisyos.foundry.methods.catalog.bayesian.gp import GaussianProcessRegressionEstimator
from polisyos.foundry.methods.catalog.econometrics.advanced import EventStudyEstimator
from polisyos.ir.analytics.uncertainty import OutputContractCapability


class BrokenValueOwner(GaussianProcessRegressionEstimator):
    """Deliberately invalid native owner for contract-gap rejection controls."""

    signature: ClassVar[MethodSignature] = replace(
        GaussianProcessRegressionEstimator.signature,
        namespace="test.value_selection",
        name="broken_owner",
        output_slots=frozenset(
            replace(
                slot, contract_owner="tests._helpers.value_selection_fixture:MissingContractOwner"
            )
            if OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION in slot.contract_capabilities
            else slot
            for slot in GaussianProcessRegressionEstimator.signature.output_slots
        ),
    )


def singleton_value_components() -> tuple[object, ...]:
    """Return one real native value owner in this test's declared intake."""
    return (component_for_method(GaussianProcessRegressionEstimator),)


def two_value_components() -> tuple[object, ...]:
    """Return two actual native owners in a declared, finite intake."""
    return (
        component_for_method(GaussianProcessRegressionEstimator),
        component_for_method(EventStudyEstimator),
    )


def one_valid_one_broken_value_components() -> tuple[object, ...]:
    """Declare one native value owner and one unresolved value declaration."""
    return (component_for_method(EventStudyEstimator), component_for_method(BrokenValueOwner))


def builtins_without_unrelated_twenty() -> tuple[object, ...]:
    """Declare the builtins less twenty owners without a value output."""
    components = builtin_foundry_method_components()
    removed = 0
    retained = []
    for component in components:
        signature = component.method_class.signature
        is_value = any(
            OutputContractCapability.VALUE_UNCERTAINTY_PROJECTION in slot.contract_capabilities
            for slot in signature.output_slots
        )
        if not is_value and removed < 20:
            removed += 1
            continue
        retained.append(component)
    assert removed == 20
    return tuple(retained)


def builtins_without_gp() -> tuple[object, ...]:
    """Declare the builtins less one genuine value owner."""
    return tuple(
        component
        for component in builtin_foundry_method_components()
        if component.method_class.signature.fqn != "bayesian.gp.gp_regression@1.0.0"
    )
