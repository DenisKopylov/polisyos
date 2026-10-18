"""Public agent sim artifact module API."""

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
from dataclasses import dataclass, field, fields
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from typing import Any, Generic, Literal, TypeVar, get_args, get_type_hints

from polisyos.core.artifacts import ArtifactStore
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import content_hash
from polisyos.foundry.agent_sim.distributions import GiniPopulationProfile
from polisyos.foundry.runtime.fingerprint import (
    DeterminismTier,
    EnvironmentFingerprint,
)

P = TypeVar("P")


@dataclass(frozen=True, slots=True)
class TrainingProfileDescriptor:
    """Describe the fixed source-defined Economics training profile in an artifact."""

    profile: GiniPopulationProfile = GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1
    profile_version: Literal["1"] = "1"
    domain: Literal["economics"] = "economics"
    resource_fields: tuple[Literal["wealth", "income"], Literal["wealth", "income"]] = (
        "wealth",
        "income",
    )
    population: Literal["active"] = "active"
    resource_domain: Literal["finite_nonnegative"] = "finite_nonnegative"
    gini_variant: Literal["classical"] = "classical"
    predicate_source: Literal[
        "polisyos.foundry.agent_sim.distributions.active_gini_population_supported"
    ] = "polisyos.foundry.agent_sim.distributions.active_gini_population_supported"

    def __post_init__(self) -> None:
        """Keep the persisted descriptor bound to the one supported profile."""
        if (
            self.profile is not GiniPopulationProfile.ECONOMICS_ACTIVE_WEALTH_INCOME_V1
            or self.profile_version != "1"
            or self.domain != "economics"
            or self.resource_fields != ("wealth", "income")
            or self.population != "active"
            or self.resource_domain != "finite_nonnegative"
            or self.gini_variant != "classical"
            or self.predicate_source
            != "polisyos.foundry.agent_sim.distributions.active_gini_population_supported"
        ):
            raise ValueError("Unsupported Economics training profile descriptor")

    def to_manifest_dict(self) -> dict[str, Any]:
        """Return the fixed, versioned descriptor payload."""
        return {
            "profile_id": self.profile.value,
            "profile_version": self.profile_version,
            "domain": self.domain,
            "resource_fields": list(self.resource_fields),
            "population": self.population,
            "resource_domain": self.resource_domain,
            "gini_variant": self.gini_variant,
            "predicate_source": self.predicate_source,
        }

    @classmethod
    def from_manifest_dict(cls, value: object) -> TrainingProfileDescriptor:
        """Parse only the exact known descriptor; never infer it from partial data."""
        if type(value) is not dict:
            raise ValueError("Invalid agent policy training profile descriptor")
        expected = cls().to_manifest_dict()
        if value != expected or set(value) != set(expected):
            raise ValueError("Unsupported agent policy training profile descriptor")
        return cls()


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


