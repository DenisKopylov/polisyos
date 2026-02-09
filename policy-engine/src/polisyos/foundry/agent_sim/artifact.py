from __future__ import annotations

"""
Immutable, content-addressable artifacts for trained agent policies.

Example:
    artifact = AgentPolicyArtifact.from_trained_policy(
        policy=trained_actor_critic,
        run_id="run_20240127_001",
        steps=10000,
        loss=0.023,
        fingerprint=EnvironmentFingerprint.capture(
            tier=DeterminismTier.BEST_EFFORT_GPU,
            seed=42,
        ),
    )
"""

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import content_hash, from_canonical_bytes
from polisyos.foundry.runtime.fingerprint import (
    DeterminismTier,
    EnvironmentFingerprint,
)

P = TypeVar("P")


@dataclass
class TrainingMetrics:
    """
    Training provenance information bundled with artifact.

    Captures essential metrics for audit trail and comparison.
    """

    training_run_id: str
    training_steps: int
    final_loss: float
    best_loss: float | None = None

    total_episodes: int | None = None
    wall_clock_seconds: float | None = None
    gpu_hours: float | None = None

    learning_rate: float | None = None
    batch_size: int | None = None
    ppo_epochs: int | None = None


@dataclass
class IOShapeSpec:
    """
    Input/output shape specification for compatibility checking.

    Enables safe hot-swap: new policy must have matching I/O shapes.
    """

    input_shape: tuple[int, ...]
    output_shape: tuple[int, ...]

    observation_keys: list[str] | None = None
    action_type: str = "continuous"
    action_dim: int | None = None

    def is_compatible(self, other: "IOShapeSpec") -> bool:
        """Check if two specs are compatible for hot-swap."""
        if (
            self.input_shape != other.input_shape
            or self.output_shape != other.output_shape
            or self.action_type != other.action_type
        ):
            return False
        if self.action_dim is None or other.action_dim is None:
            return True
        return self.action_dim == other.action_dim


