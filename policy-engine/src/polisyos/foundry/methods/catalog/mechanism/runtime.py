"""Public mechanism runtime module API."""
from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.contracts.fidelity import FidelityLevel as RuntimeFidelityLevel
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodKind,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SideEffectProfile,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset({SlotSpec("result", SlotType.SCALAR, Unit("result", "json"))})


def _serialize_tree(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _serialize_tree(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_tree(item) for item in value]
    if hasattr(value, "shape") and hasattr(value, "dtype"):
        arr = np.asarray(value)
        if arr.shape == ():
            scalar = arr.item()
            if isinstance(scalar, np.generic):
                return scalar.item()
            return scalar
        return arr.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def _coerce_target_mask(value: Any) -> Any:
    if value is None:
        return None
    import jax.numpy as jnp

    return jnp.asarray(value, dtype=jnp.bool_)


def _population_shape(state: Any) -> tuple[int, int]:
    n_agents = 0
    n_firms = 0
    agents = getattr(state, "agents", None)
    firms = getattr(state, "firms", None)
    if agents is not None and hasattr(agents, "size"):
        n_agents = int(agents.size)
    if firms is not None and hasattr(firms, "size"):
        n_firms = int(firms.size)
    return n_agents, n_firms


def _coerce_runtime_state(value: Any, *, allow_queue: bool = False) -> Any:
    if hasattr(value, "agents") or hasattr(value, "firms"):
        return value
    if allow_queue and isinstance(value, Mapping) and "queue_length" in value:
        from polisyos.foundry.queue import QueueState

        import jax.numpy as jnp

        return QueueState(queue_length=jnp.asarray(value["queue_length"], dtype=jnp.float32))
    raise TypeError("mechanism runtime methods require a Foundry runtime state object")


def _runtime_fidelity(params: Mapping[str, Any]) -> Any:
    from polisyos.foundry.contracts.fidelity import FidelityLevel as RuntimeFidelityLevel

    return RuntimeFidelityLevel(str(params.get("fidelity", RuntimeFidelityLevel.SURROGATE_FLUID.value)))


def _apply_runtime_mechanism(
    mechanism_type: str,
    state: Any,
    params: Mapping[str, Any],
    *,
    allow_queue: bool = False,
    param_keys: tuple[str, ...],
) -> dict[str, Any]:
    runtime_state = _coerce_runtime_state(state, allow_queue=allow_queue)
    fidelity = _runtime_fidelity(params)
    n_agents, n_firms = _population_shape(runtime_state)
    mechanism_params = {key: params.get(key) for key in param_keys if key in params}
    from polisyos.foundry.registry import create_mechanism_from_spec

    import jax

    mechanism = create_mechanism_from_spec(
        mechanism_type,
        mechanism_params,
        n_agents=n_agents,
        n_firms=n_firms,
        selected_fidelity=fidelity,
    )
    if hasattr(mechanism, "debug_mode"):
        # equinox modules are frozen dataclasses; debug_mode is a Python bool
        # (static field), so eqx.tree_at doesn't apply.  We bypass the frozen
        # guard via object.__setattr__, which is the standard equinox pattern
        # for mutating static fields outside of __init__.
        object.__setattr__(mechanism, "debug_mode", bool(params.get("debug_mode", False)))
    key = jax.random.PRNGKey(int(params.get("__seed__", 0)))
    initialized_state, key = mechanism.init_state(runtime_state, key)
    patches, _ = mechanism.emit_patches(
        initialized_state,
        key,
        target_mask=_coerce_target_mask(params.get("target_mask")),
    )
    return {
        "result": {
            "mechanism_type": mechanism_type,
            "runtime_fidelity": fidelity.value,
            "patches": _serialize_tree(patches),
            "n_patch_slots": len(patches),
        }
    }


@foundry_method(
    namespace="mechanism.runtime",
    version="1.0.0",
    tags={"mechanism", "runtime", "fiscal", "subsidy", "structural"},
)
class TaxSubsidyMechanismMethod:
    """Tax subsidy mechanism method public type."""
    method_kind: ClassVar[MethodKind] = MethodKind.MECHANISM
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax",)
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.PATCH_EMISSION
    runtime_mechanism_type: ClassVar[str] = "tax_subsidy"
    runtime_mechanism_class_path: ClassVar[str] = "polisyos.foundry.mechanisms:TaxSubsidy"
    supported_runtime_fidelities: ClassVar[tuple[RuntimeFidelityLevel, ...]] = tuple(
        RuntimeFidelityLevel
    )
    hybrid_default_runtime_fidelity: ClassVar[RuntimeFidelityLevel] = (
        RuntimeFidelityLevel.SURROGATE_FLUID
    )

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="tax_subsidy",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({SlotSpec("runtime_state", SlotType.SCALAR, Unit("state", "object"))}),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="rate", default=0.1),
            ParameterSpec(name="fidelity", default="fluid"),
            ParameterSpec(name="debug_mode", default=False),
            ParameterSpec(name="target_mask", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Emit fiscal subsidy patches through the unified MethodRegistry.",
        tags=frozenset({"mechanism", "runtime", "fiscal", "subsidy", "structural"}),
        when_to_use="Apply targeted subsidy or tax relief to agents/firms in simulation; analyze fiscal transfer incidence",
        citations=(
            "Mirrlees, J. (1971). An Exploration in the Theory of Optimum Income Taxation. Review of Economic Studies, 38(2), 175-208.",
        ),
        output_interpretation="Patches applied to agent income/wealth. Incidence = share of subsidy captured by each group. Check fiscal cost vs welfare gain.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        return _apply_runtime_mechanism("tax_subsidy", state, params, param_keys=("rate",))


@foundry_method(
    namespace="mechanism.runtime",
    version="1.0.0",
    tags={"mechanism", "runtime", "fiscal", "tax", "structural"},
)
class IncomeTaxMechanismMethod:
    """Income tax mechanism method public type."""
    method_kind: ClassVar[MethodKind] = MethodKind.MECHANISM
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STRICT_CPU
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax",)
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.PATCH_EMISSION
    runtime_mechanism_type: ClassVar[str] = "income_tax"
    runtime_mechanism_class_path: ClassVar[str] = "polisyos.foundry.mechanisms:IncomeTax"
    supported_runtime_fidelities: ClassVar[tuple[RuntimeFidelityLevel, ...]] = tuple(
        RuntimeFidelityLevel
    )
    hybrid_default_runtime_fidelity: ClassVar[RuntimeFidelityLevel] = (
        RuntimeFidelityLevel.SURROGATE_FLUID
    )

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="income_tax",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({SlotSpec("runtime_state", SlotType.SCALAR, Unit("state", "object"))}),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="rate", default=0.2),
            ParameterSpec(name="fidelity", default="fluid"),
            ParameterSpec(name="debug_mode", default=False),
            ParameterSpec(name="target_mask", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Emit income tax patches through the unified MethodRegistry.",
        tags=frozenset({"mechanism", "runtime", "fiscal", "tax", "structural"}),
        when_to_use="Apply income tax schedule to agents; analyze tax incidence, progressivity, and behavioral responses in simulation",
        citations=(
            "Mirrlees, J. (1971). An Exploration in the Theory of Optimum Income Taxation. Review of Economic Studies, 38(2), 175-208.",
        ),
        output_interpretation="Tax liability patches per agent. Effective rate = tax paid / gross income. Progressivity index from Gini pre/post tax.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        return _apply_runtime_mechanism("income_tax", state, params, param_keys=("rate",))


@foundry_method(
    namespace="mechanism.runtime",
    version="1.0.0",
    tags={"mechanism", "runtime", "labor", "structural"},
)
class LaborMarketMechanismMethod:
    """Labor market mechanism method public type."""
    method_kind: ClassVar[MethodKind] = MethodKind.MECHANISM
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax",)
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.PATCH_EMISSION
    runtime_mechanism_type: ClassVar[str] = "labor_market"
    runtime_mechanism_class_path: ClassVar[str] = (
        "polisyos.foundry.mechanisms:LaborMarketMechanism"
    )
    supported_runtime_fidelities: ClassVar[tuple[RuntimeFidelityLevel, ...]] = (
        RuntimeFidelityLevel.SURROGATE_FLUID,
        RuntimeFidelityLevel.RELAXED_DISCRETE,
    )
    hybrid_default_runtime_fidelity: ClassVar[RuntimeFidelityLevel] = (
        RuntimeFidelityLevel.SURROGATE_FLUID
    )

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="labor_market",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({SlotSpec("runtime_state", SlotType.SCALAR, Unit("state", "object"))}),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="employment_threshold", default=0.5),
            ParameterSpec(name="fidelity", default="fluid"),
            ParameterSpec(name="debug_mode", default=False),
            ParameterSpec(name="target_mask", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Emit labor market employment and wage patches through the unified MethodRegistry.",
        tags=frozenset({"mechanism", "runtime", "labor", "structural"}),
        when_to_use="Simulate labor market matching, wage determination, and employment transitions; evaluate minimum wage or hiring subsidy policies",
        citations=(
            "Diamond, P. (1982). Aggregate Demand Management in Search Equilibrium. Journal of Political Economy, 90(5), 881-894.",
        ),
        output_interpretation="Employment and wage patches per agent. Unemployment rate = share with no employment match. Wage distribution shift from policy.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        return _apply_runtime_mechanism(
            "labor_market",
            state,
            params,
            param_keys=("employment_threshold",),
        )


