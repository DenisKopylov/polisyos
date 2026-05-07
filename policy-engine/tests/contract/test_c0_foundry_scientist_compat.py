from __future__ import annotations

from decimal import Decimal

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    FoundryInputBindingRule,
    FoundryInputBindings,
    StateSnapshotRef,
)
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.governance.schedule import ScheduleSpec
from polisyos.ir.governance.selector_expr import SelectorPredicate
from polisyos.ir.model_spec import ModelSpec
from polisyos.ir.observation.bundles import GovernancePassMappingBundle
from polisyos.ir.observation.governance import (
    DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY,
    DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY,
)
from polisyos.ir.trinity import TrinityBundle
from polisyos.ir.types import SelectorOperator
from polisyos.scientist.orchestration.engine.state import ExperimentState


def _artifact_ref(suffix: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + suffix * 64,
        kind="test.artifact",
        media_type="application/json",
    )


def test_legacy_policy_spec_is_still_accepted_by_trinity_bundle() -> None:
    legacy_policy = PolicySpec(
        policy_id="compat_policy",
        interventions=[
            InterventionSpec(
                intervention_id="tax_cut",
                kind="income_tax",
                target=SelectorPredicate(
                    field="id",
                    operator=SelectorOperator.EQUALS,
                    value="all",
                ),
                schedule=ScheduleSpec(start_step=0, duration_steps=1),
                params={"rate": Decimal("0.1")},
            )
        ],
    )

    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="compat_problem", domain=ProblemDomain.FISCAL),
        policy_spec=legacy_policy,
        model_spec=ModelSpec(
            model_id="compat_model",
            data_snapshot_ref="sha256:" + "a" * 64,
            registry_bundle_ref="sha256:" + "b" * 64,
        ),
    )
    assert bundle.policy_spec.interventions[0].identification_mode is None


def test_foundry_input_bindings_and_experiment_state_are_unaffected() -> None:
    bindings = FoundryInputBindings(
        data_snapshot_ref=_artifact_ref("a"),
        registry_bundle_ref=_artifact_ref("b"),
        rules=[
            FoundryInputBindingRule(
                binding_id="bind_income",
                source_path="data.agent_income",
                target_slot_id="agents.income",
            )
        ],
        bound_state_snapshot_ref=StateSnapshotRef(
            artifact_id="sha256:" + "c" * 64,
            kind="foundry.state_snapshot",
            media_type="application/json",
        ),
    )
    state = ExperimentState(run_id="compat_run", inputs={"input_bindings": _artifact_ref("d")})

    assert bindings.rules[0].target_slot_id == "agents.income"
    assert state.run_id == "compat_run"


def test_governance_mapping_bundle_only_uses_resolvable_passes() -> None:
    mapping = GovernancePassMappingBundle(
        family_passes=DEFAULT_OBSERVATION_FAMILY_POLICY_REGISTRY.mandatory_pass_mapping(),
        alias_registry=DEFAULT_GOVERNANCE_PASS_ALIAS_REGISTRY,
    )

    for passes in mapping.family_passes.values():
        for canonical_pass_id in passes:
            alias = mapping.alias_registry.resolve(canonical_pass_id)
            assert alias is not None, f"unresolvable canonical pass id: {canonical_pass_id}"
