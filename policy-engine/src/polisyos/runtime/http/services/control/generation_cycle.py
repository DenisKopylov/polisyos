"""Plain-language front door for the canonical recursive generation cycle."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import artifacts, canon
from polisyos.pdc import gy_artifact_self_identity_projection, gy_content_hash
from polisyos.runtime.http.resilience import GuardedDependencyProxy
from polisyos.runtime.http.services.control.nl_pipeline import (
    build_design_problem_from_nl_request,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    derive_recursive_design_graph,
)
from polisyos.runtime.quality.design_axes.value_choice_provenance import (
    NORMATIVE_GENERATION_SOURCE_KIND,
    NormativeAuthorityTrust,
    NormativeGenerationBinding,
    NormativeGenerationDisposition,
    NormativeGenerationEvidenceRefs,
    NormativeValueScheduleOwner,
    P20NormativeChoiceError,
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
    project_pre_n9_open_world_limitations,
    project_promotion_open_world_limitation,
)
from polisyos.runtime.quality.recursive_generation_cycle import (
    RecursiveGenerationCycleRun,
    build_default_recursive_generation_cycle_controller,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime
    from pathlib import Path

    from polisyos.runtime.http.services.control.nl_pipeline import (
        _DesignProblemGatewayClient,
        _SpanSupportVerifierClient,
    )
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.runtime.quality.evaluation_safety import (
        EvalSafetyVerifierPort,
        EvaluationExecutionContext,
    )
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
NORMATIVE_RUN_DISPOSITION_KIND = "runtime.normative_generation_composition"
NORMATIVE_RUN_DISPOSITION_SCHEMA = "policyos.normative_generation_composition.v1"


class NormativeRunEvidenceRefs(BaseModel):
    """Data-only external evidence references, keyed by the actual source node."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    by_node: dict[str, NormativeGenerationEvidenceRefs] = Field(default_factory=dict)
    input_limitation: (
        Literal[
            "p20_normative_evidence_invalid",
            "p20_normative_generation_disposition_missing",
            "p20_normative_sidecar_replay_failed",
        ]
        | None
    ) = None


def parse_normative_run_evidence(value: object) -> NormativeRunEvidenceRefs | None:
    """Keep malformed external evidence as a typed refusal instead of silently dropping it."""
    if value is None:
        return None
    try:
        return NormativeRunEvidenceRefs.model_validate(value)
    except ValueError:
        return NormativeRunEvidenceRefs(input_limitation="p20_normative_evidence_invalid")


class NormativeRunStrangleReceipt(BaseModel):
    """Run-emitted witness reconciling every source leaf with the required S8 result."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    status: Literal["strangled"] = "strangled"
    default_entrypoint: Literal["ControlPlaneService.resolve_generation_value_choices"] = (
        "ControlPlaneService.resolve_generation_value_choices"
    )
    predecessor: Literal["compiled_run_completion_without_normative_disposition"] = (
        "compiled_run_completion_without_normative_disposition"
    )
    default_flipped: Literal[True] = True
    compiled_run_ref: str
    source_node_refs: tuple[str, ...]
    disposition_node_refs: tuple[str, ...]


class NormativeRunDisposition(BaseModel):
    """Current compiled-owner projection; subordinate S8 leaves claim no compiled membership."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["policyos.normative_generation_composition.v1"] = (
        NORMATIVE_RUN_DISPOSITION_SCHEMA
    )
    compiled_run_ref: str
    leaf_disposition_refs: dict[str, str]
    leaf_dispositions: dict[str, NormativeGenerationDisposition]
    authorization_status: Literal["authorized", "blocked"]
    ranked_recommendations: tuple[str, ...]
    strangle_receipt: NormativeRunStrangleReceipt
    disposition_ref: str | None = Field(default=None, exclude=True)