@dataclass
class AgentPolicyArtifact(Generic[P]):
    """
    Immutable artifact for trained agent policy.

    Stored in Content-Addressable Storage (CAS) with full provenance:
    - WHO trained it (run ID)
    - WHAT the result was (weights, loss)
    - WHERE it was trained (environment fingerprint)
    - HOW to use it (I/O shapes)
    """

    artifact_id: str
    policy_type: str

    weights_bytes: bytes
    weights_hash: str

    metrics: TrainingMetrics
    fingerprint: EnvironmentFingerprint
    io_spec: IOShapeSpec

    serialization_format: str = "equinox_v1"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    schema_version: str = "1.0"

    @classmethod
    def from_trained_policy(
        cls,
        policy: P,
        run_id: str,
        steps: int,
        loss: float,
        fingerprint: EnvironmentFingerprint,
        *,
        best_loss: float | None = None,
        extended_metrics: dict[str, Any] | None = None,
    ) -> "AgentPolicyArtifact[P]":
        """
        Create artifact from a freshly trained Equinox policy.

        Raises:
            ValueError: If serialization fails.
        """
        import equinox as eqx

        buffer = io.BytesIO()
        try:
            eqx.tree_serialise_leaves(buffer, policy)
        except Exception as exc:
            raise ValueError(f"Failed to serialize policy: {exc}") from exc

        weights_bytes = buffer.getvalue()
        weights_hash = content_hash(weights_bytes)

        io_spec = _extract_io_spec(policy)

        ext = extended_metrics or {}
        metrics = TrainingMetrics(
            training_run_id=run_id,
            training_steps=steps,
            final_loss=loss,
            best_loss=best_loss,
            total_episodes=ext.get("total_episodes"),
            wall_clock_seconds=ext.get("wall_clock_seconds"),
            gpu_hours=ext.get("gpu_hours"),
            learning_rate=ext.get("learning_rate"),
            batch_size=ext.get("batch_size"),
            ppo_epochs=ext.get("ppo_epochs"),
        )

        return cls(
            artifact_id=f"policy_{weights_hash[:16]}",
            policy_type=type(policy).__name__,
            weights_bytes=weights_bytes,
            weights_hash=weights_hash,
            metrics=metrics,
            fingerprint=fingerprint,
            io_spec=io_spec,
        )

    @classmethod
    def from_manifest_dict(
        cls,
        manifest: dict[str, Any],
        *,
        weights_bytes: bytes,
    ) -> "AgentPolicyArtifact[P]":
        """Rebuild artifact from a stored manifest dict and weights bytes."""
        metrics_data = manifest.get("metrics", {})
        metrics = TrainingMetrics(
            training_run_id=metrics_data.get("training_run_id", "unknown"),
            training_steps=int(metrics_data.get("training_steps", 0)),
            final_loss=float(metrics_data.get("final_loss", 0.0)),
            best_loss=metrics_data.get("best_loss"),
            total_episodes=metrics_data.get("total_episodes"),
            wall_clock_seconds=metrics_data.get("wall_clock_seconds"),
            gpu_hours=metrics_data.get("gpu_hours"),
            learning_rate=metrics_data.get("learning_rate"),
            batch_size=metrics_data.get("batch_size"),
            ppo_epochs=metrics_data.get("ppo_epochs"),
        )

        fp_data = manifest.get("fingerprint", {})
        tier_value = fp_data.get(
            "determinism_tier", DeterminismTier.NONDETERMINISTIC.value
        )
        try:
            tier = DeterminismTier(tier_value)
        except ValueError:
            tier = DeterminismTier.NONDETERMINISTIC
        fingerprint = EnvironmentFingerprint(
            python_version=fp_data.get("python_version", "unknown"),
            platform_system=fp_data.get("platform_system", "unknown"),
            platform_machine=fp_data.get("platform_machine", "unknown"),
            jax_version=fp_data.get("jax_version", "unknown"),
            jaxlib_version=fp_data.get("jaxlib_version", "unknown"),
            xla_flags=fp_data.get("xla_flags", ""),
            x64_enabled=bool(fp_data.get("x64_enabled", False)),
            deterministic_ops=bool(fp_data.get("deterministic_ops", False)),
            cpu_count=int(fp_data.get("cpu_count", 1)),
            cuda_version=fp_data.get("cuda_version"),
            cudnn_version=fp_data.get("cudnn_version"),
            device_name=fp_data.get("device_name"),
            determinism_tier=tier,
            random_seed=int(fp_data.get("random_seed", 0)),
            captured_at=fp_data.get(
                "captured_at", datetime.now(timezone.utc).isoformat()
            ),
        )

        io_data = manifest.get("io_spec", {})
        input_shape = tuple(io_data.get("input_shape") or ())
        output_shape = tuple(io_data.get("output_shape") or ())
        io_spec = IOShapeSpec(
            input_shape=input_shape,
            output_shape=output_shape,
            observation_keys=io_data.get("observation_keys"),
            action_type=io_data.get("action_type", "continuous"),
            action_dim=io_data.get("action_dim"),
        )

        weights_hash = manifest.get("weights_hash") or content_hash(weights_bytes)

        return cls(
            artifact_id=manifest.get("artifact_id", f"policy_{weights_hash[:16]}"),
            policy_type=manifest.get("policy_type", "UnknownPolicy"),
            weights_bytes=weights_bytes,
            weights_hash=weights_hash,
            serialization_format=manifest.get("serialization_format", "equinox_v1"),
            metrics=metrics,
            fingerprint=fingerprint,
            io_spec=io_spec,
            created_at=manifest.get(
                "created_at", datetime.now(timezone.utc).isoformat()
            ),
            schema_version=manifest.get("schema_version", "1.0"),
        )

    def load_weights(self, model_skeleton: P) -> P:
        """
        Load weights into a model skeleton.

        Args:
            model_skeleton: Uninitialized model with matching structure.

        Raises:
            ValueError: If structure doesn't match.
        """
        import equinox as eqx

        buffer = io.BytesIO(self.weights_bytes)
        try:
            loaded = eqx.tree_deserialise_leaves(buffer, model_skeleton)
        except Exception as exc:
            raise ValueError(
                "Failed to deserialize weights into skeleton. "
                f"Artifact type: {self.policy_type}, "
                f"Skeleton type: {type(model_skeleton).__name__}. "
                f"Error: {exc}"
            ) from exc

        return loaded

    def can_hot_swap(self, other: "AgentPolicyArtifact") -> bool:
        """Check if another policy can safely replace this one at runtime."""
        if self.policy_type != other.policy_type:
            return False
        return self.io_spec.is_compatible(other.io_spec)

    def validate_environment(
        self,
        current: EnvironmentFingerprint,
        min_score: float = 0.7,
    ) -> tuple[bool, float, list[str]]:
        """
        Validate current environment against artifact's training environment.

        Returns:
            Tuple of (is_valid, score, warnings)
        """
        score = self.fingerprint.compatibility_score(current)
        warnings: list[str] = []

        if score < min_score:
            warnings.append(
                f"Environment compatibility score {score:.2f} below threshold {min_score}"
            )

        if self.fingerprint.platform_machine != current.platform_machine:
            warnings.append(
                "Architecture mismatch: trained on "
                f"{self.fingerprint.platform_machine}, running on "
                f"{current.platform_machine}"
            )

        if self.fingerprint.jax_version != current.jax_version:
            warnings.append(
                "JAX version mismatch: trained with "
                f"{self.fingerprint.jax_version}, running with "
                f"{current.jax_version}"
            )

        if self.fingerprint.determinism_tier != current.determinism_tier:
            warnings.append(
                "Determinism tier mismatch: trained with "
                f"{self.fingerprint.determinism_tier.value}, running with "
                f"{current.determinism_tier.value}"
            )

        return score >= min_score, score, warnings

    def to_manifest_dict(self) -> dict[str, Any]:
        """Export artifact metadata as dict for CAS manifest storage."""
        return {
            "schema_version": self.schema_version,
            "artifact_id": self.artifact_id,
            "policy_type": self.policy_type,
            "weights_hash": self.weights_hash,
            "serialization_format": self.serialization_format,
            "created_at": self.created_at,
            "metrics": {
                "training_run_id": self.metrics.training_run_id,
                "training_steps": self.metrics.training_steps,
                "final_loss": self.metrics.final_loss,
                "best_loss": self.metrics.best_loss,
                "total_episodes": self.metrics.total_episodes,
                "wall_clock_seconds": self.metrics.wall_clock_seconds,
                "gpu_hours": self.metrics.gpu_hours,
                "learning_rate": self.metrics.learning_rate,
                "batch_size": self.metrics.batch_size,
                "ppo_epochs": self.metrics.ppo_epochs,
            },
            "fingerprint": {
                "python_version": self.fingerprint.python_version,
                "platform_system": self.fingerprint.platform_system,
                "platform_machine": self.fingerprint.platform_machine,
                "jax_version": self.fingerprint.jax_version,
                "jaxlib_version": self.fingerprint.jaxlib_version,
                "xla_flags": self.fingerprint.xla_flags,
                "x64_enabled": self.fingerprint.x64_enabled,
                "deterministic_ops": self.fingerprint.deterministic_ops,
                "cpu_count": self.fingerprint.cpu_count,
                "cuda_version": self.fingerprint.cuda_version,
                "cudnn_version": self.fingerprint.cudnn_version,
                "device_name": self.fingerprint.device_name,
                "determinism_tier": self.fingerprint.determinism_tier.value,
                "random_seed": self.fingerprint.random_seed,
                "captured_at": self.fingerprint.captured_at,
                "env_hash": self.fingerprint.compute_hash(),
            },
            "io_spec": {
                "input_shape": list(self.io_spec.input_shape),
                "output_shape": list(self.io_spec.output_shape),
                "observation_keys": self.io_spec.observation_keys,
                "action_type": self.io_spec.action_type,
                "action_dim": self.io_spec.action_dim,
            },
        }