@foundry_method(
    namespace="mechanism.runtime",
    version="1.0.0",
    tags={"mechanism", "runtime", "queue", "structural"},
)
class QueueMechanismMethod:
    """Queue mechanism method public type."""
    method_kind: ClassVar[MethodKind] = MethodKind.MECHANISM
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax",)
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.PATCH_EMISSION
    runtime_mechanism_type: ClassVar[str] = "queue"
    runtime_mechanism_class_path: ClassVar[str] = "polisyos.foundry.queue:QueueMechanism"
    supported_runtime_fidelities: ClassVar[tuple[RuntimeFidelityLevel, ...]] = (
        RuntimeFidelityLevel.SURROGATE_FLUID,
        RuntimeFidelityLevel.RELAXED_DISCRETE,
    )
    hybrid_default_runtime_fidelity: ClassVar[RuntimeFidelityLevel] = (
        RuntimeFidelityLevel.SURROGATE_FLUID
    )

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="queue",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({SlotSpec("runtime_state", SlotType.SCALAR, Unit("state", "object"))}),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="service_rate", default=1.0),
            ParameterSpec(name="arrival_rate", default=0.5),
            ParameterSpec(name="capacity", default=None),
            ParameterSpec(name="temperature", default=1.0),
            ParameterSpec(name="fidelity", default="fluid"),
            ParameterSpec(name="debug_mode", default=False),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Emit queue-length patches through the unified MethodRegistry.",
        tags=frozenset({"mechanism", "runtime", "queue", "structural"}),
        when_to_use="Model service congestion in simulation; analyze capacity, waiting times, and throughput under policy changes",
        citations=(
            "Gross, D. & Shortle, J. (2008). Fundamentals of Queueing Theory. Wiley.",
        ),
        output_interpretation="Queue-length patch. Stable queue = lambda < mu (rho < 1). Policy target: reduce waiting time or increase throughput.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        return _apply_runtime_mechanism(
            "queue",
            state,
            params,
            allow_queue=True,
            param_keys=("service_rate", "arrival_rate", "capacity", "temperature"),
        )


