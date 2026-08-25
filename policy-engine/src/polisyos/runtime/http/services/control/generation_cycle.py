"""Plain-language front door for the canonical recursive generation cycle."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
from polisyos.runtime.http.services.control.nl_pipeline import (
    build_design_problem_from_nl_request,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.design_problem import (
    DesignProblem,
    DesignProblemAuthorityError,
)
from polisyos.runtime.quality.open_world_risk import (  # noqa: TC001
    OpenWorldRiskPublicLimitation,
)
from polisyos.runtime.quality.promotion_sequence import CanonicalPromotionReceipt
from polisyos.runtime.quality.public_export import (
    PublicExportRedactionError,
    project_promotion_open_world_limitation,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveGenerationCycleRun,
    build_default_recursive_generation_cycle_controller,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from polisyos.runtime.http.services.control.nl_pipeline import (
        _DesignProblemGatewayClient,
        _SpanSupportVerifierClient,
    )
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.runtime.quality.generation_cycle import N4GenerationPort
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from polisyos.runtime.quality.recursive_generation_cycle import (
        RecursiveCycleBudget,
        RecursiveGenerationCycleController,
    )
    from polisyos.scientist import BudgetState

COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION = (
    "policyos.runtime.http.compiled_recursive_generation_cycle.v1"
)


class CompiledRecursiveGenerationCycleRun(BaseModel):
    """Content-bound plain-language problem and its canonical recursive run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    design_problem: DesignProblem
    cycle_substrate_context_ref: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    recursive_run: RecursiveGenerationCycleRun
    open_world_risk_limitations: tuple[OpenWorldRiskPublicLimitation, ...] = Field(
        default=(),
        exclude_if=lambda rows: not rows,
    )
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_bindings(self) -> CompiledRecursiveGenerationCycleRun:
        expected_problem_ref = gy_content_hash(self.design_problem.model_dump(mode="json"))
        if self.design_problem_ref != expected_problem_ref:
            raise ValueError("compiled_recursive_design_problem_hash_mismatch")
        if self.recursive_run.root_design_problem_ref != self.design_problem_ref:
            raise ValueError("compiled_recursive_run_problem_binding_mismatch")
        payload = gy_artifact_self_identity_projection(self)
        recursive_run = dict(payload["recursive_run"])
        recursive_run.pop("leaf_nodes", None)
        payload["recursive_run"] = recursive_run
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("compiled_recursive_generation_cycle_hash_mismatch")
        return self


async def compile_and_run_recursive_generation_cycle(
    *,
    raw_request: str,
    context: Mapping[str, object],
    model_name: str,
    compiler_gateway: _DesignProblemGatewayClient,
    controller: RecursiveGenerationCycleController | None = None,
    budget_state: BudgetState,
    recursive_budget: RecursiveCycleBudget,
    span_support_client: _SpanSupportVerifierClient | None = None,
    cycle_substrate_context: CycleSubstrateContext | None = None,
    root_n4_generation_port: N4GenerationPort | None = None,
    promotion_runtime: PromotionRuntime | None = None,
    repo_root: Path | None = None,
) -> CompiledRecursiveGenerationCycleRun:
    """Compile arbitrary plain language and route it through the depth-N owner."""

    if promotion_runtime is None:
        raise DesignProblemAuthorityError(
            "promotion_runtime_not_established",
            "The production composition requires its container-owned promotion runtime.",
        )
    problem = await build_design_problem_from_nl_request(
        nl_request=raw_request,
        context=context,
        model_name=model_name,
        gateway_client=compiler_gateway,
        span_support_client=span_support_client,
    )
    if problem.nl_provenance.raw_request != raw_request:
        raise DesignProblemAuthorityError(
            "cycle_plain_language_content_mismatch",
            "compiled DesignProblem does not preserve the caller's raw request",
        )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    if (
        cycle_substrate_context is not None
        and cycle_substrate_context.design_problem_ref != problem_ref
    ):
        raise DesignProblemAuthorityError(
            "cycle_substrate_design_problem_mismatch",
            "CycleSubstrateContext must be content-bound to the compiled DesignProblem",
        )
    if cycle_substrate_context is not None:
        from polisyos.runtime.quality.cycle_substrate import (
            revalidate_cycle_substrate_context,
        )

        revalidate_cycle_substrate_context(cycle_substrate_context)

    resolved_controller = controller or build_default_recursive_generation_cycle_controller(
        repo_root=repo_root,
        model_id=model_name,
        promotion_runtime=promotion_runtime,
    )

    root_ref = f"design-problem://{problem_ref.removeprefix('sha256:')}"
    recursive_graph = derive_recursive_design_graph(
        design_ref=root_ref,
        module_refs=(),
        parent_child_edges=(),
        rule_version_ref="polisyos.runtime.recursive_generation_cycle.v1",
    )
    recursive_run = await resolved_controller.run(
        recursive_graph,
        problems_by_node={root_ref: problem},
        budget_state=budget_state,
        recursive_budget=recursive_budget,
        cycle_substrate_contexts_by_node=(
            {root_ref: cycle_substrate_context} if cycle_substrate_context is not None else None
        ),
        n4_generation_ports_by_node=(
            {root_ref: root_n4_generation_port} if root_n4_generation_port is not None else None
        ),
    )
    limitations: list[OpenWorldRiskPublicLimitation] = []
    seen_vector_refs: set[str] = set()
    for leaf in recursive_run.leaf_nodes:
        cycle_run = leaf.cycle_run
        if cycle_run is None:  # pragma: no cover - enforced by RecursiveCycleNode
            continue
        for receipt_payload in cycle_run.promotion_port.receipts:
            try:
                receipt = CanonicalPromotionReceipt.model_validate(receipt_payload)
            except ValueError as exc:
                raise PublicExportRedactionError(
                    "promotion_receipt_invalid",
                    str(exc),
                ) from exc
            if promotion_runtime is None:
                raise PublicExportRedactionError("open_world_resolver_not_established")
            limitation = project_promotion_open_world_limitation(
                run=cycle_run,
                design_problem=problem,
                receipt=receipt,
                resolver=promotion_runtime.resolver,
                repo_root=repo_root,
            )
            if limitation is None:
                continue
            vector_key = str(limitation.vector_artifact_ref.artifact_id)
            if vector_key in seen_vector_refs:
                raise PublicExportRedactionError("open_world_projection_duplicate")
            seen_vector_refs.add(vector_key)
            limitations.append(limitation)
    payload = {
        "schema_version": COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
        "design_problem_ref": problem_ref,
        "design_problem": problem.model_dump(mode="json"),
        "cycle_substrate_context_ref": (
            cycle_substrate_context.content_hash if cycle_substrate_context is not None else None
        ),
        "recursive_run": recursive_run.model_dump(
            mode="json",
            exclude={"leaf_nodes"},
        ),
    }
    if limitations:
        payload["open_world_risk_limitations"] = tuple(
            row.model_dump(mode="json") for row in limitations
        )
    return CompiledRecursiveGenerationCycleRun.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )


__all__ = [
    "COMPILED_RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION",
    "CompiledRecursiveGenerationCycleRun",
    "compile_and_run_recursive_generation_cycle",
]