def store_policy_artifact(
    cas: FileSystemCAS,
    artifact: AgentPolicyArtifact,
) -> tuple[ArtifactRef, ArtifactRef]:
    """
    Store policy weights and manifest in CAS.

    Returns:
        Tuple of (weights_ref, manifest_ref)
    """
    weights_ref = cas.put_bytes(
        artifact.weights_bytes,
        PutOptions(
            kind="foundry.agent_policy",
            media_type="application/octet-stream",
        ),
    )
    manifest_ref = cas.put_json(
        artifact.to_manifest_dict(),
        PutOptions(
            kind="foundry.agent_policy_manifest",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.AgentPolicyArtifact", version="1.0"),
            inputs=[InputRef(artifact_id=weights_ref.artifact_id, role="weights")],
        ),
    )
    return weights_ref, manifest_ref


def load_policy_artifact(
    cas: FileSystemCAS,
    manifest_ref: ArtifactRef | ArtifactID | str,
    model_skeleton: P,
    current_tier: DeterminismTier,
    current_seed: int,
    *,
    min_compatibility: float = 0.7,
    strict: bool = False,
) -> tuple[P, list[str]]:
    """
    Load a policy artifact with environment validation.

    Raises:
        ValueError: If strict=True and compatibility below threshold.
        ValueError: If artifact not found or corrupted.
    """
    artifact = _load_artifact_from_cas(cas, manifest_ref)

    current_env = EnvironmentFingerprint.capture(current_tier, current_seed)
    is_valid, score, warnings = artifact.validate_environment(
        current_env, min_score=min_compatibility
    )

    if not is_valid:
        msg = (
            f"Environment compatibility {score:.2f} below threshold {min_compatibility}. "
            f"Warnings: {warnings}"
        )
        if strict:
            raise ValueError(msg)
        from polisyos.common.logger import get_logger

        get_logger(__name__).warning(msg)

    loaded_policy = artifact.load_weights(model_skeleton)
    return loaded_policy, warnings