def normative_owner_for_runtime_store(
    store: object, trust: NormativeAuthorityTrust
) -> NormativeValueScheduleOwner:
    """Reuse the canonical ambient filesystem target, preserving tenant ownership checks."""
    target = store._target if type(store) is GuardedDependencyProxy else store
    if type(target) is not artifacts.FileSystemCAS:
        raise P20NormativeChoiceError("p20_normative_signed_store_unavailable")
    return NormativeValueScheduleOwner(store=target, trust=trust)


def _read_normative_source(
    store: artifacts.ArtifactStore, ref: str, *, kind: str
) -> dict[str, object]:
    artifact_id = artifacts.ArtifactID.model_validate(ref)
    raw = store.get_bytes(artifact_id)
    manifest = store.get_manifest(artifact_id)
    if ref != f"sha256:{canon.content_hash(raw)}" or manifest.kind != kind:
        raise P20NormativeChoiceError("p20_normative_compiled_source_mismatch")
    payload = canon.from_canonical_bytes(raw)
    if not isinstance(payload, dict):
        raise P20NormativeChoiceError("p20_normative_compiled_source_invalid")
    return payload


def _normative_generation_sources(
    store: artifacts.ArtifactStore, compiled_run_ref: str, *, persist: bool
) -> dict[str, NormativeGenerationBinding]:
    from polisyos.runtime.quality.generation_cycle import GENERATION_CYCLE_SCHEMA_VERSION

    compiled = CompiledRecursiveGenerationCycleRun.model_validate(
        _read_normative_source(
            store, compiled_run_ref, kind="runtime.compiled_recursive_generation_cycle"
        )
    )
    sources = {}
    for node in compiled.recursive_run.leaf_nodes:
        if node.cycle_run is None or node.node_ref in sources:
            raise P20NormativeChoiceError("p20_normative_compiled_leaf_invalid")
        payload = node.cycle_run.model_dump(mode="json")
        raw = canon.to_canonical_bytes(payload, canon.CanonSpec(forbid_floats=False))
        source_ref = f"sha256:{canon.content_hash(raw)}"
        if persist:
            emitted = store.put_json(
                payload,
                artifacts.PutOptions(
                    kind=NORMATIVE_GENERATION_SOURCE_KIND,
                    media_type="application/json",
                    schema=artifacts.SchemaInfo(
                        name=NORMATIVE_GENERATION_SOURCE_KIND,
                        version=GENERATION_CYCLE_SCHEMA_VERSION,
                    ),
                ),
                canon_spec=canon.CanonSpec(forbid_floats=False),
            )
            if str(emitted.artifact_id) != source_ref:
                raise P20NormativeChoiceError("p20_normative_leaf_persistence_mismatch")
        else:
            stored = _read_normative_source(
                store, source_ref, kind=NORMATIVE_GENERATION_SOURCE_KIND
            )
            if stored != payload:
                raise P20NormativeChoiceError("p20_normative_compiled_leaf_mismatch")
        sources[node.node_ref] = NormativeGenerationBinding(
            compiled_run_ref=compiled_run_ref, source_run_ref=source_ref, node_ref=node.node_ref
        )
    if not sources:
        raise P20NormativeChoiceError("p20_normative_compiled_leaf_population_empty")
    return sources


def _project_normative_composition(
    *,
    store: artifacts.ArtifactStore,
    owner: NormativeValueScheduleOwner,
    compiled_run_ref: str,
    leaf_refs: dict[str, str],
    evaluated_at: datetime,
) -> NormativeRunDisposition:
    sources = _normative_generation_sources(store, compiled_run_ref, persist=False)
    if set(sources) != set(leaf_refs):
        raise P20NormativeChoiceError("p20_normative_compiled_leaf_population_mismatch")
    leaves = {}
    for node_ref, source in sources.items():
        leaf = owner.project_generation_disposition(leaf_refs[node_ref], evaluated_at=evaluated_at)
        if leaf.generation_binding != source:
            raise P20NormativeChoiceError("p20_normative_compiled_leaf_binding_mismatch")
        leaves[node_ref] = leaf
    authorized = all(leaf.authorization_status == "authorized" for leaf in leaves.values())
    return NormativeRunDisposition(
        compiled_run_ref=compiled_run_ref,
        leaf_disposition_refs=leaf_refs,
        leaf_dispositions=leaves,
        authorization_status="authorized" if authorized else "blocked",
        # A mixed composition cannot silently turn a partial selection into a run recommendation.
        ranked_recommendations=tuple(
            choice for leaf in leaves.values() for choice in leaf.ranked_recommendations
        )
        if authorized
        else (),
        strangle_receipt=NormativeRunStrangleReceipt(
            compiled_run_ref=compiled_run_ref,
            source_node_refs=tuple(sorted(sources)),
            disposition_node_refs=tuple(sorted(leaves)),
        ),
    )


