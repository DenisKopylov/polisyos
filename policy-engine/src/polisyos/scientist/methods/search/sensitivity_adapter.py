"""Public search sensitivity adapter module API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polisyos.core.artifacts import ArtifactRef, ArtifactStore

from polisyos.common.serialization import finite_real_scalar
from polisyos.scientist.methods.doe.designs import SensitivityPlan, SensitivityResult
from polisyos.scientist.methods.search.controller import SearchIteration
from polisyos.scientist.methods.search.run_state import _canonical_checkpoint_owner


class SensitivityAwareCandidateGenerator:
    """
    Resolve exploratory sensitivity and activate supported native coordinate ordering.

    Existing generators without the explicit ordering port receive metadata only.
    That bounded path does not claim a proposal or optimization effect.
    """

    def __init__(
        self,
        base_generator: object,
        sensitivity_result: SensitivityResult,
        *,
        focus_top_n: int = 3,
        exploration_factor: float = 1.5,
    ):
        if focus_top_n < 1:
            raise ValueError("focus_top_n must be >= 1")
        if exploration_factor <= 0.0:
            raise ValueError("exploration_factor must be > 0")
        self._base = base_generator
        self._result = sensitivity_result
        self._focus_top_n = focus_top_n
        self._exploration_factor = float(exploration_factor)
        self._focus_parameters = set(sensitivity_result.ranking[:focus_top_n])
        self._analysis_ref: ArtifactRef | None = None
        self._order_profile: str | None = None

    @classmethod
    def from_artifact(
        cls,
        base_generator: object,
        store: ArtifactStore,
        ref: ArtifactRef,
        *,
        focus_top_n: int = 3,
        exploration_factor: float = 1.5,
    ) -> SensitivityAwareCandidateGenerator:
        """Reproduce a persisted exploratory analysis before using its ranking."""
        from polisyos.core.artifacts import ArtifactRef
        from polisyos.scientist.methods.autotune.sensitivity_bridge import read_search_analysis

        ref = ArtifactRef.model_validate(ref)
        if isinstance(base_generator, cls):
            base_generator = base_generator._base
        configure = getattr(base_generator, "configure_sensitivity_order", None)
        result, plan = read_search_analysis(
            store, ref, require_selected_profile=callable(configure)
        )
        instance = cls(
            base_generator,
            result,
            focus_top_n=focus_top_n,
            exploration_factor=exploration_factor,
        )
        instance._analysis_ref = ref
        if callable(configure):
            policy = cls._ordering_policy(result, plan, ref)

            def read_policy():
                current_result, current_plan = read_search_analysis(store, ref)
                return cls._ordering_policy(current_result, current_plan, ref)

            configure(
                policy["parameter_order"],
                analysis_ref=ref,
                analysis_identity=policy["analysis_identity"],
                parameter_basis=policy["parameter_basis"],
                analysis_reader=read_policy,
            )
            instance._order_profile = policy["profile"]
        return instance

    @staticmethod
    def _ordering_policy(
        result: SensitivityResult, plan: SensitivityPlan, ref: ArtifactRef
    ) -> dict[str, Any]:
        if (
            result.failed_runs
            or result.total_runs == 0
            or result.successful_runs != result.total_runs
        ):
            raise ValueError("Sensitivity ordering requires a complete finite experimental basis")
        names = [parameter.name for parameter in plan.parameter_specs]
        if (
            len(result.ranking) != len(names)
            or len(set(result.ranking)) != len(names)
            or set(result.ranking) != set(names)
        ):
            raise ValueError("Sensitivity ranking does not cover the complete parameter basis")
        scores = (
            result.mu_star
            if result.method.value == "morris"
            else result.st
            if result.method.value == "sobol"
            else {}
        )
        if any(finite_real_scalar(scores.get(name)) is None for name in names):
            raise ValueError("Sensitivity ordering requires finite supported effect coordinates")
        return {
            "profile": "exploratory_coordinate_order.v1",
            "parameter_order": list(result.ranking),
            "analysis_ref": ref.model_dump(mode="json"),
            "analysis_identity": {
                key: result.metadata[key] for key in ("design_id", "analysis_id")
            },
            "parameter_basis": [
                {
                    "name": parameter.name,
                    "lower_bound": parameter.lower_bound,
                    "upper_bound": parameter.upper_bound,
                    "unit": parameter.unit,
                    "distribution": parameter.distribution.value,
                    "distribution_spec": parameter.distribution_spec.model_dump(mode="json")
                    if parameter.distribution_spec is not None
                    else None,
                }
                for parameter in plan.parameter_specs
            ],
            "authority_purpose": "exploratory_parameter_experiment",
            "population_law_status": "not_established",
        }

    @property
    def analysis_ref(self) -> ArtifactRef | None:
        return self._analysis_ref

    @property
    def order_profile(self) -> str | None:
        return self._order_profile

    def get_state(self) -> dict[str, Any] | None:
        if not _canonical_checkpoint_owner(self, SensitivityAwareCandidateGenerator):
            return None
        checkpoint = getattr(self._base, "get_state", None)
        if not callable(checkpoint):
            return None
        return checkpoint()

    def validate_checkpoint_history(
        self, history: list[SearchIteration], state: dict[str, Any]
    ) -> None:
        """Retain the base generator's complete consumed-history admission."""
        if not _canonical_checkpoint_owner(self, SensitivityAwareCandidateGenerator):
            raise ValueError("sensitivity_checkpoint_owner_profile_unsupported")
        validate = getattr(self._base, "validate_checkpoint_history", None)
        if not callable(validate):
            raise ValueError("Sensitivity base generator lacks checkpoint history admission")
        validate(history, state)

    def set_state(self, state: dict[str, Any]) -> None:
        if not _canonical_checkpoint_owner(self, SensitivityAwareCandidateGenerator):
            raise ValueError("sensitivity_checkpoint_owner_profile_unsupported")
        restore = getattr(self._base, "set_state", None)
        if not callable(restore):
            raise ValueError("Sensitivity base generator does not support checkpoints")
        restore(state)

    def configure_transfer(self, bridge: Any, fingerprint: Any) -> None:
        configure = getattr(self._base, "configure_transfer", None)
        if not callable(configure):
            raise ValueError("Sensitivity base generator cannot bind configured transfer")
        configure(bridge, fingerprint)

    def _metadata(self) -> dict[str, Any]:
        return {
            "ranking": list(self._result.ranking),
            "focus_parameters": sorted(self._focus_parameters),
            "exploration_factor": self._exploration_factor,
            "method": self._result.method.value,
            "design_id": self._result.metadata.get("design_id"),
            "analysis_id": self._result.metadata.get("analysis_id"),
            "analysis_ref": (
                self._analysis_ref.model_dump(mode="json") if self._analysis_ref else None
            ),
            "authority_purpose": "exploratory_parameter_experiment",
            "population_law_status": "not_established",
            "order_profile": self._order_profile,
            "ranking_consumer": "native_coordinate_order"
            if self._order_profile
            else "metadata_only",
            "manifest_selection": "selected"
            if self._analysis_ref is not None
            and self._analysis_ref.manifest_profile_sha256 is not None
            else "legacy_content_only",
        }

    def generate(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        candidate = self._base.generate(history, current_best, context)
        candidate = dict(candidate)
        candidate["_sensitivity"] = self._metadata()
        return candidate

    def generate_batch(
        self,
        history: list[SearchIteration],
        current_best: dict[str, Any] | None,
        context: dict[str, Any],
        batch_size: int,
    ) -> list[dict[str, Any]]:
        if hasattr(self._base, "generate_batch") and callable(self._base.generate_batch):
            batch = self._base.generate_batch(history, current_best, context, batch_size)
        else:
            batch = [self._base.generate(history, current_best, context) for _ in range(batch_size)]
        return [
            {
                **dict(candidate),
                "_sensitivity": self._metadata(),
            }
            for candidate in batch
        ]