def _load_artifact_from_cas(
    cas: FileSystemCAS,
    manifest_ref: ArtifactRef | ArtifactID | str,
) -> AgentPolicyArtifact:
    manifest_payload = _load_payload(cas, manifest_ref)
    if not isinstance(manifest_payload, dict):
        raise ValueError("Invalid agent policy manifest payload")

    weights_hash = manifest_payload.get("weights_hash")
    if not isinstance(weights_hash, str) or not weights_hash:
        raise ValueError("Agent policy manifest missing weights_hash")

    weights_bytes = cas.get_bytes(ArtifactID.from_sha256_hex(weights_hash))
    actual_hash = content_hash(weights_bytes)
    if actual_hash != weights_hash:
        raise ValueError("Weights hash mismatch for agent policy artifact")

    return AgentPolicyArtifact.from_manifest_dict(
        manifest_payload, weights_bytes=weights_bytes
    )


def _load_payload(
    cas: FileSystemCAS,
    ref: ArtifactRef | ArtifactID | str,
) -> dict[str, Any]:
    if isinstance(ref, ArtifactRef):
        artifact_id = ref.artifact_id
    elif isinstance(ref, ArtifactID):
        artifact_id = ref
    else:
        artifact_id = ArtifactID.model_validate(ref)

    payload = from_canonical_bytes(cas.get_bytes(artifact_id))
    if isinstance(payload, dict):
        return payload
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    raise ValueError("Unsupported artifact manifest payload")


def _extract_io_spec(policy: Any) -> IOShapeSpec:
    """
    Extract I/O specification from an Equinox policy.

    Handles ActorCritic and common RL architectures.
    """
    input_shape = getattr(policy, "input_shape", None)
    output_shape = getattr(policy, "output_shape", None)
    action_type = getattr(policy, "action_type", "continuous")
    action_dim = getattr(policy, "action_dim", None)

    if input_shape is None:
        shared = getattr(policy, "shared", None)
        layers = getattr(shared, "layers", None)
        if layers:
            first_layer = layers[0]
            if hasattr(first_layer, "in_features"):
                input_shape = (int(first_layer.in_features),)
        elif hasattr(policy, "actor_hidden") and hasattr(
            policy.actor_hidden, "in_features"
        ):
            input_shape = (int(policy.actor_hidden.in_features),)

    if output_shape is None:
        if hasattr(policy, "actor") and hasattr(policy.actor, "layers"):
            last_layer = policy.actor.layers[-1]
            if hasattr(last_layer, "out_features"):
                output_shape = (int(last_layer.out_features),)
        elif hasattr(policy, "actor_out") and hasattr(policy.actor_out, "out_features"):
            output_shape = (int(policy.actor_out.out_features),)
        elif action_dim is not None:
            output_shape = (int(action_dim),)

    return IOShapeSpec(
        input_shape=input_shape or (),
        output_shape=output_shape or (),
        action_type=action_type,
        action_dim=int(action_dim) if action_dim is not None else None,
    )
