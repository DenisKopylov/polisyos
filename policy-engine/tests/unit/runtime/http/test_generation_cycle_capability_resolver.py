"""Keep the governed capability owner separate from the selected data root."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core.artifacts import FileSystemCAS
from polisyos.data_requirement import compiled_requirements_for_world_slot
from polisyos.runtime.http.services.control import generation_cycle as http_cycle
from polisyos.runtime.http.services.control_registry_providers import (
    resolve_control_registry_providers,
)
from polisyos.runtime.quality.capability_resolver import (
    GOVERNED_CAPABILITY_ROWS_PATH,
    RequirementToCapabilityResolver,
)
from polisyos.runtime.quality.design_problem import DesignProblemAuthorityError
from polisyos.runtime.quality.generation_cycle import (
    GenerationCycleController,
    GenerationCycleError,
)
from polisyos.runtime.quality.open_world_risk import PromotionRuntime
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveCycleBudget,
    build_default_recursive_generation_cycle_controller,
)
from tests._helpers.controlled_candidate_profile import _budget
from tests._helpers.lane01_candidate_problem import labor_candidate_problem
from tests._helpers.runtime_http import _build_registry_providers

CODE_ROOT = Path(__file__).resolve().parents[4]


class _UnusedEvalSafetyVerifier:
    def require_admission(self, *_args: object, **_kwargs: object) -> object:
        raise AssertionError("simulate-only resolver probe called EvalSafety")


def _recursive_budget() -> RecursiveCycleBudget:
    return RecursiveCycleBudget(
        max_depth=0, max_nodes=1, min_cycles_per_leaf=1, max_cycles_per_leaf=1
    )


@pytest.mark.parametrize("selected", [True, False])
def test_registry_preserves_explicit_resolver_without_selecting_a_default(selected: bool) -> None:
    """The existing bundle transports the configured port unchanged, including None."""
    resolver = RequirementToCapabilityResolver.governed_fixture(CODE_ROOT) if selected else None
    base = _build_registry_providers()
    providers = resolve_control_registry_providers(
        connectors=base.connectors,
        source_profiles=base.source_profiles,
        binding_profiles=base.binding_profiles,
        model_profiles=base.model_profiles,
        connectors_factory=lambda: base.connectors,
        capability_resolver=resolver,
    )
    assert providers.capability_resolver is resolver


@pytest.mark.parametrize("invalid", [object(), SimpleNamespace(resolve=object())])
def test_registry_refuses_a_non_callable_resolver_port(invalid: object) -> None:
    with pytest.raises(ValueError, match="capability_resolver_port_invalid"):
        replace(_build_registry_providers(), capability_resolver=invalid)


@pytest.mark.asyncio
@pytest.mark.parametrize("selected", [True, False])
async def test_http_recursive_bridge_reaches_real_labor_compiler_with_explicit_code_owner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    record_property: Any,
    selected: bool,
) -> None:
    """Actual HTTP composition and recursive leaf pass one port to the real compiler.

    The controlled NL compiler supplies a candidate problem. The actual recursive
    controller constructs its production leaf, whose real requirement compiler is
    probed before any numerical work or result is produced.
    """
    data_root = tmp_path / "selected-catalog-data-root"
    data_root.mkdir()
    assert not (data_root / GOVERNED_CAPABILITY_ROWS_PATH).exists()
    resolver = RequirementToCapabilityResolver.governed_fixture(CODE_ROOT) if selected else None
    problem = labor_candidate_problem()
    observations: list[tuple[object, tuple[object, ...]]] = []

    async def compile_candidate_problem(**_kwargs: Any) -> Any:
        return problem

    async def probe_actual_leaf(
        leaf: GenerationCycleController, actual_problem: Any, **_kwargs: Any
    ) -> Any:
        assert actual_problem == problem
        assert leaf._repo_root == data_root.resolve()
        basis = leaf._n7_data_requirement_basis_with_report(
            actual_problem, acquisition_request={"world_slot": "global.unemployment_rate"}
        )
        matches = compiled_requirements_for_world_slot(
            world_slot="global.unemployment_rate",
            specs=basis.specs,
            capability_resolutions=basis.capability_resolutions,
        )
        observations.append((leaf._capability_resolver, matches))
        raise GenerationCycleError("test_http_resolver_compiler_probe_completed")

    monkeypatch.setattr(
        http_cycle, "build_design_problem_from_nl_request", compile_candidate_problem
    )
    monkeypatch.setattr(GenerationCycleController, "run", probe_actual_leaf)
    with pytest.raises(GenerationCycleError, match="test_http_resolver_compiler_probe_completed"):
        await http_cycle.compile_and_run_recursive_generation_cycle(
            raw_request=problem.nl_provenance.raw_request,
            context={},
            model_name="controlled-resolver-model",
            compiler_gateway=None,
            execution_intent="simulate_only",
            root_evaluation_context=None,
            budget_state=_budget(),
            recursive_budget=_recursive_budget(),
            promotion_runtime=PromotionRuntime(store=FileSystemCAS(tmp_path / "cas")),
            eval_safety_verifier=_UnusedEvalSafetyVerifier(),
            repo_root=data_root,
            capability_resolver=resolver,
        )
    assert len(observations) == 1
    actual_resolver, matches = observations[0]
    assert actual_resolver is resolver
    assert len(matches) == (1 if selected else 0)
    governed_source = CODE_ROOT / GOVERNED_CAPABILITY_ROWS_PATH
    record_property(
        "governed_resolver_composition",
        json.dumps(
            {
                "code_owner_source": str(governed_source),
                "code_owner_source_sha256": "sha256:"
                + hashlib.sha256(governed_source.read_bytes()).hexdigest(),
                "capability_index_ref": resolver.capability_index_ref if resolver else None,
                "selected_data_root": str(data_root),
                "data_root_has_governed_index": False,
                "construct": "labor.unemployment_rate",
                "world_slot": "global.unemployment_rate",
                "compiled_requirement_count": len(matches),
                "boundary": "candidate_compiler_probe_no_n4_n5_or_observed_authority",
            },
            sort_keys=True,
        ),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", ["foreign_owner", "omitted_owner", "unexpected_owner"])
async def test_http_custom_controller_refuses_different_resolver_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mismatch: str
) -> None:
    """Equal governed rows do not authorize substituting a different appointed owner."""
    problem = labor_candidate_problem()
    resolver = RequirementToCapabilityResolver.governed_fixture(CODE_ROOT)
    runtime = PromotionRuntime(store=FileSystemCAS(tmp_path / "cas"))
    verifier = _UnusedEvalSafetyVerifier()
    controller_resolver = None if mismatch == "unexpected_owner" else resolver
    selected_resolver = (
        RequirementToCapabilityResolver.governed_fixture(CODE_ROOT)
        if mismatch == "foreign_owner"
        else None
        if mismatch == "omitted_owner"
        else resolver
    )
    controller = build_default_recursive_generation_cycle_controller(
        promotion_runtime=runtime,
        eval_safety_verifier=verifier,
        repo_root=tmp_path,
        capability_resolver=controller_resolver,
    )

    async def compile_candidate_problem(**_kwargs: Any) -> Any:
        return problem

    async def leaf_must_not_run(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("a foreign capability owner reached the recursive leaf")

    monkeypatch.setattr(
        http_cycle, "build_design_problem_from_nl_request", compile_candidate_problem
    )
    monkeypatch.setattr(GenerationCycleController, "run", leaf_must_not_run)
    with pytest.raises(DesignProblemAuthorityError) as raised:
        await http_cycle.compile_and_run_recursive_generation_cycle(
            raw_request=problem.nl_provenance.raw_request,
            context={},
            model_name="controlled-resolver-model",
            compiler_gateway=None,
            execution_intent="simulate_only",
            root_evaluation_context=None,
            budget_state=_budget(),
            recursive_budget=_recursive_budget(),
            promotion_runtime=runtime,
            eval_safety_verifier=verifier,
            repo_root=tmp_path,
            capability_resolver=selected_resolver,
            controller=controller,
        )
    assert raised.value.code == "recursive_controller_capability_resolver_mismatch"