def produce_normative_run_disposition(
    *,
    store: artifacts.ArtifactStore,
    owner: NormativeValueScheduleOwner,
    compiled_run_ref: str,
    evidence: NormativeRunEvidenceRefs | None,
    evaluated_at: datetime,
) -> NormativeRunDisposition:
    """Default production bridge from current compiled CAS bytes to every S8 leaf."""
    sources = _normative_generation_sources(store, compiled_run_ref, persist=True)
    by_node = evidence.by_node if evidence else {}
    limitation = evidence.input_limitation if evidence else None
    if not set(by_node).issubset(sources):
        limitation = "p20_normative_evidence_node_mismatch"
    leaf_refs = {
        node_ref: owner.produce_generation_disposition(
            binding=binding,
            evidence=by_node.get(node_ref),
            evaluated_at=evaluated_at,
            input_limitation=limitation,
        )
        for node_ref, binding in sources.items()
    }
    projection = _project_normative_composition(
        store=store,
        owner=owner,
        compiled_run_ref=compiled_run_ref,
        leaf_refs=leaf_refs,
        evaluated_at=evaluated_at,
    )
    ref = store.put_json(
        projection.model_dump(mode="json"),
        artifacts.PutOptions(
            kind=NORMATIVE_RUN_DISPOSITION_KIND,
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=NORMATIVE_RUN_DISPOSITION_KIND,
                version=NORMATIVE_RUN_DISPOSITION_SCHEMA,
            ),
        ),
    )
    return project_normative_run_disposition(
        store=store,
        owner=owner,
        disposition_ref=str(ref.artifact_id),
        compiled_run_ref=compiled_run_ref,
        evaluated_at=evaluated_at,
    )