class _NonFiniteTrainingMetricError(ValueError):
    """A runtime training metric cannot be represented as finite canonical data."""


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

    def is_compatible(self, other: IOShapeSpec) -> bool:
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
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    schema_version: str = "1.0"
    training_profile: TrainingProfileDescriptor | None = None

    def __post_init__(self) -> None:
        """Require the descriptor to agree with the artifact schema version."""
        if (
            self.training_profile is not None
            and type(self.training_profile) is not TrainingProfileDescriptor
        ):
            raise TypeError("training_profile must be a source-defined TrainingProfileDescriptor")
        if self.schema_version == "1.0" and self.training_profile is not None:
            raise ValueError("Schema 1.0 agent policy artifacts cannot carry a training profile")
        if self.schema_version == "1.1" and self.training_profile is None:
            raise ValueError("Schema 1.1 agent policy artifacts require a training profile")
        if self.schema_version not in {"1.0", "1.1"}:
            raise ValueError(f"Unsupported agent policy artifact schema: {self.schema_version}")

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
    ) -> AgentPolicyArtifact[P]:
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
    ) -> AgentPolicyArtifact[P]:
        """Rebuild artifact from a stored manifest dict and weights bytes."""
        schema_version = manifest.get("schema_version", "1.0")
        has_training_profile = "training_profile" in manifest
        if schema_version == "1.0":
            if has_training_profile:
                raise ValueError(
                    "Schema 1.0 agent policy artifacts cannot carry a training profile"
                )
            training_profile = None
        elif schema_version == "1.1":
            if not has_training_profile:
                raise ValueError("Schema 1.1 agent policy artifacts require a training profile")
            training_profile = TrainingProfileDescriptor.from_manifest_dict(
                manifest["training_profile"]
            )
        else:
            raise ValueError(f"Unsupported agent policy artifact schema: {schema_version}")

        if "metrics" not in manifest:
            if schema_version != "1.0":
                raise _InvalidTrainingMetricError(
                    "Schema 1.1 agent policy artifacts require a metrics block."
                )
            # Preserve the historical profileless schema-1.0 read fallback.
            # These compatibility placeholders do not attest observed metrics.
            metrics_data: object = {
                "training_run_id": "unknown",
                "training_steps": 0,
                "final_loss": 0.0,
            }
        else:
            metrics_data = manifest["metrics"]
        if not isinstance(metrics_data, dict):
            raise _InvalidTrainingMetricError("Training metrics must be a mapping.")
        metric_values: dict[str, object] = {}
        for field_name, field_type, optional in _TRAINING_METRIC_FIELDS:
            if field_name not in metrics_data:
                if not optional:
                    raise _InvalidTrainingMetricError(
                        f"Required training metric {field_name!r} is missing."
                    )
                value = None
            else:
                value = metrics_data[field_name]
            metric_values[field_name] = _runtime_training_metric(
                value,
                field_name,
                field_type,
                optional=optional,
            )
        metrics = TrainingMetrics(**metric_values)

        fp_data = manifest.get("fingerprint", {})
        tier_value = fp_data.get("determinism_tier", DeterminismTier.NONDETERMINISTIC.value)
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
            captured_at=fp_data.get("captured_at", datetime.now(UTC).isoformat()),
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
            created_at=manifest.get("created_at", datetime.now(UTC).isoformat()),
            schema_version=schema_version,
            training_profile=training_profile,
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

    def can_hot_swap(self, other: AgentPolicyArtifact) -> bool:
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
        manifest = {
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
        if self.training_profile is not None:
            manifest["training_profile"] = self.training_profile.to_manifest_dict()
        return manifest


def _training_metric_field_contract() -> tuple[tuple[str, type, bool], ...]:
    """Derive each metric's declared scalar type and optionality from TrainingMetrics."""

    annotations = get_type_hints(TrainingMetrics)
    supported_types = {str, int, float}
    result: list[tuple[str, type, bool]] = []
    for metric_field in fields(TrainingMetrics):
        annotation = annotations[metric_field.name]
        union_args = get_args(annotation)
        optional = False
        if annotation in supported_types:
            field_type = annotation
        elif len(union_args) == 2 and type(None) in union_args:
            field_type = next(arg for arg in union_args if arg is not type(None))
            optional = True
            if field_type not in supported_types:
                raise TypeError(
                    f"Unsupported TrainingMetrics field annotation: {metric_field.name}"
                )
        else:
            raise TypeError(f"Unsupported TrainingMetrics field annotation: {metric_field.name}")
        result.append((metric_field.name, field_type, optional))
    return tuple(result)


_TRAINING_METRIC_FIELDS = _training_metric_field_contract()


class _InvalidTrainingMetricError(TypeError):
    """A metric violates its declared required/optional scalar field contract."""


def _canonical_training_metric(
    value: object,
    field_name: str,
    field_type: type,
    *,
    optional: bool,
) -> Decimal | int | str | None:
    """Validate one declared metric and encode float fields for canonical CAS."""

    if value is None:
        if optional:
            return None
        raise _InvalidTrainingMetricError(
            f"Required training metric {field_name!r} cannot be null."
        )
    if field_type is str:
        if not isinstance(value, str):
            raise _InvalidTrainingMetricError(f"Training metric {field_name!r} must be a string.")
        return value
    if field_type is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise _InvalidTrainingMetricError(f"Training metric {field_name!r} must be an integer.")
        return int(value)
    if field_type is float:
        if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
            raise _InvalidTrainingMetricError(
                f"Training metric {field_name!r} must be a real numeric value."
            )
        try:
            canonical_value = Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise _InvalidTrainingMetricError(
                f"Training metric {field_name!r} must be a real numeric value."
            ) from exc
        if not canonical_value.is_finite():
            raise _NonFiniteTrainingMetricError(f"Training metric {field_name!r} must be finite.")
        if not isfinite(float(canonical_value)):
            raise _NonFiniteTrainingMetricError(
                f"Training metric {field_name!r} must be finite as a runtime float."
            )
        return canonical_value
    raise _InvalidTrainingMetricError(
        f"Training metric {field_name!r} has an unsupported declared type."
    )


def _runtime_training_metric(
    value: object,
    field_name: str,
    field_type: type,
    *,
    optional: bool,
) -> float | int | str | None:
    """Validate and restore a manifest scalar to the declared runtime type."""

    if field_type is int and field_name == "training_steps" and isinstance(value, str):
        # Preserve the pre-existing reader's int(...) compatibility for this field only.
        try:
            value = int(value)
        except ValueError as exc:
            raise _InvalidTrainingMetricError(
                "Training metric 'training_steps' must be an integer."
            ) from exc
    canonical_value = _canonical_training_metric(
        value,
        field_name,
        field_type,
        optional=optional,
    )
    if field_type is float:
        return None if canonical_value is None else float(canonical_value)
    return canonical_value


def _manifest_for_cas(artifact: AgentPolicyArtifact) -> dict[str, Any]:
    """Create and validate a canonical-storage copy without changing runtime values."""

    manifest = artifact.to_manifest_dict()
    metrics = manifest["metrics"]
    for field_name, field_type, optional in _TRAINING_METRIC_FIELDS:
        if field_name not in metrics:
            if not optional:
                raise _InvalidTrainingMetricError(
                    f"Required training metric {field_name!r} is missing."
                )
            value = None
        else:
            value = metrics[field_name]
        metrics[field_name] = _canonical_training_metric(
            value,
            field_name,
            field_type,
            optional=optional,
        )
    return manifest


def store_policy_artifact(
    cas: ArtifactStore,
    artifact: AgentPolicyArtifact,
) -> tuple[ArtifactRef, ArtifactRef]:
    """
    Store policy weights and manifest in CAS.

    Float metrics use canonical Decimal values in a manifest-only copy.
    Every declared required/optional metric field is validated before either
    CAS object is written, and runtime artifact values remain unchanged.

    Returns:
        Tuple of (weights_ref, manifest_ref)
    """
    manifest = _manifest_for_cas(artifact)
    weights_ref = cas.put_bytes(
        artifact.weights_bytes,
        PutOptions(
            kind="foundry.agent_policy",
            media_type="application/octet-stream",
        ),
    )
    manifest_ref = cas.put_json(
        manifest,
        PutOptions(
            kind="foundry.agent_policy_manifest",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.foundry.AgentPolicyArtifact",
                version=artifact.schema_version,
            ),
            inputs=[InputRef(artifact_id=weights_ref.artifact_id, role="weights")],
        ),
    )
    return weights_ref, manifest_ref


def load_policy_artifact(
    cas: ArtifactStore,
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
    cas: ArtifactStore,
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

    return AgentPolicyArtifact.from_manifest_dict(manifest_payload, weights_bytes=weights_bytes)


def _load_payload(
    cas: ArtifactStore,
    ref: ArtifactRef | ArtifactID | str,
) -> dict[str, Any]:
    from polisyos.core.artifacts import load_core_json_artifact

    if isinstance(ref, (ArtifactRef, ArtifactID)):
        artifact_reference = ref
    else:
        artifact_reference = ArtifactID.model_validate(ref)

    payload = load_core_json_artifact(cas, artifact_reference)
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
        elif hasattr(policy, "actor_hidden") and hasattr(policy.actor_hidden, "in_features"):
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