@foundry_method(
    namespace="mechanism.runtime",
    version="1.0.0",
    tags={"mechanism", "runtime", "adaptive-agent", "structural"},
)
class AdaptiveAgentMechanismMethod:
    """Adaptive agent mechanism method public type."""
    method_kind: ClassVar[MethodKind] = MethodKind.MECHANISM
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("jax", "equinox", "optax")
    side_effect_profile: ClassVar[SideEffectProfile] = SideEffectProfile.PATCH_EMISSION
    runtime_mechanism_type: ClassVar[str] = "adaptive_agent"
    runtime_mechanism_class_path: ClassVar[str] = (
        "polisyos.foundry.agents:AdaptiveAgentMechanism"
    )
    supported_runtime_fidelities: ClassVar[tuple[RuntimeFidelityLevel, ...]] = tuple(
        RuntimeFidelityLevel
    )
    hybrid_default_runtime_fidelity: ClassVar[RuntimeFidelityLevel] = (
        RuntimeFidelityLevel.SURROGATE_FLUID
    )

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="adaptive_agent",
        namespace="",
        version="0.0.0",
        input_slots=frozenset({SlotSpec("runtime_state", SlotType.SCALAR, Unit("state", "object"))}),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="observation_space", default=(), is_static=True),
            ParameterSpec(name="action_space", default={"type": "continuous", "affects": ["policy.tax_rate"]}, is_static=True),
            ParameterSpec(name="utility", default=None, is_static=True),
            ParameterSpec(name="policy_model", default=None, is_static=True),
            ParameterSpec(name="weights_artifact", default=None, is_static=True),
            ParameterSpec(name="learning_rate", default=0.01),
            ParameterSpec(name="seed", default=0, is_static=True),
            ParameterSpec(name="stochastic", default=True, is_static=True),
            ParameterSpec(name="fidelity", default="fluid"),
            ParameterSpec(name="debug_mode", default=False),
            ParameterSpec(name="target_mask", default=None),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Emit adaptive agent policy patches through the unified MethodRegistry.",
        tags=frozenset({"mechanism", "runtime", "adaptive-agent", "structural"}),
        when_to_use="Endogenous agent decision-making with learning; model behavioral responses to policy interventions",
        citations=(
            "Tesfatsion, L. (2006). Agent-Based Computational Economics: A Constructive Approach to Economic Theory. Handbook of Computational Economics, Vol. 2.",
        ),
        output_interpretation="Policy patches reflecting agent decisions. Track policy convergence over steps. Evaluate welfare under learned vs fixed policy.",
    )

    @staticmethod
    def pure_step(state: Any, params: Mapping[str, Any]) -> dict[str, Any]:
        return _apply_runtime_mechanism(
            "adaptive_agent",
            state,
            params,
            param_keys=(
                "observation_space",
                "action_space",
                "utility",
                "policy_model",
                "weights_artifact",
                "learning_rate",
                "seed",
                "stochastic",
            ),
        )


__all__ = [
    "AdaptiveAgentMechanismMethod",
    "IncomeTaxMechanismMethod",
    "LaborMarketMechanismMethod",
    "QueueMechanismMethod",
    "TaxSubsidyMechanismMethod",
]
