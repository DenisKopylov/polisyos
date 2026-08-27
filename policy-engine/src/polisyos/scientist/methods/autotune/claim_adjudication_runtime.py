"""Scientist-owned admission and execution for academic claim adjudication."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    FileSystemCAS,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir.analytics.literature import (
    AdmittedClaimAdjudicationBatch,
    CausalCredibility,
    ClaimAdjudicationInputBatch,
    ClaimAdjudicationInputItem,
    ClaimAdjudicationResult,
    ClaimType,
    DesignFamily,
    RiskOfBias,
    SourceBasis,
    SupportStatus,
)

from .claim_adjudication import (
    CLAIM_ADJUDICATION_LOOP_ID,
    CLAIM_ADJUDICATION_SCHEMA_HINT,
    STRONG_DESIGN_FAMILIES,
    ClaimAdjudicationSearchConfig,
    aggregate_claim_rows,
    default_claim_adjudication_promotion_policy,
    select_prompt_variant,
)
from .models import BenchmarkEvaluation, ChampionPointer
from .registry import ChampionRegistry

if TYPE_CHECKING:
    from polisyos.data_forge.read_api.academic import AcademicBatchConfig

_INPUT_KIND = "data_forge.academic.claim_adjudication.input_batch"
_INPUT_SCHEMA = "polisyos.ir.analytics.literature.ClaimAdjudicationInputBatch"
_INPUT_PRODUCER = "polisyos.data_forge.domains.academic.batch.claim_adjudicator"
_EVALUATION_PRODUCER = "polisyos.scientist.methods.autotune.benchmark_evaluator"
_RESULT_KIND = "scientist.claim_adjudication.admitted_batch"
_RESULT_SCHEMA = "polisyos.ir.analytics.literature.AdmittedClaimAdjudicationBatch"
_RESULT_PRODUCER = "polisyos.scientist.methods.autotune.claim_adjudication_runtime"


class ClaimAdjudicationJSONClient(Protocol):
    """Narrow transport protocol for candidate evidence assessment."""

    async def chat_json(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float,
    ) -> object: ...


class AdmittedClaimAdjudicationChampion(BaseModel):
    """Champion whose evaluation and promotion policy were independently replayed."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    config: ClaimAdjudicationSearchConfig
    candidate_ref: ArtifactRef
    evaluation_ref: ArtifactRef
    pointer_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ClaimAdjudicationRuntimeOutcome(BaseModel):
    """Fail-closed outcome for one admitted claim-adjudication execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["completed", "blocked"]
    result_ref: ArtifactRef | None = None
    blockers: tuple[str, ...] = ()
    input_claims: int = Field(default=0, ge=0)
    published_claims: int = Field(default=0, ge=0)


def _component(value: object) -> str:
    return str(value)


def _pointer_sha256(pointer: ChampionPointer) -> str:
    payload = json.dumps(
        pointer.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _enum_value(enum_cls: type[Any], value: object, fallback: Any) -> Any:
    normalized = str(value or "").strip().lower().replace(" ", "_")
    try:
        return enum_cls(normalized)
    except (TypeError, ValueError):
        return fallback


def _score(value: object, fallback: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        numeric = fallback
    return max(0.0, min(1.0, numeric))


def _parsed_payload(response: object) -> dict[str, Any]:
    if isinstance(response, dict):
        payload = response
    else:
        status = getattr(response, "http_status", 200)
        if int(status or 0) < 200 or int(status or 0) >= 300:
            raise ValueError(f"claim adjudication provider returned HTTP {status}")
        payload = getattr(response, "parsed", None)
    if not isinstance(payload, dict):
        raise ValueError("claim adjudication provider did not return a JSON object")
    return payload


def _policy_publishable(
    item: ClaimAdjudicationInputItem,
    result: ClaimAdjudicationResult,
    config: ClaimAdjudicationSearchConfig,
) -> bool:
    """Compute publication authority only from admitted evidence and Scientist policy."""
    return bool(
        item.source_basis == SourceBasis.FULLTEXT
        and not item.intra_paper_contradiction
        and bool(item.supporting_spans)
        and bool(item.method_spans)
        and result.design_family.value in STRONG_DESIGN_FAMILIES
        and result.causal_credibility in set(config.publishable_credibility_allowlist)
        and result.risk_of_bias in {RiskOfBias.LOW, RiskOfBias.MODERATE}
        and result.support_status == SupportStatus.SUPPORTED
        and result.claim_validity_score >= config.high_confidence_validity_threshold
        and result.adjudication_confidence
        >= config.high_confidence_confidence_threshold
    )


def assert_claim_adjudication_authority_purpose(
    batch: AdmittedClaimAdjudicationBatch,
    *,
    purpose: str,
) -> None:
    """Reject use of execution results outside their declared authority purpose."""
    if purpose not in set(batch.authoritative_for):
        raise ValueError(f"claim adjudication receipt is not authoritative for {purpose}")


class ClaimAdjudicationRuntime:
    """Admit a promoted champion and produce content-bound publishability receipts."""

    def __init__(self, *, store: FileSystemCAS, registry: ChampionRegistry) -> None:
        self._store = store
        self._registry = registry

    def admit_champion(self) -> AdmittedClaimAdjudicationChampion:
        """Replay promotion predicates instead of trusting a registry declaration."""
        pointer = self._registry.get(CLAIM_ADJUDICATION_LOOP_ID)
        if pointer is None:
            raise ValueError("claim_adjudication_champion_missing")
        if bool(pointer.metadata.get("seeded_baseline")):
            raise ValueError("claim_adjudication_seeded_baseline_not_admitted")
        if pointer.loop_id != CLAIM_ADJUDICATION_LOOP_ID:
            raise ValueError("claim_adjudication_pointer_loop_mismatch")

        candidate_manifest = self._store.get_manifest(pointer.candidate_ref.artifact_id)
        if candidate_manifest.kind != "scientist.autotune.claim_adjudication.candidate":
            raise ValueError("claim_adjudication_candidate_kind_mismatch")
        config = ClaimAdjudicationSearchConfig.model_validate(
            from_canonical_bytes(self._store.get_bytes(pointer.candidate_ref.artifact_id))
        )
        if config.loop_id != pointer.loop_id:
            raise ValueError("claim_adjudication_candidate_loop_mismatch")
        if config.search_space_version != pointer.search_space_version:
            raise ValueError("claim_adjudication_search_space_mismatch")

        evaluation_manifest = self._store.get_manifest(pointer.evaluation_ref.artifact_id)
        if (
            evaluation_manifest.producer is None
            or _component(evaluation_manifest.producer.component) != _EVALUATION_PRODUCER
        ):
            raise ValueError("claim_adjudication_evaluation_provenance_missing")
        candidate_lineage = [
            str(item.artifact_id)
            for item in evaluation_manifest.inputs
            if item.role == "candidate"
        ]
        if candidate_lineage != [str(pointer.candidate_ref.artifact_id)]:
            raise ValueError("claim_adjudication_evaluation_lineage_mismatch")
        evaluation = BenchmarkEvaluation.model_validate(
            from_canonical_bytes(self._store.get_bytes(pointer.evaluation_ref.artifact_id))
        )
        if evaluation.loop_id != pointer.loop_id:
            raise ValueError("claim_adjudication_evaluation_loop_mismatch")
        if evaluation.candidate_ref.artifact_id != pointer.candidate_ref.artifact_id:
            raise ValueError("claim_adjudication_evaluation_candidate_mismatch")
        if evaluation.suite_version != pointer.suite_version:
            raise ValueError("claim_adjudication_suite_version_mismatch")

        policy = default_claim_adjudication_promotion_policy()
        if pointer.metadata.get("promoted_by_policy") != policy.model_dump(mode="json"):
            raise ValueError("claim_adjudication_promotion_policy_mismatch")
        if pointer.metadata.get("compare_split") != policy.compare_split.value:
            raise ValueError("claim_adjudication_compare_split_mismatch")
        if not evaluation.promotable:
            raise ValueError("claim_adjudication_evaluation_not_promotable")
        for guardrail in policy.required_guardrails:
            if not bool(evaluation.guardrails.get(guardrail)):
                raise ValueError(f"claim_adjudication_guardrail_failed:{guardrail}")
        if evaluation.sample_count(split=policy.compare_split) < policy.min_sample_count:
            raise ValueError("claim_adjudication_sample_count_insufficient")
        primary = evaluation.primary_value(
            split=policy.compare_split,
            metric=policy.primary_metric,
        )
        if primary is None:
            raise ValueError("claim_adjudication_primary_metric_missing")
        expected_metrics = evaluation.metrics_for_split(policy.compare_split)
        if pointer.metrics != expected_metrics:
            raise ValueError("claim_adjudication_pointer_metrics_mismatch")

        return AdmittedClaimAdjudicationChampion(
            config=config,
            candidate_ref=pointer.candidate_ref,
            evaluation_ref=pointer.evaluation_ref,
            pointer_sha256=_pointer_sha256(pointer),
        )

    def _load_input(self, raw_input_ref: ArtifactRef) -> ClaimAdjudicationInputBatch:
        manifest = self._store.get_manifest(raw_input_ref.artifact_id)
        if manifest.kind != _INPUT_KIND:
            raise ValueError("claim_adjudication_input_kind_mismatch")
        if manifest.artifact_schema is None or manifest.artifact_schema.name != _INPUT_SCHEMA:
            raise ValueError("claim_adjudication_input_schema_mismatch")
        if manifest.producer is None or _component(manifest.producer.component) != _INPUT_PRODUCER:
            raise ValueError("claim_adjudication_input_producer_mismatch")
        batch = ClaimAdjudicationInputBatch.model_validate(
            from_canonical_bytes(self._store.get_bytes(raw_input_ref.artifact_id))
        )
        lineage = {item.role: str(item.artifact_id) for item in manifest.inputs}
        if len(lineage) != len(manifest.inputs):
            raise ValueError("claim_adjudication_input_duplicate_lineage_role")
        expected_lineage = {"extraction_source": batch.source_artifact_ref}
        if batch.retraction_artifact_ref is not None:
            expected_lineage["retraction_source"] = batch.retraction_artifact_ref
        if lineage != expected_lineage:
            raise ValueError("claim_adjudication_input_lineage_mismatch")
        return batch

    async def _adjudicate_item(
        self,
        item: ClaimAdjudicationInputItem,
        *,
        config: ClaimAdjudicationSearchConfig,
        client: ClaimAdjudicationJSONClient,
        model: str,
        temperature: float,
    ) -> ClaimAdjudicationResult:
        passes: list[ClaimAdjudicationResult] = []
        item_payload = item.model_dump(mode="json")
        for pass_index in range(config.passes):
            prompt = (
                f"{select_prompt_variant(config, pass_index)}\n\n"
                f"Required JSON schema:\n{CLAIM_ADJUDICATION_SCHEMA_HINT}\n\n"
                "Admitted claim evidence:\n"
                f"{json.dumps(item_payload, ensure_ascii=False, sort_keys=True)}"
            )
            parsed = _parsed_payload(
                await client.chat_json(
                    model=model,
                    prompt=prompt,
                    temperature=temperature,
                )
            )
            result = ClaimAdjudicationResult(
                claim_id=item.claim_id,
                openalex_id=item.openalex_id,
                cause_variable=item.cause_variable,
                effect_variable=item.effect_variable,
                source_basis=item.source_basis,
                paper_asserts_causality_score=_score(
                    parsed.get("paper_asserts_causality_score"), 0.0
                ),
                claim_type=_enum_value(
                    ClaimType,
                    parsed.get("claim_type"),
                    ClaimType.ASSOCIATION,
                ),
                design_family=_enum_value(
                    DesignFamily,
                    parsed.get("design_family"),
                    item.design_family_hint,
                ),
                causal_credibility=_enum_value(
                    CausalCredibility,
                    parsed.get("causal_credibility"),
                    CausalCredibility.UNCLEAR,
                ),
                risk_of_bias=_enum_value(
                    RiskOfBias,
                    parsed.get("risk_of_bias"),
                    RiskOfBias.UNCLEAR,
                ),
                support_status=_enum_value(
                    SupportStatus,
                    parsed.get("support_status"),
                    SupportStatus.INSUFFICIENT,
                ),
                claim_validity_score=_score(parsed.get("claim_validity_score"), 0.0),
                adjudication_confidence=_score(
                    parsed.get("adjudication_confidence"), 0.0
                ),
                publishable_edge=False,
                adjudication_notes=str(parsed.get("adjudication_notes") or "")[:800],
                intra_paper_contradiction=item.intra_paper_contradiction,
            )
            passes.append(
                result.model_copy(
                    update={
                        "publishable_edge": _policy_publishable(item, result, config),
                    }
                )
            )
        aggregate = aggregate_claim_rows(passes, config)
        return aggregate.model_copy(
            update={
                "publishable_edge": _policy_publishable(item, aggregate, config),
                "intra_paper_contradiction": item.intra_paper_contradiction,
            }
        )

    async def adjudicate(
        self,
        raw_input_ref: ArtifactRef,
        *,
        client: ClaimAdjudicationJSONClient,
        model: str,
        temperature: float = 0.0,
    ) -> ClaimAdjudicationRuntimeOutcome:
        """Run the real admitted path or return a typed fail-closed outcome."""
        try:
            champion = self.admit_champion()
            batch = self._load_input(raw_input_ref)
            results = [
                await self._adjudicate_item(
                    item,
                    config=champion.config,
                    client=client,
                    model=model,
                    temperature=temperature,
                )
                for item in batch.items
            ]
            admitted = AdmittedClaimAdjudicationBatch(
                raw_input_ref=str(raw_input_ref.artifact_id),
                candidate_ref=str(champion.candidate_ref.artifact_id),
                evaluation_ref=str(champion.evaluation_ref.artifact_id),
                champion_pointer_sha256=champion.pointer_sha256,
                input_claim_ids=[item.claim_id for item in batch.items],
                results=results,
            )
            result_ref = self._store.put_json(
                admitted,
                ArtifactWriteOptions(
                    kind=_RESULT_KIND,
                    media_type="application/json",
                    schema=SchemaInfo(name=_RESULT_SCHEMA, version=admitted.schema_version),
                    producer=ProducerInfo(component=_RESULT_PRODUCER, version="1.0"),
                    inputs=[
                        InputRef(artifact_id=raw_input_ref.artifact_id, role="raw_input"),
                        InputRef(
                            artifact_id=champion.candidate_ref.artifact_id,
                            role="candidate",
                        ),
                        InputRef(
                            artifact_id=champion.evaluation_ref.artifact_id,
                            role="evaluation",
                        ),
                    ],
                ),
                canon_spec=CanonSpec(forbid_floats=False),
            )
        except Exception as exc:
            return ClaimAdjudicationRuntimeOutcome(
                status="blocked",
                blockers=(str(exc),),
            )
        return ClaimAdjudicationRuntimeOutcome(
            status="completed",
            result_ref=result_ref,
            input_claims=len(batch.items),
            published_claims=sum(result.publishable_edge for result in results),
        )


async def run_academic_claim_adjudication(
    config: AcademicBatchConfig,
    *,
    client: ClaimAdjudicationJSONClient,
    store: FileSystemCAS | None = None,
    registry: ChampionRegistry | None = None,
) -> dict[str, int | float]:
    """Compose the supported DataForge transport with Scientist authority."""
    from polisyos.data_forge.read_api.academic import (
        materialize_claim_adjudication_result,
        produce_claim_adjudication_input,
    )

    active_store = store or FileSystemCAS(config.claim_adjudication_cas_root)
    active_registry = registry or ChampionRegistry(
        root=config.claim_adjudication_registry_root,
        store=active_store,
    )
    raw_input_ref = produce_claim_adjudication_input(config, store=active_store)
    outcome = await ClaimAdjudicationRuntime(
        store=active_store,
        registry=active_registry,
    ).adjudicate(
        raw_input_ref,
        client=client,
        model=config.llm_model,
        temperature=config.llm_temperature,
    )
    if outcome.status != "completed" or outcome.result_ref is None:
        raise RuntimeError(
            "claim adjudication blocked: " + "; ".join(outcome.blockers)
        )
    return materialize_claim_adjudication_result(
        config,
        outcome.result_ref,
        store=active_store,
    )


__all__ = [
    "AdmittedClaimAdjudicationChampion",
    "ClaimAdjudicationJSONClient",
    "ClaimAdjudicationRuntime",
    "ClaimAdjudicationRuntimeOutcome",
    "assert_claim_adjudication_authority_purpose",
    "run_academic_claim_adjudication",
]
