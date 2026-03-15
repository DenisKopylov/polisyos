from __future__ import annotations

from typing import Any, ClassVar, Mapping

import numpy as np

from polisyos.core.observability.determinism import DeterminismTier
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
    foundry_method,
)

from .protocols import MultiplexNetworkData, NetworkData, NetworkResult


def _network_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, NetworkData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        nested = state.get("network_data")
        if isinstance(nested, NetworkData):
            return nested.model_dump(mode="python")
        if isinstance(nested, Mapping):
            payload = dict(nested)
            payload.update({k: v for k, v in state.items() if k not in {"network_data"}})
            return payload
        return dict(state)
    raise TypeError("state must be NetworkData or mapping")


def _multiplex_payload(state: Any) -> dict[str, Any]:
    if isinstance(state, MultiplexNetworkData):
        return state.model_dump(mode="python")
    if isinstance(state, Mapping):
        return dict(state)
    raise TypeError("state must be MultiplexNetworkData or mapping")


def _result_slot() -> frozenset[SlotSpec]:
    return frozenset(
        {
            SlotSpec(
                "result",
                SlotType.SCALAR,
                Unit("network", "json"),
                contract_id=NetworkResult.contract_id,
            )
        }
    )


def _row_normalize(adjacency: np.ndarray) -> np.ndarray:
    arr = np.asarray(adjacency, dtype=float)
    row_sums = np.sum(arr, axis=1, keepdims=True)
    row_sums[row_sums == 0.0] = 1.0
    return arr / row_sums


def _symmetrize(adjacency: np.ndarray) -> np.ndarray:
    arr = np.asarray(adjacency, dtype=float)
    return 0.5 * (arr + arr.T)


