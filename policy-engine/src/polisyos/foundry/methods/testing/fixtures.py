"""
Reusable test data factories for Foundry method testing.

Provides standardized sample states and parameters that can be customized
for specific method requirements.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar

import chex
import jax.numpy as jnp
import numpy as np

from polisyos.foundry.methods.base import (
    ComplexityClass,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotSpec,
    SlotType,
    Unit,
)

# =============================================================================
# Sample State Types
# =============================================================================


@chex.dataclass(frozen=True)
class SimpleFiscalState:
    """
    Simple fiscal state for testing tax/budget methods.

    Contains income, tax, and balance arrays for N agents.
    """

    income: jnp.ndarray
    tax_paid: jnp.ndarray
    disposable_income: jnp.ndarray
    total_revenue: jnp.ndarray


@chex.dataclass(frozen=True)
class SimpleAgentState:
    """
    Simple agent state for testing agent-based methods.

    Contains position, velocity, and attributes for N agents.
    """

    positions: jnp.ndarray
    velocities: jnp.ndarray
    attributes: jnp.ndarray


@chex.dataclass(frozen=True)
class SimpleScalarState:
    """
    Minimal scalar state for testing simple transformations.
    """

    value: jnp.ndarray
    counter: jnp.ndarray


# =============================================================================
# Factory Protocols
# =============================================================================


StateT = TypeVar("StateT")
ParamsT = TypeVar("ParamsT")


class SampleStateFactory(Protocol[StateT]):
    """Protocol for state factory functions."""

    def __call__(
        self,
        n_agents: int = 100,
        seed: int = 42,
        **kwargs: Any,
    ) -> StateT:
        """Create a sample state."""
        ...


class SampleParamsFactory(Protocol[ParamsT]):
    """Protocol for params factory functions."""

    def __call__(
        self,
        **overrides: Any,
    ) -> ParamsT:
        """Create sample parameters."""
        ...


# =============================================================================
# Factory Functions
# =============================================================================


def create_sample_state(
    state_type: str = "fiscal",
    n_agents: int = 100,
    seed: int = 42,
    **kwargs: Any,
) -> Any:
    """
    Create a sample state for testing.

    Args:
        state_type: Type of state to create ("fiscal", "agent", "scalar")
        n_agents: Number of agents in state
        seed: Random seed for reproducibility
        **kwargs: Additional arguments passed to state constructor

    Returns:
        Sample state instance
    """
    rng = np.random.default_rng(seed)

    if state_type == "fiscal":
        income = jnp.array(rng.lognormal(10.0, 1.0, n_agents).astype(np.float32))
        return SimpleFiscalState(
            income=income,
            tax_paid=jnp.zeros(n_agents, dtype=jnp.float32),
            disposable_income=income,
            total_revenue=jnp.array(0.0, dtype=jnp.float32),
        )

    if state_type == "agent":
        n_dims = kwargs.get("n_dims", 2)
        n_attrs = kwargs.get("n_attrs", 3)
        return SimpleAgentState(
            positions=jnp.array(rng.uniform(0, 100, (n_agents, n_dims)).astype(np.float32)),
            velocities=jnp.array(rng.normal(0, 1, (n_agents, n_dims)).astype(np.float32)),
            attributes=jnp.array(rng.uniform(0, 1, (n_agents, n_attrs)).astype(np.float32)),
        )

    if state_type == "scalar":
        return SimpleScalarState(
            value=jnp.array(np.float32(rng.uniform(0, 100))),
            counter=jnp.array(0, dtype=jnp.int32),
        )

    raise ValueError(f"Unknown state_type: {state_type}")


def create_sample_params(
    param_type: str = "fiscal",
    **overrides: Any,
) -> dict[str, Any]:
    """
    Create sample parameters for testing.

    Args:
        param_type: Type of parameters to create ("fiscal", "agent", "scalar")
        **overrides: Values to override in default parameters

    Returns:
        Dictionary of parameters (JAX arrays)
    """
    if param_type == "fiscal":
        defaults: dict[str, Any] = {
            "rate": jnp.array(0.18, dtype=jnp.float32),
            "threshold_1": jnp.array(10000.0, dtype=jnp.float32),
            "threshold_2": jnp.array(50000.0, dtype=jnp.float32),
            "rate_1": jnp.array(0.18, dtype=jnp.float32),
            "rate_2": jnp.array(0.22, dtype=jnp.float32),
            "rate_3": jnp.array(0.32, dtype=jnp.float32),
        }

    elif param_type == "agent":
        defaults = {
            "speed": jnp.array(1.0, dtype=jnp.float32),
            "attraction": jnp.array(0.1, dtype=jnp.float32),
            "repulsion": jnp.array(0.05, dtype=jnp.float32),
            "noise": jnp.array(0.01, dtype=jnp.float32),
        }

    elif param_type == "scalar":
        defaults = {
            "multiplier": jnp.array(2.0, dtype=jnp.float32),
            "offset": jnp.array(1.0, dtype=jnp.float32),
        }

    else:
        raise ValueError(f"Unknown param_type: {param_type}")

    return {**defaults, **overrides}


# =============================================================================
# Signature and Metadata Factories
# =============================================================================


def create_sample_signature(
    name: str = "test_method",
    namespace: str = "test.testing",
    version: str = "1.0.0",
    **kwargs: Any,
) -> MethodSignature:
    """Create a sample MethodSignature for testing."""
    defaults = {
        "input_slots": frozenset(
            {
                SlotSpec(
                    name="input",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("currency", "UAH"),
                ),
            }
        ),
        "output_slots": frozenset(
            {
                SlotSpec(
                    name="output",
                    slot_type=SlotType.VECTOR,
                    unit=Unit("currency", "UAH"),
                ),
            }
        ),
        "parameters": (),
        "fidelity": FidelityLevel.MEDIUM,
        "complexity": ComplexityClass.O_N,
    }

    return MethodSignature(
        name=name,
        namespace=namespace,
        version=version,
        **{**defaults, **kwargs},
    )


def create_sample_metadata(
    description: str = "Test method for unit testing",
    **kwargs: Any,
) -> MethodMetadata:
    """Create a sample MethodMetadata for testing."""
    defaults = {
        "tags": frozenset({"test", "fixture"}),
        "citations": (),
        "equations": {},
    }

    return MethodMetadata(
        description=description,
        **{**defaults, **kwargs},
    )


# =============================================================================
# Method Class Factory
# =============================================================================


def create_test_method_class(
    name: str = "TestMethod",
    namespace: str = "test.testing",
    version: str = "1.0.0",
    pure_step_fn: Callable[[Any, dict[str, Any]], Any] | None = None,
) -> type:
    """
    Dynamically create a FoundryMethod class for testing.

    Args:
        name: Class name
        namespace: Method namespace
        version: Semantic version
        pure_step_fn: Custom pure_step implementation

    Returns:
        A new class implementing FoundryMethod protocol
    """
    if pure_step_fn is None:

        def pure_step_fn(state: Any, params: dict[str, Any]) -> Any:
            return state

    signature = create_sample_signature(
        name=name.lower(),
        namespace=namespace,
        version=version,
    )

    metadata = create_sample_metadata(
        description=f"Auto-generated test method: {name}",
    )

    class_dict = {
        "signature": signature,
        "metadata": metadata,
        "pure_step": staticmethod(pure_step_fn),
    }

    return type(name, (), class_dict)