def project_normative_run_disposition(
    *,
    store: artifacts.ArtifactStore,
    owner: NormativeValueScheduleOwner,
    disposition_ref: str,
    compiled_run_ref: str,
    evaluated_at: datetime,
) -> NormativeRunDisposition:
    """Recompute complete compiled membership and current S8 authority at every egress."""
    recorded = NormativeRunDisposition.model_validate(
        _read_normative_source(store, disposition_ref, kind=NORMATIVE_RUN_DISPOSITION_KIND)
    )
    if recorded.compiled_run_ref != compiled_run_ref:
        raise P20NormativeChoiceError("p20_normative_compiled_run_substitution")
    historical_times = {leaf.admitted_at for leaf in recorded.leaf_dispositions.values()}
    if len(historical_times) != 1:
        raise P20NormativeChoiceError("p20_normative_composition_time_mismatch")
    historical = _project_normative_composition(
        store=store,
        owner=owner,
        compiled_run_ref=compiled_run_ref,
        leaf_refs=recorded.leaf_disposition_refs,
        evaluated_at=next(iter(historical_times)),
    )
    if historical != recorded:
        raise P20NormativeChoiceError("p20_normative_composition_content_mismatch")
    current = _project_normative_composition(
        store=store,
        owner=owner,
        compiled_run_ref=compiled_run_ref,
        leaf_refs=recorded.leaf_disposition_refs,
        evaluated_at=evaluated_at,
    )
    return current.model_copy(update={"disposition_ref": disposition_ref})


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
    compiler_gateway: _DesignProblemGatewayClient | None,
    controller: RecursiveGenerationCycleController | None = None,
    budget_state: BudgetState,
    recursive_budget: RecursiveCycleBudget,
    root_evaluation_context: EvaluationExecutionContext | None = None,
    eval_safety_verifier: EvalSafetyVerifierPort | None = None,
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
    if eval_safety_verifier is None:
        raise DesignProblemAuthorityError(
            "eval_safety_verifier_not_established",
            "The production composition requires its verification-only EvalSafety port.",
        )
    if root_evaluation_context is None:
        raise DesignProblemAuthorityError(
            "eval_safety_execution_context_not_established",
            "The production composition requires an explicit EvalSafety execution context.",
        )
    from polisyos.runtime.quality.evaluation_safety import EvaluationExecutionContext
    from polisyos.runtime.quality.generation_cycle import FOUNDRY_VALUE_PORT_EVALUATOR_ID

    if not isinstance(root_evaluation_context, EvaluationExecutionContext):
        raise DesignProblemAuthorityError(
            "eval_safety_execution_context_not_canonical",
            "The root EvalSafety context must be the canonical typed contract.",
        )
    if root_evaluation_context.evaluator_owner_id != FOUNDRY_VALUE_PORT_EVALUATOR_ID:
        raise DesignProblemAuthorityError(
            "eval_safety_evaluator_owner_mismatch",
            "The root EvalSafety context must name the canonical Foundry value owner.",
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

    if controller is not None:
        if getattr(controller, "_authority_scope", None) != "production":
            raise DesignProblemAuthorityError(
                "recursive_controller_not_production_scoped",
                "The HTTP composition rejects contract-testing recursive controllers.",
            )
        if getattr(controller, "_promotion_runtime", None) is not promotion_runtime:
            raise DesignProblemAuthorityError(
                "recursive_controller_foreign_promotion_runtime",
                "The HTTP composition requires its container-owned promotion runtime.",
            )
        if getattr(controller, "_eval_safety_verifier", None) is not eval_safety_verifier:
            raise DesignProblemAuthorityError(
                "recursive_controller_eval_safety_verifier_mismatch",
                "The injected recursive controller must retain the exact EvalSafety verifier.",
            )
        if (
            getattr(controller, "_epoch_subject_authority", None)
            is not promotion_runtime.epoch_subject_authority
            or getattr(controller, "_epoch_validity_gate", None)
            is not promotion_runtime.epoch_validity_gate
            or getattr(controller, "_epoch_n9_evidence_resolver", None)
            is not promotion_runtime.epoch_n9_evidence_resolver
        ):
            raise DesignProblemAuthorityError(
                "recursive_controller_epoch_owner_binding_mismatch",
                "The HTTP composition derives every epoch dependency from one runtime.",
            )
        resolved_controller = controller
    else:
        resolved_controller = build_default_recursive_generation_cycle_controller(
            repo_root=repo_root,
            model_id=model_name,
            promotion_runtime=promotion_runtime,
            eval_safety_verifier=eval_safety_verifier,
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
        evaluation_contexts_by_node={root_ref: root_evaluation_context},
    )
    limitations: list[OpenWorldRiskPublicLimitation] = []
    seen_vector_refs: set[str] = set()
    for leaf in recursive_run.leaf_nodes:
        cycle_run = leaf.cycle_run
        if cycle_run is None:  # pragma: no cover - enforced by RecursiveCycleNode
            continue
        if cycle_run.promotion_port.reason == ("epoch_validity_refused:policy_admission_missing"):
            for limitation in project_pre_n9_open_world_limitations(
                run=cycle_run,
                design_problem=problem,
                resolver=promotion_runtime.resolver,
            ):
                vector_key = str(limitation.vector_artifact_ref.artifact_id)
                if vector_key in seen_vector_refs:
                    raise PublicExportRedactionError("open_world_projection_duplicate")
                seen_vector_refs.add(vector_key)
                limitations.append(limitation)
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