@foundry_method(
    namespace="network.community",
    version="1.0.0",
    tags={"network", "community-detection"},
)
class CommunityDetectionEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("scikit-learn", "numpy")

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="community_detection",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("adjacency", SlotType.MATRIX, Unit("network", "weight"), shape=("n_nodes", "n_nodes")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(ParameterSpec(name="n_clusters", default=3),),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Spectral community detection on a weighted adjacency matrix.",
        tags=frozenset({"network", "community-detection"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        from sklearn.cluster import SpectralClustering

        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        adjacency = _symmetrize(np.asarray(data.adjacency, dtype=float))
        n_clusters = max(2, min(int(params.get("n_clusters", 3)), adjacency.shape[0] - 1))
        clustering = SpectralClustering(
            n_clusters=n_clusters,
            affinity="precomputed",
            random_state=int(params.get("__seed__", 0)),
            assign_labels="kmeans",
        )
        labels = clustering.fit_predict(adjacency)
        total_weight = float(np.sum(adjacency))
        degree = np.sum(adjacency, axis=1)
        modularity = 0.0
        if total_weight > 1e-12:
            for i in range(adjacency.shape[0]):
                for j in range(adjacency.shape[1]):
                    if labels[i] == labels[j]:
                        modularity += adjacency[i, j] - degree[i] * degree[j] / total_weight
            modularity /= total_weight
        return {
            "result": NetworkResult(
                method_name="community_detection",
                metrics={"modularity": float(modularity), "n_clusters": float(n_clusters)},
                labels=np.asarray(labels, dtype=int),
                metadata={"algorithm": "spectral_clustering"},
            )
        }


@foundry_method(
    namespace="network.io",
    version="1.0.0",
    tags={"network", "input-output-network"},
)
class InputOutputNetworkEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="input_output_network",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("adjacency", SlotType.MATRIX, Unit("network", "weight"), shape=("n_nodes", "n_nodes")),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Network linkage analysis using a Leontief-like inverse over the adjacency matrix.",
        tags=frozenset({"network", "input-output-network"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        adjacency = _row_normalize(np.asarray(data.adjacency, dtype=float))
        identity = np.eye(adjacency.shape[0], dtype=float)
        inverse = np.linalg.pinv(identity - 0.8 * adjacency)
        backward = np.sum(inverse, axis=0)
        forward = np.sum(inverse, axis=1)
        return {
            "result": NetworkResult(
                method_name="input_output_network",
                metrics={
                    "spectral_radius": float(np.max(np.abs(np.linalg.eigvals(adjacency)))),
                    "total_backward_linkage": float(np.sum(backward)),
                },
                node_scores=np.column_stack([forward, backward]),
                metadata={"inverse": inverse.tolist()},
            )
        }


@foundry_method(
    namespace="network.diffusion",
    version="1.0.0",
    tags={"network", "diffusion"},
)
class NetworkDiffusionEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="network_diffusion",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("adjacency", SlotType.MATRIX, Unit("network", "weight"), shape=("n_nodes", "n_nodes")),
                SlotSpec("node_states", SlotType.VECTOR, Unit("state", "value"), shape=("n_nodes",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="diffusion_rate", default=0.3),
            ParameterSpec(name="decay", default=0.05),
            ParameterSpec(name="n_steps", default=10),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="DeGroot-style network diffusion from initial node states.",
        tags=frozenset({"network", "diffusion"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        adjacency = _row_normalize(np.asarray(data.adjacency, dtype=float))
        current = np.asarray(data.node_states, dtype=float)
        rate = float(params.get("diffusion_rate", 0.3))
        decay = float(params.get("decay", 0.05))
        n_steps = max(1, int(params.get("n_steps", 10)))
        trajectories = [current.copy()]
        for _ in range(n_steps):
            current = np.clip((1.0 - decay) * current + rate * (adjacency @ current), 0.0, 1.0)
            trajectories.append(current.copy())
        traj = np.asarray(trajectories, dtype=float)
        return {
            "result": NetworkResult(
                method_name="network_diffusion",
                metrics={"final_mean_state": float(np.mean(traj[-1]))},
                node_scores=traj[-1],
                state_trajectories=traj,
                metadata={"n_steps": n_steps},
            )
        }


@foundry_method(
    namespace="network.contagion",
    version="1.0.0",
    tags={"network", "contagion-model"},
)
class ContagionModelEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.STATISTICAL
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="contagion_model",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec("adjacency", SlotType.MATRIX, Unit("network", "weight"), shape=("n_nodes", "n_nodes")),
                SlotSpec("node_states", SlotType.VECTOR, Unit("state", "value"), shape=("n_nodes",)),
            }
        ),
        output_slots=_result_slot(),
        parameters=(
            ParameterSpec(name="beta", default=0.4),
            ParameterSpec(name="gamma", default=0.1),
            ParameterSpec(name="n_steps", default=12),
            ParameterSpec(name="model_type", default="sis"),
        ),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Discrete-time SIS/SIR contagion model on a weighted network.",
        tags=frozenset({"network", "contagion-model"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> NetworkData:
        payload = _network_payload(fallback_state)
        payload.update(bound_inputs)
        return NetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: NetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        rng = params.get("__rng__")
        if rng is None or not hasattr(rng, "uniform"):
            rng = np.random.default_rng(int(params.get("__seed__", 0)))
        data = state if isinstance(state, NetworkData) else NetworkData.model_validate(state)
        adjacency = _row_normalize(np.asarray(data.adjacency, dtype=float))
        infected = (np.asarray(data.node_states, dtype=float) > 0.0).astype(float)
        recovered = np.zeros_like(infected)
        beta = float(params.get("beta", 0.4))
        gamma = float(params.get("gamma", 0.1))
        n_steps = max(1, int(params.get("n_steps", 12)))
        model_type = str(params.get("model_type", "sis")).lower()
        trajectories = [infected.copy()]
        peak = float(np.mean(infected))
        for _ in range(n_steps):
            exposure = adjacency @ infected
            infection_prob = np.clip(beta * exposure, 0.0, 1.0)
            recovery_prob = np.clip(np.full_like(infected, gamma), 0.0, 1.0)
            new_infected = ((rng.uniform(size=infected.shape[0]) < infection_prob) & (infected < 0.5) & (recovered < 0.5)).astype(float)
            recoveries = ((rng.uniform(size=infected.shape[0]) < recovery_prob) & (infected > 0.5)).astype(float)
            infected = np.clip(infected + new_infected - recoveries, 0.0, 1.0)
            if model_type == "sir":
                recovered = np.clip(recovered + recoveries, 0.0, 1.0)
            trajectories.append(infected.copy())
            peak = max(peak, float(np.mean(infected)))
        traj = np.asarray(trajectories, dtype=float)
        return {
            "result": NetworkResult(
                method_name="contagion_model",
                metrics={
                    "final_prevalence": float(np.mean(traj[-1])),
                    "peak_prevalence": peak,
                },
                node_scores=traj[-1],
                state_trajectories=traj,
                metadata={"model_type": model_type, "recovered_share": float(np.mean(recovered))},
            )
        }


@foundry_method(
    namespace="network.multiplex",
    version="1.0.0",
    tags={"network", "multiplex-network"},
)
class MultiplexNetworkEstimator:
    determinism_tier: ClassVar[DeterminismTier] = DeterminismTier.LIBRARY_DETERMINISTIC
    runtime_stack: ClassVar[tuple[str, ...]] = ("numpy",)

    signature: ClassVar[MethodSignature] = MethodSignature(
        name="multiplex_network",
        namespace="placeholder",
        version="0.0.0",
        input_slots=frozenset(
            {
                SlotSpec(
                    "adjacency_layers",
                    SlotType.TENSOR,
                    Unit("network", "weight"),
                    shape=("n_layers", "n_nodes", "n_nodes"),
                ),
            }
        ),
        output_slots=_result_slot(),
        parameters=(),
        fidelity=FidelityLevel.HIGH,
        complexity=ComplexityClass.O_N2,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    metadata: ClassVar[MethodMetadata] = MethodMetadata(
        description="Multiplex network analytics over several adjacency layers.",
        tags=frozenset({"network", "multiplex-network"}),
    )

    @staticmethod
    def materialize_input(bound_inputs: Mapping[str, Any], fallback_state: Any) -> MultiplexNetworkData:
        payload = _multiplex_payload(fallback_state)
        payload.update(bound_inputs)
        return MultiplexNetworkData.model_validate(payload)

    @staticmethod
    def pure_step(state: MultiplexNetworkData, params: Mapping[str, Any]) -> dict[str, Any]:
        del params
        data = state if isinstance(state, MultiplexNetworkData) else MultiplexNetworkData.model_validate(state)
        layers = np.asarray(data.adjacency_layers, dtype=float)
        aggregate = np.mean(layers, axis=0)
        overlap = float(np.mean([np.mean(np.abs(layers[i] - layers[j])) for i in range(layers.shape[0]) for j in range(i + 1, layers.shape[0])]))
        eigvals, eigvecs = np.linalg.eig(_symmetrize(aggregate))
        dominant = np.real(eigvecs[:, int(np.argmax(np.real(eigvals)))])
        dominant = np.abs(dominant)
        if np.sum(dominant) > 0:
            dominant = dominant / np.sum(dominant)
        return {
            "result": NetworkResult(
                method_name="multiplex_network",
                metrics={
                    "mean_interlayer_difference": overlap,
                    "aggregate_density": float(np.mean(aggregate > 0)),
                },
                node_scores=dominant,
                metadata={"aggregate_adjacency": aggregate.tolist()},
            )
        }


__all__ = [
    "CommunityDetectionEstimator",
    "ContagionModelEstimator",
    "InputOutputNetworkEstimator",
    "MultiplexNetworkEstimator",
    "NetworkDiffusionEstimator",
]
