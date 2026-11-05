"""Keep the served generic-root N4 port's client across prefetched reuse.

This is a wiring test for candidate-only N4 generation. It makes no claim about
root scope, authority, or header validation.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest


@pytest.mark.asyncio
async def test_prefetched_root_port_forwards_same_client_after_cycle_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Consume the actual cycle-zero organ, then preserve its client on cycle one."""
    from polisyos.pdc import gy_content_hash
    from polisyos.runtime.http.services.control.generation_cycle import (
        _generic_root_n4_generation_port,
    )
    from polisyos.runtime.quality import design_generation
    from polisyos.runtime.quality.design_generation import (
        DesignGenerationOrganRun,
        GenerationUnderAResult,
    )
    from polisyos.scientist.orchestration.llm import factory as llm_factory
    from tests.unit.runtime.quality.test_cycle_substrate import _cycle_context
    from tests.unit.runtime.quality.test_generation_cycle import (
        _controlled_declared_n4_child_inputs,
    )

    problem, result = _controlled_declared_n4_child_inputs()
    assert type(result) is GenerationUnderAResult
    problem_ref = result.design_problem_ref
    assert problem_ref == gy_content_hash(problem.model_dump(mode="json"))
    context = _cycle_context(domain=problem.domain, design_problem_ref=problem_ref)
    model_id = result.model_id
    prefetched_organ = replace(result.as_organ_run(), cycle_substrate_context=context)
    generated_organ = result.as_organ_run()
    original_client = object()
    lower_boundary_calls: list[dict[str, Any]] = []

    async def observe_lowest_n4_boundary(
        design_problem: object,
        **kwargs: Any,
    ) -> DesignGenerationOrganRun:
        assert design_problem == problem
        assert kwargs["llm_client"] is original_client
        assert kwargs["cycle_substrate_context"] is context
        assert kwargs["model_id"] == model_id
        assert kwargs["candidate_proposal_only"] is False
        lower_boundary_calls.append(dict(kwargs))
        return generated_organ

    def forbid_gateway_client_creation(**_kwargs: Any) -> None:
        raise AssertionError("prefetched_root_recreated_traced_gateway_client")

    monkeypatch.setattr(
        design_generation,
        "_generate_design_candidate_bundle_under_a",
        observe_lowest_n4_boundary,
    )
    monkeypatch.setattr(
        llm_factory,
        "create_traced_gateway_client",
        forbid_gateway_client_creation,
    )

    port = _generic_root_n4_generation_port(
        model_id=model_id,
        llm_client=original_client,
        repo_root=None,
        cycle_substrate_context=context,
        prefetched_organ_run=prefetched_organ,
    )

    cycle_zero = await port(problem, cycle_index=0)
    assert type(cycle_zero) is DesignGenerationOrganRun
    assert cycle_zero is prefetched_organ
    assert port._prefetched_organ_run is None
    assert lower_boundary_calls == []

    cycle_one = await port(problem, cycle_index=1)
    assert type(cycle_one) is DesignGenerationOrganRun
    assert cycle_one is not prefetched_organ
    assert cycle_one.result is generated_organ.result
    assert cycle_one.cycle_substrate_context is context
    assert len(lower_boundary_calls) == 1
    assert lower_boundary_calls[0]["llm_client"] is original_client
